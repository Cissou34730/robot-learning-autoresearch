"""Measure compiled dynamics and sampled open-loop torque response."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH

FRAME_SKIP = 10
CONTROL_DT = 0.020
PULSE_STEPS = 5
RELEASE_STEPS = 30


def _as_lists(values: np.ndarray) -> list:
    return np.asarray(values).tolist()


def compiled_model_summary(model: mujoco.MjModel) -> dict:
    return {
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "nbody": int(model.nbody),
            "ngeom": int(model.ngeom),
        },
        "options": {
            "timestep_s": float(model.opt.timestep),
            "integrator": int(model.opt.integrator),
            "solver": int(model.opt.solver),
            "iterations": int(model.opt.iterations),
            "tolerance": float(model.opt.tolerance),
            "gravity": _as_lists(model.opt.gravity),
        },
        "bodies": {
            "mass_kg": _as_lists(model.body_mass),
            "inertia_kg_m2": _as_lists(model.body_inertia),
        },
        "joints": {
            "damping": _as_lists(model.dof_damping),
            "armature": _as_lists(model.dof_armature),
            "range_rad": _as_lists(model.jnt_range),
        },
        "actuators": {
            "gear": _as_lists(model.actuator_gear),
            "ctrlrange": _as_lists(model.actuator_ctrlrange),
            "forcerange": _as_lists(model.actuator_forcerange),
        },
        "geoms": {
            "contype": _as_lists(model.geom_contype),
            "conaffinity": _as_lists(model.geom_conaffinity),
        },
    }


def _end_effector_position(model: mujoco.MjModel, data: mujoco.MjData) -> list[float]:
    return np.asarray(data.site("end_effector").xpos, dtype=np.float64).tolist()


def _reset_state(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: tuple[float, float]
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def run_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    posture: str,
    qpos: tuple[float, float],
    action: tuple[float, float],
) -> dict:
    _reset_state(model, data, qpos)
    initial_ee = np.asarray(_end_effector_position(model, data), dtype=np.float64)
    samples: list[dict] = []
    total_steps = PULSE_STEPS + RELEASE_STEPS

    for control_step in range(total_steps):
        command = action if control_step < PULSE_STEPS else (0.0, 0.0)
        data.ctrl[:] = command
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        ee = np.asarray(_end_effector_position(model, data), dtype=np.float64)
        samples.append(
            {
                "control_step": control_step + 1,
                "phase": "pulse" if control_step < PULSE_STEPS else "release",
                "action": list(command),
                "qpos_rad": _as_lists(data.qpos),
                "qvel_rad_s": _as_lists(data.qvel),
                "end_effector_m": ee.tolist(),
                "end_effector_displacement_m": float(np.linalg.norm(ee - initial_ee)),
                "contacts": int(data.ncon),
            }
        )

    pulse_samples = samples[:PULSE_STEPS]
    release_samples = samples[PULSE_STEPS:]
    release_ee = np.asarray(
        release_samples[0]["end_effector_m"], dtype=np.float64
    )
    all_qvel = np.asarray([sample["qvel_rad_s"] for sample in samples])
    pulse_qpos = np.asarray([sample["qpos_rad"] for sample in pulse_samples])
    post_release_ee = np.asarray(
        [sample["end_effector_m"] for sample in release_samples]
    )
    return {
        "posture": posture,
        "initial_qpos_rad": list(qpos),
        "action": list(action),
        "pulse_steps": PULSE_STEPS,
        "release_steps": RELEASE_STEPS,
        "samples": samples,
        "summary": {
            "max_abs_joint_velocity_rad_s": _as_lists(np.max(np.abs(all_qvel), axis=0)),
            "max_abs_q2_change_during_pulse_rad": float(
                np.max(np.abs(pulse_qpos[:, 1] - qpos[1]))
            ),
            "max_ee_displacement_m": float(
                max(sample["end_effector_displacement_m"] for sample in samples)
            ),
            "post_release_max_ee_displacement_from_release_m": float(
                np.max(np.linalg.norm(post_release_ee - release_ee, axis=1))
            ),
            "post_release_final_ee_displacement_from_release_m": float(
                np.linalg.norm(post_release_ee[-1] - release_ee)
            ),
            "max_contacts": max(sample["contacts"] for sample in samples),
        },
    }


def measure() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    postures = {
        "singular_reset": (0.0, 0.0),
        "open_branch_representative": (0.8, 1.0),
        "folded_branch_representative": (0.8, -1.0),
    }
    actions = {
        "shoulder_positive": (1.0, 0.0),
        "elbow_positive": (0.0, 1.0),
        "shoulder_negative": (-1.0, 0.0),
        "elbow_negative": (0.0, -1.0),
    }
    trials = [
        run_trial(
            model,
            data,
            posture=posture,
            qpos=qpos,
            action=action,
        )
        for posture, qpos in postures.items()
        for action in actions.values()
    ]
    return {
        "schema_version": 1,
        "measurement": "compiled_model_and_open_loop_response",
        "xml": str(TWO_JOINT_ARM_XML_PATH),
        "control": {
            "physics_timestep_s": float(model.opt.timestep),
            "frame_skip": FRAME_SKIP,
            "control_interval_s": CONTROL_DT,
            "pulse_steps": PULSE_STEPS,
            "release_steps": RELEASE_STEPS,
        },
        "compiled_model": compiled_model_summary(model),
        "trials": trials,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = measure()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
