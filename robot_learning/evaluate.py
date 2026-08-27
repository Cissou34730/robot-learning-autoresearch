import argparse
import json
from pathlib import Path

import numpy as np

from robot_learning.benchmark.metrics import (
    maximum_consecutive_hold_steps,
    milestone_steps,
    summarize_consecutive_hold_steps,
)
from robot_learning.benchmark.spec import (
    EVALUATION_EPISODES,
    EVALUATION_SEED,
    HOLD_SECONDS,
)
from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a trained robot policy")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--episodes", type=int, default=EVALUATION_EPISODES)
    parser.add_argument("--seed", type=int, default=EVALUATION_SEED)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def evaluate_model(
    model_path: Path,
    episodes: int = EVALUATION_EPISODES,
    seed: int = EVALUATION_SEED,
    algorithm: str | None = None,
) -> dict:
    model = load_policy(model_path, algorithm)
    env = TwoJointArmReachEnv()
    normalize_obs = load_observation_normalizer(model_path)
    if normalize_obs is None:
        normalize_obs = lambda obs: obs

    successes = 0
    consecutive_hold_steps: list[int] = []
    closest_distances: list[float] = []
    final_distances: list[float] = []
    control_dt = env.model.opt.timestep * env.frame_skip
    required_hold_steps = milestone_steps(HOLD_SECONDS, control_dt)
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        distances: list[float] = []
        done = False
        while not done:
            action, _ = model.predict(normalize_obs(obs), deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(float(info["distance"]))
            done = terminated or truncated
        maximum_hold = maximum_consecutive_hold_steps(distances)
        successes += maximum_hold >= required_hold_steps
        consecutive_hold_steps.append(maximum_hold)
        closest_distances.append(min(distances))
        final_distances.append(distances[-1])

    return {
        "schema_version": 1,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "success_percent": 100 * successes / episodes,
        "consecutive_hold_steps": summarize_consecutive_hold_steps(
            consecutive_hold_steps, required_hold_steps
        ),
        "closest_distance_cm": {
            "mean": float(np.mean(closest_distances) * 100),
            "median": float(np.median(closest_distances) * 100),
        },
        "final_distance_cm": {
            "mean": float(np.mean(final_distances) * 100),
            "median": float(np.median(final_distances) * 100),
            "worst": float(np.max(final_distances) * 100),
        },
    }


def main() -> None:
    args = parse_args()
    result = evaluate_model(
        args.model,
        episodes=args.episodes,
        seed=args.seed,
        algorithm=args.algorithm,
    )
    output = json.dumps(result, indent=2)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
