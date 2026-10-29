"""Native coding models, prompt loading and agent profiles."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runner import protocol
from runner.artifact_evidence_query import ArtifactReference, CandidateReference

# The preliminary analyst retains its existing publication/tool contract.
RESEARCH_TOOLS = ["view", "rg", "glob", "apply_patch"]


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
            "State the expected output precisely. The coder chooses the implementation."
        ),
    )
    allowed_paths: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="The exact files that a new coder can write. Omit for a correction.",
    )
    read_paths: list[str] | None = Field(
        default=None,
        max_length=64,
        description="Other files that the coder can read. Omit to keep the scope of a correction.",
    )
    source_context: str = Field(
        default="",
        max_length=32_000,
        description=(
            "Supporting facts, caller context and observed errors. "
            "The coder does not receive your conversation. "
            "The Runner gives the glossary, the current contracts/scenario.md and "
            "excerpts of the authority and operation contracts. Select additional "
            "source files in read_paths."
        ),
    )
    session_handle: str | None = Field(default=None, min_length=1)
    evidence_inputs: list[ArtifactReference | CandidateReference] | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        description=(
            "New calls only: the recorded evidence that the change will read. A "
            "measurement artifact {operation_id, artifact_index} gives its recorded "
            "structure (JSON paths and field names, no values). A candidate "
            "{candidate} gives its archive file names and artifact.json metadata."
        ),
    )

    @model_validator(mode="after")
    def require_initial_scope(self) -> ScientificCodingParams:
        if not self.session_handle and self.allowed_paths is None:
            raise ValueError(
                "A new coding call requires allowed_paths. "
                "A correction requires the returned session_handle and intent."
            )
        if self.session_handle and self.evidence_inputs:
            raise ValueError(
                "evidence_inputs belong to a new coding call; a correction reuses "
                "the original task context."
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
    "Use scientific_coding for changes of scientific source code.\n\n"
    "In intent, state the expected output precisely. "
    "The coder chooses the implementation, not what the output means.\n\n"
    "Select the exact files that the coder can write in allowed_paths, and "
    "additional source and caller files that it can read in read_paths.\n\n"
    "Put the supporting facts, the caller context and the observed errors in "
    "source_context. The coder does not receive your conversation. The Runner "
    "gives the glossary, the current contracts/scenario.md and excerpts of the "
    "authority and operation contracts to the coder and the reviewer. This does "
    "not expand their file permissions. When the change reads recorded measurement artifacts, "
    "list them in evidence_inputs. The coder then sees their recorded field "
    "structure.\n\n"
    "An independent reviewer checks the first delivery. "
    "A failed review goes without change to the same coder. "
    "The same reviewer checks the correction. "
    "You receive the final source code, the review and the repair history, "
    "or a needs_pi reason. A review that passed can still report concerns or "
    "scientific choices for you. Scientific choices and operation requests "
    "stay with you. Only the Runner executes scientific operations.\n\n"
    "To continue the same change, use session_handle. Its file "
    "permissions do not change."
)

CODER_START_CONTEXT = (
    "Installed scientific APIs: native MuJoCo 3.12.0, NOT mujoco-py, "
    "Gymnasium 1.3.0 and Stable-Baselines3 2.9.0. The dependencies and the "
    "manifests are fixed and human-owned. Write only the requested source code "
    "within the authorized file scope. Execute nothing. Before you edit a file, "
    "read the supplied task_context and the relevant authorized source and "
    "callers. Use scientific_api_reference for unfamiliar installed APIs. "
    "Report missing or unclear requirements in summary and unchecked_scope "
    "instead of guessing. The reviewer checks implementation errors and logic. "
    "The PI must review the actual diffs. No engineering handoff certifies the "
    "science or the acceptance by the Runner.\n"
)

REVIEWER_START_CONTEXT = (
    "Installed APIs: native MuJoCo 3.12.0, Gymnasium 1.3.0 and "
    "Stable-Baselines3 2.9.0. The dependencies are fixed. "
    "Review only the supplied change and the exact readable files. "
    "All writes, execution, delegation and operations are denied. "
    "Do not trust an expectation that the coder wrote until you check it. "
    "Request all engineering repairs as one complete batch in your handoff. "
    "Set validation to false only for defects that the coder can repair within "
    "the request. Report confounds, unclear requirements or scientific "
    "choices for the PI in the explanation fields, with validation true. "
    "No review certifies the science.\n"
)

REPAIR_INTENT = (
    "Correct the problems that the reviewer describes in source_context. "
    "Preserve the output that the PI requested and the authorized file scope. "
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
    parts = root / "contracts" / "instruments"
    coding = (parts / "coding.md").read_text(encoding="utf-8")
    measurement = (parts / "measurement.md").read_text(encoding="utf-8")
    return {
        "glossary": (root / "contracts" / "glossary.md").read_text(encoding="utf-8"),
        "authority": _excerpt(
            authority, "## Installed scientific stack", "## PI sessions"
        ),
        "scenario": (root / "contracts" / "scenario.md").read_text(encoding="utf-8"),
        "saved_controller": _excerpt(
            coding,
            "## Saved controller execution",
            "## Scientific coding interface",
        ),
        "python_module": _excerpt(
            measurement, "A `python_module` entry", "A paired-comparison entry"
        ),
    }


class OperationSubmissionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, object] | None = Field(
        description=(
            "One operation envelope that contracts/instruments.md defines. "
            "Use null only to accept a failed pending operation again after a repair."
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
