"""Executable laboratory check for the controlled reward-variant comparison.

The check is intentionally independent of the reward implementation for its
expected interruption consequences and its Jacobian/limit measurements.  It
writes only the requested JSON artifact; it does not train, evaluate, or edit
campaign state.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.environment import make_training_env
from robot_learning.training.reward import reach_reward


def _check(
    errors: list[str],
    label: str,
    observed: object,
    expected: object,
    condition: bool,
) -> None:
    if not condition:
        errors.append(
            f"{label}: observed={observed!r}, expected={expected!r}"
        )


def _compiled_posture_metrics(
    env: TwoJointArmReachEnv,
) -> tuple[float, float]:
    site_id = mujoco.mj_name2id(
        env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    jacobian_position = np.zeros((3, env.model.nv))
    jacobian_rotation = np.zeros((3, env.model.nv))
    mujoco.mj_jacSite(
        env.model,
        env.data,
        jacobian_position,
        jacobian_rotation,
        site_id,
    )
    condition_number = float(np.linalg.cond(jacobian_position[:2, :2]))

    margins = []
    for joint_id in range(env.model.nj):
        qpos_index = env.model.jnt_qposadr[joint_id]
        lower, upper = env.model.jnt_range[joint_id]
        margins.append(
            min(env.data.qpos[qpos_index] - lower, upper - env.data.qpos[qpos_index])
        )
    return condition_number, float(min(margins))


def _put_target_at_end_effector(env: TwoJointArmReachEnv) -> None:
    mujoco.mj_forward(env.model, env.data)
    env.data.mocap_pos[0] = env._end_effector_position()
    mujoco.mj_forward(env.model, env.data)


def _set_posture(
    env: TwoJointArmReachEnv, joint_positions: tuple[float, float]
) -> None:
    env.data.qpos[:2] = joint_positions
    env.data.qvel[:] = 0.0
    _put_target_at_end_effector(env)


def _run_checks() -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    observed: dict[str, object] = {}

    configured_env = None
    try:
        configured_env = make_training_env()
        configured_variant = configured_env.training_variant
        observed["configured_training_variant"] = configured_variant
        _check(
            errors,
            "training configuration wiring",
            configured_variant,
            "hold_aware",
            configured_variant == "hold_aware",
        )
    except Exception as exc:
        observed["configured_training_variant_error"] = str(exc)
        errors.append(f"training configuration wiring raised {exc!r}")
    finally:
        if configured_env is not None:
            configured_env.close()

    try:
        TwoJointArmReachEnv(training_variant="unknown")
    except ValueError:
        observed["unknown_variant_rejected"] = True
    else:
        observed["unknown_variant_rejected"] = False
        errors.append("unknown training variant was accepted")

    baseline_interruption = reach_reward(
        previous_distance=0.005,
        current_distance=0.02,
        success_threshold=0.01,
        held_steps=0,
        previous_held_steps=3,
        hold_steps_required=10,
        penalize_outside=True,
        reward_variant="baseline",
    )
    hold_aware_interruption = reach_reward(
        previous_distance=0.005,
        current_distance=0.02,
        success_threshold=0.01,
        held_steps=0,
        previous_held_steps=3,
        hold_steps_required=10,
        penalize_outside=True,
        reward_variant="hold_aware",
    )
    observed["baseline_interruption"] = baseline_interruption.components
    observed["hold_aware_interruption"] = hold_aware_interruption.components
    _check(
        errors,
        "baseline interruption forfeiture",
        baseline_interruption.components["hold_progress"],
        0.0,
        np.isclose(baseline_interruption.components["hold_progress"], 0.0),
    )
    _check(
        errors,
        "baseline outside interruption penalty",
        baseline_interruption.components["outside_band"],
        -0.1,
        np.isclose(baseline_interruption.components["outside_band"], -0.1),
    )
    _check(
        errors,
        "hold-aware full capital forfeiture",
        hold_aware_interruption.components["hold_progress"],
        -15.0,
        np.isclose(hold_aware_interruption.components["hold_progress"], -15.0),
    )
    _check(
        errors,
        "hold-aware material interruption penalty",
        hold_aware_interruption.components["outside_band"],
        -5.0,
        np.isclose(hold_aware_interruption.components["outside_band"], -5.0),
    )

    repeated_progress = [
        reach_reward(
            previous_distance=0.0,
            current_distance=0.0,
            success_threshold=0.01,
            held_steps=held_steps,
            previous_held_steps=held_steps - 1,
            hold_steps_required=10,
            reward_variant="hold_aware",
        ).components["hold_progress"]
        for held_steps in (1, 2, 3)
    ]
    reentry_progress = reach_reward(
        previous_distance=0.0,
        current_distance=0.0,
        success_threshold=0.01,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=10,
        reward_variant="hold_aware",
    ).components["hold_progress"]
    observed["repeated_hold_progress"] = repeated_progress
    observed["post_interruption_reentry_progress"] = reentry_progress
    _check(
        errors,
        "repeated hold updates",
        repeated_progress,
        [5.0, 5.0, 5.0],
        all(np.isclose(value, 5.0) for value in repeated_progress),
    )
    _check(
        errors,
        "hold re-entry transition",
        reentry_progress,
        5.0,
        np.isclose(reentry_progress, 5.0),
    )

    transition_env = TwoJointArmReachEnv(
        training_variant="hold_aware", max_episode_steps=10
    )
    transition_env.reset(seed=7)
    _put_target_at_end_effector(transition_env)
    _, _, _, _, in_tolerance_info = transition_env.step(np.zeros(2))
    transition_env.data.mocap_pos[0] = [0.0, 0.20, 0.02]
    mujoco.mj_forward(transition_env.model, transition_env.data)
    _, _, _, _, outside_info = transition_env.step(np.zeros(2))
    transition_env.reset(seed=8)
    observed["transition"] = {
        "in_tolerance_held_steps": in_tolerance_info["held_steps"],
        "outside_held_steps": outside_info["held_steps"],
        "outside_hold_progress": outside_info["reward_components"][
            "hold_progress"
        ],
        "outside_band": outside_info["reward_components"]["outside_band"],
        "reset_held_steps": transition_env._held_steps,
        "reset_outside_after_hold": transition_env._outside_after_hold,
    }
    _check(
        errors,
        "compiled environment in-tolerance transition",
        in_tolerance_info["held_steps"],
        1,
        in_tolerance_info["held_steps"] == 1,
    )
    _check(
        errors,
        "compiled environment interruption transition",
        outside_info["held_steps"],
        0,
        outside_info["held_steps"] == 0,
    )
    _check(
        errors,
        "compiled environment interruption attribution",
        outside_info["reward_components"],
        "negative hold-progress and outside-band terms",
        outside_info["reward_components"]["hold_progress"] < 0
        and outside_info["reward_components"]["outside_band"] < 0,
    )
    _check(
        errors,
        "compiled environment reset",
        (transition_env._held_steps, transition_env._outside_after_hold),
        (0, False),
        transition_env._held_steps == 0
        and transition_env._outside_after_hold is False,
    )
    transition_env.close()

    posture_env = TwoJointArmReachEnv(training_variant="posture_limit_aware")
    posture_env.reset(seed=9)
    _set_posture(posture_env, (0.0, np.pi / 2.0))
    safe_condition, safe_margin = _compiled_posture_metrics(posture_env)
    safe_reward = reach_reward(
        previous_distance=0.0,
        current_distance=0.0,
        success_threshold=0.01,
        reward_variant="posture_limit_aware",
        jacobian_condition_number=safe_condition,
        minimum_joint_limit_margin=safe_margin,
    )
    _set_posture(posture_env, (2.95, 0.01))
    risky_condition, risky_margin = _compiled_posture_metrics(posture_env)
    baseline_risky_reward = reach_reward(
        previous_distance=0.0,
        current_distance=0.0,
        success_threshold=0.01,
        reward_variant="baseline",
    )
    risky_reward = reach_reward(
        previous_distance=0.0,
        current_distance=0.0,
        success_threshold=0.01,
        reward_variant="posture_limit_aware",
        jacobian_condition_number=risky_condition,
        minimum_joint_limit_margin=risky_margin,
    )
    far_reward = reach_reward(
        previous_distance=0.05,
        current_distance=0.05,
        success_threshold=0.01,
        reward_variant="posture_limit_aware",
        jacobian_condition_number=risky_condition,
        minimum_joint_limit_margin=risky_margin,
    )
    observed["compiled_posture_metrics"] = {
        "safe_condition": safe_condition,
        "safe_margin": safe_margin,
        "risky_condition": risky_condition,
        "risky_margin": risky_margin,
    }
    observed["posture_rewards"] = {
        "safe": safe_reward.components,
        "baseline_risky": baseline_risky_reward.components,
        "risky": risky_reward.components,
        "far": far_reward.components,
    }
    _check(
        errors,
        "safe near-target posture control",
        safe_reward.components,
        "zero posture penalties",
        np.isclose(safe_reward.components["posture_condition"], 0.0)
        and np.isclose(safe_reward.components["posture_limit"], 0.0),
    )
    _check(
        errors,
        "risky conditioning and limit activation",
        risky_reward.components,
        "negative conditioning and limit penalties",
        risky_condition > 20.0
        and risky_margin < 0.2
        and risky_reward.components["posture_condition"] < 0.0
        and risky_reward.components["posture_limit"] < 0.0
        and np.isclose(
            risky_reward.total,
            baseline_risky_reward.total
            + risky_reward.components["posture_condition"]
            + risky_reward.components["posture_limit"],
        )
        and risky_reward.total < safe_reward.total,
    )
    _check(
        errors,
        "far posture control",
        far_reward.components,
        "no near-target posture penalties",
        np.isclose(far_reward.components["posture_condition"], 0.0)
        and np.isclose(far_reward.components["posture_limit"], 0.0),
    )
    _set_posture(posture_env, (2.95, 0.01))
    _, _, _, _, posture_info = posture_env.step(np.zeros(2))
    observed["posture_environment_wiring"] = posture_info["reward_components"]
    _check(
        errors,
        "posture environment profile wiring",
        posture_info["reward_components"],
        "active posture penalty components",
        posture_info["reward_components"].get("posture_condition", 0.0) < 0.0
        and posture_info["reward_components"].get("posture_limit", 0.0) < 0.0,
    )
    posture_env.close()

    return observed, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        observed, errors = _run_checks()
    except Exception as exc:
        observed = {"unexpected_check_error": repr(exc)}
        errors = [f"check raised unexpectedly: {exc!r}"]
    artifact = {
        "check": "mechanism_rewards",
        "status": "failed" if errors else "passed",
        "observed": observed,
        "expected": {
            "profiles": ["baseline", "hold_aware", "posture_limit_aware"],
            "configured_training_variant": "hold_aware",
            "baseline_interruption": {
                "hold_progress": 0.0,
                "outside_band": -0.1,
            },
            "hold_aware_interruption": {
                "hold_progress": -15.0,
                "outside_band": -5.0,
            },
            "posture_scope": (
                "near-target condition and joint-limit penalties only"
            ),
        },
        "checked_scope": [
            "explicit training-variant configuration wiring and unknown-profile rejection",
            "baseline versus hold-aware interruption consequences",
            "repeated hold updates, interruption re-entry, compiled transitions, and reset",
            "compiled-arm Jacobian conditioning and joint-limit metrics",
            "posture penalties for safe, risky, and far controls",
        ],
        "errors": errors,
        "unchecked_scope": [
            "PPO learning behavior and candidate performance",
            "long-horizon distributional effects across the official target range",
            "scientific validity of the chosen coefficients",
            "official evaluation outcomes",
        ],
    }
    args.artifact.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
