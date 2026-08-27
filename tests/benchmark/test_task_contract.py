import hashlib

import numpy as np
import pytest

from robot_learning.benchmark.metrics import achieved_milestones
from robot_learning.benchmark.spec import (
    CURRICULUM_STAGES,
    FINAL_STAGE_INDEX,
    FRAME_SKIP,
    MAX_EPISODE_STEPS,
    TARGET_RADIUS_RANGE,
)
from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


def test_robot_physics_asset_is_frozen():
    digest = hashlib.sha256(TWO_JOINT_ARM_XML_PATH.read_bytes()).hexdigest()
    assert digest == "6ccb918656b92a931927e2bfd90378d915da009b741155c7cafc5913b9f87f62"


def test_final_task_contract_is_fixed():
    env = TwoJointArmReachEnv()
    assert env._stage_index == FINAL_STAGE_INDEX
    assert env.success_threshold == pytest.approx(0.01)
    assert env.hold_steps_required == 100
    assert env.target_radius_range == TARGET_RADIUS_RANGE
    assert env.frame_skip == FRAME_SKIP
    assert env.max_episode_steps == MAX_EPISODE_STEPS


def test_curriculum_contract_is_progressive():
    assert CURRICULUM_STAGES == (
        (0.03, 0.02), (0.02, 0.02), (0.01, 0.02), (0.01, 0.10),
        (0.01, 0.50), (0.01, 1.00), (0.01, 1.50), (0.01, 2.00),
    )


def test_stage_is_imposed_and_never_self_advances():
    env = TwoJointArmReachEnv(stage_index=0)
    for episode in range(20):
        env.reset(seed=episode)
        env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
        env.step(np.zeros(2))
    assert env._stage_index == 0
    assert env.success_threshold == pytest.approx(0.03)


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


def test_fixed_metrics_measure_touch_and_hold_separately():
    touch = achieved_milestones([0.05, 0.015, 0.04], control_dt=0.02)
    assert touch[:2] == [True, True]
    assert touch[2:] == [False] * 6
    half_second = achieved_milestones([0.005] * 25, control_dt=0.02)
    assert half_second[:5] == [True] * 5
    assert half_second[5:] == [False] * 3
