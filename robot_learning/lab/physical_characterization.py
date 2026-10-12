"""Deterministic, non-task physical characterization of the two-joint arm.

This module deliberately uses the XML and native MuJoCo calls directly.  It
does not construct the Gymnasium environment, sample a target, or alter any
task setting.  Commands are normalized motor controls in the same bounded
range as the XML actuators; the corresponding nominal motor torque is reported
alongside the simulator's generalized actuator force.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH

CONTROL_BLOCK_STEPS = 10
CONTROL_BLOCK_SECONDS = 0.020
DEFAULT_REPEATS = 2
DEFAULT_COMMAND_BLOCKS = 8
DEFAULT_RELEASE_BLOCKS = 24
DEFAULT_DECAY_BLOCKS = 40

# These are representative planar postures, expressed in radians.  The latter
# two have the positive and negative elbow branches of a target-like posture.
CONFIGURATIONS: dict[str, tuple[float, float]] = {
    "extended": (0.0, 0.0),
    "open": (0.45, 1.20),
    "folded": (0.45, -1.20),
}


def load_model() -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Load the human-owned XML through the native MuJoCo API."""

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    return model, mujoco.MjData(model)


def reset_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: Sequence[float],
    qvel: Sequence[float] | None = None,
) -> None:
    """Reset all simulator state, then install a controlled state and forward it."""

    qpos_array = np.asarray(qpos, dtype=np.float64)
    qvel_array = (
        np.zeros(model.nv, dtype=np.float64)
        if qvel is None
        else np.asarray(qvel, dtype=np.float64)
    )
    if qpos_array.shape != (model.nq,) or qvel_array.shape != (model.nv,):
        raise ValueError("qpos and qvel must match the compiled model dimensions")
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos_array
    data.qvel[:] = qvel_array
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _bounded_command(command: Sequence[float], nu: int) -> np.ndarray:
    value = np.asarray(command, dtype=np.float64)
    if value.shape != (nu,) or not np.all(np.isfinite(value)):
        raise ValueError("command must be a finite vector with one entry per actuator")
    return np.clip(value, -1.0, 1.0)


def _endpoint(data: mujoco.MjData) -> np.ndarray:
    return np.asarray(data.site("end_effector").xpos, dtype=np.float64).copy()


def _expected_joint_torque(
    model: mujoco.MjModel, command: np.ndarray
) -> np.ndarray:
    expected = np.zeros(model.nv, dtype=np.float64)
    for actuator_id in range(model.nu):
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        if joint_id < 0:
            continue
        dof_id = int(model.jnt_dofadr[joint_id])
        # A hinge motor's scalar gear is the first component of actuator_gear.
        expected[dof_id] += float(model.actuator_gear[actuator_id, 0]) * float(
            command[actuator_id]
        )
    return expected


def _snapshot(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    command: np.ndarray,
    previous_endpoint: np.ndarray | None,
) -> tuple[dict[str, Any], np.ndarray]:
    endpoint = _endpoint(data)
    dt = float(model.opt.timestep)
    endpoint_speed = (
        0.0
        if previous_endpoint is None
        else float(np.linalg.norm(endpoint - previous_endpoint) / dt)
    )
    item = {
        "time_s": float(data.time),
        "qpos_rad": data.qpos.copy().tolist(),
        "qvel_rad_s": data.qvel.copy().tolist(),
        "endpoint_position_m": endpoint.tolist(),
        "endpoint_speed_m_s": endpoint_speed,
        "command_normalized": command.copy().tolist(),
        "expected_joint_torque_Nm": _expected_joint_torque(model, command).tolist(),
        "applied_generalized_force_Nm": data.qfrc_actuator.copy().tolist(),
    }
    return item, endpoint


def run_trace(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    qpos: Sequence[float],
    qvel: Sequence[float] | None = None,
    command: Sequence[float],
    command_steps: int,
    release_steps: int,
    sample_blocks: bool = True,
) -> dict[str, Any]:
    """Run a bounded command followed by zero command and retain both timescales."""

    if command_steps < 0 or release_steps < 0:
        raise ValueError("trace lengths must be non-negative")
    reset_state(model, data, qpos, qvel)
    bounded = _bounded_command(command, model.nu)
    zero = np.zeros(model.nu, dtype=np.float64)
    total_steps = command_steps + release_steps
    substeps: list[dict[str, Any]] = []
    control_blocks: list[dict[str, Any]] = []
    previous_endpoint: np.ndarray | None = None
    initial, previous_endpoint = _snapshot(model, data, zero, previous_endpoint)
    initial["substep_index"] = 0
    initial["phase"] = "initial"
    substeps.append(initial)

    for step_index in range(total_steps):
        active = bounded if step_index < command_steps else zero
        data.ctrl[:] = active
        mujoco.mj_step(model, data)
        item, previous_endpoint = _snapshot(model, data, active, previous_endpoint)
        substep_index = step_index + 1
        item["substep_index"] = substep_index
        item["phase"] = "command" if step_index < command_steps else "release"
        substeps.append(item)
        if sample_blocks and substep_index % CONTROL_BLOCK_STEPS == 0:
            block = dict(item)
            block["control_block_index"] = substep_index // CONTROL_BLOCK_STEPS
            block["control_block_seconds"] = float(
                model.opt.timestep * CONTROL_BLOCK_STEPS
            )
            control_blocks.append(block)

    return {
        "command_steps": command_steps,
        "release_steps": release_steps,
        "command_blocks": command_steps / CONTROL_BLOCK_STEPS,
        "release_blocks": release_steps / CONTROL_BLOCK_STEPS,
        "substep_samples": substeps,
        "control_block_observations": control_blocks,
    }


def _state_matrix(trace: dict[str, Any]) -> np.ndarray:
    return np.asarray(
        [
            sample["qpos_rad"] + sample["qvel_rad_s"]
            for sample in trace["substep_samples"]
        ],
        dtype=np.float64,
    )


def _repeat_trace(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    run: Callable[[], dict[str, Any]],
    repeats: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    traces = [run() for _ in range(repeats)]
    reference = _state_matrix(traces[0])
    differences = [
        float(np.max(np.abs(_state_matrix(trace) - reference)))
        for trace in traces[1:]
    ]
    return traces[0], {
        "trials": repeats,
        "max_abs_qpos_qvel_difference": max(differences, default=0.0),
        "deterministic_within_tolerance": bool(
            max(differences, default=0.0) <= 1e-12
        ),
        "tolerance": 1e-12,
    }


def _settling_summary(trace: dict[str, Any], release_start: int) -> dict[str, Any]:
    samples = trace["substep_samples"]
    qvel_norm = np.asarray(
        [np.linalg.norm(sample["qvel_rad_s"]) for sample in samples], dtype=np.float64
    )
    endpoint_speed = np.asarray(
        [sample["endpoint_speed_m_s"] for sample in samples], dtype=np.float64
    )
    endpoint = np.asarray(
        [sample["endpoint_position_m"] for sample in samples], dtype=np.float64
    )
    initial_endpoint = endpoint[0]
    displacement = np.linalg.norm(endpoint - initial_endpoint, axis=1)
    velocity_threshold = 0.02
    endpoint_speed_threshold = 0.005
    consecutive = 10
    settling_index: int | None = None
    for start in range(max(1, release_start), len(samples) - consecutive + 1):
        if np.all(qvel_norm[start : start + consecutive] <= velocity_threshold) and np.all(
            endpoint_speed[start : start + consecutive] <= endpoint_speed_threshold
        ):
            settling_index = start
            break
    return {
        "definition": (
            "first post-release substep with 10 consecutive samples below "
            "qvel <= 0.02 rad/s and endpoint speed <= 0.005 m/s"
        ),
        "settling_time_after_release_s": (
            None
            if settling_index is None
            else float(samples[settling_index]["time_s"] - samples[release_start]["time_s"])
        ),
        "settling_control_block": (
            None
            if settling_index is None
            else int(round(samples[settling_index]["substep_index"] / CONTROL_BLOCK_STEPS))
        ),
        "peak_endpoint_displacement_m": float(np.max(displacement)),
        "peak_joint_speed_rad_s": float(np.max(qvel_norm)),
        "final_qpos_rad": samples[-1]["qpos_rad"],
        "final_qvel_rad_s": samples[-1]["qvel_rad_s"],
        "final_endpoint_speed_m_s": float(endpoint_speed[-1]),
        "thresholds": {
            "joint_speed_rad_s": velocity_threshold,
            "endpoint_speed_m_s": endpoint_speed_threshold,
            "consecutive_substeps": consecutive,
        },
    }


def _response_summary(
    model: mujoco.MjModel, trace: dict[str, Any], command: np.ndarray
) -> dict[str, Any]:
    samples = trace["substep_samples"]
    qvel = np.asarray([sample["qvel_rad_s"] for sample in samples], dtype=np.float64)
    command_values = np.asarray(
        [sample["command_normalized"] for sample in samples], dtype=np.float64
    )
    endpoint = np.asarray(
        [sample["endpoint_position_m"] for sample in samples], dtype=np.float64
    )
    release_start = trace["command_steps"]
    return {
        "requested_command_normalized": command.tolist(),
        "expected_saturated_torque_Nm": _expected_joint_torque(model, command).tolist(),
        "saturated_fraction": float(
            np.mean(np.any(np.abs(command_values) >= 1.0 - 1e-12, axis=1))
        ),
        "peak_joint_speed_rad_s": np.max(np.abs(qvel), axis=0).tolist(),
        "peak_endpoint_displacement_m": float(
            np.max(np.linalg.norm(endpoint - endpoint[0], axis=1))
        ),
        "command_release_time_s": float(samples[release_start]["time_s"]),
        "final_qpos_rad": samples[-1]["qpos_rad"],
        "final_qvel_rad_s": samples[-1]["qvel_rad_s"],
        "endpoint_settling": _settling_summary(trace, release_start),
    }


def _name(model: mujoco.MjModel, object_type: Any, object_id: int) -> str:
    value = mujoco.mj_id2name(model, object_type, object_id)
    return str(value) if value is not None else f"unnamed_{object_id}"


def compiled_facts(model: mujoco.MjModel) -> dict[str, Any]:
    """Return compiled authority, timing, and inertial facts with SI units."""

    integrators = {
        int(mujoco.mjtIntegrator.mjINT_EULER): "Euler",
        int(mujoco.mjtIntegrator.mjINT_RK4): "RK4",
        int(mujoco.mjtIntegrator.mjINT_IMPLICIT): "implicit",
        int(mujoco.mjtIntegrator.mjINT_IMPLICITFAST): "implicitfast",
    }
    solvers = {
        int(mujoco.mjtSolver.mjSOL_PGS): "PGS",
        int(mujoco.mjtSolver.mjSOL_CG): "CG",
        int(mujoco.mjtSolver.mjSOL_NEWTON): "Newton",
    }
    options = {
        "timestep_s": float(model.opt.timestep),
        "integrator_code": int(model.opt.integrator),
        "integrator": integrators.get(int(model.opt.integrator), "unknown"),
        "solver_code": int(model.opt.solver),
        "solver": solvers.get(int(model.opt.solver), "unknown"),
        "iterations": int(model.opt.iterations),
        "tolerance": float(model.opt.tolerance),
    }
    joints = []
    for joint_id in range(model.njnt):
        dof_id = int(model.jnt_dofadr[joint_id])
        joints.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                # jnt_range is already in compiled SI units; the XML uses
                # degrees, which MuJoCo converts while compiling the model.
                "range_rad": model.jnt_range[joint_id].tolist(),
                "range_source_units": "compiled radians (XML range is degrees)",
                "damping_Nm_s": float(model.dof_damping[dof_id]),
                "armature_kg_m2": float(model.dof_armature[dof_id]),
            }
        )
    actuators = []
    for actuator_id in range(model.nu):
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        actuators.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id),
                "joint": (
                    _name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
                    if joint_id >= 0
                    else None
                ),
                "gear": model.actuator_gear[actuator_id].tolist(),
                "control_range_normalized": model.actuator_ctrlrange[
                    actuator_id
                ].tolist(),
                "nominal_torque_at_control_limits_Nm": (
                    model.actuator_gear[actuator_id, 0]
                    * model.actuator_ctrlrange[actuator_id]
                ).tolist(),
            }
        )
    bodies = []
    for body_id in range(model.nbody):
        bodies.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass_kg": float(model.body_mass[body_id]),
                "inertia_kg_m2_principal": model.body_inertia[body_id].tolist(),
            }
        )
    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "njnt": int(model.njnt),
            "nbody": int(model.nbody),
        },
        "options": options,
        "joints": joints,
        "actuators": actuators,
        "bodies": bodies,
        "gravity_m_s2": model.opt.gravity.tolist(),
    }


def _measure_free_decay(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    qpos: Sequence[float],
    velocity_perturbation: Sequence[float],
    decay_steps: int,
    repeats: int,
) -> dict[str, Any]:
    zero = np.zeros(model.nu, dtype=np.float64)
    trace, repeat = _repeat_trace(
        model,
        data,
        lambda: run_trace(
            model,
            data,
            qpos=qpos,
            qvel=velocity_perturbation,
            command=zero,
            command_steps=0,
            release_steps=decay_steps,
        ),
        repeats,
    )
    samples = trace["substep_samples"]
    norms = np.asarray(
        [np.linalg.norm(sample["qvel_rad_s"]) for sample in samples], dtype=np.float64
    )
    return {
        "initial_velocity_perturbation_rad_s": list(velocity_perturbation),
        "trace": trace,
        "repeat_consistency": repeat,
        "summary": {
            "initial_speed_rad_s": float(norms[0]),
            "final_speed_rad_s": float(norms[-1]),
            "peak_speed_rad_s": float(np.max(norms)),
            "speed_ratio_final_over_initial": float(norms[-1] / norms[0]),
            "zero_command": True,
        },
    }


def characterize(
    *,
    repeats: int = DEFAULT_REPEATS,
    command_blocks: int = DEFAULT_COMMAND_BLOCKS,
    release_blocks: int = DEFAULT_RELEASE_BLOCKS,
    decay_blocks: int = DEFAULT_DECAY_BLOCKS,
) -> dict[str, Any]:
    """Run the complete deterministic characterization and return JSON data."""

    model, data = load_model()
    timestep = float(model.opt.timestep)
    if not np.isclose(timestep, 0.002):
        raise RuntimeError(f"expected the contract timestep 0.002 s, got {timestep}")
    command_steps = command_blocks * CONTROL_BLOCK_STEPS
    release_steps = release_blocks * CONTROL_BLOCK_STEPS
    decay_steps = decay_blocks * CONTROL_BLOCK_STEPS
    commands = {
        "single_shoulder": np.array([1.0, 0.0]),
        "single_elbow": np.array([0.0, 1.0]),
        "paired": np.array([1.0, 1.0]),
    }
    step_responses: dict[str, Any] = {}
    endpoint_settling: dict[str, Any] = {}
    free_decay: dict[str, Any] = {}
    velocity_perturbation = (1.0, -0.6)
    for configuration, qpos in CONFIGURATIONS.items():
        step_responses[configuration] = {}
        for label, command in commands.items():
            trace, repeat = _repeat_trace(
                model,
                data,
                lambda qpos=qpos, command=command: run_trace(
                    model,
                    data,
                    qpos=qpos,
                    command=command,
                    command_steps=command_steps,
                    release_steps=release_steps,
                ),
                repeats,
            )
            step_responses[configuration][label] = {
                "trace": trace,
                "repeat_consistency": repeat,
                "summary": _response_summary(model, trace, command),
            }
        # A separate, identical bounded pulse gives a named endpoint settling
        # record rather than requiring consumers to infer it from the coupling
        # trials.
        settling_command = np.array([0.5, 0.5])
        settling_trace, settling_repeat = _repeat_trace(
            model,
            data,
            lambda qpos=qpos: run_trace(
                model,
                data,
                qpos=qpos,
                command=settling_command,
                command_steps=CONTROL_BLOCK_STEPS,
                release_steps=release_steps,
            ),
            repeats,
        )
        endpoint_settling[configuration] = {
            "bounded_pulse_normalized": settling_command.tolist(),
            "trace": settling_trace,
            "repeat_consistency": settling_repeat,
            "summary": _response_summary(model, settling_trace, settling_command),
        }
        free_decay[configuration] = _measure_free_decay(
            model,
            data,
            qpos=qpos,
            velocity_perturbation=velocity_perturbation,
            decay_steps=decay_steps,
            repeats=repeats,
        )

    return {
        "measurement": "two_joint_arm_physical_characterization",
        "schema_version": 1,
        "deterministic": True,
        "units": {
            "time": "s",
            "simulation_step": "0.002 s",
            "control_block": (
                f"{CONTROL_BLOCK_SECONDS:.3f} s (10 simulation steps)"
            ),
            "angle": "rad unless explicitly marked source XML degrees",
            "angular_velocity": "rad/s",
            "position": "m",
            "speed": "m/s",
            "mass": "kg",
            "inertia": "kg*m^2",
            "torque": "N*m",
            "command": "normalized actuator control in XML ctrlrange",
        },
        "protocol": {
            "repeats_per_trial": repeats,
            "configuration_qpos_rad": {
                name: list(qpos) for name, qpos in CONFIGURATIONS.items()
            },
            "step_response": (
                f"{command_blocks} commanded 20 ms blocks followed by "
                f"{release_blocks} zero-command blocks"
            ),
            "free_decay": f"{decay_blocks} zero-command 20 ms blocks after qvel perturbation",
        },
        "compiled_facts": compiled_facts(model),
        "step_responses": step_responses,
        "free_decay": free_decay,
        "endpoint_settling": endpoint_settling,
        "interpretation_note": (
            "These are controlled simulator responses, not a task-success "
            "claim. They expose saturation, coupling, decay, and settling "
            "mechanisms without changing official environment semantics."
        ),
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--command-blocks", type=int, default=DEFAULT_COMMAND_BLOCKS)
    parser.add_argument("--release-blocks", type=int, default=DEFAULT_RELEASE_BLOCKS)
    parser.add_argument("--decay-blocks", type=int, default=DEFAULT_DECAY_BLOCKS)
    args = parser.parse_args(argv)
    artifact = characterize(
        repeats=args.repeats,
        command_blocks=args.command_blocks,
        release_blocks=args.release_blocks,
        decay_blocks=args.decay_blocks,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
