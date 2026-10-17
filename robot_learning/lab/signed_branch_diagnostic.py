"""Controlled signed-IK-branch diagnostic for the active reach task.

This is a laboratory intervention, not an official policy evaluation.  The
saved model supplies the learned action and recurrent/normalization state, but
the saved runtime action callable is deliberately bypassed so that the branch
interventions are explicit and auditable.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
)
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.observations import (
    JOINT_LIMIT_RADIANS,
    ik_branch_errors,
    ik_branch_targets,
    ik_branch_validity,
    reach_observation,
)
from robot_learning.scenario.policy_io import (
    ACQUISITION_POSITION_GAIN_ACTIONS_PER_RADIAN,
    ACQUISITION_TOLERANCE_METERS,
    ACQUISITION_VELOCITY_GAIN_SECONDS,
    CONTROLLER_ACTIVATION_ID,
    MAINTENANCE_ACTION_LIMIT,
    MAINTENANCE_POSITION_GAIN_ACTIONS_PER_RADIAN,
    MAINTENANCE_VELOCITY_GAIN_SECONDS,
    RESET_ESCAPE_ELBOW_RADIANS,
    RESET_ESCAPE_MAX_STEPS,
    RESET_ESCAPE_MIN_Q2_RADIANS,
    RESET_ESCAPE_POSITION_GAIN_ACTIONS_PER_RADIAN,
    RESET_ESCAPE_VELOCITY_GAIN_SECONDS,
)


RADIUS_CM = (7.0, 11.0, 15.0, 19.0)
ANGLE_DEGREES = (-135.0, -45.0, 45.0, 135.0)
BRANCHES = ((0, 1), (1, -1))
MODES = ("raw_learned", "forced_branch_blend", "forced_branch_only")
BLEND_WEIGHT = 0.50
BASE_EPISODE_SEED = 17017
DIAGNOSTIC_CONTROLLER_ACTIVATION_ID = "i7_signed_branch_diagnostic_v1"


def _finite_action(action: Any) -> np.ndarray:
    """Convert a policy output to the unchanged two-dimensional action bounds."""
    try:
        candidate = np.asarray(action, dtype=np.float64)
    except (TypeError, ValueError):
        return np.zeros(2, dtype=np.float64)
    if candidate.shape not in ((2,), (1, 2)):
        return np.zeros(2, dtype=np.float64)
    candidate = candidate.reshape(2)
    if not np.isfinite(candidate).all():
        return np.zeros(2, dtype=np.float64)
    return np.clip(candidate, -MAINTENANCE_ACTION_LIMIT, MAINTENANCE_ACTION_LIMIT)


def _mirror_pair_key(radius_cm: float, angle_degrees: float) -> str:
    magnitude = abs(int(angle_degrees))
    return f"radius_{int(radius_cm)}cm_angles_{-magnitude}_and_{magnitude}_degrees"


def _angle_sign(angle_degrees: float) -> int:
    return -1 if angle_degrees < 0.0 else 1


def _branch_name(branch_index: int) -> str:
    return "open" if branch_index == 0 else "folded"


class SignedBranchController:
    """Bounded reset escape followed by feedback to one requested IK branch."""

    def __init__(self, branch_index: int) -> None:
        if branch_index not in (0, 1):
            raise ValueError(f"unsupported IK branch index: {branch_index}")
        self.branch_index = branch_index
        self.escape_steps = 0
        self.phase = "reset_escape"

    def reset(self) -> None:
        self.escape_steps = 0
        self.phase = "reset_escape"

    def action(self, data) -> np.ndarray:
        targets = ik_branch_targets(data)
        validity = ik_branch_validity(data)
        errors = ik_branch_errors(data)
        target = np.asarray(targets[self.branch_index], dtype=np.float64)
        branch_error = np.asarray(errors[self.branch_index], dtype=np.float64)
        qpos = np.asarray(data.qpos[:2], dtype=np.float64)
        qvel = np.asarray(data.qvel[:2], dtype=np.float64)

        # Invalid branches remain in the experiment.  Their feedback target is
        # clipped to the repository's joint limits rather than being silently
        # replaced by the other branch.
        position_target = np.clip(target, -JOINT_LIMIT_RADIANS, JOINT_LIMIT_RADIANS)
        if not bool(validity[self.branch_index]):
            position_error = position_target - qpos
        else:
            position_error = branch_error

        if self.phase == "reset_escape":
            elbow_sign = float(np.sign(target[1]))
            if elbow_sign == 0.0:
                elbow_sign = 1.0 if self.branch_index == 0 else -1.0
            escape_elbow_magnitude = min(
                max(abs(float(target[1])), RESET_ESCAPE_MIN_Q2_RADIANS),
                RESET_ESCAPE_ELBOW_RADIANS,
            )
            escape_target = np.asarray(
                [
                    qpos[0] + 0.35 * position_error[0],
                    elbow_sign * escape_elbow_magnitude,
                ],
                dtype=np.float64,
            )
            escape_error = escape_target - qpos
            result = (
                RESET_ESCAPE_POSITION_GAIN_ACTIONS_PER_RADIAN * escape_error
                - RESET_ESCAPE_VELOCITY_GAIN_SECONDS * qvel
            )
            self.escape_steps += 1
            if (
                self.escape_steps >= RESET_ESCAPE_MAX_STEPS
                or abs(float(qpos[1])) >= RESET_ESCAPE_MIN_Q2_RADIANS
            ):
                self.phase = "acquisition"
            return np.clip(
                result, -MAINTENANCE_ACTION_LIMIT, MAINTENANCE_ACTION_LIMIT
            )

        if self.phase == "maintenance":
            result = (
                MAINTENANCE_POSITION_GAIN_ACTIONS_PER_RADIAN * position_error
                - MAINTENANCE_VELOCITY_GAIN_SECONDS * qvel
            )
        else:
            result = (
                ACQUISITION_POSITION_GAIN_ACTIONS_PER_RADIAN * position_error
                - ACQUISITION_VELOCITY_GAIN_SECONDS * qvel
            )
            # The diagnostic uses the same endpoint handoff threshold as the
            # saved controller, but never changes the environment's hold logic.
            distance = float(
                np.linalg.norm(
                    data.site("end_effector").xpos - data.mocap_pos[0]
                )
            )
            if distance <= ACQUISITION_TOLERANCE_METERS:
                self.phase = "maintenance"

        return np.clip(result, -MAINTENANCE_ACTION_LIMIT, MAINTENANCE_ACTION_LIMIT)


def _require_saved_activation(runtime) -> tuple[str, bool]:
    """Require activation markers on the restored saved-runtime callables."""
    checked = (
        ("observe", runtime.io.observe),
        ("action", runtime.io.action),
        *(
            (("reset", runtime.io.reset),)
            if runtime.io.reset is not None
            else ()
        ),
    )
    for name, callable_ in checked:
        activation_id = getattr(callable_, "controller_activation_id", None)
        callable_path = getattr(callable_, "controller_callable_path", None)
        if activation_id != CONTROLLER_ACTIVATION_ID:
            raise ValueError(
                "saved runtime does not expose the required "
                f"controller_activation_id on {name}: {activation_id!r}"
            )
        if callable_path is not True:
            raise ValueError(
                "saved runtime does not expose controller_callable_path=true "
                f"on {name}"
            )
    return CONTROLLER_ACTIVATION_ID, True


def _resolve_model_path(candidate_directory: Path) -> Path:
    if not candidate_directory.is_dir():
        raise ValueError(f"--candidate must be a candidate directory: {candidate_directory}")
    preferred = candidate_directory / "model.zip"
    if preferred.is_file():
        return preferred
    zip_files = sorted(candidate_directory.glob("*.zip"))
    if len(zip_files) == 1:
        return zip_files[0]
    if not zip_files:
        raise ValueError(
            f"candidate directory contains no model.zip or unique .zip model: "
            f"{candidate_directory}"
        )
    raise ValueError(
        f"candidate directory contains multiple .zip models and no model.zip: "
        f"{candidate_directory}"
    )


def _target_episode(
    env,
    runtime,
    *,
    episode: int,
    episode_seed: int,
    mode: str,
    radius_cm: float,
    angle_degrees: float,
    branch_index: int,
    branch_sign: int,
) -> dict[str, Any]:
    runtime.reset()
    env.reset(seed=episode_seed)
    target_z = float(env.data.site("end_effector").xpos[2])
    angle_radians = math.radians(angle_degrees)
    env.data.mocap_pos[0] = [
        radius_cm / 100.0 * math.cos(angle_radians),
        radius_cm / 100.0 * math.sin(angle_radians),
        target_z,
    ]
    mujoco.mj_forward(env.model, env.data)

    target_branches = ik_branch_targets(env.data)
    target_validity = ik_branch_validity(env.data)
    branch_target = np.asarray(target_branches[branch_index], dtype=np.float64)
    branch_valid = bool(target_validity[branch_index])
    controller = SignedBranchController(branch_index)
    controller_active = mode != "raw_learned"

    initial_distance = float(
        np.linalg.norm(env.data.site("end_effector").xpos - env.data.mocap_pos[0])
    )
    minimum_distance = initial_distance
    first_reach_step: int | None = None
    maximum_held_steps = 0
    hold_interruptions = 0
    previous_held_steps = 0
    trace: list[dict[str, Any]] = []
    terminated = False
    truncated = False
    step_count = 0
    final_info: dict[str, Any] = {
        "distance": initial_distance,
        "held_steps": 0,
        "is_success": False,
    }

    while not (terminated or truncated):
        observation = reach_observation(env.data)
        learned_action = _finite_action(runtime.predict(observation))
        q_before = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
        qdot_before = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
        distance_before = float(
            np.linalg.norm(env.data.site("end_effector").xpos - env.data.mocap_pos[0])
        )
        branch_error = np.asarray(
            ik_branch_errors(env.data)[branch_index], dtype=np.float64
        )
        phase_before = controller.phase
        if controller_active:
            branch_action = _finite_action(controller.action(env.data))
            if mode == "forced_branch_only":
                applied_action = branch_action
            else:
                applied_action = _finite_action(
                    (1.0 - BLEND_WEIGHT) * learned_action
                    + BLEND_WEIGHT * branch_action
                )
        else:
            branch_action = None
            applied_action = learned_action

        _, _, terminated, truncated, info = env.step(applied_action)
        step_count += 1
        final_info = info
        distance_after = float(info["distance"])
        held_steps = int(info["held_steps"])
        minimum_distance = min(minimum_distance, distance_after)
        maximum_held_steps = max(maximum_held_steps, held_steps)
        if first_reach_step is None and distance_after <= SUCCESS_THRESHOLD:
            first_reach_step = step_count
        if previous_held_steps > 0 and held_steps == 0:
            hold_interruptions += 1
        previous_held_steps = held_steps

        trace.append(
            {
                "step": step_count,
                "learned_action": learned_action.tolist(),
                "branch_directed_action": (
                    None if branch_action is None else branch_action.tolist()
                ),
                "applied_action": _finite_action(applied_action).tolist(),
                "branch_control_active": controller_active,
                "controller_phase": phase_before,
                "selected_branch": branch_index,
                "selected_branch_sign": branch_sign,
                "branch_error_radians": branch_error.tolist(),
                "q_radians": q_before.tolist(),
                "qdot_radians_per_second": qdot_before.tolist(),
                "distance_cm": distance_before * 100.0,
                "held_steps": held_steps,
                "q_after_radians": np.asarray(env.data.qpos[:2], dtype=np.float64).tolist(),
                "qdot_after_radians_per_second": np.asarray(
                    env.data.qvel[:2], dtype=np.float64
                ).tolist(),
                "distance_after_cm": distance_after * 100.0,
            }
        )

    success = bool(final_info["is_success"])
    return {
        "episode": episode,
        "episode_seed": episode_seed,
        "mode": mode,
        "target_radius_cm": radius_cm,
        "target_angle_degrees": angle_degrees,
        "mirrored_pair_key": _mirror_pair_key(radius_cm, angle_degrees),
        "angle_sign": _angle_sign(angle_degrees),
        "branch_index": branch_index,
        "branch_sign": branch_sign,
        "branch_name": _branch_name(branch_index),
        "branch_target_radians": branch_target.tolist(),
        "target_branch_valid": branch_valid,
        "first_reach_step": first_reach_step,
        "max_held_steps": maximum_held_steps,
        "hold_interruptions": hold_interruptions,
        "interruptions": hold_interruptions,
        "first_reach": first_reach_step,
        "final_distance_cm": float(final_info["distance"]) * 100.0,
        "minimum_distance_cm": minimum_distance * 100.0,
        "steps": step_count,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "complete_uninterrupted_hold_success": success,
        "success": success,
        "acquisition_control_trace": trace,
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    episodes = len(records)
    successes = sum(bool(record["success"]) for record in records)
    reached = [record for record in records if record["first_reach_step"] is not None]
    first_reach = [record["first_reach_step"] for record in reached]
    return {
        "episodes": episodes,
        "successes": successes,
        "success_rate": None if not episodes else successes / episodes,
        "never_reached": episodes - len(reached),
        "reached_but_failed_hold": sum(
            record["first_reach_step"] is not None and not record["success"]
            for record in records
        ),
        "mean_first_reach_step": (
            None if not first_reach else sum(first_reach) / len(first_reach)
        ),
        "mean_max_held_steps": (
            None
            if not records
            else sum(record["max_held_steps"] for record in records) / episodes
        ),
        "hold_interruptions": sum(record["hold_interruptions"] for record in records),
    }


def _stratified_summaries(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    dimensions = {
        "by_mode": ("mode", lambda value: value),
        "by_branch_sign": ("branch_sign", lambda value: str(value)),
        "by_mirrored_angle_sign": ("angle_sign", lambda value: str(value)),
        "by_radius_cm": ("target_radius_cm", lambda value: str(value)),
        "by_target_branch_validity": (
            "target_branch_valid",
            lambda value: "valid" if value else "invalid",
        ),
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for output_name, (field, labeler) in dimensions.items():
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            label = labeler(record[field])
            groups.setdefault(label, []).append(record)
        result[output_name] = [
            {"stratum": label, **_summary(groups[label])}
            for label in sorted(groups)
        ]
    return result


def _paired_mirror_comparisons(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, float, int, str], dict[int, dict[str, Any]]] = {}
    for record in records:
        key = (
            record["mode"],
            record["target_radius_cm"],
            record["branch_sign"],
            record["mirrored_pair_key"],
        )
        groups.setdefault(key, {})[record["angle_sign"]] = record

    comparisons: list[dict[str, Any]] = []
    for (mode, radius_cm, branch_sign, pair_key), pair in sorted(groups.items()):
        negative = pair.get(-1)
        positive = pair.get(1)
        if negative is None or positive is None:
            continue
        comparisons.append(
            {
                "mode": mode,
                "radius_cm": radius_cm,
                "branch_sign_controlled": branch_sign,
                "mirrored_pair_key": pair_key,
                "negative_angle_degrees": negative["target_angle_degrees"],
                "positive_angle_degrees": positive["target_angle_degrees"],
                "negative_target_branch_valid": negative["target_branch_valid"],
                "positive_target_branch_valid": positive["target_branch_valid"],
                "negative_success": negative["success"],
                "positive_success": positive["success"],
                "success_difference_positive_minus_negative": int(
                    positive["success"]
                )
                - int(negative["success"]),
                "negative_first_reach_step": negative["first_reach_step"],
                "positive_first_reach_step": positive["first_reach_step"],
                "negative_max_held_steps": negative["max_held_steps"],
                "positive_max_held_steps": positive["max_held_steps"],
                "validity_matches": (
                    negative["target_branch_valid"] == positive["target_branch_valid"]
                ),
            }
        )
    return comparisons


def _finite_json(value: Any) -> Any:
    """Convert NumPy values and reject every non-finite numeric value."""
    if isinstance(value, dict):
        return {str(key): _finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_json(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("diagnostic contains a non-finite numeric value")
        return result
    if isinstance(value, np.ndarray):
        return _finite_json(value.tolist())
    return value


def _write_json(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                _finite_json(artifact),
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the controlled signed-IK-branch laboratory diagnostic."
    )
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        candidate_directory = args.candidate.resolve()
        model_path = _resolve_model_path(candidate_directory)
        runtime = load_runtime(model_path)
        saved_activation_id, saved_callable_path = _require_saved_activation(runtime)
        env = make_evaluation_env(policy_runtime=None)

        records: list[dict[str, Any]] = []
        episode = 0
        for mode in MODES:
            for radius_cm in RADIUS_CM:
                for angle_degrees in ANGLE_DEGREES:
                    for branch_index, branch_sign in BRANCHES:
                        records.append(
                            _target_episode(
                                env,
                                runtime,
                                episode=episode,
                                episode_seed=BASE_EPISODE_SEED + episode,
                                mode=mode,
                                radius_cm=radius_cm,
                                angle_degrees=angle_degrees,
                                branch_index=branch_index,
                                branch_sign=branch_sign,
                            )
                        )
                        episode += 1

        control_dt = float(env.model.opt.timestep * FRAME_SKIP)
        artifact = {
            "schema_version": 1,
            "diagnostic": "signed_branch_activation_verified_controlled_comparison",
            "protocol": {
                "candidate_directory": str(candidate_directory),
                "model_path": str(model_path.resolve()),
                "saved_runtime_activation_id": saved_activation_id,
                "saved_runtime_callable_path": saved_callable_path,
                "diagnostic_controller_activation_id": (
                    DIAGNOSTIC_CONTROLLER_ACTIVATION_ID
                ),
                "diagnostic_controller_callable_path": True,
                "saved_runtime_action_postprocessing_bypassed": True,
                "raw_action_source": (
                    "restored_runtime.model_predict_with_saved_normalizer_and_state"
                ),
                "environment_identity_io": True,
                "official_task_timing": {
                    "frame_skip": FRAME_SKIP,
                    "control_timestep_seconds": control_dt,
                    "hold_seconds": HOLD_SECONDS,
                    "hold_steps_required": int(env.hold_steps_required),
                    "success_threshold_meters": SUCCESS_THRESHOLD,
                    "horizon_steps": MAX_EPISODE_STEPS,
                },
                "modes": list(MODES),
                "fixed_blend_weight": BLEND_WEIGHT,
                "radii_cm": list(RADIUS_CM),
                "angles_degrees": list(ANGLE_DEGREES),
                "ik_branch_conditions": [
                    {
                        "branch_index": index,
                        "branch_sign": sign,
                        "branch_name": _branch_name(index),
                    }
                    for index, sign in BRANCHES
                ],
                "episode_seed_base": BASE_EPISODE_SEED,
                "target_override": (
                    "reset with a deterministic seed, overwrite only mocap target "
                    "position, then call MuJoCo forward kinematics"
                ),
                "success_semantics": (
                    "the environment's unchanged is_success and held_steps semantics"
                ),
            },
            "episodes": records,
            "summaries": _stratified_summaries(records),
            "paired_mirror_comparisons": _paired_mirror_comparisons(records),
        }
        _write_json(args.output, artifact)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
