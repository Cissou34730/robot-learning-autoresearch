"""Defect-sensitive checks for the compiled dynamics laboratory measurement.

The check runs the measurement mode, then compares its traces with independent
compiled-model facts and controlled-input consequences. It writes a review
artifact before raising for any failed check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from robot_learning.lab.compiled_dynamics_measurement import (
    FRAME_SKIP,
    run_measurement,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_SCHEMA_VERSION = 1
EXPECTED_TIMESTEP_S = 0.002
EXPECTED_CONTROL_INTERVAL_S = 0.020


def _sequence(artifact: dict[str, Any], label: str) -> dict[str, Any]:
    for sequence in artifact["sequences"]:
        if sequence["label"] == label:
            return sequence
    raise ValueError(f"measurement artifact has no {label!r} sequence")


def _check(
    checks: list[dict[str, Any]],
    name: str,
    observed: Any,
    expected: Any,
    passed: bool,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
        }
    )


def _independent_hold_probe(model: mujoco.MjModel) -> dict[str, Any]:
    """Check command persistence directly at every integration substep."""
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    data.qpos[:] = [0.30, -0.45]
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    command = np.array([0.40, 0.0], dtype=np.float64)
    substep_commands: list[list[float]] = []
    interval_positions: list[list[float]] = []
    for _ in range(3):
        data.ctrl[:] = command
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
            substep_commands.append([float(value) for value in data.ctrl])
        interval_positions.append([float(value) for value in data.qpos])
    command_is_held = all(
        np.array_equal(np.asarray(values), command) for values in substep_commands
    )
    state_evolved = any(
        not np.array_equal(np.asarray(position), [0.30, -0.45])
        for position in interval_positions
    )
    return {
        "substep_commands": substep_commands,
        "interval_positions": interval_positions,
        "command_is_held": command_is_held,
        "state_evolved": state_evolved,
    }


def _independent_signed_probe(model: mujoco.MjModel) -> dict[str, float]:
    """Measure the first shoulder response for opposite isolated commands."""
    responses: dict[str, float] = {}
    for label, command in (
        ("positive", [0.75, 0.0]),
        ("negative", [-0.75, 0.0]),
    ):
        data = mujoco.MjData(model)
        mujoco.mj_resetData(model, data)
        data.qpos[:] = [0.30, -0.45]
        data.qvel[:] = 0.0
        mujoco.mj_forward(model, data)
        data.ctrl[:] = command
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        responses[label] = float(data.qvel[0])
    return responses


def verify_measurement() -> dict[str, Any]:
    artifact = run_measurement()
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    checks: list[dict[str, Any]] = []

    compiled = artifact["model"]
    option = compiled["compiled_option"]
    _check(
        checks, "compiled timestep", option["timestep_s"], EXPECTED_TIMESTEP_S,
        option["timestep_s"] == EXPECTED_TIMESTEP_S
    )
    _check(
        checks, "ten integration substeps", compiled["frame_skip"], FRAME_SKIP,
        compiled["frame_skip"] == FRAME_SKIP
    )
    _check(
        checks, "twenty millisecond control interval",
        compiled["control_interval_s"], EXPECTED_CONTROL_INTERVAL_S,
        compiled["control_interval_s"] == EXPECTED_CONTROL_INTERVAL_S
    )

    model_gear = np.asarray(model.actuator_gear[:, 0], dtype=np.float64)
    model_ctrlrange = np.asarray(model.actuator_ctrlrange, dtype=np.float64)
    artifact_gear = np.asarray(
        [actuator["gear"][0] for actuator in compiled["actuators"]], dtype=np.float64
    )
    artifact_ctrlrange = np.asarray(
        [actuator["control_range"] for actuator in compiled["actuators"]],
        dtype=np.float64,
    )
    _check(
        checks, "exact compiled motor gear", artifact_gear.tolist(), [5.0, 5.0],
        np.array_equal(model_gear, [5.0, 5.0])
        and np.array_equal(artifact_gear, model_gear)
    )
    _check(
        checks, "exact compiled motor control ranges",
        artifact_ctrlrange.tolist(), [[-1.0, 1.0], [-1.0, 1.0]],
        np.array_equal(model_ctrlrange, [[-1.0, 1.0], [-1.0, 1.0]])
        and np.array_equal(artifact_ctrlrange, model_ctrlrange)
    )

    resets = _sequence(artifact, "repeated_reset")
    reset_positions = [record["qpos_rad"] for record in resets["trace"]]
    reset_velocities = [record["qvel_rad_s"] for record in resets["trace"]]
    reset_deterministic = (
        len(reset_positions) == 3
        and all(np.array_equal(position, [0.0, 0.0]) for position in reset_positions)
        and all(np.array_equal(velocity, [0.0, 0.0]) for velocity in reset_velocities)
        and all(position == reset_positions[0] for position in reset_positions)
        and all(velocity == reset_velocities[0] for velocity in reset_velocities)
    )
    _check(
        checks, "deterministic repeated zero reset",
        {"qpos": reset_positions, "qvel": reset_velocities},
        {"repeats": 3, "qpos": [0.0, 0.0], "qvel": [0.0, 0.0]},
        reset_deterministic
    )

    positive = _sequence(artifact, "isolated_positive_torque_step")
    negative = _sequence(artifact, "isolated_negative_torque_step")
    positive_response = float(positive["trace"][1]["qvel_rad_s"][0])
    negative_response = float(negative["trace"][1]["qvel_rad_s"][0])
    independent_response = _independent_signed_probe(model)
    opposite_response = (
        positive_response > 0.0
        and negative_response < 0.0
        and positive_response * negative_response < 0.0
        and independent_response["positive"] > 0.0
        and independent_response["negative"] < 0.0
    )
    _check(
        checks, "opposite signed isolated shoulder response",
        {
            "artifact_positive_qvel_rad_s": positive_response,
            "artifact_negative_qvel_rad_s": negative_response,
            "independent_positive_qvel_rad_s": independent_response["positive"],
            "independent_negative_qvel_rad_s": independent_response["negative"],
        },
        {"positive_sign": "+", "negative_sign": "-"},
        opposite_response
    )

    held_commands = [record["input_command"] for record in positive["trace"][1:]]
    hold_probe = _independent_hold_probe(model)
    _check(
        checks, "zero-order-held repeated updates",
        {
            "artifact_commands": held_commands,
            "independent_substep_commands": hold_probe["substep_commands"],
            "independent_state_evolved": hold_probe["state_evolved"],
        },
        {
            "artifact_repeated_command": [0.75, 0.0],
            "substeps_per_update": FRAME_SKIP,
            "state_evolution": True,
        },
        (
            len(held_commands) == 4
            and all(command == [0.75, 0.0] for command in held_commands)
            and hold_probe["command_is_held"]
            and hold_probe["state_evolved"]
        )
    )

    reversal = _sequence(artifact, "torque_reversal")
    reversal_commands = [
        record["input_command"] for record in reversal["trace"][1:]
    ]
    transition_indices = [
        index
        for index, (previous, current) in enumerate(
            zip(reversal_commands, reversal_commands[1:]), start=1
        )
        if previous[0] > 0.0 and current[0] < 0.0
    ]
    _check(
        checks, "actual positive to negative reversal transition",
        {"commands": reversal_commands, "transition_indices": transition_indices},
        {"contains_transition": True},
        bool(transition_indices)
    )

    free_decay = _sequence(artifact, "free_decay")
    free_trace = free_decay["trace"]
    free_controls_zero = all(
        record["input_command"] == [0.0, 0.0] for record in free_trace[1:]
    )
    free_non_singular = abs(np.sin(free_decay["initial_qpos_rad"][1])) > 1e-12
    free_initially_noncontact = free_trace[0]["contact_count"] == 0
    free_state_evolved = any(
        free_trace[index]["qpos_rad"] != free_trace[0]["qpos_rad"]
        or free_trace[index]["qvel_rad_s"] != free_trace[0]["qvel_rad_s"]
        for index in range(1, len(free_trace))
    )
    _check(
        checks, "nonempty zero-input free decay evolution",
        {
            "samples": len(free_trace),
            "controls_zero": free_controls_zero,
            "non_singular_initial_state": free_non_singular,
            "initial_contact_count": free_trace[0]["contact_count"],
            "state_evolved": free_state_evolved,
            "initial_qvel_rad_s": free_trace[0]["qvel_rad_s"],
        },
        {
            "minimum_samples": 2,
            "non_singular_initial_state": True,
            "initial_contact_count": 0,
            "controls_zero": True,
            "state_evolved": True,
        },
        len(free_trace) >= 2
        and free_non_singular
        and free_initially_noncontact
        and free_controls_zero
        and free_state_evolved
    )

    required_fields = {
        "qpos_rad", "qvel_rad_s", "qacc_rad_s2", "actuator_force",
        "qfrc_actuator_Nm", "end_effector_position_m", "contact_count",
    }
    all_trace_fields_present = all(
        required_fields.issubset(record)
        for sequence in artifact["sequences"]
        for record in sequence["trace"]
    )
    _check(
        checks, "bounded trace state and contact recording",
        sorted(required_fields), sorted(required_fields), all_trace_fields_present
    )

    failures = [check["name"] for check in checks if not check["passed"]]
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "verification": "compiled_dynamics_measurement",
        "executed": True,
        "checks": checks,
        "checked_scope": [
            "compiled timestep and control interval",
            "compiled motor gear and control ranges",
            "repeated zero reset",
            "opposite signed isolated response",
            "zero-order-held updates",
            "positive-to-negative reversal",
            "zero-input free decay",
            "required trace fields and contact counts",
        ],
        "unchecked_scope": [
            "scientific adequacy of the measured dynamics for policy learning",
            "long-horizon task success and 1 cm hold behavior",
            "contact behavior outside the fixed measured states",
            "agreement with hardware or any model other than this compiled MuJoCo plant",
        ],
        "failed_checks": failures,
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Verify the compiled dynamics measurement."
    )
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)
    result = verify_measurement()
    resolved_artifact_path = (
        args.artifact
        if args.artifact.is_absolute()
        else REPOSITORY_ROOT / args.artifact
    ).resolve()
    resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_artifact_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if result["failed_checks"]:
        raise RuntimeError(
            "compiled dynamics verification failed: "
            + ", ".join(result["failed_checks"])
        )


if __name__ == "__main__":
    main()
