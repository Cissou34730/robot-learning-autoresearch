"""Save SB3 weights and the inference contract used by this learning method."""

from pathlib import Path

from robot_learning.policy_runtime import frozen_scientific_modules, save_runtime
from robot_learning.scenario.policy_io import make_policy_io
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer


def save_checkpoint(model, venv, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / "model.zip"
    # Include custom researcher-defined policy classes in the SB3 archive too.
    with frozen_scientific_modules():
        model.save(model_path)
    stats_path = None
    if hasattr(venv, "save"):
        stats_path = directory / "vecnormalize.pkl"
        venv.save(str(stats_path))
    export_runtime(directory, stats_path=stats_path)
    if hasattr(model, "save_replay_buffer"):
        model.save_replay_buffer(directory / "replay_buffer.pkl")


def export_runtime(directory: Path, *, stats_path: Path | None):
    model_path = directory / "model.zip"
    normalizer = load_observation_normalizer(model_path) if stats_path else None
    save_runtime(
        model_path,
        policy_io=make_policy_io(),
        loader=load_policy,
        normalizer=normalizer,
        stats_path=stats_path,
    )
