"""Executable defect-sensitive checks for the physical characterization core.

Use ``--mode compatibility`` for a short artifact-independent native-stack
smoke of the production measurement path, or ``--mode behavioral`` for
deterministic reset, transition, and repeated-update checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from robot_learning.lab.physical_characterization import (
    CONFIGURATIONS,
    CONTROL_BLOCK_STEPS,
    load_model,
    reset_state,
    run_trace,
)


def _check(name: str, observed: Any, expected: Any, passed: bool) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "expected": expected,
        "passed": bool(passed),
    }


def compatibility_report() -> dict[str, Any]:
    """Exercise the changed native production path with only two short blocks."""

    model, data = load_model()
    reset_state(model, data, (0.0, 0.0))
    trace = run_trace(
        model,
        data,
        qpos=(0.0, 0.0),
        command=(0.25, -0.25),
        command_steps=CONTROL_BLOCK_STEPS,
        release_steps=CONTROL_BLOCK_STEPS,
    )
    initial = np.asarray(trace["substep_samples"][0]["qpos_rad"])
    final = np.asarray(trace["substep_samples"][-1]["qpos_rad"])
    checks = [
        _check(
            "native XML timestep",
            float(model.opt.timestep),
            0.002,
            bool(np.isclose(model.opt.timestep, 0.002)),
        ),
        _check(
            "two timescales present",
            (
                len(trace["substep_samples"]),
                len(trace["control_block_observations"]),
            ),
            (2 * CONTROL_BLOCK_STEPS + 1, 2),
            len(trace["control_block_observations"]) == 2,
        ),
        _check(
            "bounded production command changes state",
            final.tolist(),
            "different from initial qpos",
            bool(np.linalg.norm(final - initial) > 0.0),
        ),
    ]
    return {
        "mode": "compatibility",
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "checked_scope": [
            "native XML loading",
            "reset_state",
            "bounded command conversion and mj_step updates",
            "substep and 20 ms control-block observations",
        ],
        "unchecked_scope": [
            "full characterization duration and all configurations",
            "scientific interpretation of measured dynamics",
        ],
    }


def behavioral_report() -> dict[str, Any]:
    """Check known consequences that expose reset and transition defects."""

    model, data = load_model()
    checks: list[dict[str, Any]] = []

    # In this zero-gravity model, zero velocity plus zero command is a known
    # equilibrium.  A nonzero bounded command from the same state must depart.
    zero_trace = run_trace(
        model,
        data,
        qpos=(0.0, 0.0),
        command=(0.0, 0.0),
        command_steps=0,
        release_steps=2 * CONTROL_BLOCK_STEPS,
    )
    command_trace = run_trace(
        model,
        data,
        qpos=(0.0, 0.0),
        command=(0.5, 0.0),
        command_steps=CONTROL_BLOCK_STEPS,
        release_steps=CONTROL_BLOCK_STEPS,
    )
    zero_states = np.asarray(
        [x["qpos_rad"] + x["qvel_rad_s"] for x in zero_trace["substep_samples"]]
    )
    command_states = np.asarray(
        [x["qpos_rad"] + x["qvel_rad_s"] for x in command_trace["substep_samples"]]
    )
    checks.append(
        _check(
            "zero-command equilibrium",
            float(np.max(np.abs(zero_states))),
            "<= 1e-12",
            bool(np.max(np.abs(zero_states)) <= 1e-12),
        )
    )
    checks.append(
        _check(
            "bounded command has a known dynamic consequence",
            float(np.max(np.abs(command_states - command_states[0]))),
            "> 0",
            bool(np.max(np.abs(command_states - command_states[0])) > 0.0),
        )
    )

    # Repeat the same transition after independent resets.  Comparing every
    # substep catches state leakage, stale ctrl, and incomplete reset logic.
    repeated_a = run_trace(
        model,
        data,
        qpos=CONFIGURATIONS["open"],
        command=(0.3, -0.2),
        command_steps=2 * CONTROL_BLOCK_STEPS,
        release_steps=2 * CONTROL_BLOCK_STEPS,
    )
    repeated_b = run_trace(
        model,
        data,
        qpos=CONFIGURATIONS["open"],
        command=(0.3, -0.2),
        command_steps=2 * CONTROL_BLOCK_STEPS,
        release_steps=2 * CONTROL_BLOCK_STEPS,
    )
    states_a = np.asarray(
        [x["qpos_rad"] + x["qvel_rad_s"] for x in repeated_a["substep_samples"]]
    )
    states_b = np.asarray(
        [x["qpos_rad"] + x["qvel_rad_s"] for x in repeated_b["substep_samples"]]
    )
    repeat_difference = float(np.max(np.abs(states_a - states_b)))
    checks.append(
        _check(
            "repeated transition is identical after reset",
            repeat_difference,
            "<= 1e-12",
            repeat_difference <= 1e-12,
        )
    )

    # Visit all configurations in sequence and verify that each transition
    # starts from its requested q, rather than the previous configuration.
    transition_starts = []
    for name, qpos in CONFIGURATIONS.items():
        trace = run_trace(
            model,
            data,
            qpos=qpos,
            command=(0.0, 0.0),
            command_steps=0,
            release_steps=CONTROL_BLOCK_STEPS,
        )
        transition_starts.append(trace["substep_samples"][0]["qpos_rad"])
    expected_starts = [list(qpos) for qpos in CONFIGURATIONS.values()]
    transition_error = float(
        np.max(np.abs(np.asarray(transition_starts) - np.asarray(expected_starts)))
    )
    checks.append(
        _check(
            "configuration transitions reset to requested q",
            transition_starts,
            expected_starts,
            transition_error <= 1e-12,
        )
    )
    return {
        "mode": "behavioral",
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "checked_scope": [
            "repeated zero-command updates",
            "bounded versus zero-command consequence",
            "independent repeated trials",
            "transitions across extended, open, and folded configurations",
            "reset state and control clearing",
        ],
        "unchecked_scope": [
            "compiled inertial inventory completeness",
            "long-duration settling and free-decay summaries",
            "scientific validity of any physical conclusion",
        ],
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("compatibility", "behavioral"), default="behavioral")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = (
        compatibility_report()
        if args.mode == "compatibility"
        else behavioral_report()
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
