"""Per-section seams for the research brief.

Issue #41.2: the brief's sections are independent builders so that changes to
candidates, evidence, lineages, or cost accounting can be reviewed and tested
one section at a time instead of editing one large renderer.
"""

from research import build_research_brief as brief


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
        "## Campaign cost accounting",
        "## Terminal-readiness evidence",
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
    text = "\n".join(brief._v4_measurement_rounds_section(pending, None))
    assert text.index("### Round 1 (completed)") < text.index("### Round 2 (completed)")
    assert "first question" in text
    assert "second question" in text
    assert "`c1` `research_evaluation`" in text
    assert "Paired comparison `c1` vs `working`" in text


def test_measurement_rounds_section_is_absent_without_rounds():
    assert brief._v4_measurement_rounds_section(None, None) == []
    assert brief._v4_measurement_rounds_section({}, None) == []


def test_cost_accounting_counts_training_and_replication_factually():
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
    text = "\n".join(brief._v4_cost_accounting_section({}, results, None))
    assert "Training experiments: 3" in text
    assert "completed steps: 320" in text
    assert "requested steps: 300" in text
    assert "Replication experiments recorded: 3." in text


def test_cost_accounting_counts_repeated_rounds_and_coverage_separately():
    results = [
        {
            "index": 1,
            "kind": "training",
            "training_budget_steps": 100,
            "completed_training_steps": 100,
            "evaluation_rounds": [
                {
                    "round": 1,
                    "results": {
                        "research_evaluations": [{"episodes": 10}, {"episodes": 10}]
                    },
                },
                {
                    "round": 2,
                    "results": {
                        "research_evaluations": [{"episodes": 10}],
                        "task_reference_evaluations": [{"episodes": 200}],
                    },
                },
            ],
            "candidates": [
                {
                    "summary": {
                        "episodes": 15,
                        "episode_executions": 30,
                        "repeated_episodes": 15,
                    }
                }
            ],
        }
    ]
    text = "\n".join(brief._v4_cost_accounting_section({}, results, None))
    assert "Evaluation rounds: 2" in text
    assert "research_evaluation: 3 executions, 30 episodes" in text
    assert "task_reference: 1 executions, 200 episodes" in text
    assert "15 distinct; 30 executions; 15 repeated" in text


def test_cost_accounting_does_not_recommend_confirmation():
    text = "\n".join(brief._v4_cost_accounting_section({}, [], None)).lower()
    for wording in ("budget limit", "warning", "should", "enough", "stop"):
        assert wording not in text
