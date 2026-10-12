"""Laboratory verification for the training-only safe-IK trajectory intervention.

This executable check uses independent planar kinematics and limit calculations
to test the production training environment.  It is not a training run and
does not claim scientific validity.
"""

import argparse
import json
from itertools import product
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.environment import (
    SAFE_BRANCH_POTENTIAL_COEFFICIENT,
    SafeBranchTrajectoryEnv,
)

TWO_PI = 2.0 * np.pi


def _wrapped_delta(positions: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return (positions - reference + np.pi) % TWO_PI - np.pi


def _reference_potential(positions: np.ndarray, reference: np.ndarray) -> float:
    distance = float(np.linalg.norm(_wrapped_delta(positions, reference)))
    return 1.0 - distance / (np.sqrt(2.0) * np.pi)


def _representations(angle: float, lower: float, upper: float) -> tuple[float, ...]:
    first = int(np.ceil((lower - angle) / TWO_PI))
    last = int(np.floor((upper - angle) / TWO_PI))
    return tuple(float(angle + TWO_PI * turn) for turn in range(first, last + 1))


def _reference_candidates(
    target_xy: np.ndarray, joint_ranges: np.ndarray
) -> tuple[tuple[int, np.ndarray, float], ...]:
    x, y = np.asarray(target_xy, dtype=np.float64)
    cosine = (
        x * x
        + y * y
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if not -1.0 <= cosine <= 1.0:
        raise AssertionError("verification target is geometrically impossible")
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(y, x))
    candidates = []
    for branch, elbow in enumerate((elbow_magnitude, -elbow_magnitude)):
        shoulder = float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        shoulders = _representations(
            shoulder, float(joint_ranges[0, 0]), float(joint_ranges[0, 1])
        )
        elbows = _representations(
            elbow, float(joint_ranges[1, 0]), float(joint_ranges[1, 1])
        )
        for values in product(shoulders, elbows):
            reference = np.asarray(values, dtype=np.float64)
            half_ranges = 0.5 * (joint_ranges[:, 1] - joint_ranges[:, 0])
            margin = float(
                np.min(
                    np.minimum(
                        reference - joint_ranges[:, 0],
                        joint_ranges[:, 1] - reference,
                    )
                    / half_ranges
                )
            )
            candidates.append((branch, reference, margin))
    return tuple(candidates)


def _reference_selection(
    target_xy: np.ndarray, joint_ranges: np.ndarray
) -> tuple[int, np.ndarray, float]:
    candidates = _reference_candidates(target_xy, joint_ranges)
    feasible = [candidate for candidate in candidates if candidate[2] >= 0.0]
    if not feasible:
        raise AssertionError("verification target has no feasible branch")
    return max(
        feasible,
        key=lambda candidate: (
            candidate[2],
            -float(np.linalg.norm(_wrapped_delta(candidate[1], np.zeros(2)))),
            -candidate[0],
        ),
    )


def _branch_counts(
    target_xy: np.ndarray, joint_ranges: np.ndarray
) -> tuple[int, int]:
    candidates = _reference_candidates(target_xy, joint_ranges)
    return tuple(
        sum(candidate[0] == branch and candidate[2] >= 0.0 for candidate in candidates)
        for branch in (0, 1)
    )


def _find_targets(
    joint_ranges: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    one_target = None
    two_target = None
    for radius in np.linspace(0.06, 0.20, 15):
        for angle in np.linspace(-np.pi, np.pi, 73):
            target = np.asarray(
                [radius * np.cos(angle), radius * np.sin(angle)],
                dtype=np.float64,
            )
            counts = _branch_counts(target, joint_ranges)
            branch_count = int(sum(count > 0 for count in counts))
            if branch_count == 1 and one_target is None:
                one_target = target
            if branch_count == 2 and two_target is None:
                two_target = target
            if one_target is not None and two_target is not None:
                return one_target, two_target
    raise AssertionError("compiled joint limits did not expose both branch cases")


def _set_target(env: SafeBranchTrajectoryEnv, target_xy: np.ndarray) -> None:
    target_z = float(env.data.site("end_effector").xpos[2])
    env.data.mocap_pos[0] = [float(target_xy[0]), float(target_xy[1]), target_z]
    mujoco.mj_forward(env.model, env.data)
    env._select_safe_reference()


def _set_joint_state(
    env: SafeBranchTrajectoryEnv, positions: np.ndarray, velocities: np.ndarray
) -> None:
    for index in range(2):
        env.data.qpos[int(env.model.jnt_qposadr[index])] = float(positions[index])
        env.data.qvel[int(env.model.jnt_dofadr[index])] = float(velocities[index])
    mujoco.mj_forward(env.model, env.data)


def _behavioral_check(output: Path) -> None:
    env = SafeBranchTrajectoryEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=20,
    )
    observation, _ = env.reset(seed=1729)
    assert isinstance(env, SafeBranchTrajectoryEnv)
    assert observation.shape == env.observation_space.shape
    assert observation.shape == (11,)
    joint_ranges = np.asarray(env.model.jnt_range[:2], dtype=np.float64).copy()
    one_target, two_target = _find_targets(joint_ranges)
    env.data.mocap_pos[0] = [0.0, 0.0, float(env.data.mocap_pos[0, 2])]
    mujoco.mj_forward(env.model, env.data)
    try:
        env._select_safe_reference()
    except ValueError:
        impossible_target_rejected = True
    else:
        impossible_target_rejected = False
    assert impossible_target_rejected

    branch_observations = []
    branch_results = []
    for target in (one_target, two_target):
        _set_target(env, target)
        expected = _reference_selection(target, joint_ranges)
        actual = (
            env.safe_branch_index,
            env.safe_reference,
            env.safe_reference_margin,
        )
        expected_count = sum(
            candidate[2] >= 0.0
            for candidate in _reference_candidates(target, joint_ranges)
        )
        branch_observations.append(
            {
                "target": target.tolist(),
                "feasible_branch_count": int(
                    len(
                        {
                            candidate[0]
                            for candidate in _reference_candidates(
                                target, joint_ranges
                            )
                            if candidate[2] >= 0.0
                        }
                    )
                ),
                "feasible_representation_count": int(expected_count),
            }
        )
        assert actual[0] == expected[0]
        assert np.allclose(actual[1], expected[1])
        assert np.isclose(actual[2], expected[2])
        best_margin = max(
            candidate[2]
            for candidate in _reference_candidates(target, joint_ranges)
            if candidate[2] >= 0.0
        )
        assert np.isclose(actual[2], best_margin)
        branch_results.append(
            {
                "expected_branch": int(expected[0]),
                "selected_branch": int(actual[0]),
                "selected_reference": actual[1].tolist(),
                "selected_margin": float(actual[2]),
            }
        )
    assert branch_observations[0]["feasible_branch_count"] == 1
    assert branch_observations[1]["feasible_branch_count"] == 2

    reference = env.safe_reference
    start = reference + np.asarray([0.8, -0.7])
    toward = reference + np.asarray([0.3, -0.25])
    away = reference + np.asarray([1.2, -1.0])
    expected_toward = _reference_potential(toward, reference) - _reference_potential(
        start, reference
    )
    expected_away = _reference_potential(away, reference) - _reference_potential(
        start, reference
    )
    production_toward = env._safe_potential(toward, reference) - env._safe_potential(
        start, reference
    )
    production_away = env._safe_potential(away, reference) - env._safe_potential(
        start, reference
    )
    assert expected_toward > 0.0 and expected_away < 0.0
    assert np.isclose(production_toward, expected_toward)
    assert np.isclose(production_away, expected_away)
    assert abs(SAFE_BRANCH_POTENTIAL_COEFFICIENT * expected_toward) <= 1.0
    assert abs(SAFE_BRANCH_POTENTIAL_COEFFICIENT * expected_away) <= 1.0

    # A controlled velocity makes the next real production transition move
    # toward the selected reference; the component must match the independent
    # potential difference, rather than merely being present in info.
    env.reset(seed=1729)
    _set_target(env, two_target)
    zero = np.zeros(2, dtype=np.float64)
    velocity_direction = np.sign(env.safe_reference)
    velocity_direction[velocity_direction == 0.0] = 1.0
    _set_joint_state(env, zero, 10.0 * velocity_direction)
    env._previous_distance = env._distance_to_target()
    before = np.asarray(env.data.qpos[env.model.jnt_qposadr[:2]], dtype=np.float64)
    _, _, _, _, transition_info = env.step(np.zeros(2))
    after = np.asarray(env.data.qpos[env.model.jnt_qposadr[:2]], dtype=np.float64)
    expected_transition = SAFE_BRANCH_POTENTIAL_COEFFICIENT * (
        _reference_potential(after, env.safe_reference)
        - _reference_potential(before, env.safe_reference)
    )
    observed_transition = transition_info["reward_components"][
        "safe_branch_potential"
    ]
    assert np.isfinite(observed_transition)
    assert np.isclose(observed_transition, expected_transition)
    assert abs(observed_transition) <= SAFE_BRANCH_POTENTIAL_COEFFICIENT + 1e-12
    assert observed_transition > 0.0

    # The wrapper must preserve the complete base transition.  Compare one
    # controlled transition with the unshaped scenario environment so a
    # duplicated physics/hold/reward path cannot satisfy the potential check
    # merely by producing a plausible second state.
    mechanics_reference = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=20,
    )
    env.reset(seed=1740)
    _set_target(env, two_target)
    mechanics_reference.reset(seed=1740)
    mechanics_reference.data.mocap_pos[0] = [
        float(two_target[0]),
        float(two_target[1]),
        float(mechanics_reference.data.mocap_pos[0, 2]),
    ]
    mujoco.mj_forward(mechanics_reference.model, mechanics_reference.data)
    controlled_positions = np.asarray([0.2, -0.15], dtype=np.float64)
    controlled_velocities = np.asarray([0.4, -0.3], dtype=np.float64)
    _set_joint_state(env, controlled_positions, controlled_velocities)
    _set_joint_state(
        mechanics_reference, controlled_positions, controlled_velocities
    )
    env._previous_distance = env._distance_to_target()
    mechanics_reference._previous_distance = (
        mechanics_reference._distance_to_target()
    )
    mechanics_action = np.asarray([0.2, -0.1])
    safe_observation, safe_reward, safe_terminated, safe_truncated, safe_info = (
        env.step(mechanics_action)
    )
    base_observation, base_reward, base_terminated, base_truncated, base_info = (
        mechanics_reference.step(mechanics_action)
    )
    mechanics_component = safe_info["reward_components"]["safe_branch_potential"]
    assert np.allclose(safe_observation, base_observation)
    assert np.allclose(env.data.qpos, mechanics_reference.data.qpos)
    assert np.allclose(env.data.qvel, mechanics_reference.data.qvel)
    assert np.allclose(env.physics_step_distances, mechanics_reference.physics_step_distances)
    assert safe_terminated == base_terminated
    assert safe_truncated == base_truncated
    assert np.isclose(safe_reward - mechanics_component, base_reward)
    assert safe_info["held_steps"] == base_info["held_steps"]
    for name, value in base_info["reward_components"].items():
        assert name in safe_info["reward_components"]
        assert np.isclose(safe_info["reward_components"][name], value)

    _, _, _, _, clipped_info = env.step(np.asarray([3.0, -3.0]))
    clipped_control = env.data.ctrl.copy()
    assert np.array_equal(clipped_control, np.asarray([1.0, -1.0]))
    assert "safe_branch_potential" in clipped_info["reward_components"]

    # Repeated hold updates and a reset must retain base semantics and clear
    # episode state while selecting a fresh reference for the fresh target.
    env.reset(seed=1730)
    first_target = env.data.site("end_effector").xpos[:2].copy()
    _set_target(env, first_target)
    env._previous_distance = env._distance_to_target()
    _, _, _, _, first_hold = env.step(np.zeros(2))
    _, _, _, _, second_hold = env.step(np.zeros(2))
    assert first_hold["held_steps"] == 1
    assert second_hold["held_steps"] == 2
    previous_reference = env.safe_reference
    env.reset(seed=1731)
    assert env._held_steps == 0
    assert env._step_count == 0
    assert np.isfinite(env.safe_reference).all()
    assert not np.array_equal(env.data.mocap_pos[0], first_target)
    assert not np.array_equal(env.safe_reference, previous_reference)

    artifact = {
        "check": "safe_branch_trajectory_intervention",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "impossible_target_rejected": impossible_target_rejected,
            "branch_cases": branch_observations,
            "branch_selection": branch_results,
            "toward_potential_difference": float(production_toward),
            "away_potential_difference": float(production_away),
            "integrated_transition_potential": float(observed_transition),
            "base_transition_match": {
                "observation": True,
                "state": True,
                "physics_step_distances": True,
                "base_reward_components": True,
                "reward_before_safe_branch_term": float(
                    safe_reward - mechanics_component
                ),
                "base_reward": float(base_reward),
            },
            "clipped_control": clipped_control.tolist(),
            "hold_steps": [
                int(first_hold["held_steps"]),
                int(second_hold["held_steps"]),
            ],
        },
        "expected": {
            "observation_shape": [11],
            "impossible_target_rejected": True,
            "branch_case_counts": [1, 2],
            "selected_branch_is_independent_max_margin": True,
            "toward_positive_and_away_negative": True,
            "potential_difference_bound": 1.0,
            "production_step_contains_integrated_potential": True,
            "safe_wrapper_preserves_base_transition": True,
            "clipped_control": [1.0, -1.0],
            "hold_steps": [1, 2],
            "reset_clears_hold_and_step_state": True,
        },
        "checked_scope": [
            "finite analytic-target validation and loud rejection of an impossible target",
            "independent analytic IK, angle-representation enumeration, and compiled-limit margin selection",
            "wrapped potential sign, finite bound, and integration into a real training transition",
            "base scenario transition preservation, including state, frame-skip distances, hold state, and reward terms",
            "unchanged observation shape, action clipping, repeated hold updates, and reset isolation",
        ],
        "unchecked_scope": [
            "learning performance or causal effect on a fresh training artifact",
            "official evaluation success and protected benchmark semantics",
            "continuous-hold behavior between visible control boundaries",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def _compatibility_check(output: Path) -> None:
    """Exercise the changed production reset and step paths without an artifact."""
    env = SafeBranchTrajectoryEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=3,
    )
    observation, _ = env.reset(seed=19)
    next_observation, reward, _, _, info = env.step(np.asarray([2.0, -2.0]))
    component = info["reward_components"]["safe_branch_potential"]
    assert observation.shape == (11,)
    assert next_observation.shape == (11,)
    assert np.isfinite(next_observation).all()
    assert np.isfinite(reward)
    assert np.isfinite(component)
    assert abs(component) <= SAFE_BRANCH_POTENTIAL_COEFFICIENT + 1e-12
    assert np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0]))
    artifact = {
        "check": "safe_branch_trajectory_compatibility",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "reset_observation_shape": list(observation.shape),
            "step_observation_shape": list(next_observation.shape),
            "step_reward": float(reward),
            "safe_branch_potential": float(component),
            "clipped_control": env.data.ctrl.tolist(),
            "selected_branch": int(env.safe_branch_index),
        },
        "expected": {
            "observation_shape": [11],
            "finite_reward_observation_and_potential": True,
            "bounded_potential": True,
            "clipped_control": [1.0, -1.0],
            "selected_branch_is_stored": True,
        },
        "checked_scope": [
            "production training reset and one clipped step",
            "finite integrated safe-branch reward attribution without an artifact",
        ],
        "unchecked_scope": [
            "full branch-selection and repeated-transition behavioral check",
            "training or evaluation artifact behavior",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    if args.compatibility:
        _compatibility_check(Path(args.output))
    else:
        _behavioral_check(Path(args.output))


if __name__ == "__main__":
    main()
