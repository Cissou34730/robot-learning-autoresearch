"""Researcher-owned tests for geometry-aware policy observations."""

import mujoco
import numpy as np
import pytest

from robot_learning.scenario.environment import make_training_env
from robot_learning.scenario.observations import reach_observation


def _observation_for_target(env, angle_degrees: float) -> np.ndarray:
    angle = np.radians(angle_degrees)
    env.data.mocap_pos[0][:] = [
        0.12 * np.cos(angle),
        0.12 * np.sin(angle),
        env.data.site("end_effector").xpos[2],
    ]
    mujoco.mj_forward(env.model, env.data)
    return reach_observation(env.data)


def test_observation_uses_the_redundant_planar_slot_for_branch_preference():
    env = make_training_env()
    env.reset(seed=0)

    observation = _observation_for_target(env, -135.0)

    assert observation.shape == (11,)
    assert observation[6] > 0.0
    assert -1.0 <= observation[6] <= 1.0


def test_branch_preference_reverses_for_mirrored_targets():
    env = make_training_env()
    env.reset(seed=0)

    negative = _observation_for_target(env, -135.0)[6]
    positive = _observation_for_target(env, 135.0)[6]

    assert negative == pytest.approx(-positive)
