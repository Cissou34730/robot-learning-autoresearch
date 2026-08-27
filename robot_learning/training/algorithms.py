"""Common Stable-Baselines3 algorithm interface."""

import json
from pathlib import Path

from stable_baselines3 import PPO, SAC

ALGORITHMS = {"ppo": PPO, "sac": SAC}


def algorithm_class(name: str):
    try:
        return ALGORITHMS[name.lower()]
    except KeyError as error:
        raise ValueError(f"unsupported algorithm: {name}") from error


def artifact_algorithm(model_path: Path) -> str:
    metadata_path = model_path.parent / "artifact.json"
    if not metadata_path.exists():
        return "ppo"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return str(metadata["algorithm"]).lower()


def load_policy(model_path: Path, algorithm: str | None = None):
    name = algorithm or artifact_algorithm(model_path)
    return algorithm_class(name).load(model_path)

