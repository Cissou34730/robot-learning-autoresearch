"""Tests for the scenario policy input/output contract."""

import numpy as np

from robot_learning.scenario.policy_io import ACTION_DEADBAND, physical_action


def test_physical_action_applies_a_continuous_deadband():
    action = physical_action(np.array([-0.2, -ACTION_DEADBAND, -0.05, 0.0, 0.05, 0.2]))

    np.testing.assert_array_equal(
        action,
        np.array([-0.1, 0.0, 0.0, 0.0, 0.0, 0.1], dtype=np.float32),
    )
