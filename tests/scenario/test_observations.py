"""Tests for the scenario's policy observation representation."""

from types import SimpleNamespace

import numpy as np

from robot_learning.scenario.observations import OBSERVATION_SIZE, reach_observation


def _observation_data():
    return SimpleNamespace(
        mocap_pos=np.array([[0.0, -0.15, 0.02]]),
        qpos=np.zeros(2),
        qvel=np.zeros(2),
        site=lambda name: SimpleNamespace(
            xpos=np.array([0.12, 0.0, 0.02])
        ),
    )


def test_observation_uses_periodic_features_for_each_ik_branch_error():
    observation = reach_observation(_observation_data())

    assert OBSERVATION_SIZE == 15
    assert observation.shape == (OBSERVATION_SIZE,)
    branch_features = observation[-8:].reshape(4, 2)
    assert np.allclose(np.sum(branch_features**2, axis=1), 1.0)
