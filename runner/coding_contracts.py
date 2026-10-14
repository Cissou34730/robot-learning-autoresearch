"""Native coding models, inline prompts and agent profiles."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from typing import Literal
from pydantic import field_validator
from pydantic import model_validator
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
                    "required": ["allowed_paths", "verification_path"],
                    "properties": {
                        "allowed_paths": {"type": "array"},
                        "verification_path": {"type": "string"},
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
        default=None, min_length=1, max_length=64,
        description="Exact writable files for a new child; omit for a correction.",
    )
    read_paths: list[str] | None = Field(
        default=None, max_length=64,
        description="Additional readable files; omit to reuse correction scope.",
    )
    source_context: str = Field(default="", max_length=32_000)
    verification_path: str | None = Field(
        default=None, min_length=1,
        description="Scoped lab verification module; omit for a correction.",
    )
    session_handle: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_initial_scope(self) -> ScientificCodingParams:
        if not self.session_handle and (
            self.allowed_paths is None or self.verification_path is None
        ):
            raise ValueError(
                "A new coding call requires allowed_paths and verification_path. "
                "A correction requires the returned session_handle and intent."
            )
        return self


class CodingCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_args: list[str]
    artifact_filename: str
    check_description: str = Field(min_length=1)


class CodingReport(CodingCheck):
    summary: str
    unchecked_scope: list[str] = Field(min_length=1)
    compatibility_check: CodingCheck | None = None


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
            finding.finding_id for finding in self.findings
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


CODING_INSTRUCTIONS = """
You are a Python scientific-software engineer supporting the PI.

Implement the requested change within the authorized files. Read the relevant
sources first. Understand the supplied inputs, expected outputs and constraints.
Reuse existing code and preserve behavior the PI did not ask to change.

Use scientific_api_reference for unfamiliar library APIs.

Write a small verification module covering the changed behavior. For API or
runtime changes, include a small artifact-independent compatibility mode.
Do not claim that a mocked component has been checked against its real
implementation.

Do not execute code, install dependencies or submit operations. Runner handles
execution.

Report what changed, what the checks cover and what remains unchecked.
State that the checks have not been executed.

Return only a JSON object containing:
- summary: string
- check_args: list of module-argument strings
- artifact_filename: simple .json basename
- check_description: nonempty string
- unchecked_scope: nonempty list of strings
- compatibility_check: null, or an object containing check_args,
  artifact_filename and check_description with the same types

Use {artifact} for the output-path argument.
Use different artifact filenames for the two checks.
"""


REVIEW_INSTRUCTIONS = """
You are an independent Python scientific-code reviewer supporting the PI.

For an initial review, examine the requested behavior, actual changes and
proposed checks. Read relevant scoped files when needed. Check the coder's
claims against the source, contracts and installed APIs.
Find consequential implementation errors. Check affected boundary cases,
representations and mathematical or installed-API invariants.

Classify each finding as confirmed_defect, verification_gap or unresolved_question.
A confirmed defect requires an in-scope source path or permitted input that
violates a named requirement. State the expected behavior, actual behavior and
supporting source trace, counterexample or independent arithmetic.
A missing assertion is a verification gap, not proof of wrong production output.
A checker accepting a hypothetical malformed payload is a verification gap
unless the request requires rejection of that payload.
State uncertainty as an unresolved question. Do not invent physical requirements
from general assumptions. Use the robot contract and installed API definitions.
Do not report style issues, speculative improvements or unrelated pre-existing defects.

For a correction, retain this session's original task context. Review the supplied
correction intent and incremental diff. Check the repair and regressions caused
by it. Keep unresolved prior confirmed defects. Do not restart the initial
investigation or repeat unchanged verification gaps and questions.
Report what this correction review did not examine.
Retain each finding's ID when reassessing the same issue.

Report all findings from the pass together. Do not withhold known defects for
later rounds. Request changes for every confirmed defect in one batch.
Each request must identify its finding, the correction and exact authorized files.
The handler sends the complete batch to the same coder. You then review its repair.
Do not request repairs for hypothetical checker gaps or optional improvements.
Choose needs_pi for an unclear requirement, a change of scientific intent,
conflicting physical expectations or a repair you cannot resolve.
Do not repeat a failed repair request under a new finding ID.
Choose ready_for_pi when no confirmed defect remains. Report remaining gaps
and questions without declaring scientific approval.

Use scientific_api_reference for unfamiliar installed APIs.
Do not edit files, execute code, delegate, submit operations or choose research
direction. Request only engineering repairs within the original PI intent.
The PI retains scientific decisions and authorizes Runner checks.

Return only a JSON object containing:
- summary: string
- decision: request_changes, ready_for_pi or needs_pi
- decision_reason: nonempty string
- findings: list of objects containing finding_id, category, location, issue, requirement,
  expected_behavior, actual_behavior, evidence, consequence, confidence and
  check_coverage, all strings
- requested_changes: list of objects containing finding_id and instruction
  strings, and paths as a list of exact authorized file strings
- unchecked_scope: nonempty list of strings

An empty findings list means no confirmed defect found, not approval or proof
of correctness.
State that no code was executed and no files were changed.
"""


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
    def validate_envelope(cls, request: dict[str, object] | None) -> dict[str, object] | None:
        if request is not None:
            try:
                protocol.validate_operation_envelope(request)
            except TypeError as error:
                raise ValueError(str(error)) from error
        return request
