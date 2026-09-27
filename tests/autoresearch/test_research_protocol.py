"""Evidence integrity and instrument invocation contracts."""

from __future__ import annotations

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


def test_paired_comparison_uses_shared_episode_identities():
    comparison = paired_comparison(
        [_evaluation(3000, [True] * 6)],
        [_evaluation(3000, [False] * 6)],
    )
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


def _frozen_plan(candidate: Path, reference: Path) -> list[dict]:
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
                    "candidate_artifacts": [candidate.name],
                    "candidate_artifact_fingerprints": {
                        candidate.name: repository.file_fingerprint(candidate)
                    },
                    "reference_artifacts": [reference.name],
                    "reference_artifact_fingerprints": {
                        reference.name: repository.file_fingerprint(reference)
                    },
                }
            ],
        }
    ]


def test_frozen_paired_evidence_preserves_artifact_identity(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    candidate = tmp_path / "candidate.json"
    reference = tmp_path / "reference.json"
    _write_panel(candidate, [(0, 10, True), (1, 11, False)])
    _write_panel(reference, [(0, 10, False), (1, 11, False)])
    request = {
        "paired_comparisons": [{"candidate": "candidate", "reference": "working"}]
    }

    plan = _frozen_plan(candidate, reference)
    comparison = requested_paired_comparisons(request, {}, evidence_plan=plan)[0]

    assert comparison["episodes"] == 2
    assert comparison["candidate_wins"] == 1
    reference.write_text(json.dumps(_evaluation(10, [True, True])), encoding="utf-8")
    with pytest.raises(ValueError, match="content changed after acceptance"):
        requested_paired_comparisons(request, {}, evidence_plan=plan)


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
        ("robot_learning/scenario/__pycache__/evaluation.cpython-313.pyc", False),
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


def test_measurement_artifact_fingerprint_detects_replacement(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    artifact = tmp_path / "measurement.json"
    artifact.write_text(json.dumps(_evaluation(10, [True, False])), encoding="utf-8")
    record = {
        "episodes": 2,
        "seed": 10,
        "evaluation_artifact": artifact.name,
        "evaluation_artifact_fingerprint": repository.file_fingerprint(artifact),
    }
    assert len(repository.measurement_evidence(record)["episode_results"]) == 2
    artifact.write_text(json.dumps(_evaluation(10, [False, False])), encoding="utf-8")
    with pytest.raises(ValueError, match="content changed after recording"):
        repository.measurement_evidence(record)


def test_measurement_protocol_validates_invocation_not_scientific_content():
    protocol.validate_measurement_request(
        {
            "description": "Inspect the selected model.",
            "rationale": "The PI will interpret the factual result.",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "candidate",
                    "episodes": 2,
                    "seed": 100,
                }
            ],
        }
    )


def test_training_protocol_requires_explicit_mechanical_inputs():
    request = {
        "initialization": "fresh",
        "seed": 7,
        "steps": 100,
        "description": "Train the current recipe.",
        "rationale": "Observe its learning dynamics.",
    }
    protocol.validate_training_request(request)
    with pytest.raises(ValueError, match="parent"):
        protocol.validate_training_request({**request, "initialization": "transfer"})
