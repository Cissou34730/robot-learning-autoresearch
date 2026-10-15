"""Deterministic open-loop dynamics measurements for the official arm.

This is a measurement instrument, rather than an environment or a policy
evaluation.  It compiles the protected model directly and records the state at
every MuJoCo physics step while a control is held for one official control
interval.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from contracts.task_spec import FRAME_SKIP


SCHEMA_VERSION = "1.0"
END_EFFECTOR_SITE_NAME = "end_effector"
JOINT_COUNT = 2
ACTUATOR_COUNT = 2
DEFAULT_INTERVALS = 4
DEFAULT_DECAY_INTERVALS = 8
MAX_INTERVALS = 100

ACTUATOR_FORCE_UNITS = {
    "unit": "N*m",
    "space": "actuator",
    "meaning": (
        "scalar motor force in actuator space for the compiled hinge motor, "
        "before the transmission gear maps it to a joint torque"
    ),
}
GENERALIZED_FORCE_UNITS = {
    "unit": "N*m",
    "space": "joint",
    "meaning": "generalized actuator torque for a hinge joint in joint space",
}
JOINT_DYNAMICS_UNITS = {
    "dof_damping": "N*m*s/rad",
    "dof_armature": "kg*m^2",
    "dof_frictionloss": "N*m",
}


class DynamicsMeasurementError(RuntimeError):
    """Raised when the compiled model does not expose required data."""


def _required_attribute(owner: Any, name: str) -> Any:
    """Return a required public MuJoCo attribute without substituting values."""

    try:
        return getattr(owner, name)
    except AttributeError as exc:
        raise DynamicsMeasurementError(
            f"required public MuJoCo field {name!r} is unavailable"
        ) from exc


def _as_finite_array(owner: Any, name: str) -> np.ndarray:
    value = np.asarray(_required_attribute(owner, name), dtype=np.float64)
    if not np.all(np.isfinite(value)):
        raise DynamicsMeasurementError(
            f"required MuJoCo field {name!r} contains a non-finite value"
        )
    return value


def _as_json(value: Any) -> Any:
    """Convert NumPy and MuJoCo scalar values to JSON-compatible values."""

    if isinstance(value, np.ndarray):
        return [_as_json(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _as_json(value.item())
    if isinstance(value, (list, tuple)):
        return [_as_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _object_name(model: mujoco.MjModel, object_type: Any, object_id: int) -> str:
    name = mujoco.mj_id2name(model, object_type, object_id)
    if name is None:
        raise DynamicsMeasurementError(
            f"required name for MuJoCo object id {object_id} is unavailable"
        )
    return str(name)


def _enum_metadata(value: Any) -> dict[str, Any]:
    try:
        numeric_value: int | str = int(value)
    except (TypeError, ValueError):
        numeric_value = str(value)
    return {"value": numeric_value, "name": str(value)}


def _require_dimensions(model: mujoco.MjModel) -> None:
    for field, expected in (
        ("njnt", JOINT_COUNT),
        ("nu", ACTUATOR_COUNT),
        ("nq", JOINT_COUNT),
        ("nv", JOINT_COUNT),
    ):
        actual = int(_required_attribute(model, field))
        if actual != expected:
            raise DynamicsMeasurementError(
                f"official model must have {expected} {field}, found {actual}"
            )


def _model_metadata(
    model: mujoco.MjModel, frame_skip: int
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], int]:
    _require_dimensions(model)
    opt = _required_attribute(model, "opt")
    timestep = float(_required_attribute(opt, "timestep"))
    if not np.isfinite(timestep) or timestep <= 0.0:
        raise DynamicsMeasurementError("model timestep must be finite and positive")

    joint_ranges = _as_finite_array(model, "jnt_range")
    joint_axes = _as_finite_array(model, "jnt_axis")
    body_mass = _as_finite_array(model, "body_mass")
    body_inertia = _as_finite_array(model, "body_inertia")
    joint_qpos_addresses = _required_attribute(model, "jnt_qposadr")
    joint_dof_addresses = _required_attribute(model, "jnt_dofadr")
    joint_body_ids = _required_attribute(model, "jnt_bodyid")
    dof_damping = _as_finite_array(model, "dof_damping")
    dof_armature = _as_finite_array(model, "dof_armature")
    dof_frictionloss = _as_finite_array(model, "dof_frictionloss")
    joint_types = _required_attribute(model, "jnt_type")

    joints: list[dict[str, Any]] = []
    for joint_id in range(JOINT_COUNT):
        qpos_address = int(joint_qpos_addresses[joint_id])
        dof_address = int(joint_dof_addresses[joint_id])
        body_id = int(joint_body_ids[joint_id])
        if qpos_address < 0 or dof_address < 0:
            raise DynamicsMeasurementError("joint addresses must be non-negative")
        joints.append(
            {
                "id": joint_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "type": int(joint_types[joint_id]),
                "range_radians": joint_ranges[joint_id].tolist(),
                "axis": joint_axes[joint_id].tolist(),
                "qpos_address": qpos_address,
                "dof_address": dof_address,
                "body": {
                    "id": body_id,
                    "name": _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                    "mass_kg": float(body_mass[body_id]),
                    "inertia_kg_m2": body_inertia[body_id].tolist(),
                },
                "dof_damping": float(dof_damping[dof_address]),
                "dof_armature": float(dof_armature[dof_address]),
                "dof_frictionloss": float(dof_frictionloss[dof_address]),
                "field_units": dict(JOINT_DYNAMICS_UNITS),
            }
        )

    ctrl_ranges = _as_finite_array(model, "actuator_ctrlrange")
    actuator_gears = _as_finite_array(model, "actuator_gear")
    actuator_trn_ids = _required_attribute(model, "actuator_trnid")
    if (
        ctrl_ranges.ndim != 2
        or ctrl_ranges.shape[0] < ACTUATOR_COUNT
        or ctrl_ranges.shape[1] < 2
        or actuator_gears.ndim != 2
        or actuator_gears.shape[0] < ACTUATOR_COUNT
        or actuator_gears.shape[1] < 1
        or np.asarray(actuator_trn_ids).ndim != 2
        or np.asarray(actuator_trn_ids).shape[0] < ACTUATOR_COUNT
        or np.asarray(actuator_trn_ids).shape[1] < 1
    ):
        raise DynamicsMeasurementError(
            "actuator control ranges, gears, or transmissions have "
            "insufficient dimensions"
        )
    actuator_names: list[dict[str, Any]] = []
    for actuator_id in range(ACTUATOR_COUNT):
        low, high = ctrl_ranges[actuator_id, :2]
        if not low < 0.0 < high:
            raise DynamicsMeasurementError(
                f"actuator {actuator_id} does not support both command directions"
            )
        identifier = f"actuator_{actuator_id}"
        actuator_names.append(
            {
                "id": actuator_id,
                "name": identifier,
                "identifier": identifier,
                "identifier_metadata": {
                    "source": "index-derived",
                    "compiled_name": None,
                    "reason": "compiled actuator name is absent",
                },
                "ctrl_range": [float(low), float(high)],
                "gear": actuator_gears[actuator_id].tolist(),
                "transmission_target_id": int(actuator_trn_ids[actuator_id, 0]),
            }
        )

    option_fields = (
        "timestep",
        "integrator",
        "solver",
        "iterations",
        "ls_iterations",
        "tolerance",
        "ls_tolerance",
        "gravity",
        "wind",
        "density",
        "viscosity",
        "disableflags",
        "enableflags",
    )
    options: dict[str, Any] = {}
    for field in option_fields:
        value = _required_attribute(opt, field)
        if field in {"integrator", "solver"}:
            options[field] = _enum_metadata(value)
        else:
            array = np.asarray(value)
            if not np.all(np.isfinite(array.astype(np.float64))):
                raise DynamicsMeasurementError(
                    f"MuJoCo option {field!r} contains a non-finite value"
                )
            options[field] = _as_json(value)

    metadata = {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "timestep_seconds": timestep,
        "frame_skip": frame_skip,
        "control_interval_seconds": timestep * frame_skip,
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "nbody": int(model.nbody),
        "njnt": int(model.njnt),
        "options": options,
        "end_effector_site": END_EFFECTOR_SITE_NAME,
    }
    return metadata, joints, actuator_names, int(
        mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_SITE, END_EFFECTOR_SITE_NAME
        )
    )


def _fixed_configurations(joints: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    # These fixed hinge coordinates span moderate, inner, and outer portions
    # of the official 0.06--0.20 m target-radius interval.
    fixed = (
        ("moderate_radius", (0.0, 1.0)),
        ("inner_radius_coverage", (0.0, 2.6)),
        ("outer_radius_coverage", (0.0, 0.9)),
    )
    configurations: list[dict[str, Any]] = []
    for label, coordinates in fixed:
        qpos = np.asarray(coordinates, dtype=np.float64)
        for index, joint in enumerate(joints):
            low, high = joint["range_radians"]
            if not low <= qpos[index] <= high:
                raise DynamicsMeasurementError(
                    f"fixed configuration {label!r} is outside joint "
                    f"{joint['name']!r} range"
                )
        configurations.append(
            {"name": label, "qpos_radians": qpos.tolist()}
        )
    return configurations


def _reset(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    configuration: dict[str, Any],
    initial_velocity: np.ndarray,
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = np.asarray(configuration["qpos_radians"], dtype=np.float64)
    data.qvel[:] = initial_velocity
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _sample(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    configuration: dict[str, Any],
    probe_name: str,
    command: np.ndarray,
    intervals: int,
    initial_velocity: np.ndarray,
    *,
    actuator_id: int | None = None,
) -> dict[str, Any]:
    _reset(model, data, configuration, initial_velocity)
    baseline_ee = _as_finite_array(data, "site_xpos")[site_id].copy()
    data.ctrl[:] = command
    samples: list[dict[str, Any]] = []
    for interval in range(intervals):
        for substep in range(1, FRAME_SKIP + 1):
            mujoco.mj_step(model, data)
            samples.append(
                {
                    "control_interval": interval,
                    "substep": substep,
                    "time_seconds": float(data.time),
                    "command": command.tolist(),
                    "qpos_radians": _as_finite_array(data, "qpos").tolist(),
                    "qvel_radians_per_second": _as_finite_array(
                        data, "qvel"
                    ).tolist(),
                    "qacc_radians_per_second2": _as_finite_array(
                        data, "qacc"
                    ).tolist(),
                    "actuator_force": _as_finite_array(
                        data, "actuator_force"
                    ).tolist(),
                    "generalized_actuator_force": _as_finite_array(
                        data, "qfrc_actuator"
                    ).tolist(),
                    "force_units": {
                        "actuator_force": dict(ACTUATOR_FORCE_UNITS),
                        "generalized_actuator_force": dict(
                            GENERALIZED_FORCE_UNITS
                        ),
                    },
                    "end_effector_position_m": _as_finite_array(
                        data, "site_xpos"
                    )[site_id].tolist(),
                }
            )

    qvel = np.asarray([sample["qvel_radians_per_second"] for sample in samples])
    qacc = np.asarray([sample["qacc_radians_per_second2"] for sample in samples])
    qpos = np.asarray([sample["qpos_radians"] for sample in samples])
    ee = np.asarray([sample["end_effector_position_m"] for sample in samples])
    initial_speed = float(np.linalg.norm(initial_velocity))
    final_speed = float(np.linalg.norm(qvel[-1]))
    summary: dict[str, Any] = {
        "configuration": configuration["name"],
        "probe_name": probe_name,
        "actuator_id": actuator_id,
        "sample_count": len(samples),
        "peak_absolute_acceleration_radians_per_second2": float(
            np.max(np.abs(qacc))
        ),
        "peak_absolute_velocity_radians_per_second": float(
            np.max(np.abs(qvel))
        ),
        "velocity_decay": {
            "initial_speed_radians_per_second": initial_speed,
            "final_speed_radians_per_second": final_speed,
            "speed_change_radians_per_second": final_speed - initial_speed,
        },
        "return_to_baseline": {
            "final_qpos_displacement_radians": float(
                np.linalg.norm(qpos[-1] - np.asarray(configuration["qpos_radians"]))
            ),
            "final_end_effector_displacement_m": float(
                np.linalg.norm(ee[-1] - baseline_ee)
            ),
            "final_velocity_norm_radians_per_second": final_speed,
        },
    }
    if "saturated" in probe_name:
        summary["saturation_response"] = {
            "command_absolute_peak": float(np.max(np.abs(command))),
            "final_qpos_displacement_radians": summary["return_to_baseline"][
                "final_qpos_displacement_radians"
            ],
            "final_end_effector_displacement_m": summary["return_to_baseline"][
                "final_end_effector_displacement_m"
            ],
        }
    else:
        summary["saturation_response"] = None

    return {
        "configuration": configuration["name"],
        "probe_name": probe_name,
        "actuator_id": actuator_id,
        "initial_velocity_radians_per_second": initial_velocity.tolist(),
        "command": command.tolist(),
        "samples": samples,
        "summary": summary,
    }


def collect_measurement(
    *,
    frame_skip: int = FRAME_SKIP,
    intervals: int = DEFAULT_INTERVALS,
    decay_intervals: int = DEFAULT_DECAY_INTERVALS,
    configuration_count: int = 3,
) -> dict[str, Any]:
    """Compile the official model and return one deterministic measurement."""

    if frame_skip != FRAME_SKIP:
        raise ValueError(
            f"frame_skip must remain the official value {FRAME_SKIP}, "
            f"not {frame_skip}"
        )
    if not 1 <= intervals <= MAX_INTERVALS:
        raise ValueError(f"intervals must be between 1 and {MAX_INTERVALS}")
    if not 1 <= decay_intervals <= MAX_INTERVALS:
        raise ValueError(
            f"decay_intervals must be between 1 and {MAX_INTERVALS}"
        )
    if not 1 <= configuration_count <= 3:
        raise ValueError("configuration_count must be between 1 and 3")

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    metadata, joints, actuators, site_id = _model_metadata(model, frame_skip)
    if site_id < 0:
        raise DynamicsMeasurementError(
            f"required site {END_EFFECTOR_SITE_NAME!r} is unavailable"
        )
    configurations = _fixed_configurations(joints)[:configuration_count]

    ctrl_ranges = _as_finite_array(model, "actuator_ctrlrange")
    probes: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    initial_velocity = np.asarray((0.6, -0.4), dtype=np.float64)
    for configuration in configurations:
        decay = _sample(
            model,
            data,
            site_id,
            configuration,
            "zero_command_decay",
            np.zeros(ACTUATOR_COUNT, dtype=np.float64),
            decay_intervals,
            initial_velocity,
        )
        probes.append(decay)
        summaries.append(decay["summary"])

        for actuator_id in range(ACTUATOR_COUNT):
            low, high = ctrl_ranges[actuator_id, :2]
            small_magnitude = 0.25 * min(high, -low)
            for probe_name, command_value, probe_intervals in (
                (
                    "small_positive",
                    small_magnitude,
                    intervals,
                ),
                (
                    "small_negative",
                    -small_magnitude,
                    intervals,
                ),
                ("saturated_positive", high, intervals),
                ("saturated_negative", low, intervals),
            ):
                command = np.zeros(ACTUATOR_COUNT, dtype=np.float64)
                command[actuator_id] = command_value
                probe = _sample(
                    model,
                    data,
                    site_id,
                    configuration,
                    f"{probe_name}_joint_{actuator_id}",
                    command,
                    probe_intervals,
                    np.zeros(JOINT_COUNT, dtype=np.float64),
                    actuator_id=actuator_id,
                )
                probes.append(probe)
                summaries.append(probe["summary"])

    result = {
        "schema_version": SCHEMA_VERSION,
        "measurement_note": (
            "Deterministic open-loop evidence from the compiled official "
            "MuJoCo model; this is not policy performance."
        ),
        "units": {
            "actuator_force": dict(ACTUATOR_FORCE_UNITS),
            "generalized_actuator_force": dict(GENERALIZED_FORCE_UNITS),
            "joint_dynamics": dict(JOINT_DYNAMICS_UNITS),
        },
        "model": metadata,
        "joints": joints,
        "actuators": actuators,
        "probe_parameters": {
            "frame_skip": FRAME_SKIP,
            "substeps_per_control_interval": FRAME_SKIP,
            "control_interval_seconds": metadata["control_interval_seconds"],
            "small_command_fraction_of_symmetric_limit": 0.25,
            "decay_initial_velocity_radians_per_second": initial_velocity.tolist(),
            "probe_intervals": intervals,
            "decay_intervals": decay_intervals,
            "configuration_count": configuration_count,
            "deterministic": True,
        },
        "configurations": configurations,
        "raw_probe_records": probes,
        "summaries": summaries,
    }
    return _as_json(result)


def write_measurement(output_path: str | Path, measurement: dict[str, Any]) -> None:
    """Write a completed measurement to the requested JSON path."""

    with Path(output_path).open("w", encoding="utf-8") as handle:
        json.dump(measurement, handle, indent=2, allow_nan=False)
        handle.write("\n")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="JSON artifact path")
    parser.add_argument("--frame-skip", type=_positive_int, default=FRAME_SKIP)
    parser.add_argument(
        "--intervals", type=_positive_int, default=DEFAULT_INTERVALS
    )
    parser.add_argument(
        "--decay-intervals", type=_positive_int, default=DEFAULT_DECAY_INTERVALS
    )
    parser.add_argument(
        "--configurations", type=_positive_int, default=3, dest="configuration_count"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    measurement = collect_measurement(
        frame_skip=args.frame_skip,
        intervals=args.intervals,
        decay_intervals=args.decay_intervals,
        configuration_count=args.configuration_count,
    )
    write_measurement(args.output, measurement)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
