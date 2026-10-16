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


REVIEW_MODEL = "gpt-6-luna"


REVIEW_REASONING = "high"


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
