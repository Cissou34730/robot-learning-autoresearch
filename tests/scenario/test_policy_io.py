import numpy as np

from robot_learning.scenario.policy_io import ACTION_SCALE, physical_action


def test_physical_action_reduces_policy_command_authority():
    action = np.array([1.0, -0.5])

    np.testing.assert_allclose(
        physical_action(action),
        action * ACTION_SCALE,
    )
