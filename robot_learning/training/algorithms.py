"""Load a saved policy produced by the current training implementation."""

from pathlib import Path

from stable_baselines3 import PPO, SAC
from stable_baselines3.common.save_util import load_from_zip_file

ALGORITHM_CLASSES = {
    "ppo": PPO,
    "sac": SAC,
}


def infer_algorithm(model_path: Path) -> str:
    data, _, _ = load_from_zip_file(str(model_path), device="cpu", load_data=True)
    policy_class = data.get("policy_class")
    module = getattr(policy_class, "__module__", "")
    if module == "stable_baselines3.sac.policies":
        return "sac"
    return "ppo"


def load_policy(model_path: Path, algorithm: str | None = None):
    """Load a policy using the algorithm recorded by its training operation."""
    algorithm_name = (
        infer_algorithm(model_path) if algorithm is None else str(algorithm).lower()
    )
    if algorithm_name not in ALGORITHM_CLASSES:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    return ALGORITHM_CLASSES[algorithm_name].load(model_path)
