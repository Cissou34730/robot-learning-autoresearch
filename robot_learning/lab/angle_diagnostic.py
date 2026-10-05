"""Targeted geometry and trajectory diagnostic for the peak reach policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.task_spec import SUCCESS_THRESHOLD
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.observations import FOREARM_LENGTH, UPPER_ARM_LENGTH

NEGATIVE_FAILURE_REFERENCES = (
    (-150.62, 18.35),
    (-148.38, 17.49),
    (-147.95, 18.83),
    (-139.49, 16.54),
    (-131.47, 10.77),
    (-129.95, 10.85),
    (-129.86, 10.66),
    (-119.46, 7.92),
    (-118.78, 7.70),
)

NEGATIVE_SUCCESS_REFERENCES = (
    (-169.62, 16.72),
    (-167.61, 9.50),
    (-166.47, 6.65),
    (-163.12, 18.18),
    (-158.72, 15.61),
    (-153.82, 10.77),
    (-152.58, 14.95),
    (-151.29, 11.45),
    (-148.73, 6.89),
    (-146.20, 11.04),
)


def _wrap_to_pi(values: np.ndarray) -> np.ndarray:
    return (values + np.pi) % (2.0 * np.pi) - np.pi


def _json_float(value: float) -> float | None:
    value = float(value)
    return value if np.isfinite(value) else None


def _branch_solutions(angle_degrees: float, radius_cm: float) -> np.ndarray:
    radius = radius_cm / 100.0
    angle = np.radians(angle_degrees)
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 or cosine > 1.0:
        return np.empty((0, 2), dtype=np.float64)
    elbow = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    branches = []
    for q2 in (elbow, -elbow):
        q1 = angle - np.arctan2(
            FOREARM_LENGTH * np.sin(q2),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(q2),
        )
        branches.append((q1, q2))
    return np.asarray(branches, dtype=np.float64)


def _jacobian(qpos: np.ndarray) -> np.ndarray:
    q1, q2 = qpos
    q12 = q1 + q2
    return np.asarray(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1)
                - FOREARM_LENGTH * np.sin(q12),
                -FOREARM_LENGTH * np.sin(q12),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1)
                + FOREARM_LENGTH * np.cos(q12),
                FOREARM_LENGTH * np.cos(q12),
            ],
        ],
        dtype=np.float64,
    )


def _jacobian_metrics(qpos: np.ndarray) -> dict:
    singular_values = np.linalg.svd(_jacobian(qpos), compute_uv=False)
    minimum = float(singular_values[-1])
    maximum = float(singular_values[0])
    condition = maximum / minimum if minimum > 0.0 else float("inf")
    return {
        "minimum_singular_value": _json_float(minimum),
        "condition_number": _json_float(condition),
        "manipulability": _json_float(abs(float(np.linalg.det(_jacobian(qpos))))),
    }


def _branch_geometry(
    branches: np.ndarray, joint_limits: np.ndarray
) -> list[dict]:
    records = []
    for index, branch in enumerate(branches):
        lower_margin = branch - joint_limits[:, 0]
        upper_margin = joint_limits[:, 1] - branch
        feasible = bool(np.all(lower_margin >= 0.0) and np.all(upper_margin >= 0.0))
        records.append(
            {
                "branch": "elbow_up" if index == 0 else "elbow_down",
                "qpos_radians": branch.tolist(),
                "qpos_degrees": np.degrees(branch).tolist(),
                "feasible_under_joint_limits": feasible,
                "minimum_joint_limit_margin_degrees": float(
                    np.degrees(np.min(np.minimum(lower_margin, upper_margin)))
                ),
                **_jacobian_metrics(branch),
            }
        )
    return records


def _end_effector_velocity(env, site_id: int) -> np.ndarray:
    jacobian = np.zeros((3, env.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(env.model, env.data, jacobian, None, site_id)
    return jacobian @ env.data.qvel


def _trajectory_state(
    env,
    site_id: int,
    branches: np.ndarray,
    target: np.ndarray,
    held_steps: int,
    distance: float,
    action: np.ndarray,
) -> dict:
    qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
    qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
    ee_position = np.asarray(env.data.site("end_effector").xpos, dtype=np.float64)
    ee_velocity = _end_effector_velocity(env, site_id)
    branch_errors = _wrap_to_pi(branches - qpos)
    return {
        "qpos_radians": qpos.tolist(),
        "qvel_radians_per_second": qvel.tolist(),
        "end_effector_position_m": ee_position.tolist(),
        "end_effector_velocity_m_per_second": ee_velocity.tolist(),
        "end_effector_speed_m_per_second": float(np.linalg.norm(ee_velocity)),
        "target_distance_cm": 100.0 * float(distance),
        "held_steps": int(held_steps),
        "branch_error_norms_radians": np.linalg.norm(branch_errors, axis=1).tolist(),
        "jacobian": _jacobian_metrics(qpos),
        "action": np.asarray(action, dtype=np.float64).reshape(-1).tolist(),
        "actuator_command": np.asarray(env.data.ctrl, dtype=np.float64).copy().tolist(),
        "actuator_saturated": bool(np.any(np.abs(env.data.ctrl) >= 1.0 - 1e-9)),
        "target_position_m": target.tolist(),
    }


def _diagnostic_cases() -> list[dict]:
    cases = []
    for index, (angle, radius) in enumerate(NEGATIVE_FAILURE_REFERENCES):
        cases.append(
            {
                "case_id": f"negative_failure_reference_{index:02d}",
                "comparison_group": f"radius_match_{index:02d}",
                "reference_class": "prior_failure",
                "angle_degrees": angle,
                "radius_cm": radius,
            }
        )
        cases.append(
            {
                "case_id": f"mirrored_angle_control_{index:02d}",
                "comparison_group": f"radius_match_{index:02d}",
                "reference_class": "mirrored_angle_control",
                "angle_degrees": -angle,
                "radius_cm": radius,
            }
        )
    for index, (angle, radius) in enumerate(NEGATIVE_SUCCESS_REFERENCES):
        cases.append(
            {
                "case_id": f"negative_success_reference_{index:02d}",
                "comparison_group": "prior_negative_successes",
                "reference_class": "prior_success",
                "angle_degrees": angle,
                "radius_cm": radius,
            }
        )
    return cases


def run_diagnostic(model_path: Path, artifact_path: Path) -> None:
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    site_id = mujoco.mj_name2id(
        env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    joint_limits = np.asarray(env.model.jnt_range[:2], dtype=np.float64).copy()
    cases = _diagnostic_cases()
    episode_records = []

    for case_index, case in enumerate(cases):
        branches = _branch_solutions(case["angle_degrees"], case["radius_cm"])
        if len(branches) == 0:
            raise ValueError(f"Target is outside the analytic workspace: {case}")
        branch_geometry = _branch_geometry(branches, joint_limits)

        env.reset(seed=10000 + case_index)
        angle = np.radians(case["angle_degrees"])
        radius = case["radius_cm"] / 100.0
        target = np.asarray(
            [radius * np.cos(angle), radius * np.sin(angle), env.data.mocap_pos[0, 2]],
            dtype=np.float64,
        )
        env.data.mocap_pos[0] = target
        mujoco.mj_forward(env.model, env.data)
        env._previous_distance = env._distance_to_target()
        observation = env._observation()
        runtime.reset()

        trajectory = []
        first_entry = None
        hold_interruptions = 0
        was_in_tolerance = False
        max_held_steps = 0
        terminated = False
        truncated = False
        reward_total = 0.0

        while not (terminated or truncated):
            action = np.asarray(runtime.predict(observation), dtype=np.float64)
            observation, reward, terminated, truncated, info = env.step(action)
            reward_total += float(reward)
            distance = float(info["distance"])
            held_steps = int(info["held_steps"])
            if held_steps > 0 and first_entry is None:
                first_entry = _trajectory_state(
                    env,
                    site_id,
                    branches,
                    target,
                    held_steps,
                    distance,
                    action,
                )
                first_entry["control_step"] = len(trajectory) + 1
            if held_steps == 0 and was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            max_held_steps = max(max_held_steps, held_steps)
            state = _trajectory_state(
                env, site_id, branches, target, held_steps, distance, action
            )
            state["control_step"] = len(trajectory) + 1
            trajectory.append(state)

        final_state = trajectory[-1]
        episode_records.append(
            {
                **case,
                "episode_seed": 10000 + case_index,
                "branch_geometry": branch_geometry,
                "success": bool(info["is_success"]),
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "steps": len(trajectory),
                "reward_total": reward_total,
                "first_entry": first_entry,
                "max_held_steps": max_held_steps,
                "hold_interruptions": hold_interruptions,
                "saturated_control_steps": sum(
                    state["actuator_saturated"] for state in trajectory
                ),
                "final_state": final_state,
                "trajectory": trajectory,
            }
        )

    artifact = {
        "schema_version": 1,
        "instrument": "angle_by_radius_trajectory_diagnostic",
        "candidate": "T1:checkpoint-100352",
        "model": str(model_path),
        "success_threshold_m": SUCCESS_THRESHOLD,
        "joint_limits_degrees": np.degrees(joint_limits).tolist(),
        "target_cases": len(episode_records),
        "case_design": {
            "prior_failure_references": len(NEGATIVE_FAILURE_REFERENCES),
            "mirrored_angle_controls": len(NEGATIVE_FAILURE_REFERENCES),
            "prior_negative_success_references": len(NEGATIVE_SUCCESS_REFERENCES),
            "trajectory_sampling": "one record per 20 ms control step",
        },
        "episodes": episode_records,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()
    run_diagnostic(args.model, args.artifact)


if __name__ == "__main__":
    main()
