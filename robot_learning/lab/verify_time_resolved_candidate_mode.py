"""Defect-sensitive check for the time-resolved candidate outcome mode."""

from __future__ import annotations

import argparse
import ast
import inspect
import json
from pathlib import Path
from typing import Any

from robot_learning.lab import time_resolved_rollout_measurement as measurement


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FAILURE_SEEDS = [
    4201,
    4208,
    4225,
    4226,
    4228,
    4243,
    4244,
    4246,
    4307,
    4316,
]
EXPECTED_CONTROL_SEEDS = [
    4211,
    4214,
    4236,
    4264,
    4286,
    4297,
    4337,
    4347,
    4349,
    4355,
]
EXPECTED_ENVIRONMENT_FIELDS = [
    "endpoint_position_m",
    "endpoint_velocity_m_s",
    "distance_m",
    "distance_cm",
    "in_tolerance",
    "previous_held_steps",
    "held_steps",
    "hold_counter_transition",
    "interruption",
    "cumulative_interruptions",
]
EXPECTED_REFERENCE_FIELDS = [
    "endpoint_position_m",
    "endpoint_velocity_m_s",
    "position_error_m",
    "velocity_error_m_s",
]
EXPECTED_ENVIRONMENT_ROLE = (
    "Endpoint, distance, and hold fields are sampled from the live "
    "environment after env.step and retain task semantics."
)
EXPECTED_REFERENCE_SOURCE = (
    "Separate MuJoCo replay loaded from qpos_after_rad and "
    "qvel_after_rad_s, followed by mj_forward and mj_jacSite."
)
EXPECTED_REFERENCE_ROLE = (
    "Forward-consistent reference only; it does not replace "
    "environment-observed endpoint, distance, or hold fields."
)


class VerificationError(ValueError):
    """A candidate-mode regression check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _expect_value_error(callable_: Any, message: str) -> str:
    try:
        callable_()
    except ValueError as exc:
        return str(exc)
    raise VerificationError(message)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise VerificationError(f"source has no {name} function")


def _calls(function: ast.FunctionDef, name: str) -> list[ast.Call]:
    found = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == name:
            found.append(node)
    return found


def _attribute_calls(
    function: ast.FunctionDef, receiver: str, attribute: str
) -> list[ast.Call]:
    found = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if (
            node.func.attr == attribute
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == receiver
        ):
            found.append(node)
    return found


def _name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _dict_literal(tree: ast.Module, key: str) -> Any:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            if isinstance(key_node, ast.Constant) and key_node.value == key:
                try:
                    return ast.literal_eval(value_node)
                except (TypeError, ValueError, SyntaxError):
                    continue
    raise VerificationError(f"source has no literal metadata key {key!r}")


def _source_contract_checks() -> dict[str, Any]:
    source = inspect.getsource(measurement)
    tree = ast.parse(source)
    rollout = _function(tree, "_rollout")
    run = _function(tree, "run_measurement")
    write = _function(tree, "write_measurement")
    main = _function(tree, "main")

    rollout_calls = _calls(rollout, "_validate_rollout_outcome")
    _require(len(rollout_calls) == 1, "rollout does not validate its observed outcome")
    _require(
        _name(rollout_calls[0].args[-1]) == "allow_unexpected_outcomes",
        "rollout does not pass the opt-out mode to outcome validation",
    )

    run_rollout_calls = _calls(run, "_rollout")
    _require(len(run_rollout_calls) == 1, "run_measurement does not call rollout once")
    _require(
        len(run_rollout_calls[0].args) == 7
        and _name(run_rollout_calls[0].args[-1]) == "allow_unexpected_outcomes",
        "run_measurement does not propagate the opt-out mode to every rollout",
    )

    write_run_calls = _calls(write, "run_measurement")
    _require(len(write_run_calls) == 1, "write_measurement does not call run_measurement once")
    _require(
        len(write_run_calls[0].args) == 5
        and _name(write_run_calls[0].args[-1]) == "allow_unexpected_outcomes",
        "write_measurement does not propagate the opt-out mode",
    )

    main_write_calls = _calls(main, "write_measurement")
    _require(len(main_write_calls) == 1, "CLI main does not call write_measurement once")
    _require(
        len(main_write_calls[0].args) == 6
        and isinstance(main_write_calls[0].args[-1], ast.Attribute)
        and isinstance(main_write_calls[0].args[-1].value, ast.Name)
        and main_write_calls[0].args[-1].value.id == "args"
        and main_write_calls[0].args[-1].attr == "allow_unexpected_outcomes",
        "CLI main does not propagate the opt-out flag",
    )
    reset_calls = _attribute_calls(rollout, "env", "reset")
    runtime_reset_calls = _attribute_calls(rollout, "runtime", "reset")
    step_calls = _attribute_calls(rollout, "env", "step")
    _require(len(reset_calls) == 1, "rollout reset call is missing")
    _require(
        len(reset_calls[0].keywords) == 1
        and reset_calls[0].keywords[0].arg == "seed"
        and _name(reset_calls[0].keywords[0].value) == "seed",
        "rollout reset does not use the requested seed",
    )
    _require(len(runtime_reset_calls) == 1, "runtime reset call is missing")
    _require(len(step_calls) == 1, "repeated environment update call is missing")
    _require(
        any(
            isinstance(node, ast.For)
            and any(
                candidate in step_calls
                for candidate in ast.walk(node)
                if isinstance(candidate, ast.Call)
            )
            for node in ast.walk(rollout)
        ),
        "environment update is not inside the repeated control-step loop",
    )
    rollout_source = ast.get_source_segment(source, rollout) or ""
    for marker in (
        "expected_held_steps",
        "hold_counter_transition",
        "interruption",
        "contact",
        "kinematic_reference",
        "if terminated or truncated",
    ):
        _require(
            marker in rollout_source,
            f"rollout semantic check or field {marker!r} is missing",
        )

    _require(
        "--allow-unexpected-outcomes" in source,
        "CLI has no explicit unexpected-outcome opt-out flag",
    )
    _require(
        '"success": success' in source,
        "rollout does not record the validated actual success outcome",
    )
    _require(
        '"expected_success": expected_success' in source,
        "historical role expectation metadata is missing",
    )
    run_signature = inspect.signature(measurement.run_measurement)
    write_signature = inspect.signature(measurement.write_measurement)
    _require(
        run_signature.parameters["allow_unexpected_outcomes"].default is False,
        "run_measurement is not strict by default",
    )
    _require(
        write_signature.parameters["allow_unexpected_outcomes"].default is False,
        "write_measurement is not strict by default",
    )

    environment_fields = _dict_literal(tree, "environment_observed_fields")
    reference_fields = _dict_literal(tree, "fields")
    environment_role = _dict_literal(tree, "environment_observed_role")
    reference_source = _dict_literal(tree, "source")
    reference_role = _dict_literal(tree, "role")
    _require(
        environment_fields == EXPECTED_ENVIRONMENT_FIELDS,
        "live environment-observed field definition changed",
    )
    _require(
        reference_fields == EXPECTED_REFERENCE_FIELDS,
        "forward-reference field definition changed",
    )
    _require(
        environment_role == EXPECTED_ENVIRONMENT_ROLE,
        "live environment-observed role definition changed",
    )
    _require(
        reference_source == EXPECTED_REFERENCE_SOURCE,
        "forward-reference source definition changed",
    )
    _require(
        reference_role == EXPECTED_REFERENCE_ROLE,
        "forward-reference role definition changed",
    )
    return {
        "run_measurement_default_strict": run_signature.parameters[
            "allow_unexpected_outcomes"
        ].default
        is False,
        "write_measurement_default_strict": write_signature.parameters[
            "allow_unexpected_outcomes"
        ].default
        is False,
        "live_environment_fields": environment_fields,
        "forward_reference_fields": reference_fields,
        "reset_and_repeated_update_source_contract": True,
        "hold_transition_contact_and_termination_source_contract": True,
    }


def _outcome_mode_checks() -> dict[str, Any]:
    controlled_seed = 9999
    strict_rejected = False
    try:
        measurement._validate_rollout_outcome(
            controlled_seed,
            "failure",
            True,
            False,
        )
    except RuntimeError:
        strict_rejected = True
    _require(
        strict_rejected,
        "strict mode accepted an unexpected success for a failure role",
    )

    recorded_success = measurement._validate_rollout_outcome(
        controlled_seed,
        "failure",
        True,
        True,
    )
    _require(
        recorded_success is True,
        "opt-out mode did not preserve the controlled actual success outcome",
    )

    control_failure_rejected = False
    try:
        measurement._validate_rollout_outcome(
            controlled_seed,
            "control",
            False,
            False,
        )
    except RuntimeError:
        control_failure_rejected = True
    _require(
        control_failure_rejected,
        "strict mode accepted an unexpected failure for a control role",
    )

    return {
        "controlled_seed": controlled_seed,
        "historical_role": "failure",
        "controlled_actual_success": True,
        "strict_rejected_unexpected_success": strict_rejected,
        "opt_out_recorded_actual_success": recorded_success,
        "strict_rejected_unexpected_control_failure": control_failure_rejected,
        "expected": {
            "strict_rejected_unexpected_success": True,
            "opt_out_recorded_actual_success": True,
            "strict_rejected_unexpected_control_failure": True,
        },
    }


def _seed_and_horizon_checks() -> dict[str, Any]:
    failure_seeds = list(measurement.EXPECTED_FAILURE_SEEDS)
    control_seeds = list(measurement.EXPECTED_CONTROL_SEEDS)
    _require(failure_seeds == EXPECTED_FAILURE_SEEDS, "failure seed panel changed")
    _require(control_seeds == EXPECTED_CONTROL_SEEDS, "control seed panel changed")
    _require(
        measurement.MAX_EPISODE_STEPS == 500,
        "measurement horizon is not the required 500 control steps",
    )

    placeholder = Path("__candidate_mode_missing_model__")
    altered_failure = failure_seeds.copy()
    altered_failure[0] += 1
    altered_control = control_seeds.copy()
    altered_control[-1] += 1
    checks = {
        "altered_failure_seed_list": _expect_value_error(
            lambda: measurement.run_measurement(
                placeholder, altered_failure, control_seeds, 500
            ),
            "altered failure seeds were not rejected before model loading",
        ),
        "altered_control_seed_list": _expect_value_error(
            lambda: measurement.run_measurement(
                placeholder, failure_seeds, altered_control, 500
            ),
            "altered control seeds were not rejected before model loading",
        ),
        "altered_horizon": _expect_value_error(
            lambda: measurement.run_measurement(
                placeholder, failure_seeds, control_seeds, 499
            ),
            "altered horizon was not rejected before model loading",
        ),
    }
    return {
        "failure_seeds": failure_seeds,
        "control_seeds": control_seeds,
        "horizon": measurement.MAX_EPISODE_STEPS,
        "invalid_input_rejections": checks,
    }


def verify_candidate_mode() -> dict[str, Any]:
    return {
        "outcome_mode": _outcome_mode_checks(),
        "strict_seed_and_horizon_requirements": _seed_and_horizon_checks(),
        "source_contract": _source_contract_checks(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Check strict and candidate modes of the time-resolved measurement."
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else REPOSITORY_ROOT / args.output
    try:
        observed = verify_candidate_mode()
        result = {
            "schema_version": 1,
            "passed": True,
            "observed_vs_expected": observed,
            "checked_scope": [
                "strict rejection of both unexpected role outcomes",
                "opt-out recording of a controlled unexpected success without relabeling it",
                "strict defaults and propagation through the callable and CLI layers",
                "exact ten failure seeds, exact ten control seeds, and 500-step horizon",
                "live environment-observed and forward-reference field definitions and roles",
            ],
            "unchecked_scope": [
                "actual policy rollouts and their scientific outcomes",
                "MuJoCo transitions, resets, contacts, hold semantics, and discrepancy magnitudes",
                "scientific validity of interpreting a candidate outcome",
            ],
        }
        exit_code = 0
    except (
        VerificationError,
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OSError,
        RuntimeError,
        SyntaxError,
        json.JSONDecodeError,
    ) as exc:
        result = {
            "schema_version": 1,
            "passed": False,
            "error": str(exc),
            "observed_vs_expected": {},
            "checked_scope": [],
            "unchecked_scope": [
                "The candidate-mode check was not fully completed after this defect."
            ],
        }
        exit_code = 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
