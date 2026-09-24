"""Reuse accounting for selection-contaminated development panels.

Issue #57: identical research-panel reuse is permitted but must be accounted
for. A reused panel is reported with its reuse depth and a non-independence
qualifier, the contamination rule is stated in instrument-neutral terms, and a
lineage's selection exposure is surfaced so re-measurement on a panel it was
selected on is not read as independent confirmation.
"""

import json
from pathlib import Path

import pytest

from research import build_research_brief as brief
from research import runner_protocol as protocol
from research import runner_repository as repository

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _redirect_research_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.LOG_PATH", tmp_path / "EXPERIMENTS.md")


def _measurement(
    candidate: str, *, seed: int = 100, episodes: int = 200, fingerprint: str = "fp"
) -> dict:
    return {
        "candidate": candidate,
        "seed": seed,
        "episodes": episodes,
        "model_fingerprint": fingerprint,
    }


def test_reused_panel_is_reported_with_reuse_depth_and_qualifier():
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [
                _measurement("old-a"),
                _measurement("old-b"),
            ],
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        _measurement("c1", seed=100, episodes=200),
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "(reused panel: 2 prior measurements on these episodes)" in text
    assert "not independent confirmation" in text


def test_reused_panel_reports_when_a_prior_use_preceded_its_selection():
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [_measurement("c1")],
            "closure_decision": {"continue_from": "c1"},
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [_measurement("c1")],
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "1 prior measurement on these episodes" in text
    assert "1 preceded a closure that selected this lineage" in text


def test_fresh_panel_keeps_the_new_panel_marker():
    pending = {
        "experiment": 1,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [_measurement("c1")],
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, [], pending))
    assert "(new panel)" in text
    assert "not independent confirmation" not in text


def test_lineage_selection_exposure_is_surfaced():
    lineage = {
        "candidate": "checkpoint-100352",
        "origin_experiment": 1,
        "training_steps": 100_352,
        "artifact": "research/checkpoints/retained/x/model.zip",
        "fingerprint": "fp",
        "scientific_commit": "abc",
        "parameters": {"algorithm": {"name": "ppo"}},
        "evaluation_artifacts": ["research/evaluations/x.json"],
        "selected_panels": [[100, 200]],
        "reason": "highest measured success",
    }
    text = "\n".join(brief._authoritative_lineage_lines("working", lineage))
    assert "Panels this lineage was selected on: episodes 100–299" in text
    assert "not independent confirmation" in text


def test_reused_panel_selection_is_associated_by_fingerprint_not_label():
    # The model was selected as `checkpoint-100352` and later measured as the
    # `working` role. Only the immutable fingerprint connects the two.
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [
                {
                    "candidate": "checkpoint-100352",
                    "seed": 100,
                    "episodes": 200,
                    "model_fingerprint": "F",
                }
            ],
            "closure_decision": {"continue_from": "checkpoint-100352"},
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "working",
                            "seed": 100,
                            "episodes": 200,
                            "model_fingerprint": "F",
                        }
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "1 prior measurement on these episodes" in text
    assert "1 preceded a closure that selected this lineage" in text


def test_reused_panel_selection_is_not_attributed_to_a_different_fingerprint():
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [
                {
                    "candidate": "checkpoint-100352",
                    "seed": 100,
                    "episodes": 200,
                    "model_fingerprint": "F",
                }
            ],
            "closure_decision": {"continue_from": "checkpoint-100352"},
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "working",
                            "seed": 100,
                            "episodes": 200,
                            "model_fingerprint": "G",
                        }
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "1 prior measurement on these episodes" in text
    assert "preceded a closure" not in text


def test_preparation_evaluations_count_as_prior_panel_uses():
    prior_results = [
        {
            "index": 1,
            "preparation_evaluations": [
                {
                    "candidate": "working",
                    "seed": 100,
                    "episodes": 200,
                    "model_fingerprint": "F",
                    "instrument": "research_evaluation",
                }
            ],
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "c1",
                            "seed": 100,
                            "episodes": 200,
                            "model_fingerprint": "F",
                        }
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "(reused panel: 1 prior measurement on these episodes)" in text


def test_reused_task_reference_result_carries_the_non_independence_context():
    prior_results = [
        {
            "index": 1,
            "task_reference_evaluations": [
                {
                    "candidate": "working",
                    "panel": "task-reference-v1",
                    "panel_version": 1,
                    "seed": 1,
                    "episodes": 200,
                    "model_fingerprint": "F",
                }
            ],
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "task_reference_evaluations": [
                        {
                            "candidate": "c1",
                            "panel": "task-reference-v1",
                            "panel_version": 1,
                            "seed": 1,
                            "episodes": 200,
                            "model_fingerprint": "G",
                        }
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "(reused panel: 1 prior measurement on this panel)" in text
    assert "not independent confirmation" in text


def test_reused_paired_comparison_carries_the_non_independence_context():
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [_measurement("old")],
        }
    ]
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "paired_comparisons": [
                        {
                            "candidate": "c1",
                            "reference": "working",
                            "candidate_wins": 3,
                            "reference_wins": 1,
                            "episodes": 200,
                            "panels": [{"seed": 100, "episodes": 200}],
                        }
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, prior_results, pending))
    assert "Reused panel context:" in text
    assert "not independent confirmation" in text


def test_selection_panels_record_both_instruments_with_identity():
    pending = {
        "experiment": 2,
        "requested_evaluations": [
            {**_measurement("c1"), "instrument": "research_evaluation"},
            {
                **_measurement("c2", seed=500, fingerprint="other"),
                "instrument": "research_evaluation",
            },
        ],
        "task_reference_evaluations": [
            {
                "candidate": "c1",
                "panel": "task-reference-v1",
                "panel_version": 1,
                "episodes": 200,
                "seed": 1,
                "instrument": "task_reference",
            }
        ],
    }
    panels = protocol._selection_panels_for({}, pending, "fp")
    assert {
        "instrument": "research_evaluation",
        "seed": 100,
        "episodes": 200,
    } in panels
    assert {
        "instrument": "task_reference",
        "panel": "task-reference-v1",
        "panel_version": 1,
        "seed": 1,
        "episodes": 200,
    } in panels
    # The measurement of a different model on another panel is not exposure.
    assert all(panel.get("seed") != 500 for panel in panels)


def test_selection_panels_preserve_prior_exposure_when_a_lineage_is_reused():
    source = {"selected_panels": [[100, 200]]}
    pending = {
        "experiment": 3,
        "requested_evaluations": [
            {
                **_measurement("c1", seed=500, episodes=200),
                "instrument": "research_evaluation",
            }
        ],
    }
    panels = protocol._selection_panels_for(source, pending, "fp")
    assert panels == [
        {"instrument": "research_evaluation", "seed": 100, "episodes": 200},
        {"instrument": "research_evaluation", "seed": 500, "episodes": 200},
    ]


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
        "parameters": {"algorithm": {"name": "ppo"}},
        "scientific_commit": "a" * 40,
        "training_steps": steps,
        "evaluation_artifacts": [],
        "selected_panels": [],
        "reason": f"Preserve {path.name}.",
    }


def test_explicit_best_known_reselection_refreshes_selection_exposure(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    incumbent = _artifact(tmp_path / "incumbent", "incumbent")
    existing = _lineage(incumbent, steps=10_000)
    fingerprint = existing["fingerprint"]
    state = {
        "schema_version": 4,
        "working_lineage": dict(existing),
        "best_known_lineage": dict(existing),
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 2,
            "candidates": [],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
            "requested_evaluations": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "best_known",
                    "seed": 700,
                    "episodes": 200,
                    "model_fingerprint": fingerprint,
                }
            ],
        },
    }

    plan = protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 2,
                "continue_from": "best_known",
                "reason": "Keep the incumbent.",
                "code": {"action": "keep", "reason": "No code change."},
                "best_known": {
                    "candidate": "best_known",
                    "reason": "Confirm the incumbent.",
                },
            }
        },
        state,
    )

    assert plan["best_known_record"]["selected_panels"] == [
        {"instrument": "research_evaluation", "seed": 700, "episodes": 200}
    ]
