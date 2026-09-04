"""Human-owned persistence of a policy's executable input/output contract.

Only load trusted local artifacts: like SB3 models, these contain pickle code.
The installed Python/SB3/Torch stack is shared, not bundled or abstracted away.
"""

import hashlib
import sys
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import cloudpickle
import numpy as np

RUNTIME_FILE = "policy_runtime.pkl"
RUNTIME_VERSION = 1


@dataclass
class PolicyIO:
    observe: Callable
    action: Callable
    reset: Callable | None = None


@contextmanager
def frozen_scientific_modules():
    """Store project-defined functions/classes by value, not mutable imports.

    This is cloudpickle's serialization scope, not a plugin registry. Dependencies
    are resolved by the producer before export; installed libraries stay by reference.
    """
    existing = cloudpickle.list_registry_pickle_by_value()
    modules = [
        module
        for name, module in list(sys.modules.items())
        if module is not None
        and name not in existing
        and (
            name.startswith(("robot_learning.scenario.", "robot_learning.training."))
            or name in {"robot_learning.train", "robot_learning.evaluate"}
        )
    ]
    try:
        for module in modules:
            cloudpickle.register_pickle_by_value(module)
        yield
    finally:
        for module in modules:
            cloudpickle.unregister_pickle_by_value(module)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_runtime(
    model_path: Path,
    *,
    policy_io: PolicyIO,
    loader: Callable,
    normalizer,
    stats_path: Path | None = None,
) -> None:
    """Freeze already-resolved callables, bind them to these exact weights/stats."""
    model_path = Path(model_path)
    if normalizer is not None and stats_path is None:
        raise ValueError("A normalized policy requires its saved normalization file")
    if stats_path is not None and stats_path.parent != model_path.parent:
        raise ValueError("Normalization must be stored beside the policy")
    payload = {
        "version": RUNTIME_VERSION,
        "weights_sha256": _digest(model_path),
        "stats": None if stats_path is None else (stats_path.name, _digest(stats_path)),
        "io": policy_io,
        "loader": loader,
        "normalizer": normalizer,
    }
    destination = model_path.parent / RUNTIME_FILE
    temporary = destination.with_suffix(".tmp")
    with frozen_scientific_modules(), temporary.open("wb") as handle:
        cloudpickle.dump(payload, handle)
    temporary.replace(destination)


def validate_runtime_files(model_path: Path) -> dict:
    """Fail before executing a panel; never substitute the current science code."""
    path = Path(model_path).parent / RUNTIME_FILE
    if not path.is_file():
        raise ValueError(
            f"Missing {path}. Legacy policies require explicit migration from their "
            "historical scientific code; current observations must not be substituted."
        )
    with path.open("rb") as handle:
        payload = cloudpickle.load(handle)
    if not isinstance(payload, dict) or payload.get("version") != RUNTIME_VERSION:
        raise ValueError(f"Unsupported policy runtime: {path}")
    if _digest(Path(model_path)) != payload["weights_sha256"]:
        raise ValueError(f"Policy runtime does not match weights: {model_path}")
    if payload["stats"] is not None:
        filename, digest = payload["stats"]
        if Path(filename).name != filename:
            raise ValueError("Invalid normalization filename in runtime")
        stats = path.parent / filename
        if not stats.is_file() or _digest(stats) != digest:
            raise ValueError(f"Missing or mismatched normalization: {stats}")
    return payload


class PolicyRuntime:
    def __init__(self, payload, model_path, algorithm):
        self.io = payload["io"]
        self.normalizer = payload["normalizer"]
        self.model = payload["loader"](model_path, algorithm)
        self.observation_space = self.model.observation_space
        self.action_space = self.model.action_space
        self.reset()

    def reset(self):
        self.state = None
        self.episode_start = True

    def predict(self, observation):
        if self.normalizer is not None:
            observation = self.normalizer(observation)
        action, self.state = self.model.predict(
            observation,
            state=self.state,
            episode_start=np.array([self.episode_start]),
            deterministic=True,
        )
        self.episode_start = False
        return action


def load_runtime(model_path: Path, algorithm: str | None = None) -> PolicyRuntime:
    return PolicyRuntime(validate_runtime_files(model_path), model_path, algorithm)
