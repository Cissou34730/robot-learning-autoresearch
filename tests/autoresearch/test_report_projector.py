"""Projection tests for the campaign report (no Textual, no live app).

All material is synthetic. The tests pin the recorded-schema behaviors the
specification requires: role joins, latest-completed development evidence,
scope-preserving usage and explicit unavailable values.
"""

from datetime import UTC, datetime

from tui import projector
from tui.demo import (
    demo_clock,
    demo_records,
    demo_state,
    demo_usage_rows,
)


def _now():
    return datetime.now(tz=UTC)


def _demo_snapshot():
    started, _, now = demo_clock()
    return projector.build_snapshot(
        demo_state(now, started),
        demo_records(now),
        demo_usage_rows(now),
    )


def _observation_args():
    started, _, now = demo_clock()
    return demo_state(now, started), demo_records(now), demo_usage_rows(now)


def test_model_rows_join_roles_and_recorded_metrics():
    snapshot = _demo_snapshot()
    rows = {row.candidate_id: row for row in snapshot.model_rows}
    assert set(rows) == {
        "T4:checkpoint-120000",
        "T2:checkpoint-90000",
        "T1:checkpoint-60000",
    }
    working = rows["T4:checkpoint-120000"]
    assert working.roles == ("Working",)
    assert working.training_steps == "120,000"
    assert working.reward_training == "86.3"
    assert working.success_training == "97%"
    assert working.success_dev == "not measured"
    best = rows["T2:checkpoint-90000"]
    assert best.roles == ("Best-known",)
    assert best.reward_training == "unavailable"
    assert best.success_dev == "94%, 160 episodes / M5, task_reference"
    retained = rows["T1:checkpoint-60000"]
    assert retained.roles == ("Retained: baseline",)
    assert retained.success_dev == "89%, 160 episodes / M5, task_reference"


def test_development_success_uses_latest_completed_nonofficial_panel():
    state, records, _ = _observation_args()
    stamp = _now().isoformat()
    records.append(
        {
            "id": "M6",
            "kind": "measurement",
            "status": "completed",
            "completed_at": stamp,
            "request": {},
            "result": {
                "instrument": "task_reference",
                "measurements": [
                    {
                        "candidate_id": "T4:checkpoint-120000",
                        "instrument": "task_reference",
                        "metrics": {"success_percent": 62.5, "episodes": 100},
                    }
                ],
            },
        }
    )
    records.append(
        {
            "id": "M7",
            "kind": "measurement",
            "status": "completed",
            "completed_at": stamp,
            "request": {},
            "result": {
                "instrument": "task_reference",
                "measurements": [
                    {
                        "candidate_id": "T4:checkpoint-120000",
                        "instrument": "official panel",
                        "metrics": {
                            "success_percent": 100.0,
                            "official_benchmark": True,
                        },
                    }
                ],
            },
        }
    )
    rows = {
        row.candidate_id: row
        for row in projector.build_snapshot(state, records, []).model_rows
    }
    # Latest completed panel wins and an official panel never becomes
    # development evidence.
    assert rows["T4:checkpoint-120000"].success_dev.startswith("62.5%")
    assert "M6" in rows["T4:checkpoint-120000"].success_dev


def test_role_entries_combine_on_one_row():
    state, _, _ = _observation_args()
    state["model_roles"] = {
        "working": "T2:checkpoint-90000",
        "best_known": "T2:checkpoint-90000",
        "retained": {"reference": "T1:checkpoint-60000"},
    }
    rows = projector.build_snapshot(state, [], []).model_rows
    assert len(rows) == 2
    combined = rows[0]
    assert combined.candidate_id == "T2:checkpoint-90000"
    assert combined.roles == ("Working", "Best-known")


def test_usage_scopes_and_session_pending():
    snapshot = _demo_snapshot()
    usage = snapshot.usage
    assert usage.total_aiu == 4.2 + 1.4 + 0.7
    assert usage.pi_aiu == 4.2
    assert usage.coder_aiu == 1.4
    assert usage.reviewer_aiu == 0.7
    assert usage.input_tokens == 80_000  # token-only row keeps its own scope
    text = projector.usage_text(usage)
    assert "Copilot AIU" in text
    assert "coder 1.40" in text
    assert "session S7 accounting pending" in text


def test_usage_text_contains_no_monetary_fields():
    text = projector.usage_text(_demo_snapshot().usage)
    lowered = text.lower()
    for forbidden in ("$", "price", "cost", "eur", "usd"):
        assert forbidden not in lowered


def test_question_prefers_active_inquiry_object():
    snapshot = _demo_snapshot()
    assert snapshot.question_source == "inquiry I3"
    assert snapshot.question.startswith("Does longer settling improve hold stability")


def test_question_falls_back_to_pi_record():
    state, _, _ = _observation_args()
    state["active_inquiry"] = None
    state["pi_checkpoint"]["next_question"] = (
        "Does the gate transfer as a learned candidate?"
    )
    snapshot = projector.build_snapshot(state, [], [])
    assert snapshot.question == "Does the gate transfer as a learned candidate?"
    assert snapshot.question_source == "PI record"


def test_stage_and_terminal_status():
    snapshot = _demo_snapshot()
    assert snapshot.stage_text == "Inquiry I3 / S7"
    state, _, _ = _observation_args()
    state["active_inquiry"] = None
    state["scientific_session"] = {
        "id": "S9",
        "kind": "goal_review",
        "inquiry_id": None,
    }
    review = projector.build_snapshot(state, [], [])
    assert review.stage_text == "Goal review S9"
    state["terminal_state"] = "completed"
    ended = projector.build_snapshot(state, [], [])
    assert ended.terminal
    assert ended.status.startswith("ENDED")
    assert ended.model_rows  # role assignments remain readable after the end


def test_timeline_pending_accepted_is_not_execution():
    snapshot = _demo_snapshot()
    kinds = [entry.kind for entry in snapshot.timeline]
    assert "pending" in kinds
    pending = snapshot.timeline[0]
    assert "accepted" in pending.text
    assert "execution" in pending.text


def test_timeline_failed_operation_is_explicit_error():
    state, records, _ = _observation_args()
    records.append(
        {
            "id": "M8",
            "kind": "measurement",
            "status": "failed",
            "completed_at": _now().isoformat(),
            "error": "evaluation runner exited 1",
            "request": {},
            "result": {},
        }
    )
    snapshot = projector.build_snapshot(state, records, [])
    failures = [entry for entry in snapshot.timeline if entry.kind == "error"]
    assert failures and "M8: measurement failed" in failures[-1].text


def test_role_assignment_entry_is_readable():
    state, records, _ = _observation_args()
    snapshot = projector.build_snapshot(state, records, [])
    roles = [entry for entry in snapshot.timeline if entry.kind == "role"]
    assert (
        roles
        and roles[0].text
        == "PI assigned best known to T2:checkpoint-90000 (evidence T2, M5)"
    )


def test_activity_for_pending_operation_does_not_claim_execution():
    snapshot = _demo_snapshot()
    assert snapshot.activity_text == (
        "M6 measurement accepted - execution not observed"
    )


def test_unrecogized_candidate_metrics_stay_unavailable():
    state, _, _ = _observation_args()
    state["model_roles"]["best_known"] = "T9:checkpoint-1"
    rows = projector.build_snapshot(state, [], []).model_rows
    best = next(row for row in rows if row.candidate_id == "T9:checkpoint-1")
    assert best.reward_training == "unavailable"
    assert best.success_training == "unavailable"
    assert best.success_dev == "not measured"
    assert best.training_steps == "unavailable"


def test_activity_after_completed_operation_is_explicit():
    state, records, _ = _observation_args()
    state["pending_operation"] = None
    snapshot = projector.build_snapshot(state, records, [])
    assert snapshot.activity_text == (
        "last completed E14 inquiry - live activity not observed"
    )


def test_stage_ids_goal_counters_and_pending():
    snapshot = _demo_snapshot()
    assert snapshot.stage_ids == "I3 / S7 / T4 / M5 / E13"
    assert snapshot.goal.target_percent == 98.0
    assert snapshot.goal.best_percent == 94.0
    assert snapshot.goal.gap_points == -4.0
    assert snapshot.counters_text == (
        "Inquiries 3/15 | Trainings 4 | Measurements 5 | Sessions 7"
    )
    assert snapshot.pending_text == "Pending M6 measurement (S7 / I3)"


def test_goal_gap_text_falls_back_to_checkpoint():
    state, _, _ = _observation_args()
    state["pi_checkpoint"]["current_goal_gap"] = (
        "Best development success is still below the target."
    )
    snapshot = projector.build_snapshot(state, [], [])
    assert snapshot.goal.gap_points is None
    assert snapshot.goal.gap_text == (
        "Best development success is still below the target."
    )


def test_last_training_proxy_prefers_training_success():
    records = [
        {
            "id": "T7",
            "kind": "training",
            "status": "completed",
            "result": {
                "candidates": ["T7:checkpoint-10", "T7:checkpoint-20"],
                "learning_dynamics": [
                    {
                        "candidate": "T7:checkpoint-10",
                        "training_steps": 10,
                        "training_success": 0.5,
                        "ep_rew_mean": 10.0,
                    },
                    {
                        "candidate": "T7:checkpoint-20",
                        "training_steps": 20,
                        "training_success": 0.9,
                        "ep_rew_mean": 8.0,
                    },
                ],
            },
        }
    ]
    snapshot = projector.build_snapshot({}, records, [])
    proxy = snapshot.last_training
    assert proxy is not None
    assert proxy.operation_id == "T7"
    assert proxy.candidate == "T7:checkpoint-20"
    assert proxy.steps == "20"
    assert proxy.reward == "8.0"
    assert proxy.success == "90%"


def test_last_training_proxy_falls_back_to_reward():
    records = [
        {
            "id": "T8",
            "kind": "training",
            "status": "completed",
            "result": {
                "candidates": ["T8:checkpoint-10", "T8:checkpoint-20"],
                "learning_dynamics": [
                    {
                        "candidate": "T8:checkpoint-10",
                        "training_steps": 10,
                        "ep_rew_mean": 12.0,
                    },
                    {
                        "candidate": "T8:checkpoint-20",
                        "training_steps": 20,
                        "ep_rew_mean": 9.0,
                    },
                ],
            },
        }
    ]
    proxy = projector.build_snapshot({}, records, []).last_training
    assert proxy is not None
    assert proxy.candidate == "T8:checkpoint-10"
    assert proxy.success == "unavailable"


def test_goal_gap_uses_human_goal_dict_and_best_development():
    state, _, _ = _observation_args()
    state["human_goal"] = {
        "source": "contracts/scenario.md",
        "summary": "Reach at least 98% success on the official panel.",
    }
    records = [
        {
            "id": "M9",
            "kind": "measurement",
            "status": "completed",
            "completed_at": _now().isoformat(),
            "request": {},
            "result": {
                "measurements": [
                    {
                        "candidate_id": "T4:checkpoint-120000",
                        "instrument": "task_reference",
                        "metrics": {"success_percent": 68.1, "episodes": 100},
                    }
                ]
            },
        }
    ]
    snapshot = projector.build_snapshot(state, records, [])
    assert snapshot.goal.text.startswith("Reach at least 98%")
    assert snapshot.goal.target_percent == 98.0
    assert snapshot.goal.best_percent == 68.1
    assert snapshot.goal.gap_points == -29.9
