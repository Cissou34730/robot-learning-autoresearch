"""Defect-sensitive verification for research evaluation diagnostics.

This module is intended for the existing ``python_module`` instrument.  It
does not evaluate a learned policy or make a scientific claim; it checks the
diagnostic bookkeeping against controlled kinematic states.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.scenario.evaluation import (
    _validated_physics_step_distances,
    finalize_episode_diagnostics,
    initialize_episode_diagnostics,
    update_episode_diagnostics,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _assert_close(actual: float, expected: float, message: str) -> None:
    _assert(
        bool(np.isclose(actual, expected, rtol=1e-9, atol=1e-9)),
        f"{message}: observed {actual!r}, expected {expected!r}",
    )


def _position(qpos: np.ndarray) -> np.ndarray:
    shoulder, elbow = qpos
    return np.asarray(
        [
            UPPER_ARM_LENGTH * np.cos(shoulder)
            + FOREARM_LENGTH * np.cos(shoulder + elbow),
            UPPER_ARM_LENGTH * np.sin(shoulder)
            + FOREARM_LENGTH * np.sin(shoulder + elbow),
            0.02,
        ],
        dtype=np.float64,
    )


def _reference_planar_jacobian(qpos: np.ndarray) -> np.ndarray:
    shoulder, elbow = qpos
    distal_angle = shoulder + elbow
    return np.asarray(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(shoulder)
                - FOREARM_LENGTH * np.sin(distal_angle),
                -FOREARM_LENGTH * np.sin(distal_angle),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(shoulder)
                + FOREARM_LENGTH * np.cos(distal_angle),
                FOREARM_LENGTH * np.cos(distal_angle),
            ],
        ],
        dtype=np.float64,
    )


def _reference_jacobian_summary(qpos: np.ndarray) -> dict:
    singular_values = np.linalg.svd(
        _reference_planar_jacobian(qpos), compute_uv=False
    )
    rank_tolerance = (
        2 * np.finfo(np.float64).eps * float(np.max(singular_values))
    )
    rank = int(np.count_nonzero(singular_values > rank_tolerance))
    return {
        "singular_values": singular_values,
        "rank": rank,
        "rank_deficient": rank < 2,
        "condition_number": (
            None
            if rank < 2
            else float(singular_values[0] / singular_values[-1])
        ),
    }


def _reference_ik(target: np.ndarray, elbow: float) -> np.ndarray:
    radius_squared = float(target[0] ** 2 + target[1] ** 2)
    cosine = (
        radius_squared
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = float(elbow * np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = float(
        np.arctan2(target[1], target[0])
        - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )
    return np.asarray([shoulder, elbow], dtype=np.float64)


def _set_state(model, data, qpos: np.ndarray, qvel: np.ndarray) -> None:
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    for index in range(2):
        data.qpos[int(model.jnt_qposadr[index])] = qpos[index]
        data.qvel[int(model.jnt_dofadr[index])] = qvel[index]
    mujoco.mj_forward(model, data)


def _behavioral_check(output: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    interval = 0.020

    # The first diagnostic boundary is the compiled reset posture, which is
    # singular for planar Cartesian motion.
    q_initial = np.asarray([0.0, 0.0], dtype=np.float64)
    q_open = _reference_ik(_position(np.asarray([0.30, 0.80])), +1.0)
    q_folded = _reference_ik(_position(np.asarray([0.30, 0.80])), -1.0)
    target = _position(q_open)
    data.mocap_pos[0] = target
    _set_state(model, data, q_initial, np.zeros(2))
    state = initialize_episode_diagnostics(model, data, target, interval)

    data.ctrl[:] = np.asarray([0.25, -0.40])
    _set_state(model, data, q_open, np.asarray([3.0, 4.0]))
    update_episode_diagnostics(
        state,
        model,
        data,
        in_tolerance=True,
        applied_action=data.ctrl.copy(),
        held_steps=1,
    )
    data.ctrl[:] = np.asarray([-0.20, 0.30])
    _set_state(model, data, q_folded, np.zeros(2))
    update_episode_diagnostics(
        state,
        model,
        data,
        in_tolerance=False,
        applied_action=data.ctrl.copy(),
        held_steps=0,
    )
    data.ctrl[:] = np.asarray([0.70, -0.80])
    _set_state(model, data, q_folded, np.asarray([6.0, 8.0]))
    update_episode_diagnostics(
        state,
        model,
        data,
        in_tolerance=True,
        applied_action=data.ctrl.copy(),
        held_steps=1,
    )
    observed = finalize_episode_diagnostics(state)

    ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    expected_margin = float(
        np.min(
            np.minimum(
                np.vstack([q_open, q_folded, q_folded]) - ranges[:, 0],
                ranges[:, 1] - np.vstack([q_open, q_folded, q_folded]),
            )
        )
    )
    expected_cartesian_speeds = [
        np.linalg.norm(_position(q_open) - _position(q_initial)) / interval,
        np.linalg.norm(_position(q_folded) - _position(q_open)) / interval,
        0.0,
    ]
    expected_joint_speeds = [5.0, 0.0, 10.0]

    _assert(
        set(observed) >= {
            "max_joint_speed_norm_rad_per_s",
            "first_entry_joint_speed_norm_rad_per_s",
            "final_joint_speed_norm_rad_per_s",
            "max_cartesian_speed_m_per_s",
            "first_entry_cartesian_speed_m_per_s",
            "final_cartesian_speed_m_per_s",
            "min_joint_limit_margin_rad",
            "first_entry_joint_limit_margin_rad",
            "final_joint_limit_margin_rad",
            "ik_branch_context",
            "trajectory_trace",
        },
        "the complete diagnostic field set is required",
    )
    trace = observed["trajectory_trace"]
    _assert(
        [row["control_step"] for row in trace] == [0, 1, 2, 3],
        "trajectory control steps must include reset and every update",
    )
    _assert(
        [row["held_steps"] for row in trace] == [0, 1, 0, 1]
        and [row["in_tolerance"] for row in trace]
        == [False, True, False, True],
        "trajectory must expose the in-tolerance transition and hold state",
    )
    _assert(
        trace[0]["applied_clipped_action"] is None
        and trace[1]["applied_clipped_action"] == [0.25, -0.4],
        "trajectory must capture the applied action after each update",
    )
    _assert(
        np.allclose(trace[1]["qpos_rad"], q_open)
        and np.allclose(trace[3]["qvel_rad_per_s"], [6.0, 8.0])
        and np.isclose(
            trace[1]["target_relative_distance_m"],
            np.linalg.norm(target - _position(q_open)),
        ),
        "trajectory must capture state and target-relative distance",
    )
    _assert_close(
        trace[1]["joint_limit_margin_rad"],
        float(np.min(np.minimum(q_open - ranges[:, 0], ranges[:, 1] - q_open))),
        "trajectory joint-limit margin",
    )
    for field in (
        "qpos_rad",
        "qvel_rad_per_s",
        "end_effector_position_m",
        "target_relative_position_m",
        "target_relative_distance_m",
        "jacobian",
        "radial_cartesian_velocity_m_per_s",
        "tangential_cartesian_velocity_m_per_s",
        "joint_limit_margin_rad",
        "physics_step_distances_cm",
    ):
        _assert(field in trace[1], f"trajectory field is missing: {field}")

    reset_jacobian = _reference_jacobian_summary(q_initial)
    reset_record = trace[0]["jacobian"]
    _assert(
        reset_record["rank"] == 1
        and reset_record["rank_deficient"] is True
        and reset_record["condition_number"] is None,
        "reset singularity needs an explicit rank-deficient condition",
    )
    for actual, expected in zip(
        reset_record["singular_values"],
        reset_jacobian["singular_values"],
    ):
        _assert_close(actual, float(expected), "reset Jacobian singular value")

    bent_jacobian = _reference_jacobian_summary(q_open)
    bent_record = trace[1]["jacobian"]
    _assert(
        bent_record["rank"] == bent_jacobian["rank"] == 2
        and bent_record["rank_deficient"] is False,
        "a bent state must have full planar Jacobian rank",
    )
    for actual, expected in zip(
        bent_record["singular_values"],
        bent_jacobian["singular_values"],
    ):
        _assert_close(actual, float(expected), "bent Jacobian singular value")
    _assert_close(
        bent_record["condition_number"],
        float(bent_jacobian["condition_number"]),
        "bent Jacobian condition number",
    )

    # Check signed radial/tangential velocity against an independent Jacobian
    # at a bent state that is not at the target.
    trace_reference_state = initialize_episode_diagnostics(
        model, data, target, interval
    )
    q_bent = np.asarray([0.20, 0.30], dtype=np.float64)
    qvel_bent = np.asarray([1.0, -2.0], dtype=np.float64)
    _set_state(model, data, q_bent, qvel_bent)
    update_episode_diagnostics(
        trace_reference_state,
        model,
        data,
        in_tolerance=False,
        applied_action=np.asarray([0.1, 0.2]),
        held_steps=0,
    )
    velocity_record = finalize_episode_diagnostics(trace_reference_state)[
        "trajectory_trace"
    ][1]
    target_direction = target[:2] - _position(q_bent)[:2]
    target_direction /= np.linalg.norm(target_direction)
    tangent_direction = np.asarray(
        [-target_direction[1], target_direction[0]], dtype=np.float64
    )
    reference_velocity = _reference_planar_jacobian(q_bent) @ qvel_bent
    _assert_close(
        velocity_record["radial_cartesian_velocity_m_per_s"],
        float(np.dot(reference_velocity, target_direction)),
        "radial Cartesian velocity",
    )
    _assert_close(
        velocity_record["tangential_cartesian_velocity_m_per_s"],
        float(np.dot(reference_velocity, tangent_direction)),
        "tangential Cartesian velocity",
    )
    _assert_close(
        observed["max_joint_speed_norm_rad_per_s"],
        max(expected_joint_speeds),
        "maximum joint speed",
    )
    _assert_close(
        observed["first_entry_joint_speed_norm_rad_per_s"],
        expected_joint_speeds[0],
        "first-entry joint speed",
    )
    _assert_close(
        observed["final_joint_speed_norm_rad_per_s"],
        expected_joint_speeds[-1],
        "final joint speed",
    )
    _assert_close(
        observed["max_cartesian_speed_m_per_s"],
        max(expected_cartesian_speeds),
        "maximum Cartesian speed",
    )
    _assert_close(
        observed["first_entry_cartesian_speed_m_per_s"],
        expected_cartesian_speeds[0],
        "first-entry Cartesian speed",
    )
    _assert_close(
        observed["final_cartesian_speed_m_per_s"],
        expected_cartesian_speeds[-1],
        "final Cartesian speed",
    )
    _assert_close(
        observed["min_joint_limit_margin_rad"],
        expected_margin,
        "minimum joint-limit margin",
    )
    _assert_close(
        observed["first_entry_joint_limit_margin_rad"],
        float(np.min(np.minimum(q_open - ranges[:, 0], ranges[:, 1] - q_open))),
        "first-entry joint-limit margin",
    )
    _assert_close(
        observed["final_joint_limit_margin_rad"],
        float(
            np.min(np.minimum(q_folded - ranges[:, 0], ranges[:, 1] - q_folded))
        ),
        "final joint-limit margin",
    )

    branch_context = observed["ik_branch_context"]
    _assert(
        set(branch_context["target"]["feasible_branches"]) == {"open", "folded"},
        "both analytic branches should be feasible for the controlled target",
    )
    _assert(
        branch_context["target"]["solutions"]["open"]["elbow_rad"] >= 0.0
        and branch_context["target"]["solutions"]["folded"]["elbow_rad"] <= 0.0,
        "open and folded branch labels must not be swapped",
    )
    _assert(
        branch_context["first_entry"]["nearest_branch"] == "open",
        "the first entry must identify the open branch",
    )
    _assert(
        branch_context["final_boundary"]["nearest_branch"] == "folded",
        "the final boundary must identify the folded branch",
    )

    # A fresh diagnostic state must not carry maxima, minima, or entry state
    # across a reset.
    _set_state(model, data, q_initial, np.zeros(2))
    fresh = initialize_episode_diagnostics(model, data, target, interval)
    _set_state(model, data, q_initial, np.zeros(2))
    update_episode_diagnostics(fresh, model, data, in_tolerance=False)
    reset_observed = finalize_episode_diagnostics(fresh)
    _assert(
        reset_observed["first_entry_joint_speed_norm_rad_per_s"] is None,
        "reset must clear first-entry state",
    )
    _assert_close(
        reset_observed["max_joint_speed_norm_rad_per_s"],
        0.0,
        "reset maximum joint speed",
    )
    _assert(
        len(reset_observed["trajectory_trace"]) == 2
        and reset_observed["trajectory_trace"][0]["control_step"] == 0,
        "a fresh diagnostic state must start a fresh trajectory trace",
    )

    # Use an independent within-interval reference.  The second held
    # interval has one out-of-tolerance physics step; the third does not.
    telemetry_state = initialize_episode_diagnostics(
        model,
        data,
        target,
        interval,
        success_threshold=0.075,
    )
    telemetry_sequences = (
        (False, (0.02, 0.08, 0.03)),
        (True, (0.04, 0.09, 0.05)),
        (True, (0.06, 0.07, 0.05)),
        (False, (0.20, 0.04, 0.03)),
    )
    for in_tolerance, distances in telemetry_sequences:
        update_episode_diagnostics(
            telemetry_state,
            model,
            data,
            in_tolerance=in_tolerance,
            physics_step_distances=distances,
        )
    telemetry_observed = finalize_episode_diagnostics(telemetry_state)
    _assert_close(
        telemetry_observed["max_physics_step_distance_cm"],
        20.0,
        "maximum physics-step distance",
    )
    _assert_close(
        telemetry_observed["max_physics_step_distance_during_hold_cm"],
        9.0,
        "maximum held-interval physics-step distance",
    )
    _assert(
        telemetry_observed[
            "hold_intervals_with_out_of_tolerance_physics_step"
        ]
        == 1,
        "only one held interval should contain an out-of-tolerance step",
    )
    _assert(
        telemetry_observed["out_of_tolerance_physics_substeps_during_hold"] == 1,
        "only one held physics substep should be out of tolerance",
    )
    telemetry_reset = finalize_episode_diagnostics(
        initialize_episode_diagnostics(
            model,
            data,
            target,
            interval,
            success_threshold=0.075,
        )
    )
    _assert_close(
        telemetry_reset["max_physics_step_distance_cm"],
        0.0,
        "reset maximum physics-step distance",
    )
    _assert(
        telemetry_reset[
            "hold_intervals_with_out_of_tolerance_physics_step"
        ]
        == 0,
        "reset must clear held-interval physics-step counts",
    )
    _assert(
        [len(row["physics_step_distances_cm"]) for row in telemetry_observed[
            "trajectory_trace"
        ][1:]]
        == [3, 3, 3, 3],
        "each updated trace row must retain its bounded physics-step distances",
    )
    _assert(
        telemetry_observed["trajectory_trace"][2]["physics_step_distances_cm"]
        == [4.0, 9.0, 5.0],
        "trajectory must retain physics-step distances in boundary order",
    )

    _write(
        output,
        {
            "mode": "behavioral",
            "observed": {
                "boundary_diagnostics": observed,
                "physics_step_diagnostics": telemetry_observed,
            },
            "expected": {
                "joint_speed_norm_rad_per_s": expected_joint_speeds,
                "cartesian_speed_m_per_s": expected_cartesian_speeds,
                "joint_limit_margin_rad": expected_margin,
                "first_entry_branch": "open",
                "final_boundary_branch": "folded",
                "reset_first_entry": None,
                "max_physics_step_distance_cm": 20.0,
                "max_physics_step_distance_during_hold_cm": 9.0,
                "hold_intervals_with_out_of_tolerance_physics_step": 1,
                "out_of_tolerance_physics_substeps_during_hold": 1,
                "trajectory_reset_rank_deficient": True,
                "trajectory_rows_include_actions_and_jacobians": True,
            },
            "checked_scope": [
                "repeated post-step updates",
                "first-tolerance entry and final boundary snapshots",
                "compiled joint-limit margin",
                "actual end-effector displacement over 20 ms intervals",
                "analytic open/folded labeling and nearest-branch context",
                "diagnostic reset isolation",
                "repeated within-interval telemetry updates",
                "hold versus non-hold interval classification",
                "threshold-based out-of-tolerance substep counting",
                "independent compiled-versus-analytic Jacobian singular values",
                "explicit rank-deficient condition representation at reset",
                "per-boundary qpos/qvel/action, distance, velocity, and limit margin",
                "trace control-step ordering and reset isolation",
            ],
            "unchecked_scope": [
                "learned-policy evaluation",
                "protected benchmark semantics",
                "whether a learned policy reaches a scientific performance target",
            ],
        },
    )


def _compatibility_check(output: Path) -> None:
    env = TwoJointArmReachEnv(
        target_radius_range=(0.15, 0.15),
        success_threshold=0.20,
        hold_seconds=0.10,
        max_episode_steps=4,
    )
    clipped_env = TwoJointArmReachEnv(
        target_radius_range=(0.15, 0.15),
        success_threshold=0.20,
        hold_seconds=0.10,
        max_episode_steps=4,
    )
    try:
        _, _ = env.reset(seed=17)
        _assert(env.physics_step_distances == (), "reset must clear telemetry")
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
        state = initialize_episode_diagnostics(
            env.model,
            env.data,
            target,
            env.model.opt.timestep * env.frame_skip,
            success_threshold=env.success_threshold,
        )
        hold_flags = []
        interval_lengths = []
        for index in range(3):
            if index < 2:
                env.data.mocap_pos[0] = env.data.site("end_effector").xpos
            else:
                env.data.mocap_pos[0] = (
                    env.data.site("end_effector").xpos
                    + np.asarray([1.0, 0.0, 0.0])
                )
            control_action = (
                np.asarray([2.0, -2.0], dtype=np.float32)
                if index == 0
                else np.zeros(2, dtype=np.float32)
            )
            _, _, terminated, truncated, info = env.step(control_action)
            published_distances = env.physics_step_distances
            _assert(
                isinstance(published_distances, tuple)
                and len(published_distances) == env.frame_skip,
                "each production step must publish one distance per mj_step",
            )
            _assert(
                all(
                    np.isfinite(value) and value >= 0.0
                    for value in published_distances
                ),
                "production telemetry must be finite and nonnegative",
            )
            distances = _validated_physics_step_distances(env)
            _assert_close(
                distances[-1],
                float(info["distance"]),
                "last physics distance must equal the policy-step distance",
            )
            interval_lengths.append(len(distances))
            hold_flags.append(bool(info["held_steps"] > 0))
            update_episode_diagnostics(
                state,
                env.model,
                env.data,
                in_tolerance=bool(info.get("held_steps", 0) > 0),
                physics_step_distances=distances,
                success_threshold=env.success_threshold,
                applied_action=np.asarray(env.data.ctrl, dtype=np.float64).copy(),
                held_steps=int(info.get("held_steps", 0)),
            )
            if terminated or truncated:
                break
        observed = finalize_episode_diagnostics(state)
        production_trace = observed["trajectory_trace"]
        _assert(
            len(production_trace) == len(interval_lengths) + 1
            and production_trace[0]["physics_step_distances_cm"] == [],
            "production trace must include reset and only executed steps",
        )
        _assert(
            production_trace[1]["applied_clipped_action"] == [1.0, -1.0],
            "production trace must capture the clipped env.data.ctrl",
        )
        _assert(
            all(
                len(row["physics_step_distances_cm"]) == env.frame_skip
                for row in production_trace[1:]
            ),
            "production trace must retain every bounded physics-step distance",
        )
        _assert(
            hold_flags[:2] == [True, True] and hold_flags[2:] == [False],
            "controlled target changes must exercise hold and non-hold intervals",
        )
        _assert(
            observed["max_physics_step_distance_cm"]
            >= observed["max_physics_step_distance_during_hold_cm"],
            "all-interval maximum must include held intervals",
        )
        _assert(
            observed["final_joint_speed_norm_rad_per_s"] is not None
            and observed["final_cartesian_speed_m_per_s"] is not None,
            "production environment steps must reach a final diagnostic boundary",
        )
        _, _ = env.reset(seed=18)
        _assert(env.physics_step_distances == (), "reset must isolate telemetry")
        fresh = initialize_episode_diagnostics(
            env.model,
            env.data,
            np.asarray(env.data.mocap_pos[0], dtype=np.float64),
            env.model.opt.timestep * env.frame_skip,
            success_threshold=env.success_threshold,
        )
        _assert(
            finalize_episode_diagnostics(fresh)["ik_branch_context"]["first_entry"]
            is None,
            "production reset must clear the prior entry snapshot",
        )

        # Clipping remains a policy-step invariant: an out-of-range action and
        # its clipped equivalent must have identical controlled consequences.
        obs_a, _ = clipped_env.reset(seed=23)
        result_a = clipped_env.step(np.asarray([2.0, -2.0], dtype=np.float32))
        obs_b, _ = clipped_env.reset(seed=23)
        result_b = clipped_env.step(np.asarray([1.0, -1.0], dtype=np.float32))
        _assert(np.allclose(obs_a, obs_b), "seeded reset observations must match")
        _assert(
            np.allclose(result_a[0], result_b[0]),
            "action clipping changed observation",
        )
        _assert_close(result_a[1], result_b[1], "action clipping changed reward")
        _assert(
            result_a[2] == result_b[2] and result_a[3] == result_b[3],
            "action clipping changed termination or truncation",
        )
    finally:
        env.close()
        clipped_env.close()

    _write(
        output,
        {
            "mode": "compatibility",
            "observed": {
                "production_path": "TwoJointArmReachEnv.reset/step plus diagnostic helpers",
                "bounded_steps": 3,
                "interval_lengths": interval_lengths,
                "hold_flags": hold_flags,
                "reset_repeated": True,
                "reset_telemetry": (),
                "trace_rows": len(production_trace),
                "first_applied_clipped_action": production_trace[1][
                    "applied_clipped_action"
                ],
            },
            "expected": {
                "final_boundary_fields_present": True,
                "reset_clears_first_entry": True,
                "physics_steps_per_interval": env.frame_skip,
                "hold_flags": [True, True, False],
                "clipped_action_equivalence": True,
            },
            "checked_scope": [
                "artifact-independent production environment reset and steps",
                "diagnostic initialization, repeated updates, finalization, and reset",
                "repeated internal-step telemetry publication",
                "hold/non-hold transition classification using the environment threshold",
                "reset isolation of the latest telemetry interval",
                "preservation of action clipping and policy-step consequences",
                "artifact-independent production trajectory trace and Jacobian fields",
            ],
            "unchecked_scope": [
                "learned-policy runtime loading",
                "full evaluation artifact generation",
                "scientific validity of any measured behavior",
            ],
        },
    )


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("behavioral", "compatibility"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "compatibility":
        _compatibility_check(args.output)
    else:
        _behavioral_check(args.output)


if __name__ == "__main__":
    main()
