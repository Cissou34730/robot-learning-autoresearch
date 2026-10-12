"""Defect-sensitive verification for a compiled dynamics artifact.

The checks use fixed timing, posture, and kinematic expectations independent
of the characterization summaries. They expose incomplete or static
artifacts; they do not certify the scientific interpretation of a measurement.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


EXPECTED_TIMESTEP = 0.002
EXPECTED_FRAME_SKIP = 10
EXPECTED_CONTROL_DT = EXPECTED_TIMESTEP * EXPECTED_FRAME_SKIP
EXPECTED_TOTAL_STEPS = 60
EXPECTED_ACTIVE_STEPS = 12
EXPECTED_ZERO_DECAY_ACTIVE_STEPS = 10
UPPER_ARM_LENGTH = 0.12
FOREARM_LENGTH = 0.10
INNER_RADIUS = 0.08
OUTER_RADIUS = 0.18
EXPECTED_POSTURE_NAMES = (
    "reset_singular",
    "inner_open",
    "inner_folded",
    "outer_open",
    "outer_folded",
)
EXPECTED_EXPERIMENT_NAMES = (
    "saturated_shoulder_step",
    "saturated_elbow_step",
    "saturated_bilateral_step",
    "zero_command_decay",
)


class VerificationError(RuntimeError):
    """Raised after a JSON result has been written for a failed check."""


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must be a JSON object")
    return value


def _require_field(mapping: dict[str, Any], field: str, label: str) -> Any:
    if field not in mapping:
        raise VerificationError(f"required field is missing: {label}.{field}")
    return mapping[field]


def _finite_vector(value: Any, length: int, label: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != length:
        raise VerificationError(f"{label} must be a list of length {length}")
    result = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(result)):
        raise VerificationError(f"{label} contains a non-finite value")
    return result


def _close(actual: float, expected: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance)


def _expected_posture_q(name: str) -> np.ndarray:
    if name == "reset_singular":
        return np.zeros(2, dtype=float)
    if name.startswith("inner_"):
        radius = INNER_RADIUS
    elif name.startswith("outer_"):
        radius = OUTER_RADIUS
    else:
        raise VerificationError(f"unknown posture name: {name}")
    branch = "open" if name.endswith("_open") else "folded"
    cosine = (
        radius * radius
        - UPPER_ARM_LENGTH * UPPER_ARM_LENGTH
        - FOREARM_LENGTH * FOREARM_LENGTH
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    elbow = elbow_magnitude if branch == "open" else -elbow_magnitude
    shoulder = -float(
        np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )
    return np.asarray([shoulder, elbow], dtype=float)


def _experiment_index(
    experiments: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for experiment in experiments:
        posture = _require_field(experiment, "posture", "experiment")
        name = _require_field(experiment, "name", "experiment")
        key = (str(posture), str(name))
        if key in index:
            raise VerificationError(f"duplicate experiment: {key}")
        index[key] = experiment
    return index


def _check_result(
    checks: list[dict[str, Any]],
    name: str,
    observed: Any,
    expected: Any,
    passed: bool,
    scope: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else "failed",
            "observed": observed,
            "expected": expected,
            "checked_scope": scope,
        }
    )


def verify(artifact_path: Path, output_path: Path) -> None:
    artifact = _require_mapping(
        json.loads(artifact_path.read_text(encoding="utf-8")),
        "characterization artifact",
    )
    checks: list[dict[str, Any]] = []
    unchecked_scope: list[str] = [
        "Scientific interpretation of compiled inertia and solver fields.",
        "Generalization beyond the five deterministic postures and commands.",
        "Policy behavior, target sampling, and official hold success.",
    ]

    contract = _require_mapping(
        _require_field(artifact, "measurement_contract", "artifact"),
        "measurement_contract",
    )
    timestep = float(_require_field(contract, "compiled_timestep_s", "contract"))
    frame_skip = int(_require_field(contract, "frame_skip", "contract"))
    control_interval = float(
        _require_field(contract, "control_interval_s", "contract")
    )
    control_rate = float(_require_field(contract, "control_rate_hz", "contract"))
    _check_result(
        checks,
        "nominal_timing",
        {
            "timestep_s": timestep,
            "frame_skip": frame_skip,
            "control_interval_s": control_interval,
            "control_rate_hz": control_rate,
        },
        {
            "timestep_s": EXPECTED_TIMESTEP,
            "frame_skip": EXPECTED_FRAME_SKIP,
            "control_interval_s": EXPECTED_CONTROL_DT,
            "control_rate_hz": 50.0,
        },
        _close(timestep, EXPECTED_TIMESTEP)
        and frame_skip == EXPECTED_FRAME_SKIP
        and _close(control_interval, EXPECTED_CONTROL_DT)
        and _close(control_rate, 50.0),
        "compiled timestep and ten-physics-step control interval",
    )

    compiled = _require_mapping(
        _require_field(artifact, "compiled_model", "artifact"), "compiled_model"
    )
    joints = _require_field(compiled, "joints", "compiled_model")
    if not isinstance(joints, list) or len(joints) != 2:
        raise VerificationError("compiled_model.joints must contain two joints")
    damping_values = []
    for joint in joints:
        joint_mapping = _require_mapping(joint, "compiled joint")
        damping_values.append(float(_require_field(joint_mapping, "damping", "joint")))
        _require_field(joint_mapping, "armature", "joint")
    options = _require_mapping(
        _require_field(compiled, "options", "compiled_model"),
        "compiled_model.options",
    )
    for field in (
        "timestep",
        "integrator",
        "solver",
        "iterations",
        "tolerance",
        "ls_iterations",
        "noslip_iterations",
        "ccd_iterations",
        "sdf_iterations",
    ):
        _require_field(options, field, "compiled_model.options")
    _check_result(
        checks,
        "positive_joint_damping",
        damping_values,
        "all compiled joint damping values > 0",
        all(value > 0.0 for value in damping_values),
        "zero-command decay assumption in the compiled joint model",
    )

    posture_values = _require_field(artifact, "postures", "artifact")
    if not isinstance(posture_values, list):
        raise VerificationError("artifact.postures must be a list")
    postures = {
        str(_require_field(posture, "name", "posture")): posture
        for posture in (_require_mapping(item, "posture") for item in posture_values)
    }
    posture_names_ok = tuple(postures) == EXPECTED_POSTURE_NAMES
    posture_q_ok = True
    posture_observed: dict[str, list[float]] = {}
    for name in EXPECTED_POSTURE_NAMES:
        if name not in postures:
            posture_q_ok = False
            continue
        q = _finite_vector(
            _require_field(postures[name], "q", f"posture {name}"),
            2,
            f"posture {name}.q",
        )
        posture_observed[name] = q.tolist()
        posture_q_ok = posture_q_ok and np.allclose(
            q, _expected_posture_q(name), rtol=1e-8, atol=1e-8
        )
    _check_result(
        checks,
        "reset_and_ik_postures",
        {"names": list(postures), "q": posture_observed},
        {
            "names": list(EXPECTED_POSTURE_NAMES),
            "q": {
                name: _expected_posture_q(name).tolist()
                for name in EXPECTED_POSTURE_NAMES
            },
        },
        posture_names_ok and posture_q_ok,
        "reset singular state plus independent inner/outer open/folded IK states",
    )

    experiments_value = _require_field(artifact, "experiments", "artifact")
    if not isinstance(experiments_value, list):
        raise VerificationError("artifact.experiments must be a list")
    experiments = [
        _require_mapping(item, "experiment") for item in experiments_value
    ]
    experiment_index = _experiment_index(experiments)
    expected_keys = {
        (posture_name, experiment_name)
        for posture_name in EXPECTED_POSTURE_NAMES
        for experiment_name in EXPECTED_EXPERIMENT_NAMES
    }
    trace_shape_ok = set(experiment_index) == expected_keys
    controls_ok = True
    timing_ok = True
    reset_repeats_ok = True
    changed_response: dict[str, float] = {}

    for key in sorted(expected_keys):
        if key not in experiment_index:
            continue
        experiment = experiment_index[key]
        name = f"{key[0]}/{key[1]}"
        active_steps = int(
            _require_field(experiment, "active_control_steps", name)
        )
        expected_active = (
            EXPECTED_ZERO_DECAY_ACTIVE_STEPS
            if key[1] == "zero_command_decay"
            else EXPECTED_ACTIVE_STEPS
        )
        trace_shape_ok = trace_shape_ok and (
            int(_require_field(experiment, "total_control_steps", name))
            == EXPECTED_TOTAL_STEPS
            and active_steps == expected_active
        )
        initial_state = _require_mapping(
            _require_field(experiment, "initial_state", name),
            f"{name}.initial_state",
        )
        initial_q = _finite_vector(
            _require_field(initial_state, "q", f"{name}.initial_state"),
            2,
            f"{name}.initial_state.q",
        )
        initial_qdot = _finite_vector(
            _require_field(initial_state, "qdot", f"{name}.initial_state"),
            2,
            f"{name}.initial_state.qdot",
        )
        reset_repeats_ok = reset_repeats_ok and np.allclose(
            initial_q, _expected_posture_q(key[0]), rtol=1e-8, atol=1e-8
        )
        reset_repeats_ok = reset_repeats_ok and np.allclose(
            initial_qdot, np.zeros(2), rtol=0.0, atol=1e-12
        )
        trace = _require_field(experiment, "trace", name)
        if not isinstance(trace, list) or len(trace) != EXPECTED_TOTAL_STEPS:
            trace_shape_ok = False
            continue
        for expected_step, record_value in enumerate(trace, start=1):
            record = _require_mapping(record_value, f"{name}.trace record")
            actual_step = int(
                _require_field(record, "control_step", f"{name}.trace")
            )
            actual_time = float(_require_field(record, "time_s", f"{name}.trace"))
            trace_shape_ok = trace_shape_ok and actual_step == expected_step
            timing_ok = timing_ok and _close(
                actual_time, expected_step * EXPECTED_CONTROL_DT
            )
            _finite_vector(
                _require_field(record, "q", f"{name}.trace"),
                2,
                f"{name}.trace.q",
            )
            _finite_vector(
                _require_field(record, "qdot", f"{name}.trace"),
                2,
                f"{name}.trace.qdot",
            )
            _finite_vector(
                _require_field(
                    record, "end_effector_position", f"{name}.trace"
                ),
                3,
                f"{name}.trace.end_effector_position",
            )
            _finite_vector(
                _require_field(
                    record, "end_effector_velocity", f"{name}.trace"
                ),
                3,
                f"{name}.trace.end_effector_velocity",
            )
            controls = _finite_vector(
                _require_field(
                    record, "commanded_controls", f"{name}.trace"
                ),
                2,
                f"{name}.trace.commanded_controls",
            )
            controls_ok = controls_ok and bool(
                np.all(controls >= -1.0) and np.all(controls <= 1.0)
            )
        first_q = _finite_vector(
            _require_field(trace[0], "q", f"{name}.trace[0]"),
            2,
            f"{name}.trace[0].q",
        )
        changed_response[name] = float(np.linalg.norm(first_q - initial_q))

    _check_result(
        checks,
        "complete_repeated_traces",
        {
            "experiment_count": len(experiments),
            "expected_count": len(expected_keys),
            "all_traces_have_expected_steps": trace_shape_ok,
            "all_repeated_resets_match_reference": reset_repeats_ok,
        },
        "five postures x four experiments x 60 control records",
        trace_shape_ok
        and reset_repeats_ok
        and len(experiment_index) == len(expected_keys),
        "repeated updates, transitions, and reset initialization across all postures",
    )
    _check_result(
        checks,
        "bounded_controls",
        {"within_closed_interval": controls_ok},
        "every recorded command is in [-1, 1]",
        controls_ok,
        "all commanded controls in every trace",
    )
    _check_result(
        checks,
        "trace_timing",
        {"all_record_times_match": timing_ok},
        "record time equals control_step x 0.020 s",
        timing_ok,
        "per-control-step timestamps",
    )
    saturated_key = "reset_singular/saturated_shoulder_step"
    if saturated_key not in changed_response:
        raise VerificationError("reset saturated shoulder experiment is missing")
    saturated_command = _finite_vector(
        _require_field(
            experiment_index[("reset_singular", "saturated_shoulder_step")],
            "active_command",
            "reset saturated shoulder experiment",
        ),
        2,
        "reset saturated shoulder command",
    )
    saturated_trace_command = _finite_vector(
        _require_field(
            _require_field(
                experiment_index[("reset_singular", "saturated_shoulder_step")],
                "trace",
                "reset saturated shoulder experiment",
            )[0],
            "commanded_controls",
            "reset saturated shoulder first record",
        ),
        2,
        "reset saturated shoulder first trace command",
    )
    _check_result(
        checks,
        "nonzero_saturated_response",
        {
            "active_command": saturated_command.tolist(),
            "first_trace_command": saturated_trace_command.tolist(),
            "reset_singular_first_step_q_change_rad": changed_response[saturated_key],
        },
        "active and first recorded command [1, 0] with positive response after one interval",
        np.allclose(saturated_command, [1.0, 0.0], rtol=0.0, atol=1e-12)
        and np.allclose(
            saturated_trace_command, [1.0, 0.0], rtol=0.0, atol=1e-12
        )
        and changed_response[saturated_key] > 1e-9,
        "reset singular saturated motor command",
    )

    zero_decay = experiment_index[("reset_singular", "zero_command_decay")]
    zero_trace = _require_field(zero_decay, "trace", "zero_command_decay")
    active_record = _require_mapping(
        zero_trace[EXPECTED_ZERO_DECAY_ACTIVE_STEPS - 1],
        "zero_command_decay active record",
    )
    first_zero_record = _require_mapping(
        zero_trace[EXPECTED_ZERO_DECAY_ACTIVE_STEPS],
        "zero_command_decay first zero record",
    )
    final_zero_record = _require_mapping(
        zero_trace[-1], "zero_command_decay final record"
    )
    active_command = _finite_vector(
        _require_field(active_record, "commanded_controls", "zero_command_decay"),
        2,
        "zero_command_decay active controls",
    )
    first_zero_command = _finite_vector(
        _require_field(
            first_zero_record, "commanded_controls", "zero_command_decay"
        ),
        2,
        "zero_command_decay first zero controls",
    )
    active_speed = float(
        np.linalg.norm(
            _finite_vector(
                _require_field(active_record, "qdot", "zero_command_decay"),
                2,
                "zero_command_decay active qdot",
            )
        )
    )
    final_speed = float(
        np.linalg.norm(
            _finite_vector(
                _require_field(final_zero_record, "qdot", "zero_command_decay"),
                2,
                "zero_command_decay final qdot",
            )
        )
    )
    _check_result(
        checks,
        "zero_command_velocity_decay",
        {
            "active_command": active_command.tolist(),
            "first_zero_command": first_zero_command.tolist(),
            "qdot_norm_at_zero_transition": active_speed,
            "qdot_norm_after_zero_phase": final_speed,
        },
        "nonzero velocity before zero command and lower velocity after damping",
        bool(
            np.any(np.abs(active_command) > 0.0)
            and np.allclose(first_zero_command, np.zeros(2))
            and active_speed > 1e-9
            and final_speed < active_speed
        ),
        "reset saturated burst followed by repeated zero-command updates",
    )

    reset_shoulder = _require_field(
        experiment_index[("reset_singular", "saturated_shoulder_step")],
        "trace",
        "reset shoulder experiment",
    )
    reset_elbow = _require_field(
        experiment_index[("reset_singular", "saturated_elbow_step")],
        "trace",
        "reset elbow experiment",
    )
    reset_position = np.asarray(
        [UPPER_ARM_LENGTH + FOREARM_LENGTH, 0.0, 0.02], dtype=float
    )
    shoulder_position = _finite_vector(
        reset_shoulder[0]["end_effector_position"], 3, "reset shoulder position"
    )
    elbow_position = _finite_vector(
        reset_elbow[0]["end_effector_position"], 3, "reset elbow position"
    )
    tangential = abs(float(np.dot(shoulder_position[:2] - reset_position[:2], [0.0, 1.0])))
    radial_inward = max(
        0.0, -float(np.dot(elbow_position[:2] - reset_position[:2], [1.0, 0.0]))
    )
    radial_supported = radial_inward > 1e-12 and tangential > 1e-12
    radial_passed = radial_inward < tangential if radial_supported else True
    if not radial_supported:
        unchecked_scope.append(
            "Reset radial-versus-tangential comparison was not supported by "
            "nonzero first-step directional displacements."
        )
    _check_result(
        checks,
        "reset_radial_vs_tangential_response",
        {
            "first_step_radial_inward_displacement_m": radial_inward,
            "first_step_tangential_displacement_m": tangential,
            "comparison_supported": radial_supported,
        },
        "radial inward response is smaller than tangential response when both are nonzero",
        radial_passed,
        "independent planar displacement comparison at reset singular posture",
    )

    failures = [check["name"] for check in checks if check["status"] == "failed"]
    result = {
        "schema": "robot_learning.lab.verify_compiled_dynamics.v1",
        "artifact": str(artifact_path),
        "passed": not failures,
        "checks": checks,
        "checked_scope": [check["checked_scope"] for check in checks],
        "unchecked_scope": unchecked_scope,
    }
    output_path.write_text(
        json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise VerificationError(
            "compiled dynamics verification failed: " + ", ".join(failures)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a compiled dynamics characterization artifact."
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.artifact, args.output)


if __name__ == "__main__":
    main()
