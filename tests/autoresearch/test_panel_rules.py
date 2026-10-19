"""Protected-panel boundaries and removal of the stopping machinery."""

import ast
from pathlib import Path

import pytest

from benchmark import final_contract
from benchmark.adapters.final_benchmark import research_panel_overlaps_protected
from runner import protocol

ROOT = Path(__file__).resolve().parents[2]


def _request(
    panels: list[tuple[int, int]], *, instrument: str = "research_evaluation"
) -> dict:
    measurements = []
    for index, (seed, episodes) in enumerate(panels):
        entry: dict = {
            "instrument": instrument,
            "candidate": f"candidate-{index}",
        }
        if instrument == "research_evaluation":
            entry.update({"seed": seed, "episodes": episodes})
        measurements.append(entry)
    return {
        "description": "Measure a development panel.",
        "rationale": "The PI will interpret the factual result.",
        "measurements": measurements,
    }


def test_official_panel_overlap_is_rejected():
    request = _request([(final_contract.EVALUATION_SEED, 10)])
    protocol.validate_measurement_request(request)
    with pytest.raises(ValueError, match="protected benchmark evidence"):
        protocol.validate_panel_independence(
            request, protected_overlap=research_panel_overlaps_protected
        )


def test_generic_runner_does_not_read_the_protected_panel():
    for relative in ("runner/protocol.py", "runner/run_experiment.py"):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not (
                    node.module.startswith("benchmark")
                    and not node.module.startswith("benchmark.adapters")
                ), (
                    relative,
                    node.module,
                )

    # `runner.protocol` is not a sanctioned scenario importer either.
    tree = ast.parse((ROOT / "runner" / "protocol.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("robot_learning.scenario"), node.module


def test_development_panel_overlap_is_not_runner_policy():
    protocol.validate_panel_independence(_request([(100, 200), (150, 200)]))


def test_task_reference_panel_is_not_checked():
    protocol.validate_panel_independence(
        _request([(0, 0)], instrument="task_reference")
    )


def test_request_without_purpose_is_accepted():
    protocol.validate_measurement_request(_request([(100, 200)]))


def test_terminal_validation_machinery_is_removed():
    assert not hasattr(protocol, "validate_terminal_validation_request")
    assert not hasattr(protocol, "normalize_measurement_purposes")
    assert not hasattr(protocol, "MEASUREMENT_PURPOSES")
    assert not (ROOT / "research" / "stopping_policy.py").exists()
    assert not (ROOT / "research" / "stopping_contract.md").exists()
