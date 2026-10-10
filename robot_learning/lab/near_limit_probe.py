"""Measure joint-limit behavior during controlled approach and reversal."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


FRAME_SKIP = 10
APPROACH_CONTROL_STEPS = 20
REVERSAL_CONTROL_STEPS = 20
SHOULDER_JOINT_ID = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


def reset_state(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def constraint_rows(data: mujoco.MjData) -> list[dict]:
    return [
        {
            "type": int(data.efc_type[index]),
            "id": int(data.efc_id[index]),
            "force": float(data.efc_force[index]),
        }
        for index in range(int(data.nefc))
    ]


def run_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    start_qpos: np.ndarray,
    direction: float,
    start_label: str,
) -> dict:
    reset_state(model, data, start_qpos)
    response: list[dict] = []
    for phase, action, count in (
        (
            "approach",
            np.asarray([direction, 0.0], dtype=np.float64),
            APPROACH_CONTROL_STEPS,
        ),
        (
            "reversal",
            np.asarray([-direction, 0.0], dtype=np.float64),
            REVERSAL_CONTROL_STEPS,
        ),
    ):
        data.ctrl[:] = action
        for control_step in range(count):
            for _ in range(FRAME_SKIP):
                mujoco.mj_step(model, data)
            response.append(
                {
                    "phase": phase,
                    "control_step": control_step + 1,
                    "qpos": data.qpos.copy().tolist(),
                    "qvel": data.qvel.copy().tolist(),
                    "qacc": data.qacc.copy().tolist(),
                    "ctrl": data.ctrl.copy().tolist(),
                    "actuator_force": data.actuator_force.copy().tolist(),
                    "qfrc_actuator": data.qfrc_actuator.copy().tolist(),
                    "qfrc_constraint": data.qfrc_constraint.copy().tolist(),
                    "constraints": constraint_rows(data),
                }
            )
    return {
        "start_label": start_label,
        "start_qpos": start_qpos.tolist(),
        "approach_action": [direction, 0.0],
        "reversal_action": [-direction, 0.0],
        "response": response,
    }


def collect_measurement() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    trials = []
    for direction in (-1.0, 1.0):
        for start_angle, start_label in (
            (1.8, "interior"),
            (2.35, "near_limit"),
            (2.65, "very_near_limit"),
        ):
            for elbow_angle in (-0.8, 0.0, 0.8):
                start_qpos = np.asarray(
                    [direction * start_angle, elbow_angle], dtype=np.float64
                )
                trials.append(
                    run_trial(
                        model,
                        data,
                        start_qpos,
                        direction,
                        f"{start_label}_elbow_{elbow_angle:+.1f}",
                    )
                )
    return {
        "schema_version": 1,
        "experiment": "joint_limit_approach_and_reversal",
        "measurement_semantics": {
            "integration_timestep_seconds": float(model.opt.timestep),
            "control_interval_steps": FRAME_SKIP,
            "control_interval_seconds": float(model.opt.timestep * FRAME_SKIP),
            "approach_control_steps": APPROACH_CONTROL_STEPS,
            "reversal_control_steps": REVERSAL_CONTROL_STEPS,
            "constraint_force_semantics": (
                "MuJoCo efc constraint rows and generalized qfrc_constraint "
                "recorded after each control interval"
            ),
        },
        "compiled_model": {
            "joint_range": model.jnt_range.tolist(),
            "joint_limited": model.jnt_limited.tolist(),
            "actuator_gear": model.actuator_gear.tolist(),
            "actuator_ctrlrange": model.actuator_ctrlrange.tolist(),
            "dof_armature": model.dof_armature.tolist(),
            "dof_damping": model.dof_damping.tolist(),
        },
        "shoulder_joint_id": SHOULDER_JOINT_ID,
        "trials": trials,
    }


def main() -> None:
    args = parse_args()
    artifact = collect_measurement()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
