import argparse
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.training.normalization import load_observation_normalizer
from robot_learning.training.research_config import EVALUATION_MILESTONES


def milestone_steps(hold_seconds: float, control_dt: float) -> int:
    return max(round(hold_seconds / control_dt), 1)


def achieved_milestones(
    distances: list[float], control_dt: float
) -> list[bool]:
    """Return fixed-ladder achievements for one complete episode."""
    achieved: list[bool] = []
    for threshold, hold_seconds in EVALUATION_MILESTONES:
        required = milestone_steps(hold_seconds, control_dt)
        streak = 0
        best_streak = 0
        for distance in distances:
            streak = streak + 1 if distance <= threshold else 0
            best_streak = max(best_streak, streak)
        achieved.append(best_streak >= required)
    return achieved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a trained agent over random targets"
    )
    parser.add_argument(
        "--model", type=Path, required=True, help="path to a trained model.zip"
    )
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model = PPO.load(args.model)
    env = TwoJointArmReachEnv()
    normalize_obs = load_observation_normalizer(args.model)
    if normalize_obs is None:
        print("Warning: no vecnormalize.pkl found — evaluating without normalization")

    successes = 0
    final_distances = []
    closest_distances = []
    episode_lengths = []
    milestone_counts = np.zeros(len(EVALUATION_MILESTONES), dtype=np.int64)
    control_dt = env.model.opt.timestep * env.frame_skip
    for episode in range(args.episodes):
        obs, _ = env.reset(seed=args.seed + episode)
        done = False
        steps = 0
        distances = []
        while not done:
            action, _ = model.predict(normalize_obs(obs), deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1
            distances.append(float(info["distance"]))
        successes += info["is_success"]
        final_distances.append(info["distance"])
        closest_distances.append(min(distances))
        milestone_counts += achieved_milestones(distances, control_dt)
        episode_lengths.append(steps)

    distances_cm = np.array(final_distances) * 100
    closest_cm = np.array(closest_distances) * 100
    milestone_rates = 100 * milestone_counts / args.episodes
    progress_score = float(np.mean(milestone_rates))
    print(f"Model: {args.model}")
    print(f"Episodes: {args.episodes}")
    print(
        f"Success rate: {successes}/{args.episodes} ({100 * successes / args.episodes:.0f}%)"
    )
    print(
        f"Final distance (cm): mean {distances_cm.mean():.1f}, "
        f"median {np.median(distances_cm):.1f}, worst {distances_cm.max():.1f}"
    )
    print(
        f"Closest distance (cm): mean {closest_cm.mean():.2f}, "
        f"median {np.median(closest_cm):.2f}"
    )
    print(f"Curriculum progress score: {progress_score:.2f}%")
    for (threshold, hold_seconds), rate in zip(
        EVALUATION_MILESTONES, milestone_rates, strict=True
    ):
        print(
            f"  milestone {100 * threshold:g} cm / {hold_seconds:g} s: "
            f"{rate:.1f}%"
        )
    print(f"Episode length: mean {np.mean(episode_lengths):.0f}/500 steps")


if __name__ == "__main__":
    main()
