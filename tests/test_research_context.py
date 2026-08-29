import json

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


def test_brief_includes_compact_measured_challenger_diagnostics(
    monkeypatch, tmp_path
):
    summary = {
        "episodes": 4,
        "success_percent": 50.0,
        "pooled_success_percent": 50.0,
        "seed_count": 1,
        "failed_episode_progress": {
            "failed_episodes": 2,
            "longest_consecutive_steps_mean": 23.0,
            "best_window_inside_steps_mean": 41.0,
            "required_steps": 100,
        },
        "failure_diagnostics": [
            {
                "best_window_inside_steps": 41,
                "longest_consecutive_steps": 23,
                "target_radius_cm": 12.0,
            }
        ],
    }
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(
            {
                "accepted_artifact": "accepted",
                "pending_researcher_decision": {
                    "experiment": 4,
                    "candidates": [{"name": "hold-focused", "summary": summary}],
                    "champion_available": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "## Measured challenger diagnostics" in brief
    assert "**hold-focused**" in brief
    assert "Mean longest failed hold: 23.0/100 steps." in brief
