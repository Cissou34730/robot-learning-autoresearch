import argparse
import json
from pathlib import Path

import numpy as np

from robot_learning.benchmark.metrics import achieved_milestones
from robot_learning.benchmark.spec import (
    CURRICULUM_STAGES,
    EVALUATION_EPISODES,
    EVALUATION_SEED,
    FINAL_STAGE_INDEX,
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
    parser.add_argument("--stage-index", type=int, required=True)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def evaluate_model(
    model_path: Path,
    stage_index: int,
    episodes: int = EVALUATION_EPISODES,
    seed: int = EVALUATION_SEED,
    algorithm: str | None = None,
) -> dict:
    if not 0 <= stage_index < len(CURRICULUM_STAGES):
        raise ValueError(f"invalid curriculum stage: {stage_index}")
    model = load_policy(model_path, algorithm)
    # The final task keeps episodes alive long enough to measure every easier
    # milestone on exactly the same deterministic trajectories.
    env = TwoJointArmReachEnv(stage_index=FINAL_STAGE_INDEX)
    normalize_obs = load_observation_normalizer(model_path)
    if normalize_obs is None:
        normalize_obs = lambda obs: obs

    milestone_counts = np.zeros(len(CURRICULUM_STAGES), dtype=np.int64)
    closest_distances: list[float] = []
    final_distances: list[float] = []
    control_dt = env.model.opt.timestep * env.frame_skip
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        distances: list[float] = []
        done = False
        while not done:
            action, _ = model.predict(normalize_obs(obs), deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(float(info["distance"]))
            done = terminated or truncated
        milestone_counts += achieved_milestones(distances, control_dt)
        closest_distances.append(min(distances))
        final_distances.append(distances[-1])

    rates = (100 * milestone_counts / episodes).tolist()
    return {
        "schema_version": 1,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "stage_index": stage_index,
        "stage_success_percent": rates,
        "current_stage_success_percent": rates[stage_index],
        "final_success_percent": rates[FINAL_STAGE_INDEX],
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
        args.stage_index,
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
