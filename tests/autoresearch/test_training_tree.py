"""Tests for the recorded relationships shown in the training tree."""

from tui.training_tree import build_training_tree


def test_training_tree_links_measurements_and_transfer_by_candidate_identity():
    records = [
        {
            "id": "T1",
            "kind": "training",
            "status": "completed",
            "result": {
                "initialization": "fresh",
                "candidates": ["T1:checkpoint-60000", "T1:checkpoint-120000"],
                "learning_dynamics": [
                    {"candidate": "T1:checkpoint-60000", "training_steps": 60000},
                    {"candidate": "T1:checkpoint-120000", "training_steps": 120000},
                ],
            },
        },
        {
            "id": "M1",
            "kind": "measurement",
            "status": "completed",
            "result": {
                "measurements": [
                    {
                        "candidate": "T1:checkpoint-120000",
                        "instrument": "research_evaluation",
                        "metrics": {"success_percent": 74, "episodes": 100},
                    },
                    {
                        "candidate": "missing:checkpoint",
                        "instrument": "task_reference",
                        "metrics": {"success_percent": 25, "episodes": 160},
                    },
                ]
            },
        },
        {
            "id": "T2",
            "kind": "training",
            "status": "completed",
            "result": {
                "initialization": "transfer",
                "parent": "T1:checkpoint-120000",
                "candidates": ["T2:checkpoint-120000"],
            },
        },
    ]
    roots = build_training_tree({}, records)
    training = roots[0]
    first, second = training.children
    assert not first.children
    assert [item.kind for item in second.children] == ["training", "measurement"]
    transfer, measurement = second.children
    assert transfer.children[0].detail == ("Candidate: T2:checkpoint-120000",)
    assert measurement.summary.startswith("success 74%")
    assert roots[1].children[0].detail[1] == "Candidate: missing:checkpoint"


def test_recipe_archive_is_kept_separate_from_current_candidate_identities():
    training = {
        "id": "T1",
        "kind": "training",
        "status": "completed",
        "result": {"candidates": ["T1:checkpoint-10"]},
    }
    measurement = {
        "id": "M1",
        "kind": "measurement",
        "status": "completed",
        "result": {
            "measurements": [
                {"candidate": "T1:checkpoint-10", "metrics": {"success_percent": 50}}
            ]
        },
    }
    roots = build_training_tree(
        {}, [measurement], archived_state={"campaign": {}}, archived_records=[training]
    )
    assert roots[0].item_id == "recipe:root"
    assert not roots[0].children[0].children[0].children
    assert roots[1].children[0].item_id.startswith("campaign:measurement:")


def test_pending_measurement_uses_frozen_candidate_and_shows_pending_result():
    training = {
        "id": "T1",
        "kind": "training",
        "status": "completed",
        "result": {"candidates": ["T1:checkpoint-10"]},
    }
    state = {
        "pending_operation": {
            "id": "M1",
            "kind": "measurement",
            "progress": "accepted",
            "data": {
                "measurements": [
                    {
                        "candidate_id": "T1:checkpoint-10",
                        "instrument": "research_evaluation",
                    }
                ],
                "partial_results": [],
            },
        }
    }
    interrupted = {"id": "M1", "kind": "measurement", "status": "interrupted"}
    roots = build_training_tree(state, [training, interrupted])
    measurement = roots[0].children[0].children[0]
    assert measurement.title.startswith("M1")
    assert "result pending" in measurement.summary
    state["pending_operation"]["failure"] = "measurement failed"
    failed = build_training_tree(state, [training, interrupted])
    assert "failed" in failed[0].children[0].children[0].summary
    assert "result unavailable" in failed[0].children[0].children[0].summary


def test_variant_checkpoints_keep_each_panel_of_a_shared_measurement():
    training = {
        "id": "T1",
        "kind": "training",
        "status": "completed",
        "result": {
            "variants": [
                {"label": "a", "candidates": ["T1:a-checkpoint-10"]},
                {"label": "b", "candidates": ["T1:b-checkpoint-10"]},
            ]
        },
    }
    measurement = {
        "id": "M1",
        "kind": "measurement",
        "status": "completed",
        "result": {
            "measurements": [
                {"candidate": "T1:a-checkpoint-10", "metrics": {"success_percent": 30}},
                {"candidate": "T1:b-checkpoint-10", "metrics": {"success_percent": 70}},
            ]
        },
    }
    roots = build_training_tree({}, [training, measurement])
    assert [root.title for root in roots] == ["T1:a Training", "T1:b Training"]
    assert roots[0].children[0].children[0].summary.startswith("success 30%")
    assert roots[1].children[0].children[0].summary.startswith("success 70%")
