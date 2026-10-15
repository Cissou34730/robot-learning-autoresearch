"""Native coding models, prompt loading and agent profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runner import protocol

# The preliminary analyst retains its existing publication/tool contract.
RESEARCH_TOOLS = [
    "view",
    "rg",
    "glob",
    "apply_patch",
    "powershell",
    "read_powershell",
    "stop_powershell",
    "list_powershell",
]


MAIN_PI_TOOLS = ["view", "rg", "glob"]


CODING_TOOLS = ["view", "apply_patch", "scientific_api_reference"]


REVIEW_TOOLS = ["view", "scientific_api_reference"]


REVIEW_MODEL = "gpt-6-luna"


REVIEW_REASONING = "max"


def normalize_model(model: str) -> str:
    """OpenCode named the provider inside the model; the SDK names only the model."""
    return model.split("/", 1)[1] if "/" in model else model


class ScientificCodingParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "anyOf": [
                {
                    "required": ["allowed_paths"],
                    "properties": {
                        "allowed_paths": {"type": "array"},
                        "session_handle": {"type": "null"},
                    },
                },
                {
                    "required": ["session_handle"],
                    "properties": {"session_handle": {"type": "string"}},
                },
            ]
        },
    )

    intent: str = Field(min_length=1, max_length=16_000)
    allowed_paths: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Exact writable files for a new child; omit for a correction.",
    )
    read_paths: list[str] | None = Field(
        default=None,
        max_length=64,
        description="Additional readable files; omit to reuse correction scope.",
    )
    source_context: str = Field(
        default="",
        max_length=32_000,
        description=(
            "Task-specific facts, concrete input/output requirements, caller context "
            "and observed errors. The child does not receive the PI conversation. "
            "Current scenario, authority and operation-contract excerpts are supplied "
            "by the harness; select additional source files in read_paths."
        ),
    )
    session_handle: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_initial_scope(self) -> ScientificCodingParams:
        if not self.session_handle and self.allowed_paths is None:
            raise ValueError(
                "A new coding call requires allowed_paths. "
                "A correction requires the returned session_handle and intent."
            )
        return self


class CodingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    unchecked_scope: list[str] = Field(min_length=1)


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1)
    category: Literal["confirmed_defect", "verification_gap", "unresolved_question"]
    location: str = Field(min_length=1)
    issue: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    expected_behavior: str = Field(min_length=1)
    actual_behavior: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    consequence: str = Field(min_length=1)
    confidence: str = Field(min_length=1)
    check_coverage: str = Field(min_length=1)


class ReviewChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    paths: list[str] = Field(min_length=1)


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    decision: Literal["request_changes", "ready_for_pi", "needs_pi"]
    decision_reason: str = Field(min_length=1)
    findings: list[ReviewFinding]
    requested_changes: list[ReviewChange]
    unchecked_scope: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def require_complete_batch(self) -> ReviewReport:
        identifiers = [finding.finding_id for finding in self.findings]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Review finding IDs must be unique.")
        requested = [change.finding_id for change in self.requested_changes]
        if len(requested) != len(set(requested)):
            raise ValueError("Repair requests must have unique finding IDs.")
        defects = {
            finding.finding_id
            for finding in self.findings
            if finding.category == "confirmed_defect"
        }
        if self.decision == "request_changes":
            if not defects or set(requested) != defects:
                raise ValueError(
                    "A repair batch must cover all confirmed defects, "
                    "and must not include gaps or unresolved questions."
                )
        elif requested:
            raise ValueError("Only request_changes may contain repair requests.")
        if self.decision == "ready_for_pi" and defects:
            raise ValueError("Confirmed defects require repairs or a needs_pi handoff.")
        return self


_PROMPT_DIRECTORY = Path(__file__).resolve().parent
CODING_INSTRUCTIONS = (_PROMPT_DIRECTORY / "scientific-coder.md").read_text(
    encoding="utf-8"
)
REVIEW_INSTRUCTIONS = (_PROMPT_DIRECTORY / "scientific-reviewer.md").read_text(
    encoding="utf-8"
)


class OperationSubmissionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, object] | None = Field(
        description=(
            "One existing contracts/instruments.md operation envelope. "
            "Use null only to reaccept a failed pending operation after repair."
        ),
        json_schema_extra={
            "anyOf": [protocol.operation_envelope_schema(), {"type": "null"}],
        },
    )

    @field_validator("request")
    @classmethod
    def validate_envelope(
        cls, request: dict[str, object] | None
    ) -> dict[str, object] | None:
        if request is not None:
            try:
                protocol.validate_operation_submission(request)
            except TypeError as error:
                raise ValueError(str(error)) from error
        return request
