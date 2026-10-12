"""Deterministic MuJoCo characterization of the authored two-joint arm."""

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


PULSE_STEPS = 20
COAST_STEPS = 120
REPEATABILITY_TOLERANCE = 1.0e-12


def compile_production_model() -> mujoco.MjModel:
    """Compile the authored XML, without substituting a laboratory model."""
    return mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))


def configure_zero_gravity(model: mujoco.MjModel) -> None:
    """Set the explicitly controlled measurement condition."""
    model.opt.gravity[:] = 0.0


def _enum_name(enum_type: Any, value: int) -> str:
    if enum_type is mujoco.mjtIntegrator:
        members = (
            enum_type.mjINT_EULER,
            enum_type.mjINT_RK4,
            enum_type.mjINT_IMPLICIT,
            enum_type.mjINT_IMPLICITFAST,
        )
    elif enum_type is mujoco.mjtSolver:
        members = (
            enum_type.mjSOL_PGS,
            enum_type.mjSOL_CG,
            enum_type.mjSOL_NEWTON,
        )
    else:
        raise ValueError(f"unsupported MuJoCo enum type {enum_type!r}")
    for member in members:
        if int(member.value) == int(value):
            return member.name
    raise ValueError(f"unknown MuJoCo enum value {value} for {enum_type.__name__}")


def _option_settings(model: mujoco.MjModel) -> dict[str, Any]:
    opt = model.opt
    return {
        "timestep_s": float(opt.timestep),
        "integrator": {
            "value": int(opt.integrator),
            "name": _enum_name(mujoco.mjtIntegrator, int(opt.integrator)),
        },
        "solver": {
            "value": int(opt.solver),
            "name": _enum_name(mujoco.mjtSolver, int(opt.solver)),
        },
        "gravity_m_per_s2": np.asarray(opt.gravity, dtype=float).tolist(),
        "wind_m_per_s": np.asarray(opt.wind, dtype=float).tolist(),
        "density_kg_per_m3": float(opt.density),
        "viscosity_pa_s": float(opt.viscosity),
        "iterations": int(opt.iterations),
        "ls_iterations": int(opt.ls_iterations),
        "tolerance": float(opt.tolerance),
        "noslip_iterations": int(opt.noslip_iterations),
        "noslip_tolerance": float(opt.noslip_tolerance),
        "impratio": float(opt.impratio),
        "disableflags": int(opt.disableflags),
        "enableflags": int(opt.enableflags),
    }


def _object_name(model: mujoco.MjModel, object_type: Any, index: int) -> str | None:
    name = mujoco.mj_id2name(model, object_type, index)
    return None if name is None else str(name)


def _model_inventory(model: mujoco.MjModel) -> dict[str, Any]:
    return {
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "njnt": int(model.njnt),
            "nbody": int(model.nbody),
            "nsite": int(model.nsite),
            "nu": int(model.nu),
        },
        "joints": [
            {
                "id": index,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, index),
                "type": int(model.jnt_type[index]),
                "qpos_address": int(model.jnt_qposadr[index]),
                "dof_address": int(model.jnt_dofadr[index]),
            }
            for index in range(model.njnt)
        ],
        "bodies": [
            {
                "id": index,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_BODY, index),
                "mass_kg": float(model.body_mass[index]),
                "inertia_kg_m2": np.asarray(
                    model.body_inertia[index], dtype=float
                ).tolist(),
            }
            for index in range(model.nbody)
        ],
        "actuators": [
            {
                "id": index,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index),
                "gear": np.asarray(model.actuator_gear[index], dtype=float).tolist(),
                "force_range_native": np.asarray(
                    model.actuator_forcerange[index], dtype=float
                ).tolist(),
                "ctrl_range_native": np.asarray(
                    model.actuator_ctrlrange[index], dtype=float
                ).tolist(),
                "ctrl_limited": bool(model.actuator_ctrllimited[index]),
            }
            for index in range(model.nu)
        ],
    }


def _require_two_joint_arm(model: mujoco.MjModel) -> None:
    if (model.njnt, model.nq, model.nv, model.nu) != (2, 2, 2, 2):
        raise ValueError(
            "the compiled production model must have exactly two joints, "
            f"two position/velocity coordinates, and two actuators; got "
            f"njnt={model.njnt}, nq={model.nq}, nv={model.nv}, nu={model.nu}"
        )
    site_names = {
        _object_name(model, mujoco.mjtObj.mjOBJ_SITE, index)
        for index in range(model.nsite)
    }
    if "end_effector" not in site_names:
        raise ValueError(
            "the compiled production model must contain site 'end_effector'"
        )


def _pulse_control(model: mujoco.MjModel, joint_index: int, sign: int) -> np.ndarray:
    if sign not in (-1, 1):
        raise ValueError(f"pulse sign must be -1 or 1, got {sign}")
    ranges = np.asarray(model.actuator_ctrlrange, dtype=float)
    limited = bool(model.actuator_ctrllimited[joint_index])
    low, high = (float(value) for value in ranges[joint_index])
    if not np.isfinite([low, high]).all() or high < low:
        raise ValueError(f"invalid actuator control range for actuator {joint_index}")
    if low > 0.0 or high < 0.0:
        raise ValueError(
            "zero command is outside an actuator control range; braking trials "
            "cannot be defined explicitly"
        )
    command = high if sign > 0 else low
    if not limited:
        command = float(sign)
    if command == 0.0:
        raise ValueError(
            f"actuator {joint_index} has no nonzero command for pulse sign {sign}"
        )
    result = np.zeros(model.nu, dtype=float)
    result[joint_index] = command
    return result


def _reset_data(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _end_effector_position(data: mujoco.MjData) -> np.ndarray:
    try:
        return np.asarray(data.site("end_effector").xpos, dtype=float).copy()
    except (KeyError, ValueError):
        raise ValueError("production data does not expose site 'end_effector'") from None


def _trace_sample(
    data: mujoco.MjData,
    command: np.ndarray,
    time_s: float,
    phase: str,
) -> dict[str, Any]:
    qpos = np.asarray(data.qpos, dtype=float).copy()
    qvel = np.asarray(data.qvel, dtype=float).copy()
    qacc = np.asarray(data.qacc, dtype=float).copy()
    qfrc_actuator = np.asarray(data.qfrc_actuator, dtype=float).copy()
    actuator_force = np.asarray(data.actuator_force, dtype=float).copy()
    end_effector_position = _end_effector_position(data)
    if not all(
        np.isfinite(values).all()
        for values in (
            qpos,
            qvel,
            qacc,
            qfrc_actuator,
            actuator_force,
            command,
            end_effector_position,
        )
    ):
        raise ValueError("non-finite value encountered in a MuJoCo trial trace")
    return {
        "time_s": float(time_s),
        "phase": phase,
        "qpos_rad": qpos.tolist(),
        "qvel_rad_per_s": qvel.tolist(),
        "qacc_rad_per_s2": qacc.tolist(),
        "qfrc_actuator_Nm": qfrc_actuator.tolist(),
        "actuator_force_native": actuator_force.tolist(),
        "ctrl_native": np.asarray(command, dtype=float).tolist(),
        "end_effector_position_m": end_effector_position.tolist(),
    }


def _trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    joint_index: int,
    sign: int,
) -> dict[str, Any]:
    timestep = float(model.opt.timestep)
    pulse = _pulse_control(model, joint_index, sign)
    _reset_data(model, data)
    trace: list[dict[str, Any]] = []
    for step in range(PULSE_STEPS + COAST_STEPS):
        phase = "pulse" if step < PULSE_STEPS else "coast"
        command = pulse if phase == "pulse" else np.zeros(model.nu, dtype=float)
        data.ctrl[:] = command
        mujoco.mj_step(model, data)
        trace.append(_trace_sample(data, command, (step + 1) * timestep, phase))

    qvel = np.asarray([sample["qvel_rad_per_s"] for sample in trace], dtype=float)
    qacc = np.asarray([sample["qacc_rad_per_s2"] for sample in trace], dtype=float)
    qfrc = np.asarray([sample["qfrc_actuator_Nm"] for sample in trace], dtype=float)
    actuator_force = np.asarray(
        [sample["actuator_force_native"] for sample in trace], dtype=float
    )
    qpos = np.asarray([sample["qpos_rad"] for sample in trace], dtype=float)
    ctrl = np.asarray([sample["ctrl_native"] for sample in trace], dtype=float)

    peak_velocity = float(np.max(np.abs(qvel[:, joint_index])))
    stop_threshold = max(1.0e-8, 0.01 * peak_velocity)
    release_index = PULSE_STEPS - 1
    stopping_index = next(
        (
            index
            for index in range(PULSE_STEPS, len(trace))
            if abs(qvel[index, joint_index]) <= stop_threshold
        ),
        None,
    )
    stopping_time = None
    stopping_distance = None
    if stopping_index is not None:
        stopping_time = float(
            trace[stopping_index]["time_s"] - trace[release_index]["time_s"]
        )
        stopping_distance = float(
            abs(qpos[stopping_index, joint_index] - qpos[release_index, joint_index])
        )

    low, high = np.asarray(model.actuator_ctrlrange[joint_index], dtype=float)
    at_limit = np.isclose(ctrl[:, joint_index], low) | np.isclose(
        ctrl[:, joint_index], high
    )
    return {
        "joint_index": joint_index,
        "joint_name": _object_name(
            model, mujoco.mjtObj.mjOBJ_JOINT, joint_index
        ),
        "pulse_sign": sign,
        "pulse_command_native": float(pulse[joint_index]),
        "pulse_steps": PULSE_STEPS,
        "coast_steps": COAST_STEPS,
        "trace": trace,
        "summary": {
            "peak_abs_qvel_rad_per_s": peak_velocity,
            "peak_abs_qacc_rad_per_s2": float(
                np.max(np.abs(qacc[:, joint_index]))
            ),
            "peak_abs_qfrc_actuator_Nm": float(
                np.max(np.abs(qfrc[:, joint_index]))
            ),
            "peak_abs_actuator_force_native": float(
                np.max(np.abs(actuator_force[:, joint_index]))
            ),
            "stopping_threshold_rad_per_s": stop_threshold,
            "stopping_time_after_release_s": stopping_time,
            "stopping_distance_after_release_rad": stopping_distance,
            "saturation_fraction": float(np.mean(at_limit)),
        },
    }


def _compare_trials(
    first: list[dict[str, Any]], second: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(first) != len(second):
        raise ValueError("repeatability comparison received different trial counts")
    fields = (
        "qpos_rad",
        "qvel_rad_per_s",
        "qacc_rad_per_s2",
        "qfrc_actuator_Nm",
        "actuator_force_native",
        "ctrl_native",
        "end_effector_position_m",
    )
    maximum = 0.0
    for first_trial, second_trial in zip(first, second):
        if (first_trial["joint_index"], first_trial["pulse_sign"]) != (
            second_trial["joint_index"],
            second_trial["pulse_sign"],
        ):
            raise ValueError("repeatability comparison received reordered trials")
        first_trace = first_trial["trace"]
        second_trace = second_trial["trace"]
        if len(first_trace) != len(second_trace):
            raise ValueError("repeatability comparison received different trace lengths")
        for first_sample, second_sample in zip(first_trace, second_trace):
            for field in fields:
                difference = np.max(
                    np.abs(
                        np.asarray(first_sample[field], dtype=float)
                        - np.asarray(second_sample[field], dtype=float)
                    )
                )
                maximum = max(maximum, float(difference))
    return {
        "max_abs_trace_difference": maximum,
        "tolerance": REPEATABILITY_TOLERANCE,
        "passed": maximum <= REPEATABILITY_TOLERANCE,
        "compared_trial_count": len(first),
        "compared_internal_samples_per_trial": PULSE_STEPS + COAST_STEPS,
    }


def characterize() -> dict[str, Any]:
    """Run the bounded repeated pulse/free-response measurement."""
    model = compile_production_model()
    compiled_options = _option_settings(model)
    _require_two_joint_arm(model)
    configure_zero_gravity(model)
    effective_options = _option_settings(model)
    data = mujoco.MjData(model)

    first_trials = [
        _trial(model, data, joint_index, sign)
        for joint_index in range(2)
        for sign in (-1, 1)
    ]
    second_trials = [
        _trial(model, data, joint_index, sign)
        for joint_index in range(2)
        for sign in (-1, 1)
    ]
    return {
        "schema_version": 1,
        "mode": "measurement",
        "production_xml_path": str(TWO_JOINT_ARM_XML_PATH.resolve()),
        "conditions": {
            "initial_qpos_rad": [0.0, 0.0],
            "initial_qvel_rad_per_s": [0.0, 0.0],
            "gravity": "zeroed after XML compilation",
            "target_dependence": "none",
            "command_protocol": (
                f"{PULSE_STEPS} internal steps at a signed bounded command, "
                f"then {COAST_STEPS} internal steps at zero command"
            ),
        },
        "options": {
            "compiled_from_xml": compiled_options,
            "effective_measurement": effective_options,
        },
        "model": _model_inventory(model),
        "units_and_semantics": {
            "time": "seconds from the start of each trial; samples are post-mj_step",
            "qpos": "radians for the two hinge joints",
            "qvel": "radians per second",
            "qacc": "radians per second squared",
            "qfrc_actuator": "generalized actuator torque in N m for these hinges",
            "actuator_force": "native MuJoCo actuator force, transmission-dependent",
            "ctrl": "native actuator control command",
            "end_effector_position": "world Cartesian meters",
            "stopping": (
                "first coast sample below max(1e-8, 1% of peak joint speed); "
                "distance is absolute joint displacement from pulse release"
            ),
            "saturation_fraction": (
                "fraction of all recorded samples whose selected actuator "
                "command equals a compiled control-range endpoint"
            ),
        },
        "trials": first_trials,
        "repeatability": _compare_trials(first_trials, second_trials),
    }


def compatibility() -> dict[str, Any]:
    """Compile the production XML and exercise one native simulation step."""
    model = compile_production_model()
    configure_zero_gravity(model)
    data = mujoco.MjData(model)
    _reset_data(model, data)
    data.ctrl[:] = 0.0
    mujoco.mj_step(model, data)
    return {
        "schema_version": 1,
        "mode": "compatibility",
        "production_xml_path": str(TWO_JOINT_ARM_XML_PATH.resolve()),
        "compiled": True,
        "one_mj_step_completed": True,
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "njnt": int(model.njnt),
            "nu": int(model.nu),
        },
        "post_step_qpos_rad": np.asarray(data.qpos, dtype=float).tolist(),
        "post_step_qvel_rad_per_s": np.asarray(data.qvel, dtype=float).tolist(),
        "gravity_m_per_s2": np.asarray(model.opt.gravity, dtype=float).tolist(),
    }


def _write_json(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("measurement", "compatibility"), default="measurement"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = characterize() if args.mode == "measurement" else compatibility()
    _write_json(args.output, payload)


if __name__ == "__main__":
    main()
