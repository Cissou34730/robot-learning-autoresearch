"""Characterize compiled arm dynamics under bounded, known actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


FRAME_SKIP = 10
POSTURE_SET = (
    ("fully_extended", (0.0, 0.0)),
    ("open_representative", (0.8, -1.2)),
    ("folded_representative", (-1.2, 1.8)),
    ("inner_workspace_posture", (0.0, 2.4)),
)
ACTION_SET = (
    ("shoulder_positive", (1.0, 0.0)),
    ("elbow_positive", (0.0, 1.0)),
    ("both_positive", (1.0, 1.0)),
    ("both_negative", (-1.0, -1.0)),
)


def _float_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in np.asarray(values).reshape(-1)]


def _compiled_model_facts(model: mujoco.MjModel) -> dict:
    actuator_forcerange = np.asarray(model.actuator_forcerange)
    body_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        for body_id in range(model.nbody)
    ]
    return {
        "timestep_seconds": float(model.opt.timestep),
        "integrator": int(model.opt.integrator),
        "solver": int(model.opt.solver),
        "solver_tolerance": float(model.opt.tolerance),
        "body_names": body_names,
        "body_mass": _float_list(model.body_mass),
        "body_inertia": [
            _float_list(inertia) for inertia in np.asarray(model.body_inertia)
        ],
        "dof_damping": _float_list(model.dof_damping),
        "dof_armature": _float_list(model.dof_armature),
        "actuator_gear": [
            _float_list(gear) for gear in np.asarray(model.actuator_gear)
        ],
        "actuator_ctrlrange": [
            _float_list(control_range)
            for control_range in np.asarray(model.actuator_ctrlrange)
        ],
        "actuator_forcerange": [
            _float_list(force_range) for force_range in actuator_forcerange
        ],
        "actuator_forcelimited": [
            bool(value) for value in np.asarray(model.actuator_forcelimited)
        ],
    }


def _reset_posture(model: mujoco.MjModel, data: mujoco.MjData, qpos: tuple[float, float]) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:2] = qpos
    data.qvel[:2] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _sample_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    control_step: int,
    action: tuple[float, float],
    phase: str,
) -> dict:
    site_position = np.asarray(data.site_xpos[site_id])
    spatial_velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(
        model,
        data,
        mujoco.mjtObj.mjOBJ_SITE,
        site_id,
        spatial_velocity,
        0,
    )
    site_velocity = spatial_velocity[3:]
    return {
        "control_step": control_step,
        "phase": phase,
        "action": [float(value) for value in action],
        "qpos": _float_list(data.qpos[:2]),
        "qvel": _float_list(data.qvel[:2]),
        "qacc": _float_list(data.qacc[:2]),
        "actuator_force": _float_list(data.actuator_force),
        "end_effector_position": _float_list(site_position),
        "end_effector_velocity": _float_list(site_velocity),
        "end_effector_speed": float(np.linalg.norm(site_velocity)),
    }


def _run_trace(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    qpos: tuple[float, float],
    action: tuple[float, float],
    impulse_control_steps: int = 10,
    release_control_steps: int = 100,
) -> dict:
    _reset_posture(model, data, qpos)
    trace = [
        _sample_state(model, data, site_id, 0, (0.0, 0.0), "initial")
    ]
    for control_step in range(1, impulse_control_steps + release_control_steps + 1):
        if control_step <= impulse_control_steps:
            applied_action = action
            phase = "impulse"
        else:
            applied_action = (0.0, 0.0)
            phase = "release"
        data.ctrl[:] = applied_action
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        trace.append(
            _sample_state(model, data, site_id, control_step, applied_action, phase)
        )

    impulse_samples = trace[1 : impulse_control_steps + 1]
    release_samples = trace[impulse_control_steps + 1 :]
    return {
        "posture_qpos": [float(value) for value in qpos],
        "commanded_action": [float(value) for value in action],
        "impulse_control_steps": impulse_control_steps,
        "release_control_steps": release_control_steps,
        "initial_state": trace[0],
        "trace": trace,
        "summary": {
            "peak_abs_qvel_during_impulse": float(
                max(np.max(np.abs(sample["qvel"])) for sample in impulse_samples)
            ),
            "peak_abs_qacc_during_impulse": float(
                max(np.max(np.abs(sample["qacc"])) for sample in impulse_samples)
            ),
            "peak_end_effector_speed_during_impulse": float(
                max(sample["end_effector_speed"] for sample in impulse_samples)
            ),
            "release_final_abs_qvel": float(
                np.max(np.abs(release_samples[-1]["qvel"]))
            ),
            "release_final_end_effector_speed": float(
                release_samples[-1]["end_effector_speed"]
            ),
            "release_max_abs_qvel": float(
                max(np.max(np.abs(sample["qvel"])) for sample in release_samples)
            ),
        },
    }


def characterize(artifact: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    if site_id < 0:
        raise RuntimeError("compiled model does not contain end_effector site")

    traces = []
    for posture_name, qpos in POSTURE_SET:
        for action_name, action in ACTION_SET:
            trace = _run_trace(model, data, site_id, qpos, action)
            trace["posture_name"] = posture_name
            trace["action_name"] = action_name
            traces.append(trace)

    result = {
        "schema_version": 1,
        "measurement": "compiled_system_characterization",
        "model_xml": str(TWO_JOINT_ARM_XML_PATH),
        "frame_skip": FRAME_SKIP,
        "control_interval_seconds": float(model.opt.timestep * FRAME_SKIP),
        "measurement_design": {
            "postures": [
                {"name": name, "qpos": [float(value) for value in qpos]}
                for name, qpos in POSTURE_SET
            ],
            "actions": [
                {"name": name, "action": [float(value) for value in action]}
                for name, action in ACTION_SET
            ],
            "trace_semantics": (
                "Each trace starts from zero velocity, applies the bounded action "
                "for ten control intervals, then applies zero action for one "
                "hundred control intervals."
            ),
        },
        "compiled_model": _compiled_model_facts(model),
        "traces": traces,
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    characterize(args.artifact)


if __name__ == "__main__":
    main()
