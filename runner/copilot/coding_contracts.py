"""Native coding models, prompt loading and agent profiles."""

from __future__ import annotations

from pathlib import Path

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


REVIEW_REASONING = "high"


def normalize_model(model: str) -> str:
    """Keep external routing; only Copilot's own provider prefix is redundant."""
    return model.removeprefix("github-copilot/")


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

    intent: str = Field(
        min_length=1,
        max_length=16_000,
        description=(
            "State the expected output precisely. "
            "The coder chooses how to implement it."
        ),
    )
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
            "Supporting facts, caller context and observed errors. "
            "The child does not receive the PI conversation. "
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


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation: bool = Field(strict=True)
    what_is_wrong: str
    why: str
    where: str

    @model_validator(mode="after")
    def require_failed_review_details(self) -> ReviewReport:
        if not self.validation and not all(
            value.strip() for value in (self.what_is_wrong, self.why, self.where)
        ):
            raise ValueError("A failed review must state what is wrong, why and where.")
        return self


_PROMPT_DIRECTORY = Path(__file__).resolve().parent
CODING_INSTRUCTIONS = (_PROMPT_DIRECTORY / "scientific-coder.md").read_text(
    encoding="utf-8"
)
REVIEW_INSTRUCTIONS = (_PROMPT_DIRECTORY / "scientific-reviewer.md").read_text(
    encoding="utf-8"
)

CODING_TOOL_DESCRIPTION = (
    "Use scientific_coding for scientific source changes.\n\n"
    "In intent, state the expected output precisely. "
    "The coder chooses how to implement it, not what the output means.\n\n"
    "Select exact writable files in allowed_paths and additional "
    "readable source and caller files in read_paths.\n\n"
    "Put supporting facts, caller context and observed errors "
    "in source_context. The child "
    "does not receive your conversation. The harness supplies current "
    "scenario, authority and operation-contract text to both authors "
    "and reviewers, without expanding their file permissions.\n\n"
    "An independent reviewer examines the initial delivery. "
    "A failed review goes unchanged to the same coder. "
    "The same reviewer checks the correction. "
    "You receive the final source, review, repair history "
    "or a needs_pi reason. A passed review can still report concerns or "
    "scientific choices for you. Scientific choices and operation requests "
    "remain yours. Only Runner executes scientific operations.\n\n"
    "Continue the same change using session_handle; its file "
    "permissions remain unchanged."
)

CODER_START_CONTEXT = (
    "Installed scientific APIs: native MuJoCo 3.12.0, NOT mujoco-py; "
    "Gymnasium 1.3.0; Stable-Baselines3 2.9.0. Dependencies and manifests "
    "are fixed and human-owned. Author only the requested "
    "scoped source; execute nothing. Read the supplied task_context "
    "and relevant authorized source and callers before editing. "
    "Use scientific_api_reference for unfamiliar installed APIs. "
    "Report missing or unclear requirements in summary and "
    "unchecked_scope instead of guessing. "
    "The reviewer checks implementation errors and logic. "
    "The parent PI must review actual diffs. "
    "No engineering handoff certifies science or Runner acceptance.\n"
)

REVIEWER_START_CONTEXT = (
    "Installed APIs: native MuJoCo 3.12.0, Gymnasium 1.3.0, "
    "Stable-Baselines3 2.9.0. Dependencies are fixed. "
    "Review only the supplied change and exact readable files. "
    "All writes, execution, delegation and operations are denied. "
    "Do not trust coder-authored expectations without checking them. "
    "Request complete engineering repair batches through your handoff. "
    "Set validation false only for defects the coder can repair within "
    "the request. Report confounds, unclear requirements or scientific "
    "choices for the PI in the explanation fields with validation true. "
    "No review certifies science.\n"
)

REPAIR_INTENT = (
    "Correct the problems described by the reviewer in source_context. "
    "Preserve the PI's requested output and authorized file scope. "
    "Report unclear requirements instead of guessing."
)


def _excerpt(text: str, start: str, end: str) -> str:
    _, found, tail = text.partition(start)
    if not found:
        raise ValueError(f"Required coding-context section is missing: {start}")
    selected, found, _ = tail.partition(end)
    if not found:
        raise ValueError(f"Required coding-context boundary is missing: {end}")
    return start + selected


def load_task_context(root: Path) -> dict[str, str]:
    """Fixed contract text given to every coder and reviewer."""
    authority = (root / "contracts" / "authority.md").read_text(encoding="utf-8")
    instruments = (root / "contracts" / "instruments.md").read_text(encoding="utf-8")
    return {
        "authority": _excerpt(
            authority, "## Installed scientific stack", "## PI sessions"
        ),
        "scenario": (root / "contracts" / "scenario.md").read_text(encoding="utf-8"),
        "saved_controller": _excerpt(
            instruments,
            "## Saved controller execution",
            "## Scientific coding interface",
        ),
        "python_module": _excerpt(
            instruments, "A `python_module` entry", "A paired-comparison entry"
        ),
    }


class OperationSubmissionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, object] | None = Field(
        description=(
            "One operation envelope defined in contracts/instruments.md. "
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
