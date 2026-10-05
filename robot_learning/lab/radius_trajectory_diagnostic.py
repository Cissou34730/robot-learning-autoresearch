"""Radius-stratified trajectory telemetry for inquiry I1."""

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import FRAME_SKIP, SUCCESS_THRESHOLD
from robot_learning.scenario.environment import make_evaluation_env

CONTROL_DT = 0.002 * FRAME_SKIP
ACTION_LIMIT = 1.0
MOTOR_GEAR = 5.0
RADIUS_BINS_CM = ((6.0, 10.0), (10.0, 14.0), (14.0, 18.0), (18.0, 20.0))


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def branch_metrics(qpos: np.ndarray, target: np.ndarray) -> tuple[str, float, float]:
    target_x, target_y = float(target[0]), float(target[1])
    cosine = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    open_error = np.array(
        [
            wrap_to_pi(shoulder_for_elbow(elbow_open) - float(qpos[0])),
            wrap_to_pi(elbow_open - float(qpos[1])),
        ]
    )
    folded_elbow = -elbow_open
    folded_error = np.array(
        [
            wrap_to_pi(shoulder_for_elbow(folded_elbow) - float(qpos[0])),
            wrap_to_pi(folded_elbow - float(qpos[1])),
        ]
    )
    open_distance = float(np.linalg.norm(open_error))
    folded_distance = float(np.linalg.norm(folded_error))
    if open_distance <= folded_distance:
        return "open", open_distance, folded_distance - open_distance
    return "folded", folded_distance, open_distance - folded_distance


def jacobian_singular_values(qpos: np.ndarray) -> tuple[float, float]:
    q1, q2 = float(qpos[0]), float(qpos[1])
    q12 = q1 + q2
    jacobian = np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1) - FOREARM_LENGTH * np.sin(q12),
                -FOREARM_LENGTH * np.sin(q12),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1) + FOREARM_LENGTH * np.cos(q12),
                FOREARM_LENGTH * np.cos(q12),
            ],
        ]
    )
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    return float(singular_values[-1]), float(singular_values[0])


def finite_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "maximum": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "maximum": float(np.max(array)),
    }


def radius_bin(radius_cm: float) -> str:
    for lower, upper in RADIUS_BINS_CM[:-1]:
        if lower <= radius_cm < upper:
            return f"{lower:.0f}-{upper:.0f}cm"
    lower, upper = RADIUS_BINS_CM[-1]
    if lower <= radius_cm <= upper:
        return f"{lower:.0f}-{upper:.0f}cm"
    raise ValueError(f"target radius outside official range: {radius_cm}")


def summarize_episodes(episodes: list[dict]) -> dict:
    successes = [episode for episode in episodes if episode["success"]]
    entered = [episode for episode in episodes if episode["tolerance_entry_step"] is not None]
    return {
        "episodes": len(episodes),
        "successes": sum(bool(episode["success"]) for episode in episodes),
        "success_percent": (
            100.0 * sum(bool(episode["success"]) for episode in episodes) / len(episodes)
            if episodes
            else None
        ),
        "entered_tolerance": len(entered),
        "never_entered_tolerance": len(episodes) - len(entered),
        "entry_rate_percent": 100.0 * len(entered) / len(episodes)
        if episodes
        else None,
        "success_among_entries_percent": 100.0 * len(successes) / len(entered)
        if entered
        else None,
        "first_entry_speed_mps": finite_stats(
            [
                episode["first_entry_speed_mps"]
                for episode in entered
                if episode["first_entry_speed_mps"] is not None
            ]
        ),
        "first_entry_radial_speed_mps": finite_stats(
            [
                episode["first_entry_radial_speed_mps"]
                for episode in entered
                if episode["first_entry_radial_speed_mps"] is not None
            ]
        ),
        "minimum_distance_cm": finite_stats(
            [episode["minimum_distance_cm"] for episode in episodes]
        ),
        "speed_at_minimum_distance_mps": finite_stats(
            [episode["speed_at_minimum_distance_mps"] for episode in episodes]
        ),
        "peak_speed_mps": finite_stats([episode["peak_speed_mps"] for episode in episodes]),
        "minimum_jacobian_sigma": finite_stats(
            [episode["minimum_jacobian_sigma"] for episode in episodes]
        ),
        "saturated_action_episode_percent": 100.0
        * sum(episode["saturated_action_steps"] > 0 for episode in episodes)
        / len(episodes)
        if episodes
        else None,
        "clipped_action_episode_percent": 100.0
        * sum(episode["clipped_action_steps"] > 0 for episode in episodes)
        / len(episodes)
        if episodes
        else None,
        "branch_counts": {
            "open": sum(episode["branch_counts"]["open"] for episode in episodes),
            "folded": sum(episode["branch_counts"]["folded"] for episode in episodes),
        },
        "branch_switches": int(sum(episode["branch_switches"] for episode in episodes)),
        "hold_interruptions": int(
            sum(episode["hold_interruptions"] for episode in episodes)
        ),
    }


def measure(model_path: Path, episodes: int, seed: int) -> dict:
    if episodes < 1:
        raise ValueError("episodes must be positive")

    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    measured_episodes: list[dict] = []

    for episode_index in range(episodes):
        obs, _ = env.reset(seed=seed + episode_index)
        runtime.reset()
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        target_radius_cm = float(np.hypot(target[0], target[1]) * 100.0)
        target_angle_degrees = float(np.degrees(np.arctan2(target[1], target[0])))
        trajectory: list[dict] = []
        reward_total = 0.0
        terminated = False
        truncated = False
        previous_in_tolerance = False
        tolerance_entry_step: int | None = None
        hold_interruptions = 0
        first_entry_speed_mps: float | None = None
        first_entry_radial_speed_mps: float | None = None
        minimum_distance_cm = float("inf")
        speed_at_minimum_distance_mps = float("nan")
        peak_speed_mps = 0.0
        minimum_jacobian_sigma = float("inf")
        saturated_action_steps = 0
        clipped_action_steps = 0
        branch_counts = {"open": 0, "folded": 0}
        previous_branch: str | None = None
        branch_switches = 0
        step_count = 0
        success = False

        while not (terminated or truncated):
            qpos_before = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
            qvel_before = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
            position_before = np.asarray(
                env.data.site("end_effector").xpos, dtype=np.float64
            ).copy()
            raw_action = np.asarray(runtime.predict(obs), dtype=np.float64).reshape(-1)
            commanded_action = np.clip(
                raw_action, env.action_space.low, env.action_space.high
            )
            obs, reward, terminated, truncated, info = env.step(commanded_action)
            step_count += 1
            reward_total += float(reward)

            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
            position = np.asarray(
                env.data.site("end_effector").xpos, dtype=np.float64
            ).copy()
            position_velocity = (position - position_before) / CONTROL_DT
            error = target - position
            distance_cm = 100.0 * float(np.linalg.norm(error))
            speed_mps = float(np.linalg.norm(position_velocity))
            radial_unit = target[:2] / np.linalg.norm(target[:2])
            radial_speed_mps = float(np.dot(position_velocity[:2], radial_unit))
            tangential_unit = np.array([-radial_unit[1], radial_unit[0]])
            tangential_speed_mps = float(
                np.dot(position_velocity[:2], tangential_unit)
            )
            branch, branch_error, branch_margin = branch_metrics(qpos, target)
            sigma_min, sigma_max = jacobian_singular_values(qpos)
            in_tolerance = distance_cm <= 100.0 * SUCCESS_THRESHOLD
            if in_tolerance and tolerance_entry_step is None:
                tolerance_entry_step = step_count
                first_entry_speed_mps = speed_mps
                first_entry_radial_speed_mps = radial_speed_mps
            if previous_in_tolerance and not in_tolerance:
                hold_interruptions += 1
            previous_in_tolerance = in_tolerance
            if branch != previous_branch and previous_branch is not None:
                branch_switches += 1
            previous_branch = branch
            branch_counts[branch] += 1
            if distance_cm <= minimum_distance_cm:
                minimum_distance_cm = distance_cm
                speed_at_minimum_distance_mps = speed_mps
            peak_speed_mps = max(peak_speed_mps, speed_mps)
            minimum_jacobian_sigma = min(minimum_jacobian_sigma, sigma_min)
            at_action_limit = bool(
                np.any(np.abs(commanded_action) >= ACTION_LIMIT - 1e-9)
            )
            was_clipped = bool(np.any(np.abs(raw_action) > ACTION_LIMIT + 1e-9))
            saturated_action_steps += int(at_action_limit)
            clipped_action_steps += int(was_clipped)
            torque = commanded_action * MOTOR_GEAR
            held_steps = int(info.get("held_steps", 0))
            if "is_success" in info:
                success = bool(info["is_success"])
            trajectory.append(
                {
                    "step": step_count,
                    "qpos_rad": qpos.tolist(),
                    "qvel_rad_s": qvel.tolist(),
                    "qpos_before_rad": qpos_before.tolist(),
                    "qvel_before_rad_s": qvel_before.tolist(),
                    "action_raw": raw_action.tolist(),
                    "action_commanded": commanded_action.tolist(),
                    "torque_commanded": torque.tolist(),
                    "action_at_limit": at_action_limit,
                    "action_was_clipped": was_clipped,
                    "end_effector_position_m": position.tolist(),
                    "end_effector_velocity_mps": position_velocity.tolist(),
                    "target_error_m": error.tolist(),
                    "distance_cm": distance_cm,
                    "speed_mps": speed_mps,
                    "radial_speed_mps": radial_speed_mps,
                    "tangential_speed_mps": tangential_speed_mps,
                    "in_tolerance": in_tolerance,
                    "held_steps": held_steps,
                    "branch": branch,
                    "branch_error_rad": branch_error,
                    "branch_error_margin_rad": branch_margin,
                    "jacobian_sigma_min": sigma_min,
                    "jacobian_sigma_max": sigma_max,
                }
            )

        final_distance_cm = float(trajectory[-1]["distance_cm"])
        measured_episodes.append(
            {
                "episode": episode_index,
                "episode_seed": seed + episode_index,
                "target_radius_cm": target_radius_cm,
                "target_angle_degrees": target_angle_degrees,
                "success": success,
                "reward_total": reward_total,
                "steps": step_count,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "tolerance_entry_step": tolerance_entry_step,
                "first_entry_speed_mps": first_entry_speed_mps,
                "first_entry_radial_speed_mps": first_entry_radial_speed_mps,
                "final_distance_cm": final_distance_cm,
                "minimum_distance_cm": minimum_distance_cm,
                "speed_at_minimum_distance_mps": speed_at_minimum_distance_mps,
                "peak_speed_mps": peak_speed_mps,
                "minimum_jacobian_sigma": minimum_jacobian_sigma,
                "saturated_action_steps": saturated_action_steps,
                "clipped_action_steps": clipped_action_steps,
                "branch_counts": branch_counts,
                "branch_switches": branch_switches,
                "hold_interruptions": hold_interruptions,
                "trajectory": trajectory,
            }
        )

    by_radius = {}
    for lower, upper in RADIUS_BINS_CM:
        label = f"{lower:.0f}-{upper:.0f}cm"
        by_radius[label] = summarize_episodes(
            [
                episode
                for episode in measured_episodes
                if radius_bin(episode["target_radius_cm"]) == label
            ]
        )
    return {
        "schema_version": 1,
        "instrument": "radius_trajectory_diagnostic",
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "control_dt_seconds": CONTROL_DT,
        "action_limit": ACTION_LIMIT,
        "motor_gear": MOTOR_GEAR,
        "tolerance_cm": 100.0 * SUCCESS_THRESHOLD,
        "radius_bins_cm": [list(bounds) for bounds in RADIUS_BINS_CM],
        "summary": summarize_episodes(measured_episodes),
        "radius_stratified_summary": by_radius,
        "episode_trajectories": measured_episodes,
        "units": {
            "position": "m",
            "velocity": "m/s",
            "joint_position": "rad",
            "joint_velocity": "rad/s",
            "action": "normalized",
            "torque": "simulator torque units",
            "distance": "cm",
            "time": "control_steps",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = measure(args.model, args.episodes, args.seed)
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(args.artifact),
                "episodes": result["episodes"],
                "success_percent": result["summary"]["success_percent"],
            }
        )
    )


if __name__ == "__main__":
    main()
