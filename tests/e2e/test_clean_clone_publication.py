"""End-to-end test that published lineage roles survive a real clone.

The test publishes a v4 closure into a throwaway Git repository, pushes it to a
bare remote and clones it back. It is slow because it spawns real Git
processes, so it lives outside the campaign-time test domains.
"""

import json
import subprocess
from pathlib import Path

import pytest

from research import runner_repository as repository
from research.run_experiment import apply_previous_result_decision


@pytest.fixture(autouse=True)
def _redirect_research_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.LOG_PATH", tmp_path / "EXPERIMENTS.md")


def _artifact(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker.encode("ascii"))
    path.joinpath("artifact.json").write_text(
        json.dumps({"marker": marker}), encoding="utf-8"
    )
    path.joinpath("policy_runtime.pkl").write_bytes(
        b"runtime:" + marker.encode("ascii")
    )
    return path


def _lineage(path: Path, *, steps: int) -> dict:
    return {
        "artifact": path.name,
        "fingerprint": repository.artifact_fingerprint(path),
        "origin_experiment": 1,
        "candidate": path.name,
        "parameters": {"algorithm": {"name": path.name}},
        "scientific_commit": "a" * 40,
        "training_steps": steps,
        "evaluation_artifacts": [],
        "reason": f"Preserve {path.name}.",
    }


def test_published_v4_roles_survive_clean_clone(monkeypatch, tmp_path):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    monkeypatch.setattr("research.runner_paths.ROOT", repository_root)
    monkeypatch.setattr(
        "research.runner_paths.RESEARCH_DIR", repository_root / "research"
    )
    state_path = repository_root / "research" / "research_state.json"
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    working = _artifact(
        repository_root / "research" / "checkpoints" / "challengers" / "working",
        "working",
    )
    best = _artifact(
        repository_root / "research" / "checkpoints" / "challengers" / "best",
        "best",
    )
    alternative = _artifact(
        repository_root / "research" / "checkpoints" / "challengers" / "alternative",
        "alternative",
    )
    best_known = _lineage(best, steps=80_000)
    best_known["artifact"] = repository.repo_relative_path(best)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": best_known,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 3,
            "candidates": [
                {
                    "name": "checkpoint-100352",
                    "artifact": repository.repo_relative_path(working),
                    "timesteps": 100_352,
                    "evaluations": [],
                },
                {
                    "name": "checkpoint-40960",
                    "artifact": repository.repo_relative_path(alternative),
                    "timesteps": 40_960,
                    "evaluations": [],
                },
            ],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
        },
    }
    repository.write_state(state)
    proposal = {
        "previous_result_decision": {
            "experiment": 3,
            "continue_from": "checkpoint-100352",
            "reason": "Continue the working model.",
            "code": {"action": "keep", "reason": "Keep the recipe."},
            "retain": [
                {
                    "candidate": "checkpoint-40960",
                    "id": "alternative",
                    "reason": "Preserve a distinct alternative.",
                }
            ],
        }
    }

    assert not apply_previous_result_decision(proposal, state)
    published = repository.read_state()
    assert published["working_lineage"]["candidate"] == "checkpoint-100352"
    assert published["best_known_lineage"]["candidate"] == best.name
    assert published["retained_lineages"][0]["id"] == "alternative"

    subprocess.run(
        ["git", "init"], cwd=repository_root, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "core.longpaths", "true"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "add", "research/checkpoints/retained", "research/research_state.json"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "publish lineage"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "clone", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )
    cloned_state = json.loads(
        clone.joinpath("research/research_state.json").read_text(encoding="utf-8")
    )
    cloned_records = [
        cloned_state["working_lineage"],
        cloned_state["best_known_lineage"],
        *cloned_state["retained_lineages"],
    ]
    assert len({record["fingerprint"] for record in cloned_records}) == 3
    for record in cloned_records:
        cloned_artifact = clone / record["artifact"]
        repository.require_complete_inference_artifact(
            cloned_artifact, "cloned lineage"
        )
        assert repository.artifact_fingerprint(cloned_artifact) == record["fingerprint"]
