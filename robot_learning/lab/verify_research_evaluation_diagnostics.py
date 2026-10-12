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

    q_initial = np.asarray([0.10, 0.20], dtype=np.float64)
    q_open = _reference_ik(_position(np.asarray([0.30, 0.80])), +1.0)
    q_folded = _reference_ik(_position(np.asarray([0.30, 0.80])), -1.0)
    target = _position(q_open)
    data.mocap_pos[0] = target
    _set_state(model, data, q_initial, np.zeros(2))
    state = initialize_episode_diagnostics(model, data, target, interval)

    _set_state(model, data, q_open, np.asarray([3.0, 4.0]))
    update_episode_diagnostics(state, model, data, in_tolerance=True)
    _set_state(model, data, q_folded, np.zeros(2))
    update_episode_diagnostics(state, model, data, in_tolerance=True)
    _set_state(model, data, q_folded, np.asarray([6.0, 8.0]))
    update_episode_diagnostics(state, model, data, in_tolerance=True)
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
        },
        "the complete diagnostic field set is required",
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

    _write(
        output,
        {
            "mode": "behavioral",
            "observed": observed,
            "expected": {
                "joint_speed_norm_rad_per_s": expected_joint_speeds,
                "cartesian_speed_m_per_s": expected_cartesian_speeds,
                "joint_limit_margin_rad": expected_margin,
                "first_entry_branch": "open",
                "final_boundary_branch": "folded",
                "reset_first_entry": None,
            },
            "checked_scope": [
                "repeated post-step updates",
                "first-tolerance entry and final boundary snapshots",
                "compiled joint-limit margin",
                "actual end-effector displacement over 20 ms intervals",
                "analytic open/folded labeling and nearest-branch context",
                "diagnostic reset isolation",
            ],
            "unchecked_scope": [
                "learned-policy evaluation",
                "protected benchmark semantics",
                "intra-physics-step excursions",
            ],
        },
    )


def _compatibility_check(output: Path) -> None:
    env = TwoJointArmReachEnv(
        target_radius_range=(0.15, 0.15),
        max_episode_steps=3,
    )
    try:
        _, _ = env.reset(seed=17)
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
        state = initialize_episode_diagnostics(
            env.model,
            env.data,
            target,
            env.model.opt.timestep * env.frame_skip,
        )
        for action in (
            np.zeros(2, dtype=np.float32),
            np.asarray([0.25, -0.25], dtype=np.float32),
            np.zeros(2, dtype=np.float32),
        ):
            _, _, terminated, truncated, info = env.step(action)
            update_episode_diagnostics(
                state,
                env.model,
                env.data,
                in_tolerance=bool(info.get("held_steps", 0) > 0),
            )
            if terminated or truncated:
                break
        observed = finalize_episode_diagnostics(state)
        _assert(
            observed["final_joint_speed_norm_rad_per_s"] is not None
            and observed["final_cartesian_speed_m_per_s"] is not None,
            "production environment steps must reach a final diagnostic boundary",
        )
        _, _ = env.reset(seed=18)
        fresh = initialize_episode_diagnostics(
            env.model,
            env.data,
            np.asarray(env.data.mocap_pos[0], dtype=np.float64),
            env.model.opt.timestep * env.frame_skip,
        )
        _assert(
            finalize_episode_diagnostics(fresh)["ik_branch_context"]["first_entry"]
            is None,
            "production reset must clear the prior entry snapshot",
        )
    finally:
        env.close()

    _write(
        output,
        {
            "mode": "compatibility",
            "observed": {
                "production_path": "TwoJointArmReachEnv.reset/step plus diagnostic helpers",
                "bounded_steps": 3,
                "reset_repeated": True,
            },
            "expected": {
                "final_boundary_fields_present": True,
                "reset_clears_first_entry": True,
            },
            "checked_scope": [
                "artifact-independent production environment reset and steps",
                "diagnostic initialization, repeated updates, finalization, and reset",
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
