"""Validate and summarize an M5 control-step trace for descriptive analysis.

All outcome and hold checks use the environment-reported distance channel, as
does the accessible research environment. The separately q-derived distance
is retained throughout so stale-site discrepancies are not hidden.
"""

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


PANEL_SIZE = 200
FIRST_EXPECTED_SEED = 2026101800
MAX_EPISODE_STEPS = 500
REQUIRED_HOLD_STEPS = 100
SUCCESS_THRESHOLD_M = 0.01
CONTROL_SUBSTEPS = 10
CONTROL_DT_SECONDS = 0.02
JOINT_LIMIT_RAD = math.radians(170.0)
LINK_LENGTHS_M = (0.12, 0.10)
ACTUATOR_GEARS = (5.0, 5.0)
OUTCOMES = ("success", "no_reach_failure", "post_reach_failure")
RADIAL_BINS = (
    ("6–<10 cm", 6.0, 10.0),
    ("10–<14 cm", 10.0, 14.0),
    ("14–<18 cm", 14.0, 18.0),
    ("18–20 cm", 18.0, 20.0),
)
ANGULAR_SECTORS = tuple(
    (f"[{lower},{lower + 45})°", float(lower), float(lower + 45))
    for lower in range(-180, 180, 45)
)


class EvidenceError(ValueError):
    """Raised when an input trace is incomplete or internally inconsistent."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise EvidenceError(f"non-finite JSON constant is not allowed: {value}")


def _check_finite_json(value: Any, location: str = "root") -> None:
    """Reject non-finite floats anywhere, including otherwise unused fields."""
    if isinstance(value, dict):
        for key, child in value.items():
            _check_finite_json(child, f"{location}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_finite_json(child, f"{location}/{index}")
    elif type(value) is float and not math.isfinite(value):
        raise EvidenceError(f"{location} contains a non-finite number")


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as source:
            artifact = json.load(
                source,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_nonstandard_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, EvidenceError) as exc:
        raise EvidenceError(f"cannot read trace artifact {path}: {exc}") from exc
    _check_finite_json(artifact)
    return artifact


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{location} must be a JSON object")
    return value


def _array(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceError(f"{location} must be a JSON array")
    return value


def _required(record: Any, field: str, location: str) -> Any:
    mapping = _mapping(record, location)
    if field not in mapping:
        raise EvidenceError(f"{location} is missing required field {field!r}")
    return mapping[field]


def _integer(
    value: Any, location: str, minimum: int, maximum: int | None = None
) -> int:
    if type(value) is not int:
        raise EvidenceError(f"{location} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"at least {minimum}"
        if maximum is not None:
            bounds += f" and at most {maximum}"
        raise EvidenceError(f"{location} must be {bounds}; got {value}")
    return value


def _number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{location} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise EvidenceError(f"{location} must be a finite number") from exc
    if not math.isfinite(number):
        raise EvidenceError(f"{location} must be a finite number")
    return number


def _vector(value: Any, length: int, location: str) -> list[float]:
    items = _array(value, location)
    if len(items) != length:
        raise EvidenceError(f"{location} must contain exactly {length} values")
    return [
        _number(item, f"{location}/{index}") for index, item in enumerate(items)
    ]


def _close(
    actual: float, expected: float, location: str, *, tolerance: float = 1e-8
) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-8, abs_tol=tolerance):
        raise EvidenceError(
            f"{location} is inconsistent: got {actual}, expected {expected}"
        )


def _bounded(value: float, lower: float, upper: float, location: str) -> float:
    tolerance = 1e-9
    if value < lower and math.isclose(value, lower, rel_tol=0.0, abs_tol=tolerance):
        return lower
    if value > upper and math.isclose(value, upper, rel_tol=0.0, abs_tol=tolerance):
        return upper
    if not lower <= value <= upper:
        raise EvidenceError(
            f"{location} must be between {lower} and {upper}; got {value}"
        )
    return value


def _wrap_to_pi(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _expected_branch_errors(
    radius_m: float, angle_degrees: float, q: list[float]
) -> dict[str, list[float]]:
    target_x = radius_m * math.cos(math.radians(angle_degrees))
    target_y = radius_m * math.sin(math.radians(angle_degrees))
    upper, forearm = LINK_LENGTHS_M
    cosine = (
        target_x**2 + target_y**2 - upper**2 - forearm**2
    ) / (2.0 * upper * forearm)
    if cosine < -1.0 - 1e-12 or cosine > 1.0 + 1e-12:
        raise EvidenceError("target is outside the two-link arm workspace")
    elbow_magnitude = math.acos(max(-1.0, min(1.0, cosine)))
    target_angle = math.atan2(target_y, target_x)
    result = {}
    for branch, elbow in (
        ("elbow_positive", elbow_magnitude),
        ("elbow_negative", -elbow_magnitude),
    ):
        shoulder = target_angle - math.atan2(
            forearm * math.sin(elbow),
            upper + forearm * math.cos(elbow),
        )
        result[branch] = [
            _wrap_to_pi(shoulder - q[0]),
            _wrap_to_pi(elbow - q[1]),
        ]
    return result


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _branch_metrics(
    errors: dict[str, list[float]],
) -> tuple[dict[str, float], dict[str, float], str]:
    norms = {branch: _norm(values) for branch, values in errors.items()}
    cumulative = {
        branch: sum(abs(value) for value in values)
        for branch, values in errors.items()
    }
    positive = cumulative["elbow_positive"]
    negative = cumulative["elbow_negative"]
    if math.isclose(positive, negative, rel_tol=1e-12, abs_tol=1e-12):
        identity = "tie"
    else:
        identity = "elbow_positive" if positive < negative else "elbow_negative"
    return norms, cumulative, identity


def _validate_metadata(artifact: dict[str, Any]) -> None:
    if _integer(_required(artifact, "schema_version", "trace"), "schema_version", 1) != 1:
        raise EvidenceError("trace schema_version must be 1")
    if (
        _integer(_required(artifact, "episodes", "trace"), "episodes", PANEL_SIZE)
        != PANEL_SIZE
    ):
        raise EvidenceError(f"trace must declare exactly {PANEL_SIZE} episodes")
    metadata = _mapping(_required(artifact, "metadata", "trace"), "metadata")
    units = _mapping(_required(metadata, "units", "metadata"), "metadata/units")
    expected_units = {
        "joint_position": "rad",
        "joint_velocity": "rad/s",
        "endpoint_error": "m",
        "environment_reported_distance": "m",
        "joint_limit_margin": "rad",
        "command": "normalized actuator command",
        "torque": "N m",
        "target_radius": "m",
        "target_angle": "degrees",
    }
    for field, expected in expected_units.items():
        if _required(units, field, "metadata/units") != expected:
            raise EvidenceError(
                f"metadata/units/{field} must be {expected!r}"
            )
    if _required(metadata, "joint_order", "metadata") != ["shoulder", "elbow"]:
        raise EvidenceError("metadata/joint_order must be ['shoulder', 'elbow']")
    if (
        _integer(
            _required(metadata, "control_substeps", "metadata"),
            "metadata/control_substeps",
            CONTROL_SUBSTEPS,
        )
        != CONTROL_SUBSTEPS
    ):
        raise EvidenceError(f"metadata/control_substeps must be {CONTROL_SUBSTEPS}")
    if (
        _required(metadata, "control_sampling", "metadata")
        != "10 MuJoCo substeps per control step"
    ):
        raise EvidenceError("metadata/control_sampling is inconsistent")
    _close(
        _number(
            _required(metadata, "control_timestep_seconds", "metadata"),
            "metadata/control_timestep_seconds",
        ),
        CONTROL_DT_SECONDS,
        "metadata/control_timestep_seconds",
        tolerance=1e-12,
    )
    if (
        _integer(
            _required(metadata, "hold_steps_required", "metadata"),
            "metadata/hold_steps_required",
            REQUIRED_HOLD_STEPS,
        )
        != REQUIRED_HOLD_STEPS
    ):
        raise EvidenceError(
            f"metadata/hold_steps_required must be {REQUIRED_HOLD_STEPS}"
        )
    if (
        _required(metadata, "torque_sampling", "metadata")
        != "control-step endpoint"
    ):
        raise EvidenceError("metadata/torque_sampling is inconsistent")
    for field in ("distance_semantics", "reset_sample", "scope"):
        value = _required(metadata, field, "metadata")
        if not isinstance(value, str) or not value.strip():
            raise EvidenceError(f"metadata/{field} must be a nonempty string")


def _validate_sample(
    raw: Any,
    *,
    location: str,
    control_step: int,
    radius_m: float,
    angle_degrees: float,
) -> dict[str, Any]:
    sample = _mapping(raw, location)
    if (
        _integer(
            _required(sample, "control_step", location),
            f"{location}/control_step",
            0,
            MAX_EPISODE_STEPS,
        )
        != control_step
    ):
        raise EvidenceError(f"{location}/control_step is not consecutive")
    q = _vector(_required(sample, "q_rad", location), 2, f"{location}/q_rad")
    qdot = _vector(
        _required(sample, "qdot_rad_s", location), 2, f"{location}/qdot_rad_s"
    )
    if control_step == 0:
        for index, value in enumerate(q):
            _close(value, 0.0, f"{location}/q_rad/{index}")
        for index, value in enumerate(qdot):
            _close(value, 0.0, f"{location}/qdot_rad_s/{index}")

    error_vector = _vector(
        _required(sample, "endpoint_minus_target_m", location),
        3,
        f"{location}/endpoint_minus_target_m",
    )
    q_distance = _number(
        _required(sample, "endpoint_error_norm_m", location),
        f"{location}/endpoint_error_norm_m",
    )
    if q_distance < 0.0:
        raise EvidenceError(f"{location}/endpoint_error_norm_m must be nonnegative")
    _close(_norm(error_vector), q_distance, f"{location}/endpoint_error_norm_m")

    target_x = radius_m * math.cos(math.radians(angle_degrees))
    target_y = radius_m * math.sin(math.radians(angle_degrees))
    end_x = LINK_LENGTHS_M[0] * math.cos(q[0]) + LINK_LENGTHS_M[1] * math.cos(
        q[0] + q[1]
    )
    end_y = LINK_LENGTHS_M[0] * math.sin(q[0]) + LINK_LENGTHS_M[1] * math.sin(
        q[0] + q[1]
    )
    expected_error = [end_x - target_x, end_y - target_y, 0.0]
    for axis, (actual, expected) in enumerate(
        zip(error_vector, expected_error, strict=True)
    ):
        _close(actual, expected, f"{location}/endpoint_minus_target_m/{axis}")
    _close(
        q_distance,
        _norm(expected_error),
        f"{location}/endpoint_error_norm_m",
    )

    environment_distance = _number(
        _required(sample, "environment_reported_distance_m", location),
        f"{location}/environment_reported_distance_m",
    )
    if environment_distance < 0.0:
        raise EvidenceError(
            f"{location}/environment_reported_distance_m must be nonnegative"
        )

    raw_branches = _mapping(
        _required(sample, "ik_branch_joint_errors_rad", location),
        f"{location}/ik_branch_joint_errors_rad",
    )
    branches = {}
    expected_branches = _expected_branch_errors(radius_m, angle_degrees, q)
    for branch in ("elbow_positive", "elbow_negative"):
        values = _vector(
            _required(raw_branches, branch, f"{location}/ik_branch_joint_errors_rad"),
            2,
            f"{location}/ik_branch_joint_errors_rad/{branch}",
        )
        for index, (actual, expected) in enumerate(
            zip(values, expected_branches[branch], strict=True)
        ):
            _close(
                actual,
                expected,
                f"{location}/ik_branch_joint_errors_rad/{branch}/{index}",
            )
        branches[branch] = values

    margins = _mapping(
        _required(sample, "joint_limit_margins_rad", location),
        f"{location}/joint_limit_margins_rad",
    )
    for index, joint in enumerate(("shoulder", "elbow")):
        joint_margin = _mapping(
            _required(margins, joint, f"{location}/joint_limit_margins_rad"),
            f"{location}/joint_limit_margins_rad/{joint}",
        )
        to_lower = _number(
            _required(joint_margin, "to_lower_limit_rad", f"{location}/{joint}"),
            f"{location}/joint_limit_margins_rad/{joint}/to_lower_limit_rad",
        )
        to_upper = _number(
            _required(joint_margin, "to_upper_limit_rad", f"{location}/{joint}"),
            f"{location}/joint_limit_margins_rad/{joint}/to_upper_limit_rad",
        )
        _close(
            to_lower,
            q[index] + JOINT_LIMIT_RAD,
            f"{location}/joint_limit_margins_rad/{joint}/to_lower_limit_rad",
        )
        _close(
            to_upper,
            JOINT_LIMIT_RAD - q[index],
            f"{location}/joint_limit_margins_rad/{joint}/to_upper_limit_rad",
        )

    held_steps = _integer(
        _required(sample, "held_steps", location),
        f"{location}/held_steps",
        0,
        REQUIRED_HOLD_STEPS,
    )
    command_fields = (
        ("clipped_applied_command", 1.0),
        ("nominal_command_times_gear_torque_nm", None),
        ("measured_generalized_applied_joint_torque_nm", None),
    )
    control_vectors: dict[str, list[float] | None] = {}
    for field, _ in command_fields:
        value = _required(sample, field, location)
        if control_step == 0:
            if value is not None:
                raise EvidenceError(f"{location}/{field} must be null at reset")
            control_vectors[field] = None
            continue
        vector = _vector(value, 2, f"{location}/{field}")
        control_vectors[field] = vector

    if control_step > 0:
        command = control_vectors["clipped_applied_command"]
        nominal_torque = control_vectors["nominal_command_times_gear_torque_nm"]
        measured_torque = control_vectors[
            "measured_generalized_applied_joint_torque_nm"
        ]
        assert command is not None and nominal_torque is not None
        assert measured_torque is not None
        for index, (value, gear) in enumerate(
            zip(command, ACTUATOR_GEARS, strict=True)
        ):
            if value < -1.0 - 1e-8 or value > 1.0 + 1e-8:
                raise EvidenceError(
                    f"{location}/clipped_applied_command/{index} exceeds [-1, 1]"
                )
            expected_torque = value * gear
            _close(
                nominal_torque[index],
                expected_torque,
                f"{location}/nominal_command_times_gear_torque_nm/{index}",
            )
            _close(
                measured_torque[index],
                expected_torque,
                f"{location}/measured_generalized_applied_joint_torque_nm/{index}",
                tolerance=1e-7,
            )

    return {
        "control_step": control_step,
        "q_rad": q,
        "qdot_rad_s": qdot,
        "qdot_norm_rad_s": _norm(qdot),
        "endpoint_minus_target_m": error_vector,
        "endpoint_error_norm_m": q_distance,
        "environment_reported_distance_m": environment_distance,
        "ik_branch_joint_errors_rad": branches,
        "joint_limit_margins_rad": margins,
        "held_steps": held_steps,
        "control_vectors": control_vectors,
    }


def _validate_episode(raw: Any, index: int) -> dict[str, Any]:
    location = f"episode_rows/{index}"
    episode = _mapping(raw, location)
    if (
        _integer(
            _required(episode, "episode", location),
            f"{location}/episode",
            0,
            PANEL_SIZE - 1,
        )
        != index
    ):
        raise EvidenceError(f"{location}/episode is not consecutive")
    expected_seed = FIRST_EXPECTED_SEED + index
    seed = _integer(
        _required(episode, "episode_seed", location),
        f"{location}/episode_seed",
        FIRST_EXPECTED_SEED,
        FIRST_EXPECTED_SEED + PANEL_SIZE - 1,
    )
    if seed != expected_seed:
        raise EvidenceError(
            f"{location}/episode_seed must be consecutive from "
            f"{FIRST_EXPECTED_SEED}; got {seed}"
        )

    radius_m = _bounded(
        _number(
            _required(episode, "target_radius_m", location),
            f"{location}/target_radius_m",
        ),
        0.06,
        0.20,
        f"{location}/target_radius_m",
    )
    angle_degrees = _bounded(
        _number(
            _required(episode, "target_angle_degrees", location),
            f"{location}/target_angle_degrees",
        ),
        -180.0,
        180.0,
        f"{location}/target_angle_degrees",
    )
    outcome = _required(episode, "outcome", location)
    if outcome not in OUTCOMES:
        raise EvidenceError(f"{location}/outcome must be one of {OUTCOMES}")
    success = _required(episode, "success", location)
    if type(success) is not bool:
        raise EvidenceError(f"{location}/success must be a boolean")
    steps = _integer(
        _required(episode, "steps", location),
        f"{location}/steps",
        1,
        MAX_EPISODE_STEPS,
    )
    first_reach_raw = _required(episode, "first_reach_step", location)
    first_reach_step = (
        None
        if first_reach_raw is None
        else _integer(
            first_reach_raw,
            f"{location}/first_reach_step",
            1,
            steps,
        )
    )
    terminated = _required(episode, "terminated", location)
    truncated = _required(episode, "truncated", location)
    if type(terminated) is not bool or type(truncated) is not bool:
        raise EvidenceError(f"{location} termination flags must be booleans")
    if success is not terminated:
        raise EvidenceError(f"{location} success and terminated flags disagree")
    if truncated is not (steps == MAX_EPISODE_STEPS):
        raise EvidenceError(f"{location} truncated flag and episode length disagree")
    if not (terminated or truncated):
        raise EvidenceError(f"{location} has no terminal condition")
    if success != (outcome == "success"):
        raise EvidenceError(f"{location} outcome and success flag disagree")

    trajectory = _array(
        _required(episode, "trajectory", location), f"{location}/trajectory"
    )
    if len(trajectory) != steps + 1:
        raise EvidenceError(
            f"{location}/trajectory must contain steps + 1 samples "
            f"({steps + 1}); found {len(trajectory)}"
        )
    samples = [
        _validate_sample(
            raw_sample,
            location=f"{location}/trajectory/{sample_index}",
            control_step=sample_index,
            radius_m=radius_m,
            angle_degrees=angle_degrees,
        )
        for sample_index, raw_sample in enumerate(trajectory)
    ]

    first_observed_reach = None
    previous_held = 0
    disagreement_steps = []
    for sample_index, sample in enumerate(samples):
        if sample_index == 0:
            expected_held = 0
        elif sample["environment_reported_distance_m"] <= SUCCESS_THRESHOLD_M:
            expected_held = previous_held + 1
        else:
            expected_held = 0
        if sample["held_steps"] != expected_held:
            raise EvidenceError(
                f"{location}/trajectory/{sample_index}/held_steps is inconsistent "
                "with uninterrupted environment-reported-distance samples"
            )
        if expected_held > REQUIRED_HOLD_STEPS:
            raise EvidenceError(f"{location} exceeds the required hold counter")
        if expected_held > 0 and first_observed_reach is None:
            first_observed_reach = sample_index
        previous_held = expected_held
        environment_inside = (
            sample["environment_reported_distance_m"] <= SUCCESS_THRESHOLD_M
        )
        q_inside = sample["endpoint_error_norm_m"] <= SUCCESS_THRESHOLD_M
        if environment_inside != q_inside:
            disagreement_steps.append(sample_index)

    if first_reach_step != first_observed_reach:
        raise EvidenceError(
            f"{location} first_reach_step does not match the first positive "
            "environment held-step sample"
        )
    if outcome == "no_reach_failure" and first_reach_step is not None:
        raise EvidenceError(f"{location} no-reach outcome has a first reach")
    if outcome == "post_reach_failure" and first_reach_step is None:
        raise EvidenceError(f"{location} post-reach outcome has no first reach")
    if success:
        if first_reach_step is None:
            raise EvidenceError(f"{location} success has no first reach")
        expected_final_step = first_reach_step + REQUIRED_HOLD_STEPS - 1
        if steps != expected_final_step:
            raise EvidenceError(
                f"{location} successful uninterrupted hold must end at step "
                f"{expected_final_step}; trace ends at {steps}"
            )
        successful_hold = samples[
            first_reach_step : first_reach_step + REQUIRED_HOLD_STEPS
        ]
        if [sample["held_steps"] for sample in successful_hold] != list(
            range(1, REQUIRED_HOLD_STEPS + 1)
        ):
            raise EvidenceError(f"{location} does not contain the uninterrupted hold")
        if samples[-1]["held_steps"] != REQUIRED_HOLD_STEPS:
            raise EvidenceError(f"{location} final held-step count is not 100")
    elif any(sample["held_steps"] >= REQUIRED_HOLD_STEPS for sample in samples):
        raise EvidenceError(f"{location} reached a complete hold but is labeled failed")

    return {
        "episode": index,
        "episode_seed": seed,
        "target_radius_cm": radius_m * 100.0,
        "target_angle_degrees": -180.0 if angle_degrees == 180.0 else angle_degrees,
        "outcome": outcome,
        "success": success,
        "first_reach_step": first_reach_step,
        "steps": steps,
        "terminated": terminated,
        "truncated": truncated,
        "trajectory": samples,
        "tolerance_disagreement_steps": disagreement_steps,
    }


def _radial_label(radius_cm: float) -> str:
    for label, lower, upper in RADIAL_BINS[:-1]:
        if lower <= radius_cm < upper:
            return label
    if RADIAL_BINS[-1][1] <= radius_cm <= RADIAL_BINS[-1][2]:
        return RADIAL_BINS[-1][0]
    raise EvidenceError(f"target radius {radius_cm} cm is outside the radial bins")


def _angular_label(angle_degrees: float) -> str:
    for label, lower, upper in ANGULAR_SECTORS:
        if lower <= angle_degrees < upper:
            return label
    raise EvidenceError(f"target angle {angle_degrees} is outside the angular sectors")


def _norm_at(sample: dict[str, Any], field: str) -> float | None:
    values = sample["control_vectors"][field]
    return None if values is None else _norm(values)


def _episode_features(row: dict[str, Any]) -> dict[str, Any]:
    samples = row["trajectory"]
    first_reach = row["first_reach_step"]
    minimum_sample = min(
        samples,
        key=lambda sample: sample["endpoint_error_norm_m"],
    )
    minimum_environment_sample = min(
        samples,
        key=lambda sample: sample["environment_reported_distance_m"],
    )
    selected_samples = {
        "reset": samples[0],
        "first_reach": None if first_reach is None else samples[first_reach],
        "minimum_error": minimum_sample,
        "final": samples[-1],
    }

    def branch_details(sample: dict[str, Any] | None) -> dict[str, Any] | None:
        if sample is None:
            return None
        norms, cumulative, identity = _branch_metrics(
            sample["ik_branch_joint_errors_rad"]
        )
        return {
            "error_norms_rad": norms,
            "cumulative_joint_error_rad": cumulative,
            "minimum_cumulative_joint_error_branch": identity,
        }

    branch_at = {
        name: branch_details(sample) for name, sample in selected_samples.items()
    }
    reach_sample = selected_samples["first_reach"]
    if first_reach is None:
        pre_reach_samples = samples[1:]
        acquisition_samples = samples[1:]
        held_samples = []
        post_reach_samples = []
    else:
        pre_reach_samples = samples[:first_reach]
        acquisition_samples = samples[1 : first_reach + 1]
        held_samples = [sample for sample in samples if sample["held_steps"] > 0]
        post_reach_samples = samples[first_reach + 1 :]

    def peak_qdot_sample(
        rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not rows:
            return None
        # max() retains the first matching item, so equal-norm peaks select
        # the earliest control-step sample.
        return max(rows, key=lambda sample: sample["qdot_norm_rad_s"])

    peak_pre_reach_sample = peak_qdot_sample(pre_reach_samples)
    peak_post_reach_sample = peak_qdot_sample(post_reach_samples)

    def maximum_norm(rows: list[dict[str, Any]], field: str) -> float | None:
        values = [_norm_at(sample, field) for sample in rows]
        nonnull = [value for value in values if value is not None]
        return max(nonnull) if nonnull else None

    discrepancy_by_sample = [
        abs(
            sample["environment_reported_distance_m"]
            - sample["endpoint_error_norm_m"]
        )
        for sample in samples
    ]
    maximum_discrepancy = max(discrepancy_by_sample)
    maximum_discrepancy_step = discrepancy_by_sample.index(maximum_discrepancy)
    margins = [
        value
        for sample in samples
        for joint in ("shoulder", "elbow")
        for value in (
            sample["joint_limit_margins_rad"][joint]["to_lower_limit_rad"],
            sample["joint_limit_margins_rad"][joint]["to_upper_limit_rad"],
        )
    ]
    reach_margins = (
        []
        if reach_sample is None
        else [
            value
            for joint in ("shoulder", "elbow")
            for value in (
                reach_sample["joint_limit_margins_rad"][joint][
                    "to_lower_limit_rad"
                ],
                reach_sample["joint_limit_margins_rad"][joint][
                    "to_upper_limit_rad"
                ],
            )
        ]
    )

    def selected_norm(sample: dict[str, Any] | None, field: str) -> float | None:
        return None if sample is None else _norm_at(sample, field)

    feature_record: dict[str, Any] = {
        "episode": row["episode"],
        "episode_seed": row["episode_seed"],
        "target_radius_cm": row["target_radius_cm"],
        "target_angle_degrees": row["target_angle_degrees"],
        "outcome": row["outcome"],
        "success": row["success"],
        "first_reach_step": first_reach,
        "steps": row["steps"],
        "initial_endpoint_error_m": samples[0]["endpoint_error_norm_m"],
        "minimum_endpoint_error_m": minimum_sample["endpoint_error_norm_m"],
        "minimum_error_control_step": minimum_sample["control_step"],
        "final_endpoint_error_m": samples[-1]["endpoint_error_norm_m"],
        "initial_environment_reported_distance_m": (
            samples[0]["environment_reported_distance_m"]
        ),
        "minimum_environment_reported_distance_m": (
            minimum_environment_sample["environment_reported_distance_m"]
        ),
        "minimum_environment_distance_control_step": (
            minimum_environment_sample["control_step"]
        ),
        "environment_reported_distance_at_minimum_q_error_m": (
            minimum_sample["environment_reported_distance_m"]
        ),
        "final_environment_reported_distance_m": (
            samples[-1]["environment_reported_distance_m"]
        ),
        "environment_vs_q_distance_discrepancy_at_reset_m": abs(
            samples[0]["environment_reported_distance_m"]
            - samples[0]["endpoint_error_norm_m"]
        ),
        "environment_vs_q_distance_discrepancy_at_minimum_q_error_m": abs(
            minimum_sample["environment_reported_distance_m"]
            - minimum_sample["endpoint_error_norm_m"]
        ),
        "environment_vs_q_distance_discrepancy_at_final_m": abs(
            samples[-1]["environment_reported_distance_m"]
            - samples[-1]["endpoint_error_norm_m"]
        ),
        "maximum_abs_environment_vs_q_distance_discrepancy_m": maximum_discrepancy,
        "maximum_distance_discrepancy_control_step": maximum_discrepancy_step,
        "tolerance_class_disagreement_sample_count": len(
            row["tolerance_disagreement_steps"]
        ),
        "tolerance_class_disagreement_control_steps": row[
            "tolerance_disagreement_steps"
        ],
        "first_reach_endpoint_error_m": (
            None
            if reach_sample is None
            else reach_sample["endpoint_error_norm_m"]
        ),
        "first_reach_qdot_norm_rad_s": (
            None if reach_sample is None else reach_sample["qdot_norm_rad_s"]
        ),
        "first_reach_qdot_rad_s": (
            None if reach_sample is None else reach_sample["qdot_rad_s"]
        ),
        "first_reach_shoulder_qdot_rad_s": (
            None if reach_sample is None else reach_sample["qdot_rad_s"][0]
        ),
        "first_reach_elbow_qdot_rad_s": (
            None if reach_sample is None else reach_sample["qdot_rad_s"][1]
        ),
        "peak_pre_reach_qdot_rad_s": (
            None
            if peak_pre_reach_sample is None
            else peak_pre_reach_sample["qdot_rad_s"]
        ),
        "peak_pre_reach_shoulder_qdot_rad_s": (
            None
            if peak_pre_reach_sample is None
            else peak_pre_reach_sample["qdot_rad_s"][0]
        ),
        "peak_pre_reach_elbow_qdot_rad_s": (
            None
            if peak_pre_reach_sample is None
            else peak_pre_reach_sample["qdot_rad_s"][1]
        ),
        "peak_pre_reach_qdot_norm_rad_s": (
            None
            if peak_pre_reach_sample is None
            else peak_pre_reach_sample["qdot_norm_rad_s"]
        ),
        "peak_pre_reach_qdot_control_step": (
            None
            if peak_pre_reach_sample is None
            else peak_pre_reach_sample["control_step"]
        ),
        "peak_post_reach_qdot_rad_s": (
            None
            if peak_post_reach_sample is None
            else peak_post_reach_sample["qdot_rad_s"]
        ),
        "peak_post_reach_shoulder_qdot_rad_s": (
            None
            if peak_post_reach_sample is None
            else peak_post_reach_sample["qdot_rad_s"][0]
        ),
        "peak_post_reach_elbow_qdot_rad_s": (
            None
            if peak_post_reach_sample is None
            else peak_post_reach_sample["qdot_rad_s"][1]
        ),
        "peak_post_reach_qdot_norm_rad_s": (
            None
            if peak_post_reach_sample is None
            else peak_post_reach_sample["qdot_norm_rad_s"]
        ),
        "peak_post_reach_qdot_control_step": (
            None
            if peak_post_reach_sample is None
            else peak_post_reach_sample["control_step"]
        ),
        "minimum_joint_limit_margin_rad_overall": min(margins),
        "minimum_joint_limit_margin_rad_at_first_reach": (
            None if not reach_margins else min(reach_margins)
        ),
        "first_reach_clipped_command_norm": selected_norm(
            reach_sample, "clipped_applied_command"
        ),
        "first_reach_nominal_torque_norm_nm": selected_norm(
            reach_sample, "nominal_command_times_gear_torque_nm"
        ),
        "first_reach_measured_torque_norm_nm": selected_norm(
            reach_sample, "measured_generalized_applied_joint_torque_nm"
        ),
        "maximum_acquisition_clipped_command_norm": maximum_norm(
            acquisition_samples, "clipped_applied_command"
        ),
        "maximum_acquisition_nominal_torque_norm_nm": maximum_norm(
            acquisition_samples, "nominal_command_times_gear_torque_nm"
        ),
        "maximum_acquisition_measured_torque_norm_nm": maximum_norm(
            acquisition_samples, "measured_generalized_applied_joint_torque_nm"
        ),
        "maximum_held_sample_clipped_command_norm": maximum_norm(
            held_samples, "clipped_applied_command"
        ),
        "maximum_held_sample_nominal_torque_norm_nm": maximum_norm(
            held_samples, "nominal_command_times_gear_torque_nm"
        ),
        "maximum_held_sample_measured_torque_norm_nm": maximum_norm(
            held_samples, "measured_generalized_applied_joint_torque_nm"
        ),
        "branch_error_norms_rad": {
            name: None if detail is None else detail["error_norms_rad"]
            for name, detail in branch_at.items()
        },
        "branch_cumulative_joint_error_rad": {
            name: (
                None
                if detail is None
                else detail["cumulative_joint_error_rad"]
            )
            for name, detail in branch_at.items()
        },
        "branch_identity_by_minimum_cumulative_joint_error": {
            name: (
                None
                if detail is None
                else detail["minimum_cumulative_joint_error_branch"]
            )
            for name, detail in branch_at.items()
            if name != "final"
        },
    }
    for context, details in branch_at.items():
        for branch in ("elbow_positive", "elbow_negative"):
            feature_record[
                f"{branch}_error_norm_rad_at_{context}"
            ] = None if details is None else details["error_norms_rad"][branch]
            feature_record[
                f"{branch}_cumulative_joint_error_rad_at_{context}"
            ] = (
                None
                if details is None
                else details["cumulative_joint_error_rad"][branch]
            )
    return feature_record


NUMERIC_FEATURES = (
    "target_radius_cm",
    "target_angle_degrees",
    "first_reach_step",
    "steps",
    "initial_endpoint_error_m",
    "minimum_endpoint_error_m",
    "minimum_error_control_step",
    "final_endpoint_error_m",
    "initial_environment_reported_distance_m",
    "minimum_environment_reported_distance_m",
    "minimum_environment_distance_control_step",
    "environment_reported_distance_at_minimum_q_error_m",
    "final_environment_reported_distance_m",
    "environment_vs_q_distance_discrepancy_at_reset_m",
    "environment_vs_q_distance_discrepancy_at_minimum_q_error_m",
    "environment_vs_q_distance_discrepancy_at_final_m",
    "maximum_abs_environment_vs_q_distance_discrepancy_m",
    "maximum_distance_discrepancy_control_step",
    "tolerance_class_disagreement_sample_count",
    "first_reach_endpoint_error_m",
    "first_reach_qdot_norm_rad_s",
    "first_reach_shoulder_qdot_rad_s",
    "first_reach_elbow_qdot_rad_s",
    "peak_pre_reach_shoulder_qdot_rad_s",
    "peak_pre_reach_elbow_qdot_rad_s",
    "peak_pre_reach_qdot_norm_rad_s",
    "peak_pre_reach_qdot_control_step",
    "peak_post_reach_shoulder_qdot_rad_s",
    "peak_post_reach_elbow_qdot_rad_s",
    "peak_post_reach_qdot_norm_rad_s",
    "peak_post_reach_qdot_control_step",
    "minimum_joint_limit_margin_rad_overall",
    "minimum_joint_limit_margin_rad_at_first_reach",
    "first_reach_clipped_command_norm",
    "first_reach_nominal_torque_norm_nm",
    "first_reach_measured_torque_norm_nm",
    "maximum_acquisition_clipped_command_norm",
    "maximum_acquisition_nominal_torque_norm_nm",
    "maximum_acquisition_measured_torque_norm_nm",
    "maximum_held_sample_clipped_command_norm",
    "maximum_held_sample_nominal_torque_norm_nm",
    "maximum_held_sample_measured_torque_norm_nm",
) + tuple(
    f"{branch}_{metric}_at_{context}"
    for context in ("reset", "first_reach", "minimum_error", "final")
    for branch in ("elbow_positive", "elbow_negative")
    for metric in ("error_norm_rad", "cumulative_joint_error_rad")
)


def _summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    outcome_counts = {outcome: 0 for outcome in OUTCOMES}
    for row in rows:
        outcome_counts[row["outcome"]] += 1
    features = {}
    for feature in NUMERIC_FEATURES:
        values = [
            row[feature]
            for row in rows
            if row[feature] is not None
        ]
        features[feature] = {
            "sample_size": len(values),
            "mean": (sum(values) / len(values)) if values else None,
            "median": statistics.median(values) if values else None,
        }
    branch_identity_counts = {
        key: {
            "sample_size": 0,
            "counts": {
                branch: 0
                for branch in ("elbow_positive", "elbow_negative", "tie")
            },
        }
        for key in ("reset", "first_reach", "minimum_error")
    }
    for row in rows:
        identities = row["branch_identity_by_minimum_cumulative_joint_error"]
        for key in branch_identity_counts:
            identity = identities[key]
            if identity is not None:
                branch_identity_counts[key]["sample_size"] += 1
                branch_identity_counts[key]["counts"][identity] += 1
    return {
        "episode_count": len(rows),
        "outcome_counts": outcome_counts,
        "feature_summaries": features,
        "branch_identity_counts": branch_identity_counts,
    }


def _stratified_summaries(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sector_groups = {label: [] for label, _, _ in ANGULAR_SECTORS}
    radial_groups = {label: [] for label, _, _ in RADIAL_BINS}
    cell_groups = {
        sector: {radius: [] for radius, _, _ in RADIAL_BINS}
        for sector, _, _ in ANGULAR_SECTORS
    }
    for row in rows:
        sector = _angular_label(row["target_angle_degrees"])
        radial = _radial_label(row["target_radius_cm"])
        sector_groups[sector].append(row)
        radial_groups[radial].append(row)
        cell_groups[sector][radial].append(row)
    return (
        {
            label: _summarize_group(sector_groups[label])
            for label, _, _ in ANGULAR_SECTORS
        },
        {
            label: _summarize_group(radial_groups[label])
            for label, _, _ in RADIAL_BINS
        },
        {
            sector: {
                radial: _summarize_group(cell_groups[sector][radial])
                for radial, _, _ in RADIAL_BINS
            }
            for sector, _, _ in ANGULAR_SECTORS
        },
    )


def _mean_vector(vectors: list[list[float]], size: int) -> list[float] | None:
    if not vectors:
        return None
    return [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(size)
    ]


def _mean_or_none(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _nearest_branch_error(sample: dict[str, Any]) -> float:
    norms, _, _ = _branch_metrics(sample["ik_branch_joint_errors_rad"])
    return min(norms.values())


def _control_step_curves(
    population: list[dict[str, Any]],
) -> dict[str, Any]:
    groups = {}
    for outcome in OUTCOMES:
        outcome_rows = [row for row in population if row["outcome"] == outcome]
        steps = []
        for control_step in range(21):
            samples = [
                row["trajectory"][control_step]
                for row in outcome_rows
                if control_step <= row["steps"]
            ]
            steps.append(
                {
                    "control_step": control_step,
                    "sample_size": len(samples),
                    "mean_q_rad": _mean_vector(
                        [sample["q_rad"] for sample in samples], 2
                    ),
                    "mean_qdot_norm_rad_s": _mean_or_none(
                        [sample["qdot_norm_rad_s"] for sample in samples]
                    ),
                    "mean_environment_reported_distance_m": _mean_or_none(
                        [
                            sample["environment_reported_distance_m"]
                            for sample in samples
                        ]
                    ),
                    "mean_q_derived_distance_m": _mean_or_none(
                        [sample["endpoint_error_norm_m"] for sample in samples]
                    ),
                    "mean_nearest_branch_error_norm_rad": _mean_or_none(
                        [_nearest_branch_error(sample) for sample in samples]
                    ),
                }
            )
        groups[outcome] = {
            "episode_count": len(outcome_rows),
            "steps": steps,
        }
    return groups


def _post_reach_curves(population: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {}
    for outcome in OUTCOMES:
        outcome_rows = [row for row in population if row["outcome"] == outcome]
        reached_rows = [row for row in outcome_rows if row["first_reach_step"] is not None]
        offsets = []
        for offset in range(REQUIRED_HOLD_STEPS):
            samples = []
            for row in reached_rows:
                sample_step = row["first_reach_step"] + offset
                if sample_step <= row["steps"]:
                    samples.append(row["trajectory"][sample_step])
            offsets.append(
                {
                    "steps_after_first_reach": offset,
                    "sample_size": len(samples),
                    "mean_qdot_rad_s": _mean_vector(
                        [sample["qdot_rad_s"] for sample in samples], 2
                    ),
                    "mean_qdot_norm_rad_s": _mean_or_none(
                        [sample["qdot_norm_rad_s"] for sample in samples]
                    ),
                    "mean_environment_reported_distance_m": _mean_or_none(
                        [
                            sample["environment_reported_distance_m"]
                            for sample in samples
                        ]
                    ),
                    "mean_q_derived_distance_m": _mean_or_none(
                        [sample["endpoint_error_norm_m"] for sample in samples]
                    ),
                    "mean_held_steps": _mean_or_none(
                        [float(sample["held_steps"]) for sample in samples]
                    ),
                }
            )
        groups[outcome] = {
            "episode_count": len(outcome_rows),
            "reached_episode_count": len(reached_rows),
            "steps_after_first_reach": offsets,
        }
    return groups


def build_analysis(artifact: Any) -> dict[str, Any]:
    """Validate an M5 artifact and build descriptive episode/stratum summaries."""
    _check_finite_json(artifact)
    root = _mapping(artifact, "trace artifact root")
    _validate_metadata(root)
    raw_rows = _array(_required(root, "episode_rows", "trace"), "episode_rows")
    if len(raw_rows) != PANEL_SIZE:
        raise EvidenceError(
            f"episode_rows must contain exactly {PANEL_SIZE} episodes; "
            f"found {len(raw_rows)}"
        )
    rows = [_validate_episode(row, index) for index, row in enumerate(raw_rows)]
    seeds = [row["episode_seed"] for row in rows]
    if len(set(seeds)) != PANEL_SIZE or seeds != list(
        range(FIRST_EXPECTED_SEED, FIRST_EXPECTED_SEED + PANEL_SIZE)
    ):
        raise EvidenceError("episode seeds must be 200 unique consecutive M5 seeds")

    episode_features = [_episode_features(row) for row in rows]
    outcome_counts = {
        outcome: sum(row["outcome"] == outcome for row in rows)
        for outcome in OUTCOMES
    }
    sector_summaries, radial_summaries, cell_summaries = _stratified_summaries(
        episode_features
    )
    sector_population = [
        row
        for row in episode_features
        if _angular_label(row["target_angle_degrees"]) == "[-180,-135)°"
    ]
    trajectory_rows = {row["episode_seed"]: row for row in rows}
    sector_trajectory = [
        trajectory_rows[row["episode_seed"]] for row in sector_population
    ]
    populations = {
        "full_panel": rows,
        "sector_[-180,-135)_degrees": sector_trajectory,
    }
    control_curves = {
        population: _control_step_curves(selected)
        for population, selected in populations.items()
    }
    post_reach_curves = {
        population: _post_reach_curves(selected)
        for population, selected in populations.items()
    }
    return {
        "schema_version": 1,
        "input": {
            "episodes": PANEL_SIZE,
            "episode_seed_start": FIRST_EXPECTED_SEED,
            "episode_seed_end": FIRST_EXPECTED_SEED + PANEL_SIZE - 1,
        },
        "overall_outcome_counts": {
            "episode_count": PANEL_SIZE,
            "successes": outcome_counts["success"],
            "no_reach_failures": outcome_counts["no_reach_failure"],
            "post_reach_failures": outcome_counts["post_reach_failure"],
            "outcome_counts": outcome_counts,
        },
        "stratified_episode_summaries": {
            "angular_sectors": sector_summaries,
            "radial_bins": radial_summaries,
            "sector_by_radius": cell_summaries,
        },
        "episodes": episode_features,
        "control_step_means_reset_through_step_20": control_curves,
        "post_first_reach_means_up_to_100_samples": post_reach_curves,
        "definitions_and_scope": {
            "outcome_and_hold_source": (
                "Outcomes, first reach and held-step progression follow the "
                "accessible research environment's post-substep samples and "
                "environment-reported distance channel."
            ),
            "paired_distance_channels": (
                "Environment-reported and q-derived distances are preserved "
                "separately; their absolute discrepancies and 1 cm tolerance "
                "classification disagreements reveal stale-site discrepancies."
            ),
            "sampling_limit": (
                "Ten MuJoCo substeps per control step cannot establish "
                "within-step occupancy."
            ),
            "official_scope": (
                "The research trace cannot establish protected official success "
                "or official generalization."
            ),
            "interpretation": (
                "Summaries are descriptive; no inferential or causal claims are made."
            ),
            "minimum_error_sample": (
                "The first sample attaining the minimum q-derived endpoint error."
            ),
            "branch_error_norm": (
                "Euclidean norm of the two recorded joint-angle errors for a branch."
            ),
            "branch_identity": (
                "Branch with the smaller sum of absolute shoulder and elbow errors; "
                "exact numerical ties are labeled tie."
            ),
            "nearest_branch_error": (
                "Minimum Euclidean branch joint-error norm at that sample."
            ),
            "joint_limit_margins": (
                "Margins are signed arithmetic differences from the declared "
                "+/-170 degree limits. A negative value means the sampled q "
                "crossed that declared limit in the research simulation; values "
                "are not clamped or filtered."
            ),
            "qdot_vector_order": ["shoulder", "elbow"],
            "pre_reach_qdot": (
                "For reached episodes, samples before first reach, including the "
                "reset sample; for no-reach episodes, all control samples from "
                "step 1 through episode end."
            ),
            "post_reach_qdot": (
                "Samples strictly after the first-reach sample; absent when no "
                "sample follows first reach."
            ),
            "peak_qdot_sample_selection": (
                "For each pre- and post-reach peak, select the sample with the "
                "largest Euclidean norm of its two-joint qdot vector. If multiple "
                "samples tie, select the earliest. The reported shoulder/elbow "
                "vector, norm and control step all come from that same sample."
            ),
            "acquisition_control_samples": (
                "Control samples from step 1 through first reach inclusive; if "
                "there is no reach, all control samples through episode end."
            ),
            "held_control_samples": (
                "All control samples whose environment held-step counter is positive; "
                "for interrupted failures this can include multiple hold attempts."
            ),
            "time_series_samples": (
                "Control-step means use reset through step 20 when present. "
                "Post-reach offset 0 is the first-reach sample; offsets 0–99 "
                "are at most 100 samples."
            ),
            "radial_bins_cm": [
                {
                    "label": label,
                    "lower_inclusive": lower,
                    "upper_inclusive" if index == len(RADIAL_BINS) - 1 else "upper_exclusive": upper,
                }
                for index, (label, lower, upper) in enumerate(RADIAL_BINS)
            ],
            "angular_sectors_degrees": [
                {
                    "label": label,
                    "lower_inclusive": lower,
                    "upper_exclusive": upper,
                }
                for label, lower, upper in ANGULAR_SECTORS
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and descriptively analyze the 200-episode M5 control-step "
            "trace artifact."
        )
    )
    parser.add_argument("--trace", type=Path, required=True, help="M5 trace JSON")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path")
    arguments = parser.parse_args(argv)
    try:
        trace_path = arguments.trace.expanduser().resolve(strict=True)
        output_path = arguments.output.expanduser().resolve()
        if not trace_path.is_file():
            raise EvidenceError(f"trace artifact is not a file: {trace_path}")
        if output_path == trace_path:
            raise EvidenceError("output path must not overwrite the trace artifact")
        if not output_path.parent.is_dir():
            raise EvidenceError(f"output directory does not exist: {output_path.parent}")
        if output_path.exists():
            raise EvidenceError(f"output file already exists: {output_path}")
        analysis = build_analysis(_load_json(trace_path))
        serialized = json.dumps(
            analysis, indent=2, ensure_ascii=False, allow_nan=False
        )
        output_path.write_text(serialized + "\n", encoding="utf-8")
    except (EvidenceError, OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
