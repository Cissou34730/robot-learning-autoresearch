"""Measure residual-policy arrival states against local plant feedback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    UPPER_ARM_LENGTH,
)
from robot_learning.scenario.environment import make_evaluation_env


FRAME_SKIP = 10
CONTROL_STEPS = 100
SUCCESS_THRESHOLD = 0.01


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_configuration(radius: float, angle: float, elbow_sign: float) -> np.ndarray:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return np.array([_wrap_to_pi(float(shoulder)), elbow], dtype=np.float64)


def _set_state(
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
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _distance(data: mujoco.MjData, target: np.ndarray) -> float:
    return float(np.linalg.norm(data.site("end_effector").xpos - target))


def _site_linear_velocity(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> np.ndarray:
    jacobian = np.zeros((3, model.nv), dtype=np.float64)
    rotational_jacobian = np.zeros((3, model.nv), dtype=np.float64)
    mujoco.mj_jacSite(model, data, jacobian, rotational_jacobian, site_id)
    return (jacobian @ data.qvel)[:2].copy()


def _advance(model: mujoco.MjModel, data: mujoco.MjData, action: np.ndarray) -> None:
    data.ctrl[:] = np.clip(action, -1.0, 1.0)
    for _ in range(FRAME_SKIP):
        mujoco.mj_step(model, data)


def _feedback_action(
    data: mujoco.MjData, qtarget: np.ndarray, controller: str
) -> np.ndarray:
    if controller == "zero":
        return np.zeros(2, dtype=np.float64)
    if controller == "local_pd":
        kp, kd = 1.0, 0.2
    elif controller == "strong_local_pd":
        kp, kd = 3.0, 0.8
    else:
        raise ValueError(f"unknown controller: {controller}")
    error = np.array(
        [_wrap_to_pi(float(target - current)) for current, target in zip(data.qpos, qtarget)]
    )
    return np.clip((kp * error - kd * data.qvel) / 5.0, -1.0, 1.0)


def _retention_rollout(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    qtarget: np.ndarray,
    qpos: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
    controller: str,
) -> dict:
    _set_state(model, data, qpos, qvel, target)
    distances: list[float] = []
    speeds: list[float] = []
    held_steps = 0
    max_held_steps = 0
    entries = 0
    exits = 0
    previous_inside = False
    saturated_steps = 0

    for _ in range(CONTROL_STEPS):
        action = _feedback_action(data, qtarget, controller)
        saturated_steps += int(bool(np.any(np.abs(action) >= 0.999999)))
        _advance(model, data, action)
        distance = _distance(data, target)
        inside = distance <= SUCCESS_THRESHOLD
        if inside and not previous_inside:
            entries += 1
        if previous_inside and not inside:
            exits += 1
        if inside:
            held_steps += 1
            max_held_steps = max(max_held_steps, held_steps)
        else:
            held_steps = 0
        previous_inside = inside
        distances.append(distance)
        speeds.append(float(np.linalg.norm(data.qvel)))

    return {
        "controller": controller,
        "completed_hold": bool(max_held_steps >= CONTROL_STEPS),
        "in_tolerance_steps": int(sum(value <= SUCCESS_THRESHOLD for value in distances)),
        "max_consecutive_tolerance_steps": int(max_held_steps),
        "sampled_boundary_entries": int(entries),
        "sampled_boundary_exits": int(exits),
        "sampled_boundary_crossings": int(entries + exits),
        "minimum_distance_m": float(min(distances)),
        "maximum_distance_m": float(max(distances)),
        "final_distance_m": float(distances[-1]),
        "minimum_retention_margin_m": float(SUCCESS_THRESHOLD - max(distances)),
        "maximum_joint_speed_rad_s": float(max(speeds)),
        "saturated_control_steps": int(saturated_steps),
    }


def _braking_probe(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    qpos: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
) -> dict:
    _set_state(model, data, qpos, qvel, target)
    speed_before = float(np.linalg.norm(data.qvel))
    opposing_action = -np.sign(data.qvel)
    _advance(model, data, opposing_action)
    speed_after = float(np.linalg.norm(data.qvel))
    distance_after = _distance(data, target)
    return {
        "speed_before_rad_s": speed_before,
        "speed_after_rad_s": speed_after,
        "speed_reduction_rad_s": float(speed_before - speed_after),
        "distance_after_m": distance_after,
        "one_step_retention_margin_m": float(SUCCESS_THRESHOLD - distance_after),
    }


def _compiled_properties(model: mujoco.MjModel) -> dict:
    return {
        "timestep_s": float(model.opt.timestep),
        "integrator": int(model.opt.integrator),
        "solver": int(model.opt.solver),
        "body_masses_kg": [float(value) for value in model.body_mass],
        "dof_damping": [float(value) for value in model.dof_damping],
        "dof_armature": [float(value) for value in model.dof_armature],
        "actuator_gear": model.actuator_gear[:, 0].astype(float).tolist(),
        "actuator_ctrlrange": model.actuator_ctrlrange.astype(float).tolist(),
    }


def _angle_sector(angle_degrees: float) -> int:
    return int(np.floor((angle_degrees + 180.0) / 30.0) * 30.0 - 180.0)


def _select_branch(
    model: mujoco.MjModel,
    radius: float,
    angle: float,
    qpos: np.ndarray,
) -> tuple[str, np.ndarray, float]:
    branch_candidates = []
    for branch_name, elbow_sign in (("open", 1.0), ("folded", -1.0)):
        qtarget = _branch_configuration(radius, angle, elbow_sign)
        valid = bool(
            np.all(qtarget >= model.jnt_range[:2, 0])
            and np.all(qtarget <= model.jnt_range[:2, 1])
        )
        if valid:
            error = np.array(
                [_wrap_to_pi(float(current - desired)) for current, desired in zip(qpos, qtarget)]
            )
            branch_candidates.append((float(np.linalg.norm(error)), branch_name, qtarget))
    if not branch_candidates:
        raise RuntimeError("residual target has no valid inverse-kinematic branch")
    residual, branch_name, qtarget = min(branch_candidates, key=lambda item: item[0])
    return branch_name, qtarget, residual


def _arrival_diagnostics(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    qpos: np.ndarray,
    qvel: np.ndarray,
    task_velocity: np.ndarray,
    target: np.ndarray,
    radius: float,
    angle: float,
    state_selection: str,
    first_reach_step: int | None,
) -> tuple[dict, str, np.ndarray]:
    branch_name, qtarget, branch_residual = _select_branch(
        model, radius, angle, qpos
    )
    _set_state(model, data, qpos, qvel, target)
    end_effector = np.asarray(data.site("end_effector").xpos, dtype=np.float64)
    displacement = target[:2] - end_effector[:2]
    distance = float(np.linalg.norm(displacement))
    radial_unit = displacement / distance if distance > 0.0 else np.zeros(2)
    radial_velocity = float(np.dot(task_velocity, radial_unit))
    tangential_velocity = task_velocity - radial_velocity * radial_unit
    return (
        {
            "state_selection": state_selection,
            "first_reach_step": first_reach_step,
            "selected_branch": branch_name,
            "branch_residual_rad": branch_residual,
            "qpos_rad": qpos.tolist(),
            "qvel_rad_s": qvel.tolist(),
            "end_effector_velocity_m_s": task_velocity.tolist(),
            "radial_velocity_m_s": radial_velocity,
            "tangential_speed_m_s": float(np.linalg.norm(tangential_velocity)),
            "joint_speed_rad_s": float(np.linalg.norm(qvel)),
        },
        branch_name,
        qtarget,
    )


def measure(candidate: Path, episodes: int, seed: int) -> dict:
    runtime = load_runtime(candidate)
    env = make_evaluation_env(policy_runtime=runtime)
    model = env.model
    data = env.data
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    policy_records: list[dict] = []
    arrival_records: list[dict] = []
    residual_cases: list[dict] = []

    for episode in range(episodes):
        observation, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target = np.asarray(data.mocap_pos[0], dtype=np.float64).copy()
        target_radius = float(np.hypot(target[0], target[1]))
        target_angle = float(np.degrees(np.arctan2(target[1], target[0])))
        first_inside: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
        closest_state: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
        closest_distance = float("inf")
        first_reach_step: int | None = None
        max_held_steps = 0
        hold_interruptions = 0
        was_inside = False
        min_distance = float("inf")
        final_distance = float("nan")
        success = False
        steps = 0
        terminated = False
        truncated = False

        while not (terminated or truncated):
            action = runtime.predict(observation)
            observation, _, terminated, truncated, info = env.step(action)
            steps += 1
            distance = float(info["distance"])
            final_distance = distance
            min_distance = min(min_distance, distance)
            state = (
                data.qpos.copy(),
                data.qvel.copy(),
                _site_linear_velocity(model, data, site_id),
            )
            if distance < closest_distance:
                closest_distance = distance
                closest_state = state
            held_steps = int(info.get("held_steps", 0))
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                if first_inside is None:
                    first_inside = state
                    first_reach_step = steps
            elif was_inside:
                hold_interruptions += 1
            was_inside = held_steps > 0
            success = bool(info.get("is_success", False))

        policy_records.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_m": target_radius,
                "target_angle_degrees": target_angle,
                "angle_sector_start_degrees": _angle_sector(target_angle),
                "success": success,
                "steps": steps,
                "first_reach_step": first_reach_step,
                "min_distance_m": min_distance,
                "final_distance_m": final_distance,
                "max_held_steps": max_held_steps,
                "hold_interruptions": hold_interruptions,
            }
        )
        selected_state = first_inside or closest_state
        if selected_state is None:
            raise RuntimeError("failed policy episode did not produce a simulator state")
        qpos, qvel, task_velocity = selected_state
        state_selection = (
            "first_in_tolerance" if first_inside is not None else "closest_approach"
        )
        arrival, branch_name, qtarget = _arrival_diagnostics(
            model,
            data,
            qpos=qpos,
            qvel=qvel,
            task_velocity=task_velocity,
            target=target,
            radius=target_radius,
            angle=np.radians(target_angle),
            state_selection=state_selection,
            first_reach_step=first_reach_step,
        )
        zero_retention = _retention_rollout(
            model,
            data,
            qtarget=qtarget,
            qpos=qpos,
            qvel=qvel,
            target=target,
            controller="zero",
        )
        arrival_records.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_m": target_radius,
                "target_angle_degrees": target_angle,
                "angle_sector_start_degrees": _angle_sector(target_angle),
                "success": success,
                "policy_failure_class": (
                    None
                    if success
                    else (
                        "hold_interruption"
                        if first_inside is not None
                        else "no_first_reach"
                    )
                ),
                **arrival,
                "zero_action_retention": zero_retention,
            }
        )
        if success:
            continue
        residual_cases.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_m": target_radius,
                "target_angle_degrees": target_angle,
                "angle_sector_start_degrees": _angle_sector(target_angle),
                "policy_failure_class": (
                    "hold_interruption" if first_inside is not None else "no_first_reach"
                ),
                "state_selection": (
                    "first_in_tolerance" if first_inside is not None else "closest_approach"
                ),
                "qpos_rad": qpos.tolist(),
                "qvel_rad_s": qvel.tolist(),
                "selected_branch": branch_name,
                "branch_target_qpos_rad": qtarget.tolist(),
                "braking_probe": _braking_probe(
                    model, data, qpos=qpos, qvel=qvel, target=target
                ),
                "local_feedback": [
                    zero_retention,
                    *[
                        _retention_rollout(
                            model,
                            data,
                            qtarget=qtarget,
                            qpos=qpos,
                            qvel=qvel,
                            target=target,
                            controller=controller,
                        )
                        for controller in ("local_pd", "strong_local_pd")
                    ],
                ],
            }
        )

    controller_summary = {}
    for controller in ("zero", "local_pd", "strong_local_pd"):
        results = [
            result
            for case in residual_cases
            for result in case["local_feedback"]
            if result["controller"] == controller
        ]
        controller_summary[controller] = {
            "cases": len(results),
            "completed_holds": sum(result["completed_hold"] for result in results),
            "completion_rate": (
                sum(result["completed_hold"] for result in results) / len(results)
                if results
                else 0.0
            ),
            "mean_sampled_boundary_exits": (
                float(np.mean([result["sampled_boundary_exits"] for result in results]))
                if results
                else 0.0
            ),
            "mean_minimum_retention_margin_m": (
                float(
                    np.mean(
                        [result["minimum_retention_margin_m"] for result in results]
                    )
                )
                if results
                else 0.0
            ),
        }

    failed = [record for record in policy_records if not record["success"]]
    return {
        "schema_version": 1,
        "measurement": "matched_arrival_trajectory_and_local_feedback_margin",
        "candidate": str(candidate),
        "panel": {"episodes": episodes, "seed": seed},
        "control_interval": {
            "frame_skip": FRAME_SKIP,
            "control_steps": CONTROL_STEPS,
            "success_threshold_m": SUCCESS_THRESHOLD,
        },
        "compiled_properties": _compiled_properties(model),
        "policy_summary": {
            "successes": sum(record["success"] for record in policy_records),
            "failures": len(failed),
            "first_reaches": sum(
                record["first_reach_step"] is not None for record in policy_records
            ),
            "hold_interruptions": sum(
                record["hold_interruptions"] for record in policy_records
            ),
        },
        "local_feedback_summary": controller_summary,
        "arrival_records": arrival_records,
        "policy_episode_records": policy_records,
        "residual_cases": residual_cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=160)
    parser.add_argument("--seed", type=int, default=4200)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    if args.episodes < 1:
        raise ValueError("episodes must be positive")
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(
        json.dumps(measure(args.candidate, args.episodes, args.seed), indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
