import hashlib

import numpy as np
import pytest

from robot_learning.benchmark.metrics import achieved_goal
from robot_learning.benchmark.spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


def test_robot_physics_asset_is_frozen():
    digest = hashlib.sha256(TWO_JOINT_ARM_XML_PATH.read_bytes()).hexdigest()
    assert digest == "6ccb918656b92a931927e2bfd90378d915da009b741155c7cafc5913b9f87f62"


def test_final_task_contract_is_fixed():
    env = TwoJointArmReachEnv()
    assert env.success_threshold == pytest.approx(SUCCESS_THRESHOLD)
    control_dt = env.model.opt.timestep * env.frame_skip
    assert env.hold_steps_required == round(HOLD_SECONDS / control_dt)
    assert env.target_radius_range == TARGET_RADIUS_RANGE
    assert env.frame_skip == FRAME_SKIP
    assert env.max_episode_steps == MAX_EPISODE_STEPS


def test_seed_produces_reproducible_fixed_distribution():
    env_a, env_b = TwoJointArmReachEnv(), TwoJointArmReachEnv()
    env_a.reset(seed=42)
    env_b.reset(seed=42)
    assert np.allclose(env_a.data.mocap_pos[0], env_b.data.mocap_pos[0])
    radius = float(np.linalg.norm(env_a.data.mocap_pos[0][:2]))
    assert TARGET_RADIUS_RANGE[0] <= radius <= TARGET_RADIUS_RANGE[1]


def test_final_hold_requires_100_consecutive_steps():
    env = TwoJointArmReachEnv()
    env.reset(seed=0)
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    for step in range(100):
        _, _, terminated, truncated, info = env.step(np.zeros(2))
        assert not truncated
        assert terminated is (step == 99)
    assert info["held_steps"] == 100


def test_fixed_metric_requires_the_complete_hold():
    assert not achieved_goal([0.005] * 99, control_dt=0.02)
    assert achieved_goal([0.005] * 100, control_dt=0.02)
