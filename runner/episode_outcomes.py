"""Per-episode outcomes of recorded measurements: success by stratum and paired counts."""

from __future__ import annotations

import json
import math
from contextlib import ExitStack
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from benchmark.paired_evidence import paired_comparison
from runner.json_artifact_view import JsonArray, scalar_value
from runner.proportion_interval import (
    RecordedReference,
    recorded_measurement,
    wilson_interval,
)


class Strata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: str = Field(
        default="/episode_results",
        description="JSON Pointer to per-episode rows that carry episode_seed.",
    )
    field: str = Field(min_length=1, description="Numeric field of those rows.")
    edges: list[float] = Field(
        min_length=2,
        max_length=21,
        description="Increasing bin edges; the last bin includes its upper edge.",
    )

    @model_validator(mode="after")
    def validate_edges(self) -> Strata:
        if not all(math.isfinite(edge) for edge in self.edges) or any(
            upper <= lower for lower, upper in zip(self.edges, self.edges[1:])
        ):
            raise ValueError("edges must be finite and strictly increasing")
        return self


class EpisodeOutcomeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurements: list[RecordedReference] = Field(
        min_length=1,
        max_length=2,
        description="One recorded measurement, or two of the same episodes to pair.",
    )
    strata: Strata | None = None
    confidence: float = Field(
        ge=0.5, le=0.999, description="Two-sided interval level that you choose."
    )


def _pointer_value(document: Any, pointer: str) -> Any:
    from runner.artifact_evidence_query import _tokens

    value = document
    for token in _tokens(pointer):
        value = (
            value[int(token)] if isinstance(value, (list, JsonArray)) else value[token]
        )
    return value


def _number(value: Any) -> float | None:
    value = scalar_value(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _load(state: dict, reference: RecordedReference, resources: ExitStack) -> dict:
    from runner import repository
    from runner.artifact_evidence_query import (
        _artifact_catalog,
        _artifact_value,
        _recorded_artifact,
    )

    event, item = recorded_measurement(state, reference)
    metrics = item["metrics"]
    recorded_path = repository.canonical_repo_path(metrics["evaluation_artifact"])
    index = next(
        position
        for position, entry in enumerate(_artifact_catalog(event))
        if repository.canonical_repo_path(entry["artifact_path"]) == recorded_path
    )
    path, provenance = _recorded_artifact(
        state, repository.current_campaign_id(state), event["id"], index
    )
    document = _artifact_value(path, provenance, resources)
    outcomes: dict[int, bool] = {}
    for row in document["episode_results"]:
        seed = int(scalar_value(row["episode_seed"]))
        if seed in outcomes:
            raise ValueError(f"{event['id']}: episode seed {seed} appears twice")
        outcomes[seed] = bool(scalar_value(row["success"]))
    successes = sum(outcomes.values())
    recorded_successes = metrics.get("successes")
    if len(outcomes) != int(metrics["episodes"]) or (
        recorded_successes is not None and int(recorded_successes) != successes
    ):
        raise ValueError(f"{event['id']}: episode results differ from the record")
    if item["instrument"] == "task_reference":
        panel = f"{metrics.get('panel')}:{metrics.get('panel_version')}"
    else:
        panel = str(metrics.get("evaluation_semantics") or "")
    return {
        "source": {
            "operation_id": event["id"],
            "candidate": item["candidate"],
            "instrument": item["instrument"],
            "label": item.get("label"),
        },
        "identity": f"{item['instrument']}:{panel}",
        "outcomes": outcomes,
        "document": document,
    }


def _rate(outcomes: dict[int, bool], seeds: list[int], confidence: float) -> dict:
    if not seeds:
        return {"successes": 0, "trials": 0}
    successes = sum(outcomes[seed] for seed in seeds)
    return {
        "successes": successes,
        "trials": len(seeds),
        **wilson_interval(successes, len(seeds), confidence),
    }


def sign_test_p_value(first: int, second: int) -> float:
    """Exact two-sided sign test over discordant episodes."""
    discordant = first + second
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, value) for value in range(min(first, second) + 1))
    return min(1.0, 2 * tail / 2**discordant)


def _paired(loaded: list[dict], seeds: list[int], confidence: float) -> dict:
    if not seeds:
        return {"episodes": 0}
    first, second = (
        [
            {
                "episodes": len(seeds),
                "evaluation_semantics": item["identity"],
                "episode_results": [
                    {"episode_seed": seed, "success": item["outcomes"][seed]}
                    for seed in seeds
                ],
            }
        ]
        for item in loaded
    )
    counts = paired_comparison(first, second)
    first_only, second_only = counts["candidate_wins"], counts["reference_wins"]
    both_success = sum(loaded[0]["outcomes"][seed] for seed in seeds) - first_only
    result = {
        "episodes": counts["episodes"],
        "both_success": both_success,
        "first_only_success": first_only,
        "second_only_success": second_only,
        "both_failure": counts["episodes"] - both_success - first_only - second_only,
        "net_first_minus_second": counts["net_wins"],
        "sign_test_p_value": sign_test_p_value(first_only, second_only),
    }
    if counts["discordant_episodes"]:
        result["first_share_of_discordant"] = wilson_interval(
            first_only, counts["discordant_episodes"], confidence
        )
    return result


def _bin_label(edges: list[float], index: int) -> str:
    closing = "]" if index == len(edges) - 2 else ")"
    return f"[{edges[index]:g}, {edges[index + 1]:g}{closing}"


def _strata(
    loaded: list[dict], strata: Strata, seeds: list[int], confidence: float
) -> dict:
    values: dict[int, float] = {}
    fields: set[str] = set()
    for row in _pointer_value(loaded[0]["document"], strata.rows):
        fields.update(row)
        value = _number(row.get(strata.field))
        if value is not None:
            values[int(scalar_value(row["episode_seed"]))] = value
    if not values:
        raise KeyError(
            f"numeric {strata.field!r} in rows at {strata.rows}; "
            f"row fields: {sorted(fields)}"
        )
    edges = strata.edges
    groups: list[list[int]] = [[] for _ in edges[:-1]]
    outside = without_value = 0
    for seed in seeds:
        value = values.get(seed)
        if value is None:
            without_value += 1
            continue
        if value < edges[0] or value > edges[-1]:
            outside += 1
            continue
        index = next(
            position
            for position in range(len(groups))
            if value < edges[position + 1] or position == len(groups) - 1
        )
        groups[index].append(seed)
    bins = []
    for index, group in enumerate(groups):
        entry: dict[str, Any] = {
            "bin": _bin_label(edges, index),
            "episodes": len(group),
            "measurements": [
                _rate(item["outcomes"], group, confidence) for item in loaded
            ],
        }
        if len(loaded) == 2:
            entry["paired"] = _paired(loaded, group, confidence)
        bins.append(entry)
    return {
        "values_from": {
            **loaded[0]["source"],
            "rows": strata.rows,
            "field": strata.field,
        },
        "bins": bins,
        "episodes_outside_edges": outside,
        "episodes_without_value": without_value,
    }


def query_episode_outcomes(args: dict[str, Any], campaign_id: str = "") -> str:
    """Native custom-tool handler over recorded, fingerprint-verified artifacts."""
    from runner import repository
    from runner.artifact_evidence_query import (
        ArtifactUnavailableError,
        FingerprintMismatchError,
    )

    try:
        params = EpisodeOutcomeParams.model_validate(args)
        state = repository.load_state(allow_missing_artifact=True)
        if not campaign_id or repository.current_campaign_id(state) != campaign_id:
            raise ValueError("tool campaign does not match the active Runner state")
        with ExitStack() as resources:
            loaded = [
                _load(state, reference, resources) for reference in params.measurements
            ]
            seeds = sorted(loaded[0]["outcomes"])
            if len(loaded) == 2 and (
                loaded[0]["identity"] != loaded[1]["identity"]
                or loaded[0]["outcomes"].keys() != loaded[1]["outcomes"].keys()
            ):
                raise ValueError(
                    "the two measurements do not cover the same episodes under the "
                    "same instrument and evaluation semantics"
                )
            result: dict[str, Any] = {
                "status": "computed",
                "confidence": params.confidence,
                "measurements": [
                    {
                        **item["source"],
                        **_rate(item["outcomes"], seeds, params.confidence),
                    }
                    for item in loaded
                ],
            }
            if len(loaded) == 2:
                result["paired"] = _paired(loaded, seeds, params.confidence)
            if params.strata:
                result["strata"] = _strata(
                    loaded, params.strata, seeds, params.confidence
                )
    except ArtifactUnavailableError as error:
        return json.dumps({"status": "artifact_unavailable", "error": error.reason})
    except FingerprintMismatchError as error:
        return json.dumps({"status": "fingerprint_mismatch", "error": str(error)})
    except (KeyError, IndexError) as error:
        return json.dumps(
            {"status": "field_absent", "error": f"artifact has no {error.args[0]}"}
        )
    except (AttributeError, OSError, TypeError, ValueError) as error:
        return json.dumps({"status": "invalid_request", "error": str(error)})
    result["assumptions"] = [
        "intervals treat episodes as independent with one success probability per group",
        "the sign test uses only episodes where exactly one measurement succeeded",
        "edges chosen after seeing outcomes make stratum differences optimistic",
    ]
    return json.dumps(result, ensure_ascii=False)
