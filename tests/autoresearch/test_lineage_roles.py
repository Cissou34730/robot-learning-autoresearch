"""Independent model roles in the inquiry-centered lifecycle."""

import json
import subprocess
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_protocol as protocol
from research import runner_repository as repository


def _artifact(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker.encode())
    path.joinpath("artifact.json").write_text(
        json.dumps({"marker": marker}), encoding="utf-8"
    )
    path.joinpath("policy_runtime.pkl").write_bytes(b"runtime:" + marker.encode())
    return path


def _lineage(path: Path, *, steps: int, experiment: int = 1) -> dict:
    return {
        "artifact": path.name,
        "fingerprint": repository.artifact_fingerprint(path),
        "origin_experiment": experiment,
        "candidate": path.name,
        "parameters": {"algorithm": {"name": path.name}},
        "scientific_commit": "a" * 40,
        "training_steps": steps,
        "evaluation_artifacts": [],
        "reason": f"Preserve {path.name}.",
        "designation_ordinal": 1,
    }


def _active_inquiry(session_id: str = "session") -> dict:
    return {
        "id": 1,
        "question": "Can a distinct method improve control?",
        "scope": "Method learning behavior.",
        "closure_condition": "Resolve whether to promote, retain, or abandon it.",
        "status": "active",
        "session_id": session_id,
        "reframes": [],
    }


def _active_method(
    lineage: dict | None = None, *, lifecycle: str = "development"
) -> dict:
    return {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can this method improve control?",
        "rationale": "It tests a distinct learning path.",
        "lifecycle": lifecycle,
        "base_scientific_commit": "a" * 40,
        "current_lineage": lineage,
        "iterations": [],
        "resolution": None,
    }


def _state(tmp_path: Path) -> dict:
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["inquiry_session"] = {
        "id": "session",
        "campaign_id": "campaign",
        "inquiry_id": 1,
        "role": "principal_investigator",
        "status": "started",
    }
    state["active_inquiry"] = _active_inquiry()
    return state


def test_model_roles_are_independent_training_parents(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working", "working")
    best = _artifact(tmp_path / "best", "best")
    method = _artifact(tmp_path / "method", "method")
    retained = _artifact(tmp_path / "retained", "retained")
    state = _state(tmp_path)
    state["working_lineage"] = _lineage(working, steps=120_000)
    state["best_known_lineage"] = _lineage(best, steps=90_000)
    state["active_method"] = _active_method(_lineage(method, steps=70_000))
    state["retained_lineages"] = [
        {"id": "alternative", **_lineage(retained, steps=60_000)}
    ]

    assert protocol.training_parent(
        {"training_parent": "working"}, state, "transfer"
    ) == ("working", working, 120_000)
    assert protocol.training_parent(
        {"training_parent": "best_known"}, state, "transfer"
    ) == ("best_known", best, 90_000)
    assert protocol.training_parent(
        {"training_parent": "active_method"}, state, "transfer"
    ) == ("active_method", method, 70_000)
    assert protocol.training_parent(
        {"training_parent": "alternative"}, state, "transfer"
    ) == ("alternative", retained, 60_000)


def test_measurement_catalog_exposes_active_method_without_requiring_working(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    method = _artifact(tmp_path / "method", "method")
    state = _state(tmp_path)
    state["active_method"] = _active_method(_lineage(method, steps=20_000))

    available = protocol.available_evaluation_candidates(
        {
            "candidates": [
                {
                    "name": "checkpoint-10k",
                    "artifact": "candidate",
                    "evaluations": [],
                }
            ]
        },
        state,
    )

    assert set(available) == {"checkpoint-10k", "active_method"}
    assert available["active_method"]["artifact"] == method.name


def test_active_method_artifact_survives_cleanup_roles(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    method = _artifact(tmp_path / "method", "method")
    state = _state(tmp_path)
    state["active_method"] = _active_method(_lineage(method, steps=20_000))

    assert method in repository.role_and_retention_artifacts(state)


def test_active_inquiry_requires_complete_bounds_and_matching_session(tmp_path):
    state = _state(tmp_path)
    repository.validate_research_state(state, allow_missing_artifact=True)

    state["active_inquiry"]["question"] = ""
    with pytest.raises(ValueError, match="question"):
        repository.validate_research_state(state, allow_missing_artifact=True)

    state = _state(tmp_path)
    state["inquiry_session"]["id"] = "other"
    with pytest.raises(ValueError, match="own the current inquiry_session"):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_schema_five_rejects_missing_fields_and_legacy_panel_shapes(tmp_path):
    state = _state(tmp_path)
    del state["pending_scientific_commit"]
    with pytest.raises(RuntimeError, match="research state is incomplete"):
        repository.validate_research_state(state, allow_missing_artifact=True)

    state = _state(tmp_path)
    working = _artifact(tmp_path / "working", "working")
    state["working_lineage"] = _lineage(working, steps=120_000)
    state["working_lineage"]["selected_panels"] = [["research_evaluation", 100, 200]]
    with pytest.raises(TypeError, match="panel identity objects"):
        repository.validate_research_state(state, allow_missing_artifact=True)

    state = _state(tmp_path)
    state["active_method"] = _active_method()
    state["active_method"]["status"] = "active"
    state["active_method"]["stage"] = "development"
    with pytest.raises(ValueError, match="requires exactly"):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_method_is_declared_before_nonbaseline_training(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("observation", encoding="utf-8")
    state = _state(tmp_path)
    proposal = {
        "kind": "training",
        "method_id": "method-a",
        "initialization": "fresh",
        "change": "Change the method.",
        "investigation_design": {
            "evidence": [
                {"source": "evidence.txt", "observation": "Observed behavior."}
            ],
            "objective_link": "The behavior affects the objective.",
            "initialization_reason": "Fresh isolates the changed method.",
            "rationale": "This run tests the method.",
            "expected_observation": "Learning changes measurably.",
            "open_question": "How will learning change?",
        },
    }
    with pytest.raises(ValueError, match="declared active_method"):
        protocol.validate_proposal_against_state(proposal, state)


def test_method_start_creates_a_first_class_method():
    state = _state(Path("."))
    state["pending_scientific_parent"] = "b" * 40
    plan = protocol.plan_method_start(
        {
            "method": {
                "action": "start",
                "id": "method-a",
                "scientific_question": "Can this method learn robust control?",
                "rationale": "It explores a distinct representation.",
                "lifecycle": "concept",
            }
        },
        state,
    )
    assert plan["method"] == {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can this method learn robust control?",
        "rationale": "It explores a distinct representation.",
        "lifecycle": "concept",
        "base_scientific_commit": "b" * 40,
        "current_lineage": None,
        "iterations": [],
        "resolution": None,
    }


def test_method_iteration_can_abandon_a_collapsed_run_without_candidate(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(protocol, "validate_postmortem_evidence", lambda *a, **k: "x")
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    state = _state(tmp_path)
    state["active_method"] = _active_method()
    state["active_method"]["iterations"] = [
        {"experiment": 2, "status": "training_error"}
    ]
    state["pending_analysis"] = {
        "experiment": 2,
        "baseline": False,
        "method_id": "method-a",
        "candidates": [],
        "parameters": {},
        "initialization": "fresh",
        "parent_training_steps": 0,
        "code_parent_commit": "a" * 40,
        "result": {},
    }
    plan = protocol.plan_method_decision(
        {
            "method_decision": {
                "experiment": 2,
                "action": "abandon",
                "outcome": "The collapsed run rejects this implementation.",
                "reason": "The method did not produce a usable policy.",
                "code": {"action": "revert", "reason": "Discard the failed recipe."},
            }
        },
        state,
    )
    assert plan["active_method"]["lifecycle"] == "abandoned"
    assert plan["active_method"]["current_lineage"] is None
    assert plan["active_method"]["iterations"][0]["status"] == "abandon"


def test_post_training_continue_uses_the_shared_method_decision_executor(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(protocol, "validate_postmortem_evidence", lambda *a, **k: "x")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = _state(tmp_path)
    state["active_method"] = _active_method()
    state["active_method"]["iterations"] = [
        {"experiment": 2, "status": "awaiting_analysis"}
    ]
    state["pending_analysis"] = {
        "experiment": 2,
        "inquiry_id": 1,
        "baseline": False,
        "method_id": "method-a",
        "candidates": [
            {
                "name": "candidate",
                "artifact": candidate.name,
                "fingerprint": repository.artifact_fingerprint(candidate),
                "timesteps": 5_000,
                "evaluations": [],
            }
        ],
        "parameters": {},
        "initialization": "fresh",
        "parent_training_steps": 0,
        "code_parent_commit": "a" * 40,
        "result": {
            "schema_version": 1,
            "record_type": "experiment",
            "campaign_id": "campaign",
            "index": 2,
            "status": "trained",
            "verdict": "awaiting analysis",
        },
    }
    proposal = {
        "method_decision": {
            "experiment": 2,
            "action": "continue",
            "outcome": "The method warrants another iteration.",
            "reason": "The first run established a usable lineage.",
            "candidate": "candidate",
            "code": {"action": "keep", "reason": "Keep the method recipe."},
        }
    }
    research = tmp_path / "research"
    research.mkdir()
    monkeypatch.setattr(repository.paths, "RESEARCH_DIR", research)
    monkeypatch.setattr(repository.paths, "STATE_PATH", research / "state.json")
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", research / "proposal.json")
    monkeypatch.setattr(repository.paths, "RESULTS_PATH", research / "results.jsonl")
    monkeypatch.setattr(repository.paths, "LOG_PATH", research / "EXPERIMENTS.md")
    monkeypatch.setattr(
        repository.paths, "POSTMORTEM_PATH", research / "postmortems.md"
    )
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_method_science", lambda plan: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)
    repository.write_state(state)
    repository.paths.PROPOSAL_PATH.write_text(json.dumps(proposal), encoding="utf-8")

    assert run_experiment.resolve_method_decision(proposal) == 0
    resolved = repository.read_state()
    assert resolved["pending_method_decision"] is None
    assert resolved["pending_analysis"] is None
    assert resolved["active_method"]["lifecycle"] == "development"
    assert resolved["active_method"]["current_lineage"]["candidate"] == "candidate"
    result = repository.result_records()[0]
    assert result["method_decision"]["action"] == "continue"


def test_maturing_a_method_does_not_promote_it(monkeypatch, tmp_path):
    monkeypatch.setattr(protocol, "validate_postmortem_evidence", lambda *a, **k: "x")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    working = _artifact(tmp_path / "working", "working")
    state = _state(tmp_path)
    state["working_lineage"] = _lineage(working, steps=120_000)
    state["active_method"] = _active_method()
    state["active_method"]["iterations"] = [
        {"experiment": 2, "status": "awaiting_analysis"}
    ]
    state["pending_analysis"] = {
        "experiment": 2,
        "baseline": False,
        "method_id": "method-a",
        "candidates": [
            {
                "name": "candidate",
                "artifact": candidate.name,
                "fingerprint": repository.artifact_fingerprint(candidate),
                "timesteps": 5_000,
                "evaluations": [],
            }
        ],
        "parameters": {},
        "initialization": "fresh",
        "parent_training_steps": 0,
        "code_parent_commit": "a" * 40,
        "result": {},
    }

    plan = protocol.plan_method_decision(
        {
            "method_decision": {
                "experiment": 2,
                "action": "mature",
                "outcome": "The method is ready for inquiry-level comparison.",
                "reason": "Its development question is resolved.",
                "candidate": "candidate",
                "code": {"action": "keep", "reason": "Keep the mature recipe."},
            }
        },
        state,
    )

    assert plan["active_method"]["lifecycle"] == "mature"
    assert (
        plan["working_record"]["fingerprint"] == state["working_lineage"]["fingerprint"]
    )
    assert plan["working_name"] == "working"


def test_abandon_restores_the_pre_method_recipe_and_leaves_git_clean(
    monkeypatch, tmp_path
):
    root = tmp_path / "repo"
    source = root / "robot_learning" / "scenario" / "method.py"
    harness = root / "research" / "run_experiment.py"
    source.parent.mkdir(parents=True)
    harness.parent.mkdir(parents=True)
    source.write_text("recipe = 'pre-method'\n", encoding="utf-8")
    harness.write_text("harness = 'original'\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "base"], cwd=root, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source.write_text("recipe = 'later-anchor'\n", encoding="utf-8")
    harness.write_text("harness = 'maintainer-fix'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "later anchor"], cwd=root, check=True
    )
    latest = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source.write_text("recipe = 'method-edit'\n", encoding="utf-8")

    state = _state(tmp_path)
    state["pending_scientific_parent"] = latest
    state["active_method"] = _active_method(lifecycle="concept")
    state["active_method"]["base_scientific_commit"] = base
    proposal = {
        "method_decision": {
            "action": "abandon",
            "outcome": "Abandon before allocating training.",
            "reason": "The implementation invalidated the method premise.",
            "code": {"action": "revert", "reason": "Restore the pre-method recipe."},
        }
    }
    state_path = tmp_path / "state.json"
    proposal_path = tmp_path / "proposal.json"
    monkeypatch.setattr(repository.paths, "ROOT", root)
    monkeypatch.setattr(repository.paths, "STATE_PATH", state_path)
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(repository.paths, "RESULTS_PATH", tmp_path / "results.jsonl")
    monkeypatch.setattr(repository.paths, "LOG_PATH", tmp_path / "EXPERIMENTS.md")
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(repository, "push_head", lambda: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)
    repository.write_state(state)
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    assert run_experiment.resolve_method_decision(proposal) == 0
    assert source.read_text(encoding="utf-8") == "recipe = 'pre-method'\n"
    assert harness.read_text(encoding="utf-8") == "harness = 'maintainer-fix'\n"
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status == ""
    resolved = repository.read_state()
    assert resolved["active_method"]["lifecycle"] == "abandoned"


def _mature_resolution_case(
    monkeypatch, tmp_path, *, lifecycle: str
) -> tuple[dict, dict]:
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    working = _artifact(tmp_path / "working", "working")
    state = _state(tmp_path)
    state["working_lineage"] = _lineage(working, steps=120_000)
    state["best_known_lineage"] = _lineage(working, steps=120_000)
    state["active_method"] = _active_method(
        _lineage(candidate, steps=5_000, experiment=2), lifecycle=lifecycle
    )
    state["active_method"]["iterations"] = [{"experiment": 2, "status": "mature"}]
    state["pending_scientific_parent"] = "a" * 40
    evaluation_semantics = "shared-semantics"

    def evaluation(name: str, fingerprint: str) -> dict:
        artifact = tmp_path / f"{name}-evaluation.json"
        artifact.write_text(
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
            "evaluation_semantics": evaluation_semantics,
            "model_fingerprint": fingerprint,
            "evaluation_artifact": artifact.name,
            "evaluation_artifact_fingerprint": repository.file_fingerprint(artifact),
        }

    state["preparation_measurement"] = {
        "experiment": 2,
        "inquiry_id": 1,
        "rounds": [],
        "partial_evaluations": [
            evaluation("active_method", repository.artifact_fingerprint(candidate)),
            evaluation("working", repository.artifact_fingerprint(working)),
        ],
        "partial_task_reference_evaluations": [],
    }
    proposal = {
        "method_decision": {
            "action": "promote",
            "outcome": "Promote after mature comparison.",
            "reason": "The paired inquiry measurement supports promotion.",
            "code": {"action": "keep", "reason": "Keep the method recipe."},
        }
    }
    return state, proposal


def test_method_promotion_requires_prior_maturity(monkeypatch, tmp_path):
    state, proposal = _mature_resolution_case(
        monkeypatch, tmp_path, lifecycle="development"
    )
    with pytest.raises(ValueError, match="already marked mature"):
        protocol.plan_method_decision(proposal, state)


def test_mature_promotion_requires_paired_working_evidence(monkeypatch, tmp_path):
    state, proposal = _mature_resolution_case(monkeypatch, tmp_path, lifecycle="mature")
    state["preparation_measurement"]["partial_evaluations"] = state[
        "preparation_measurement"
    ]["partial_evaluations"][:1]
    with pytest.raises(ValueError, match="fingerprint-bound.*working"):
        protocol.plan_method_decision(proposal, state)


def test_mature_inquiry_measurement_can_promote_without_training(monkeypatch, tmp_path):
    state, proposal = _mature_resolution_case(monkeypatch, tmp_path, lifecycle="mature")
    state["preparation_measurement"]["rounds"] = [
        {"round": 1, "status": "completed", "paired_comparisons": []}
    ]
    plan = protocol.plan_method_decision(proposal, state)
    assert plan["working_record"]["candidate"] == "candidate"
    assert plan["active_method"]["lifecycle"] == "promoted"
    assert plan["active_method"]["resolution"]["action"] == "promote"
    assert plan["best_known_record"]["candidate"] == "working"

    research = tmp_path / "research"
    research.mkdir(exist_ok=True)
    monkeypatch.setattr(repository.paths, "STATE_PATH", research / "state.json")
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", research / "proposal.json")
    monkeypatch.setattr(repository.paths, "RESULTS_PATH", research / "results.jsonl")
    monkeypatch.setattr(repository.paths, "LOG_PATH", research / "EXPERIMENTS.md")
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)
    monkeypatch.setattr(run_experiment, "_publish_method_science", lambda plan: None)
    repository.write_state(state)
    repository.paths.PROPOSAL_PATH.write_text(json.dumps(proposal), encoding="utf-8")

    assert run_experiment.resolve_method_decision(proposal) == 0
    resolved = repository.read_state()
    assert resolved["working_lineage"]["candidate"] == "candidate"
    assert resolved["active_method"]["lifecycle"] == "promoted"
    assert resolved["last_experiment"] == 0
    assert resolved["last_allocated_experiment"] == 0
    assert not repository.paths.RESULTS_PATH.exists()
    assert resolved["preparation_measurement"]["rounds"][0]["round"] == 1

    monkeypatch.setattr(protocol, "scientific_strategy_section", lambda *args: "ok")
    monkeypatch.setattr(protocol, "scientific_strategy_registers", lambda section: {})
    close = {
        "inquiry": {
            "action": "close",
            "outcome": "The mature method was promoted with paired evidence.",
        }
    }
    assert run_experiment.resolve_inquiry_operation(close, "inquiry") == 0
    inquiry_record = repository.history_records()[-1]
    assert inquiry_record["record_type"] == "inquiry"
    assert inquiry_record["measurement_rounds"][0]["round"] == 1
    assert inquiry_record["method"]["lifecycle"] == "promoted"


def test_mature_method_can_be_retained_without_changing_working(monkeypatch, tmp_path):
    state, proposal = _mature_resolution_case(monkeypatch, tmp_path, lifecycle="mature")
    proposal["method_decision"].update(
        action="retain",
        retained_id="mature-alternative",
    )
    plan = protocol.plan_method_decision(proposal, state)
    assert plan["working_record"]["candidate"] == "working"
    assert plan["retained"][-1]["id"] == "mature-alternative"
    assert plan["active_method"]["lifecycle"] == "retained"


def test_mature_method_abandon_recovers_after_durable_cleanup(monkeypatch, tmp_path):
    state, proposal = _mature_resolution_case(monkeypatch, tmp_path, lifecycle="mature")
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    proposal["method_decision"].update(
        action="abandon",
        code={"action": "revert", "reason": "Return to the inquiry anchor."},
    )
    plan = protocol.plan_method_decision(proposal, state)
    assert plan["working_record"]["candidate"] == "working"
    assert plan["active_method"]["lifecycle"] == "abandoned"
    assert plan["active_method"]["current_lineage"] is None
    assert plan["released_method_lineage"]["candidate"] == "candidate"

    research = tmp_path / "research"
    research.mkdir(exist_ok=True)
    monkeypatch.setattr(repository.paths, "STATE_PATH", research / "state.json")
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", research / "proposal.json")
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    original_remove = repository.remove_heavyweight_artifacts
    cleanup_attempts = 0

    def track_cleanup(artifact):
        nonlocal cleanup_attempts
        cleanup_attempts += 1
        original_remove(artifact)

    clear_attempts = 0

    def fail_first_clear(message):
        nonlocal clear_attempts
        if message.startswith("clear method"):
            clear_attempts += 1
            if clear_attempts == 1:
                raise OSError("injected pending-clear failure")

    monkeypatch.setattr(repository, "remove_heavyweight_artifacts", track_cleanup)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", fail_first_clear)
    monkeypatch.setattr(run_experiment, "_publish_method_science", lambda plan: None)
    repository.write_state(state)
    repository.paths.PROPOSAL_PATH.write_text(json.dumps(proposal), encoding="utf-8")

    with pytest.raises(OSError, match="injected pending-clear failure"):
        run_experiment.resolve_method_decision(proposal)
    interrupted = repository.read_state()
    assert interrupted["pending_method_decision"]["progress"] == "cleanup_published"
    assert cleanup_attempts == 1
    assert not (tmp_path / "candidate" / "model.zip").exists()

    assert run_experiment.resolve_method_decision(proposal) == 0
    resolved = repository.read_state()
    assert resolved["pending_method_decision"] is None
    assert resolved["active_method"]["lifecycle"] == "abandoned"
    assert cleanup_attempts == 1
    assert not (tmp_path / "candidate" / "model.zip").exists()
    assert (tmp_path / "working" / "model.zip").exists()


def test_mature_method_decision_publication_recovers_without_an_experiment(
    monkeypatch, tmp_path
):
    state, proposal = _mature_resolution_case(monkeypatch, tmp_path, lifecycle="mature")
    proposal["method_decision"].update(
        action="retain",
        retained_id="durable-method",
    )
    research = tmp_path / "research"
    research.mkdir(exist_ok=True)
    state_path = research / "research_state.json"
    proposal_path = research / "proposal.json"
    results_path = research / "results.jsonl"
    monkeypatch.setattr(repository.paths, "STATE_PATH", state_path)
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(repository.paths, "RESULTS_PATH", results_path)
    monkeypatch.setattr(repository.paths, "LOG_PATH", research / "EXPERIMENTS.md")
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)
    monkeypatch.setattr(run_experiment, "_publish_method_science", lambda plan: None)
    repository.write_state(state)
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    original_publish = repository.publish_artifact
    attempts = 0

    def fail_first_publication(publication):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("injected publication failure")
        original_publish(publication)

    monkeypatch.setattr(repository, "publish_artifact", fail_first_publication)
    with pytest.raises(OSError, match="injected publication failure"):
        run_experiment.resolve_method_decision(proposal)
    interrupted = repository.read_state()
    assert interrupted["pending_method_decision"]["progress"] == "planned"
    assert interrupted["last_experiment"] == 0

    assert run_experiment.resolve_method_decision(proposal) == 0
    recovered = repository.read_state()
    assert recovered["pending_method_decision"] is None
    assert recovered["active_method"]["lifecycle"] == "retained"
    assert recovered["retained_lineages"][-1]["id"] == "durable-method"
    assert recovered["last_experiment"] == 0
    assert not results_path.exists()


@pytest.mark.parametrize(
    "progress",
    [
        "planned",
        "artifacts_published",
        "code_applied",
        "science_published",
        "decision_recorded",
        "memory_published",
        "cleanup_complete",
        "cleanup_published",
    ],
)
def test_method_decision_resumes_from_each_persisted_progress(
    monkeypatch, tmp_path, progress
):
    state, proposal = _mature_resolution_case(monkeypatch, tmp_path, lifecycle="mature")
    proposal["method_decision"].update(
        action="retain",
        retained_id="resume-method",
    )
    plan = protocol.plan_method_decision(proposal, state)
    state["pending_method_decision"] = {
        "method_id": plan["method_id"],
        "action": plan["method_action"],
        "plan": run_experiment._serialize_method_decision_plan(plan),
        "progress": progress,
    }
    if progress in {
        "decision_recorded",
        "memory_published",
        "cleanup_complete",
        "cleanup_published",
    }:
        state["working_lineage"] = plan["working_record"]
        state["best_known_lineage"] = plan["best_known_record"]
        state["active_method"] = plan["active_method"]
        state["retained_lineages"] = plan["retained"]
        state["best_known_designation_counter"] = plan["designation_counter"]
        state["pending_scientific_parent"] = None

    research = tmp_path / "research"
    research.mkdir(exist_ok=True)
    monkeypatch.setattr(repository.paths, "STATE_PATH", research / "state.json")
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", research / "proposal.json")
    monkeypatch.setattr(repository, "publish_artifact", lambda publication: None)
    monkeypatch.setattr(repository, "apply_code_lineage_decision", lambda code: None)
    monkeypatch.setattr(run_experiment, "_publish_method_science", lambda value: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)
    repository.write_state(state)

    run_experiment.complete_method_decision_operation(state)

    assert state["pending_method_decision"] is None
    assert state["active_method"]["lifecycle"] == "retained"
    assert state["retained_lineages"][-1]["id"] == "resume-method"


def test_continuation_freezes_complete_parent_identity(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working", "working")
    lineage = _lineage(working, steps=120_000)
    lineage["candidate"] = "checkpoint-100352"
    state = _state(tmp_path)
    state["working_lineage"] = lineage

    resolved = protocol.resolved_training_parent(
        {"kind": "continuation", "training_parent": "working"},
        state,
        "transfer",
    )
    assert resolved["identifier"] == "working"
    assert resolved["candidate"] == "checkpoint-100352"
    assert resolved["training_steps"] == 120_000
