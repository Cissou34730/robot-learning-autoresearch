"""Training-log queries use operation and variant identities."""

from __future__ import annotations

import json

import pytest

from runner import paths, query_training_log, repository, training_series


def test_training_log_cli_rejects_non_operation_identity():
    with pytest.raises(SystemExit):
        query_training_log.parse_arguments(
            ["--operation", "2", "--from-step", "0", "--to-step", "10"]
        )


def test_discover_lists_variant_names_when_variant_is_omitted(tmp_path, monkeypatch):
    log_dir = tmp_path / "campaigns" / "training_logs"
    campaign_dir = log_dir / "campaign-one"
    campaign_dir.mkdir(parents=True)
    (campaign_dir / "t1-zeta-attempt-1.log").write_text("", encoding="utf-8")
    (campaign_dir / "t1-alpha-attempt-1.log").write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "SPLIT", False)
    monkeypatch.setattr(paths, "TRAINING_LOG_DIR", log_dir)
    monkeypatch.setattr(
        repository,
        "load_state",
        lambda **_: {
            "campaign": {"id": "campaign-one"},
            "operation_events": [
                {"id": "T1", "kind": "training", "status": "completed"}
            ],
        },
    )

    result = json.loads(
        query_training_log.query_training_log(
            {"operation_id": "T1"}, campaign_id="campaign-one"
        )
    )

    assert result["status"] == "discovered"
    assert result["available_variants"] == ["alpha", "zeta"]

    series = json.loads(
        training_series.query_training_series(
            {"operation_id": "T1", "metric": "success_rate"},
            campaign_id="campaign-one",
        )
    )

    assert series["status"] == "variant_required"
    assert series["provenance"]["available_variants"] == ["alpha", "zeta"]
