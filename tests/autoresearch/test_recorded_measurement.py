import pytest

from runner.proportion_interval import (
    RecordedReference,
    recorded_counts,
    recorded_measurement,
)


def _research(candidate, successes, seed=100000, label="run"):
    return {
        "instrument": "research_evaluation",
        "candidate": candidate,
        "label": label,
        "metrics": {
            "seed": seed,
            "episodes": 400,
            "successes": successes,
            "evaluation_semantics": "s1",
        },
    }


def _reference(candidate, successes, label="run"):
    return {
        "instrument": "task_reference",
        "candidate": candidate,
        "label": label,
        "metrics": {
            "panel": "task-reference",
            "panel_version": "v1",
            "episodes": 200,
            "successes": successes,
        },
    }


def _state():
    def event(operation_id, *items):
        return {
            "id": operation_id,
            "kind": "measurement",
            "status": "completed",
            "result": {"measurements": list(items)},
        }

    return {
        "operation_events": [
            event("M1", _reference("T2:a", 195)),
            event("M2", _reference("T2:b", 197), _research("T2:b", 390, seed=200000)),
            event("M3", _research("T3:c", 388), _reference("T3:c", 196)),
        ]
    }


def test_instrument_selects_one_of_two_measurements_with_the_same_label():
    state = _state()
    with pytest.raises(ValueError, match="has 2 measurements"):
        recorded_measurement(
            state, RecordedReference(operation_id="M3", candidate="T3:c")
        )

    _, item = recorded_measurement(
        state,
        RecordedReference(
            operation_id="M3", candidate="T3:c", instrument="task_reference"
        ),
    )

    assert item["metrics"]["successes"] == 196


def test_recorded_source_lists_the_candidates_measured_on_the_same_episodes():
    reference = RecordedReference(
        operation_id="M2", candidate="T2:b", instrument="task_reference"
    )

    [source] = recorded_counts(_state(), [reference])["sources"]

    assert source["candidates_measured_on_these_episodes"] == 3
    assert [
        entry["candidate"] for entry in source["measurements_on_these_episodes"]
    ] == [
        "T2:b",
        "T3:c",
        "T2:a",
    ]
