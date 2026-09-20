"""Per-section seams for the research brief.

Issue #41.2: the brief's sections are independent builders so that changes to
candidates, evidence, lineages, or campaign activity can be reviewed and tested
one section at a time instead of editing one large renderer.
"""

import json

import pytest

from research import build_research_brief as brief
from research.build_research_brief import render_research_brief


def test_phase_section_tracks_the_lifecycle_state():
    assert "experiment preparation" in "\n".join(
        brief._v4_phase_section({}, None, None, "none", None, "cid", "base")
    )
    assert "post-training analysis" in "\n".join(
        brief._v4_phase_section({}, {"experiment": 1}, None, 1, None, "cid", "base")
    )
    assert "terminal official assessment" in "\n".join(
        brief._v4_phase_section(
            {"terminal_campaign_status": "goal_reached"},
            None,
            None,
            "none",
            "goal_reached",
            "cid",
            "base",
        )
    )


def test_lineage_section_points_at_the_authoritative_lineages():
    lines = brief._v4_lineage_section({}, {})
    text = "\n".join(lines)
    assert "## Current lineages and scientific recipes" in text
    assert "## Working lineage" in text
    assert "Working: unset" in text


def test_experiment_index_section_renders_one_row_per_experiment():
    assert brief._v4_experiment_index_section([]) == [
        "",
        "## Campaign experiment index",
        "",
        (
            "Each row records what one experiment did and concluded. Past closure "
            "choices answered the question that experiment asked; they are not a "
            "default for the next one. Each recorded closure is shown with the "
            "de-templated rationale that answered its question; a closure whose "
            "rationale is not reproduced here is withheld."
        ),
        "",
        "| # | Operation / family | Parent | Intervention | Measurements | Hypothesis assessment | Final decisions | Detail |",
        "|---:|---|---|---|---|---|---|---|",
        "| - | - | - | - | - | - | - | - |",
    ]

    lines = brief._v4_experiment_index_section(
        [{"index": 2, "kind": "training", "family": "f"}]
    )
    assert any(line.startswith("| 2 | training / f |") for line in lines)


def test_evidence_section_reports_an_empty_record_clearly():
    lines = brief._v4_evidence_section(None, [])
    assert lines[:3] == ["", "## Development evidence index", ""]
    assert lines[3] == "No fingerprint-bound development evidence recorded yet."


def test_synthesis_section_falls_back_when_no_strategy_exists():
    lines = brief._v4_synthesis_section("", "cid")
    assert "## Provisional scientific synthesis" in lines
    assert lines[-1] == "No scientific strategy recorded for this campaign yet."


def test_repeated_operations_section_is_factual_when_empty():
    lines = brief._v4_repeated_operations_section([])
    assert lines == ["", "## Repeated operations", "", "No repeated operations recorded."]


def test_intervention_surfaces_section_is_factual_when_empty():
    lines = brief._v4_intervention_surfaces_section([])
    assert "## Intervention surfaces" in lines
    assert any("unchanged" in line for line in lines)


def test_intervention_surfaces_are_ordered_by_path_not_count(monkeypatch):
    sources = [
        "robot_learning/scenario/alpha.py",
        "robot_learning/scenario/beta.py",
        "robot_learning/training/zeta.py",
    ]
    monkeypatch.setattr(brief, "_researcher_owned_sources", lambda: list(sources))
    results = [
        {"code_changes": ["robot_learning/training/zeta.py"]},
        {"code_changes": ["robot_learning/training/zeta.py"]},
        {"code_changes": ["robot_learning/scenario/beta.py"]},
    ]
    surfaces, _, _ = brief._intervention_surfaces(results)
    # Issue #55: path order, never count order.
    assert surfaces == [
        ("robot_learning/scenario/alpha.py", 0),
        ("robot_learning/scenario/beta.py", 1),
        ("robot_learning/training/zeta.py", 2),
    ]


def test_intervention_surface_section_is_not_count_ranked(monkeypatch):
    sources = [
        "robot_learning/scenario/alpha.py",
        "robot_learning/scenario/beta.py",
        "robot_learning/training/zeta.py",
    ]
    monkeypatch.setattr(brief, "_researcher_owned_sources", lambda: list(sources))
    results = [
        {"code_changes": ["robot_learning/training/zeta.py"]},
        {"code_changes": ["robot_learning/training/zeta.py"]},
        {"code_changes": ["robot_learning/scenario/beta.py"]},
    ]
    text = "\n".join(brief._v4_intervention_surfaces_section(results))
    changed = text.split("### Not yet changed")[0]
    never_changed = text.split("### Not yet changed")[1]
    # Path order holds inside the changed group; the count leader is not first.
    assert changed.index("robot_learning/scenario/beta.py") < changed.index(
        "robot_learning/training/zeta.py"
    )
    assert "changed in 1 experiment" in changed
    assert "changed in 2 experiments" in changed
    # Never-changed sources get their own group rather than trailing zeros.
    assert "robot_learning/scenario/alpha.py" in never_changed
    assert "path order" in text



def test_reusable_lineages_and_best_known_default_to_unset():
    reusable = brief._v4_reusable_lineages_section({})
    assert reusable[-1] == "No retained alternatives."
    best_known = brief._v4_best_known_section({})
    assert best_known[-1] == "- Best known: unset"


def test_official_section_is_absent_until_a_verdict_exists():
    assert brief._v4_official_section({}, None) == []
    lines = brief._v4_official_section(
        {
            "official_metrics": {"success_percent": 98.0},
            "official_benchmark_model": {"selected": "working", "artifact": "a"},
            "official_benchmark_verdict": "goal_reached",
        },
        "goal_reached",
    )
    assert "## Official report" in lines
    assert "- Verdict: goal_reached" in lines


def test_composed_brief_orders_each_section_once():
    text = brief._render_v4_research_brief({}, [], "", "cid", "base", "PPO", {})
    headings = [
        "## Current phase and latest event",
        "## Latest experiment",
        "## Current lineages and scientific recipes",
        "## Working lineage",
        "## Campaign experiment index",
        "## Development evidence index",
        "## Campaign activity record",
        "## Provisional scientific synthesis",
        "## Repeated operations",
        "## Intervention surfaces",
        "## Reusable lineages",
        "## Best-known model",
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_measurement_rounds_section_groups_rounds_in_order():
    pending = {
        "evaluation_rounds": [
            {
                "round": 1,
                "question": "first question",
                "reason": "first reason",
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "c1",
                            "episodes": 10,
                            "seed": 1,
                            "success_percent": 90.0,
                            "selection": "observed signal",
                            "evaluation_artifact": "research/evaluations/x.json",
                        }
                    ]
                },
            },
            {
                "round": 2,
                "question": "second question",
                "reason": "second reason",
                "status": "completed",
                "results": {
                    "paired_comparisons": [
                        {
                            "candidate": "c1",
                            "reference": "working",
                            "candidate_wins": 3,
                            "reference_wins": 1,
                            "episodes": 10,
                        }
                    ]
                },
            },
        ]
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, [], pending))
    assert text.index("### Round 1 (completed)") < text.index("### Round 2 (completed)")
    assert "first question" in text
    assert "second question" in text
    assert "`c1` `research_evaluation`" in text
    assert "episodes 1–10" in text
    assert "(new panel)" in text
    assert "Paired comparison `c1` vs `working`" in text


def test_measurement_round_panel_novelty_is_round_scoped():
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        {"candidate": "c1", "seed": 100, "episodes": 200},
                        {"candidate": "c2", "seed": 100, "episodes": 200},
                    ]
                },
            },
            {
                "round": 2,
                "results": {
                    "research_evaluations": [
                        {"candidate": "c3", "seed": 100, "episodes": 200}
                    ]
                },
            },
        ],
    }
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [
                {"candidate": "old", "seed": 900, "episodes": 200}
            ],
        }
    ]
    text = "\n".join(
        brief._v4_measurement_rounds_section({}, prior_results, pending)
    )
    round_one = text.split("### Round 2")[0]
    round_two = text.split("### Round 2")[1]
    # Two candidates sharing one panel in the same round are both new.
    assert round_one.count("(new panel)") == 2
    assert "(reused panel)" not in round_one
    # The identical panel in a later round is cross-round reuse.
    assert "(reused panel: 2 prior measurements on these episodes)" in round_two


def test_measurement_round_panel_novelty_recognises_prior_experiments():
    pending = {
        "experiment": 2,
        "evaluation_rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        {"candidate": "c1", "seed": 900, "episodes": 200}
                    ]
                },
            }
        ],
    }
    prior_results = [
        {
            "index": 1,
            "requested_evaluations": [
                {"candidate": "old", "seed": 900, "episodes": 200}
            ],
        }
    ]
    text = "\n".join(
        brief._v4_measurement_rounds_section({}, prior_results, pending)
    )
    assert "(reused panel: 1 prior measurement on these episodes)" in text


def test_measurement_rounds_retain_de_templated_rationale_during_preparation():
    record = {
        "index": 1,
        "evaluation_rounds": [
            {
                "round": 1,
                "question": "does it reproduce",
                "reason": "round reason",
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "checkpoint-100",
                            "seed": 100,
                            "episodes": 200,
                            "success_percent": 90.0,
                            "selection": "proxy peak template",
                            "evaluation_artifact": "research/evaluations/e.json",
                        }
                    ]
                },
            }
        ],
    }
    analysis = "\n".join(brief._v4_measurement_rounds_section({}, [], record))
    preparation = "\n".join(
        brief._v4_measurement_rounds_section({}, [record], None)
    )

    # Follow-up analysis keeps the evidence needed to adapt the next round.
    assert "Selection: proxy peak template" in analysis
    assert "Reason: round reason" in analysis
    # Issue #54: preparation keeps the rationale as well, but de-templated. The
    # content stays auditable while the inline field names that read as a form
    # to copy are not reproduced.
    assert "does it reproduce" in preparation
    assert "success 90.00%" in preparation
    assert "proxy peak template" in preparation
    assert "round reason" in preparation
    assert "Selection: proxy peak template" not in preparation
    assert "Reason: round reason" not in preparation
    assert "Recorded rationale for a past decision" in preparation
    assert "Completed measurement rounds" in preparation
    assert "Measurement rounds for the current experiment" in analysis


def _closed_experiment(
    index: int,
    family: str,
    *,
    continue_from: str,
    best_known: str,
    code: str,
    reason: str | None,
    selection: str | None,
) -> dict:
    record = {
        "index": index,
        "kind": "training",
        "family": family,
        "closure_decision": {
            "continue_from": continue_from,
            "best_known": {"candidate": best_known},
            "code": {"action": code},
        },
        "evaluation_rounds": [],
    }
    if reason is not None or selection is not None:
        round_record = {
            "round": 1,
            "question": f"question-{index}",
            "status": "completed",
            "results": {},
        }
        if reason is not None:
            round_record["reason"] = reason
        if selection is not None:
            round_record["results"] = {
                "research_evaluations": [
                    {
                        "candidate": best_known,
                        "seed": index,
                        "episodes": 10,
                        "selection": selection,
                    }
                ]
            }
        record["evaluation_rounds"] = [round_record]
    return record


def test_composed_preparation_brief_pairs_every_closure_with_its_rationale():
    results = [
        _closed_experiment(
            1,
            "alpha",
            continue_from="checkpoint-10",
            best_known="checkpoint-10",
            code="keep",
            reason="reason-alpha",
            selection="selection-alpha",
        ),
        _closed_experiment(
            2,
            "beta",
            continue_from="checkpoint-20",
            best_known="checkpoint-20",
            code="revert",
            reason="reason-beta",
            selection="selection-beta",
        ),
        # A recorded closure whose rationale is not reproduced must be withheld.
        _closed_experiment(
            3,
            "gamma",
            continue_from="checkpoint-30",
            best_known="checkpoint-30",
            code="keep",
            reason=None,
            selection=None,
        ),
        # The most recent experiment also carries its rationale in the rounds.
        _closed_experiment(
            4,
            "delta",
            continue_from="checkpoint-40",
            best_known="checkpoint-40",
            code="keep",
            reason="reason-delta",
            selection="selection-delta",
        ),
    ]
    text = brief._render_v4_research_brief(
        {"schema_version": 4, "campaign": {"id": "cid", "base_commit": "base"}},
        results,
        "",
        "cid",
        "base",
        "PPO",
        {},
    )

    # One documented predicate governs the whole preparation brief.
    assert brief._precedent_prose_inline(None) is False
    assert brief._precedent_prose_inline({"experiment": 5}) is True
    # Every visible closure is paired with the rationale that answered it.
    paired = [
        (
            "working checkpoint-10; best known checkpoint-10; code keep",
            "reason-alpha",
            "selection-alpha",
        ),
        (
            "working checkpoint-20; best known checkpoint-20; code revert",
            "reason-beta",
            "selection-beta",
        ),
        (
            "working checkpoint-40; best known checkpoint-40; code keep",
            "reason-delta",
            "selection-delta",
        ),
    ]
    for outcome, reason, selection in paired:
        assert outcome in text
        assert reason in text
        assert selection in text
    # A closure with no reproduced rationale is withheld rather than shown bare.
    assert "working checkpoint-30; best known checkpoint-30; code keep" not in text
    assert "closure withheld during preparation" in text
    # The rationale is de-templated, never the inline answer-form field names.
    assert "Reason:" not in text
    assert "Selection:" not in text


def test_activity_record_lists_consumed_research_intervals_factually():
    results = [
        {
            "index": 1,
            "kind": "training",
            "requested_evaluations": [
                {"candidate": "c1", "seed": 4200, "episodes": 160},
                {"candidate": "c2", "seed": 4200, "episodes": 160},
                {"candidate": "c3", "seed": 4400, "episodes": 160},
            ],
        }
    ]
    text = "\n".join(brief._v4_activity_record_section({}, results, None))
    assert "research_evaluation intervals consumed: 4200–4359, 4400–4559." in text
    assert "recommend" not in text.lower()


def test_measurement_rounds_section_is_absent_without_rounds():
    assert brief._v4_measurement_rounds_section({}, [], None) == []
    assert brief._v4_measurement_rounds_section({}, [], {}) == []


def test_activity_record_counts_training_and_replication_factually():
    results = [
        {
            "index": 1,
            "kind": "training",
            "training_budget_steps": 100,
            "completed_training_steps": 100,
        },
        {
            "index": 2,
            "kind": "training",
            "training_budget_steps": 100,
            "completed_training_steps": 120,
        },
        {
            "index": 3,
            "kind": "replication",
            "training_budget_steps": 100,
            "completed_training_steps": 100,
            "replication_of": 1,
        },
    ]
    text = "\n".join(brief._v4_activity_record_section({}, results, None))
    assert "Training experiments: 3" in text
    assert "Replication experiments recorded: 3." in text
    # Issue #46: no campaign-wide running total of consumed resources.
    assert "completed steps" not in text
    assert "requested steps" not in text


def _measurement(
    candidate: str,
    *,
    seed: int = 4200,
    episodes: int = 160,
    semantics: str = "semantics",
) -> dict:
    return {
        "candidate": candidate,
        "seed": seed,
        "episodes": episodes,
        "evaluation_semantics": semantics,
        "metrics": {"seed": seed, "episodes": episodes, "evaluation_semantics": semantics},
    }


def _task_reference(candidate: str, *, seed: int = 7300, episodes: int = 200) -> dict:
    return {
        "candidate": candidate,
        "panel": "task-reference-v1",
        "seed": seed,
        "episodes": episodes,
    }


def test_activity_record_counts_cross_model_panel_reuse_at_campaign_level():
    results = [
        {
            "index": 1,
            "kind": "training",
            "requested_evaluations": [
                _measurement("c1"),
                _measurement("c2"),
            ],
            "task_reference_evaluations": [_task_reference("c1")],
        },
        {
            "index": 2,
            "kind": "training",
            "requested_evaluations": [_measurement("c3")],
            "task_reference_evaluations": [_task_reference("c3")],
        },
    ]
    text = "\n".join(brief._v4_activity_record_section({}, results, None))
    assert "Instrument executions: 3 research_evaluation, 2 task_reference." in text
    assert "research_evaluation coverage: 160 distinct episodes; 480 episode" in text
    assert "320 repeated." in text
    assert "task_reference coverage: 200 distinct episodes; 400 episode" in text
    assert "200 repeated." in text


def test_activity_record_distinguishes_overlapping_research_panels():
    results = [
        {
            "index": 1,
            "kind": "training",
            "requested_evaluations": [
                _measurement("c1", seed=4200, semantics="v1"),
                _measurement("c2", seed=4360, semantics="v1"),
            ],
        }
    ]
    text = "\n".join(brief._v4_activity_record_section({}, results, None))
    # Two disjoint 160-episode panels: 320 distinct identities, no repetition.
    assert "research_evaluation coverage: 320 distinct episodes; 320 episode" in text
    assert "0 repeated." in text


def test_activity_record_counts_repeated_rounds_and_coverage_separately():
    results = [
        {
            "index": 1,
            "kind": "training",
            "training_budget_steps": 100,
            "completed_training_steps": 100,
            "evaluation_rounds": [{"round": 1}, {"round": 2}],
            "requested_evaluations": [
                _measurement("c1", episodes=10, seed=1),
                _measurement("c2", episodes=10, seed=1),
            ],
        }
    ]
    text = "\n".join(brief._v4_activity_record_section({}, results, None))
    assert "Evaluation rounds: 2." in text
    assert "Instrument executions: 2 research_evaluation, 0 task_reference." in text
    assert "research_evaluation coverage: 10 distinct episodes; 20 episode" in text
    assert "10 repeated." in text


def test_activity_record_does_not_recommend_confirmation():
    text = "\n".join(brief._v4_activity_record_section({}, [], None)).lower()
    for wording in ("budget limit", "warning", "should", "enough", "stop"):
        assert wording not in text


def test_activity_record_separates_execution_from_evidence_coverage():
    results = [
        {
            "index": 1,
            "kind": "training",
            "evaluation_rounds": [{"round": 1}],
            "requested_evaluations": [_measurement("c1")],
            "task_reference_evaluations": [_task_reference("c1")],
        }
    ]
    text = "\n".join(brief._v4_activity_record_section({}, results, None))
    assert "### Executed so far" in text
    assert "### Evidence coverage" in text
    executed = text.split("### Evidence coverage")[0]
    coverage = text.split("### Evidence coverage")[1]
    assert "Training experiments: 1." in executed
    assert "Evaluation rounds: 1." in executed
    assert "coverage:" not in executed
    assert "coverage:" in coverage
    # Issue #46: the coverage group keeps the panel-design facts.
    assert "research_evaluation intervals consumed:" in coverage


@pytest.mark.parametrize(
    "state",
    [
        {"schema_version": 4, "campaign": {"id": "cid", "base_commit": "base"}},
        {"schema_version": 3, "accepted_metrics": {"episodes": 400}},
        {"accepted_metrics": {"episodes": 400}},
    ],
)
def test_rendered_brief_carries_no_budget_vocabulary(monkeypatch, tmp_path, state):
    """Issue #46: every schema branch renders without budget vocabulary."""
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    lowered = render_research_brief().lower()
    for wording in ("cost", "budget", "remaining", "allowance", "spent"):
        assert wording not in lowered
