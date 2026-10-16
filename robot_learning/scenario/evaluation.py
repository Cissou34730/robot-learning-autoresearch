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
import numbers

import mujoco
import numpy as np

from benchmark.paired_evidence import episode_outcomes
from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _json_value(value):
    """Convert compiled/scientific values to finite JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (numbers.Integral, np.integer)):
        return int(value)
    if isinstance(value, (numbers.Real, np.floating)):
        value = float(value)
        return value if np.isfinite(value) else None
    # MuJoCo enum values are integer-like on the supported native binding.
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _json_value(enum_value)
    return None


def _finite_float(value: float) -> float | None:
    value = float(value)
    return value if np.isfinite(value) else None


def _ik_branch_errors(target_position: np.ndarray, qpos: np.ndarray) -> list:
    """Return the same four wrapped IK errors exposed to the policy."""
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    def wrap_to_pi(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    shoulder_open = shoulder_for_elbow(elbow_open)
    elbow_folded = -elbow_open
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    return [
        wrap_to_pi(shoulder_open - float(qpos[0])),
        wrap_to_pi(elbow_open - float(qpos[1])),
        wrap_to_pi(shoulder_folded - float(qpos[0])),
        wrap_to_pi(elbow_folded - float(qpos[1])),
    ]


def _dense_mass_matrix(model, data) -> list:
    matrix = np.zeros((int(model.nv), int(model.nv)), dtype=np.float64)
    mujoco.mj_fullM(model, data, matrix)
    return _json_value(matrix)


def _model_summary(model, data) -> dict:
    """Capture only facts exposed by the compiled MuJoCo model and data."""
    dimension_names = (
        "nq",
        "nv",
        "nu",
        "nbody",
        "njnt",
        "ngeom",
        "nsite",
        "nconmax",
    )
    dimensions = {
        name: _json_value(getattr(model, name, None)) for name in dimension_names
    }
    option_names = (
        "solver",
        "integrator",
        "iterations",
        "tolerance",
        "noslip_iterations",
        "noslip_tolerance",
        "ls_iterations",
        "ls_tolerance",
        "ccd_iterations",
        "ccd_tolerance",
    )
    solver_options = {
        name: _json_value(getattr(model.opt, name, None)) for name in option_names
    }
    return {
        "dimensions": dimensions,
        "timestep_seconds": _json_value(model.opt.timestep),
        "gravity_meters_per_second_squared": _json_value(model.opt.gravity),
        "solver_options": solver_options,
        "body_mass_kg": _json_value(model.body_mass),
        "body_inertia_kg_m2": _json_value(model.body_inertia),
        "dof_damping": _json_value(model.dof_damping),
        "dof_armature": _json_value(model.dof_armature),
        "dof_joint_ids": _json_value(model.dof_jntid),
        "actuator_gear": _json_value(model.actuator_gear),
        "actuator_ctrlrange": _json_value(model.actuator_ctrlrange),
        "actuator_ctrllimited": _json_value(model.actuator_ctrllimited),
        "actuator_forcerange": _json_value(model.actuator_forcerange),
        "actuator_forcelimited": _json_value(model.actuator_forcelimited),
        "initial_joint_space_mass_matrix": _dense_mass_matrix(model, data),
    }


def _contact_observation(model, data) -> tuple[int, float | None, list]:
    contact_count = int(data.ncon)
    maximum_force_norm = 0.0
    force_was_nonfinite = False
    geom_pairs = []
    for contact_id in range(contact_count):
        contact = data.contact[contact_id]
        geom_pairs.append([int(contact.geom1), int(contact.geom2)])
        force_torque = np.zeros(6, dtype=np.float64)
        mujoco.mj_contactForce(model, data, contact_id, force_torque)
        force_norm = float(np.linalg.norm(force_torque[:3]))
        if np.isfinite(force_norm):
            maximum_force_norm = max(maximum_force_norm, force_norm)
        else:
            force_was_nonfinite = True
    if force_was_nonfinite and maximum_force_norm == 0.0:
        maximum_force = None
    else:
        maximum_force = _finite_float(maximum_force_norm)
    return contact_count, maximum_force, geom_pairs


def _new_columnar_trace(keys: tuple[str, ...]) -> dict[str, list]:
    return {key: [] for key in keys}


def _finite_max(values: list[float | None]) -> float | None:
    finite_values = [
        float(value)
        for value in values
        if value is not None and np.isfinite(float(value))
    ]
    return max(finite_values) if finite_values else None


def _trace_schema(env) -> dict:
    timestep = float(env.model.opt.timestep)
    control_interval = timestep * int(env.frame_skip)
    return {
        "units": {
            "time": "seconds",
            "qpos": "radians",
            "qvel": "radians_per_second",
            "qacc": "radians_per_second_squared",
            "position": "meters",
            "distance": "centimeters",
            "target_radius": "centimeters",
            "target_angle": "degrees",
            "action": "policy action units before environment processing",
            "control": "compiled MuJoCo control units",
            "held_steps": "control_steps",
            "mass_matrix": "compiled MuJoCo joint-space mass units",
            "actuator_force": "compiled MuJoCo actuator force units",
            "generalized_actuator_force": "compiled MuJoCo generalized force units",
            "contact_force_norm": "compiled MuJoCo force units",
            "contact_geom_pairs": "compiled geom ids",
        },
        "sampling": {
            "reset": "one state captured after env.reset and target sampling",
            "control_endpoint": (
                "one row after each unchanged env.step call, after its internal "
                "frame_skip substeps and hold update"
            ),
            "internal_substep": (
                "one row after each unchanged mujoco.mj_step performed by "
                "env.step"
            ),
        },
        "internal_substep_seconds": timestep,
        "control_interval_seconds": control_interval,
        "internal_substep_milliseconds": 1000.0 * timestep,
        "control_endpoint_milliseconds": 1000.0 * control_interval,
        "frame_skip": int(env.frame_skip),
        "control_endpoint_semantics": (
            "20 ms endpoint after 10 internal 2 ms substeps for the loaded model"
        ),
    }


def _controller_runtime_metadata(runtime) -> tuple[str | None, bool]:
    """Read explicit controller markers from the saved executable runtime."""
    policy_io = runtime.io
    activation_id = getattr(policy_io, "controller_activation_id", None)
    callable_path = getattr(policy_io, "controller_callable_path", None)
    # Runtime restore reconstructs PolicyIO from its callables.  The factory
    # puts the same explicit markers on those callables so they remain
    # inspectable without changing the human-owned PolicyIO dataclass.
    if activation_id is None:
        activation_id = getattr(
            policy_io.action, "controller_activation_id", None
        )
    if callable_path is None:
        callable_path = getattr(
            policy_io.action, "controller_callable_path", None
        )
    if not isinstance(activation_id, str) or not activation_id:
        activation_id = None
    callable_path = callable_path is True
    # Make the recovered facts directly available on the restored PolicyIO as
    # well as on the callable that carried them through runtime restoration.
    policy_io.controller_activation_id = activation_id
    policy_io.controller_callable_path = callable_path
    return activation_id, callable_path


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
    controller_activation_id, controller_callable_path = (
        _controller_runtime_metadata(runtime)
    )

    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    episode_traces: list[dict] = []
    model_summary = None
    shadow_data = mujoco.MjData(env.model)
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        if model_summary is None:
            model_summary = _model_summary(env.model, env.data)
        reset_qpos = np.asarray(env.data.qpos, dtype=np.float64).copy()
        reset_qvel = np.asarray(env.data.qvel, dtype=np.float64).copy()
        reset_qacc = np.asarray(env.data.qacc, dtype=np.float64).copy()
        reset_end_effector = np.asarray(
            env.data.site("end_effector").xpos, dtype=np.float64
        ).copy()
        reset_distance_cm = 100.0 * float(
            np.linalg.norm(reset_end_effector - target_position)
        )
        reset_branch_errors = _ik_branch_errors(target_position, reset_qpos)
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
        control_trace = _new_columnar_trace(
            (
                "action",
                "control",
                "control_saturated",
                "qpos",
                "qvel",
                "qacc",
                "end_effector_position",
                "distance",
                "ik_branch_errors",
                "held_steps",
                "mass_matrix",
                "time_seconds",
            )
        )
        substep_trace = _new_columnar_trace(
            (
                "control_step",
                "substep",
                "qpos",
                "qvel",
                "qacc",
                "end_effector_position",
                "distance",
                "actuator_force",
                "generalized_actuator_force",
                "contact_count",
                "maximum_contact_force_norm",
                "contact_geom_pairs",
                "time_seconds",
            )
        )
        substep_distances: list[float | None] = []
        hold_substep_distances: list[float | None] = []
        actuator_force_norms: list[float | None] = []
        generalized_force_norms: list[float | None] = []
        contact_force_norms: list[float | None] = []
        contact_counts: list[int] = []
        while not (terminated or truncated):
            # Copying the pre-step state into a separate data object lets the
            # unchanged environment perform its official step while the
            # research trace observes every internal MuJoCo substep.
            mujoco.mj_copyData(shadow_data, env.model, env.data)
            hold_was_active = was_in_tolerance
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

            actual_control = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            action_array = np.asarray(action, dtype=np.float64)
            control_trace["action"].append(_json_value(action_array))
            control_trace["control"].append(_json_value(actual_control))
            control_trace["control_saturated"].append(
                _json_value(
                    np.logical_or(
                        actual_control <= np.asarray(env.action_space.low),
                        actual_control >= np.asarray(env.action_space.high),
                    )
                )
            )
            control_trace["qpos"].append(_json_value(env.data.qpos))
            control_trace["qvel"].append(_json_value(env.data.qvel))
            control_trace["qacc"].append(_json_value(env.data.qacc))
            control_trace["end_effector_position"].append(
                _json_value(env.data.site("end_effector").xpos)
            )
            control_trace["distance"].append(_finite_float(distance_cm))
            control_trace["ik_branch_errors"].append(
                _json_value(_ik_branch_errors(target_position, env.data.qpos))
            )
            control_trace["held_steps"].append(held_steps)
            control_trace["mass_matrix"].append(
                _dense_mass_matrix(env.model, env.data)
            )
            control_trace["time_seconds"].append(
                _finite_float(steps * float(env.model.opt.timestep) * env.frame_skip)
            )

            shadow_data.ctrl[:] = actual_control
            for substep in range(int(env.frame_skip)):
                mujoco.mj_step(env.model, shadow_data)
                substep_end_effector = np.asarray(
                    shadow_data.site("end_effector").xpos, dtype=np.float64
                )
                substep_distance_cm = 100.0 * float(
                    np.linalg.norm(substep_end_effector - target_position)
                )
                (
                    contact_count,
                    maximum_contact_force_norm,
                    contact_geom_pairs,
                ) = _contact_observation(env.model, shadow_data)
                substep_trace["control_step"].append(steps)
                substep_trace["substep"].append(substep + 1)
                substep_trace["qpos"].append(_json_value(shadow_data.qpos))
                substep_trace["qvel"].append(_json_value(shadow_data.qvel))
                substep_trace["qacc"].append(_json_value(shadow_data.qacc))
                substep_trace["end_effector_position"].append(
                    _json_value(substep_end_effector)
                )
                substep_trace["distance"].append(
                    _finite_float(substep_distance_cm)
                )
                substep_trace["actuator_force"].append(
                    _json_value(shadow_data.actuator_force)
                )
                substep_trace["generalized_actuator_force"].append(
                    _json_value(shadow_data.qfrc_actuator)
                )
                substep_trace["contact_count"].append(contact_count)
                substep_trace["maximum_contact_force_norm"].append(
                    maximum_contact_force_norm
                )
                substep_trace["contact_geom_pairs"].append(contact_geom_pairs)
                substep_trace["time_seconds"].append(
                    _finite_float(
                        (
                            (steps - 1) * int(env.frame_skip)
                            + substep
                            + 1
                        )
                        * float(env.model.opt.timestep)
                    )
                )
                substep_distances.append(_finite_float(substep_distance_cm))
                if hold_was_active:
                    hold_substep_distances.append(
                        _finite_float(substep_distance_cm)
                    )
                actuator_force = np.asarray(
                    shadow_data.actuator_force, dtype=np.float64
                )
                generalized_force = np.asarray(
                    shadow_data.qfrc_actuator, dtype=np.float64
                )
                actuator_force_norms.append(
                    _finite_float(np.linalg.norm(actuator_force))
                )
                generalized_force_norms.append(
                    _finite_float(np.linalg.norm(generalized_force))
                )
                contact_force_norms.append(maximum_contact_force_norm)
                contact_counts.append(contact_count)

        diagnostic = {
            "episode": episode,
            "episode_seed": seed + episode,
            "target_radius_cm": float(
                np.hypot(target_position[0], target_position[1]) * 100.0
            ),
            "target_angle_degrees": float(
                np.degrees(np.arctan2(target_position[1], target_position[0]))
            ),
            "min_distance_cm": _finite_float(min_distance_cm),
            "final_distance_cm": _finite_float(final_distance_cm),
            "first_reach_step": first_reach_step,
            "max_held_steps": max_held_steps,
            "in_tolerance_steps": in_tolerance_steps,
            "hold_interruptions": hold_interruptions,
            "reset_to_first_reach_control_steps": first_reach_step,
            "max_substep_distance_cm": _finite_max(substep_distances),
            "max_substep_distance_during_hold_cm": _finite_max(
                hold_substep_distances
            ),
            "peak_actuator_force_norm": _finite_max(actuator_force_norms),
            "peak_generalized_actuator_force_norm": _finite_max(
                generalized_force_norms
            ),
            "peak_contact_force_norm": _finite_max(contact_force_norms),
            "max_contact_count": max(contact_counts, default=0),
        }
        episode_results.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                # Scenario task outcome, not Gymnasium termination.
                "success": success,
                "reward_total": reward_total,
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
        episode_diagnostics.append(diagnostic)
        episode_traces.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_position_meters": _json_value(target_position),
                "target_radius_cm": diagnostic["target_radius_cm"],
                "target_angle_degrees": diagnostic["target_angle_degrees"],
                "reset_state": {
                    "qpos": _json_value(reset_qpos),
                    "qvel": _json_value(reset_qvel),
                    "qacc": _json_value(reset_qacc),
                    "end_effector_position": _json_value(reset_end_effector),
                    "distance_cm": _finite_float(reset_distance_cm),
                    "ik_branch_errors": _json_value(reset_branch_errors),
                },
                "control_steps": control_trace,
                "internal_substeps": substep_trace,
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": 5,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "success_percent": 100 * successes / episodes,
        "episode_results": episode_results,
        # Researcher-owned evidence for distinguishing reach failures from hold
        # failures and checking whether performance varies by target geometry.
        "research_evidence": {
            "controller_activation_id": controller_activation_id,
            "controller_callable_path": controller_callable_path,
            "episode_diagnostics": episode_diagnostics,
            "model_summary": model_summary,
            "trace_schema": _trace_schema(env),
            "episode_traces": episode_traces,
            "units": {"distance": "cm", "time": "control_steps"},
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
