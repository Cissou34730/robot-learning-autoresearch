"""One canonical, lineage-aware representation of checkpoint time and identity.

A trained policy is a point on a lineage, not a bare step counter. Every
candidate therefore exposes one coordinate:

- ``identifier``: an immutable experiment-scoped identity such as
  ``experiment-2/delta-100352``;
- ``run_steps``: the steps executed in the current experiment;
- ``parent_accumulated_steps``: the accumulated steps of the parent lineage;
- ``accumulated_steps``: ``parent_accumulated_steps + run_steps`` for a
  transfer and ``run_steps`` alone for fresh training;
- ``parent_lineage``: the parent lineage identity;
- ``parent_fingerprint``: the parent artifact fingerprint.

Records written before this representation existed are read through
``coordinates_from_record``, the explicit legacy translation layer. It
prefers explicit coordinate fields and otherwise derives them from the older
``timesteps``/``training_steps`` naming without rewriting the record.
"""

from __future__ import annotations

# The fields that make up one canonical checkpoint coordinate.
COORDINATE_FIELDS = (
    "identifier",
    "run_steps",
    "parent_accumulated_steps",
    "accumulated_steps",
    "parent_lineage",
    "parent_fingerprint",
)


def canonical_identifier(experiment: int, run_steps: int) -> str:
    """The immutable experiment-scoped identity of one checkpoint."""
    return f"experiment-{int(experiment)}/delta-{int(run_steps)}"


def canonical_coordinates(
    experiment: int | None,
    run_steps: int,
    *,
    parent_accumulated_steps: int = 0,
    parent_lineage: str = "",
    parent_fingerprint: str | None = None,
) -> dict:
    """Build the coordinate of a checkpoint from its own lineage facts."""
    run = int(run_steps)
    parent = int(parent_accumulated_steps or 0)
    return {
        "identifier": (
            canonical_identifier(experiment, run) if experiment is not None else None
        ),
        "run_steps": run,
        "parent_accumulated_steps": parent,
        "accumulated_steps": parent + run,
        "parent_lineage": str(parent_lineage or ""),
        "parent_fingerprint": parent_fingerprint,
    }


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _as_positive_int(value: object) -> int | None:
    resolved = _as_int(value)
    if resolved is None or resolved < 0:
        return None
    return resolved


def _legacy_parent_lineage(record: dict) -> str:
    """The parent identity an older record already carries, if any."""
    explicit = record.get("parent_lineage")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    parent = record.get("training_parent_lineage")
    if isinstance(parent, dict):
        candidate = str(parent.get("candidate") or "").strip()
        if candidate:
            origin = parent.get("origin_experiment")
            if isinstance(origin, int) and not isinstance(origin, bool):
                return f"{candidate}@{origin}"
            return candidate
        identifier = str(parent.get("identifier") or "").strip()
        if identifier:
            return identifier
    for key in ("training_parent", "parent"):
        value = record.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "fresh":
            return value.strip()
    return ""


def _legacy_parent_fingerprint(record: dict) -> str | None:
    explicit = record.get("parent_fingerprint")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    parent = record.get("training_parent_lineage")
    if isinstance(parent, dict):
        fingerprint = parent.get("fingerprint")
        if isinstance(fingerprint, str) and fingerprint.strip():
            return fingerprint.strip()
    fallback = record.get("training_parent_fingerprint")
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def coordinates_from_record(
    record: dict,
    *,
    experiment: int | None = None,
    run_steps: int | None = None,
    parent_accumulated_steps: int | None = None,
    parent_lineage: str | None = None,
    parent_fingerprint: str | None = None,
) -> dict:
    """The canonical coordinates of a record, translating legacy fields.

    Explicit arguments win, then explicit coordinate fields, then the legacy
    translation layer. Unknown values stay ``None`` so a legacy record is never
    silently rewritten with a guessed lineage.
    """
    if not isinstance(record, dict):
        record = {}

    resolved_experiment = experiment
    if resolved_experiment is None:
        resolved_experiment = record.get("origin_experiment")
    if resolved_experiment is None:
        resolved_experiment = record.get("experiment")
    resolved_experiment = _as_int(resolved_experiment)

    resolved_run = run_steps
    if resolved_run is None:
        resolved_run = record.get("run_steps")
    if resolved_run is None:
        resolved_run = record.get("timesteps")
    resolved_run = _as_positive_int(resolved_run)

    resolved_parent = parent_accumulated_steps
    if resolved_parent is None:
        resolved_parent = record.get("parent_accumulated_steps")
    if resolved_parent is None:
        resolved_parent = record.get("parent_training_steps")
    resolved_parent = _as_positive_int(resolved_parent)

    resolved_accumulated = record.get("accumulated_steps")
    resolved_accumulated = _as_positive_int(resolved_accumulated)
    if resolved_accumulated is None:
        resolved_accumulated = _as_positive_int(record.get("training_steps"))
    if resolved_accumulated is None and resolved_run is not None:
        resolved_accumulated = (resolved_parent or 0) + resolved_run
    if (
        resolved_parent is None
        and resolved_run is not None
        and resolved_accumulated is not None
        and resolved_accumulated >= resolved_run
    ):
        resolved_parent = resolved_accumulated - resolved_run

    identifier = record.get("identifier")
    if not (isinstance(identifier, str) and identifier.strip()):
        identifier = None
        if resolved_experiment is not None and resolved_run is not None:
            identifier = canonical_identifier(resolved_experiment, resolved_run)

    resolved_parent_lineage = parent_lineage
    if resolved_parent_lineage is None:
        resolved_parent_lineage = _legacy_parent_lineage(record)

    resolved_parent_fingerprint = parent_fingerprint
    if resolved_parent_fingerprint is None:
        resolved_parent_fingerprint = _legacy_parent_fingerprint(record)

    return {
        "identifier": identifier,
        "run_steps": resolved_run,
        "parent_accumulated_steps": resolved_parent,
        "accumulated_steps": resolved_accumulated,
        "parent_lineage": resolved_parent_lineage,
        "parent_fingerprint": resolved_parent_fingerprint,
    }
