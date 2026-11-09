"""Scoped Git publication without oversized process arguments."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from runner import (
    execution,
    paths,
    protocol,
    query_training_log,
    recipe_development,
    repository,
    run_experiment,
)


def _remove_readonly(function, value, error):
    path = Path(value)
    if (
        os.name != "nt"
        or not isinstance(error[1], PermissionError)
        or not path.is_file()
        or not path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
    ):
        raise error[1]
    path.chmod(stat.S_IWRITE)
    function(value)


@pytest.fixture(autouse=True)
def single_root_publication(monkeypatch):
    # Split campaign repositories never push; these tests cover the push path.
    monkeypatch.setattr(paths, "SPLIT", False)


@pytest.fixture
def git_repository(monkeypatch):
    # Windows Git cannot access pytest's mode-0o700 temporary directories.
    root = Path(tempfile.gettempdir()) / f"robot-learning-git-test-{uuid4().hex}"
    root.mkdir()
    monkeypatch.setattr(paths, "ROOT", root)
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(count + 1))
    monkeypatch.setenv(f"GIT_CONFIG_KEY_{count}", "safe.directory")
    monkeypatch.setenv(f"GIT_CONFIG_VALUE_{count}", str(root))
    try:
        repository.git("init", "--quiet")
        repository.git("config", "user.name", "Tests")
        repository.git("config", "user.email", "tests@example.invalid")
        repository.git("config", "commit.gpgsign", "false")
        monkeypatch.setattr(repository, "push_head", lambda: None)
        yield root
    finally:
        shutil.rmtree(root, onerror=_remove_readonly)


def test_initialized_campaign_keeps_generated_outputs_out_of_scientific_delta(
    git_repository, monkeypatch
):
    from tools.initialize_campaign import CAMPAIGN_GITIGNORE

    root = git_repository
    (root / ".gitignore").write_text(CAMPAIGN_GITIGNORE, encoding="utf-8")
    reward = root / "robot_learning/training/reward.py"
    reward.parent.mkdir(parents=True)
    reward.write_text("VALUE = 1\n", encoding="utf-8")
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "initial recipe")
    monkeypatch.setattr(paths, "SPLIT", True)
    ignored_outputs = [
        "campaigns/training_logs/campaign-one/t1-attempt-1.log",
        "campaigns/evaluations/campaign-one/research.json",
        "campaigns/evaluations/campaign-one/reference.json",
        "campaigns/evaluations/campaign-one/official.json",
        "campaigns/evaluations/campaign-one/research.json.progress",
        "campaigns/evaluations/campaign-one/research.json.progress.tmp",
        "campaigns/evaluations/campaign-one/module.json",
        "campaigns/evaluations/campaign-one/.module.json.pending",
        "campaigns/brief.md",
        "models/candidates/campaign-one/t1/model.zip",
        "models/candidates/campaign-one/t1/candidate_manifest.json",
        "models/candidates/campaign-one/t1/checkpoint-10/training_metrics.json",
        "runner/state/last_train_summary.md",
        "runner/state/last_evaluation.json",
        "runner/state/GOAL_REACHED",
        "runner/state/RECOVERY_PENDING",
        "runner/state/RESTART_PENDING",
        "pi_workspace/operation_request.json",
        "reports/session_usage/campaign-one.jsonl",
        ".copilot/opencode/catalogue.json",
        ".copilot/opencode/session.json",
        ".copilot/controller-stops/request.stop",
        ".copilot/large-output/review.json",
        "robot_learning/training/__pycache__/reward.pyc",
    ]
    for relative in ignored_outputs:
        output = root / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("generated output\n", encoding="utf-8")
    reward.write_text("VALUE = 2\n", encoding="utf-8")

    ignored = repository.git("check-ignore", "--", *ignored_outputs).splitlines()
    assert set(ignored) == set(ignored_outputs)
    assert all(
        paths.locate(relative) == root / relative for relative in ignored_outputs
    )
    assert repository.status_paths((".",)) == ["robot_learning/training/reward.py"]
    delta = repository.scientific_delta("HEAD")
    protocol.validate_research_delta_ownership(delta)
    assert delta == ["robot_learning/training/reward.py"]
    assert all(
        (root / relative).read_text(encoding="utf-8") == "generated output\n"
        for relative in ignored_outputs
    )


def _development_delivery(git_repository, monkeypatch):
    from tools.initialize_campaign import CAMPAIGN_GITIGNORE

    root = git_repository
    (root / ".gitignore").write_text(CAMPAIGN_GITIGNORE, encoding="utf-8")
    monkeypatch.setattr(paths, "SPLIT", True)
    for name, relative in {
        "STATE_PATH": "runner/state/research_state.json",
        "RESULTS_PATH": "campaigns/results.jsonl",
        "LOG_PATH": "campaigns/EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": "pi_workspace/operation_request.json",
        "CAMPAIGNS_DIR": "campaigns",
        "TRAINING_LOG_DIR": "campaigns/training_logs",
    }.items():
        monkeypatch.setattr(paths, name, root / relative)
    files = {
        "robot_learning/__init__.py": b"",
        "robot_learning/training/reward.py": b"VALUE = 'chosen'\n",
        "robot_learning/training/current_params.json": b'{"training": {"n_envs": 1}}\n',
        "robot_learning/training/reward_config.json": b'{"progress": 10}\r\n',
        "robot_learning/scenario/assets/task.xml": b'<task name="chosen"/>\r\n',
        "robot_learning/scenario/assets/texture.bin": b"\x00\xffrecipe asset\x80",
        "robot_learning/scenario/assets/targets.jsonl": b'{"target": [1, 2]}\n',
        "robot_learning/training/training_metrics.json": b'{"score": 0.3}',
        "robot_learning/training/train.log": b"private training history\n",
        "robot_learning/training/checkpoints/step-10/model.zip": b"trained policy",
        "robot_learning/lab/trial.py": b"VALUE = 'private'\n",
        "robot_learning/variants/other/training/reward.py": b"VALUE = 'alternative'\n",
        "pi_workspace/scientific_model.md": b"Accepted model\r\nExact bytes.\r\n",
        "models/candidates/campaign/t1/model.zip": b"old trained policy",
        "campaigns/training_logs/campaign/t1.log": b"private training history",
        "campaigns/evaluations/campaign/panel.json": b'{"score": 0.3}',
        ".copilot/session-state/development/session.json": b"private session",
        "reports/session_usage/campaign.jsonl": b'{"aiu": 12}\n',
    }
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "development history")
    old_commit = repository.git("rev-parse", "HEAD").strip()
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": old_commit},
        last_verdict="development",
    )
    state["scientific_model"].update(status="ready", commit=old_commit)
    request = {
        key: "Development conclusion."
        for key in repository.CHECKPOINT_FIELDS
        - {
            "session_id",
            "inquiry_id",
            "scientific_commit",
            "evidence_references",
            "completed_operations",
        }
    }
    request.update(evidence_references=[], completed_operations=[])
    checkpoint = {
        **request,
        "session_id": "S1",
        "inquiry_id": None,
        "scientific_commit": old_commit,
    }
    state.update(
        campaign_phase="startup",
        recipe_development=checkpoint,
        pi_checkpoint=checkpoint,
    )
    state["counters"].update(session=1, event=1)
    state["operation_events"] = [
        {
            "id": "E1",
            "kind": "checkpoint",
            "session_id": "S1",
            "inquiry_id": None,
            "request": request,
            "result": {"status": "checkpointed", "session_id": "S1"},
            "status": "completed",
            "error": None,
            "supersedes": None,
            "superseded_by": None,
            "completed_at": "now",
        }
    ]
    state["candidates"]["T1:checkpoint-10"] = {
        "id": "T1:checkpoint-10",
        "artifact": "models/candidates/campaign/t1",
        "fingerprint": "a" * 64,
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {"training": {"n_envs": 1}},
        "scientific_commit": old_commit,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["model_roles"]["working"] = "T1:checkpoint-10"
    repository.write_state(state)
    repository.git("add", "--", "runner/state/research_state.json")
    repository.git("commit", "--quiet", "-m", "finalized development checkpoint")
    archive = paths.recipe_development_archive(root, "campaign")
    paths.recipe_handoff_directory(root).mkdir(parents=True, exist_ok=True)
    return state, old_commit, files, archive


def _complete_candidate(root, state, candidate_id="T1:checkpoint-10"):
    artifact = "campaigns/checkpoints/retained/campaign/t1-selected"
    for name in (*repository.INFERENCE_ARTIFACT_FILES, "vecnormalize.pkl"):
        target = root / artifact / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"saved {name}".encode())
    candidate = state["candidates"][candidate_id]
    candidate["artifact"] = artifact
    candidate["fingerprint"] = repository.artifact_fingerprint(root / artifact)
    state["model_roles"]["best_known"] = candidate_id
    return artifact


def test_recipe_delivery_carries_the_best_known_candidate_and_its_lineage(
    git_repository, monkeypatch
):
    state, old_commit, _files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    artifact = _complete_candidate(git_repository, state)
    original = dict(state["candidates"]["T1:checkpoint-10"])
    lineage_of = recipe_development.candidate_lineage
    monkeypatch.setattr(
        recipe_development,
        "candidate_lineage",
        lambda state, candidate: {
            **lineage_of(state, candidate),
            "chapters": [
                {
                    "operation": "T1",
                    "variant": None,
                    "measurements": [{"operation": "M3"}],
                }
            ],
        },
    )
    logs = paths.TRAINING_LOG_DIR / repository.current_campaign_id(state)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "t1-attempt-1.log").write_text("lineage log", encoding="utf-8")
    (logs / "t2-attempt-1.log").write_text("other log", encoding="utf-8")
    try:
        assert recipe_development.publish(state, {"training": {"n_envs": 1}})
        fresh = repository.load_state(allow_missing_artifact=False)
        assert [path.name for path in logs.iterdir()] == ["t1-attempt-1.log"]
        assert query_training_log._training_operation(fresh, "T1")[
            "recipe_development_lineage"
        ]
        with pytest.raises(ValueError, match="recipe_lineage.json"):
            query_training_log._training_operation(fresh, "T2")
        session = {"id": "S2", "kind": "startup", "inquiry_id": None}
        checkpoint_request = {
            key: "Startup conclusion."
            for key in repository.CHECKPOINT_FIELDS
            - {"session_id", "inquiry_id", "scientific_commit"}
        }
        checkpoint_request.update(
            evidence_references=["T1", "M3"], completed_operations=[]
        )
        planned = protocol.plan_checkpoint(
            checkpoint_request,
            {**fresh, "scientific_session": {**session, "operation_ids": []}},
        )
        repository.validate_research_state(
            {
                **fresh,
                "pi_checkpoint": {
                    **planned,
                    "scientific_commit": fresh["scientific_model"]["commit"],
                },
            },
            allow_missing_artifact=False,
        )
        with pytest.raises(ValueError, match=r"T2\. Accepted: \['M3', 'T1'\]"):
            protocol.plan_checkpoint(
                {**checkpoint_request, "evidence_references": ["T2"]},
                {**fresh, "scientific_session": {**session, "operation_ids": []}},
            )
        delivered = fresh["candidates"]["T1:checkpoint-10"]
        assert set(fresh["candidates"]) == {"T1:checkpoint-10"}
        assert fresh["model_roles"] == {
            "working": "T1:checkpoint-10",
            "best_known": "T1:checkpoint-10",
            "retained": {},
        }
        assert delivered["fingerprint"] == original["fingerprint"]
        assert delivered["evaluation_artifacts"] == []
        assert delivered["scientific_commit"] != old_commit
        repository.require_resolvable_commit(delivered["scientific_commit"])
        assert fresh["counters"]["training"] == 1
        assert fresh["operation_events"] == []
        for name in repository.INFERENCE_ARTIFACT_FILES:
            repository.require_path_at_commit("HEAD", f"{artifact}/{name}")
        lineage = json.loads(
            (git_repository / recipe_development.LINEAGE_PATH).read_text()
        )
        assert lineage["candidate"] == "T1:checkpoint-10"
        repository.require_path_at_commit("HEAD", recipe_development.LINEAGE_PATH)
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_candidate_lineage_follows_parents_and_variants_first_run_first():
    def training(identifier, result):
        return {
            "id": identifier,
            "kind": "training",
            "status": "completed",
            "result": result,
        }

    def candidate(identifier, steps):
        operation, name = identifier.split(":")
        return {"origin_operation": operation, "name": name, "training_steps": steps}

    state = {
        "candidates": {
            "T1:wide-checkpoint-100": candidate("T1:wide-checkpoint-100", 100),
            "T2:checkpoint-50": candidate("T2:checkpoint-50", 50),
        },
        "operation_events": [
            training(
                "T1",
                {
                    "initialization": "fresh",
                    "seed": 0,
                    "parent": None,
                    "variants": [
                        {"label": "wide", "parent": None, "parameters": {"a": 1}},
                        {"label": "narrow", "parent": None, "parameters": {}},
                    ],
                    "mechanical_provenance": {
                        "changed_files": [
                            {"path": "robot_learning/variants/wide/env.py"},
                            {"path": "robot_learning/variants/narrow/env.py"},
                        ]
                    },
                },
            ),
            training(
                "T2",
                {
                    "initialization": "transfer",
                    "seed": 1,
                    "parent": "T1:wide-checkpoint-100",
                    "mechanical_provenance": {"changed_files": []},
                },
            ),
            {
                "id": "M1",
                "kind": "measurement",
                "status": "completed",
                "result": {
                    "measurements": [
                        {
                            "candidate": "T2:checkpoint-50",
                            "instrument": "research_evaluation",
                            "metrics": {"successes": 9, "episodes": 10},
                        }
                    ]
                },
            },
        ],
    }
    lineage = recipe_development.candidate_lineage(state, "T2:checkpoint-50")
    first, second = lineage["chapters"]
    assert first["operation"] == "T1" and first["variant"] == "wide"
    assert first["changed_files"] == ["robot_learning/variants/wide/env.py"]
    assert first["parameter_changes"] == {"a": 1}
    assert second["parent"] == "T1:wide-checkpoint-100"
    assert second["measurements"] == [
        {
            "operation": "M1",
            "instrument": "research_evaluation",
            "successes": 9,
            "episodes": 10,
        }
    ]


def test_recipe_delivery_preserves_tracked_canonical_assets_without_training_state(
    git_repository, monkeypatch
):
    state, _old_commit, files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    untracked = (
        "robot_learning/training/model.zip",
        "robot_learning/training/policy.optimizer.pth",
        "robot_learning/training/vecnormalize.pkl",
        "robot_learning/training/untracked_config.json",
    )
    for logical in untracked:
        (git_repository / logical).write_bytes(b"untracked development output")
    try:
        assert recipe_development.publish(state, {"training": {"n_envs": 1}})
        for logical in (
            "robot_learning/training/reward_config.json",
            "robot_learning/scenario/assets/task.xml",
            "robot_learning/scenario/assets/texture.bin",
            "robot_learning/scenario/assets/targets.jsonl",
        ):
            assert (git_repository / logical).read_bytes() == files[logical]
            repository.require_path_at_commit("HEAD", logical)
        assert json.loads(
            (git_repository / "robot_learning/training/current_params.json").read_text()
        ) == {"training": {"n_envs": 1}}
        for logical in (
            *untracked,
            "robot_learning/training/training_metrics.json",
            "robot_learning/training/train.log",
            "robot_learning/training/checkpoints",
        ):
            assert not (git_repository / logical).exists()
        assert (git_repository / "pi_workspace/scientific_model.md").read_bytes() == (
            files["pi_workspace/scientific_model.md"]
        )
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


@pytest.mark.parametrize(
    "name", ["model.zip", "policy.optimizer.pth", "vecnormalize.pkl"]
)
def test_recipe_delivery_rejects_tracked_trained_artifacts_before_archiving(
    git_repository, monkeypatch, name
):
    state, _old_commit, _files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    artifact = git_repository / "robot_learning/training" / name
    artifact.write_bytes(b"serialized development state")
    reward = git_repository / "robot_learning/training/reward.py"
    reward.write_text(
        "from pathlib import Path\n"
        f"VALUE = Path(__file__).with_name({name!r}).read_bytes()\n",
        encoding="utf-8",
    )
    repository.git("add", "--", "robot_learning/training")
    repository.git("commit", "--quiet", "-m", "canonical trained dependency")
    head = repository.git("rev-parse", "HEAD").strip()
    state["recipe_development"]["scientific_commit"] = head
    repository.write_state(state)
    repository.git("add", "--", "runner/state/research_state.json")
    repository.git("commit", "--quiet", "-m", "record canonical trained dependency")
    head = repository.git("rev-parse", "HEAD").strip()
    try:
        with pytest.raises(RuntimeError, match="excluded trained artifact"):
            recipe_development.publish(state, {"training": {"n_envs": 1}})
        assert not archive.exists()
        assert repository.git("rev-parse", "HEAD").strip() == head
        assert artifact.read_bytes() == b"serialized development state"
        assert repository.load_state(allow_missing_artifact=True)["candidates"]
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


@pytest.mark.parametrize("change", ["modified", "missing", "hardlink"])
def test_recipe_delivery_validates_canonical_assets_before_archiving(
    git_repository, monkeypatch, change
):
    state, _old_commit, _files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    source = git_repository / "robot_learning/training/reward_config.json"
    if change == "modified":
        source.write_bytes(b'{"progress": 20}\n')
    elif change == "missing":
        source.unlink()
    else:
        os.link(source, git_repository / "robot_learning/lab/config_alias.json")
    try:
        with pytest.raises((ValueError, RuntimeError)):
            recipe_development.publish(state, {"training": {"n_envs": 1}})
        assert not archive.exists()
        assert repository.load_state(allow_missing_artifact=True)["candidates"]
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_recipe_delivery_is_fresh_and_development_git_is_private(
    git_repository, monkeypatch
):
    state, old_commit, files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    try:
        assert recipe_development.publish(state, {"training": {"n_envs": 1}})
        fresh = repository.load_state(allow_missing_artifact=True)
        from runner import artifact_evidence_query, build_brief

        monkeypatch.setattr(build_brief, "RESEARCH_DIR", paths.CAMPAIGNS_DIR)
        transitional = git_repository / "runner/state/research_state.json"
        fresh_bytes = transitional.read_bytes()
        transitional.write_text(json.dumps(state), encoding="utf-8")
        assert "Development conclusion." not in build_brief.render_research_brief()
        transitional.write_bytes(fresh_bytes)
        assert "Development conclusion." not in build_brief.render_research_brief()
        index = json.loads(
            artifact_evidence_query.query_artifact({"action": "operations"}, "campaign")
        )
        assert index["result"]["matches"] == []
        for action in ("metadata", "read", "query", "discover"):
            request = {"action": action, "operation_id": "E1"}
            if action == "query":
                request["path"] = "/"
            result = json.loads(
                artifact_evidence_query.query_artifact(request, "campaign")
            )
            assert result["status"] == "artifact_unavailable"
        assert fresh["campaign_phase"] == "startup"
        assert fresh["recipe_phase"] == "included"
        assert fresh["campaign"]["id"] == state["campaign"]["id"]
        assert fresh["recipe_development"] is fresh["pi_checkpoint"] is None
        assert fresh["recipe_handover"] == {
            name: state["recipe_development"][name]
            for name in repository.RECIPE_HANDOVER_FIELDS
        }
        assert (
            fresh["scientific_session"]
            is fresh["pending_operation"]
            is fresh["active_inquiry"]
            is None
        )
        assert fresh["candidates"] == {}
        with pytest.raises(KeyError, match="unknown candidate"):
            protocol.resolve_candidate(fresh, "T1:checkpoint-10")
        assert fresh["model_roles"] == {
            "working": None,
            "best_known": None,
            "retained": {},
        }
        assert fresh["operation_events"] == []
        archived_state = json.loads(
            (archive / "runner/state/research_state.json").read_text(encoding="utf-8")
        )
        assert archived_state["candidates"] == state["candidates"]
        assert archived_state["operation_events"] == state["operation_events"]
        assert fresh["counters"] == state["counters"]
        assert (
            git_repository / "pi_workspace/scientific_model.md"
        ).read_bytes() == files["pi_workspace/scientific_model.md"]
        assert (
            git_repository / "reports/session_usage/campaign.jsonl"
        ).read_bytes() == files["reports/session_usage/campaign.jsonl"]
        for relative, content in files.items():
            assert (archive / relative).read_bytes() == content
        for relative in (
            "models",
            ".copilot",
            "robot_learning/lab",
            "robot_learning/variants",
            "campaigns/evaluations",
            "campaigns/training_logs",
        ):
            assert not (git_repository / relative).exists()
        repository.require_path_at_commit(
            fresh["scientific_model"]["commit"], fresh["scientific_model"]["path"]
        )
        repository.require_resolvable_commit(fresh["campaign"]["base_commit"])
        with pytest.raises(RuntimeError, match="does not resolve"):
            repository.require_resolvable_commit(old_commit)
        assert not recipe_development.publish(fresh, {"training": {"n_envs": 1}})
        assert not recipe_development.recover()
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


@pytest.mark.parametrize("recipe_at_base", [False, True])
def test_recipe_delivery_keeps_recipe_references_but_not_development_history(
    git_repository, monkeypatch, recipe_at_base
):
    (git_repository / "recipe.txt").write_text("starting recipe\n", encoding="utf-8")
    repository.git("add", "--", "recipe.txt")
    repository.git("commit", "--quiet", "-m", "starting recipe")
    recipe = repository.git("rev-parse", "HEAD").strip()
    repository.git("tag", "starting-recipe-v1", recipe)
    repository.git("tag", "-a", "starting-recipe-annotated", "-m", "recipe", recipe)
    base = recipe
    if not recipe_at_base:
        repository.git("commit", "--quiet", "--allow-empty", "-m", "campaign base")
        base = repository.git("rev-parse", "HEAD").strip()
    state, old_commit, _files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    state["campaign"]["base_commit"] = base
    repository.write_state(state)
    repository.git("add", "--", "runner/state/research_state.json")
    repository.git("commit", "--quiet", "-m", "record campaign base")
    # A tag on the campaign's own history must not carry it into the delivery.
    repository.git("tag", "development-snapshot", old_commit)
    try:
        assert recipe_development.publish(state, {"training": {"n_envs": 1}})
        assert (
            repository.git("rev-parse", "starting-recipe-v1^{commit}").strip() == recipe
        )
        assert (
            repository.git("rev-parse", "starting-recipe-annotated^{commit}").strip()
            == recipe
        )
        assert "development-snapshot" not in repository.git("tag", "--list")
        with pytest.raises(RuntimeError, match="does not resolve"):
            repository.require_resolvable_commit(old_commit)
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


@pytest.mark.parametrize(
    "stage", ["published", "awaiting_session_end", "preparing", "ready"]
)
def test_reset_ends_the_previous_delivery_record(tmp_path, stage):
    root = tmp_path / "campaign"
    root.mkdir()
    marker = paths.recipe_handoff_directory(root) / "handoff.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps({"stage": stage, "campaign_id": "old"}), encoding="utf-8"
    )
    if stage in {"preparing", "ready"}:
        with pytest.raises(RuntimeError, match="unfinished"):
            recipe_development.require_no_unfinished_swap(root)
        assert marker.is_file()
        return
    recipe_development.require_no_unfinished_swap(root)
    recipe_development.abandon_queued_delivery(root)
    abandoned = marker.with_name("handoff.abandoned-old.json")
    assert marker.is_file() is (stage == "published")
    assert abandoned.is_file() is (stage == "awaiting_session_end")


@pytest.mark.parametrize("boundary", ["staged", "archived", "replaced"])
def test_recipe_delivery_recovers_without_rebuilding_or_losing_archive(
    git_repository, monkeypatch, boundary
):
    state, old_commit, files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    original_finish = recipe_development._finish_swap
    original_replace = Path.replace

    def replace(source, target):
        result = original_replace(source, target)
        if (boundary == "archived" and target.resolve() == archive.resolve()) or (
            boundary == "replaced" and target.resolve() == git_repository.resolve()
        ):
            raise OSError("interrupted directory swap")
        return result

    def finish(root, marker):
        raise OSError("interrupted after staging")

    try:
        if boundary == "staged":
            monkeypatch.setattr(recipe_development, "_finish_swap", finish)
        else:
            monkeypatch.setattr(Path, "replace", replace)
        with pytest.raises(OSError, match="interrupted"):
            recipe_development.publish(state, {"training": {"n_envs": 1}})
        monkeypatch.setattr(recipe_development, "_finish_swap", original_finish)
        monkeypatch.setattr(Path, "replace", original_replace)
        monkeypatch.setattr(
            recipe_development,
            "_build_public_tree",
            lambda *_args: pytest.fail("recovery must not rebuild publication"),
        )
        assert recipe_development.recover()
        fresh = repository.load_state(allow_missing_artifact=True)
        assert fresh["campaign_phase"] == "startup"
        assert fresh["operation_events"] == []
        assert (
            repository._git_at(
                archive,
                ("-c", f"safe.directory={archive}", "cat-file", "-t", old_commit),
            ).strip()
            == "commit"
        )
        for relative, content in files.items():
            assert (archive / relative).read_bytes() == content
        assert not recipe_development.recover()
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_queued_recipe_delivery_from_runner_child(git_repository, monkeypatch):
    from runner.launcher.campaign_lock import CampaignLock
    from runner.launcher.child import ChildRunner, RunLog
    from runner.launcher.phases import Phases
    from runner.launcher.runner_client import RunnerClient

    state, _old_commit, _files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    original_directory = Path.cwd()
    log = RunLog(git_repository / "reports/launcher/test.log")
    stop = SimpleNamespace(
        path=paths.stop_request_path(git_repository),
        deadline_passed=lambda: False,
        requested=lambda: False,
    )
    children = ChildRunner(cwd=git_repository, stop=stop, log=log)
    client = RunnerClient(
        harness_root=paths.HARNESS_ROOT,
        children=children,
        trust=SimpleNamespace(verify=lambda: None, refresh=lambda: None),
        timesteps=10_000,
        max_timesteps=500_000,
    )
    phase = Phases(
        options=SimpleNamespace(
            campaign_root=git_repository, harness_root=paths.HARNESS_ROOT
        ),
        runner=client,
        sessions=SimpleNamespace(close_runtime=lambda: None, forget=lambda: None),
        stop=stop,
        events=SimpleNamespace(),
        home=Path.home(),
    )
    try:
        with CampaignLock(git_repository, "busy"):
            recipe_development.queue(state, {"training": {"n_envs": 1}})
            monkeypatch.setenv(paths.CAMPAIGN_ROOT_ENV, str(git_repository))
            monkeypatch.setenv(
                "PYTHONPATH",
                os.pathsep.join((str(git_repository), str(paths.HARNESS_ROOT))),
            )
            os.chdir(git_repository)
            assert phase.recipe_delivery() == 0
            assert Path.cwd().resolve() == git_repository.resolve()
        assert repository.load_state(allow_missing_artifact=True)["candidates"] == {}
        assert (archive / "reports/launcher/test.log").is_file()
        assert (
            paths.recipe_handoff_directory(git_repository) / "launcher-delivery.log"
        ).is_file()
    finally:
        os.chdir(original_directory)
        client.close()
        log.close()
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_preparing_recipe_recovers_in_selected_uv_child_under_campaign_lock(
    git_repository, monkeypatch
):
    from runner.launcher.campaign_lock import CampaignLock
    from runner.launcher.runner_client import uv_executable

    state, _old_commit, _files, _archive = _development_delivery(
        git_repository, monkeypatch
    )

    def interrupted(*_args):
        raise OSError("interrupted during preparation")

    monkeypatch.setattr(recipe_development, "_build_public_tree", interrupted)
    try:
        with CampaignLock(git_repository, "busy"):
            with pytest.raises(OSError, match="interrupted during preparation"):
                recipe_development.publish(state, {"training": {"n_envs": 1}})
            result = subprocess.run(
                [
                    uv_executable(),
                    "run",
                    "--project",
                    str(paths.HARNESS_ROOT),
                    "python",
                    "-m",
                    "runner.recipe_development",
                ],
                cwd=paths.HARNESS_ROOT,
                env=paths.python_environment(git_repository),
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr
        fresh = repository.load_state(allow_missing_artifact=True)
        assert fresh["campaign_phase"] == "startup"
        assert fresh["operation_events"] == []
        assert fresh["candidates"] == {}
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


@pytest.mark.parametrize(
    "mismatch", ["parameters", "source", "head", "foreign", "campaign", "stage"]
)
def test_recipe_delivery_rejects_mismatched_inputs_without_mutation(
    git_repository, monkeypatch, mismatch
):
    state, _old_commit, _files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    parameters = {"training": {"n_envs": 1}}
    recipe_development.queue(state, parameters)
    marker_path = paths.recipe_handoff_directory(git_repository) / "handoff.json"
    marker = json.loads(marker_path.read_text())
    if mismatch == "parameters":
        marker["parameters"] = {"training": {"n_envs": 99}}
    elif mismatch == "source":
        marker["scientific_commit"] = "f" * 40
    elif mismatch == "head":
        marker["development_head"] = "f" * 40
    elif mismatch == "foreign":
        marker.update(campaign_id="previous", stage="published")
        parameters = {"training": {"n_envs": 99}}
    elif mismatch == "campaign":
        state["campaign"]["id"] = "foreign-campaign"
    else:
        marker["stage"] = "invalid"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    before = marker_path.read_bytes()
    head = repository.git("rev-parse", "HEAD").strip()
    try:
        with pytest.raises(RuntimeError, match="Recipe delivery"):
            recipe_development.publish(state, parameters)
        assert marker_path.read_bytes() == before
        assert repository.git("rev-parse", "HEAD").strip() == head
        assert not archive.exists()
        assert not (archive.parent / "public").exists()
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_selected_variant_materializes_effective_files_without_changing_restore_schema(
    git_repository, monkeypatch
):
    # Content, not line-ending conversion, is under test here.
    repository.git("config", "core.autocrlf", "false")
    state, old_commit, files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    state["campaign_phase"] = "recipe_development"
    state["recipe_development"] = state["pi_checkpoint"] = None
    state["operation_events"] = [
        {"id": "T1", "kind": "training", "request": {"variants": [{"label": "other"}]}}
    ]
    state["candidates"]["T1:checkpoint-10"]["name"] = "other-checkpoint-10"
    selected = [
        "robot_learning/training/reward.py",
        "robot_learning/training/current_params.json",
    ]
    plan = {
        **protocol.plan_recipe_paths(old_commit, selected),
        "candidate_id": "T1:checkpoint-10",
        "parameters": {"training": {"n_envs": 4}},
        "session_id": "S1",
    }
    assert recipe_development.restore_variant(state, plan)
    assert recipe_development.variant_matches(state, plan)
    assert (git_repository / selected[0]).read_bytes() == files[
        "robot_learning/variants/other/training/reward.py"
    ]
    assert json.loads((git_repository / selected[1]).read_text()) == plan["parameters"]
    assert (git_repository / "robot_learning/__init__.py").read_bytes() == files[
        "robot_learning/__init__.py"
    ]
    assert set(plan) == {
        "parent",
        "restore",
        "remove_created",
        "candidate_id",
        "parameters",
        "session_id",
    }


def test_full_variant_recipe_restore_materializes_all_effective_sources_and_parameters(
    git_repository, monkeypatch
):
    # Content, not line-ending conversion, is under test here.
    repository.git("config", "core.autocrlf", "false")
    state, _old_commit, files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    helper = "robot_learning/training/variant_helper.py"
    base = "robot_learning/training/base_helper.py"
    overlay_files = {
        f"robot_learning/variants/other/{helper.removeprefix('robot_learning/')}": b"VALUE = 'selected helper'\n",
        f"robot_learning/variants/ignored/{helper.removeprefix('robot_learning/')}": b"VALUE = 'unselected helper'\n",
        "robot_learning/variants/other/__init__.py": b"UNTRUSTED = True\n",
        base: b"VALUE = 'unchanged base'\n",
    }
    for relative, content in overlay_files.items():
        target = git_repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    repository.git("add", "--", "robot_learning")
    repository.git("commit", "--quiet", "-m", "record full variant recipe")
    parent = repository.git("rev-parse", "HEAD").strip()
    state.update(
        campaign_phase="recipe_development",
        recipe_development=None,
        pi_checkpoint=None,
        scientific_session={"id": "S2", "kind": "recipe_development"},
    )
    candidate = state["candidates"]["T1:checkpoint-10"]
    candidate.update(
        name="other-checkpoint-10",
        scientific_commit=parent,
        parameters={"training": {"n_envs": 4}},
    )
    artifact = git_repository / candidate["artifact"]
    for filename in {*repository.ARTIFACT_FILES, *repository.INFERENCE_ARTIFACT_FILES}:
        (artifact / filename).write_bytes(b"frozen candidate")
    candidate["fingerprint"] = repository.artifact_fingerprint(artifact)
    fingerprint = candidate["fingerprint"]
    state["operation_events"] = [
        {
            "id": "T1",
            "kind": "training",
            "request": {"variants": [{"label": "other"}, {"label": "ignored"}]},
        }
    ]
    added = "robot_learning/training/added.py"
    (git_repository / added).write_bytes(b"EXTRA = True\n")
    laboratory = git_repository / "robot_learning/lab/trial.py"
    laboratory.write_bytes(b"VALUE = 'current laboratory'\n")
    request = {"candidate": candidate["id"], "reason": "Restore the effective recipe."}
    protocol.validate_operation_shape("restore_recipe", request)
    plan = protocol.plan_recipe_restore(request, state)
    assert {helper, base, "robot_learning/training/reward.py"} <= set(plan["restore"])
    assert plan["remove_created"] == [added]
    assert all(recipe_development.is_recipe_source(path) for path in plan["restore"])
    result = {}

    def complete(current, restored_result, apply):
        repository._validate_completed_event_result("restore_recipe", restored_result)
        result.update(restored_result)
        apply(current, restored_result)

    monkeypatch.setattr(run_experiment, "_complete_operation", complete)
    monkeypatch.setattr(
        repository,
        "durable_artifact_destination",
        lambda **_kwargs: git_repository / "campaigns/checkpoints/retained/selected",
    )
    parameters = git_repository / "robot_learning/training/current_params.json"
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: json.loads(parameters.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *_args, **_kwargs: pytest.fail("no training"),
    )
    state["model_roles"]["best_known"] = candidate["id"]
    state["model_roles"]["retained"] = {"selected": candidate["id"]}
    assert (
        run_experiment._execute_recipe_restore(
            state, {"progress": "restoring", "data": {"plan": plan}}
        )
        == 0
    )
    assert recipe_development.variant_matches(state, plan)
    assert (git_repository / helper).read_bytes() == b"VALUE = 'selected helper'\n"
    assert (git_repository / base).read_bytes() == overlay_files[base]
    assert (git_repository / "robot_learning/training/reward.py").read_bytes() == files[
        "robot_learning/variants/other/training/reward.py"
    ]
    assert json.loads(parameters.read_text()) == candidate["parameters"]
    assert not (git_repository / added).exists()
    assert laboratory.read_bytes() == b"VALUE = 'current laboratory'\n"
    for relative in (
        "robot_learning/__init__.py",
        "robot_learning/training/training_metrics.json",
        "robot_learning/training/train.log",
        "robot_learning/training/checkpoints/step-10/model.zip",
        "campaigns/evaluations/campaign/panel.json",
    ):
        assert (git_repository / relative).read_bytes() == files[relative]
    assert repository.artifact_fingerprint(artifact) == fingerprint
    assert (
        repository.artifact_fingerprint(git_repository / candidate["artifact"])
        == fingerprint
    )
    assert state["model_roles"] == {
        "working": candidate["id"],
        "best_known": candidate["id"],
        "retained": {"selected": candidate["id"]},
    }
    assert result["parameters"] == candidate["parameters"]
    assert result["removed_paths"] == [added]


def test_variant_restore_writes_the_checkout_bytes_of_the_target(git_repository):
    # Raw blob bytes would change the evaluation-semantics fingerprint of a
    # restored file without any content change.
    (git_repository / ".gitattributes").write_text("*.py text eol=crlf\n")
    overlay = "robot_learning/variants/selected/scenario/environment.py"
    source = git_repository / overlay
    source.parent.mkdir(parents=True)
    source.write_bytes(b"A = 1\nB = 2\n")
    repository.git("add", "--", ".gitattributes", overlay)
    repository.git("commit", "--quiet", "-m", "variant source")
    parent = repository.git("rev-parse", "HEAD").strip()
    assert (
        recipe_development._recorded_source(
            parent, overlay, "robot_learning/scenario/environment.py"
        )
        == b"A = 1\r\nB = 2\r\n"
    )


@pytest.mark.parametrize("mode", ["isolated", "skipped", "inquiry"])
def test_selected_overlay_only_file_requires_isolated_recipe_development(
    git_repository, monkeypatch, mode
):
    state, _old_commit, files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    helper = "robot_learning/training/variant_helper.py"
    overlay = "robot_learning/variants/other/training/variant_helper.py"
    content = b"VALUE = 'selected overlay only'\n"
    (git_repository / overlay).write_bytes(content)
    repository.git("add", "--", overlay)
    repository.git("commit", "--quiet", "-m", "record overlay-only helper")
    parent = repository.git("rev-parse", "HEAD").strip()
    state.update(
        campaign_phase="recipe_development" if mode != "inquiry" else "research",
        recipe_development=None,
        pi_checkpoint=None,
        scientific_session={"id": "S2", "kind": "recipe_development"},
    )
    if mode == "skipped":
        state["recipe_phase"] = "skipped"
    candidate = state["candidates"]["T1:checkpoint-10"]
    candidate.update(
        name="other-checkpoint-10",
        scientific_commit=parent,
        parameters={"training": {"n_envs": 4}},
    )
    artifact = git_repository / candidate["artifact"]
    for filename in {*repository.ARTIFACT_FILES, *repository.INFERENCE_ARTIFACT_FILES}:
        (artifact / filename).write_bytes(b"recorded candidate artifact")
    candidate["fingerprint"] = repository.artifact_fingerprint(artifact)
    state["operation_events"] = [
        {"id": "T1", "kind": "training", "request": {"variants": [{"label": "other"}]}}
    ]
    parameters_path = "robot_learning/training/current_params.json"
    request = {
        "candidate": candidate["id"],
        "reason": "Restore the selected recorded variant.",
    }
    assert not (git_repository / helper).exists()
    assert not repository.tracked_at_commit(parent, helper)
    if mode != "isolated":
        plan = protocol.plan_recipe_restore(request, state)
        assert recipe_development._variant_paths(state, plan) is None
        assert helper not in plan["restore"]
        assert not (git_repository / helper).exists()
        assert (git_repository / parameters_path).read_bytes() == files[parameters_path]
        return
    plan = protocol.plan_recipe_restore(request, state)
    assert helper in plan["restore"]
    assert parameters_path in plan["restore"]
    assert "robot_learning/training/reward.py" in plan["restore"]
    assert not plan["remove_created"]
    assert set(plan) == {
        "parent",
        "restore",
        "remove_created",
        "candidate_id",
        "parameters",
        "session_id",
    }
    assert recipe_development.restore_variant(state, plan)
    assert recipe_development.variant_matches(state, plan)
    assert (git_repository / helper).read_bytes() == content
    assert (
        json.loads((git_repository / parameters_path).read_text())
        == candidate["parameters"]
    )
    assert (git_repository / "robot_learning/__init__.py").read_bytes() == files[
        "robot_learning/__init__.py"
    ]


@pytest.mark.parametrize(
    "protected",
    [
        "robot_learning/__init__.py",
        "robot_learning/scenario/__init__.py",
        "robot_learning/variants/other/__init__.py",
        "robot_learning/variants/other/scenario/__init__.py",
        "robot_learning/variants/other/SCENARIO/__INIT__.py",
    ],
)
def test_overlay_restore_rejects_protected_initializer_aliases(
    git_repository, monkeypatch, protected
):
    state, _old_commit, files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    state.update(
        campaign_phase="recipe_development",
        recipe_development=None,
        pi_checkpoint=None,
        scientific_session={"id": "S2", "kind": "recipe_development"},
    )
    candidate = state["candidates"]["T1:checkpoint-10"]
    artifact = git_repository / candidate["artifact"]
    for filename in {*repository.ARTIFACT_FILES, *repository.INFERENCE_ARTIFACT_FILES}:
        (artifact / filename).write_bytes(b"recorded candidate artifact")
    candidate["fingerprint"] = repository.artifact_fingerprint(artifact)
    with pytest.raises(ValueError, match="requires candidate and reason"):
        protocol.plan_recipe_restore(
            {
                "candidate": "T1:checkpoint-10",
                "reason": "Restore selected source.",
                "paths": [protected, "robot_learning/training/current_params.json"],
            },
            state,
        )
    assert (git_repository / "robot_learning/__init__.py").read_bytes() == files[
        "robot_learning/__init__.py"
    ]


@pytest.mark.parametrize(
    "queue_gap",
    [
        "none",
        "missing",
        "previous",
        "interrupted",
        "interrupted_launcher",
        "different_pending",
    ],
)
def test_isolated_checkpoint_finalizes_before_delivery_and_startup_continues_ids(
    git_repository, monkeypatch, queue_gap
):
    state, old_commit, _files, archive = _development_delivery(
        git_repository, monkeypatch
    )
    request = {
        key: value
        for key, value in state["recipe_development"].items()
        if key not in {"scientific_commit", "session_id", "inquiry_id"}
    }
    state.update(
        campaign_phase="recipe_development",
        recipe_development=None,
        pi_checkpoint=None,
        operation_events=[],
    )
    state["counters"].update(session=0, event=0)
    repository.start_scientific_session(
        state,
        kind="recipe_development",
        objective="Select the complete recipe.",
        backend_adapter="copilot",
        backend_model="model",
        backend_reasoning="high",
    )
    _complete_candidate(git_repository, state)
    repository.write_state(state)
    monkeypatch.setattr(
        run_experiment, "_load_experiment_config", lambda: {"training": {"n_envs": 1}}
    )
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *_args, **_kwargs: pytest.fail("delivery must not train"),
    )
    try:
        run_experiment.accept_operation({"checkpoint": request}, state)
        original_commit = repository.commit_runner_memory
        marker_path = paths.recipe_handoff_directory(git_repository) / "handoff.json"

        def interrupt_after_finalization(message):
            result = original_commit(message)
            if message.startswith("finalize "):
                raise OSError("interrupted after finalization commit")
            return result

        interrupted = queue_gap in {
            "interrupted",
            "interrupted_launcher",
            "different_pending",
        }
        if interrupted:
            monkeypatch.setattr(
                repository, "commit_runner_memory", interrupt_after_finalization
            )
            with pytest.raises(OSError, match="after finalization commit"):
                run_experiment.execute_pending_operation()
            assert (
                repository.read_state()["pending_operation"]["progress"] == "completed"
            )
            assert repository.read_committed_state("HEAD")["pending_operation"] is None
            monkeypatch.setattr(
                repository,
                "commit_runner_memory",
                lambda *_args: pytest.fail(
                    "already finalized checkpoint must not commit"
                ),
            )
        else:
            assert run_experiment.execute_pending_operation() == 0
        finalized_head = repository.git("rev-parse", "HEAD").strip()
        if queue_gap == "different_pending":
            different = repository.read_state()
            different["pending_operation"]["id"] = "E2"
            repository.write_state(different)
            state_bytes = paths.STATE_PATH.read_bytes()
            marker_bytes = marker_path.read_bytes()
            request_bytes = paths.OPERATION_REQUEST_PATH.read_bytes()
            with pytest.raises(RuntimeError, match="fully finalized"):
                recipe_development.deliver()
            assert paths.STATE_PATH.read_bytes() == state_bytes
            assert marker_path.read_bytes() == marker_bytes
            assert paths.OPERATION_REQUEST_PATH.read_bytes() == request_bytes
            assert repository.git("rev-parse", "HEAD").strip() == finalized_head
            assert not archive.exists()
            return
        if queue_gap == "missing":
            marker_path.unlink()
        elif queue_gap == "previous":
            marker = json.loads(marker_path.read_text())
            marker.update(
                campaign_id="previous-campaign",
                stage="published",
                parameters={"training": {"n_envs": 99}},
            )
            marker_path.write_text(json.dumps(marker), encoding="utf-8")
        assert not archive.exists()
        completed = repository.load_state(allow_missing_artifact=True)
        assert (completed["pending_operation"] is not None) == interrupted
        with pytest.raises(ValueError, match="delivery must finish"):
            repository.start_scientific_session(
                completed,
                kind="startup",
                objective="Start fresh.",
                backend_adapter="copilot",
                backend_model="model",
                backend_reasoning="high",
            )
        final_session = git_repository / ".copilot/session-state/development/final.json"
        final_session.write_bytes(b"final backend session record")
        if queue_gap == "interrupted_launcher":
            from runner.launcher import campaign
            from runner.launcher.options import PhaseBackend

            commands = []

            def runner(*arguments):
                assert archive.exists()
                assert repository.read_state()["pending_operation"] is None
                commands.append(arguments[0])
                return SimpleNamespace(exit_code=0)

            campaign.prepare(
                SimpleNamespace(
                    options=SimpleNamespace(
                        campaign_root=git_repository,
                        session=lambda _kind: PhaseBackend("new-model", "low"),
                        max_inquiries_explicit=True,
                        max_inquiries=7,
                    ),
                    recipe_delivery=recipe_development.deliver,
                    runner=SimpleNamespace(runner=runner),
                    events=SimpleNamespace(status=lambda *_args, **_kwargs: None),
                )
            )
            assert commands == [
                "--validate-session-backend",
                "--synchronize-max-inquiries",
            ]
        else:
            assert recipe_development.deliver()
        assert json.loads(marker_path.read_text())["development_head"] == finalized_head
        fresh = repository.load_state(allow_missing_artifact=True)
        archived_state = json.loads(
            (archive / "runner/state/research_state.json").read_text(encoding="utf-8")
        )
        assert archived_state["pending_operation"] is None
        assert archived_state["recipe_development"] == archived_state["pi_checkpoint"]
        assert archived_state["operation_events"][0]["status"] == "completed"
        assert not (archive / "pi_workspace/operation_request.json").exists()
        assert (
            archive / ".copilot/session-state/development/final.json"
        ).read_bytes() == b"final backend session record"
        assert not (git_repository / ".copilot").exists()
        assert set(fresh["candidates"]) == {"T1:checkpoint-10"}
        assert json.loads(
            (git_repository / "robot_learning/training/current_params.json").read_text()
        ) == {"training": {"n_envs": 1}}
        session = repository.start_scientific_session(
            fresh,
            kind="startup",
            objective="Start fresh from the recipe.",
            backend_adapter="copilot",
            backend_model="model",
            backend_reasoning="high",
        )
        assert session["id"] == "S2"
        assert session["scientific_parent_commit"] != old_commit
        assert fresh["counters"]["event"] == archived_state["counters"]["event"]
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_development_checkpoint_requires_the_best_known_candidate_recipe(
    git_repository, monkeypatch
):
    state, _old_commit, _files, _archive = _development_delivery(
        git_repository, monkeypatch
    )
    request = {
        key: value
        for key, value in state["recipe_development"].items()
        if key not in {"scientific_commit", "session_id", "inquiry_id"}
    }
    state.update(
        campaign_phase="recipe_development",
        recipe_development=None,
        pi_checkpoint=None,
        operation_events=[],
    )
    state["counters"].update(session=0, event=0)
    repository.start_scientific_session(
        state,
        kind="recipe_development",
        objective="Select the complete recipe.",
        backend_adapter="copilot",
        backend_model="model",
        backend_reasoning="high",
    )
    repository.write_state(state)
    monkeypatch.setattr(
        run_experiment, "_load_experiment_config", lambda: {"training": {"n_envs": 1}}
    )
    reward = git_repository / "robot_learning/training/reward.py"
    try:
        with pytest.raises(ValueError, match="best-known candidate"):
            run_experiment.accept_operation({"checkpoint": request}, state)
        _complete_candidate(git_repository, state)
        repository.write_state(state)
        reward.write_bytes(b"VALUE = 'changed after training'\n")
        with pytest.raises(ValueError, match="differs from the recipe"):
            run_experiment.accept_operation({"checkpoint": request}, state)
        reward.write_bytes(b"VALUE = 'chosen'\n")
        accepted = run_experiment.accept_operation({"checkpoint": request}, state)
        assert accepted["kind"] == "checkpoint"
    finally:
        shutil.rmtree(
            paths.recipe_handoff_directory(git_repository), onerror=_remove_readonly
        )


def test_campaign_memory_publication_excludes_science_and_local_artifacts(
    git_repository, monkeypatch
):
    from tools.initialize_campaign import CAMPAIGN_GITIGNORE

    root = git_repository
    (root / ".gitignore").write_text(CAMPAIGN_GITIGNORE, encoding="utf-8")
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "initial campaign")
    parent = repository.git("rev-parse", "HEAD").strip()
    monkeypatch.setattr(paths, "SPLIT", True)
    memory = [
        "runner/state/research_state.json",
        "campaigns/results.jsonl",
        "campaigns/EXPERIMENTS.md",
        "pi_workspace/scientific_model.md",
        "campaigns/checkpoints/candidates/campaign-one/t1/checkpoint-10/model.zip",
        "campaigns/checkpoints/candidates/campaign-one/t1/checkpoint-10/artifact.json",
        "campaigns/checkpoints/candidates/campaign-one/t1/checkpoint-10/policy_runtime.pkl",
        "campaigns/checkpoints/retained/campaign-one/best/model.zip",
    ]
    science = [
        "robot_learning/training/reward.py",
        "robot_learning/lab/diagnostic.py",
    ]
    local_artifacts = [
        "campaigns/evaluations/campaign-one/panel.json",
        "campaigns/training_logs/campaign-one/t1-attempt-1.log",
    ]
    for relative in memory + science + local_artifacts:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("output\n", encoding="utf-8")

    delta = repository.scientific_delta(parent)
    protocol.validate_research_delta_ownership(delta)
    assert delta == ["robot_learning/training/reward.py"]
    assert set(repository.changed_runner_memory()) == set(memory)
    assert repository.commit_runner_memory("complete operation")
    committed = repository.committed_change_paths(parent)
    assert set(committed) == set(memory)
    assert set(repository.status_paths((".",))) == set(science)
    assert all((root / relative).is_file() for relative in local_artifacts)

    unexpected = "campaigns/unclassified.py"
    (root / unexpected).write_text("not Runner output\n", encoding="utf-8")
    with pytest.raises(ValueError, match="human-owned or unclassified"):
        protocol.validate_research_delta_ownership(repository.scientific_delta(parent))


def test_large_publication_commits_only_requested_paths(git_repository):
    root = git_repository
    for name in ("unrelated.txt", "literal-a.txt", "obsolete[ab].txt"):
        (root / name).write_text("original", encoding="utf-8")
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "baseline")
    (root / "unrelated.txt").write_text("unrelated staged edit", encoding="utf-8")
    (root / "literal-a.txt").write_text("unrelated unstaged edit", encoding="utf-8")
    repository.git("add", "--", "unrelated.txt")
    (root / "obsolete[ab].txt").unlink()
    scope = [
        "obsolete[ab].txt",
        "literal-[ab].txt",
        "space name.txt",
        "unicode-\u00e9.txt",
    ]
    for name in scope[1:]:
        (root / name).write_text("requested", encoding="utf-8")
    for index in range(400):
        name = f"checkpoint-{index:04d}-{'x' * 80}.json"
        (root / name).write_text("{}", encoding="utf-8")
        scope.append(name)
    expanded = subprocess.list2cmdline(["git", "add", "-A", "--", *scope])
    assert len(expanded.encode("utf-16-le")) // 2 + 1 > (
        repository.WINDOWS_COMMAND_LINE_LIMIT
    )

    assert repository.commit_paths("scoped publication", scope)

    committed = set(
        repository.git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "HEAD")
        .rstrip("\0")
        .split("\0")
    )
    assert committed == set(scope)
    assert repository.git("show", "HEAD:unrelated.txt") == "original"
    assert repository.git("show", "HEAD:literal-a.txt") == "original"
    assert repository.git("diff", "--cached", "--name-only").strip() == "unrelated.txt"
    assert not repository.commit_paths("unchanged scope", scope[1:])
    assert repository.git("log", "-1", "--format=%s").strip() == "scoped publication"


def test_publication_accepts_a_literal_directory_scope(git_repository):
    root = git_repository
    directory = root / "bundle[1]"
    directory.mkdir()
    (directory / "model.zip").write_bytes(b"model")
    (root / "outside.txt").write_text("outside", encoding="utf-8")

    assert repository.commit_paths("directory publication", ["bundle[1]"])
    assert repository.git("ls-tree", "-r", "--name-only", "HEAD").strip() == (
        "bundle[1]/model.zip"
    )
    assert repository.git("status", "--porcelain", "--", "outside.txt").strip() == (
        "?? outside.txt"
    )


def test_batched_head_check_compares_each_worktree_file_with_head(git_repository):
    root = git_repository
    (root / "contracts").mkdir()
    (root / "contracts" / "a.md").write_text("a", encoding="utf-8")
    (root / "contracts" / "b[1].md").write_text("b", encoding="utf-8")
    repository.git("add", "-A")
    repository.git("commit", "--quiet", "-m", "base")
    trusted = ["contracts/a.md", "contracts/b[1].md"]
    repository.require_paths_at_head(trusted)

    (root / "contracts" / "b[1].md").write_text("changed", encoding="utf-8")
    with pytest.raises(
        ValueError, match=r"does not contain the current contracts/b\[1\]\.md"
    ):
        repository.require_paths_at_head(trusted)
    (root / "contracts" / "b[1].md").write_text("b", encoding="utf-8")

    (root / "contracts" / "new.md").write_text("new", encoding="utf-8")
    with pytest.raises(ValueError, match="does not contain contracts/new.md"):
        repository.require_paths_at_head([*trusted, "contracts/new.md"])

    (root / "contracts" / "a.md").unlink()
    with pytest.raises(ValueError, match="missing from the worktree: contracts/a.md"):
        repository.require_paths_at_head(trusted)


def test_staged_scope_checks_respect_windows_command_limit(monkeypatch):
    scope = [f"artifact {index:04d} {'x' * 80}-\U0001f680.json" for index in range(400)]
    observed: list[str] = []

    def git(*args):
        command = subprocess.list2cmdline(["git", *args])
        assert len(command.encode("utf-16-le")) // 2 + 1 <= (
            repository.WINDOWS_COMMAND_LINE_LIMIT
        )
        assert args[:6] == (
            "--literal-pathspecs",
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--",
        )
        observed.extend(args[6:])
        return ""

    monkeypatch.setattr(repository, "git", git)
    assert not repository.has_staged_changes(scope)
    assert observed == scope


def test_staged_scope_check_finds_changes_in_later_batch(monkeypatch):
    scope = [f"artifact-{index:04d}-{'x' * 80}.json" for index in range(400)]

    def git(*args):
        return f"{scope[-1]}\0" if scope[-1] in args[6:] else ""

    monkeypatch.setattr(repository, "git", git)
    assert repository.has_staged_changes(scope)


def test_git_pathspec_batches_reject_an_unrepresentable_single_path():
    with pytest.raises(ValueError, match="process-command limit"):
        list(
            repository._git_pathspec_batches(
                ("diff", "--"), ["x" * repository.WINDOWS_COMMAND_LINE_LIMIT]
            )
        )


@pytest.mark.parametrize("fail", [False, True])
def test_pathspec_file_preserves_literal_paths_and_is_removed(monkeypatch, fail):
    scope = ["literal[ab].txt", "space name.txt", "unicode-\u00e9.txt"]
    observed: list[Path] = []

    def git(*args):
        assert args[:3] == ("--literal-pathspecs", "add", "-A")
        assert args[-1] == "--pathspec-file-nul"
        path = Path(args[-2].removeprefix("--pathspec-from-file="))
        observed.append(path)
        assert path.read_bytes() == b"".join(
            name.encode("utf-8") + b"\0" for name in scope
        )
        if fail:
            raise RuntimeError("injected Git failure")
        return ""

    monkeypatch.setattr(repository, "git", git)
    if fail:
        with pytest.raises(RuntimeError, match="injected Git failure"):
            repository.git_with_pathspecs("add", "-A", scope=scope)
    else:
        repository.git_with_pathspecs("add", "-A", scope=scope)
    assert observed
    assert all(not path.exists() for path in observed)


@pytest.mark.parametrize(
    "failure",
    [
        "remote: Internal Server Error",
        "remote: fatal error in commit_refs",
        "fatal: The requested URL returned error: 500",
        "error: RPC failed; HTTP 502 curl 22",
        "fatal: The requested URL returned error: 503",
        "fatal: The requested URL returned error: 504",
    ],
)
def test_push_retries_transient_failure_with_fixed_commit_and_branch(
    monkeypatch, failure
):
    commit = "a" * 40
    destination = "refs/heads/research"
    pushes = []
    waits = []
    resolutions = []
    head = {"commit": commit, "branch": destination}

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            resolutions.append(args)
            return head["commit"] + "\n"
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            resolutions.append(args)
            return head["branch"] + "\n"
        pushes.append(args)
        if len(pushes) == 1:
            raise RuntimeError(failure)
        return ""

    def sleep(seconds):
        waits.append(seconds)
        head.update(commit="b" * 40, branch="refs/heads/different")

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", sleep)

    repository.push_head()

    assert pushes == [("push", "origin", f"{commit}:{destination}")] * 2
    assert waits == [60]
    assert resolutions == [
        ("rev-parse", "HEAD"),
        ("symbolic-ref", "--quiet", "HEAD"),
    ]


@pytest.mark.parametrize("failures", [0, 3, 4])
def test_push_retry_limit_and_error_preservation(monkeypatch, failures):
    pushes = []
    waits = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        if len(pushes) <= failures:
            raise RuntimeError(f"remote: Internal Server Error\nrequest-{len(pushes)}")
        return ""

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", waits.append)

    if failures == 4:
        with pytest.raises(repository.PublicationError, match="request-4") as raised:
            repository.push_head()
        assert isinstance(raised.value.__cause__, RuntimeError)
    else:
        repository.push_head()

    assert len(pushes) == min(failures + 1, 4)
    assert waits == [60] * min(failures, 3)


@pytest.mark.parametrize(
    "failure",
    [
        "fatal: Authentication failed",
        "remote: GH001: Large files detected",
        "rejected (non-fast-forward)",
        "rejected (fetch first)",
        "remote: GH013: Repository rule violations found",
        "fatal: Could not resolve host: github.com",
        "remote: Internal Server Error\nfatal: Authentication failed",
    ],
)
def test_push_does_not_retry_permanent_or_unknown_errors(monkeypatch, failure):
    pushes = []
    waits = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        raise RuntimeError(failure)

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", waits.append)

    with pytest.raises(repository.PublicationError) as raised:
        repository.push_head()

    assert failure in str(raised.value)
    assert len(pushes) == 1
    assert waits == []


def test_push_stops_retrying_when_rejection_becomes_permanent(monkeypatch):
    failures = iter(
        [
            RuntimeError("remote: Internal Server Error"),
            RuntimeError("rejected (non-fast-forward)"),
        ]
    )
    pushes = []
    waits = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        raise next(failures)

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", waits.append)

    with pytest.raises(repository.PublicationError, match="non-fast-forward"):
        repository.push_head()

    assert len(pushes) == 2
    assert waits == [60]


def test_push_retry_wait_is_interruptible(monkeypatch):
    pushes = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        raise RuntimeError("remote: Internal Server Error")

    def sleep(seconds):
        assert seconds == 60
        raise KeyboardInterrupt

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", sleep)

    with pytest.raises(KeyboardInterrupt):
        repository.push_head()

    assert len(pushes) == 1
