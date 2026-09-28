"""Schema-6 training-log lookup uses operation identity."""

from __future__ import annotations

import pytest

from research import query_training_log


def test_training_log_lookup_uses_the_training_operation_id(monkeypatch, tmp_path):
    directory = tmp_path / "training_logs" / "campaign"
    directory.mkdir(parents=True)
    directory.joinpath("t2-attempt-2.log").write_text(
        "| train/ | |\n| total_timesteps | 20 |\n| ep_rew_mean | 4 |\n",
        encoding="utf-8",
    )
    directory.joinpath("t2-attempt-1.log").write_text(
        "| train/ | |\n| total_timesteps | 10 |\n| ep_rew_mean | 2 |\n",
        encoding="utf-8",
    )
    directory.joinpath("t3-attempt-1.log").write_text(
        "| train/ | |\n| total_timesteps | 30 |\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        query_training_log.paths, "TRAINING_LOG_DIR", tmp_path / "training_logs"
    )
    monkeypatch.setattr(
        query_training_log.repository,
        "load_state",
        lambda **_kwargs: {"campaign": {"id": "campaign"}},
    )
    monkeypatch.setattr(
        query_training_log.repository,
        "current_campaign_id",
        lambda _state: "campaign",
    )

    assert [
        attempt for attempt, _path in query_training_log.training_log_paths("T2")
    ] == [
        1,
        2,
    ]
    assert query_training_log.training_log_paths("T3")[0][0] == 1


def test_training_log_cli_rejects_non_operation_identity():
    with pytest.raises(SystemExit):
        query_training_log.parse_arguments(
            ["--operation", "2", "--from-step", "0", "--to-step", "10"]
        )
