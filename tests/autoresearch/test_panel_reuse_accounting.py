"""Panel reuse remains explicit in evidence while the brief stays generic."""

from research import build_research_brief as brief
from research import runner_protocol as protocol


def _measurement(
    candidate: str,
    *,
    seed: int = 100,
    episodes: int = 200,
    fingerprint: str = "fp",
) -> dict:
    return {
        "candidate": candidate,
        "seed": seed,
        "episodes": episodes,
        "model_fingerprint": fingerprint,
    }


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
                "model_fingerprint": "fp",
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
    assert all(panel.get("seed") != 500 for panel in panels)


def test_selection_panels_preserve_prior_exposure_when_lineage_is_reused():
    source = {
        "selected_panels": [
            {"instrument": "research_evaluation", "seed": 100, "episodes": 200}
        ]
    }
    pending = {
        "requested_evaluations": [
            {
                **_measurement("c1", seed=500, episodes=200),
                "instrument": "research_evaluation",
            }
        ]
    }
    assert protocol._selection_panels_for(source, pending, "fp") == [
        {"instrument": "research_evaluation", "seed": 100, "episodes": 200},
        {"instrument": "research_evaluation", "seed": 500, "episodes": 200},
    ]


def test_duplicate_selection_panels_are_counted_once():
    source = {
        "selected_panels": [
            {"instrument": "research_evaluation", "seed": 100, "episodes": 200}
        ]
    }
    pending = {
        "requested_evaluations": [
            {**_measurement("c1"), "instrument": "research_evaluation"}
        ]
    }
    assert protocol._selection_panels_for(source, pending, "fp") == [
        {"instrument": "research_evaluation", "seed": 100, "episodes": 200}
    ]


def test_generic_brief_does_not_expand_panel_specific_diagnostics():
    state = {
        "campaign": {"id": "campaign"},
        "last_verdict": "measurement complete",
        "active_inquiry": None,
        "active_method": None,
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_analysis": None,
        "pending_evaluation_request": None,
        "pending_inquiry_operation": None,
        "pending_final_benchmark": None,
        "pending_campaign_conclusion": None,
        "preparation_measurement": {
            "rounds": [{"results": {"research_evaluations": [{"status": "reused"}]}}]
        },
    }
    rendered = brief._render_inquiry_centered_brief(state, [], [], "", "campaign", None)
    assert "scenario-specific diagnoses" in rendered
    assert "Reused panel context" not in rendered
