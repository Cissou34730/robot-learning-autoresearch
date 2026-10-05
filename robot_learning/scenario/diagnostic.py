"""Targeted behavioral diagnostics for the reach-and-hold policy."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import make_evaluation_env

LOW_VELOCITY_ENDPOINT_THRESHOLD = 0.02
LOW_VELOCITY_JOINT_THRESHOLD = 0.10
JOINT_LIMITS = np.deg2rad(np.array([-170.0, 170.0]))
FAILING_ANGLES_DEGREES = (-151.0, -143.0, -135.0, -127.0, -119.0)
CONTROL_ANGLES_DEGREES = (-115.0, -107.0, -99.0, -91.0, -83.0)
MATCHED_RADII_METRES = (0.07, 0.11, 0.15, 0.19)


def wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def ik_solutions(target: np.ndarray) -> dict[str, np.ndarray]:
    upper = 0.12
    forearm = 0.10
    target_angle = float(np.arctan2(target[1], target[0]))
    cos_elbow = (target[0] ** 2 + target[1] ** 2 - upper**2 - forearm**2) / (
        2.0 * upper * forearm
    )
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return target_angle - float(
            np.arctan2(
                forearm * np.sin(elbow),
                upper + forearm * np.cos(elbow),
            )
        )

    return {
        "elbow_positive": np.array(
            [shoulder_for_elbow(elbow_open), elbow_open], dtype=np.float64
        ),
        "elbow_negative": np.array(
            [shoulder_for_elbow(-elbow_open), -elbow_open], dtype=np.float64
        ),
    }


def set_target(env, radius: float, angle_degrees: float) -> None:
    angle = np.deg2rad(angle_degrees)
    target_z = float(env.data.site("end_effector").xpos[2])
    env.data.mocap_pos[0] = [
        radius * np.cos(angle),
        radius * np.sin(angle),
        target_z,
    ]
    mujoco.mj_forward(env.model, env.data)
    env._previous_distance = env._distance_to_target()


def state_metrics(env, solutions: dict[str, np.ndarray]) -> dict:
    qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
    qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
    jacp = np.zeros((3, env.model.nv), dtype=np.float64)
    jacr = np.zeros((3, env.model.nv), dtype=np.float64)
    site_id = mujoco.mj_name2id(env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    mujoco.mj_jacSite(env.model, env.data, jacp, jacr, site_id)
    jacobian = jacp[:2, :2]
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    min_singular_value = float(singular_values[-1])
    condition_number = (
        None
        if min_singular_value <= 1e-12
        else float(singular_values[0] / min_singular_value)
    )
    endpoint_velocity = jacobian @ qvel
    branch_distances = {
        name: float(np.linalg.norm(wrap_to_pi(qpos - posture)))
        for name, posture in solutions.items()
    }
    nearest_branch = min(branch_distances, key=branch_distances.get)
    lower = np.full(2, JOINT_LIMITS[0], dtype=np.float64)
    upper = np.full(2, JOINT_LIMITS[1], dtype=np.float64)
    joint_limit_margins = np.minimum(qpos - lower, upper - qpos)
    return {
        "qpos_rad": qpos.tolist(),
        "qvel_rad_s": qvel.tolist(),
        "endpoint_velocity_m_s": endpoint_velocity.tolist(),
        "endpoint_speed_m_s": float(np.linalg.norm(endpoint_velocity)),
        "joint_speed_rad_s": float(np.linalg.norm(qvel)),
        "branch_distances_rad": branch_distances,
        "nearest_branch": nearest_branch,
        "joint_limit_margins_rad": joint_limit_margins.tolist(),
        "minimum_joint_limit_margin_rad": float(np.min(joint_limit_margins)),
        "jacobian_determinant": float(np.linalg.det(jacobian)),
        "jacobian_min_singular_value": min_singular_value,
        "jacobian_condition_number": condition_number,
    }


def run_episode(
    runtime,
    env,
    *,
    seed: int,
    target_radius: float | None = None,
    target_angle_degrees: float | None = None,
    target_source: str,
) -> dict:
    obs, _ = env.reset(seed=seed)
    if target_radius is not None and target_angle_degrees is not None:
        set_target(env, target_radius, target_angle_degrees)
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
        obs = env._observation()
    else:
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    runtime.reset()
    solutions = ik_solutions(target_position)

    initial_metrics = state_metrics(env, solutions)
    min_joint_limit_margin = initial_metrics["minimum_joint_limit_margin_rad"]
    min_jacobian_singular_value = initial_metrics["jacobian_min_singular_value"]
    max_jacobian_condition_number = initial_metrics["jacobian_condition_number"]
    max_endpoint_speed = 0.0
    max_joint_speed = 0.0
    max_action_magnitude = 0.0
    saturated_steps = 0
    first_entry_step = None
    first_entry_metrics = None
    first_low_velocity_step = None
    hold_interruptions = []
    max_held_steps = 0
    in_tolerance_steps = 0
    previous_in_tolerance = False
    min_distance = float("inf")
    reward_total = 0.0
    steps = 0
    terminated = False
    truncated = False
    success = False
    final_distance = float("nan")
    while not (terminated or truncated):
        raw_action = np.asarray(runtime.predict(obs), dtype=np.float64).reshape(-1)
        obs, reward, terminated, truncated, info = env.step(raw_action)
        steps += 1
        reward_total += float(reward)
        distance = float(info["distance"])
        min_distance = min(min_distance, distance)
        final_distance = distance
        held_steps = int(info.get("held_steps", 0))
        in_tolerance = held_steps > 0
        metrics = state_metrics(env, solutions)
        min_joint_limit_margin = min(
            min_joint_limit_margin,
            metrics["minimum_joint_limit_margin_rad"],
        )
        min_jacobian_singular_value = min(
            min_jacobian_singular_value,
            metrics["jacobian_min_singular_value"],
        )
        if metrics["jacobian_condition_number"] is not None:
            if max_jacobian_condition_number is None:
                max_jacobian_condition_number = metrics["jacobian_condition_number"]
            else:
                max_jacobian_condition_number = max(
                    max_jacobian_condition_number,
                    metrics["jacobian_condition_number"],
                )
        max_endpoint_speed = max(max_endpoint_speed, metrics["endpoint_speed_m_s"])
        max_joint_speed = max(max_joint_speed, metrics["joint_speed_rad_s"])
        applied_action = np.asarray(env.data.ctrl[:2], dtype=np.float64)
        action_magnitude = float(np.max(np.abs(applied_action)))
        max_action_magnitude = max(max_action_magnitude, action_magnitude)
        saturated_steps += int(np.any(np.abs(applied_action) >= 0.999999))

        if in_tolerance:
            in_tolerance_steps += 1
            if first_entry_step is None:
                first_entry_step = steps
                first_entry_metrics = {
                    "distance_m": distance,
                    **metrics,
                }
            if (
                first_entry_step is not None
                and first_low_velocity_step is None
                and metrics["endpoint_speed_m_s"] <= LOW_VELOCITY_ENDPOINT_THRESHOLD
                and metrics["joint_speed_rad_s"] <= LOW_VELOCITY_JOINT_THRESHOLD
            ):
                first_low_velocity_step = steps
        elif previous_in_tolerance:
            hold_interruptions.append(steps)
        previous_in_tolerance = in_tolerance
        max_held_steps = max(max_held_steps, held_steps)
        success = bool(info.get("is_success", False))

    final_metrics = state_metrics(env, solutions)
    target_radius_cm = float(np.hypot(target_position[0], target_position[1]) * 100.0)
    target_angle = float(np.degrees(np.arctan2(target_position[1], target_position[0])))
    return {
        "episode_seed": seed,
        "target_source": target_source,
        "target_radius_cm": target_radius_cm,
        "target_angle_degrees": target_angle,
        "success": success,
        "steps": steps,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "reward_total": reward_total,
        "min_distance_cm": min_distance * 100.0,
        "final_distance_cm": final_distance * 100.0,
        "first_entry_step": first_entry_step,
        "first_low_velocity_step": first_low_velocity_step,
        "max_held_steps": max_held_steps,
        "in_tolerance_steps": in_tolerance_steps,
        "hold_interruptions": len(hold_interruptions),
        "hold_interruption_steps": hold_interruptions,
        "branch_at_entry": (
            None
            if first_entry_metrics is None
            else first_entry_metrics["nearest_branch"]
        ),
        "branch_at_terminal": final_metrics["nearest_branch"],
        "branch_distances_at_entry_rad": (
            None
            if first_entry_metrics is None
            else first_entry_metrics["branch_distances_rad"]
        ),
        "branch_distances_at_terminal_rad": final_metrics["branch_distances_rad"],
        "entry_metrics": first_entry_metrics,
        "terminal_metrics": final_metrics,
        "minimum_joint_limit_margin_rad": min_joint_limit_margin,
        "minimum_jacobian_singular_value": min_jacobian_singular_value,
        "maximum_jacobian_condition_number": max_jacobian_condition_number,
        "maximum_endpoint_speed_m_s": max_endpoint_speed,
        "maximum_joint_speed_rad_s": max_joint_speed,
        "maximum_applied_action_magnitude": max_action_magnitude,
        "saturated_action_steps": saturated_steps,
        "saturated_action_fraction": saturated_steps / max(steps, 1),
    }


def build_targeted_cases() -> list[dict]:
    cases = []
    case_index = 0
    for sector, angles in (
        ("failing_sector", FAILING_ANGLES_DEGREES),
        ("adjacent_control_sector", CONTROL_ANGLES_DEGREES),
    ):
        for radius in MATCHED_RADII_METRES:
            for angle in angles:
                cases.append(
                    {
                        "seed": 100000 + case_index,
                        "radius": radius,
                        "angle": angle,
                        "sector": sector,
                    }
                )
                case_index += 1
    return cases


def summarize(episodes: list[dict]) -> dict:
    groups = {}
    for episode in episodes:
        group = episode["target_source"]
        groups.setdefault(group, []).append(episode)
    summary = {}
    for group, rows in groups.items():
        summary[group] = {
            "episodes": len(rows),
            "successes": sum(row["success"] for row in rows),
            "success_percent": 100.0 * sum(row["success"] for row in rows) / len(rows),
            "mean_first_entry_step": _mean(row["first_entry_step"] for row in rows),
            "mean_first_low_velocity_step": _mean(
                row["first_low_velocity_step"] for row in rows
            ),
            "mean_max_held_steps": _mean(row["max_held_steps"] for row in rows),
            "mean_hold_interruptions": _mean(row["hold_interruptions"] for row in rows),
            "mean_maximum_endpoint_speed_m_s": _mean(
                row["maximum_endpoint_speed_m_s"] for row in rows
            ),
            "mean_minimum_joint_limit_margin_rad": _mean(
                row["minimum_joint_limit_margin_rad"] for row in rows
            ),
            "mean_minimum_jacobian_singular_value": _mean(
                row["minimum_jacobian_singular_value"] for row in rows
            ),
            "mean_saturated_action_fraction": _mean(
                row["saturated_action_fraction"] for row in rows
            ),
            "branch_at_entry_counts": _counts(row["branch_at_entry"] for row in rows),
        }
    return summary


def _mean(values) -> float | None:
    present = [float(value) for value in values if value is not None]
    return None if not present else float(np.mean(present))


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is not None:
            counts[value] = counts.get(value, 0) + 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--panel-episodes", type=int, default=160)
    parser.add_argument("--panel-seed", type=int, default=4200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.panel_episodes < 1:
        raise ValueError("panel-episodes must be positive")
    runtime = load_runtime(args.model)
    env = make_evaluation_env(policy_runtime=runtime)
    episodes = []
    for episode in range(args.panel_episodes):
        episodes.append(
            run_episode(
                runtime,
                env,
                seed=args.panel_seed + episode,
                target_source="panel_replay",
            )
        )
    for case in build_targeted_cases():
        result = run_episode(
            runtime,
            env,
            seed=case["seed"],
            target_radius=case["radius"],
            target_angle_degrees=case["angle"],
            target_source=case["sector"],
        )
        result["matched_grid_sector"] = case["sector"]
        episodes.append(result)
    env.close()
    result = {
        "schema_version": 1,
        "model": str(args.model),
        "panel": {
            "episodes": args.panel_episodes,
            "seed": args.panel_seed,
            "target_radius_range_m": list(TARGET_RADIUS_RANGE),
        },
        "targeted_grid": {
            "failing_angles_degrees": list(FAILING_ANGLES_DEGREES),
            "control_angles_degrees": list(CONTROL_ANGLES_DEGREES),
            "matched_radii_m": list(MATCHED_RADII_METRES),
        },
        "episodes": episodes,
        "summary": summarize(episodes),
        "units": {
            "distance": "m and cm where named",
            "time": "control_steps",
            "velocity": "m/s and rad/s where named",
            "angles": "rad and degrees where named",
        },
    }
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
