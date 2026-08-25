import argparse
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.training.normalization import load_observation_normalizer


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
    episode_lengths = []
    for episode in range(args.episodes):
        obs, _ = env.reset(seed=args.seed + episode)
        done = False
        steps = 0
        while not done:
            action, _ = model.predict(normalize_obs(obs), deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1
        successes += info["is_success"]
        final_distances.append(info["distance"])
        episode_lengths.append(steps)

    distances_cm = np.array(final_distances) * 100
    print(f"Model: {args.model}")
    print(f"Episodes: {args.episodes}")
    print(
        f"Success rate: {successes}/{args.episodes} ({100 * successes / args.episodes:.0f}%)"
    )
    print(
        f"Final distance (cm): mean {distances_cm.mean():.1f}, "
        f"median {np.median(distances_cm):.1f}, worst {distances_cm.max():.1f}"
    )
    print(f"Episode length: mean {np.mean(episode_lengths):.0f}/200 steps")


if __name__ == "__main__":
    main()
