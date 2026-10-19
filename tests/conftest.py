"""Load scientific test subjects from the explicitly selected campaign."""

import pytest

from runner import paths


def pytest_report_header():
    if not (paths.ROOT / "robot_learning").is_dir():
        raise pytest.UsageError(
            "Select an initialized campaign with ROBOT_LEARNING_CAMPAIGN_ROOT "
            "before running harness tests."
        )
    return f"Harness: {paths.HARNESS_ROOT}; campaign: {paths.ROOT}"


@pytest.fixture(autouse=True)
def _single_root_sandbox(monkeypatch):
    monkeypatch.setattr(paths, "SPLIT", False)
