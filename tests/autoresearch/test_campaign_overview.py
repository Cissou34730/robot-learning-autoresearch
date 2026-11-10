"""Campaign overview projections."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from tui.activity import EvaluationProgress
from tui.overview import MODEL_READY, overview_campaign, overview_values
from tui.projector import GoalSummary


def test_overview_uses_recorded_campaign_values_and_live_evaluation():
    started = datetime(2026, 1, 1, tzinfo=UTC)
    state = {
        "campaign": {"id": "test", "started_at": started.isoformat()},
        "campaign_phase": "research",
        "counters": {"inquiry": 4},
    }
    campaign = overview_campaign(1, state, [], True)
    evaluation = EvaluationProgress(
        operation_id="M1", panel_index=1, panel_total=2, episodes=35, episodes_total=100
    )
    values = overview_values(
        campaign, "running", evaluation, now=started + timedelta(hours=2)
    )
    assert values[0:3] == ("Inquiry", "running", "unavailable")
    assert values[4:6] == ("1/2 35/100", "4")
    assert values[7] == "not assessed"
    assert campaign.snapshot is not None
    campaign.snapshot.goal = GoalSummary(target_percent=80)
    assert overview_values(campaign, "running", evaluation, now=started)[6] == "?/80%"


def test_overview_reports_missing_state_and_missing_installation():
    now = datetime.now(tz=UTC)
    missing_state = overview_campaign(1, None, [], True)
    absent = overview_campaign(2, None, [], False)
    assert overview_values(missing_state, "running", None, now=now)[0] == "unavailable"
    assert overview_values(absent, "not installed", None, now=now)[0] == "not set up"


def test_overview_reports_scientific_model_publication():
    now = datetime.now(tz=UTC)
    base = {"campaign": {"id": "test"}, "campaign_phase": "startup"}
    values = {
        status: overview_values(
            overview_campaign(
                1, {**base, "scientific_model": {"status": status}}, [], True
            ),
            "running",
            None,
            now=now,
        )[8]
        for status in ("pending", "ready")
    }
    assert values == {"pending": "not published", "ready": MODEL_READY}
    assert (
        overview_values(overview_campaign(1, base, [], True), "running", None, now=now)[
            8
        ]
        == "unavailable"
    )


def test_scientific_model_reads_the_recorded_commit_only(tmp_path):
    import json
    import os
    import shutil
    import subprocess
    from uuid import uuid4

    from tui.scientific_model import MODEL_PATH, load_scientific_model

    root = Path(os.environ.get("TEMP", str(tmp_path))) / f"model-{uuid4().hex}"

    def git(*arguments):
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    try:
        assert load_scientific_model(root).status == "missing"
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        model = root / MODEL_PATH
        model.parent.mkdir(parents=True)
        model.write_text("# Established facts\n\nPublished.\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-q", "-m", "model")
        commit = git("rev-parse", "HEAD")
        model.write_text("# Draft after publication\n", encoding="utf-8")
        state_path = root / "runner" / "state" / "research_state.json"
        state_path.parent.mkdir(parents=True)

        def read(record):
            state_path.write_text(
                json.dumps({"scientific_model": record}), encoding="utf-8"
            )
            return load_scientific_model(root)

        pending = {"status": "pending", "path": MODEL_PATH, "commit": None}
        assert read(pending).status == "pending"
        view = read({"status": "ready", "path": MODEL_PATH, "commit": commit})
        assert (view.status, view.commit, view.text) == (
            "ready",
            commit,
            "# Established facts\n\nPublished.\n",
        )
        missing = {"status": "ready", "path": MODEL_PATH, "commit": "0" * 40}
        assert read(missing).status == "error"
        other = {"status": "ready", "path": "other.md", "commit": commit}
        assert read(other).status == "error"
    finally:
        shutil.rmtree(root, ignore_errors=True)
