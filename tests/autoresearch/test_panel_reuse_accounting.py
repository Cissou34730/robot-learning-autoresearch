"""Reuse accounting for selection-contaminated development panels.

Issue #57: identical research-panel reuse is permitted but must be accounted
for. A reused panel is reported with its reuse depth and a non-independence
qualifier, the contamination rule is stated in instrument-neutral terms, and a
lineage's selection exposure is surfaced so re-measurement on a panel it was
selected on is not read as independent confirmation.
"""

from pathlib import Path

from research import build_research_brief as brief
from research import runner_protocol as protocol

ROOT = Path(__file__).resolve().parents[2]


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
    text = "\n".join(
        brief._v4_measurement_rounds_section({}, prior_results, pending)
    )
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
    text = "\n".join(
        brief._v4_measurement_rounds_section({}, prior_results, pending)
    )
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


def test_selection_panels_are_recorded_on_a_newly_selected_lineage():
    pending = {
        "experiment": 2,
        "requested_evaluations": [
            {**_measurement("c1"), "instrument": "research_evaluation"},
            {
                **_measurement("c2", fingerprint="other"),
                "instrument": "research_evaluation",
            },
            {
                "candidate": "c1",
                "panel": "task-reference-v1",
                "episodes": 200,
                "seed": 1,
                "instrument": "task_reference",
            },
        ],
    }
    panels = protocol._selection_panels_for({}, pending, "fp")
    assert panels == [[100, 200]]


def test_selection_panels_preserve_prior_exposure_when_a_lineage_is_reused():
    source = {"selected_panels": [[100, 200]]}
    pending = {
        "experiment": 3,
        "requested_evaluations": [
            {**_measurement("c1", seed=500, episodes=200), "instrument": "research_evaluation"}
        ],
    }
    panels = protocol._selection_panels_for(source, pending, "fp")
    assert panels == [[100, 200], [500, 200]]


def test_instrument_documentation_states_the_rule_in_neutral_terms():
    instruments = " ".join(
        (ROOT / "research" / "instruments.md").read_text(encoding="utf-8").split()
    )
    program = " ".join(
        (ROOT / "research" / "program.md").read_text(encoding="utf-8").split()
    )

    # The rule is about reuse, not about one instrument.
    assert "Any panel reused during model selection" in instruments
    assert "identically reused research panel" in program
    assert "not independent held-out confirmation" in instruments
    assert "not independent held-out confirmation" in program
    # `task_reference` is named as the permanently reused case, not the cause.
    assert "permanently reused case" in instruments
    assert "permanently reused case" in program
