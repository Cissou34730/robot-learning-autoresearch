"""Compare matched near-limit holds with and without the shoulder constraint."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


FRAME_SKIP = 10
CONTROL_STEPS = 240
HOLD_STEPS_REQUIRED = 100
SUCCESS_THRESHOLD = 0.01
SHOULDER_JOINT_ID = 0
JOINT_LIMIT = np.deg2rad(170.0)
POSITION_GAIN = np.asarray([1.2, 0.8], dtype=np.float64)
VELOCITY_GAIN = np.asarray([0.15, 0.10], dtype=np.float64)
TARGET_STATES = (
    (-2.80, 2.40),
    (-2.90, 2.40),
    (-2.96, 2.40),
    (-JOINT_LIMIT, 2.40),
    (-2.90, 2.60),
    (-2.96, 2.60),
    (-JOINT_LIMIT, 2.60),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


def end_effector_position(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    del model
    return data.site("end_effector").xpos.copy()


def target_position(qpos: np.ndarray) -> np.ndarray:
    return np.asarray(
        [
            0.12 * np.cos(qpos[0]) + 0.10 * np.cos(qpos[0] + qpos[1]),
            0.12 * np.sin(qpos[0]) + 0.10 * np.sin(qpos[0] + qpos[1]),
            0.02,
        ],
        dtype=np.float64,
    )


def reset_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = qvel
    data.mocap_pos[0] = target
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
    target_qpos: np.ndarray,
    limited: bool,
) -> dict:
    initial_qpos = target_qpos + np.asarray([0.30, 0.0], dtype=np.float64)
    initial_qvel = np.zeros(2, dtype=np.float64)
    target = target_position(target_qpos)
    reset_state(model, data, initial_qpos, initial_qvel, target)

    rows: list[dict] = []
    first_reach_step: int | None = None
    current_held_steps = 0
    max_held_steps = 0
    hold_interruptions = 0
    was_in_tolerance = False
    first_constraint_step: int | None = None
    for control_step in range(1, CONTROL_STEPS + 1):
        qpos = data.qpos[:2].copy()
        qvel = data.qvel[:2].copy()
        action = np.clip(
            POSITION_GAIN * (target_qpos - qpos) - VELOCITY_GAIN * qvel,
            -1.0,
            1.0,
        )
        data.ctrl[:] = action
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)

        distance = float(np.linalg.norm(end_effector_position(model, data) - target))
        in_tolerance = distance <= SUCCESS_THRESHOLD
        if in_tolerance:
            if first_reach_step is None:
                first_reach_step = control_step
            current_held_steps += 1
            max_held_steps = max(max_held_steps, current_held_steps)
        elif was_in_tolerance:
            hold_interruptions += 1
            current_held_steps = 0
        else:
            current_held_steps = 0
        was_in_tolerance = in_tolerance

        shoulder_constraint_force = float(data.qfrc_constraint[SHOULDER_JOINT_ID])
        if (
            first_constraint_step is None
            and abs(shoulder_constraint_force) > 1e-8
        ):
            first_constraint_step = control_step
        rows.append(
            {
                "control_step": control_step,
                "distance_m": distance,
                "in_tolerance": in_tolerance,
                "qpos": data.qpos[:2].copy().tolist(),
                "qvel": data.qvel[:2].copy().tolist(),
                "qacc": data.qacc[:2].copy().tolist(),
                "action": data.ctrl[:2].copy().tolist(),
                "qfrc_actuator": data.qfrc_actuator[:2].copy().tolist(),
                "qfrc_constraint": data.qfrc_constraint[:2].copy().tolist(),
                "shoulder_constraint_force": shoulder_constraint_force,
                "constraints": constraint_rows(data),
            }
        )

    return {
        "limited": limited,
        "target_qpos": target_qpos.tolist(),
        "target_position": target.tolist(),
        "initial_qpos": initial_qpos.tolist(),
        "initial_qvel": initial_qvel.tolist(),
        "first_constraint_step": first_constraint_step,
        "first_reach_step": first_reach_step,
        "max_held_steps": max_held_steps,
        "hold_interruptions": hold_interruptions,
        "success": max_held_steps >= HOLD_STEPS_REQUIRED,
        "response": rows,
    }


def compare_preconstraint_trajectories(
    limited_trial: dict, unlimited_trial: dict
) -> dict:
    limited_rows = limited_trial["response"]
    unlimited_rows = unlimited_trial["response"]
    constraint_step = limited_trial["first_constraint_step"]
    prefix_length = (
        CONTROL_STEPS
        if constraint_step is None
        else max(int(constraint_step) - 1, 0)
    )
    qpos_differences = []
    qvel_differences = []
    for index in range(prefix_length):
        qpos_differences.append(
            np.max(
                np.abs(
                    np.asarray(limited_rows[index]["qpos"])
                    - np.asarray(unlimited_rows[index]["qpos"])
                )
            )
        )
        qvel_differences.append(
            np.max(
                np.abs(
                    np.asarray(limited_rows[index]["qvel"])
                    - np.asarray(unlimited_rows[index]["qvel"])
                )
            )
        )
    return {
        "preconstraint_control_steps": prefix_length,
        "max_preconstraint_qpos_difference": float(
            max(qpos_differences, default=0.0)
        ),
        "max_preconstraint_qvel_difference": float(
            max(qvel_differences, default=0.0)
        ),
    }


def collect_measurement() -> dict:
    limited_model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    unlimited_model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    unlimited_model.jnt_limited[SHOULDER_JOINT_ID] = 0
    limited_data = mujoco.MjData(limited_model)
    unlimited_data = mujoco.MjData(unlimited_model)

    trials = []
    for shoulder, elbow in TARGET_STATES:
        target_qpos = np.asarray([shoulder, elbow], dtype=np.float64)
        limited_trial = run_trial(
            limited_model, limited_data, target_qpos, limited=True
        )
        unlimited_trial = run_trial(
            unlimited_model, unlimited_data, target_qpos, limited=False
        )
        trials.append(
            {
                "target_qpos": target_qpos.tolist(),
                "target_radius_cm": float(
                    np.linalg.norm(limited_trial["target_position"][:2]) * 100.0
                ),
                "target_angle_degrees": float(
                    np.degrees(
                        np.arctan2(
                            limited_trial["target_position"][1],
                            limited_trial["target_position"][0],
                        )
                    )
                ),
                "limited": limited_trial,
                "unlimited_counterfactual": unlimited_trial,
                "preconstraint_comparison": compare_preconstraint_trajectories(
                    limited_trial, unlimited_trial
                ),
            }
        )
    return {
        "schema_version": 1,
        "experiment": "matched_post_constraint_hold_comparison",
        "measurement_semantics": {
            "integration_timestep_seconds": float(limited_model.opt.timestep),
            "control_interval_steps": FRAME_SKIP,
            "control_interval_seconds": float(
                limited_model.opt.timestep * FRAME_SKIP
            ),
            "control_steps": CONTROL_STEPS,
            "hold_steps_required": HOLD_STEPS_REQUIRED,
            "success_threshold_m": SUCCESS_THRESHOLD,
            "controller": (
                "identical saturated joint-space PD replay from matched "
                "near-limit initial states"
            ),
            "counterfactual": (
                "same compiled model and target with only the shoulder "
                "joint limit disabled"
            ),
            "constraint_force_semantics": (
                "generalized MuJoCo qfrc_constraint shoulder component "
                "recorded after each control interval"
            ),
        },
        "compiled_model": {
            "joint_range": limited_model.jnt_range.tolist(),
            "joint_limited_official": limited_model.jnt_limited.tolist(),
            "joint_limited_counterfactual": unlimited_model.jnt_limited.tolist(),
            "actuator_gear": limited_model.actuator_gear.tolist(),
            "actuator_ctrlrange": limited_model.actuator_ctrlrange.tolist(),
            "dof_armature": limited_model.dof_armature.tolist(),
            "dof_damping": limited_model.dof_damping.tolist(),
        },
        "trials": trials,
    }


def main() -> None:
    args = parse_args()
    artifact = collect_measurement()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
