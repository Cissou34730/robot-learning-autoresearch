"""Small Runner check for the dynamics measurement instrument."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Sequence

from contracts.task_spec import FRAME_SKIP
from robot_learning.lab import measure_dynamics


REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "measurement_note",
    "units",
    "model",
    "joints",
    "actuators",
    "probe_parameters",
    "configurations",
    "raw_probe_records",
    "summaries",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _assert_finite(value: Any, path: str = "value") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        _assert(math.isfinite(float(value)), f"{path} is not finite")


def _check_artifact(measurement: dict[str, Any]) -> dict[str, Any]:
    _assert(
        REQUIRED_TOP_LEVEL_FIELDS <= set(measurement),
        "measurement is missing required top-level fields",
    )
    model = measurement["model"]
    _assert(
        math.isclose(model["timestep_seconds"], 0.002, rel_tol=0.0, abs_tol=1e-12),
        "compiled timestep is not the official 0.002 seconds",
    )
    _assert(model["frame_skip"] == FRAME_SKIP, "official frame skip is missing")
    _assert(
        math.isclose(
            model["control_interval_seconds"],
            0.002 * FRAME_SKIP,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "control interval is not the official frame-held interval",
    )

    units = measurement["units"]
    _assert(
        units["actuator_force"]["unit"] == "N*m"
        and units["actuator_force"]["space"] == "actuator",
        "actuator-space force units are missing or ambiguous",
    )
    _assert(
        units["generalized_actuator_force"]["unit"] == "N*m"
        and units["generalized_actuator_force"]["space"] == "joint",
        "joint-space generalized force units are missing or ambiguous",
    )
    _assert(
        units["joint_dynamics"]
        == {
            "dof_damping": "N*m*s/rad",
            "dof_armature": "kg*m^2",
            "dof_frictionloss": "N*m",
        },
        "joint dynamics unit metadata is incomplete",
    )
    for joint in measurement["joints"]:
        _assert(
            joint["field_units"] == units["joint_dynamics"],
            f"joint dynamics units are missing for {joint['name']}",
        )

    actuators = measurement["actuators"]
    _assert(len(actuators) == 2, "both official actuators must be described")
    for actuator_id in range(2):
        for direction, sign in (
            ("small_positive", 1),
            ("small_negative", -1),
            ("saturated_positive", 1),
            ("saturated_negative", -1),
        ):
            expected_name = f"{direction}_joint_{actuator_id}"
            matching = [
                record
                for record in measurement["raw_probe_records"]
                if record["probe_name"] == expected_name
            ]
            _assert(matching, f"{expected_name} probe is missing")
            command_value = matching[0]["command"][actuator_id]
            _assert(
                command_value * sign > 0.0,
                f"{expected_name} does not command the expected direction",
            )

    _assert(
        measurement["probe_parameters"]["substeps_per_control_interval"]
        == FRAME_SKIP,
        "probe substep count does not use the official frame skip",
    )
    _assert(
        measurement["raw_probe_records"], "raw probe records are empty"
    )
    for record in measurement["raw_probe_records"]:
        samples = record["samples"]
        _assert(samples, f"probe {record['probe_name']} has no substep records")
        _assert(
            {sample["substep"] for sample in samples} <= set(range(1, FRAME_SKIP + 1)),
            f"probe {record['probe_name']} has invalid substep numbers",
        )
        samples_by_interval: dict[int, set[int]] = {}
        for sample in samples:
            samples_by_interval.setdefault(sample["control_interval"], set()).add(
                sample["substep"]
            )
        _assert(
            all(
                substeps == set(range(1, FRAME_SKIP + 1))
                for substeps in samples_by_interval.values()
            ),
            f"probe {record['probe_name']} does not retain every physics substep",
        )
        for sample in samples:
            _assert(
                sample["force_units"]["actuator_force"]
                == units["actuator_force"]
                and sample["force_units"]["generalized_actuator_force"]
                == units["generalized_actuator_force"],
                f"force units are missing for probe {record['probe_name']}",
            )
            _assert(
                len(sample["qpos_radians"]) == 2
                and len(sample["qvel_radians_per_second"]) == 2
                and len(sample["qacc_radians_per_second2"]) == 2,
                f"probe {record['probe_name']} has an invalid state shape",
            )
    _assert_finite(measurement)
    return {
        "status": "passed",
        "production_cli": True,
        "top_level_fields_checked": sorted(REQUIRED_TOP_LEVEL_FIELDS),
        "probe_records_checked": len(measurement["raw_probe_records"]),
        "substep_state_values_checked": sum(
            len(record["samples"]) for record in measurement["raw_probe_records"]
        ),
    }


def run_artifact_check() -> dict[str, Any]:
    """Exercise the production CLI using a temporary measurement artifact."""

    with tempfile.TemporaryDirectory(prefix="verify-dynamics-") as directory:
        temporary_output = Path(directory) / "measurement.json"
        measure_dynamics.main(
            [
                "--output",
                str(temporary_output),
                "--intervals",
                "1",
                "--decay-intervals",
                "2",
                "--configurations",
                "3",
            ]
        )
        with temporary_output.open("r", encoding="utf-8") as handle:
            measurement = json.load(handle)
    return _check_artifact(measurement)


def run_compatibility_check() -> dict[str, Any]:
    """Check the production collection path without reading a JSON artifact."""

    measurement = measure_dynamics.collect_measurement(
        intervals=1, decay_intervals=1, configuration_count=1
    )
    model = measurement["model"]
    _assert(model["xml_path"].endswith("two_joint_arm.xml"), "wrong model path")
    _assert(model["frame_skip"] == FRAME_SKIP, "wrong production frame skip")
    _assert(
        measurement["raw_probe_records"],
        "production collection returned no in-memory probes",
    )
    _assert_finite(measurement)
    return {
        "status": "passed",
        "production_collection_path": True,
        "artifact_read": False,
        "raw_probe_records_checked": len(measurement["raw_probe_records"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="check-result JSON path")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run the in-memory production-path compatibility check",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = (
        run_compatibility_check() if args.compatibility else run_artifact_check()
    )
    with Path(args.artifact).open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
