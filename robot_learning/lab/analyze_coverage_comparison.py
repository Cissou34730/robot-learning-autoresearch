"""Compare paired research-evaluation outcomes by target geometry.

The input format is the research-evaluation artifact produced by
``robot_learning.scenario.evaluation``. Reach timing is reported only in
control steps; this analysis makes no within-step occupancy inference.
"""

import argparse
import json
import math
from pathlib import Path


PANEL_SIZE = 200
MAX_EPISODE_STEPS = 500
REQUIRED_HOLD_STEPS = 100
RADIAL_BINS = (
    ("6–<10 cm", 6.0, 10.0),
    ("10–<14 cm", 10.0, 14.0),
    ("14–<18 cm", 14.0, 18.0),
    ("18–20 cm", 18.0, 20.0),
)
ANGULAR_SECTORS = tuple(
    (
        f"[{lower},{lower + 45})°",
        float(lower),
        float(lower + 45),
    )
    for lower in range(-180, 180, 45)
)


class EvidenceError(ValueError):
    """Raised when an input artifact is incomplete or internally inconsistent."""


def _unique_object(pairs):
    """Reject duplicate keys instead of silently accepting the last value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value):
    raise EvidenceError(f"non-finite JSON constant is not allowed: {value}")


def _load_json(path, label):
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(
                source,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_nonstandard_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, EvidenceError) as exc:
        raise EvidenceError(f"cannot read {label} artifact {path}: {exc}") from exc


def _required(record, field, location):
    if not isinstance(record, dict):
        raise EvidenceError(f"{location} must be a JSON object")
    if field not in record:
        raise EvidenceError(f"{location} is missing required field {field!r}")
    return record[field]


def _integer(value, location, minimum, maximum=None):
    if type(value) is not int:
        raise EvidenceError(f"{location} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"at least {minimum}"
        if maximum is not None:
            bounds += f" and at most {maximum}"
        raise EvidenceError(f"{location} must be {bounds}; got {value}")
    return value


def _number(value, location):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{location} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise EvidenceError(f"{location} must be a finite number")
    return number


def _bounded_radius(value, location):
    radius = _number(value, location)
    # Target coordinates are converted through floating-point trigonometry;
    # tolerate only negligible rounding at the declared 6 cm and 20 cm limits.
    tolerance = 1e-9
    if radius < 6.0 and math.isclose(radius, 6.0, rel_tol=0.0, abs_tol=tolerance):
        return 6.0
    if radius > 20.0 and math.isclose(radius, 20.0, rel_tol=0.0, abs_tol=tolerance):
        return 20.0
    if not 6.0 <= radius <= 20.0:
        raise EvidenceError(f"{location} must be between 6 and 20 cm; got {radius}")
    return radius


def _bounded_angle(value, location):
    angle = _number(value, location)
    tolerance = 1e-9
    if angle < -180.0 and math.isclose(
        angle, -180.0, rel_tol=0.0, abs_tol=tolerance
    ):
        return -180.0
    if angle > 180.0 and math.isclose(
        angle, 180.0, rel_tol=0.0, abs_tol=tolerance
    ):
        return 180.0
    if not -180.0 <= angle <= 180.0:
        raise EvidenceError(
            f"{location} must be between -180 and 180 degrees; got {angle}"
        )
    return angle


def _read_evaluation(path, label):
    artifact = _load_json(path, label)
    if not isinstance(artifact, dict):
        raise EvidenceError(f"{label} artifact root must be a JSON object")
    if _required(artifact, "official_benchmark", label) is not False:
        raise EvidenceError(f"{label} artifact is not identified as a research evaluation")
    if _integer(
        _required(artifact, "episodes", label), f"{label} /episodes", 0
    ) != PANEL_SIZE:
        raise EvidenceError(
            f"{label} artifact must declare exactly {PANEL_SIZE} episodes"
        )

    episode_results = _required(artifact, "episode_results", label)
    diagnostics_root = _required(artifact, "research_evidence", label)
    diagnostics = _required(
        diagnostics_root, "episode_diagnostics", f"{label} /research_evidence"
    )
    if not isinstance(episode_results, list):
        raise EvidenceError(f"{label} /episode_results must be an array")
    if not isinstance(diagnostics, list):
        raise EvidenceError(
            f"{label} /research_evidence/episode_diagnostics must be an array"
        )
    if len(episode_results) != PANEL_SIZE:
        raise EvidenceError(
            f"{label} /episode_results must contain exactly {PANEL_SIZE} rows; "
            f"found {len(episode_results)}"
        )
    if len(diagnostics) != PANEL_SIZE:
        raise EvidenceError(
            f"{label} /research_evidence/episode_diagnostics must contain exactly "
            f"{PANEL_SIZE} rows; found {len(diagnostics)}"
        )

    outcomes = {}
    for index, episode in enumerate(episode_results):
        location = f"{label} /episode_results/{index}"
        seed = _integer(
            _required(episode, "episode_seed", location),
            f"{location}/episode_seed",
            0,
        )
        if seed in outcomes:
            raise EvidenceError(
                f"{label} has duplicate episode seed {seed} in /episode_results"
            )
        success = _required(episode, "success", location)
        if type(success) is not bool:
            raise EvidenceError(f"{location}/success must be a boolean")
        outcomes[seed] = {"success": success}

    diagnostic_by_seed = {}
    for index, diagnostic in enumerate(diagnostics):
        location = f"{label} /research_evidence/episode_diagnostics/{index}"
        seed = _integer(
            _required(diagnostic, "episode_seed", location),
            f"{location}/episode_seed",
            0,
        )
        if seed in diagnostic_by_seed:
            raise EvidenceError(
                f"{label} has duplicate diagnostic for episode seed {seed}"
            )

        radius_raw = _number(
            _required(diagnostic, "target_radius_cm", location),
            f"{location}/target_radius_cm",
        )
        radius = _bounded_radius(radius_raw, f"{location}/target_radius_cm")
        angle_raw = _number(
            _required(diagnostic, "target_angle_degrees", location),
            f"{location}/target_angle_degrees",
        )
        angle = _bounded_angle(angle_raw, f"{location}/target_angle_degrees")

        first_reach = _required(diagnostic, "first_reach_step", location)
        if first_reach is not None:
            first_reach = _integer(
                first_reach,
                f"{location}/first_reach_step",
                1,
                MAX_EPISODE_STEPS,
            )
        max_held = _integer(
            _required(diagnostic, "max_held_steps", location),
            f"{location}/max_held_steps",
            0,
            MAX_EPISODE_STEPS,
        )
        interruptions = _integer(
            _required(diagnostic, "hold_interruptions", location),
            f"{location}/hold_interruptions",
            0,
            MAX_EPISODE_STEPS,
        )
        if first_reach is None and (max_held != 0 or interruptions != 0):
            raise EvidenceError(
                f"{location} has hold diagnostics but no first reach step"
            )
        if first_reach is not None and max_held == 0:
            raise EvidenceError(
                f"{location} has a first reach step but zero maximum held steps"
            )

        diagnostic_by_seed[seed] = {
            "target_radius_cm": radius,
            "target_radius_source": radius_raw,
            "target_angle_degrees": angle,
            "target_angle_source": angle_raw,
            "first_reach_step": first_reach,
            "max_held_steps": max_held,
            "hold_interruptions": interruptions,
        }

    if outcomes.keys() != diagnostic_by_seed.keys():
        missing = sorted(outcomes.keys() - diagnostic_by_seed.keys())
        unmatched = sorted(diagnostic_by_seed.keys() - outcomes.keys())
        raise EvidenceError(
            f"{label} episode/diagnostic seeds do not match; "
            f"missing diagnostics for {missing}, unmatched diagnostics for {unmatched}"
        )

    rows = {}
    for seed, outcome in outcomes.items():
        diagnostic = diagnostic_by_seed[seed]
        hold_completed = diagnostic["max_held_steps"] >= REQUIRED_HOLD_STEPS
        if outcome["success"] != hold_completed:
            raise EvidenceError(
                f"{label} episode seed {seed} has success={outcome['success']!r}, "
                f"but max_held_steps={diagnostic['max_held_steps']} "
                f"(required hold: {REQUIRED_HOLD_STEPS} consecutive steps)"
            )
        rows[seed] = {**outcome, **diagnostic}
    return rows


def _radial_label(radius):
    for label, lower, upper in RADIAL_BINS[:-1]:
        if lower <= radius < upper:
            return label
    # The final band includes its 20 cm upper endpoint.
    if RADIAL_BINS[-1][1] <= radius <= RADIAL_BINS[-1][2]:
        return RADIAL_BINS[-1][0]
    raise EvidenceError(f"target radius {radius} cm is outside the radial bins")


def _angular_label(angle):
    # atan2 may represent the negative x-axis as +180 degrees. The requested
    # sectors are half-open over [-180, 180), so use its equivalent -180 value.
    normalized = -180.0 if angle == 180.0 else angle
    for label, lower, upper in ANGULAR_SECTORS:
        if lower <= normalized < upper:
            return label
    raise EvidenceError(f"target angle {angle} degrees is outside the angular sectors")


def _mean(values):
    return sum(values) / len(values) if values else None


def _summarize(rows):
    episode_count = len(rows)
    successes = sum(row["success"] for row in rows)
    failures = episode_count - successes
    no_reach_failures = sum(
        not row["success"] and row["first_reach_step"] is None for row in rows
    )
    post_reach_failures = failures - no_reach_failures
    reached = [row for row in rows if row["first_reach_step"] is not None]
    return {
        "episode_count": episode_count,
        "successes": successes,
        "failures": failures,
        "success_percent": 100.0 * successes / episode_count if episode_count else None,
        "no_reach_failures": no_reach_failures,
        "post_reach_failures": post_reach_failures,
        "reached_episode_count": len(reached),
        "mean_first_reach_step": _mean(
            [row["first_reach_step"] for row in reached]
        ),
        "mean_max_held_steps": _mean([row["max_held_steps"] for row in rows]),
        "mean_hold_interruptions": _mean(
            [row["hold_interruptions"] for row in rows]
        ),
    }


def _group_rows(rows, labels, label_for):
    groups = {label: [] for label in labels}
    for row in rows:
        groups[label_for(row)].append(row)
    return {label: _summarize(groups[label]) for label in labels}


def _summarize_candidate(rows):
    row_list = list(rows.values())
    return {
        "overall": _summarize(row_list),
        "radial_bins": _group_rows(
            row_list,
            [item[0] for item in RADIAL_BINS],
            lambda row: _radial_label(row["target_radius_cm"]),
        ),
        "angular_sectors": _group_rows(
            row_list,
            [item[0] for item in ANGULAR_SECTORS],
            lambda row: _angular_label(row["target_angle_degrees"]),
        ),
    }


def _paired_summary(candidate_rows, reference_rows):
    pairs = []
    for seed in sorted(candidate_rows):
        candidate = candidate_rows[seed]
        reference = reference_rows[seed]
        candidate_success = candidate["success"]
        reference_success = reference["success"]
        pairs.append(
            {
                "candidate_win": candidate_success and not reference_success,
                "reference_win": reference_success and not candidate_success,
                "target_radius_cm": candidate["target_radius_cm"],
                "target_angle_degrees": candidate["target_angle_degrees"],
            }
        )

    def count_pairs(selected):
        return {
            "episode_count": len(selected),
            "candidate_wins": sum(row["candidate_win"] for row in selected),
            "reference_wins": sum(row["reference_win"] for row in selected),
            "ties": sum(
                not row["candidate_win"] and not row["reference_win"]
                for row in selected
            ),
        }

    radial = {item[0]: [] for item in RADIAL_BINS}
    angular = {item[0]: [] for item in ANGULAR_SECTORS}
    for row in pairs:
        radial[_radial_label(row["target_radius_cm"])].append(row)
        angular[_angular_label(row["target_angle_degrees"])].append(row)
    return {
        "overall": count_pairs(pairs),
        "radial_bins": {label: count_pairs(rows) for label, rows in radial.items()},
        "angular_sectors": {
            label: count_pairs(rows) for label, rows in angular.items()
        },
    }


def build_comparison(candidate_rows, reference_rows):
    """Validate pairing and construct all overall and geometry-stratified summaries."""
    if candidate_rows.keys() != reference_rows.keys():
        missing_reference = sorted(candidate_rows.keys() - reference_rows.keys())
        missing_candidate = sorted(reference_rows.keys() - candidate_rows.keys())
        raise EvidenceError(
            "candidate and reference episode seeds do not match; "
            f"missing from reference: {missing_reference}, "
            f"missing from candidate: {missing_candidate}"
        )
    if len(candidate_rows) != PANEL_SIZE:
        raise EvidenceError(
            f"paired comparison requires exactly {PANEL_SIZE} distinct episode seeds"
        )

    for seed in sorted(candidate_rows):
        candidate = candidate_rows[seed]
        reference = reference_rows[seed]
        if (
            candidate["target_radius_source"] != reference["target_radius_source"]
            or candidate["target_angle_source"] != reference["target_angle_source"]
        ):
            raise EvidenceError(
                f"candidate and reference targets differ for episode seed {seed}"
            )

    return {
        "schema_version": 1,
        "episode_count": PANEL_SIZE,
        "candidate": _summarize_candidate(candidate_rows),
        "reference": _summarize_candidate(reference_rows),
        "paired": _paired_summary(candidate_rows, reference_rows),
        "interpretation": {
            "no_reach_failure": "A failed episode with no recorded first_reach_step.",
            "post_reach_failure": (
                "A failed episode with a recorded first_reach_step."
            ),
            "reach_timing": (
                "Diagnostics are measured in control steps; no within-step "
                "occupancy is inferred."
            ),
            "radial_bins_cm": [
                {"label": "6–<10 cm", "lower_inclusive": 6, "upper_exclusive": 10},
                {
                    "label": "10–<14 cm",
                    "lower_inclusive": 10,
                    "upper_exclusive": 14,
                },
                {
                    "label": "14–<18 cm",
                    "lower_inclusive": 14,
                    "upper_exclusive": 18,
                },
                {
                    "label": "18–20 cm",
                    "lower_inclusive": 18,
                    "upper_inclusive": 20,
                },
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


def _parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Compare two paired 200-episode research evaluations by target "
            "radius and angle."
        )
    )
    parser.add_argument("--candidate", required=True, help="candidate JSON artifact")
    parser.add_argument("--reference", required=True, help="reference JSON artifact")
    parser.add_argument("--output", required=True, help="comparison JSON output path")
    return parser, parser.parse_args(argv)


def main(argv=None):
    parser, arguments = _parse_arguments(argv)
    candidate_path = Path(arguments.candidate)
    reference_path = Path(arguments.reference)
    output_path = Path(arguments.output)
    try:
        resolved_output = output_path.resolve()
        if resolved_output in {candidate_path.resolve(), reference_path.resolve()}:
            raise EvidenceError("output path must not overwrite either input artifact")
        candidate_rows = _read_evaluation(candidate_path, "candidate")
        reference_rows = _read_evaluation(reference_path, "reference")
        comparison = build_comparison(candidate_rows, reference_rows)
        serialized = json.dumps(
            comparison, indent=2, ensure_ascii=False, allow_nan=False
        )
        output_path.write_text(serialized + "\n", encoding="utf-8")
    except (EvidenceError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
