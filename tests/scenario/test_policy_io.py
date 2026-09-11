import numpy as np

from robot_learning.scenario.policy_io import make_policy_io


def test_action_mapping_smooths_command_changes():
    policy_io = make_policy_io()

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])
    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.75, -0.75])


def test_action_mapping_reset_clears_previous_command():
    policy_io = make_policy_io()
    policy_io.action(np.array([1.0, -1.0]))

    assert policy_io.reset is not None
    policy_io.reset()

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])
