import pickle
from pathlib import Path

import numpy as np


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
    # Read the saved statistics directly: VecNormalize.load() would only need a
    # vectorized env to attach to, which would pull the training environment
    # into every evaluation.
    with stats_path.open("rb") as handle:
        vec_normalize = pickle.load(handle)
    return ObservationNormalizer(
        mean=np.array(vec_normalize.obs_rms.mean),
        var=np.array(vec_normalize.obs_rms.var),
        epsilon=vec_normalize.epsilon,
        clip=vec_normalize.clip_obs,
    )
