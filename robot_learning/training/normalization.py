from pathlib import Path

import numpy as np
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from robot_learning.environments.reach_env import TwoJointArmReachEnv


class ObservationNormalizer:
    def __init__(self, mean: np.ndarray, var: np.ndarray, epsilon: float, clip: float):
        self.mean = mean
        self.var = var
        self.epsilon = epsilon
        self.clip = clip

    def __call__(self, obs: np.ndarray) -> np.ndarray:
        normalized = (obs - self.mean) / np.sqrt(self.var + self.epsilon)
        return np.clip(normalized, -self.clip, self.clip).astype(np.float32)


def find_stats_path(model_path: Path) -> Path | None:
    candidates = [
        model_path.with_name(f"{model_path.stem}_vecnormalize.pkl"),
        model_path.parent / "vecnormalize.pkl",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_observation_normalizer(model_path: Path) -> ObservationNormalizer | None:
    stats_path = find_stats_path(model_path)
    if stats_path is None:
        return None
    dummy_venv = DummyVecEnv([lambda: TwoJointArmReachEnv()])
    vec_normalize = VecNormalize.load(str(stats_path), dummy_venv)
    return ObservationNormalizer(
        mean=np.array(vec_normalize.obs_rms.mean),
        var=np.array(vec_normalize.obs_rms.var),
        epsilon=vec_normalize.epsilon,
        clip=vec_normalize.clip_obs,
    )
