"""Defect-sensitive checks for the fresh direct-torque training route.

This module is intended for the ``python_module`` instrument.  It uses a
reference action that only clips the supplied command, controlled simulator
states, and explicit reward consequences.  It does not train or evaluate a
learned policy.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np

from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    make_evaluation_env,
)
from robot_learning.scenario.policy_io import (
    DIRECT_CONTROL_PROFILE,
    RESIDUAL_TORQUE_PROFILE,
    make_policy_io,
)
from robot_learning.training.environment import make_training_env
from robot_learning.training.reward import TARGETED_REGULATION_PROFILE, reach_reward


SUCCESS_THRESHOLD = 0.01
HOLD_STEPS_REQUIRED = 100


class VerificationFailure(AssertionError):
    """A controlled laboratory check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _expected_clipped_action(action: np.ndarray) -> np.ndarray:
    """Independent direct-control reference: only the actuator bounds apply."""
    action = np.asarray(action, dtype=np.float64)
    return np.minimum(np.maximum(action, -1.0), 1.0)


def _close_comparison(
    observed: np.ndarray, expected: np.ndarray, label: str
) -> dict[str, object]:
    observed = np.asarray(observed, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    error = float(np.max(np.abs(observed - expected)))
    _require(error <= 1.0e-12, f"{label} differs by {error}")
    return {
        "label": label,
        "observed": observed.tolist(),
        "expected": expected.tolist(),
        "max_abs_error": error,
    }


def _set_state(
    env: TwoJointArmReachEnv,
    q: tuple[float, float],
    qvel: tuple[float, float],
    radius: float,
    angle: float,
) -> None:
    env.data.qpos[:2] = q
    env.data.qvel[:2] = qvel
    env.data.mocap_pos[0] = [
        radius * np.cos(angle),
        radius * np.sin(angle),
        0.02,
    ]
    mujoco.mj_forward(env.model, env.data)


def _check_profile_routes(observations: list[dict[str, object]]) -> None:
    training = make_training_env()
    try:
        _require(
            training.control_profile == DIRECT_CONTROL_PROFILE,
            "fresh training environment still uses residual control",
        )
        _require(
            training.reward_profile == TARGETED_REGULATION_PROFILE,
            "training reward profile changed",
        )
        observations.append(
            {
                "label": "fresh_training_route",
                "observed": {
                    "control_profile": training.control_profile,
                    "reward_profile": training.reward_profile,
                },
                "expected": {
                    "control_profile": DIRECT_CONTROL_PROFILE,
                    "reward_profile": TARGETED_REGULATION_PROFILE,
                },
            }
        )
    finally:
        training.close()

    evaluation = make_evaluation_env()
    try:
        _require(
            evaluation.control_profile == DIRECT_CONTROL_PROFILE,
            "evaluation default control profile changed",
        )
        observations.append(
            {
                "label": "evaluation_default_route",
                "observed": evaluation.control_profile,
                "expected": DIRECT_CONTROL_PROFILE,
            }
        )
    finally:
        evaluation.close()

    residual_runtime = SimpleNamespace(
        io=make_policy_io(control_profile=RESIDUAL_TORQUE_PROFILE)
    )
    marked = TwoJointArmReachEnv(policy_runtime=residual_runtime)
    try:
        _require(
            marked.control_profile == RESIDUAL_TORQUE_PROFILE,
            "saved residual runtime marker was not preserved",
        )
        observations.append(
            {
                "label": "saved_runtime_marker",
                "observed": marked.control_profile,
                "expected": RESIDUAL_TORQUE_PROFILE,
            }
        )
    finally:
        marked.close()


def _check_direct_updates_and_resets(
    observations: list[dict[str, object]],
) -> None:
    env = TwoJointArmReachEnv(frame_skip=1, control_profile=DIRECT_CONTROL_PROFILE)
    try:
        update_cases = (
            (
                "changed_state_one",
                (0.35, -0.20),
                (0.40, -0.30),
                0.12,
                -2.20,
                (1.40, -0.80),
            ),
            (
                "changed_state_two",
                (-0.80, 0.80),
                (-0.25, 0.60),
                0.16,
                0.70,
                (0.30, -1.45),
            ),
            (
                "changed_state_three",
                (1.10, -0.35),
                (1.10, -0.90),
                0.10,
                -2.50,
                (-1.20, 1.30),
            ),
        )
        reset_records = []
        for reset_seed, case in zip((17, 18, 19), update_cases):
            env.reset(seed=reset_seed)
            _require(
                np.allclose(env.data.qpos[:2], 0.0)
                and np.allclose(env.data.qvel[:2], 0.0)
                and env._held_steps == 0,
                f"reset {reset_seed} did not restore the controlled state",
            )
            label, q, qvel, radius, angle, learned_action = case
            _set_state(env, q, qvel, radius, angle)
            action = np.asarray(learned_action, dtype=np.float64)
            env.step(action)
            reset_records.append(
                {
                    "seed": reset_seed,
                    "qpos_after_reset": [0.0, 0.0],
                    "qvel_after_reset": [0.0, 0.0],
                    "held_steps_after_reset": 0,
                }
            )
            observations.append(
                {
                    "label": label,
                    "comparison": _close_comparison(
                        env.data.ctrl.copy(),
                        _expected_clipped_action(action),
                        label,
                    ),
                }
            )

        env.reset(seed=29)
        _require(
            np.allclose(env.data.qpos[:2], 0.0)
            and np.allclose(env.data.qvel[:2], 0.0)
            and env._held_steps == 0,
            "repeated reset did not restore the controlled state",
        )
        observations.append(
            {
                "label": "repeated_resets",
                "observed": reset_records
                + [
                    {
                        "seed": 29,
                        "qpos_after_reset": env.data.qpos[:2].tolist(),
                        "qvel_after_reset": env.data.qvel[:2].tolist(),
                        "held_steps_after_reset": env._held_steps,
                    }
                ],
                "expected": {
                    "each_reset_qpos": [0.0, 0.0],
                    "each_reset_qvel": [0.0, 0.0],
                    "each_reset_held_steps": 0,
                },
            }
        )

        transition_records = []
        for reset_seed in (41, 42):
            env.reset(seed=reset_seed)
            distance_sequence = iter((0.005, 0.005, 0.02, 0.005))
            original_distance = env._distance_to_target
            env._distance_to_target = lambda: next(distance_sequence)
            try:
                transitions = [
                    env.step(np.zeros(2, dtype=np.float32)) for _ in range(4)
                ]
            finally:
                env._distance_to_target = original_distance
            held_steps = [transition[4]["held_steps"] for transition in transitions]
            _require(
                held_steps == [1, 2, 0, 1],
                f"hold interruption did not reset on seed {reset_seed}",
            )
            _require(
                transitions[2][2] is False
                and transitions[2][4]["is_success"] is False,
                "interrupted hold changed termination semantics",
            )
            transition_records.append(
                {
                    "seed": reset_seed,
                    "held_steps": held_steps,
                    "interruption_reward_components": transitions[2][4][
                        "reward_components"
                    ],
                }
            )
        observations.append(
            {
                "label": "repeated_hold_transitions",
                "observed": transition_records,
                "expected": {
                    "held_steps_per_sequence": [1, 2, 0, 1],
                    "interruption_is_not_success": True,
                },
            }
        )
    finally:
        env.close()


def _check_export_profile(observations: list[dict[str, object]]) -> None:
    from robot_learning.training import checkpoint

    captured: dict[str, object] = {}

    def capture_save_runtime(model_path, **kwargs):
        del model_path
        captured.update(kwargs)

    original_save_runtime = checkpoint.save_runtime
    checkpoint.save_runtime = capture_save_runtime
    try:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint.export_runtime(Path(directory), stats_path=None)
    finally:
        checkpoint.save_runtime = original_save_runtime

    policy_io = captured.get("policy_io")
    observed_profile = getattr(policy_io, "control_profile", None)
    _require(
        observed_profile == DIRECT_CONTROL_PROFILE,
        f"checkpoint export uses {observed_profile!r}, not direct control",
    )
    observations.append(
        {
            "label": "checkpoint_runtime_profile",
            "observed": observed_profile,
            "expected": DIRECT_CONTROL_PROFILE,
        }
    )


def _targeted_reward(
    previous_distance: float,
    current_distance: float,
    *,
    held_steps: int,
    previous_held_steps: int,
    penalize_outside: bool = False,
    joint_velocity: tuple[float, float] = (0.1, -0.1),
    endpoint_velocity: float = 0.01,
    action: tuple[float, float] = (0.2, -0.2),
):
    return reach_reward(
        previous_distance,
        current_distance,
        SUCCESS_THRESHOLD,
        np.asarray(action, dtype=np.float64),
        held_steps=held_steps,
        previous_held_steps=previous_held_steps,
        hold_steps_required=HOLD_STEPS_REQUIRED,
        penalize_outside=penalize_outside,
        reward_profile=TARGETED_REGULATION_PROFILE,
        joint_velocity=np.asarray(joint_velocity, dtype=np.float64),
        endpoint_velocity=endpoint_velocity,
    )


def _check_reward_consequences(observations: list[dict[str, object]]) -> None:
    acquisition = _targeted_reward(
        0.08,
        0.04,
        held_steps=0,
        previous_held_steps=0,
    )
    hold_update = _targeted_reward(
        0.008,
        0.008,
        held_steps=1,
        previous_held_steps=0,
        endpoint_velocity=0.4,
    )
    interruption = _targeted_reward(
        0.008,
        0.02,
        held_steps=0,
        previous_held_steps=3,
        penalize_outside=True,
        endpoint_velocity=0.4,
    )
    _require(
        acquisition.components["progress"] > 0.0
        and acquisition.components["closeness"] > 0.0
        and acquisition.components["hold_progress"] == 0.0,
        "acquisition reward did not expose progress/closeness separately from hold",
    )
    _require(
        hold_update.components["progress"] == 0.0
        and hold_update.components["hold_progress"] > 0.0
        and hold_update.components["targeted_endpoint_velocity"] < 0.0
        and hold_update.components["targeted_action_regulation"] < 0.0,
        "hold/regulation reward consequences were not distinct",
    )
    _require(
        interruption.components["hold_progress"] == 0.0
        and interruption.components["outside_band"] < 0.0
        and interruption.components["targeted_endpoint_velocity"] < 0.0,
        "interrupted hold did not expose its reset and regulation consequences",
    )
    observations.append(
        {
            "label": "acquisition_hold_interruption_reward",
            "observed": {
                "acquisition": acquisition.components,
                "hold_update": hold_update.components,
                "interruption": interruption.components,
            },
            "expected": {
                "acquisition_has_positive_progress_and_closeness": True,
                "acquisition_has_no_hold_progress": True,
                "hold_update_has_hold_progress_and_regulation_penalties": True,
                "interruption_resets_hold_progress_and_penalizes_outside": True,
            },
        }
    )


def run_checks() -> dict[str, object]:
    observations: list[dict[str, object]] = []
    _check_profile_routes(observations)
    _check_direct_updates_and_resets(observations)
    _check_export_profile(observations)
    _check_reward_consequences(observations)
    return {
        "passed": True,
        "observed_vs_expected": observations,
        "checked_scope": [
            "fresh full-radius training control profile and retained targeted reward profile",
            "evaluation default and explicit saved-runtime profile semantics",
            "independent clipped-action reference across repeated changed states",
            "repeated resets of qpos, qvel, and hold state",
            "checkpoint export control-profile persistence",
            "acquisition, hold/regulation, and interrupted-hold reward consequences",
        ],
        "unchecked_scope": [
            "long-horizon learning performance and matched-panel capability",
            "learned-policy performance or official evaluation success",
            "scientific validity of the reward as a predictor of task success",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    try:
        result = run_checks()
    except Exception as error:
        result = {
            "passed": False,
            "observed_vs_expected": {
                "error_type": type(error).__name__,
                "error": str(error),
            },
            "checked_scope": [
                "direct-torque route checks up to the first failure",
            ],
            "unchecked_scope": [
                "checks after the first failure",
                "long-horizon learning performance and matched-panel capability",
                "learned-policy performance or official evaluation success",
            ],
        }
    args.artifact.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not result["passed"]:
        raise VerificationFailure(result["observed_vs_expected"]["error"])


if __name__ == "__main__":
    main()
