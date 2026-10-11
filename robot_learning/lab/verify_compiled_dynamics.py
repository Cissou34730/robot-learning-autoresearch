"""Executable, defect-sensitive checks for the compiled dynamics measurement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from robot_learning.lab import compiled_dynamics


FK_POSES = (
    np.array([0.0, 0.0], dtype=np.float64),
    np.array([0.6, -0.8], dtype=np.float64),
    np.array([-1.1, 1.2], dtype=np.float64),
)
TRACE_CONTROL_STEPS = 3
INTERNAL_STEPS = 10
TOLERANCE = 0.01


def _position(data: mujoco.MjData, site_id: int) -> np.ndarray:
    return np.asarray(data.site_xpos[site_id], dtype=np.float64).copy()


def _write(path: Path, artifact: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(compiled_dynamics._jsonable(artifact), handle, indent=2)
        handle.write("\n")


def run_checks() -> dict[str, Any]:
    model, ids = compiled_dynamics.load_compiled_model()
    data = mujoco.MjData(model)
    checks: list[dict[str, Any]] = []

    def fail(message: str) -> None:
        error = AssertionError(message)
        error.checks = checks  # type: ignore[attr-defined]
        raise error

    fk_errors = []
    for pose in FK_POSES:
        mujoco.mj_resetData(model, data)
        data.qpos[:] = pose
        data.qvel[:] = 0.0
        mujoco.mj_forward(model, data)
        observed = _position(data, ids["site_id"])
        expected = np.array(
            [
                0.12 * np.cos(pose[0]) + 0.10 * np.cos(pose[0] + pose[1]),
                0.12 * np.sin(pose[0]) + 0.10 * np.sin(pose[0] + pose[1]),
                0.02,
            ],
            dtype=np.float64,
        )
        error = float(np.max(np.abs(observed - expected)))
        fk_errors.append(error)
        if error > 1e-12:
            fail(f"forward kinematics mismatch at {pose.tolist()}: {error}")
    checks.append(
        {
            "name": "analytic_forward_kinematics",
            "expected": {
                "formula": "[0.12 cos(q1)+0.10 cos(q1+q2), "
                "0.12 sin(q1)+0.10 sin(q1+q2), 0.02]",
                "maximum_error_m": "<= 1e-12",
                "pose_count": len(FK_POSES),
            },
            "observed": {
                "maximum_error_m": max(fk_errors),
                "errors_m": fk_errors,
            },
        }
    )

    invariant_pose = np.array([0.4, -0.7], dtype=np.float64)
    mujoco.mj_resetData(model, data)
    data.qpos[:] = invariant_pose
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    initial_qpos = data.qpos.copy()
    initial_qvel = data.qvel.copy()
    max_qpos_drift = 0.0
    max_qvel_magnitude = 0.0
    for _ in range(40):
        mujoco.mj_step(model, data)
        max_qpos_drift = max(
            max_qpos_drift, float(np.max(np.abs(data.qpos - initial_qpos)))
        )
        max_qvel_magnitude = max(
            max_qvel_magnitude, float(np.max(np.abs(data.qvel)))
        )
    if max_qpos_drift > 1e-12 or max_qvel_magnitude > 1e-12:
        fail(
            "zero-action, zero-velocity state changed: "
            f"qpos drift={max_qpos_drift}, qvel={max_qvel_magnitude}"
        )
    checks.append(
        {
            "name": "zero_action_state_invariance",
            "expected": {
                "initial_qpos_rad": invariant_pose.tolist(),
                "internal_updates": 40,
                "maximum_qpos_drift": "<= 1e-12 rad",
                "maximum_qvel": "<= 1e-12 rad/s",
            },
            "observed": {
                "maximum_qpos_drift_rad": max_qpos_drift,
                "maximum_qvel_rad_per_s": max_qvel_magnitude,
            },
        }
    )

    target = np.array([0.15, 0.04, 0.02], dtype=np.float64)
    controls = np.asarray(
        [[0.25, -0.15], [-0.25, 0.15], [0.1, -0.1]], dtype=np.float64
    )
    trace_lengths = []
    update_magnitudes = []
    repeated_update_counts = []
    for _ in range(3):
        trace = compiled_dynamics.run_control_trace(
            model,
            ids,
            qpos=[0.6, -0.8],
            qvel=[0.0, 0.0],
            target=target,
            controls=controls,
        )
        count = len(trace["steps"]["time_seconds"])
        expected_count = TRACE_CONTROL_STEPS * INTERNAL_STEPS
        if count != expected_count:
            fail(f"internal trace has {count} samples, expected {expected_count}")
        if trace["initial"]["time_seconds"] != 0.0:
            fail("reset-like trace did not start at time zero")
        qpos_trace = np.asarray(trace["steps"]["qpos"], dtype=np.float64)
        update_magnitudes.append(
            float(np.max(np.abs(qpos_trace[-1] - qpos_trace[0])))
        )
        repeated_update_counts.append(
            int(np.sum(np.linalg.norm(np.diff(qpos_trace, axis=0), axis=1) > 1e-15))
        )
        trace_lengths.append(count)
    if not all(value >= expected_count - 2 for value in repeated_update_counts):
        fail("repeated internal control updates did not update qpos")
    checks.append(
        {
            "name": "repeated_internal_updates_and_reset_like_traces",
            "expected": {
                "reinitializations": 3,
                "samples_per_trace": TRACE_CONTROL_STEPS * INTERNAL_STEPS,
                "time_step_seconds": 0.002,
                "nonzero_control_changes_qpos": True,
                "repeated_updates_per_trace": f">= {TRACE_CONTROL_STEPS * INTERNAL_STEPS - 2}",
            },
            "observed": {
                "trace_lengths": trace_lengths,
                "qpos_change_first_to_last_rad": update_magnitudes,
                "repeated_update_counts": repeated_update_counts,
            },
        }
    )

    # Every control boundary is inside, while two deliberately chosen
    # interior samples are outside.  This is independent of MuJoCo dynamics
    # and directly tests the sampled-versus-continuous distinction.
    constructed_distances = np.array(
        [0.009, 0.012, 0.009, 0.009, 0.009, 0.009, 0.011, 0.009],
        dtype=np.float64,
    )
    summary = compiled_dynamics.summarize_distance_trace(
        constructed_distances,
        tolerance=TOLERANCE,
        internal_steps_per_control=4,
    )
    boundary_values = constructed_distances[3::4]
    independent_boundary_result = bool(np.all(boundary_values <= TOLERANCE))
    independent_continuous_result = bool(
        np.all(constructed_distances <= TOLERANCE)
    )
    independent_excursions = int(
        np.sum(constructed_distances[np.arange(8) % 4 != 3] > TOLERANCE)
    )
    if (
        not independent_boundary_result
        or independent_continuous_result
        or independent_excursions != 2
        or summary["boundary_all_within_tolerance"] is not True
        or summary["continuous_all_within_tolerance"] is not False
        or summary["interior_excursion_count"] != 2
    ):
        fail("sampled/continuous tolerance excursion was not detected")
    checks.append(
        {
            "name": "sampled_vs_continuous_tolerance_excursion",
            "expected": {
                "boundary_all_within_tolerance": True,
                "continuous_all_within_tolerance": False,
                "interior_excursion_count": 2,
            },
            "observed": {
                "independent_boundary_all_within_tolerance": independent_boundary_result,
                "independent_continuous_all_within_tolerance": independent_continuous_result,
                "independent_interior_excursion_count": independent_excursions,
                "analyzer_summary": summary,
            },
        }
    )
    return {
        "artifact_type": "compiled_dynamics_verification",
        "status": "passed",
        "checks": checks,
        "checked_scope": [
            "compiled two-link planar forward kinematics",
            "zero-action invariance from zero velocity",
            "repeated held internal updates and reset-like reinitialization",
            "sampled versus continuous tolerance analysis",
        ],
        "unchecked_scope": [
            "learned-policy behavior or success rates",
            "protected benchmark and evaluator semantics",
            "scientific interpretation of any measured dynamics",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify compiled dynamics laboratory invariants."
    )
    parser.add_argument("output", type=Path, help="JSON artifact output path")
    args = parser.parse_args()
    try:
        artifact = run_checks()
    except Exception as exc:
        artifact = {
            "artifact_type": "compiled_dynamics_verification",
            "status": "failed",
            "error": str(exc),
            "checks": getattr(exc, "checks", []),
            "checked_scope": [
                "compiled two-link planar forward kinematics",
                "zero-action invariance from zero velocity",
                "repeated held internal updates and reset-like reinitialization",
                "sampled versus continuous tolerance analysis",
            ],
            "unchecked_scope": [
                "checks after the first failing check",
                "learned-policy behavior or success rates",
                "protected benchmark and evaluator semantics",
            ],
        }
        _write(args.output, artifact)
        raise
    _write(args.output, artifact)


if __name__ == "__main__":
    main()
