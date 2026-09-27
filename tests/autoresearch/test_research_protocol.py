"""Focused tests for evidence integrity and inquiry-centered proposal contracts."""

import json
from pathlib import Path

import pytest

from research import runner_protocol as protocol
from research import runner_repository as repository
from research.runner_execution import requested_paired_comparisons
from robot_learning.paired_evidence import paired_comparison as paired_counts
from robot_learning.scenario.evaluation import (
    summarize_research_evaluations as summarize_evaluations,
)
from robot_learning.training.comparison import exact_mcnemar_pvalue, paired_comparison


def _evaluation(seed: int, outcomes: list[bool]) -> dict:
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "success_percent": 100 * sum(outcomes) / len(outcomes),
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": outcome,
                "steps": 100,
                "reward_total": 1.0,
            }
            for episode, outcome in enumerate(outcomes)
        ],
    }


def _campaign_state() -> dict:
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
    state["active_inquiry"] = {
        "id": 1,
        "question": "What method can improve robust control?",
        "scope": "Learning dynamics and resulting behavior.",
        "closure_condition": "Resolve whether to promote, retain, or abandon.",
        "status": "active",
        "session_id": "session",
        "reframes": [],
    }
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can method A improve robust control?",
        "rationale": "It provides a distinct learning path.",
        "lifecycle": "development",
        "base_scientific_commit": "a" * 40,
        "current_lineage": None,
        "iterations": [],
        "resolution": None,
    }
    return state


def _investigation(source: str = "evidence.txt") -> dict:
    return {
        "evidence": [{"source": source, "observation": "Learning slowed."}],
        "objective_link": "The failure affects the campaign objective.",
        "initialization_reason": "Fresh initialization isolates this method.",
        "rationale": "The run resolves a method-level uncertainty.",
        "expected_observation": "Learning progress changes.",
        "open_question": "Does the method alter learning progress?",
    }


def _measurement(candidate: str, seed: int = 1000) -> dict:
    return {
        "instrument": "research_evaluation",
        "candidate": candidate,
        "episodes": 2,
        "seed": seed,
        "selection": "This model answers the current inquiry question.",
        "omitted_alternative": None,
    }


def test_paired_comparison_uses_shared_episode_identities():
    candidate = [_evaluation(3000, [True] * 6)]
    reference = [_evaluation(3000, [False] * 6)]
    comparison = paired_comparison(candidate, reference)
    assert comparison["candidate_wins"] == 6
    assert comparison["reference_wins"] == 0
    assert comparison["exact_p_value"] == pytest.approx(0.03125)


def test_paired_comparison_rejects_panels_without_shared_episodes():
    with pytest.raises(ValueError, match="do not cover identical episodes"):
        paired_comparison(
            [_evaluation(3000, [True, False])],
            [_evaluation(4000, [True, False])],
        )


def test_protected_paired_counts_exclude_the_statistic():
    counts = paired_counts(
        [_evaluation(3000, [True, True])],
        [_evaluation(3000, [False, False])],
    )
    assert counts["candidate_wins"] == 2
    assert counts["episodes"] == 2
    assert "exact_p_value" not in counts
    assert exact_mcnemar_pvalue(0, 0) == 1.0


def test_evaluation_summary_does_not_invent_scenario_diagnostics():
    summary = summarize_evaluations(
        [_evaluation(3000, [True, False]), _evaluation(4000, [True] * 8)]
    )
    assert summary["episodes"] == 10
    assert summary["seed_count"] == 2
    assert summary["pooled_success_percent"] == pytest.approx(90.0)
    assert "failure_diagnostics" not in summary


def test_paired_comparison_aligns_outcomes_by_episode_identity():
    candidate = _evaluation(3000, [True, True, False, False])
    reference = _evaluation(3000, [True, True, False, False])
    reference["episode_results"].reverse()

    comparison = paired_comparison([candidate], [reference])

    assert comparison["episodes"] == 4
    assert comparison["discordant_episodes"] == 0


def _write_panel(path: Path, identities: list[tuple[int, int, bool]]) -> None:
    path.write_text(
        json.dumps(
            {
                "episodes": len(identities),
                "seed": 10,
                "episode_results": [
                    {"episode": episode, "episode_seed": seed, "success": success}
                    for episode, seed, success in identities
                ],
            }
        ),
        encoding="utf-8",
    )


def _frozen_plan(candidate_paths: list[Path], reference_paths: list[Path]) -> list:
    def artifacts(paths: list[Path]) -> tuple[list[str], dict[str, str]]:
        names = [path.name for path in paths]
        return names, {path.name: repository.file_fingerprint(path) for path in paths}

    candidates, candidate_fingerprints = artifacts(candidate_paths)
    references, reference_fingerprints = artifacts(reference_paths)
    return [
        {
            "candidate": "candidate",
            "reference": "working",
            "candidate_model_fingerprint": "candidate-model",
            "reference_model_fingerprint": "working-model",
            "panels": [
                {
                    "instrument": "research_evaluation",
                    "episodes": 2,
                    "seed": 10,
                    "evaluation_semantics": "semantics",
                    "candidate_artifacts": candidates,
                    "candidate_artifact_fingerprints": candidate_fingerprints,
                    "reference_artifacts": references,
                    "reference_artifact_fingerprints": reference_fingerprints,
                }
            ],
        }
    ]


PAIRED_REQUEST = {
    "paired_comparisons": [{"candidate": "candidate", "reference": "working"}]
}


def test_frozen_paired_evidence_pairs_only_shared_episode_identities(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    candidate = tmp_path / "candidate.json"
    reference = tmp_path / "reference.json"
    _write_panel(candidate, [(0, 10, True), (1, 11, False)])
    _write_panel(reference, [(0, 10, False), (1, 12, True)])

    comparison = requested_paired_comparisons(
        PAIRED_REQUEST, {}, evidence_plan=_frozen_plan([candidate], [reference])
    )[0]

    assert comparison["episodes"] == 1
    assert comparison["candidate_wins"] == 1
    panel = comparison["panels"][0]
    assert panel["shared_episode_seeds"] == [10]
    assert (panel["candidate_episodes"], panel["reference_episodes"]) == (2, 2)
    assert comparison["candidate_model_fingerprint"] == "candidate-model"


@pytest.mark.parametrize(
    ("corruption", "message"),
    [
        ("conflicting_duplicate", "conflicting deterministic measurements"),
        ("repeated_identity", "repeats an episode identity"),
        ("replaced_artifact", "content changed after acceptance"),
        ("changed_shared_identities", "shared episode identities changed"),
    ],
)
def test_frozen_paired_evidence_rejects_corrupted_panels(
    monkeypatch, tmp_path, corruption, message
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    candidate = tmp_path / "candidate.json"
    duplicate = tmp_path / "candidate-duplicate.json"
    reference = tmp_path / "reference.json"
    _write_panel(candidate, [(0, 10, True), (1, 11, False)])
    _write_panel(duplicate, [(0, 10, False), (1, 11, False)])
    _write_panel(reference, [(0, 10, False), (1, 11, False)])
    if corruption == "repeated_identity":
        _write_panel(candidate, [(0, 10, True), (0, 10, False)])
    candidates = (
        [candidate, duplicate] if corruption == "conflicting_duplicate" else [candidate]
    )
    plan = _frozen_plan(candidates, [reference])
    if corruption == "replaced_artifact":
        _write_panel(reference, [(0, 10, True), (1, 11, True)])
    if corruption == "changed_shared_identities":
        plan[0]["panels"][0]["shared_episode_seeds"] = [10]

    with pytest.raises(ValueError, match=message):
        requested_paired_comparisons(PAIRED_REQUEST, {}, evidence_plan=plan)


SEMANTICS_TREE = (
    "robot_learning/scenario/__init__.py",
    "robot_learning/scenario/evaluation.py",
    "robot_learning/scenario/environment.py",
    "robot_learning/scenario/reward.py",
    "robot_learning/scenario/training_environment.py",
    "robot_learning/scenario/observations.py",
    "robot_learning/scenario/policy_io.py",
    "robot_learning/scenario/viewer.py",
    "robot_learning/scenario/progress.py",
    "robot_learning/scenario/final_benchmark.py",
    "robot_learning/scenario/task_reference.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/normalization.py",
    "research/build_research_brief.py",
    "run_research.ps1",
    *protocol.EVALUATION_RUNTIME_PATHS,
)


def _semantics_tree(root: Path) -> None:
    for relative in SEMANTICS_TREE:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("relative", "changes_identity"),
    [
        ("robot_learning/scenario/evaluation.py", True),
        ("robot_learning/scenario/environment.py", True),
        ("robot_learning/scenario/measurement_config.json", True),
        *[(relative, True) for relative in protocol.EVALUATION_RUNTIME_PATHS],
        ("robot_learning/scenario/reward.py", False),
        ("robot_learning/scenario/training_environment.py", False),
        ("robot_learning/scenario/observations.py", False),
        ("robot_learning/scenario/policy_io.py", False),
        ("robot_learning/training/algorithms.py", False),
        ("robot_learning/training/normalization.py", False),
        ("robot_learning/scenario/viewer.py", False),
        ("robot_learning/scenario/progress.py", False),
        ("robot_learning/scenario/final_benchmark.py", False),
        ("robot_learning/scenario/task_reference.py", False),
        ("robot_learning/scenario/__init__.py", False),
        ("robot_learning/scenario/__pycache__/evaluation.cpython-312.pyc", False),
        ("robot_learning/scenario/evaluation.py.tmp", False),
        ("robot_learning/scenario/.mypy_cache/state.json", False),
        ("research/build_research_brief.py", False),
        ("run_research.ps1", False),
    ],
)
def test_evaluation_semantics_cover_only_measurement_semantics(
    monkeypatch, tmp_path, relative, changes_identity
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    _semantics_tree(tmp_path)
    before = protocol.evaluation_semantics_fingerprint()
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("changed = True\n")

    assert (protocol.evaluation_semantics_fingerprint() != before) is changes_identity


def test_evaluation_semantics_track_added_renamed_and_deleted_files(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    _semantics_tree(tmp_path)
    original = protocol.evaluation_semantics_fingerprint()
    added = tmp_path / "robot_learning/scenario/instrument.py"
    added.write_text("probe = 1\n", encoding="utf-8")
    with_added = protocol.evaluation_semantics_fingerprint()
    renamed = added.rename(added.with_name("renamed_instrument.py"))
    with_renamed = protocol.evaluation_semantics_fingerprint()
    renamed.unlink()

    assert len({original, with_added, with_renamed}) == 3
    assert protocol.evaluation_semantics_fingerprint() == original


def _with_foreign_inquiry_reference(state: dict, reference: str) -> None:
    foreign_lineage = {"artifact": "lineage", "inquiry_id": 2}
    if reference in {"working_lineage", "best_known_lineage"}:
        state[reference] = foreign_lineage
    elif reference == "retained_lineages":
        state[reference] = [{"id": "alternative", **foreign_lineage}]
    elif reference == "active_method":
        state["active_method"]["inquiry_id"] = 2
    else:
        state["active_method"].update(
            lifecycle="abandoned",
            resolution={
                "action": "abandon",
                "outcome": "Abandoned.",
                "reason": "Another inquiry resolved it.",
                "inquiry_id": 2,
            },
        )


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("working_lineage", "cannot carry inquiry ownership"),
        ("best_known_lineage", "cannot carry inquiry ownership"),
        ("retained_lineages", "cannot carry inquiry ownership"),
        ("active_method", "must belong to the active inquiry"),
        ("method_resolution", "belongs to another inquiry"),
    ],
)
def test_state_rejects_cross_inquiry_lineage_references(reference, message):
    state = _campaign_state()
    repository.validate_research_state(state, allow_missing_artifact=True)
    _with_foreign_inquiry_reference(state, reference)

    with pytest.raises(ValueError, match=message):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_measurement_artifact_fingerprint_detects_replacement(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    artifact = tmp_path / "measurement.json"
    artifact.write_text(json.dumps(_evaluation(10, [True, False])), encoding="utf-8")
    record = {
        "episodes": 2,
        "seed": 10,
        "evaluation_semantics": "semantics",
        "evaluation_artifact": artifact.name,
        "evaluation_artifact_fingerprint": repository.file_fingerprint(artifact),
    }
    evidence = repository.measurement_evidence(record)
    assert [item["episode_seed"] for item in evidence["episode_results"]] == [10, 11]

    artifact.write_text(json.dumps(_evaluation(10, [False, False])), encoding="utf-8")
    with pytest.raises(ValueError, match="content changed after recording"):
        repository.measurement_evidence(record)


def test_evaluation_request_can_measure_an_active_method_without_comparison():
    request = {
        "question": "How does the method behave internally?",
        "reason": "Inspect learning without requiring an incumbent comparison.",
        "measurements": [_measurement("active_method")],
    }
    protocol.validate_evaluation_request(request)


def test_evaluation_request_limits_distinct_models():
    request = {
        "question": "Which models are informative?",
        "reason": "Bound the measurement round.",
        "measurements": [
            _measurement("one", 1000),
            _measurement("two", 2000),
            _measurement("three", 3000),
            _measurement("four", 4000),
        ],
    }
    with pytest.raises(ValueError, match="at most 3 distinct models"):
        protocol.validate_evaluation_request(request)


def test_investigation_design_accepts_prediction_or_open_question():
    predicted = _investigation()
    predicted.pop("open_question")
    predicted["predicted_behavioral_path"] = "Control should stabilize earlier."
    protocol.validate_investigation_design({"investigation_design": predicted})
    protocol.validate_investigation_design({"investigation_design": _investigation()})


def test_training_requires_matching_active_method(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("observed", encoding="utf-8")
    memory = tmp_path / "postmortems.md"
    memory.write_text(
        "## campaign / Scientific strategy\n\n"
        "**Current synthesis:** A current explanation.\n\n"
        "**Lessons and limits:** Evidence is limited.\n\n"
        "**Competing explanations:** Two mechanisms remain.\n\n"
        "**Decision frontier:** A further run distinguishes them.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", memory)
    state = _campaign_state()
    proposal = {
        "kind": "training",
        "method_id": "method-a",
        "initialization": "fresh",
        "change": "Change the method.",
        "investigation_design": _investigation(),
    }
    assert protocol.validate_proposal_against_state(proposal, state) == "training"

    proposal["method_id"] = "other"
    with pytest.raises(ValueError, match="must match active_method.id"):
        protocol.validate_proposal_against_state(proposal, state)
