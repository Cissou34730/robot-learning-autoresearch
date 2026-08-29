"""The generic artifact contract the executor depends on.

The runner never inspects the learning algorithm. It only requires that the
active training entry point produces a reloadable artifact that describes its
own effective configuration. This test exercises that contract as a black box,
through the existing training CLI and the existing `load_policy()` interface.

It deliberately names no algorithm: a researcher may replace the learning
method entirely, and this contract must keep holding.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from robot_learning.scenario import make_training_env
from robot_learning.training.algorithms import load_policy

ROOT = Path(__file__).resolve().parents[2]
SMOKE_TIMESTEPS = 64


@pytest.fixture(scope="module")
def trained_artifact(tmp_path_factory) -> Path:
    """Train with the smallest practical budget; never a full research run."""
    output_dir = tmp_path_factory.mktemp("artifact") / "smoke"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot_learning.train",
            "--timesteps",
            str(SMOKE_TIMESTEPS),
            "--seed",
            "0",
            "--n-envs",
            "1",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, (
        completed.stdout[-3000:] + completed.stderr[-3000:]
    )
    return output_dir


def test_training_entry_point_produces_the_required_artifact_files(trained_artifact):
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        assert (trained_artifact / filename).is_file(), filename
    assert (trained_artifact / "candidate_manifest.json").is_file()
    assert (trained_artifact / "final_checkpoint" / "model.zip").is_file()


def test_artifact_records_effective_configuration_and_preprocessing(trained_artifact):
    artifact = json.loads(
        (trained_artifact / "artifact.json").read_text(encoding="utf-8")
    )

    assert artifact["effective_config"]
    assert artifact["seed"] == 0
    assert artifact["timesteps"] >= SMOKE_TIMESTEPS
    assert artifact["completed"] is True
    # Preprocessing state travels with the policy so evaluation can restore it.
    assert (trained_artifact / "vecnormalize.pkl").stat().st_size > 0


def test_saved_policy_reloads_and_predicts_a_usable_action(trained_artifact):
    artifact = json.loads(
        (trained_artifact / "artifact.json").read_text(encoding="utf-8")
    )

    policy = load_policy(trained_artifact / "model.zip", artifact["algorithm"])

    assert hasattr(policy, "predict")
    env = make_training_env()
    observation, _ = env.reset(seed=0)
    action, _ = policy.predict(observation, deterministic=True)
    assert env.action_space.contains(action)
