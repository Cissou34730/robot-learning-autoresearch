"""Strict schema-6 campaign reset and maintenance-import boundaries."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from runner import paths, protocol, repository, reset_campaign

SCIENTIFIC_MODEL_TEXT = (
    "## Established facts\nThe robot has actuated joints.\n"
    "## Physical consequences\nTorque affects the robot's motion.\n"
    "## Unknowns\nLearning performance remains uncertain.\n"
    "## Decision-relevant synthesis\nCompare measured results: caf\u00e9.\n"
)


def _bind_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    research = root / "campaigns"
    state = root / "runner" / "state"
    workspace = root / "pi_workspace"
    values = {
        "ROOT": root,
        "CAMPAIGNS_DIR": research,
        "RUNNER_STATE_DIR": state,
        "PI_WORKSPACE_DIR": workspace,
        "RESEARCH_DIR": research,
        "LOG_PATH": research / "EXPERIMENTS.md",
        "RESULTS_PATH": research / "results.jsonl",
        "OPERATION_REQUEST_PATH": workspace / "operation_request.json",
        "STATE_PATH": state / "research_state.json",
        "TRAINING_LOG_DIR": research / "training_logs",
        "SCIENTIFIC_MODEL_PATH": workspace / "scientific_model.md",
        "RECOVERY_PENDING_PATH": state / "RECOVERY_PENDING",
        "RESTART_PENDING_PATH": state / "RESTART_PENDING",
        "CANDIDATE_ROOT": root / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
    }
    for name, value in values.items():
        monkeypatch.setattr(paths, name, value)
    return research


def _candidate(fingerprint: str) -> dict:
    return {
        "id": "T1:checkpoint-10",
        "artifact": "campaigns/checkpoints/candidates/source/t1/checkpoint-10",
        "fingerprint": fingerprint,
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {"algorithm": {"name": "ppo"}},
        "scientific_commit": "a" * 40,
        "training_steps": 10,
        "evaluation_artifacts": ["campaigns/evaluations/source/panel.json"],
    }


def _prepared_source_state(candidate: dict) -> dict:
    state = repository.empty_campaign_state(
        campaign={
            "id": "source",
            "started_at": "now",
            "base_commit": "base",
        },
        last_verdict="prepared model",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "b" * 40,
    }
    state["candidates"] = {candidate["id"]: copy.deepcopy(candidate)}
    state["model_roles"] = {
        "working": candidate["id"],
        "best_known": candidate["id"],
        "retained": {},
    }
    repository.validate_research_state(state, allow_missing_artifact=True)
    return state


def test_fresh_campaign_writes_only_schema7_memory(monkeypatch, tmp_path):
    research = _bind_paths(monkeypatch, tmp_path)
    obsolete = (
        "pi_workspace/operation_request.json",
        "campaigns/postmortems.md",
        "campaigns/archive.md",
        "runner/state/last_train_summary.md",
        "runner/state/last_evaluation.json",
        "campaigns/brief.md",
        "pi_workspace/scientific_model.md",
    )
    for relative in obsolete:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("stale\n", encoding="utf-8")
    (research / "checkpoints" / "accepted").mkdir(parents=True)
    (research / "checkpoints" / "accepted" / "envelope.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (research / "results.jsonl").write_text('{"legacy": true}\n', encoding="utf-8")
    monkeypatch.setattr(reset_campaign, "git", lambda *_args, **_kwargs: "head\n")

    state = reset_campaign.write_fresh_campaign(None)

    assert state["schema_version"] == 7
    assert state["campaign_phase"] == "recipe_development"
    assert state["recipe_development"] is None
    assert set(state) == repository.STATE_FIELDS
    assert state["scientific_model"] == {
        "status": "pending",
        "path": "pi_workspace/scientific_model.md",
        "commit": None,
    }
    assert state["model_roles"] == {
        "working": None,
        "best_known": None,
        "retained": {},
    }
    assert state["candidates"] == {}
    assert state["operation_events"] == []
    assert state["pending_operation"] is None
    assert state["active_inquiry"] is None
    assert state["pi_checkpoint"] is None
    assert state["scientific_session"] is None
    assert json.loads(paths.STATE_PATH.read_text(encoding="utf-8")) == state
    assert paths.RESULTS_PATH.read_text(encoding="utf-8") == ""
    assert paths.LOG_PATH.read_text(
        encoding="utf-8"
    ) == repository.render_operation_log([])
    assert not (research / "checkpoints").exists()
    for relative in obsolete:
        assert not (tmp_path / relative).exists()
    with pytest.raises(ValueError, match="scientific model must be ready"):
        repository.start_scientific_session(
            state, kind="goal_review", objective="Choose the first operation."
        )


def test_recipe_import_excludes_campaign_memory_and_laboratory(monkeypatch):
    source_recipe = [
        "robot_learning/training/reward.py",
        "robot_learning/training/algorithms.py",
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
        "robot_learning/training/current_params.json",
    ]
    later_science = "robot_learning/scenario/later_extension.py"
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda commit: None)
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda commit: [
            *source_recipe,
            later_science,
            "robot_learning/lab/diagnostic.py",
            "runner/state/research_state.json",
            "campaigns/evaluations/source/evidence.json",
            "robot_learning/scenario/__init__.py",
            "tests/autoresearch/test_scenario_boundary.py",
        ],
    )
    monkeypatch.setattr(
        repository,
        "tracked_at_commit",
        lambda commit, relative: relative != later_science,
    )

    assert reset_campaign.scientific_plan("source") == {
        "parent": "source",
        "restore": source_recipe,
        "remove_created": [later_science],
    }

    monkeypatch.setattr(
        reset_campaign.protocol,
        "plan_recipe_paths",
        lambda _commit: {
            "parent": "source",
            "restore": ["campaigns/evaluations/source/evidence.json"],
            "remove_created": [],
        },
    )
    with pytest.raises(RuntimeError, match="non-scientific path"):
        reset_campaign.scientific_plan("source")


@pytest.mark.parametrize(
    ("analysis", "failure"),
    [
        (None, None),
        (SCIENTIFIC_MODEL_TEXT.encode("utf-8"), None),
        (SCIENTIFIC_MODEL_TEXT.replace("\n", "\r\n").encode("utf-8"), None),
        (SCIENTIFIC_MODEL_TEXT.encode("utf-8"), "analysis_restore"),
        (SCIENTIFIC_MODEL_TEXT.encode("utf-8"), "campaign_publication"),
    ],
    ids=[
        "bare",
        "prepared-utf8",
        "prepared-crlf-utf8",
        "restore-failure",
        "publication-failure",
    ],
)
def test_fresh_recipe_ref_restores_recipe_into_empty_schema7_campaign(
    monkeypatch, tmp_path, analysis, failure
):
    root = tmp_path
    source = "a" * 40
    recipe = {
        "robot_learning/training/reward.py": "SOURCE_REWARD = True\n",
        "robot_learning/scenario/source_only.py": "SOURCE_ONLY = True\n",
        "robot_learning/training/algorithms.py": "SOURCE_ALGORITHM = True\n",
        "robot_learning/train.py": "SOURCE_TRAIN = True\n",
        "robot_learning/evaluate.py": "SOURCE_EVALUATE = True\n",
        "robot_learning/play.py": "SOURCE_PLAY = True\n",
        "robot_learning/training/current_params.json": '{"algorithm":{"name":"ppo"}}\n',
    }
    for relative, content in recipe.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"CURRENT_{target.stem.upper()} = True\n", encoding="utf-8")

    candidate = _candidate("f" * 64)
    source_state = _prepared_source_state(candidate)
    source_state["active_inquiry"] = {"id": "I7", "question": "source inquiry"}
    source_state["scientific_session"] = {"id": "S7", "kind": "inquiry"}
    source_state["pi_checkpoint"] = {"session_id": "S7"}
    source_state["operation_events"] = [
        {"id": "M9", "kind": "measurement", "status": "completed"}
    ]
    source_state["counters"] = {
        "inquiry": 7,
        "session": 8,
        "measurement": 9,
        "training": 6,
        "event": 5,
    }
    source_state["official_assessment"] = {"candidate": candidate["id"]}
    source_state["terminal_state"] = {"status": "goal_reached"}
    source_memory = {
        "runner/state/research_state.json": json.dumps(source_state),
        "campaigns/results.jsonl": '{"id":"T1","status":"completed"}\n',
        "campaigns/EXPERIMENTS.md": "# Source campaign history\n",
        "pi_workspace/scientific_model.md": "# Old analysis\n" + SCIENTIFIC_MODEL_TEXT,
        "pi_workspace/operation_request.json": '{"kind":"training"}\n',
        "campaigns/postmortems.md": "# Source postmortem\n",
        "campaigns/brief.md": "# Source bounded-session context\n",
        "campaigns/evaluations/source/evidence.json": '{"success_rate":0.97}\n',
        "campaigns/checkpoints/candidates/source/t1/checkpoint-10/model.zip": (
            "trained policy"
        ),
        "models/candidates/source/model.zip": "disposable trained policy",
        "robot_learning/lab/source_diagnostic.py": "SOURCE_EVIDENCE = True\n",
        "runner/state/GOAL_REACHED": "stale goal marker\n",
        "runner/state/RECOVERY_PENDING": "stale recovery marker\n",
        "runner/state/RESTART_PENDING": "stale restart marker\n",
        "runner/state/BASELINE_PENDING": "stale baseline marker\n",
    }
    for relative, content in source_memory.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    (root / "robot_learning/scenario/source_only.py").unlink()
    later = root / "robot_learning/scenario/later_extension.py"
    later.write_text("LATER_EXTENSION = True\n", encoding="utf-8")
    _bind_paths(monkeypatch, root)
    (root / ".git").mkdir()
    plan = {
        "parent": source,
        "restore": list(recipe),
        "remove_created": ["robot_learning/scenario/later_extension.py"],
    }
    publications: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr(
        reset_campaign,
        "resolve_commit",
        lambda reference, label: (
            source
            if (reference, label) == ("strong-baseline", "RecipeRef")
            else pytest.fail("unexpected recipe resolution")
        ),
    )
    monkeypatch.setattr(reset_campaign, "scientific_plan", lambda commit: plan)
    monkeypatch.setattr(
        reset_campaign,
        "commit_files",
        lambda _commit: (
            set(recipe)
            | ({"pi_workspace/scientific_model.md"} if analysis is not None else set())
        ),
    )
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: {})
    monkeypatch.setattr(
        reset_campaign, "verify_task_compatibility", lambda _commit: None
    )

    def committed_analysis(commit: str, relative: str) -> bytes:
        assert commit == source
        assert relative == "pi_workspace/scientific_model.md"
        assert analysis is not None
        return analysis

    monkeypatch.setattr(reset_campaign, "git_bytes", committed_analysis)
    resolved_commits = []
    monkeypatch.setattr(
        repository, "require_resolvable_commit", resolved_commits.append
    )
    monkeypatch.setattr(reset_campaign, "validate_restored_recipe", lambda: None)

    def publish(_message, scope, purpose):
        publications.append((purpose, tuple(scope)))
        if failure == "campaign_publication" and purpose == "campaign":
            raise repository.PublicationError("publication interrupted")

    monkeypatch.setattr(reset_campaign, "publish_reset_changes", publish)
    monkeypatch.setattr(reset_campaign, "git", lambda *_args, **_kwargs: "new-head\n")

    def restore_paths(commit: str, restorable: list[str]) -> None:
        assert commit == source
        assert restorable == list(recipe)
        for relative in restorable:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(recipe[relative], encoding="utf-8")

    monkeypatch.setattr(repository, "restore_paths", restore_paths)

    if failure == "analysis_restore":

        def refuse_analysis(_path, _content):
            raise OSError("analysis restoration interrupted")

        monkeypatch.setattr(repository, "atomic_write_bytes", refuse_analysis)

    if failure:
        with pytest.raises(RuntimeError, match="reset failed") as caught:
            reset_campaign.reset_fresh("strong-baseline")
        assert paths.reset_marker_path(root).exists()
        state = json.loads(paths.STATE_PATH.read_text(encoding="utf-8"))
        assert state["scientific_session"] is None
        assert state["candidates"] == {}
        if failure == "analysis_restore":
            assert isinstance(caught.value.__cause__, OSError)
            assert state["scientific_model"]["status"] == "pending"
            assert not paths.SCIENTIFIC_MODEL_PATH.exists()
            assert [purpose for purpose, _scope in publications] == ["recipe"]
        else:
            assert isinstance(caught.value.__cause__, repository.PublicationError)
            assert state["scientific_model"]["status"] == "ready"
            assert state["scientific_model"]["commit"] == source
            assert paths.SCIENTIFIC_MODEL_PATH.read_bytes() == analysis
        return

    campaign_id, resolved_source = reset_campaign.reset_fresh("strong-baseline")

    state = json.loads(
        (root / "runner/state/research_state.json").read_text(encoding="utf-8")
    )
    assert resolved_source == source
    assert campaign_id == state["campaign"]["id"]
    assert state["schema_version"] == 7
    assert state["campaign_phase"] == "recipe_development"
    assert state["recipe_development"] is None
    assert set(state) == repository.STATE_FIELDS
    assert state["campaign"]["id"] != source_state["campaign"]["id"]
    assert state["campaign"]["recipe_source_commit"] == source
    assert state["campaign"]["base_commit"] == "new-head"
    assert state["scientific_model"] == {
        "status": "ready" if analysis is not None else "pending",
        "path": "pi_workspace/scientific_model.md",
        "commit": source if analysis is not None else None,
    }
    assert resolved_commits == ([source] if analysis is not None else [])
    assert state["active_inquiry"] is None
    assert state["scientific_session"] is None
    assert state["pi_checkpoint"] is None
    assert state["pending_operation"] is None
    assert state["operation_events"] == []
    assert state["counters"] == {
        "inquiry": 0,
        "session": 0,
        "measurement": 0,
        "training": 0,
        "event": 0,
    }
    assert state["official_assessment"] is None
    assert state["terminal_state"] is None
    assert state["candidates"] == {}
    assert state["model_roles"] == {
        "working": None,
        "best_known": None,
        "retained": {},
    }

    for relative, content in recipe.items():
        assert (root / relative).read_text(encoding="utf-8") == content
    assert not later.exists()
    assert (root / "campaigns/results.jsonl").read_text(encoding="utf-8") == ""
    assert (root / "campaigns/EXPERIMENTS.md").read_text(
        encoding="utf-8"
    ) == repository.render_operation_log([])
    if analysis is not None:
        assert paths.SCIENTIFIC_MODEL_PATH.read_bytes() == analysis
    else:
        assert not paths.SCIENTIFIC_MODEL_PATH.exists()
    for relative in (
        "pi_workspace/operation_request.json",
        "campaigns/postmortems.md",
        "campaigns/brief.md",
        "campaigns/evaluations",
        "campaigns/checkpoints",
        "robot_learning/lab",
        "runner/state/GOAL_REACHED",
        "runner/state/RECOVERY_PENDING",
        "runner/state/RESTART_PENDING",
        "runner/state/BASELINE_PENDING",
        "models/candidates",
    ):
        assert not (root / relative).exists()
    assert publications[0] == ("recipe", tuple(reset_campaign.plan_paths(plan)))
    assert publications[1][0] == "campaign"
    assert set(reset_campaign.CAMPAIGN_PATHS) <= set(publications[1][1])


@pytest.mark.parametrize("clean", [False, True], ids=["reset", "clean"])
@pytest.mark.parametrize(
    "analysis",
    [
        b"\xff",
        b"",
        b" \r\n",
        b"## Established facts\nThe robot has actuated joints.\n",
        SCIENTIFIC_MODEL_TEXT.replace(
            "Compare measured results: caf\u00e9.", ""
        ).encode("utf-8"),
    ],
    ids=["invalid-utf8", "empty", "whitespace", "incomplete", "empty-register"],
)
def test_invalid_recipe_analysis_is_rejected_before_cleanup(
    monkeypatch, tmp_path, analysis, clean
):
    _bind_paths(monkeypatch, tmp_path)
    (tmp_path / ".git").mkdir()
    previous = {
        "pi_workspace/scientific_model.md": SCIENTIFIC_MODEL_TEXT.encode("utf-8"),
        "runner/state/research_state.json": b'{"previous": true}\n',
        "models/candidates/old/model.zip": b"old policy",
    }
    for relative, content in previous.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda *_args: "source")
    monkeypatch.setattr(reset_campaign, "scientific_plan", lambda _commit: {})
    monkeypatch.setattr(
        reset_campaign,
        "commit_files",
        lambda _commit: {
            "robot_learning/training/current_params.json",
            "pi_workspace/scientific_model.md",
        },
    )
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: {})
    monkeypatch.setattr(reset_campaign, "git_bytes", lambda *_args: analysis)
    monkeypatch.setattr(
        reset_campaign, "verify_task_compatibility", lambda _commit: None
    )

    def mutation_forbidden(*_args, **_kwargs):
        pytest.fail("invalid analysis must be rejected before campaign cleanup")

    for name in ("mark_reset_started", "remove_path", "git"):
        monkeypatch.setattr(reset_campaign, name, mutation_forbidden)

    with pytest.raises(ValueError):
        if clean:
            reset_campaign.clean_campaign_changes(recipe_ref="source")
        else:
            reset_campaign.reset_fresh("source")

    assert not paths.reset_marker_path(tmp_path).exists()
    for relative, content in previous.items():
        assert (tmp_path / relative).read_bytes() == content


@pytest.mark.parametrize(
    "analysis",
    [None, b"\xff", b"", SCIENTIFIC_MODEL_TEXT.encode("utf-8")],
    ids=["missing", "invalid-utf8", "empty", "valid"],
)
def test_recipe_analysis_preserves_analyst_validation_result(
    monkeypatch, tmp_path, analysis
):
    from runner import invocation_result, run_experiment

    _bind_paths(monkeypatch, tmp_path)
    if analysis is not None:
        paths.SCIENTIFIC_MODEL_PATH.parent.mkdir(parents=True)
        paths.SCIENTIFIC_MODEL_PATH.write_bytes(analysis)
    results = {}
    monkeypatch.setattr(invocation_result, "put", results.__setitem__)
    valid = analysis == SCIENTIFIC_MODEL_TEXT.encode("utf-8")

    assert run_experiment.check_scientific_model_deliverable() == (0 if valid else 1)
    assert results["validation"]["valid"] is valid
    if valid:
        assert results["validation"]["message"] == "SCIENTIFIC_MODEL_DELIVERABLE_VALID"
    else:
        assert results["validation"]["message"].startswith(
            "SCIENTIFIC_MODEL_DELIVERABLE_INVALID: "
        )


@pytest.mark.parametrize("schema", [6, 7])
def test_baseline_import_builds_clean_startup_state(monkeypatch, schema):
    candidate = _candidate("f" * 64)
    source_state = _prepared_source_state(candidate)
    if schema == 6:
        source_state["schema_version"] = 6
        source_state.pop("campaign_phase")
        source_state.pop("recipe_development")
    original = copy.deepcopy(source_state)

    state = reset_campaign.baseline_state(
        source_state,
        candidate,
        base_commit="base",
        recipe_source=candidate["scientific_commit"],
    )

    assert state["campaign"]["id"] != source_state["campaign"]["id"]
    assert state["schema_version"] == 7
    assert state["campaign_phase"] == "startup"
    assert state["recipe_development"] is None
    assert source_state == original
    assert state["campaign"]["recipe_source_commit"] == candidate["scientific_commit"]
    assert state["scientific_model"] == source_state["scientific_model"]
    assert state["candidates"] == {candidate["id"]: candidate}
    assert state["model_roles"] == {
        "working": candidate["id"],
        "best_known": candidate["id"],
        "retained": {},
    }
    assert state["active_inquiry"] is None
    assert state["pi_checkpoint"] is None
    assert state["scientific_session"] is None
    assert state["operation_events"] == []
    assert state["pending_operation"] is None
    assert state["terminal_state"] is None
    assert state["official_assessment"] is None
    monkeypatch.setattr(repository, "git", lambda *_args: "a" * 40)
    session = repository.start_scientific_session(
        state,
        kind="startup",
        objective="Review the imported candidate.",
        backend_adapter="copilot",
        backend_model="test-model",
        backend_reasoning="high",
    )
    assert session["id"] == "S1"
    repository.validate_research_state(state, allow_missing_artifact=True)


@pytest.mark.parametrize("schema", [6, 7])
def test_baseline_preflight_normalizes_source_without_mutating_it(monkeypatch, schema):
    candidate = _candidate("f" * 64)
    source_state = _prepared_source_state(candidate)
    source_state["counters"]["session"] = 2
    if schema == 6:
        source_state["schema_version"] = 6
        source_state.pop("campaign_phase")
        source_state.pop("recipe_development")
    else:
        source_state["campaign_phase"] = "research"
    original = copy.deepcopy(source_state)
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: source_state)
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda value, _label: value)
    monkeypatch.setattr(reset_campaign, "git_bytes", lambda *_args: b"model")
    monkeypatch.setattr(
        reset_campaign, "verify_task_compatibility", lambda _commit: None
    )
    monkeypatch.setattr(reset_campaign, "baseline_restore_paths", lambda *_args: [])
    monkeypatch.setattr(
        reset_campaign,
        "artifact_fingerprint_at_commit",
        lambda *_args: candidate["fingerprint"],
    )
    monkeypatch.setattr(reset_campaign, "scientific_plan", lambda _commit: {})

    normalized, imported, _restore, _plan = reset_campaign.verify_baseline_source(
        "source"
    )

    assert normalized["schema_version"] == 7
    assert normalized["campaign_phase"] == "research"
    assert normalized["recipe_development"] is None
    assert imported == candidate
    assert source_state == original


def test_baseline_import_seeds_operation_counters_before_first_training():
    candidate = _candidate("f" * 64)
    source_state = _prepared_source_state(candidate)
    source_state["counters"]["measurement"] = 4

    state = reset_campaign.baseline_state(
        source_state,
        candidate,
        base_commit="base",
        recipe_source=candidate["scientific_commit"],
    )

    assert state["counters"]["measurement"] == 4
    assert state["counters"]["training"] == 1
    assert protocol.allocate_operation_id("training", state) == "T2"
    assert state["candidates"] == {candidate["id"]: candidate}


@pytest.mark.parametrize("schema", [6, 7])
def test_baseline_evidence_lookup_accepts_legacy_measurement_history(
    monkeypatch, tmp_path, schema
):
    _bind_paths(monkeypatch, tmp_path)
    candidate = _candidate("f" * 64)
    source_state = _prepared_source_state(candidate)
    relative = candidate["evaluation_artifacts"][0]
    artifact = tmp_path / relative
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"measurement": 1}\n', encoding="utf-8")
    historical = copy.deepcopy(source_state)
    if schema == 6:
        historical["schema_version"] = 6
        historical.pop("campaign_phase")
        historical.pop("recipe_development")
    historical["operation_events"] = [
        {
            "id": "M1",
            "kind": "measurement",
            "status": "completed",
            "result": {
                "measurements": [
                    {
                        "candidate_id": candidate["id"],
                        "metrics": {
                            "evaluation_artifact": relative,
                            "evaluation_artifact_fingerprint": repository.file_fingerprint(
                                artifact
                            ),
                        },
                    }
                ]
            },
        }
    ]
    required = {
        *(
            f"{candidate['artifact']}/{name}"
            for name in repository.INFERENCE_ARTIFACT_FILES
        ),
        "pi_workspace/scientific_model.md",
    }
    monkeypatch.setattr(reset_campaign, "git", lambda *_args: "source\nmeasurement\n")
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: historical)
    monkeypatch.setattr(reset_campaign, "commit_files", lambda _commit: required)

    assert reset_campaign.baseline_restore_paths(
        "source", candidate, source_state
    ) == sorted(required)
    assert artifact.read_text(encoding="utf-8") == '{"measurement": 1}\n'


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "artifact",
            "benchmark/reference",
            "approved checkpoint archive root",
        ),
        (
            "evaluation_artifacts",
            ["contracts/program.md"],
            "below campaigns/evaluations",
        ),
    ],
)
def test_baseline_source_rejects_out_of_scope_restore_paths(
    monkeypatch, field, value, message
):
    candidate = _candidate("f" * 64)
    candidate[field] = value
    state = _prepared_source_state(candidate)
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: state)
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda value, _label: value)
    monkeypatch.setattr(reset_campaign, "git_bytes", lambda *_args: b"scientific model")
    monkeypatch.setattr(
        reset_campaign, "verify_task_compatibility", lambda _commit: None
    )

    with pytest.raises(ValueError, match=message):
        reset_campaign.verify_baseline_source("source")


def test_invalid_baseline_target_is_rejected_before_backup(monkeypatch):
    candidate = _candidate("f" * 64)
    state = _prepared_source_state(candidate)
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda value, _label: value)
    monkeypatch.setattr(
        reset_campaign,
        "verify_baseline_source",
        lambda _commit: (
            state,
            candidate,
            ["contracts/program.md"],
            {"parent": "source", "restore": [], "remove_created": []},
        ),
    )
    monkeypatch.setattr(
        reset_campaign,
        "remove_path",
        lambda *_args: pytest.fail("cleanup must not start"),
    )

    with pytest.raises(ValueError, match="outside the permitted scope"):
        reset_campaign.reset_baseline("source")


def test_baseline_reset_restores_its_local_evaluation_without_a_backup(
    monkeypatch, tmp_path
):
    _bind_paths(monkeypatch, tmp_path)
    (tmp_path / ".git").mkdir()
    candidate = _candidate("f" * 64)
    state = _prepared_source_state(candidate)
    preserved = tmp_path / "campaigns/evaluations/source/panel.json"
    stale = tmp_path / "campaigns/evaluations/other/stale.json"
    for target, content in ((preserved, '{"panel": 1}\n'), (stale, "{}\n")):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda value, _label: value)
    monkeypatch.setattr(
        reset_campaign,
        "verify_baseline_source",
        lambda _commit: (
            state,
            candidate,
            [],
            {"parent": "source", "restore": [], "remove_created": []},
        ),
    )
    monkeypatch.setattr(repository, "apply_recipe_restore", lambda _plan: None)
    monkeypatch.setattr(reset_campaign, "validate_restored_recipe", lambda: None)
    monkeypatch.setattr(reset_campaign, "apply_restore", lambda *_args: None)
    monkeypatch.setattr(reset_campaign, "publish_reset_changes", lambda *_args: None)
    monkeypatch.setattr(reset_campaign, "git", lambda *_args, **_kwargs: "head\n")
    monkeypatch.setattr(repository, "validate_research_state", lambda *_a, **_k: None)

    campaign_id, source = reset_campaign.reset_baseline("source")

    assert source == "source"
    assert preserved.read_text(encoding="utf-8") == '{"panel": 1}\n'
    assert not stale.exists()
    written = json.loads(paths.STATE_PATH.read_text(encoding="utf-8"))
    assert written["campaign"]["id"] == campaign_id
    assert written["model_roles"]["working"] == candidate["id"]
    assert not list(tmp_path.rglob("research-reset-backups"))


def test_baseline_cli_validates_source_before_cleaning(monkeypatch):
    monkeypatch.setattr(
        reset_campaign,
        "parse_args",
        lambda: reset_campaign.argparse.Namespace(
            mode="baseline",
            clean=True,
            recipe_ref=None,
            baseline_ref="source",
        ),
    )
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda *_args: "source")
    monkeypatch.setattr(
        reset_campaign,
        "verify_baseline_source",
        lambda _commit: (_ for _ in ()).throw(ValueError("invalid source path")),
    )
    monkeypatch.setattr(
        reset_campaign,
        "ensure_clean_repository",
        lambda **_kwargs: pytest.fail("cleaning must not start"),
    )

    assert reset_campaign.main() == 1


def test_retired_training_log_source_argument_is_rejected(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reset_campaign.py",
            "--mode",
            "baseline",
            "--baseline-ref",
            "source",
            "--training-log-source",
            "archive",
        ],
    )

    with pytest.raises(SystemExit):
        reset_campaign.parse_args()


def test_clean_reset_refuses_and_preserves_unrelated_untracked_files(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(*arguments: str, **_kwargs) -> str:
        calls.append(arguments)
        if arguments[:2] == ("ls-files", "--others"):
            return "docs/inquiry-centered-lifecycle-redesign.md\0campaigns/brief.md\0"
        return ""

    monkeypatch.setattr(reset_campaign, "git", fake_git)

    with pytest.raises(RuntimeError, match="docs/inquiry-centered"):
        reset_campaign.clean_campaign_changes()
    assert not any(arguments[:2] == ("clean", "-fd") for arguments in calls)


def test_reset_record_exists_only_once_campaign_changes_start(monkeypatch, tmp_path):
    _bind_paths(monkeypatch, tmp_path)
    (tmp_path / ".git").mkdir()
    marker = paths.reset_marker_path(tmp_path)
    monkeypatch.setattr(
        reset_campaign,
        "parse_args",
        lambda: reset_campaign.argparse.Namespace(
            mode="fresh", clean=False, recipe_ref=None, baseline_ref=None
        ),
    )
    monkeypatch.setattr(reset_campaign, "ensure_clean_repository", lambda **_k: None)
    monkeypatch.setattr(
        reset_campaign,
        "git",
        lambda *arguments, **_kwargs: "" if arguments[0] == "status" else "head\n",
    )
    monkeypatch.setattr(reset_campaign, "publish_reset_changes", lambda *_args: None)

    def refuse(_targets):
        raise RuntimeError("campaign file is locked")

    monkeypatch.setattr(reset_campaign, "preflight_targets", refuse)
    assert reset_campaign.main() == 1
    assert not marker.exists()

    def interrupted(_source):
        raise OSError("interrupted")

    monkeypatch.setattr(reset_campaign, "preflight_targets", lambda _targets: None)
    monkeypatch.setattr(reset_campaign, "write_fresh_campaign", interrupted)
    assert reset_campaign.main() == 1
    assert marker.exists()

    monkeypatch.setattr(
        reset_campaign,
        "write_fresh_campaign",
        lambda _source: {"campaign": {"id": "new"}},
    )
    assert reset_campaign.main() == 0
    assert not marker.exists()
