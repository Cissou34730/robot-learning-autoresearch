"""Executable, defect-sensitive checks for dynamics characterization."""

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from robot_learning.lab.dynamics_characterization import (
    COAST_STEPS,
    PULSE_STEPS,
    REPEATABILITY_TOLERANCE,
    characterize,
    compile_production_model,
    compatibility,
    configure_zero_gravity,
)


def _write_json(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _independent_control_trace(
    model: mujoco.MjModel, joint_index: int, steps: int
) -> list[tuple[list[float], list[float], list[float]]]:
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    low, high = np.asarray(model.actuator_ctrlrange[joint_index], dtype=float)
    command = np.zeros(model.nu, dtype=float)
    command[joint_index] = high if high != 0.0 else low
    if command[joint_index] == 0.0:
        raise ValueError("controlled-input reference has no nonzero actuator command")
    result = []
    for _ in range(steps):
        data.ctrl[:] = command
        mujoco.mj_step(model, data)
        result.append(
            (
                np.asarray(data.qpos, dtype=float).tolist(),
                np.asarray(data.qvel, dtype=float).tolist(),
                np.asarray(data.actuator_force, dtype=float).tolist(),
            )
        )
    return result


def _behavioral_check() -> dict[str, Any]:
    model = compile_production_model()
    configure_zero_gravity(model)
    dimensions = {
        "njnt": int(model.njnt),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
    }
    dimensions_passed = (model.njnt, model.nq, model.nv, model.nu) == (2, 2, 2, 2)
    if not dimensions_passed:
        raise ValueError(f"compiled production model is not two-joint: {dimensions}")

    measurement = characterize()
    trials = measurement["trials"]
    observed_pairs = {(trial["joint_index"], trial["pulse_sign"]) for trial in trials}
    expected_pairs = {(joint, sign) for joint in range(2) for sign in (-1, 1)}
    trace_lengths = [len(trial["trace"]) for trial in trials]
    trace_fields = {
        "qpos_rad",
        "qvel_rad_per_s",
        "qacc_rad_per_s2",
        "qfrc_actuator_Nm",
        "actuator_force_native",
        "ctrl_native",
        "end_effector_position_m",
    }
    transitions_present = all(
        [sample["phase"] for sample in trial["trace"][:PULSE_STEPS]]
        == ["pulse"] * PULSE_STEPS
        and [sample["phase"] for sample in trial["trace"][PULSE_STEPS:]]
        == ["coast"] * COAST_STEPS
        for trial in trials
    )
    traces_have_fields = all(
        len(trial["trace"]) == PULSE_STEPS + COAST_STEPS
        and all(trace_fields <= sample.keys() for sample in trial["trace"])
        for trial in trials
    )
    pulse_coverage_passed = (
        observed_pairs == expected_pairs
        and all(length >= PULSE_STEPS + COAST_STEPS for length in trace_lengths)
        and transitions_present
        and traces_have_fields
    )

    responsive_trials = []
    for trial in trials:
        joint = trial["joint_index"]
        pulse_samples = [
            sample
            for sample in trial["trace"]
            if abs(sample["ctrl_native"][joint]) > 0.0
        ]
        peak_force = max(
            (abs(sample["actuator_force_native"][joint]) for sample in pulse_samples),
            default=0.0,
        )
        responsive_trials.append(
            {
                "joint_index": joint,
                "pulse_sign": trial["pulse_sign"],
                "nonzero_command_samples": len(pulse_samples),
                "peak_abs_actuator_force_native": peak_force,
                "responsive": peak_force > 1.0e-12,
            }
        )
    force_response_passed = bool(responsive_trials) and all(
        item["responsive"] for item in responsive_trials
    )

    first = _independent_control_trace(model, 0, 6)
    second = _independent_control_trace(model, 0, 6)
    independent_difference = max(
        float(
            np.max(
                np.abs(
                    np.asarray(first_step, dtype=float)
                    - np.asarray(second_step, dtype=float)
                )
            )
        )
        for first_step, second_step in zip(first, second)
    )
    independent_repeatability_passed = (
        len(first) == len(second)
        and independent_difference <= REPEATABILITY_TOLERANCE
    )
    repeatability = measurement["repeatability"]
    repeatability_passed = bool(
        repeatability["passed"]
        and repeatability["max_abs_trace_difference"] <= REPEATABILITY_TOLERANCE
        and independent_repeatability_passed
    )
    checks = {
        "compiled_dimensions": {
            "observed": dimensions,
            "expected": {"njnt": 2, "nq": 2, "nv": 2, "nu": 2},
            "passed": dimensions_passed,
        },
        "pulse_trace_coverage": {
            "observed": {
                "pairs": sorted(observed_pairs),
                "trace_lengths": trace_lengths,
                "required_trace_length": PULSE_STEPS + COAST_STEPS,
                "pulse_to_coast_transition_present": transitions_present,
                "required_fields_present": traces_have_fields,
            },
            "expected": {
                "pairs": sorted(expected_pairs),
                "both_signs_and_joints": True,
                "internal_samples_per_trial": PULSE_STEPS + COAST_STEPS,
            },
            "passed": pulse_coverage_passed,
        },
        "actuator_force_response": {
            "observed": responsive_trials,
            "expected": "every signed pulse has nonzero actuator force",
            "passed": force_response_passed,
        },
        "repeatability": {
            "observed": {
                "measurement_comparison": repeatability,
                "independent_reset_trace_max_abs_difference": independent_difference,
            },
            "expected": {
                "measurement_max_difference_at_most": REPEATABILITY_TOLERANCE,
                "independent_reset_trace_max_difference_at_most": REPEATABILITY_TOLERANCE,
            },
            "passed": repeatability_passed,
        },
    }
    if not all(check["passed"] for check in checks.values()):
        raise AssertionError("dynamics characterization verification failed")
    return {
        "schema_version": 1,
        "mode": "behavioral_check",
        "status": "passed",
        "checks": checks,
        "checked_scope": [
            "authored XML compilation and exact two-joint dimensions",
            "both signed pulses on both joints with post-step internal traces",
            "nonzero actuator-force response to nonzero controlled input",
            "repeated updates after reset and deterministic repeated traces",
        ],
        "unchecked_scope": [
            "physical validity of the authored XML parameters",
            "agreement with hardware measurements",
            "long-horizon dynamics beyond the bounded trial window",
            "scientific interpretation of braking or hold performance",
        ],
    }


def _compatibility_check() -> dict[str, Any]:
    observed = compatibility()
    if not observed["compiled"] or not observed["one_mj_step_completed"]:
        raise AssertionError("production compatibility path did not complete")
    return {
        "schema_version": 1,
        "mode": "compatibility_check",
        "status": "passed",
        "checked_scope": [
            "production XML compilation",
            "native MuJoCo MjData reset and one mj_step",
            "zero-gravity measurement configuration",
        ],
        "observed": observed,
        "expected": {
            "compiled": True,
            "one_mj_step_completed": True,
            "gravity_m_per_s2": [0.0, 0.0, -0.0],
        },
        "unchecked_scope": [
            "two-joint inventory and pulse/free-response trial coverage",
            "actuator authority and braking summaries",
            "repeatability over the full characterization trial set",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check", "compatibility"), default="check")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = (
            _behavioral_check()
            if args.mode == "check"
            else _compatibility_check()
        )
    except Exception as error:
        _write_json(
            args.output,
            {
                "schema_version": 1,
                "mode": f"{args.mode}_check",
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "unchecked_scope": [
                    "checks after the first failed production-path operation"
                ],
            },
        )
        raise
    _write_json(args.output, payload)


if __name__ == "__main__":
    main()
