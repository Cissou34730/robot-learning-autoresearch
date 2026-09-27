"""End-to-end proof that inquiry-centered model roles survive a clean clone."""

import json
import subprocess
from pathlib import Path

from research import run_experiment
from research import runner_repository as repository


def _artifact(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker.encode())
    path.joinpath("artifact.json").write_text(
        json.dumps({"marker": marker}), encoding="utf-8"
    )
    path.joinpath("policy_runtime.pkl").write_bytes(b"runtime:" + marker.encode())
    return path


def _lineage(path: Path, *, steps: int) -> dict:
    return {
        "artifact": repository.repo_relative_path(path),
        "fingerprint": repository.artifact_fingerprint(path),
        "origin_experiment": 1,
        "candidate": path.name,
        "parameters": {},
        "scientific_commit": None,
        "training_steps": steps,
        "evaluation_artifacts": [],
        "reason": f"Preserve {path.name}.",
    }


def test_published_inquiry_roles_survive_clean_clone(monkeypatch, tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    research = root / "research"
    research.mkdir()
    for name, value in {
        "ROOT": root,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "RESULTS_PATH": research / "results.jsonl",
        "POSTMORTEM_PATH": research / "postmortems.md",
        "PROPOSAL_PATH": research / "proposal.json",
    }.items():
        monkeypatch.setattr(repository.paths, name, value)

    incumbent = _artifact(root / "artifacts" / "incumbent", "incumbent")
    candidate = _artifact(root / "artifacts" / "candidate", "candidate")
    alternative = _artifact(root / "artifacts" / "alternative", "alternative")
    evaluation_dir = research / "evaluations"
    evaluation_dir.mkdir()

    def evaluation(name: str, artifact: Path) -> dict:
        path = evaluation_dir / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "episodes": 2,
                    "seed": 100,
                    "episode_results": [
                        {"episode": 0, "episode_seed": 100, "success": False},
                        {"episode": 1, "episode_seed": 101, "success": True},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return {
            "candidate": name,
            "instrument": "research_evaluation",
            "episodes": 2,
            "seed": 100,
            "evaluation_semantics": "shared-semantics",
            "model_fingerprint": repository.artifact_fingerprint(artifact),
            "evaluation_artifact": repository.repo_relative_path(path),
            "evaluation_artifact_fingerprint": repository.file_fingerprint(path),
        }

    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="trained",
    )
    state["working_lineage"] = _lineage(incumbent, steps=120_000)
    state["best_known_lineage"] = _lineage(incumbent, steps=120_000)
    state["retained_lineages"] = [
        {"id": "alternative", **_lineage(alternative, steps=40_000)}
    ]
    state["inquiry_session"] = {
        "id": "session",
        "campaign_id": "campaign",
        "inquiry_id": 1,
        "role": "principal_investigator",
        "status": "started",
    }
    state["active_inquiry"] = {
        "id": 1,
        "question": "Is the new method ready?",
        "scope": "Measured model behavior.",
        "closure_condition": "Choose its role.",
        "status": "active",
        "session_id": "session",
        "reframes": [],
    }
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can method A improve control?",
        "rationale": "It is a distinct method.",
        "lifecycle": "mature",
        "base_scientific_commit": "base",
        "current_lineage": _lineage(candidate, steps=100_352),
        "iterations": [{"experiment": 2, "status": "mature"}],
        "resolution": None,
    }
    state["preparation_measurement"] = {
        "experiment": 2,
        "inquiry_id": 1,
        "method_id": "method-a",
        "rounds": [],
        "partial_evaluations": [
            evaluation("active_method", candidate),
            evaluation("working", incumbent),
        ],
        "partial_task_reference_evaluations": [],
    }
    repository.write_state(state)
    proposal = {
        "method_decision": {
            "action": "promote",
            "outcome": "Promote the mature measured method.",
            "reason": "Paired evidence supports promotion.",
            "code": {"action": "keep", "reason": "Keep the method recipe."},
        }
    }
    repository.paths.PROPOSAL_PATH.write_text(json.dumps(proposal), encoding="utf-8")
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda state: None)
    monkeypatch.setattr(run_experiment, "_publish_method_science", lambda plan: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)
    assert run_experiment.resolve_method_decision(proposal) == 0
    published = repository.read_state()
    assert published["working_lineage"]["candidate"] == "candidate"
    assert published["best_known_lineage"]["candidate"] == incumbent.name
    assert published["active_method"]["lifecycle"] == "promoted"
    assert published["retained_lineages"][0]["id"] == "alternative"

    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "core.longpaths", "true"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "publish roles"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=root, check=True
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "clone", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )

    cloned = json.loads(
        clone.joinpath("research/research_state.json").read_text(encoding="utf-8")
    )
    records = [
        cloned["working_lineage"],
        cloned["best_known_lineage"],
        cloned["active_method"]["current_lineage"],
        *cloned["retained_lineages"],
    ]
    assert records[0]["fingerprint"] == records[2]["fingerprint"]
    assert records[0]["fingerprint"] != records[1]["fingerprint"]
    assert records[0]["fingerprint"] != records[3]["fingerprint"]
    assert records[1]["fingerprint"] != records[3]["fingerprint"]
    for record in records:
        artifact = clone / record["artifact"]
        repository.require_complete_inference_artifact(artifact, "cloned lineage")
        assert repository.artifact_fingerprint(artifact) == record["fingerprint"]
