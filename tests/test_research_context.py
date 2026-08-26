from research.build_research_brief import (
    parse_training_records,
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

    assert "Peak success: 0.25 at 1024 steps" in summary
    assert "First zero-success snapshot after the peak: 2048 steps" in summary
    assert "Final policy std: 0.5" in summary
    assert "models/reach-example/model.zip" in summary
