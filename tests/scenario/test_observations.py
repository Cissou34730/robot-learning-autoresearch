import mujoco
import numpy as np

from robot_learning.scenario.environment import make_training_env
from robot_learning.scenario.observations import (
    OBSERVATION_SCALE,
    reach_observation,
)


def test_reach_observation_scales_each_physical_feature_group():
    env = make_training_env()
    env.reset(seed=0)
    env.data.qpos[:] = [np.pi, -np.pi]
    env.data.qvel[:] = [10.0, -10.0]
    mujoco.mj_forward(env.model, env.data)

    observation = reach_observation(env.data)

    assert np.allclose(observation[:4], [1.0, -1.0, 1.0, -1.0])
    assert np.allclose(OBSERVATION_SCALE[:2], [np.pi, np.pi])
    assert np.allclose(OBSERVATION_SCALE[2:4], [10.0, 10.0])
    assert np.allclose(OBSERVATION_SCALE[4:7], [0.22, 0.22, 0.22])
    assert np.allclose(OBSERVATION_SCALE[7:], [np.pi] * 4)
