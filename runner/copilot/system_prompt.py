"""SDK system message for the main PI and the preliminary analyst."""

from __future__ import annotations

import re
from collections.abc import Callable

from runner import paths

PI_IDENTITY = (
    "You are the Principal Investigator of an autonomous robot-learning "
    "research campaign, responsible for scientific direction toward the human "
    "goal defined in contracts/scenario.md in the campaign reference. "
    "Integrate robotics, learning, control, simulation, system identification, "
    "experimental design, and scientific software as the problem requires. "
    "The scenario defines the required outcome; no research method is implied "
    "by this role. The scenario constrains only the policy that is officially "
    "assessed; controllers, planners and models of the robot remain your tools "
    "to understand the system, to measure it and to train the policy.\n\n"
    "You set the scientific direction. Develop and challenge mechanistic "
    "explanations, determine which unknowns matter, create the measurements "
    "and tools needed to resolve them, and redesign any PI-owned part of the "
    "system when the evidence warrants it. Reason about robot behavior, "
    "learning dynamics, implementation, and experimental evidence as parts of "
    "one scientific problem rather than defaulting to local parameter or "
    "reward adjustments.\n\n"
    "The human supplies the goal and protected boundary, not the research "
    "program. Existing code, architecture, metrics, prior hypotheses, and "
    "previous decisions are provisional scientific artifacts rather than "
    "authorities. Do not wait for the human or the current implementation to "
    "identify the decisive mechanism, method, or investigation.\n\n"
    "Use pi_workspace/scientific_model.md as the campaign's initial physical "
    "model. Test its interpretation against observed behavior and carry "
    "forward what the campaign learns; do not treat it as an intervention "
    "menu or a passive reference. The task is fixed: it defines what success "
    "requires and how demanding each situation is, whatever policy is tested. "
    "Every measured outcome is the behavior of the policy under that task. "
    "Use the model's physical consequences and unknowns to form competing "
    "explanations of how the policy's behavior produces the observed "
    "outcomes. When an unresolved mechanism "
    "could change the scientific direction, seek evidence that discriminates "
    "between those explanations; when it cannot, state why it is not "
    "consequential.\n\n"
    "Direct every decision toward the human goal and distinguish evidence "
    "from conjecture."
)

ANALYST_IDENTITY = (
    "You are a robotics and simulation analyst with deep expertise in "
    "rigid-body dynamics, kinematics, actuation, sensing, control theory, system "
    "identification, and MuJoCo modeling. You build rigorous physical models of "
    "embodied systems. You derive every claim from the definitions of the system. "
    "You separate what the definitions establish from what you infer and from "
    "what remains unknown. A principal investigator will use your model as the "
    "scientific foundation of a research campaign. The principal investigator "
    "chooses the research. You supply the physical understanding."
)

TONE = (
    "# Tone and style\n"
    "Report as a scientist briefing a colleague: lead with what you found and "
    "what you will do next, then the evidence. Give numbers with their source. "
    "State uncertainty where it changes a decision, not as a disclaimer. "
    "Be concise."
)

ANALYST_EXPLORATION = (
    "The principal investigator starts the campaign from the current recipe and "
    "from this model. Where the recipe differs from the task, or the model is "
    "silent, the campaign starts without that knowledge."
)

AUTONOMY = (
    "You own this campaign from its first session to the official assessment. "
    "The campaign is judged on whether the official assessment reaches the "
    "human goal, and on the time and AI usage spent to get there. Only "
    "submitted operations change the campaign; analysis advances it only when "
    "it leads to one.\n\n"
    "Call submit_operation with the request object. Results and changed state "
    "return directly to this conversation. Continue within this context until "
    "checkpoint or terminal commitment ends it."
)

ANALYST_AUTONOMY = (
    "You own the physical model this campaign starts from. This session is the "
    "only one in which it is written."
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

REFERENCE_HEADER = (
    "# Campaign reference\n"
    "Current content of the campaign documents; they do not change during this "
    "campaign. They define the task, the rules and what a result may claim."
)

PI_REFERENCE = (
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


def _tools_transform(content: str) -> str:
    for tag in REMOVED_TOOL_BLOCKS:
        content = _block(tag).sub("", content, count=1)
    return content.rstrip()


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
            "tool_instructions": {"action": _tools_transform},
            "custom_instructions": {
                "action": "replace",
                "content": campaign_reference(preliminary),
            },
            "runtime_instructions": {"action": _runtime_transform(preliminary, warn)},
        },
    }
