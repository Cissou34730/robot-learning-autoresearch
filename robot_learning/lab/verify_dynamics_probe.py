"""Defect-sensitive executable checks for :mod:`dynamics_probe`.

The checks use the compiled model and repeated controlled transitions.  They
test measurement integrity and a few independently expected consequences;
they do not certify physical-model validity or policy performance.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.lab.dynamics_probe import (
    DEFAULT_DECAY_SUBSTEPS,
    DEFAULT_PULSE_CONTROL,
    DEFAULT_SEED,
    DEFAULT_SUBSTEPS,
    collect_probe,
)


def _finite(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite(child) for child in value)
    return True


def _result(
    name: str, observed: Any, expected: Any, passed: bool, scope: str
) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "expected": expected,
        "passed": bool(passed),
        "checked_scope": scope,
    }


def _configurations(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in artifact["configurations"]}


def _trajectory_checks(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    reset_states: list[dict[str, Any]] = []
    configured_qpos_ok = True
    for configuration in artifact["configurations"]:
        for trajectory_name, trajectory in configuration["probes"].items():
            reset_states.append(trajectory["initial_state"])
            configured_qpos_ok = configured_qpos_ok and np.allclose(
                trajectory["initial_state"]["qpos_rad"], configuration["qpos_rad"]
            )
            declared = int(trajectory["declared_substeps"])
            samples = trajectory["samples"]
            checks.append(
                _result(
                    f"{configuration['name']}.{trajectory_name}.substep_count",
                    len(samples),
                    declared,
                    len(samples) == declared,
                    "every recorded trajectory retains exactly its declared post-step samples",
                )
            )
            finite = all(
                _finite(sample["qpos_rad"])
                and _finite(sample["qvel_rad_s"])
                and _finite(sample["qacc_rad_s2"])
                for sample in samples
            )
            checks.append(
                _result(
                    f"{configuration['name']}.{trajectory_name}.finite_state",
                    finite,
                    True,
                    finite,
                    "qpos, qvel, and qacc at every physics substep",
                )
            )
            has_transition = bool(samples) and float(
                np.max(
                    np.abs(
                        np.asarray(samples[-1]["qpos_rad"], dtype=np.float64)
                        - np.asarray(trajectory["initial_state"]["qpos_rad"], dtype=np.float64)
                    )
                )
            ) > 1.0e-12
            checks.append(
                _result(
                    f"{configuration['name']}.{trajectory_name}.transition",
                    has_transition,
                    True,
                    has_transition,
                    "nonzero controlled probes must actually advance the repeated state transition",
                )
            )

    reset_values = all(np.allclose(state["qvel_rad_s"], 0.0) for state in reset_states)
    checks.append(
        _result(
            "independent_resets",
            {
                "recorded_resets": len(reset_states),
                "declared_resets": artifact["metadata"]["independent_reset_count"],
                "all_qvel_zero": reset_values,
                "all_qpos_match_configuration": configured_qpos_ok,
            },
            {
                "recorded_equals_declared": True,
                "all_qvel_zero": True,
                "all_qpos_match_configuration": True,
            },
            len(reset_states) == artifact["metadata"]["independent_reset_count"]
            and reset_values
            and configured_qpos_ok,
            "repeated independent reset before every trajectory",
        )
    )
    return checks


def _expected_consequence_checks(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    configurations = _configurations(artifact)
    reset = configurations["reset_fully_extended"]
    reset_radii = [
        float(trajectory["initial_state"]["end_effector_radius_m"])
        for trajectory in reset["probes"].values()
    ]
    reset_states = [trajectory["initial_state"] for trajectory in reset["probes"].values()]
    reset_radius_ok = all(math.isclose(radius, 0.22, abs_tol=1.0e-6) for radius in reset_radii)
    reset_state_ok = all(
        np.allclose(state["qpos_rad"], 0.0) and np.allclose(state["qvel_rad_s"], 0.0)
        for state in reset_states
    )
    checks.append(
        _result(
            "reset_geometry",
            {"radii_m": reset_radii, "zero_qpos_qvel": reset_state_ok},
            {"qpos_rad": 0.0, "qvel_rad_s": 0.0, "radius_m": 0.22},
            reset_radius_ok and reset_state_ok,
            "reset posture kinematics and repeated reset state",
        )
    )

    orthogonal = configurations["orthogonal_elbow"]["probes"]
    acceleration_observations: dict[str, dict[str, float]] = {}
    signs_ok = True
    for joint_id in (0, 1):
        positive = float(orthogonal[f"joint_{joint_id}_positive"]["samples"][0]["qacc_rad_s2"][joint_id])
        negative = float(orthogonal[f"joint_{joint_id}_negative"]["samples"][0]["qacc_rad_s2"][joint_id])
        acceleration_observations[f"joint_{joint_id}"] = {
            "positive_first_qacc": positive,
            "negative_first_qacc": negative,
        }
        signs_ok = signs_ok and positive > 0.0 and negative < 0.0
    checks.append(
        _result(
            "opposite_first_acceleration_signs",
            acceleration_observations,
            {"positive_qacc": "> 0", "negative_qacc": "< 0"},
            signs_ok,
            "orthogonal non-singular configuration, each actuator independently pulsed",
        )
    )

    reversal_observations: dict[str, dict[str, bool]] = {}
    reversal_ok = True
    for joint_id in (0, 1):
        samples = orthogonal[f"joint_{joint_id}_reversal"]["samples"]
        values = [float(sample["applied_ctrl"][joint_id]) for sample in samples]
        has_positive = any(value > 0.0 for value in values)
        has_negative = any(value < 0.0 for value in values)
        reversal_observations[f"joint_{joint_id}"] = {
            "has_positive_action": has_positive,
            "has_negative_action": has_negative,
        }
        reversal_ok = reversal_ok and has_positive and has_negative
    checks.append(
        _result(
            "reversal_contains_both_signs",
            reversal_observations,
            {"each_joint": ["positive", "negative"]},
            reversal_ok,
            "recorded applied controls in both phases of each reversal trajectory",
        )
    )
    return checks


def verify(
    *,
    substeps: int = DEFAULT_SUBSTEPS,
    decay_substeps: int = DEFAULT_DECAY_SUBSTEPS,
    pulse_control: float = DEFAULT_PULSE_CONTROL,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    artifact = collect_probe(
        substeps=substeps,
        decay_substeps=decay_substeps,
        pulse_control=pulse_control,
        seed=seed,
    )
    model = artifact["compiled_model"]
    checks = [
        _result(
            "compiled_model_dimensions",
            {"nq": model["nq"], "nv": model["nv"], "nu": model["nu"]},
            {"nq": 2, "nv": 2, "nu": 2},
            (model["nq"], model["nv"], model["nu"]) == (2, 2, 2),
            "compiled authoritative model dimensions",
        ),
        _result(
            "compiled_timestep",
            model["timestep_s"],
            0.002,
            math.isclose(float(model["timestep_s"]), 0.002, abs_tol=1.0e-12),
            "compiled MuJoCo physics timestep",
        ),
    ]
    checks.extend(_trajectory_checks(artifact))
    checks.extend(_expected_consequence_checks(artifact))
    passed = all(item["passed"] for item in checks)
    return {
        "schema_version": 1,
        "verification": "two_joint_arm_dynamics_probe",
        "execution_note": "Executable integrity proposal; passing checks do not certify scientific validity.",
        "settings": artifact["metadata"]["settings"],
        "checks": checks,
        "all_checks_passed": passed,
        "checked_scope": [
            "compiled dimensions and timestep",
            "repeated independent zero-velocity resets",
            "finite per-substep qpos, qvel, and qacc",
            "nonzero controlled transitions",
            "opposite first acceleration signs at the orthogonal configuration",
            "reversal actions containing both signs",
            "reset radius near 0.22 m",
        ],
        "unchecked_scope": [
            "scientific sufficiency of the authored dynamics model",
            "policy learning or official task success",
            "long-horizon stabilization beyond the short probes",
            "statistical uncertainty and target-distribution performance",
            "interpretation of solver or joint-limit behavior beyond recorded indicators",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="JSON verification artifact path")
    parser.add_argument("--substeps", type=int, default=DEFAULT_SUBSTEPS)
    parser.add_argument("--decay-substeps", type=int, default=DEFAULT_DECAY_SUBSTEPS)
    parser.add_argument("--pulse-control", type=float, default=DEFAULT_PULSE_CONTROL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    result = verify(
        substeps=args.substeps,
        decay_substeps=args.decay_substeps,
        pulse_control=args.pulse_control,
        seed=args.seed,
    )
    path = Path(args.output)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if not result["all_checks_passed"]:
        raise AssertionError("dynamics probe verification failed; inspect the JSON artifact")


if __name__ == "__main__":
    main()
