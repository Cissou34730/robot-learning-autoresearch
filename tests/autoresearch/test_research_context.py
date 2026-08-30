import json
from pathlib import Path

from research.build_research_brief import (
    parse_training_records,
    render_research_brief,
    render_training_summary,
)

SAMPLE_LOG = """
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 400         |
|    ep_rew_mean          | 2.5         |
|    success_rate         | 0.25        |
| time/                   |             |
|    total_timesteps      | 1024        |
| train/                  |             |
|    explained_variance   | 0.4         |
|    std                  | 0.9         |
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 500         |
|    ep_rew_mean          | 10          |
|    success_rate         | 0           |
| time/                   |             |
|    total_timesteps      | 2048        |
| train/                  |             |
|    explained_variance   | 0.8         |
|    std                  | 0.5         |
-----------------------------------------
Model saved to models/reach-example/model.zip
"""


def test_training_log_parser_groups_metric_snapshots():
    records = parse_training_records(SAMPLE_LOG)

    assert len(records) == 2
    assert records[0]["success_rate"] == 0.25
    assert records[0]["total_timesteps"] == 1024
    assert records[1]["std"] == 0.5


def test_training_summary_keeps_decision_relevant_metrics():
    summary = render_training_summary(SAMPLE_LOG)

    assert "Peak-success snapshot" not in summary
    assert "stochastic training policy" in summary
    assert "false peak" in summary
    assert "Final policy std: 0.5" in summary
    assert "models/reach-example/model.zip" in summary


def test_brief_reports_the_measured_score_and_points_at_the_detail(
    monkeypatch, tmp_path
):
    summary = {
        "episodes": 4,
        "success_percent": 50.0,
        "pooled_success_percent": 50.0,
        "seed_count": 1,
    }
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(
            {
                "accepted_artifact": "accepted",
                "accepted_evaluations": [
                    "models/candidates/evaluation-experiment-3-champion-4ep-seed1000.json"
                ],
                "pending_researcher_decision": {
                    "experiment": 4,
                    "candidates": [
                        {
                            "name": "hold-focused",
                            "summary": summary,
                            "evaluations": [
                                {
                                    "episodes": 4,
                                    "seed": 3000,
                                    "success_percent": 50.0,
                                    "evaluation_artifact": (
                                        "models/candidates/"
                                        "evaluation-experiment-4-1.json"
                                    ),
                                }
                            ],
                        }
                    ],
                    "champion_available": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "hold-focused: pooled success 50.00%" in brief
    assert "4 episodes, seed 3000, success 50.00%" in brief
    assert "models/candidates/evaluation-experiment-4-1.json" in brief
    assert (
        "Accepted evaluation detail: "
        "`models/candidates/evaluation-experiment-3-champion-4ep-seed1000.json`"
    ) in brief
    assert "Measured challenger diagnostics" not in brief
    assert "Observed failure diagnostics" not in brief


def test_brief_groups_original_and_exact_replications(monkeypatch, tmp_path):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "index": index,
                    "verdict": "measured",
                    "change": "same method",
                    "hypothesis": "check spread",
                    "family": "method",
                    "training_seed": seed,
                    "candidate_metrics": {"success_percent": success},
                    **(
                        {"replication_of": replication_of}
                        if replication_of is not None
                        else {}
                    ),
                }
            )
            for index, seed, success, replication_of in [
                (12, 1, 40.0, None),
                (15, 2, 60.0, 12),
                (16, 3, 50.0, 12),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "## Replication Evidence" in brief
    assert "`12`" in brief
    assert "seed 1" in brief and "seed 2" in brief and "seed 3" in brief
    assert "40.00-60.00%" in brief


def test_brief_keeps_the_declared_family_without_deriving_a_taxonomy(
    monkeypatch, tmp_path
):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        json.dumps(
            {
                "index": 3,
                "verdict": "measured",
                "change": "increase the closeness reward",
                "hypothesis": "shaping",
                "family": "declared-family",
                "candidate_metrics": {"success_percent": 40.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "declared-family" in brief
    assert "## Tested hypothesis families" not in brief
    assert "reward.CLOSENESS_COEFFICIENT" not in brief


def test_lineage_orchestration_requires_markdown_postmortem():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")
    program = (root / "research" / "program.md").read_text(encoding="utf-8")

    assert "Test-LineageResearchMemory" in script
    assert "postmortems.md" in script
    assert "preserved candidate artifacts" not in script
    assert "preserve_candidates" not in script
    assert "previous_experiment_postmortem" not in program
