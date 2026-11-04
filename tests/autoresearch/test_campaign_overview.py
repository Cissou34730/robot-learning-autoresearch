"""Campaign overview projections."""

from datetime import UTC, datetime, timedelta

from tui.activity import EvaluationProgress
from tui.overview import overview_campaign, overview_values
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
