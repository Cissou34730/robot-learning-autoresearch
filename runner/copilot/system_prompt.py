"""SDK system message for the main PI and the preliminary analyst."""

from __future__ import annotations

import re
from collections.abc import Callable

from runner import paths

PI_IDENTITY = (
    "You are the principal investigator (PI) of an autonomous robot-learning "
    "research campaign. You are responsible for the scientific direction toward "
    "the goal that contracts/scenario.md defines in the campaign reference. "
    "Integrate robotics, learning, control, simulation, system identification, "
    "experimental design and scientific software as the problem requires. The "
    "task defines the required result. This role implies no research method.\n\n"
    "The task constrains only the policy that the official assessment "
    "evaluates. Controllers, planners and robot models remain your tools to "
    "understand the system, to measure it and to train the policy.\n\n"
    "You set the scientific direction. Develop mechanistic explanations and "
    "challenge them. Determine which unknowns matter. Create the measurements "
    "and the tools that resolve them. Redesign any PI-owned part of the system "
    "when the evidence warrants it.\n\n"
    "Reason about the robot behavior, the learning dynamics, the implementation "
    "and the experimental evidence as one scientific problem. Do not default to "
    "local adjustments of parameters or of the reward.\n\n"
    "The human supplies the goal and the protected limits, not the research "
    "program. The existing code, architecture, metrics, prior hypotheses and "
    "earlier decisions are provisional scientific artifacts, not authorities. "
    "Do not wait for the human or for the current implementation to identify "
    "the decisive mechanism, method or investigation.\n\n"
    "Use pi_workspace/scientific_model.md as the initial physical model of the "
    "campaign. Test its interpretation against the observed behavior, and carry "
    "forward what the campaign learns in your session records. Do not treat the "
    "scientific model as a menu of interventions or as passive background.\n\n"
    "The task is fixed for every policy that you test. The episode outcomes of a "
    "policy measure the behavior of that policy under the task.\n\n"
    "Use the physical consequences and the unknowns of the scientific model to "
    "form competing mechanistic explanations. Each explanation of a policy "
    "result states how the behavior of the policy produces that result. When an "
    "unresolved "
    "mechanism could change the scientific direction, seek evidence that "
    "discriminates between the explanations. When it cannot, state why it is "
    "not consequential.\n\n"
    "Direct every decision toward the goal. Distinguish evidence from conjecture."
)

ANALYST_IDENTITY = (
    "You are a robotics and simulation analyst with deep expertise in "
    "rigid-body dynamics, kinematics, actuation, sensing, control theory, system "
    "identification and MuJoCo modeling. You build rigorous physical models of "
    "embodied systems. You derive every claim from the definitions of the system. "
    "You separate what the definitions establish from what you infer and from "
    "what remains unknown.\n\n"
    "The principal investigator (PI) will use your physical model as the "
    "scientific foundation of a research campaign. The PI chooses the research. "
    "You supply the physical understanding."
)

TONE = (
    "# Tone and style\n"
    "Report as a scientist who briefs a colleague. Lead with what you found and "
    "what you will do next. Then give the evidence. Give each number with its "
    "source. State uncertainty where it changes a decision, not as a disclaimer. "
    "Be concise."
)

ANALYST_EXPLORATION = (
    "The PI starts the campaign from the inherited recipe and from this "
    "physical model. Where the inherited recipe differs from the task, or where "
    "the model is silent, the campaign starts without that knowledge."
)

AUTONOMY = (
    "You own this campaign from its first session to the official assessment. "
    "The human judges the campaign on two things: whether the official "
    "assessment reaches the goal, and the time and AI usage that it needs. Only "
    "submitted operations change the campaign. Analysis moves the campaign "
    "forward only when it leads to an operation.\n\n"
    "Call submit_operation with the request object. The results and the changed "
    "state come back to this conversation. Continue in this conversation until a "
    "checkpoint operation or the request for the official assessment ends it."
)

ANALYST_AUTONOMY = (
    "You own the physical model that this campaign starts from. Only this "
    "session writes it."
)

REMOVED_RUNTIME_BLOCKS = (
    "editing_constraints",
    "destructive_actions",
    "subagent_usage",
    "session_context",
    "github_reference_formatting",
    "git_commit_trailer",
)

# Bash and CLI bullets do not apply: these sessions have no shell.
REMOVED_EFFICIENCY_LINES = (
    "* Chain related bash commands",
    "* Suppress verbose output",
    "Your output appears in a command-line interface.",
)

REMOVED_IDENTITY_TEXT = (
    "You are an interactive tool that helps users with software engineering tasks.",
    "Your job is to perform the task the user requested.",
)

REMOVED_TOOL_BLOCKS = (
    "gh_cli_preference",
    "github-mcp-server-*",
    "code_search_tools",
)

# The main PI has no shell, so its usage rules would only mislead. The analyst
# has a shell under a command policy and keeps them.
PI_ONLY_REMOVED_TOOL_BLOCKS = ("powershell",)

REFERENCE_HEADER = (
    "# Campaign reference\n"
    "The current content of the campaign documents. They do not change during "
    "this campaign. They define the task, the rules and what a result can claim. "
    "contracts/glossary.md defines the terms that they use."
)

PI_REFERENCE = (
    "contracts/glossary.md",
    "contracts/scenario.md",
    "contracts/authority.md",
    "contracts/program.md",
    "contracts/instruments.md",
    "contracts/instruments/measurement.md",
    "contracts/instruments/training.md",
    "contracts/instruments/inquiry.md",
    "contracts/instruments/coding.md",
    "contracts/instruments/readers.md",
    "contracts/policy_runtime.py",
)

REFERENCE_READ_DENIAL = "Its current content is in your system prompt."


def reference_paths(preliminary: bool) -> tuple[str, ...]:
    if not preliminary:
        return PI_REFERENCE
    robots = sorted(
        f"contracts/robots/{path.name}"
        for path in (paths.HARNESS_ROOT / "contracts" / "robots").glob("*")
        if path.is_file() and path.name != "__init__.py" and path.stat().st_size > 0
    )
    return (
        "contracts/glossary.md",
        "contracts/scenario.md",
        "contracts/task_spec.py",
        *robots,
        "contracts/authority.md",
        "contracts/policy_runtime.py",
        "contracts/instruments/scientific-model.md",
    )


def _reference_file(relative: str) -> str:
    root = paths.ROOT if paths.is_campaign_owned(relative) else paths.HARNESS_ROOT
    text = (root / relative).read_text(encoding="utf-8").rstrip()
    return f"File {relative}:\n````\n{text}\n````"


def campaign_reference(preliminary: bool) -> str:
    files = [_reference_file(relative) for relative in reference_paths(preliminary)]
    return "\n\n".join([REFERENCE_HEADER, *files])


def _block(tag: str) -> re.Pattern:
    tag = re.escape(tag)
    return re.compile(rf"<{tag}>.*?</{tag}>\s*", re.DOTALL)


def _runtime_transform(
    preliminary: bool, warn: Callable[[str], None]
) -> Callable[[str], str]:
    replaced = {
        "autonomy_and_persistence": ANALYST_AUTONOMY if preliminary else AUTONOMY
    }
    removed = REMOVED_RUNTIME_BLOCKS
    if preliminary:
        replaced["exploration_and_reading_files"] = ANALYST_EXPLORATION
    else:
        removed += ("exploration_and_reading_files",)

    def transform(content: str) -> str:
        for tag, text in replaced.items():
            block = f"<{tag}>\n{text}\n</{tag}>\n\n"
            content, count = _block(tag).subn(
                lambda _, block=block: block, content, count=1
            )
            if not count:
                warn(f"system prompt: runtime block <{tag}> not found; not replaced")
        for tag in removed:
            content = _block(tag).sub("", content, count=1)
        return content.rstrip()

    return transform


def _efficiency_transform(content: str) -> str:
    return "\n".join(
        line
        for line in content.splitlines()
        if not line.startswith(REMOVED_EFFICIENCY_LINES)
    ).rstrip()


def _identity_transform(content: str) -> str:
    for text in REMOVED_IDENTITY_TEXT:
        content = content.replace(text, "")
    content = re.sub(
        r"# Search and delegation\n.*?(?=^# |\Z)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )
    return re.sub(r"[ \t]*\n(?:[ \t]*\n)+", "\n\n", content).strip()


def _tools_transform(preliminary: bool) -> Callable[[str], str]:
    removed = REMOVED_TOOL_BLOCKS
    if not preliminary:
        removed += PI_ONLY_REMOVED_TOOL_BLOCKS

    def transform(content: str) -> str:
        for tag in removed:
            content = _block(tag).sub("", content, count=1)
        return content.rstrip()

    return transform


def system_message(preliminary: bool, warn: Callable[[str], None]) -> dict:
    return {
        "mode": "customize",
        "sections": {
            "identity": {"action": _identity_transform},
            "preamble": {
                "action": "replace",
                "content": ANALYST_IDENTITY if preliminary else PI_IDENTITY,
            },
            "tone": {"action": "replace", "content": TONE},
            "tool_efficiency": {"action": _efficiency_transform},
            "code_change_rules": {"action": "remove"},
            "guidelines": {"action": "remove"},
            "last_instructions": {"action": "remove"},
            "tool_instructions": {"action": _tools_transform(preliminary)},
            "custom_instructions": {
                "action": "replace",
                "content": campaign_reference(preliminary),
            },
            "runtime_instructions": {"action": _runtime_transform(preliminary, warn)},
        },
    }
