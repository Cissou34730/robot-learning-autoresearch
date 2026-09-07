from types import SimpleNamespace

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation


class FakeData:
    def __init__(self):
        self.mocap_pos = np.array([[0.08, -0.14, 0.02]], dtype=np.float64)
        self.qpos = np.array([0.2, -0.4], dtype=np.float64)
        self.qvel = np.array([0.3, -0.1], dtype=np.float64)
        self._end_effector = np.array([0.04, -0.12, 0.02], dtype=np.float64)

    def site(self, name):
        assert name == "end_effector"
        return SimpleNamespace(xpos=self._end_effector)


def test_observation_uses_periodic_ik_residuals_without_changing_shape():
    data = FakeData()
    observation = reach_observation(data)

    target_x, target_y = data.mocap_pos[0][:2]
    elbow_open = np.arccos(
        np.clip(
            (target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2)
            / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
            -1.0,
            1.0,
        )
    )

    def shoulder_for_elbow(elbow):
        return np.arctan2(target_y, target_x) - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )

    elbow_folded = -elbow_open
    expected_residuals = np.array(
        [
            shoulder_for_elbow(elbow_open) - data.qpos[0],
            elbow_open - data.qpos[1],
            shoulder_for_elbow(elbow_folded) - data.qpos[0],
            elbow_folded - data.qpos[1],
        ]
    )
    expected_residuals = (expected_residuals + np.pi) % (2.0 * np.pi) - np.pi

    assert observation.shape == (11,)
    assert np.all(np.isfinite(observation))
    np.testing.assert_allclose(observation[7:], np.sin(expected_residuals), atol=1e-6)
