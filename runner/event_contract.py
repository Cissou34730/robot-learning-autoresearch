"""Identity contract of the campaign event journal (schema version 2).

Every event names who owns it through explicit identity fields. A reader builds
its tree from those fields alone; it never infers an owner. This module is the
single statement of which identities each kind of event must carry.

Identity fields:

``session_id``
    The durable session key: ``S<n>`` for a scientific session, or
    ``PREPARATION_SESSION`` for the campaign preparation. Never a backend
    conversation id.
``operation_id``
    The operation (``T3``, ``M2``, ``E5``, or ``OFFICIAL_OPERATION``).
``inquiry_id``
    The inquiry. An inquiry spans sessions, so it never owns an operation by
    itself; the session does.
``attempt`` and ``actor``
    Which PI invocation and who spoke (pi, coder, reviewer, runner, launcher).
    They only keep rows from different invocations apart.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = 2
PREPARATION_SESSION = "preparation"
OFFICIAL_OPERATION = "official"

ENVELOPE_FIELDS = (
    "schema_version",
    "event_id",
    "campaign_id",
    "ts",
    "kind",
    "scope",
    "severity",
    "session_id",
    "operation_id",
    "inquiry_id",
    "attempt",
    "actor",
    "payload",
)


@dataclass(frozen=True)
class KindRule:
    """The identities one kind of event must carry, and where it belongs."""

    requires: tuple[str, ...] = ()
    owner: str = "campaign"  # campaign | session | operation


_SESSION = KindRule(requires=("session_id",), owner="session")
_INQUIRY = KindRule(requires=("session_id", "inquiry_id"), owner="session")
_OPERATION = KindRule(requires=("session_id", "operation_id"), owner="operation")
# Always shown in the Campaign group, whatever identities they also carry.
_CAMPAIGN = KindRule()
# Shown with the most specific owner they name, else in the Campaign group.
_NAMED_OWNER = KindRule(owner="session")

RULES: dict[str, KindRule] = {
    "campaign_started": _CAMPAIGN,
    "campaign_concluded": _CAMPAIGN,
    "campaign_usage": _CAMPAIGN,
    "run_state": _CAMPAIGN,
    "notice": _NAMED_OWNER,
    "warning": _NAMED_OWNER,
    "error": _NAMED_OWNER,
    "publication_retry": _NAMED_OWNER,
    "publication_recovered": _NAMED_OWNER,
    "campaign_goal_review": _NAMED_OWNER,
    # Session level.
    "session_start": _SESSION,
    "session_started": _SESSION,
    "session_ended": _SESSION,
    "checkpoint_saved": _SESSION,
    "scientific_model_validated": _SESSION,
    "pi_message": _SESSION,
    "pi_context": _SESSION,
    "tool_call_started": _SESSION,
    "tool_call_completed": _SESSION,
    "tool_call_failed": _SESSION,
    "tool_denied": _SESSION,
    "coding": _SESSION,
    "file_changed": _SESSION,
    "operation_submitted": _SESSION,
    "usage_update": _SESSION,
    "session_usage": _SESSION,
    "activity": _SESSION,
    "inquiry_opened": _INQUIRY,
    "inquiry_closed": _INQUIRY,
    "inquiry_reframed": _INQUIRY,
    # Operation level.
    "operation_requested": _OPERATION,
    "operation_started": _OPERATION,
    "operation_progress": _OPERATION,
    "operation_completed": _OPERATION,
    "operation_failed": _OPERATION,
    "training_progress": _OPERATION,
    "eval_progress": _OPERATION,
    "training_checkpoints": _OPERATION,
    "measurement_panel_started": _OPERATION,
    "measurement_panel_completed": _OPERATION,
    # Facts about models: they belong to the operation that produced them when
    # it is named, otherwise to the campaign.
    "candidate_created": KindRule(owner="operation"),
    "role_assigned": KindRule(owner="operation"),
}

_UNKNOWN = KindRule()


def rule_for(kind: str) -> KindRule:
    """An unknown kind has no requirement and belongs to the campaign."""
    return RULES.get(kind, _UNKNOWN)


def missing_identity(
    kind: str, *, session_id: str, operation_id: str, inquiry_id: str
) -> tuple[str, ...]:
    """The required identity fields an event does not carry.

    The official assessment is campaign-owned work: it has an operation but no
    scientific session.
    """
    present = {
        "session_id": session_id,
        "operation_id": operation_id,
        "inquiry_id": inquiry_id,
    }
    missing = [name for name in rule_for(kind).requires if not present[name]]
    if "session_id" in missing and operation_id == OFFICIAL_OPERATION:
        missing.remove("session_id")
    return tuple(missing)


def validate_record(record: object) -> list[str]:
    """Problems of one decoded journal line; an empty list means it is valid."""
    if not isinstance(record, dict):
        return ["the record is not an object"]
    problems = [
        f"missing envelope field {name}"
        for name in ENVELOPE_FIELDS
        if name not in record
    ]
    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version is not {SCHEMA_VERSION}")
    kind = record.get("kind")
    if not isinstance(kind, str) or not kind:
        problems.append("kind is empty")
        return problems
    if not isinstance(record.get("payload"), dict):
        problems.append("payload is not an object")
    missing = missing_identity(
        kind,
        session_id=str(record.get("session_id") or ""),
        operation_id=str(record.get("operation_id") or ""),
        inquiry_id=str(record.get("inquiry_id") or ""),
    )
    problems.extend(f"{kind} lacks {name}" for name in missing)
    return problems
