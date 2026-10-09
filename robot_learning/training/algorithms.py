"""Load a saved policy produced by the current training implementation."""

from pathlib import Path

from stable_baselines3 import PPO, SAC

ALGORITHM_CLASSES = {
    "ppo": PPO,
    "sac": SAC,
}


def load_policy(model_path: Path, algorithm: str | None = None):
    """Load a policy using the algorithm recorded by its training operation."""
    algorithm_name = "ppo" if algorithm is None else str(algorithm).lower()
    if algorithm_name not in ALGORITHM_CLASSES:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    return ALGORITHM_CLASSES[algorithm_name].load(model_path)
