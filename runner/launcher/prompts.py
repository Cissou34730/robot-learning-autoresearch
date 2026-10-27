"""PI and analyst prompts. The wording is campaign-facing and must not drift."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runner.launcher import pstext
from runner.launcher.pstext import field, items, text
from runner.launcher.summaries import completed_events, latest_session_result

STARTUP_OBJECTIVE = (
    "Choose the first scientific direction, as the section 'Campaign start' of "
    "contracts/program.md defines."
)
GOAL_REVIEW_OBJECTIVE = (
    "Use the completed evidence to update the scientific direction toward the "
    "goal. When the evidence supports it, correct earlier conclusions, limits or "
    "proposed questions. Request measurements when they remove an uncertainty or "
    "develop the method. Compare the two actions that the section 'Goal-review "
    "session' of contracts/program.md defines, and choose one: request the "
    "official assessment, whose pass or fail result ends this campaign, or open "
    "one inquiry about the gap to the goal."
)
# The PowerShell here-string carried the checkout's CRLF line endings; keep them.
SCIENTIFIC_MODEL_OBJECTIVE = """Write the scientific model of the robot and of the task. The scientific model exists before any training or campaign evidence.

Work from first principles and from the human-owned definitions of the robot, the simulator and the task. Explain the robot as an embodied dynamical system. Show how its morphology, actuation, sensors, control loop, simulator and task geometry together determine the behaviors that are possible, limited or scientifically uncertain.

The scientific model explains causes. It gives the reasons for the behavior. It is more than a list of components or a summary of the repository.

Analyze these items from first principles and from the human-owned definitions:

* the morphology, the degrees of freedom, the geometry, the reachable workspace, the joint limits and the relevant kinematic structure of the robot.
* the actuation, and how commanded actions make physical motion over time.
* the dynamic properties of the simulated robot that have an effect on behavior, for example timing, damping, inertia and control authority.
* the initial physical state, and how it changes the problem that the controller must solve.
* the geometry and the physical requirements of the task.
* the coupled physical capabilities that success requires, for example reach, trajectory control, convergence and stabilization, and the physical interactions between them.
* the sensors and the observation: which physical state is observable, which is derived, which is ambiguous and which is not available.
* the relation between observation, control action, robot motion and episode outcome.
* the alternative physical configurations or solutions of the robot, for example several kinematic solutions.
* the invariances of the definitions, for example symmetries and conserved quantities, and what each makes equal or different across configurations, targets and behavior.
* the constraints (physical, kinematic, dynamic, control and observability) that make some situations more demanding than others, and what a controller must do to succeed in each.
* the physical quantities, over the complete behavior, that are scientifically useful to understand the robot.

For each important physical consequence and each unknown, state:

1. The research decisions that it can change.
2. The assumptions on which this effect depends.
3. The source references in the source code or in the contracts.
4. The fact or the evidence that can support it, weaken it or change it.

The scientific model states physical consequences and the evidence that separates them. The PI selects the changes.

End with a section that has content and the heading `## Decision-relevant synthesis`. Select only the physical consequences and the unknowns that are most likely to change the first decisions of the campaign. For each selected item, give these four points in short form: its effect on decisions, its assumptions, its source references and the evidence that separates the possibilities.

The PI receives this section as the handoff into the startup session. The section states consequences and the evidence that separates them. The PI selects the changes.

The final result is a short scientific model with content. It explains how the complete coupled system works, physically and scientifically.""".replace(
    "\n", "\r\n"
)

_FENCE = "````"
_CONTRACT_FILES = {
    "measurement": "contracts/instruments/measurement.md",
    "training": "contracts/instruments/training.md",
    "model_role": "contracts/instruments/training.md",
    "restore_recipe": "contracts/instruments/training.md",
    "inquiry": "contracts/instruments/inquiry.md",
    "campaign_conclusion": "contracts/instruments/inquiry.md",
    "checkpoint": "contracts/instruments.md",
}


def inquiry_objective(inquiry_id: object) -> str:
    return (
        f"Move {text(inquiry_id)} forward with the work for one session. This work "
        "does not need to answer the full inquiry. Choose this work from the "
        "completed evidence and the open scientific question."
    )


@dataclass(frozen=True)
class Transition:
    """A required checkpoint before any further operation."""

    objective: str
    inquiry: str


def required_transition(availability: dict) -> Transition | None:
    if not availability.get("checkpoint_required"):
        return None
    reason = text(availability.get("checkpoint_reason"))
    return Transition(
        objective=f"Save the session record. {reason}",
        inquiry=reason,
    )


def first_message_files(
    paths: list[str], *, harness_root: Path, campaign_root: Path
) -> list[str]:
    blocks = []
    for relative in paths:
        root = harness_root if relative.startswith("contracts/") else campaign_root
        path = root / Path(*relative.split("/"))
        if path.is_file():
            with path.open(encoding="utf-8-sig", newline="") as stream:
                content = stream.read().rstrip()
            blocks.append(
                f"File {relative} (current at session start):\n{_FENCE}\n{content}\n{_FENCE}"
            )
    return blocks


@dataclass(frozen=True)
class SessionPrompt:
    text: str
    context_note: str | None


@dataclass(frozen=True)
class PromptContext:
    """What a scientific-session prompt depends on besides durable state."""

    harness_root: Path
    campaign_root: Path
    timesteps: int
    max_timesteps: int
    conversation_exists: bool


def _best_evidence(state: dict, checkpoint: object) -> str:
    if pstext.truthy(field(state, "official_assessment")):
        return text(field(field(state, "official_assessment"), "summary"))
    references = field(checkpoint, "evidence_references")
    if pstext.truthy(checkpoint) and pstext.count(references) > 0:
        return f"The last session record cites: {pstext.join(references, ', ')}."
    best_known = field(field(state, "model_roles"), "best_known")
    if pstext.truthy(best_known):
        return (
            f"The best-known candidate is {text(best_known)}. Read its "
            "measurements in campaigns/brief.md."
        )
    if completed_events(state):
        return (
            "campaigns/brief.md contains the evidence of completed operations. No "
            "candidate has the best-known role."
        )
    return "No measurement or training has completed in this campaign."


def _checkpoint_text(checkpoint: object, name: str, missing: str) -> str:
    value = field(checkpoint, name)
    if pstext.truthy(checkpoint) and pstext.truthy(value):
        return text(value)
    return missing


def _inquiry_line(state: dict, transition: Transition | None) -> str:
    inquiry = field(state, "active_inquiry")
    if transition is not None:
        return transition.inquiry
    if pstext.truthy(inquiry):
        return (
            f"{text(field(inquiry, 'id'))}: {text(field(inquiry, 'question'))} "
            f"Connection to the goal: {text(field(inquiry, 'goal_connection'))} "
            f"Closure condition: {text(field(inquiry, 'closure_condition'))}"
        )
    if pstext.same(field(field(state, "scientific_session"), "kind"), "inquiry"):
        return (
            "The inquiry is closed. Record its result and the campaign decision that "
            "follows."
        )
    return (
        "None. Before you choose the official assessment or one inquiry, you can "
        "measure and give roles that the evidence supports."
    )


def _handoff_context(
    state: dict, kind: object, checkpoint: object, synthesis: str
) -> list[str]:
    inquiry = field(state, "active_inquiry")
    if pstext.same(kind, "goal_review") and pstext.truthy(checkpoint):
        return [
            (
                "This is the handoff from your previous session. It is the current "
                "scientific state, not the opinion of another PI. The current "
                "scientific understanding below is the synthesis of that session, "
                "word for word."
            ),
            (
                "Proposed question for this goal-review session, word for word:\n"
                f"{text(field(checkpoint, 'next_question'))}"
            ),
            (
                "Continue from the completed evidence. Earlier conclusions, research "
                "limits, priorities and proposed next actions are scientific judgments "
                "that you can change. Correct a conclusion that the evidence does not "
                "support, or a question that the available evidence already answers. "
                "Record the correction and its reason."
            ),
        ]
    if pstext.same(kind, "inquiry") and pstext.truthy(inquiry):
        conclusion = text(field(inquiry, "handoff_conclusion"))
        lines = []
        if not pstext.same(conclusion, synthesis):
            lines.append(
                "Synthesis of the goal-review session that opened the active inquiry, "
                f"word for word:\n{conclusion}"
            )
        lines.append("Continue the work from the completed evidence.")
        return lines
    return []


def _decision_guidance(state: dict, kind: object) -> list[str]:
    goal_review = pstext.same(kind, "goal_review")
    lines = [
        "Compare the chances of the strongest candidate on the official panel with "
        "the chances of one more inquiry. Use the completed evidence and its limits "
        "for both actions. Explain why the chosen action is better now."
        if goal_review
        else "State the open question that the operation addresses, or the step that "
        "it adds to the method. State how its result can make or select a better "
        "candidate.",
        (
            "Examine the completed evidence, the relevant training curves and the "
            "candidates that you did not measure."
        ),
        (
            "Choose the candidate and the operation whose result best improves your "
            "next decision toward the goal."
        ),
    ]
    if goal_review:
        lines += [
            (
                "For a measurement, explain how its possible results change your "
                "choice between the two actions."
            ),
            (
                "Record the chosen action, the official assessment or the inquiry, and "
                "its reason from the evidence."
            ),
            (
                "In the reason of the chosen operation, keep the relevant remaining "
                "failures, the evidence against your choice and the uncertainty."
            ),
            (
                "In a goal-review session, next_question must be exactly the question "
                "of the inquiry that you opened in this session."
            ),
        ]
    else:
        lines.append(
            "Explain how the possible results of the selected operation can change "
            "the direction."
        )
        if pstext.same(kind, "inquiry") and pstext.truthy(
            field(state, "active_inquiry")
        ):
            lines.append(
                "While the inquiry is active, next_question must be exactly its "
                "current question."
            )
    if not pstext.same(kind, "startup"):
        lines.append(
            "When evidence answers the active inquiry or changes its direction, "
            "record this decision. Do not move to another question without a record."
        )
    return lines


def _legal_operations(
    state: dict, session: object, availability: dict, transition: Transition | None
) -> list[str]:
    if transition is None:
        return [
            (
                "Operation kinds that you can submit now: "
                f"{pstext.join(availability.get('allowed_operations') or [], ', ')}. "
                "The request and evidence checks still apply."
            )
        ]
    kind = field(session, "kind")
    lines = [
        (
            "The only next action that you can submit is the checkpoint operation. "
            "It saves the session record."
        ),
        (
            f"The current session is {text(field(session, 'id'))}. It stays active "
            "until the Runner accepts this checkpoint operation."
        ),
        "When you open, reframe or close an inquiry, this session does not end.",
        (
            "Set completed_operations to exactly: "
            f"{pstext.to_json(items(field(session, 'operation_ids')))}"
        ),
        (
            "In this session, do not request training, measurement, role changes, "
            "recipe restoration, another inquiry change or the official assessment."
        ),
    ]
    if pstext.same(kind, "goal_review"):
        lines.append(
            "Set next_question to exactly the question of the inquiry that you "
            "opened in this session."
        )
    elif pstext.same(kind, "inquiry") and pstext.truthy(field(state, "active_inquiry")):
        lines.append("Set next_question to exactly the question of the active inquiry.")
    elif pstext.same(kind, "inquiry"):
        lines.append(
            "Set next_question to the scientific question that you propose for the "
            "next goal-review session. In that session, you can change or refuse it "
            "with the completed evidence."
        )
    return lines


def _training_allocation(
    kind: object, transition: Transition | None, context: PromptContext
) -> str:
    if transition is not None or pstext.same(kind, "goal_review"):
        return ""
    if pstext.same(kind, "startup"):
        return (
            f"Training allocation: up to {context.timesteps} requested steps per run."
        )
    return (
        f"Training allocation: {context.timesteps} steps per run. A run can extend to "
        f"{context.max_timesteps} steps."
    )


def _submission_guidance(availability: dict, transition: Transition | None) -> str:
    if transition is not None:
        return (
            "Use the session record format in contracts/instruments.md in the "
            "campaign reference. Keep the decision of this transition, the evidence, "
            "the remaining gap to the goal and the next direction."
        )
    contracts = "; ".join(
        f"{text(kind)} in {_CONTRACT_FILES[text(kind).lower()]}"
        for kind in availability.get("allowed_operations") or []
        if text(kind).lower() in _CONTRACT_FILES
    )
    return (
        "When you are ready, use the request envelope in contracts/instruments.md "
        f"and the format of the operation that you choose: {contracts}. Both are in "
        "the campaign reference. Submit one scientific action."
    )


def scientific_session_prompt(
    state: dict,
    availability: dict,
    context: PromptContext,
    *,
    validation_error: str = "",
) -> SessionPrompt:
    checkpoint = field(state, "pi_checkpoint")
    session = field(state, "scientific_session")
    kind = field(session, "kind")
    transition = required_transition(availability)
    synthesis = _checkpoint_text(
        checkpoint,
        "current_synthesis",
        "No session record contains a synthesis yet.",
    )
    gap = _checkpoint_text(
        checkpoint,
        "current_goal_gap",
        "No session record contains a goal gap yet.",
    )
    frontier = (
        text(field(checkpoint, "decision_frontier"))
        if pstext.truthy(checkpoint)
        else "No session record contains open questions yet."
    )
    objective = (
        transition.objective if transition else text(field(session, "objective"))
    )
    context_files = (
        ["campaigns/brief.md"]
        if not context.conversation_exists and transition is None
        else []
    )
    included = first_message_files(
        context_files,
        harness_root=context.harness_root,
        campaign_root=context.campaign_root,
    )
    model_file = first_message_files(
        ["pi_workspace/scientific_model.md"] if context_files else [],
        harness_root=context.harness_root,
        campaign_root=context.campaign_root,
    )
    role_line = "You are the PI that your system prompt describes."
    if model_file:
        role_line += " The scientific model of the system that you study follows."
    source_guidance = (
        "Start with campaigns/brief.md and the last session record. Read other "
        "evidence when the scientific question needs it."
    )
    context_note = None
    if included:
        characters = len("".join(model_file + included))
        context_note = (
            "CONTEXT | first message includes pi_workspace/scientific_model.md, "
            f"{', '.join(context_files)} ({(characters + 500) // 1000}k chars)"
        )
        source_guidance = (
            "The scientific model is at the start of this message, and "
            "campaigns/brief.md is at the end. The summary of the last session "
            "record is above. Read other evidence when the scientific question "
            "needs it."
        )
    sections = [
        role_line,
        *model_file,
        *_handoff_context(state, kind, checkpoint, synthesis),
        (
            "From the decision-relevant synthesis of the scientific model, select the "
            "scientific distinction or the capability question that decides the first "
            "direction. State which results "
            "can change that decision, and how the first action follows from it. "
            "Evidence can change the conclusions of the scientific model. Do not "
            "request a measurement only to repeat what the scientific model states."
            if pstext.same(kind, "startup")
            else ""
        ),
        f"Current scientific understanding: {synthesis}",
        (
            "Completed evidence for the goal, and the recorded limits of your "
            "conclusions: "
            f"{_best_evidence(state, checkpoint)} {latest_session_result(state)}"
        ),
        f"Current goal gap: {gap}",
        f"Open questions (decision_frontier): {frontier}",
        (
            f"Active inquiry: {_inquiry_line(state, transition)}"
            if not pstext.same(kind, "startup")
            else ""
        ),
        f"Session objective: {objective}",
        *([] if transition else _decision_guidance(state, kind)),
        *_legal_operations(state, session, availability, transition),
        _training_allocation(kind, transition, context),
        (
            f"The Runner did not accept the proposed action: {validation_error} "
            "Correct it, and keep the valid scientific work."
            if validation_error
            else ""
        ),
        source_guidance,
        _submission_guidance(availability, transition),
        *included,
    ]
    return SessionPrompt(
        "\n\n".join(section for section in sections if section), context_note
    )


def repair_prompt(session_prompt: str, pending: dict) -> str:
    return "\n\n".join(
        [
            session_prompt,
            (
                f"The requested action {text(field(pending, 'id'))} failed: "
                f"{text(field(pending, 'failure'))}"
            ),
            (
                "This failure is execution history, not scientific evidence. Find the "
                "cause and correct the scientific source code, or choose another "
                "action. Call submit_operation with request=null to accept the "
                "corrected pending action again, or give a replacement request."
            ),
        ]
    )


def scientific_model_prompt(goal: str) -> str:
    return "\n\n".join(
        [
            (
                "You are the robotics and simulation analyst that your system prompt "
                "describes."
            ),
            f"Goal: {goal}",
            f"Session objective: {SCIENTIFIC_MODEL_OBJECTIVE}",
            (
                "Base the scientific model on contracts/scenario.md and on the "
                "human-owned definitions of the robot, the simulator and the task in "
                "the campaign reference."
            ),
            (
                "The code in robot_learning/ is the inherited recipe. Its rewards, "
                "training environments and observation construction are design "
                "choices, not properties of the robot. Mark each statement that comes "
                "from them as a design choice."
            ),
            (
                "The document has four registers, with these headings: Established "
                "facts, Physical consequences, Unknowns, and Decision-relevant "
                "synthesis. Write each register as a level-two heading (##). Put all "
                "its content under that heading. Use level-three headings (###) for "
                "topics in a register. Mark each statement as a repository fact, a "
                "reasoned implication or an unresolved quantity. Keep the source "
                "references so that the PI can verify them later."
            ),
            (
                "Include only what the definitions justify before campaign evidence "
                "exists. Write the result to pi_workspace/scientific_model.md."
            ),
        ]
    )


def scientific_model_retry_prompt(goal: str, feedback: str) -> str:
    return "\n\n".join(
        [
            f"Goal: {goal}",
            f"The Runner did not accept the scientific model: {feedback}",
            (
                "Correct pi_workspace/scientific_model.md. Keep the valid content. Make "
                "all four required registers substantial, with source references that "
                "the PI can find. Make sure that the synthesis selects the items that can "
                "change decisions. Each "
                "register is a level-two heading (##) with its content directly under it. "
                "Move topic sections into a register and change their headings to level "
                "three (###)."
            ),
        ]
    )
