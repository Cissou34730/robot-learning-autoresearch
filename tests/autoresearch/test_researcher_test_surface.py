"""No test path belongs to the Researcher's write surface.

Issue #30: a rejected proposal once told the Researcher to restore a human-owned
test file it does not own, and the Researcher then edited that file. The
ownership rejection must never prescribe an edit to an unowned path: it names the
paths and tells the Researcher to drop them from the proposal instead.
"""

import pytest

from research import runner_protocol as protocol
from research.runner_protocol import (
    NOT_OWNED_PATHS_REMEDY,
    TEST_SURFACE_REJECTION,
    is_researcher_owned,
    validate_experiment_semantics,
    validate_research_delta_ownership,
)

RESEARCHER_PATH = "robot_learning/scenario/reward.py"
TEST_PATHS = (
    "tests/scenario/test_reward.py",
    "tests/training/test_policy.py",
    "tests/autoresearch/test_scenario_boundary.py",
    "tests/benchmark/test_task_contract.py",
    "tests/e2e/test_reset_research.py",
    "tests/conftest.py",
)


def test_no_researcher_owned_prefix_covers_the_test_tree():
    assert not any(
        prefix.startswith("tests/") for prefix in protocol.RESEARCHER_OWNED_PREFIXES
    )


@pytest.mark.parametrize("path", TEST_PATHS)
def test_a_test_path_is_never_researcher_owned(path):
    assert not is_researcher_owned(path)


@pytest.mark.parametrize("path", TEST_PATHS)
def test_a_proposal_delta_containing_a_test_path_is_rejected(path):
    with pytest.raises(ValueError, match="not part of the researcher's surface"):
        validate_research_delta_ownership([RESEARCHER_PATH, path])


def test_the_rejection_names_the_paths_and_prescribes_dropping_them():
    offending = ["tests/scenario/test_reward.py", "tests/training/test_policy.py"]
    expected = f"{TEST_SURFACE_REJECTION}: {sorted(offending)}; {NOT_OWNED_PATHS_REMEDY}"

    with pytest.raises(ValueError) as error:
        validate_research_delta_ownership([RESEARCHER_PATH, *offending])

    message = str(error.value)
    assert message == expected
    for path in offending:
        assert path in message
    # The regression this locks: the message never tells the Researcher to edit,
    # restore or otherwise modify a path it does not own.
    assert "restore" not in message
    assert "edit" not in message
    assert "modify" not in message


def test_the_remedy_sentence_is_exact():
    assert NOT_OWNED_PATHS_REMEDY == (
        "drop those paths from the proposal, because they are not the "
        "researcher's changes to make"
    )


def test_a_proposal_delta_of_researcher_owned_paths_still_validates():
    validate_research_delta_ownership(
        ["robot_learning/scenario/reward.py", "robot_learning/training/algorithms.py"]
    )
    validate_experiment_semantics(
        {},
        "training",
        "transfer",
        None,
        ["robot_learning/scenario/reward.py"],
        False,
    )
