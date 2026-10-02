"""Targeted diagnostics for separating outer-workspace reach from hold failure."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

CONTROL_DT_SECONDS = 0.020
RADII_CM = (6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0)
ANGLE_COUNT = 16


def _mean(values: list[float]) -> float | None:
    return None if not values else float(np.mean(values))


def _summarize(rows: list[dict]) -> dict:
    entries = [row for row in rows if row["first_reach_step"] is not None]
    return {
        "episodes": len(rows),
        "successes": sum(bool(row["success"]) for row in rows),
        "success_percent": 100.0
        * sum(bool(row["success"]) for row in rows)
        / len(rows),
        "first_entries": len(entries),
        "first_entry_percent": 100.0 * len(entries) / len(rows),
        "mean_first_reach_step": _mean(
            [float(row["first_reach_step"]) for row in entries]
        ),
        "mean_entry_speed_cm_per_s": _mean(
            [float(row["entry_speed_cm_per_s"]) for row in entries]
        ),
        "mean_longest_uninterrupted_hold_steps": _mean(
            [float(row["longest_uninterrupted_hold_steps"]) for row in rows]
        ),
        "mean_hold_interruptions": _mean(
            [float(row["hold_interruptions"]) for row in rows]
        ),
    }


def _group_summary(rows: list[dict], field: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        key = str(row[field])
        groups.setdefault(key, []).append(row)
    return {key: _summarize(groups[key]) for key in sorted(groups)}


def run_diagnostic(model_path: Path, output_path: Path, seed: int) -> None:
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    rows: list[dict] = []

    angles = np.linspace(-180.0, 180.0, ANGLE_COUNT, endpoint=False)
    episode_index = 0
    for radius_cm in RADII_CM:
        for angle_degrees in angles:
            radius_m = radius_cm / 100.0
            angle_radians = np.radians(angle_degrees)
            obs, _ = env.reset(seed=seed + episode_index)
            del obs
            env.data.mocap_pos[0] = [
                radius_m * np.cos(angle_radians),
                radius_m * np.sin(angle_radians),
                float(env._end_effector_position()[2]),
            ]
            mujoco.mj_forward(env.model, env.data)
            env._previous_distance = env._distance_to_target()
            observation = env._observation()
            runtime.reset()

            target_position = env.data.mocap_pos[0].copy()
            previous_position = env._end_effector_position()
            previous_distance_cm = 100.0 * env._distance_to_target()
            first_reach_step = None
            pre_entry_distance_cm = None
            entry_speed_cm_per_s = None
            entry_elbow_angle_degrees = None
            max_held_steps = 0
            in_tolerance_steps = 0
            hold_interruptions = 0
            was_in_tolerance = False
            reward_total = 0.0
            steps = 0
            success = False
            terminated = False
            truncated = False

            while not (terminated or truncated):
                action = runtime.predict(observation)
                observation, reward, terminated, truncated, info = env.step(action)
                steps += 1
                reward_total += float(reward)
                position = env._end_effector_position()
                distance_cm = 100.0 * float(info["distance"])
                held_steps = int(info.get("held_steps", 0))
                max_held_steps = max(max_held_steps, held_steps)
                if held_steps > 0:
                    in_tolerance_steps += 1
                    if first_reach_step is None:
                        first_reach_step = steps
                        pre_entry_distance_cm = previous_distance_cm
                        entry_speed_cm_per_s = float(
                            np.linalg.norm(position - previous_position)
                            / CONTROL_DT_SECONDS
                            * 100.0
                        )
                        entry_elbow_angle_degrees = float(
                            np.degrees(env.data.qpos[1])
                        )
                elif was_in_tolerance:
                    hold_interruptions += 1
                was_in_tolerance = held_steps > 0
                previous_position = position.copy()
                previous_distance_cm = distance_cm
                success = bool(info.get("is_success", False))

            rows.append(
                {
                    "episode": episode_index,
                    "episode_seed": seed + episode_index,
                    "target_radius_cm": float(radius_cm),
                    "target_angle_degrees": float(angle_degrees),
                    "success": success,
                    "steps": steps,
                    "reward_total": reward_total,
                    "first_reach_step": first_reach_step,
                    "pre_entry_distance_cm": pre_entry_distance_cm,
                    "entry_speed_cm_per_s": entry_speed_cm_per_s,
                    "entry_elbow_angle_degrees": entry_elbow_angle_degrees,
                    "longest_uninterrupted_hold_steps": max_held_steps,
                    "in_tolerance_steps": in_tolerance_steps,
                    "hold_interruptions": hold_interruptions,
                    "terminated": bool(terminated),
                    "truncated": bool(truncated),
                    "target_position_cm": [float(value * 100.0) for value in target_position],
                }
            )
            episode_index += 1

    artifact = {
        "schema_version": 1,
        "model": str(model_path),
        "seed": seed,
        "episodes": len(rows),
        "control_dt_seconds": CONTROL_DT_SECONDS,
        "radii_cm": list(RADII_CM),
        "angle_count": ANGLE_COUNT,
        "summary": _summarize(rows),
        "by_radius_cm": _group_summary(rows, "target_radius_cm"),
        "by_angle_degrees": _group_summary(rows, "target_angle_degrees"),
        "episode_diagnostics": rows,
        "units": {
            "distance": "cm",
            "speed": "cm_per_s",
            "time": "control_steps",
            "angle": "degrees",
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=3000)
    args = parser.parse_args()
    run_diagnostic(args.model, args.output, args.seed)


if __name__ == "__main__":
    main()
