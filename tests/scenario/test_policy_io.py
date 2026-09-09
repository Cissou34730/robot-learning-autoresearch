import numpy as np

from robot_learning.scenario.policy_io import physical_action


def test_physical_action_preserves_direction_and_saturation():
    action = physical_action(np.array([-1.0, -0.5, 0.0, 0.5, 1.0]))

    np.testing.assert_allclose(action, [-1.0, -0.4375, 0.0, 0.4375, 1.0])
