"""Scenario-owned research evaluation.

This module runs a model over the deterministic evaluation panel it is asked
for and records the minimal factual outcome of every episode. It draws no
scientific conclusion and preselects no behavioral metric.

Anything else the current research question needs goes into `research_evidence`,
an opaque channel owned by the researcher. Filling, replacing or emptying it is
ordinary research code and requires no change to the generic AutoResearch core,
which never interprets its contents.
"""

from collections.abc import Callable
from pathlib import Path

import mujoco
import numpy as np

from benchmark.paired_evidence import episode_outcomes
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4
# Bumped when the per-evaluation artifact schema changes.
RESEARCH_EVALUATION_SCHEMA_VERSION = 7

_JOINT_LIMIT_RADIANS = float(np.deg2rad(170.0))
_IK_BRANCHES = ("open", "folded")


def _finite_float(value, *, field: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(
            f"{field} must be finite for research evaluation serialization"
        )
    return number


def _finite_array(value, *, field: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64).copy()
    if not np.all(np.isfinite(array)):
        raise ValueError(
            f"{field} must be finite for research evaluation serialization"
        )
    return array


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _validate_evaluation_model(model) -> np.ndarray:
    expected_dimensions = {
        "nq": 2,
        "nv": 2,
        "nu": 2,
        "njnt": 2,
        "nmocap": 1,
    }
    for field, expected in expected_dimensions.items():
        actual = int(getattr(model, field))
        if actual != expected:
            raise ValueError(
                f"the two-joint arm requires model.{field}={expected}, got {actual}"
            )

    qpos_addresses = np.asarray(model.jnt_qposadr)
    dof_addresses = np.asarray(model.jnt_dofadr)
    if qpos_addresses.shape != (2,) or not np.array_equal(
        qpos_addresses, np.array([0, 1])
    ):
        raise ValueError(
            "the two-joint arm requires two consecutive joint qpos addresses"
        )
    if dof_addresses.shape != (2,) or not np.array_equal(
        dof_addresses, np.array([0, 1])
    ):
        raise ValueError(
            "the two-joint arm requires two consecutive joint dof addresses"
        )

    joint_ranges = _finite_array(model.jnt_range, field="joint_range")
    if joint_ranges.shape != (2, 2):
        raise ValueError("the two-joint arm requires a 2x2 compiled joint range")
    expected_ranges = np.array(
        [
            [-_JOINT_LIMIT_RADIANS, _JOINT_LIMIT_RADIANS],
            [-_JOINT_LIMIT_RADIANS, _JOINT_LIMIT_RADIANS],
        ],
        dtype=np.float64,
    )
    if not np.allclose(joint_ranges, expected_ranges, rtol=0.0, atol=1e-12):
        raise ValueError(
            "the two-joint arm requires compiled +/-170 degree joint limits"
        )
    return joint_ranges


def _signed_limit_margins(
    qpos: np.ndarray, joint_ranges: np.ndarray, *, field: str
) -> np.ndarray:
    qpos = _finite_array(qpos, field=field)
    if qpos.shape != (2,):
        raise ValueError(f"{field} must have shape (2,), got {qpos.shape}")
    margins = np.minimum(qpos - joint_ranges[:, 0], joint_ranges[:, 1] - qpos)
    return _finite_array(margins, field=f"{field}_margins")


def _analytic_ik_candidates(
    target_position: np.ndarray, joint_ranges: np.ndarray
) -> tuple[dict[str, dict], dict[str, np.ndarray]]:
    target_position = _finite_array(target_position, field="target_position")
    if target_position.shape != (3,):
        raise ValueError(
            f"target_position must have shape (3,), got {target_position.shape}"
        )

    target_x = float(target_position[0])
    target_y = float(target_position[1])
    target_angle = _finite_float(
        np.arctan2(target_y, target_x), field="target_angle"
    )
    target_radius_squared = _finite_float(
        np.float64(target_x) * np.float64(target_x)
        + np.float64(target_y) * np.float64(target_y),
        field="target_radius_squared",
    )
    cos_elbow = _finite_float(
        (
            target_radius_squared
            - UPPER_ARM_LENGTH**2
            - FOREARM_LENGTH**2
        )
        / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
        field="ik_elbow_cosine",
    )
    has_planar_solution = bool(-1.0 <= cos_elbow <= 1.0)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    candidates: dict[str, dict] = {}
    candidate_qpos: dict[str, np.ndarray] = {}
    for branch, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = target_angle - float(
            np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        qpos = _finite_array(
            np.array([_wrap_to_pi(shoulder), elbow], dtype=np.float64),
            field=f"{branch}_ik_qpos",
        )
        margins = _signed_limit_margins(
            qpos, joint_ranges, field=f"{branch}_ik_qpos"
        )
        candidate_qpos[branch] = qpos
        candidates[branch] = {
            "qpos": qpos.tolist(),
            "joint_limit_margins_rad": margins.tolist(),
            "feasible": bool(has_planar_solution and np.all(margins >= 0.0)),
        }

    return candidates, candidate_qpos


def _failed_episode_step(
    env,
    trace_data,
    *,
    site_id: int,
    step: int,
    held_steps: int,
    candidate_qpos: dict[str, np.ndarray],
    joint_ranges: np.ndarray,
) -> dict:
    """Capture one factual post-step state without changing the environment."""
    # mj_step integrates qpos/qvel before all derived kinematics are current.
    # Forward a copy so the trace is state-consistent without changing the
    # environment data that will drive the next policy step.
    mujoco.mj_copyData(trace_data, env.model, env.data)
    mujoco.mj_forward(env.model, trace_data)

    qpos = _finite_array(trace_data.qpos, field="qpos")
    if qpos.shape != (2,):
        raise ValueError(f"qpos must have shape (2,), got {qpos.shape}")
    qvel = _finite_array(trace_data.qvel, field="qvel")
    if qvel.shape != (2,):
        raise ValueError(f"qvel must have shape (2,), got {qvel.shape}")
    end_effector_position = _finite_array(
        trace_data.site("end_effector").xpos, field="end_effector_position"
    )
    if end_effector_position.shape != (3,):
        raise ValueError(
            "end_effector_position must have shape (3,), "
            f"got {end_effector_position.shape}"
        )
    target_position = _finite_array(trace_data.mocap_pos[0], field="target_position")
    if target_position.shape != (3,):
        raise ValueError(
            f"target_position must have shape (3,), got {target_position.shape}"
        )
    applied_action = _finite_array(trace_data.ctrl, field="action")
    if applied_action.shape != (2,):
        raise ValueError(f"action must have shape (2,), got {applied_action.shape}")

    jacobian_position = np.empty((3, env.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        env.model,
        trace_data,
        jacobian_position,
        None,
        site_id,
    )
    jacobian_position = _finite_array(
        jacobian_position, field="end_effector_position_jacobian"
    )
    if jacobian_position.shape != (3, 2):
        raise ValueError(
            "the two-joint arm requires a 3x2 end-effector position Jacobian"
        )
    end_effector_velocity = _finite_array(
        jacobian_position @ qvel, field="end_effector_velocity"
    )
    actual_joint_limit_margins = _signed_limit_margins(
        qpos, joint_ranges, field="qpos"
    )
    wrapped_qpos_residuals: dict[str, list[float]] = {}
    for branch in _IK_BRANCHES:
        if branch not in candidate_qpos:
            raise ValueError(f"missing {branch} analytic IK candidate")
        residual = np.array(
            [_wrap_to_pi(float(value)) for value in candidate_qpos[branch] - qpos],
            dtype=np.float64,
        )
        wrapped_qpos_residuals[branch] = _finite_array(
            residual, field=f"{branch}_wrapped_qpos_residual"
        ).tolist()
    jacobian_determinant = _finite_float(
        np.linalg.det(jacobian_position[:2, :2]),
        field="jacobian_determinant",
    )

    return {
        "step": int(step),
        "action": applied_action.tolist(),
        "qpos": qpos.tolist(),
        "qvel": qvel.tolist(),
        "end_effector_position": end_effector_position.tolist(),
        "end_effector_velocity": end_effector_velocity.tolist(),
        "distance_cm": _finite_float(
            100.0 * np.linalg.norm(end_effector_position - target_position),
            field="distance_cm",
        ),
        "held_steps": int(held_steps),
        "jacobian_determinant": jacobian_determinant,
        "ncon": int(trace_data.ncon),
        "joint_limit_margins_rad": actual_joint_limit_margins.tolist(),
        "wrapped_qpos_residuals": wrapped_qpos_residuals,
    }


def evaluate_research_model(
    model_path: Path,
    *,
    episodes: int,
    seed: int,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Measure a deterministic panel with episode seeds starting at ``seed``."""
    if episodes < 1:
        raise ValueError("an evaluation panel requires at least one episode")
    runtime = load_runtime(model_path, algorithm)
    env = make_evaluation_env(policy_runtime=runtime)
    joint_ranges = _validate_evaluation_model(env.model)
    site_id = mujoco.mj_name2id(
        env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    if site_id < 0:
        raise ValueError("the evaluation model has no end-effector site")
    trace_data = mujoco.MjData(env.model)

    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target_position = _finite_array(
            env.data.mocap_pos[0], field="target_position"
        )
        if target_position.shape != (3,):
            raise ValueError(
                f"target_position must have shape (3,), got {target_position.shape}"
            )
        ik_candidates, candidate_qpos = _analytic_ik_candidates(
            target_position, joint_ranges
        )
        reward_total = 0.0
        steps = 0
        success = False
        terminated = False
        truncated = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        trajectory: list[dict] = []
        min_distance_state_index: int | None = None
        min_distance_state_cm = float("inf")
        nearest_ik_branch_at_min_distance: str | None = None
        nearest_ik_qpos_residual_at_min_distance: list[float] | None = None
        nearest_ik_residual_rad_at_min_distance: float | None = None
        min_actual_joint_limit_margin_rad = float("inf")
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])
            state = _failed_episode_step(
                env,
                trace_data,
                site_id=site_id,
                step=steps - 1,
                held_steps=held_steps,
                candidate_qpos=candidate_qpos,
                joint_ranges=joint_ranges,
            )
            trajectory.append(state)
            state_distance_cm = float(state["distance_cm"])
            state_margin = min(
                float(margin) for margin in state["joint_limit_margins_rad"]
            )
            min_actual_joint_limit_margin_rad = min(
                min_actual_joint_limit_margin_rad, state_margin
            )
            if (
                min_distance_state_index is None
                or state_distance_cm < min_distance_state_cm
            ):
                min_distance_state_index = int(state["step"])
                min_distance_state_cm = state_distance_cm
                residual_norms = {
                    branch: float(
                        np.linalg.norm(
                            np.asarray(
                                state["wrapped_qpos_residuals"][branch],
                                dtype=np.float64,
                            )
                        )
                    )
                    for branch in _IK_BRANCHES
                }
                nearest_ik_branch_at_min_distance = min(
                    _IK_BRANCHES, key=lambda branch: residual_norms[branch]
                )
                nearest_ik_qpos_residual_at_min_distance = list(
                    state["wrapped_qpos_residuals"][
                        nearest_ik_branch_at_min_distance
                    ]
                )
                nearest_ik_residual_rad_at_min_distance = _finite_float(
                    residual_norms[nearest_ik_branch_at_min_distance],
                    field="nearest_ik_residual_rad_at_min_distance",
                )

        episode_results.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                # Scenario task outcome, not Gymnasium termination.
                "success": success,
                "reward_total": _finite_float(reward_total, field="reward_total"),
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
        episode_diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_cm": _finite_float(
                    np.hypot(target_position[0], target_position[1]) * 100.0,
                    field="target_radius_cm",
                ),
                "target_angle_degrees": _finite_float(
                    np.degrees(np.arctan2(target_position[1], target_position[0])),
                    field="target_angle_degrees",
                ),
                "min_distance_cm": _finite_float(
                    min_distance_cm, field="min_distance_cm"
                ),
                "final_distance_cm": _finite_float(
                    final_distance_cm, field="final_distance_cm"
                ),
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "ik_candidates": ik_candidates,
                "min_distance_state_index": min_distance_state_index,
                "nearest_ik_branch_at_min_distance": (
                    nearest_ik_branch_at_min_distance
                ),
                "nearest_ik_qpos_residual_at_min_distance": (
                    nearest_ik_qpos_residual_at_min_distance
                ),
                "nearest_ik_residual_rad_at_min_distance": (
                    nearest_ik_residual_rad_at_min_distance
                ),
                "min_actual_joint_limit_margin_rad": _finite_float(
                    min_actual_joint_limit_margin_rad,
                    field="min_actual_joint_limit_margin_rad",
                ),
                "first_reach_state_index": (
                    None if first_reach_step is None else first_reach_step - 1
                ),
            }
        )
        if not success:
            episode_diagnostics[-1]["trajectory"] = trajectory
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": RESEARCH_EVALUATION_SCHEMA_VERSION,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "success_percent": 100 * successes / episodes,
        "episode_results": episode_results,
        # Researcher-owned evidence for distinguishing reach failures from hold
        # failures and checking whether performance varies by target geometry.
        "research_evidence": {
            "episode_diagnostics": episode_diagnostics,
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "trajectory": {
                    "step": "zero-based outer control step",
                    "action": "MuJoCo actuator control units",
                    "qpos": "radians",
                    "qvel": "radians per second",
                    "end_effector_position": "meters",
                    "end_effector_velocity": "meters per second",
                    "distance_cm": "cm",
                    "held_steps": "control steps",
                    "jacobian_determinant": "square meters per square radians",
                    "ncon": "contact count",
                    "joint_limit_margins_rad": (
                        "radians; signed margin to each compiled joint limit"
                    ),
                    "wrapped_qpos_residuals": (
                        "radians per joint, wrapped to [-pi, pi]"
                    ),
                },
            },
        },
    }


def summarize_research_evaluations(
    evaluations: list[dict],
    summary_version: int = RESEARCH_EVALUATION_SUMMARY_VERSION,
) -> dict:
    """Consolidate several completed evaluation panels for the same model.

    Only the primary task outcome is pooled here; the detailed measurements stay
    in each evaluation artifact and are not duplicated into this summary.
    """
    if not evaluations:
        raise ValueError("an evaluation summary requires at least one evaluation")
    outcomes = episode_outcomes(evaluations)
    total_episodes = len(outcomes)
    total_successes = sum(outcomes.values())
    episode_executions = sum(int(item["episodes"]) for item in evaluations)
    seed_success = {
        str(item["seed"]): float(item["success_percent"]) for item in evaluations
    }
    pooled_success = 100 * total_successes / total_episodes
    return {
        "schema_version": 4,
        "evaluation_summary_version": summary_version,
        "episodes": total_episodes,
        "episode_executions": episode_executions,
        "repeated_episodes": episode_executions - total_episodes,
        "seed_count": len(evaluations),
        "seed_success_percent": seed_success,
        "worst_seed_success_percent": min(seed_success.values()),
        "pooled_success_percent": pooled_success,
        "success_percent": pooled_success,
    }
