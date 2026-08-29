"""Load a saved policy produced by the current training implementation."""

from pathlib import Path

from stable_baselines3 import PPO


def load_policy(model_path: Path, algorithm: str | None = None):
    """`algorithm` stays optional because the CLI and the protected benchmark
    entry point forward it; the current training implementation is PPO."""
    if algorithm is not None and str(algorithm).lower() != "ppo":
        raise ValueError(f"unsupported algorithm: {algorithm}")
    return PPO.load(model_path)
