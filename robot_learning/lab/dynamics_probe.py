"""Deterministic saturated-command dynamics measurement for the two-joint arm.

This module deliberately measures the embodied MuJoCo model only.  It does not
create an environment, train a policy, or evaluate a learned policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


# The scenario's fixed policy interval is ten 0.002 s MuJoCo integration
# steps.  Keeping this local to the probe documents the sampling protocol
# without changing the human-owned task constants.
FRAME_SKIP = 10
TOTAL_DURATION_SECONDS = 5.0
PULSE_DURATION_SECONDS = 1.0
SETTLING_VELOCITY_THRESHOLD_RAD_PER_S = 0.05
MOVING_BODY_NAMES = ("upper_arm", "forearm")
END_EFFECTOR_SITE_NAME = "end_effector"


def _finite_float(value: Any, description: str) -> float:
    """Convert a scalar to JSON-safe float and reject invalid simulation data."""

    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{description} is not finite: {result!r}")
    return result


def _finite_vector(values: Any, description: str) -> list[float]:
    """Convert a numeric vector to JSON-safe floats and reject invalid values."""

    array = np.asarray(values, dtype=float).reshape(-1)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{description} contains a non-finite value")
    return [float(value) for value in array]


def _sample_count(duration_seconds: float, control_interval_seconds: float) -> int:
    """Return an exact integer number of control samples for a requested duration."""

    samples = int(round(duration_seconds / control_interval_seconds))
    represented_duration = samples * control_interval_seconds
    if not np.isclose(represented_duration, duration_seconds, rtol=0.0, atol=1e-12):
        raise ValueError(
            "probe duration is not an integral number of control intervals: "
            f"duration={duration_seconds}, interval={control_interval_seconds}"
        )
    return samples


def _object_name(
    model: mujoco.MjModel, object_type: Any, object_id: int, description: str
) -> str | None:
    """Return an object's MuJoCo name, preserving an explicitly unnamed object."""

    name = mujoco.mj_id2name(model, object_type, object_id)
    if name is None:
        return None
    if not name:
        raise ValueError(f"{description} has an empty MuJoCo name")
    return str(name)


def _joint_limit_margins(
    model: mujoco.MjModel, data: mujoco.MjData
) -> list[float]:
    """Return distance to the nearest declared limit for every hinge joint."""

    margins: list[float] = []
    for joint_id in range(int(model.njnt)):
        if not bool(model.jnt_limited[joint_id]):
            raise ValueError(
                f"joint {joint_id} has no declared limits; "
                "the probe requires joint-limit margins"
            )
        qpos_address = int(model.jnt_qposadr[joint_id])
        lower, upper = (
            float(model.jnt_range[joint_id, 0]),
            float(model.jnt_range[joint_id, 1]),
        )
        position = float(data.qpos[qpos_address])
        margins.append(
            _finite_float(
                min(position - lower, upper - position),
                f"joint {joint_id} limit margin",
            )
        )
    return margins


def _model_section(
    model: mujoco.MjModel, control_interval_seconds: float
) -> dict[str, Any]:
    """Describe the loaded model quantities used by the probe."""

    joint_names = [
        _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id, f"joint {joint_id}")
        for joint_id in range(int(model.njnt))
    ]
    actuator_names = [
        _object_name(
            model,
            mujoco.mjtObj.mjOBJ_ACTUATOR,
            actuator_id,
            f"actuator {actuator_id}",
        )
        for actuator_id in range(int(model.nu))
    ]

    body_records: list[dict[str, Any]] = []
    for body_name in MOVING_BODY_NAMES:
        body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
        if body_id < 0:
            raise ValueError(
                f"authoritative model is missing moving body {body_name!r}"
            )
        body_records.append(
            {
                "name": body_name,
                "id": int(body_id),
                "mass_kg": _finite_float(
                    model.body_mass[body_id], f"{body_name} mass"
                ),
                "inertia_kg_m2": _finite_vector(
                    model.body_inertia[body_id], f"{body_name} inertia"
                ),
            }
        )

    dof_damping = _finite_vector(model.dof_damping, "DOF damping")
    dof_armature = _finite_vector(model.dof_armature, "DOF armature")
    actuator_records: list[dict[str, Any]] = []
    for actuator_id in range(int(model.nu)):
        record: dict[str, Any] = {
            "id": actuator_id,
            "ctrl_range": _finite_vector(
                model.actuator_ctrlrange[actuator_id],
                f"actuator {actuator_id} control range",
            ),
            "gear": _finite_vector(
                model.actuator_gear[actuator_id], f"actuator {actuator_id} gear"
            ),
        }
        if actuator_names[actuator_id] is not None:
            record["name"] = actuator_names[actuator_id]
        actuator_records.append(record)

    section: dict[str, Any] = {
        "xml_authority": (
            "contracts.robots.two_joint_arm.TWO_JOINT_ARM_XML_PATH"
        ),
        "timestep_seconds": _finite_float(
            model.opt.timestep, "MuJoCo model timestep"
        ),
        "joint_count": int(model.njnt),
        "dof_count": int(model.nv),
        "actuator_count": int(model.nu),
        "dof_damping": dof_damping,
        "dof_damping_units": "N m s/rad",
        "dof_armature": dof_armature,
        "dof_armature_units": "kg m^2",
        "moving_bodies": body_records,
        "actuators": actuator_records,
        "frame_skip": FRAME_SKIP,
        "control_interval_seconds": _finite_float(
            control_interval_seconds, "control interval"
        ),
    }
    if all(name is not None for name in joint_names):
        section["joint_names"] = [str(name) for name in joint_names]
    return section


def _reset_data(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    """Reset state and explicitly establish the probe's zero initial condition."""

    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _trace_sample(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    control_sample: int,
    command: Sequence[float],
    site_id: int,
) -> dict[str, Any]:
    """Capture one boundary after the held command has been integrated."""

    return {
        "control_sample": control_sample,
        "time_seconds": _finite_float(data.time, "trace time"),
        "command": _finite_vector(command, "trace command"),
        "qpos_rad": _finite_vector(data.qpos, "trace qpos"),
        "qvel_rad_per_s": _finite_vector(data.qvel, "trace qvel"),
        "qacc_rad_per_s2": _finite_vector(data.qacc, "trace qacc"),
        "qfrc_actuator_nm": _finite_vector(
            data.qfrc_actuator, "trace actuator generalized force"
        ),
        "end_effector_position_m": _finite_vector(
            data.site_xpos[site_id], "trace end-effector position"
        ),
        "joint_limit_margin_rad": _joint_limit_margins(model, data),
    }


def _settling_sample(
    traces: Sequence[dict[str, Any]], first_sample_to_check: int
) -> int | None:
    """Find the first one-indexed trace sample below the velocity threshold."""

    for trace in traces:
        if int(trace["control_sample"]) < first_sample_to_check:
            continue
        velocities = np.asarray(trace["qvel_rad_per_s"], dtype=float)
        if float(np.max(np.abs(velocities))) <= SETTLING_VELOCITY_THRESHOLD_RAD_PER_S:
            return int(trace["control_sample"])
    return None


def _response_summary(
    traces: Sequence[dict[str, Any]],
    first_sample_to_check: int,
    settling_reference: str,
) -> dict[str, Any]:
    """Summarize extrema, final state, limits, and the settling-threshold crossing."""

    qvel = np.asarray([trace["qvel_rad_per_s"] for trace in traces], dtype=float)
    qacc = np.asarray([trace["qacc_rad_per_s2"] for trace in traces], dtype=float)
    actuator_force = np.asarray(
        [trace["qfrc_actuator_nm"] for trace in traces], dtype=float
    )
    qpos = np.asarray([trace["qpos_rad"] for trace in traces], dtype=float)
    limit_margins = np.asarray(
        [trace["joint_limit_margin_rad"] for trace in traces], dtype=float
    )
    if not all(
        np.all(np.isfinite(values))
        for values in (qvel, qacc, actuator_force, qpos, limit_margins)
    ):
        raise ValueError("response trace contains a non-finite summary value")

    final_trace = traces[-1]
    settling_sample = _settling_sample(traces, first_sample_to_check)
    return {
        "peak_abs_joint_velocity_rad_per_s": _finite_float(
            np.max(np.abs(qvel)), "peak joint velocity"
        ),
        "peak_abs_joint_acceleration_rad_per_s2": _finite_float(
            np.max(np.abs(qacc)), "peak joint acceleration"
        ),
        "peak_abs_actuator_generalized_force_nm": _finite_float(
            np.max(np.abs(actuator_force)), "peak actuator generalized force"
        ),
        "final_joint_state": {
            "qpos_rad": [float(value) for value in final_trace["qpos_rad"]],
            "qvel_rad_per_s": [float(value) for value in final_trace["qvel_rad_per_s"]],
        },
        "maximum_abs_joint_position_rad": _finite_float(
            np.max(np.abs(qpos)), "maximum absolute joint position"
        ),
        "minimum_joint_limit_margin_rad": _finite_float(
            np.min(limit_margins), "minimum joint-limit margin"
        ),
        "first_control_sample_below_settling_velocity": settling_sample,
        "settling_threshold_crossing_found": settling_sample is not None,
        "settling_reference": settling_reference,
    }


def _run_response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    name: str,
    commands: Sequence[Sequence[float]],
    frame_skip: int,
    site_id: int,
    pulse_samples: int | None = None,
) -> dict[str, Any]:
    """Reset and run one deterministic held-command protocol."""

    if len(commands) == 0:
        raise ValueError(f"response {name!r} has no control commands")
    _reset_data(model, data)
    traces: list[dict[str, Any]] = []
    for control_sample, command in enumerate(commands, start=1):
        command_array = np.asarray(command, dtype=float)
        if command_array.shape != (int(model.nu),):
            raise ValueError(
                f"response {name!r} command has shape {command_array.shape}; "
                f"expected {(int(model.nu),)}"
            )
        if not np.all(np.isfinite(command_array)):
            raise ValueError(f"response {name!r} contains a non-finite command")
        data.ctrl[:] = command_array
        mujoco.mj_step(model, data, nstep=frame_skip)
        # mj_step leaves some forward-derived fields at the state preceding
        # its final integration update. Refresh them so every recorded field
        # describes the same control-boundary state as qpos, qvel, and time.
        mujoco.mj_forward(model, data)
        traces.append(
            _trace_sample(
                model, data, control_sample, command_array, site_id
            )
        )

    if pulse_samples is None:
        first_sample_to_check = 1
        settling_reference = "after_command_start"
    else:
        first_sample_to_check = pulse_samples + 1
        settling_reference = "after_pulse"

    result: dict[str, Any] = {
        "name": name,
        "control_sample_count": len(commands),
        "duration_seconds": _finite_float(data.time, f"{name} duration"),
        "reset_state": {
            "qpos_rad": [0.0 for _ in range(int(model.nq))],
            "qvel_rad_per_s": [0.0 for _ in range(int(model.nv))],
        },
        "trace_boundary": (
            "Each row is recorded after its command has been held for "
            f"{frame_skip} MuJoCo integration steps."
        ),
        "traces": traces,
        "summary": _response_summary(
            traces, first_sample_to_check, settling_reference
        ),
    }
    if pulse_samples is not None:
        result["pulse_duration_seconds"] = _finite_float(
            pulse_samples * float(model.opt.timestep) * frame_skip,
            f"{name} pulse duration",
        )
        result["pulse_control_sample_count"] = pulse_samples
    return result


def run_probe(output_path: Path) -> None:
    """Load the authoritative XML, run all protocols, and write one JSON artifact."""

    xml_path = Path(TWO_JOINT_ARM_XML_PATH)
    if not xml_path.is_file():
        raise FileNotFoundError(
            f"authoritative two-joint-arm XML does not exist: {xml_path}"
        )

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    if int(model.njnt) != 2 or int(model.nv) != 2 or int(model.nu) != 2:
        raise ValueError(
            "the authoritative probe expects exactly two hinge joints and "
            f"two actuators, got njnt={model.njnt}, nv={model.nv}, nu={model.nu}"
        )
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, END_EFFECTOR_SITE_NAME
    )
    if site_id < 0:
        raise ValueError(
            f"authoritative model is missing site {END_EFFECTOR_SITE_NAME!r}"
        )

    timestep_seconds = _finite_float(model.opt.timestep, "MuJoCo model timestep")
    control_interval_seconds = timestep_seconds * FRAME_SKIP
    total_samples = _sample_count(
        TOTAL_DURATION_SECONDS, control_interval_seconds
    )
    pulse_samples = _sample_count(PULSE_DURATION_SECONDS, control_interval_seconds)
    if pulse_samples >= total_samples:
        raise ValueError("pulse duration must be shorter than the total response")

    data = mujoco.MjData(model)
    commands: list[tuple[str, list[list[float]], int | None]] = [
        (
            "constant_[1,0]",
            [[1.0, 0.0] for _ in range(total_samples)],
            None,
        ),
        (
            "constant_[0,1]",
            [[0.0, 1.0] for _ in range(total_samples)],
            None,
        ),
        (
            "constant_[1,1]",
            [[1.0, 1.0] for _ in range(total_samples)],
            None,
        ),
        (
            "constant_[-1,1]",
            [[-1.0, 1.0] for _ in range(total_samples)],
            None,
        ),
        (
            "pulse_[1,0]_then_[0,0]",
            [[1.0, 0.0] for _ in range(pulse_samples)]
            + [[0.0, 0.0] for _ in range(total_samples - pulse_samples)],
            pulse_samples,
        ),
    ]
    responses = [
        _run_response(
            model,
            data,
            name=name,
            commands=protocol_commands,
            frame_skip=FRAME_SKIP,
            site_id=site_id,
            pulse_samples=pulse_sample_count,
        )
        for name, protocol_commands, pulse_sample_count in commands
    ]

    artifact: dict[str, Any] = {
        "measurement": (
            "Deterministic zero-state saturated-command dynamics probe; "
            "not a training run or policy evaluation."
        ),
        "model": _model_section(model, control_interval_seconds),
        "analysis": {
            "units": {
                "time": "seconds",
                "joint_position": "radians",
                "joint_velocity": "radians per second",
                "joint_acceleration": "radians per second squared",
                "actuator_generalized_force": "newton metres",
                "end_effector_position": "metres",
                "joint_limit_margin": "radians to the nearest declared limit",
                "body_mass": "kilograms",
                "body_inertia": "kilogram metres squared",
            },
            "settling_velocity_threshold_rad_per_s": (
                SETTLING_VELOCITY_THRESHOLD_RAD_PER_S
            ),
            "settling_threshold_definition": (
                "The first recorded control boundary at or below the threshold "
                "in every joint's absolute velocity. For constant protocols "
                "the search starts at command sample 1; for the pulse it "
                "starts at the first zero-command sample after the pulse. "
                "This is an instantaneous threshold crossing, not a claim of "
                "sustained equilibrium. A false "
                "settling_threshold_crossing_found value means no such "
                "boundary was observed in the recorded duration."
            ),
            "total_duration_seconds": TOTAL_DURATION_SECONDS,
            "pulse_duration_seconds": PULSE_DURATION_SECONDS,
            "trace_samples_are_one_indexed": True,
            "zero_order_hold": (
                "Each command is written once per control sample and held "
                f"for exactly {FRAME_SKIP} integration steps."
            ),
            "summary_peak_definition": (
                "Peak values are maxima of absolute recorded joint or "
                "generalized-force components over control-boundary traces."
            ),
        },
        "responses": responses,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(artifact, output_file, indent=2, allow_nan=False)
        output_file.write("\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic two-joint-arm dynamics probe."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path for the JSON measurement artifact",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point for ``python -m robot_learning.lab.dynamics_probe``."""

    arguments = _parse_args()
    run_probe(arguments.output)


if __name__ == "__main__":
    main()
