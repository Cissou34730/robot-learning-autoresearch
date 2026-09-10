import numpy as np

from robot_learning.scenario.policy_io import ACTION_SCALE, physical_action


def test_physical_action_attenuates_each_joint_command():
    action = np.array([0.8, -0.4], dtype=np.float32)

    np.testing.assert_allclose(
        physical_action(action),
        ACTION_SCALE * action,
    )
