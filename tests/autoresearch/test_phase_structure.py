"""Launcher and prompt contracts for the strict schema-6 lifecycle."""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from runner import (
    execution,
    repository,
    reset_campaign,
    run_experiment,
)
from runner import (
    paths as runner_paths,
)
from runner import (
    protocol as runner_protocol,
)
from runner.launcher import phases, runner_client
from runner.launcher.runner_client import LauncherError, RunnerClient
from runner.launcher.trust import TrustSnapshot, TrustViolation, protected_files


def _short_temp_repo(tmp_path: Path) -> Path:
    return (
        Path(os.environ.get("TEMP", str(tmp_path.parent)))
        / f"{tmp_path.name}-{uuid4().hex}-repo"
    )


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Tests",
            "-c",
            "user.email=tests@example.invalid",
            *arguments,
        ],
        check=True,
        capture_output=True,
    )


def _violation(snapshot: TrustSnapshot) -> str:
    with pytest.raises(TrustViolation) as raised:
        snapshot.verify()
    return str(raised.value)


def _trust_test_repository(path: Path) -> None:
    if path.exists() and not any(path.iterdir()):
        path.rmdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "campaigns" / "evaluations" / "campaign").mkdir(parents=True)
    (path / "benchmark" / "adapters").mkdir(parents=True)
    (path / "runner" / "state").mkdir(parents=True)
    (path / "pi_workspace").mkdir(parents=True)
    (path / "robot_learning" / "scenario").mkdir(parents=True)
    (path / "robot_learning" / "training").mkdir(parents=True)
    (path / "docs").mkdir()
    (path / "run_research.ps1").write_text("# trusted launcher\n", encoding="utf-8")
    (path / "benchmark" / "adapters" / "final_benchmark.py").write_text(
        "VALUE = 'protected'\n", encoding="utf-8"
    )
    (path / "runner" / "state" / "research_state.json").write_text(
        '{"status":"initial"}\n', encoding="utf-8"
    )
    (path / "robot_learning" / "training" / "algorithm.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Tests",
            "-c",
            "user.email=tests@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    (path / "docs" / "untracked-plan.md").write_text(
        "preserve this plan\n", encoding="utf-8"
    )
    (path / "runner" / "state" / "research_state.json").write_text(
        '{"status":"stopped"}\n', encoding="utf-8"
    )
    (path / "campaigns" / "evaluations" / "campaign" / "interrupted.json").write_text(
        '{"completed":false}\n', encoding="utf-8"
    )


def test_launcher_trust_gate_allows_only_the_documented_pi_surface(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    (root / "robot_learning" / "training" / "algorithm.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    (root / "pi_workspace" / "operation_request.json").write_text(
        '{"checkpoint": {}}', encoding="utf-8"
    )
    snapshot.verify()
    assert (root / "docs" / "untracked-plan.md").read_text(
        encoding="utf-8"
    ) == "preserve this plan\n"
    assert (root / "runner" / "state" / "research_state.json").read_text(
        encoding="utf-8"
    ) == '{"status":"stopped"}\n'
    assert (
        root / "campaigns" / "evaluations" / "campaign" / "interrupted.json"
    ).read_text(encoding="utf-8") == '{"completed":false}\n'


def test_launcher_trust_snapshot_protects_the_separate_harness(tmp_path):
    campaign = _short_temp_repo(tmp_path)
    harness = _short_temp_repo(tmp_path)
    _trust_test_repository(campaign)
    _trust_test_repository(harness)
    snapshot = TrustSnapshot.capture(campaign, preliminary=False, harness_root=harness)
    (campaign / "robot_learning" / "training" / "algorithm.py").write_text(
        "allowed\n", encoding="utf-8"
    )
    snapshot.verify()
    (harness / "run_research.ps1").write_text("not allowed\n", encoding="utf-8")
    assert "outside the PI-owned paths" in _violation(snapshot)


def test_launcher_trust_snapshot_excludes_git_probe_directory(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    probe = root / ".py-git-probe" / "probe"
    probe.mkdir(parents=True)
    marker = probe / "marker.txt"
    marker.write_text("initial\n", encoding="utf-8")
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    marker.write_text("changed\n", encoding="utf-8")
    snapshot.verify()


def test_launcher_protected_file_scan_fails_closed_on_enumeration_error(tmp_path):
    with pytest.raises(OSError, match="missing-root"):
        protected_files(tmp_path / "missing-root", preliminary=False)


@pytest.mark.parametrize(
    "relative",
    [
        "run_research.ps1",
        "benchmark/adapters/final_benchmark.py",
        "docs/untracked-plan.md",
    ],
)
def test_launcher_trust_snapshot_rejects_protected_file_modification(
    tmp_path, relative
):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    with (root / relative).open("a", encoding="utf-8") as stream:
        stream.write("PI mutation\n")
    assert relative in _violation(snapshot)


def test_launcher_trust_snapshot_ignores_assume_unchanged_index_mask(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    _git(root, "update-index", "--assume-unchanged", "run_research.ps1")
    with (root / "run_research.ps1").open("a", encoding="utf-8") as stream:
        stream.write("hidden mutation\n")
    assert "run_research.ps1" in _violation(snapshot)


def test_launcher_trust_snapshot_rejects_protected_commit_and_head_change(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    with (root / "run_research.ps1").open("a", encoding="utf-8") as stream:
        stream.write("committed mutation\n")
    _git(root, "add", "run_research.ps1")
    _git(root, "commit", "-qm", "untrusted protected commit")
    message = _violation(snapshot)
    assert "HEAD" in message
    assert "run_research.ps1" in message


def test_launcher_trust_snapshot_rejects_added_non_pi_file(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    (root / "docs" / "new-plan.md").write_text("new\n", encoding="utf-8")
    assert "docs/new-plan.md" in _violation(snapshot)


def test_launcher_trust_snapshot_rejects_deleted_non_pi_file(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    (root / "docs" / "untracked-plan.md").unlink()
    assert "docs/untracked-plan.md" in _violation(snapshot)


def test_preliminary_snapshot_allows_only_scientific_model_handoff(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    model = root / "pi_workspace" / "scientific_model.md"
    model.write_text("initial model\n", encoding="utf-8")
    _git(root, "add", "pi_workspace/scientific_model.md")
    _git(root, "commit", "-qm", "add scientific model")
    snapshot = TrustSnapshot.capture(root, preliminary=True)
    model.write_text("updated model\n", encoding="utf-8")
    snapshot.verify()
    (root / "pi_workspace" / "operation_request.json").write_text(
        '{"checkpoint": {}}', encoding="utf-8"
    )
    assert "pi_workspace/operation_request.json" in _violation(snapshot)


def test_launcher_trust_snapshot_refresh_accepts_trusted_runner_commit(tmp_path):
    root = _short_temp_repo(tmp_path)
    _trust_test_repository(root)
    snapshot = TrustSnapshot.capture(root, preliminary=False)
    (root / "runner" / "state" / "research_state.json").write_text(
        '{"status":"trusted"}\n', encoding="utf-8"
    )
    _git(root, "add", "runner/state/research_state.json")
    _git(root, "commit", "-qm", "trusted runner state")
    assert "HEAD" in _violation(snapshot)
    TrustSnapshot.capture(root, preliminary=False).verify()


def test_failed_runner_exit_refreshes_snapshot_after_trusted_publication(
    monkeypatch, tmp_path
):
    calls = []
    trust = SimpleNamespace(
        verify=lambda: calls.append("verify"),
        refresh=lambda: calls.append("refresh"),
    )

    def run(command, *, operation, input_text=None):
        calls.append("runner")
        return 1

    monkeypatch.setattr(runner_client, "uv_executable", lambda: "uv")
    client = RunnerClient(
        harness_root=tmp_path,
        children=SimpleNamespace(run=run),
        trust=trust,
        timesteps=10,
        max_timesteps=20,
    )
    try:
        assert client.runner("--execute-pending").exit_code == 1
    finally:
        client.close()
    assert calls == ["verify", "runner", "refresh"]


@pytest.mark.parametrize("progress", ["result_ready", "completed"])
def test_pending_publication_failure_stops_without_pi_repair(tmp_path, progress):
    operation_id = f"T-{uuid4().hex}"
    state = {
        "pending_operation": {
            "id": operation_id,
            "progress": progress,
            "failure": None,
        }
    }
    before = copy.deepcopy(state)

    def refuse(*_args, **_kwargs):
        pytest.fail("No Runner or PI work may follow a publication failure.")

    stage = phases.Phases(
        options=SimpleNamespace(campaign_root=tmp_path),
        runner=SimpleNamespace(runner=refuse, build_brief=refuse),
        sessions=SimpleNamespace(run=refuse),
        stop=SimpleNamespace(requested=lambda: False),
        events=SimpleNamespace(),
        home=tmp_path,
    )
    with pytest.raises(LauncherError, match=operation_id):
        stage.pending_operation(state)
    assert state == before


@pytest.mark.parametrize("progress", [None, "training_dispatched"])
def test_publication_failure_guard_preserves_other_recovery_routes(progress):
    pending = (
        {"id": "T1", "progress": progress, "failure": "execution error"}
        if progress is not None
        else None
    )
    phases.require_publication_recovered({"pending_operation": pending})


def test_schema6_state_and_model_are_the_only_fresh_start_contract():
    assert "pi_workspace/operation_request.json" in reset_campaign.CAMPAIGN_PATHS
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    assert state["schema_version"] == 6
    assert set(state) == repository.STATE_FIELDS
    assert state["scientific_model"]["status"] == "pending"
    assert state["active_inquiry"] is None
    assert state["pi_checkpoint"] is None
    assert state["scientific_session"] is None


def test_scientific_model_and_request_paths_remain_protected():
    assert runner_protocol.is_protected_source("pi_workspace/scientific_model.md")
    assert not runner_protocol.is_researcher_owned("pi_workspace/scientific_model.md")
    assert repository.is_runner_owned("pi_workspace/operation_request.json")


def _goal_review_candidate(
    monkeypatch, tmp_path: Path, *, at_cap: bool = True
) -> tuple[dict, dict]:
    research = tmp_path / "campaigns"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "EVALUATION_DIR": research / "evaluations",
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
    }.items():
        monkeypatch.setattr(runner_paths, name, value)
    monkeypatch.setattr(
        runner_paths,
        "campaign_retained_root",
        lambda campaign_id: research / "checkpoints" / "retained" / campaign_id,
    )
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(repository, "campaign_lab_manifest", list)
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "a" * 40
    )
    monkeypatch.setattr(
        runner_protocol, "require_trusted_assessment_runtime", lambda _path: None
    )
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    if at_cap:
        state["counters"]["inquiry"] = state["campaign"]["max_inquiries"]
    repository.start_scientific_session(
        state,
        kind="goal_review",
        objective="Choose the campaign decision from completed evidence.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    evidence = research / "evaluations" / "campaign" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}", encoding="utf-8")
    state["operation_events"].append(
        {
            "id": "M1",
            "kind": "measurement",
            "session_id": "S0",
            "inquiry_id": None,
            "request": {
                "description": "Measure the available candidate.",
                "rationale": "Support a model-role decision.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "episodes": 1,
                        "seed": 1,
                    }
                ],
            },
            "result": {
                "status": "completed",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "candidate_id": candidate["id"],
                        "label": "recorded evidence",
                        "metrics": {
                            "episodes": 1,
                            "successes": 0,
                            "success_percent": 0.0,
                            "evaluation_artifact": repository.repo_relative_path(
                                evidence
                            ),
                            "evaluation_artifact_fingerprint": hashlib.sha256(
                                evidence.read_bytes()
                            ).hexdigest(),
                            "model_fingerprint": candidate["fingerprint"],
                        },
                    }
                ],
                "paired_comparisons": [],
                "tool_provenance": None,
            },
            "status": "completed",
            "error": None,
            "supersedes": None,
            "superseded_by": None,
            "completed_at": "now",
        }
    )
    state["counters"]["measurement"] = 1
    repository.write_state(state)
    return state, candidate


def _best_known_request(candidate: dict) -> dict:
    return {
        "model_role": {
            "action": "set_best_known",
            "candidate": candidate["id"],
            "reason": "Select the strongest available evidence-backed candidate.",
            "evidence": ["M1"],
        }
    }


def _open_inquiry_request() -> dict:
    return {
        "inquiry": {
            "action": "open",
            "question": "Which method addresses the remaining uncertainty?",
            "goal_connection": "The answer determines the next campaign direction.",
            "closure_condition": "Resolve the method decision.",
            "rationale": "The current evidence leaves a consequential uncertainty.",
        }
    }


def test_goal_review_measurement_returns_to_same_session_before_inquiry(
    monkeypatch, tmp_path
):
    state, _candidate = _goal_review_candidate(monkeypatch, tmp_path)
    session = state["scientific_session"]
    counters = dict(state["counters"])
    module = tmp_path / "robot_learning" / "lab" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return None\n", encoding="utf-8")
    artifact = runner_paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Investigate the unresolved method before opening an inquiry.",
            "rationale": "The observation informs the scientific direction.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": ["--output", str(artifact)],
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)

    def run_module(_module, *_args):
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"observation": 3}', encoding="utf-8")
        return "diagnostic complete"

    monkeypatch.setattr(execution, "run_module", run_module)
    monkeypatch.setattr(
        repository,
        "publish_campaign_laboratory",
        lambda _operation_id: {"commit": "c" * 40, "manifest": [], "fingerprint": "f"},
    )
    assert run_experiment.execute_pending_operation() == 0
    measured = repository.read_state()
    event = measured["operation_events"][-1]
    assert event["id"] == f"M{counters['measurement'] + 1}"
    assert event["inquiry_id"] is None
    assert event["result"]["status"] == "completed"
    metrics = event["result"]["measurements"][0]["metrics"]
    assert repository.measurement_evidence(metrics)["observation"] == 3
    assert measured["scientific_session"]["id"] == session["id"]
    assert (
        measured["scientific_session"]["backend_session_id"]
        == session["backend_session_id"]
    )
    assert measured["scientific_session"]["operation_ids"] == [event["id"]]
    assert measured["active_inquiry"] is None
    assert measured["pending_operation"] is None
    assert measured["counters"]["inquiry"] == counters["inquiry"]
    assert measured["counters"]["training"] == counters["training"]
    assert measured["counters"]["measurement"] == counters["measurement"] + 1
    assert (
        runner_protocol.validate_operation_request(request, measured) == "measurement"
    )
    with pytest.raises(ValueError, match="inquiry open is not available"):
        runner_protocol.validate_operation_request(_open_inquiry_request(), measured)


@pytest.mark.parametrize(
    ("count", "active_field", "expected"),
    [
        (14, None, False),
        (15, None, True),
        (16, None, True),
        (15, "active_inquiry", False),
        (15, "scientific_session", False),
        (15, "pending_operation", False),
        (15, "terminal_state", False),
    ],
)
def test_launcher_pauses_at_cap_only_after_scientific_work_is_checkpointed(
    count, active_field, expected
):
    state = {
        "campaign": {"max_inquiries": 15},
        "counters": {"inquiry": count},
        "active_inquiry": None,
        "scientific_session": None,
        "pending_operation": None,
        "terminal_state": None,
    }
    if active_field:
        state[active_field] = {"id": "active"}
    before = copy.deepcopy(state)
    assert phases.inquiry_cap_reached(state) is expected
    assert state == before


def test_goal_review_assigns_best_known_and_requests_assessment_at_cap(
    monkeypatch, tmp_path
):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path)
    assessment = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The PI chooses to assess its explicitly selected candidate.",
        }
    }
    with pytest.raises(ValueError, match="best-known"):
        runner_protocol.validate_operation_request(assessment, state)
    with pytest.raises(ValueError, match="inquiry open is not available"):
        runner_protocol.validate_operation_request(_open_inquiry_request(), state)

    training_count = state["counters"]["training"]
    run_experiment.accept_operation(_best_known_request(candidate), state)
    assert run_experiment.execute_pending_operation() == 0
    assigned = repository.read_state()
    assert assigned["model_roles"]["best_known"] == candidate["id"]
    assert assigned["terminal_state"] is None
    assert assigned["official_assessment"] is None
    assert assigned["counters"]["inquiry"] == state["campaign"]["max_inquiries"]
    assert assigned["counters"]["training"] == training_count
    run_experiment.accept_operation(assessment, assigned)
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    assert persisted["terminal_state"]["status"] == "official_assessment_requested"
    assert persisted["terminal_state"]["model"] == candidate["id"]
    assert persisted["official_assessment"] is None
    assert persisted["counters"]["inquiry"] == state["campaign"]["max_inquiries"]
    assert persisted["counters"]["training"] == training_count


@pytest.mark.parametrize("action", ["set_working", "retain"])
def test_goal_review_permits_other_model_roles_at_cap(monkeypatch, tmp_path, action):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path)
    request = _best_known_request(candidate)
    request["model_role"]["action"] = action
    if action == "retain":
        request["model_role"]["label"] = "reference"
    assert runner_protocol.validate_operation_request(request, state) == "model_role"


@pytest.mark.parametrize("evidence", [[], ["M404"], ["M1"]])
def test_goal_review_role_requires_completed_evidence(monkeypatch, tmp_path, evidence):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path)
    state["operation_events"][0].update(
        status="failed",
        result={"status": "failed", "error": "implementation failure"},
        error="implementation failure",
    )
    request = _best_known_request(candidate)
    request["model_role"]["evidence"] = evidence
    with pytest.raises(ValueError, match="evidence"):
        runner_protocol.validate_operation_request(request, state)
