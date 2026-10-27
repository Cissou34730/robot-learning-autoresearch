"""PI and analyst prompts. The wording is campaign-facing and must not drift."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runner.launcher import pstext
from runner.launcher.pstext import field, items, text
from runner.launcher.summaries import completed_events, latest_session_result

STARTUP_OBJECTIVE = (
    "Establish the initial scientific direction as contracts/program.md "
    "'Campaign startup' defines."
)
GOAL_REVIEW_OBJECTIVE = (
    "Use the completed evidence to update the scientific direction toward the human "
    "goal. Correct inherited interpretations, constraints or proposed questions when "
    "existing evidence warrants it. Request measurements when they resolve an "
    "uncertainty or develop the method. Compare the two outcomes as contracts/"
    "program.md 'Goal review' defines and choose one: request the official "
    "assessment, whose pass or fail result ends this campaign, or open one bounded "
    "goal-linked inquiry."
)
# The PowerShell here-string carried the checkout's CRLF line endings; keep them.
SCIENTIFIC_MODEL_OBJECTIVE = """Construct the physical and scientific model of the robot and the task. The model exists before any training or campaign evidence.

Work from first principles and from the human-owned definitions of the robot, the simulator, and the task. Explain the robot as an embodied dynamical system. Show how its morphology, actuation, sensing, control loop, simulator, and task geometry together determine the behaviors that are possible, constrained, or scientifically uncertain.

Build a scientific model of the system. The model explains mechanisms. It gives the reasons behind the behavior, and it goes beyond a list of components or a summary of the repository.

Analyze, from first principles and from the human-owned definitions:

* the robot morphology, degrees of freedom, geometry, reachable workspace, joint constraints, and relevant kinematic structure.
* the actuation model, and how commanded actions produce physical motion over time.
* the dynamic properties of the simulated robot that materially affect behavior, including timing, damping, inertia, and control authority.
* the initial physical state, and how it shapes the task that the controller must solve.
* the geometry and physical requirements of the task.
* the coupled physical capabilities that success requires, including reaching, trajectory control, convergence, and stabilization, together with the physically justified interactions between them.
* the sensing and observation model: which physical state is observable, which is derived, which is ambiguous, and which is unavailable.
* the relation between observation, control action, robot motion, and task outcome.
* alternative physical configurations or solutions available to the robot, such as multiple kinematic solutions.
* the invariances of the definitions, such as symmetries and conserved quantities, and what each makes equal or different across configurations, targets, and behavior.
* the physical, kinematic, dynamic, control, and observability constraints that make some situations more demanding than others, and what a controller must do to succeed in each.
* the physical quantities, across the complete behavior, that are scientifically meaningful for understanding the robot.

For each consequential physical implication and each unknown, state:

1. The research decisions that it could change.
2. The assumptions on which that relevance depends.
3. The source references in the implementation or the contracts.
4. The observation or evidence that would support, weaken, or revise it.

The model states physical consequences and the evidence that discriminates between them. The principal investigator selects the interventions.

Finish with a substantive section with the heading `## Decision-relevant synthesis`. Select only the physical consequences and unknowns that are most likely to change the first campaign decisions. For each selected item, keep these four points in compact form: its decision relevance, its assumptions, its source references, and its discriminating evidence. The principal investigator receives this section as the handoff into startup. The section states consequences and discriminating evidence. The principal investigator selects the interventions.

The final output is a compact and substantive scientific model. It explains how the complete coupled system works physically and scientifically.""".replace(
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
        f"Advance {text(inquiry_id)} with a session-sized deliverable, "
        "not necessarily a complete answer to the inquiry. Choose the deliverable "
        "from completed evidence and the remaining scientific question."
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
        objective=f"Save the scientific session record. {reason}",
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
        return (
            "The latest scientific session record cites: "
            f"{pstext.join(references, ', ')}."
        )
    best_known = field(field(state, "model_roles"), "best_known")
    if pstext.truthy(best_known):
        return (
            f"The explicit best-known model is {text(best_known)}; inspect its "
            "referenced measurements in campaigns/brief.md."
        )
    if completed_events(state):
        return (
            "Completed operation evidence exists in campaigns/brief.md, but no "
            "best-known model has been assigned."
        )
    return "No development operation has completed in this campaign."


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
            f"Goal relevance: {text(field(inquiry, 'goal_connection'))} "
            f"Closure condition: {text(field(inquiry, 'closure_condition'))}"
        )
    if pstext.same(field(field(state, "scientific_session"), "kind"), "inquiry"):
        return "The inquiry has closed. Preserve its outcome and the resulting campaign decision."
    return (
        "None. Measurements and evidence-backed model-role assignments are available "
        "before choosing official assessment or one bounded goal-linked inquiry."
    )


def _handoff_context(
    state: dict, kind: object, checkpoint: object, synthesis: str
) -> list[str]:
    inquiry = field(state, "active_inquiry")
    if pstext.same(kind, "goal_review") and pstext.truthy(checkpoint):
        return [
            (
                "Restored scientific handoff from the same PI's previous session. This is "
                "current scientific state, not another PI's opinion. The current scientific "
                "understanding below is that session's synthesis, verbatim."
            ),
            (
                "Proposed question for this goal review, verbatim:\n"
                f"{text(field(checkpoint, 'next_question'))}"
            ),
            (
                "Continue from the completed evidence, but treat inherited interpretations, "
                "research constraints, priorities and proposed next actions as revisable "
                "scientific judgments. Correct an unsupported interpretation or a question "
                "already settled by available evidence, and record the correction and its "
                "basis."
            ),
        ]
    if pstext.same(kind, "inquiry") and pstext.truthy(inquiry):
        conclusion = text(field(inquiry, "handoff_conclusion"))
        lines = []
        if not pstext.same(conclusion, synthesis):
            lines.append(
                "Synthesis from the goal review that opened the active inquiry, "
                f"verbatim:\n{conclusion}"
            )
        lines.append("Continue the bounded work from completed evidence.")
        return lines
    return []


def _decision_guidance(state: dict, kind: object) -> list[str]:
    goal_review = pstext.same(kind, "goal_review")
    lines = [
        "Compare the strongest candidate's prospects on the official panel with the "
        "prospects of further bounded work. Use completed evidence and its limits for "
        "both choices. Explain why the chosen action is preferable now."
        if goal_review
        else "State the unresolved distinction or the development step the operation "
        "addresses, and how its outcome could produce or select a better candidate.",
        (
            "Review completed evidence, the relevant learning trajectory, and unmeasured "
            "candidate artifacts."
        ),
        (
            "Choose the artifact and operation whose result would most improve the next "
            "decision toward the human goal."
        ),
    ]
    if goal_review:
        lines += [
            (
                "For a measurement, explain how its possible outcomes would affect the "
                "campaign-level choice."
            ),
            "Record the chosen assessment or inquiry and its evidence-based reason.",
            (
                "Preserve relevant residual failures, counterevidence and uncertainty in the "
                "chosen operation's reason."
            ),
            (
                "In goal review, next_question must exactly match the question of the "
                "inquiry opened in this session."
            ),
        ]
    else:
        lines.append(
            "Explain how the decision-relevant possible outcomes of the selected "
            "operation would affect the direction."
        )
        if pstext.same(kind, "inquiry") and pstext.truthy(
            field(state, "active_inquiry")
        ):
            lines.append(
                "While the inquiry remains active, next_question must exactly match its "
                "current question."
            )
    if not pstext.same(kind, "startup"):
        lines.append(
            "When evidence resolves or redirects the active inquiry, record that "
            "decision explicitly rather than drifting to another question."
        )
    return lines


def _legal_operations(
    state: dict, session: object, availability: dict, transition: Transition | None
) -> list[str]:
    if transition is None:
        return [
            (
                "Currently permitted operation kinds: "
                f"{pstext.join(availability.get('allowed_operations') or [], ', ')}. "
                "Request and evidence checks still apply."
            )
        ]
    kind = field(session, "kind")
    lines = [
        (
            "The sole legal next action is the checkpoint operation that saves the "
            "scientific session record."
        ),
        (
            f"The current scientific session is {text(field(session, 'id'))}. It remains "
            "active until the Runner accepts this checkpoint."
        ),
        "Opening, reframing or closing an inquiry does not end this scientific session.",
        (
            "Set completed_operations exactly to: "
            f"{pstext.to_json(items(field(session, 'operation_ids')))}"
        ),
        (
            "Do not request training, measurement, model-role changes, restoration, another "
            "inquiry change, or a campaign conclusion in this session."
        ),
    ]
    if pstext.same(kind, "goal_review"):
        lines.append(
            "Set next_question exactly to the question of the inquiry opened in this "
            "session."
        )
    elif pstext.same(kind, "inquiry") and pstext.truthy(field(state, "active_inquiry")):
        lines.append(
            "Set next_question exactly to the current active inquiry question."
        )
    elif pstext.same(kind, "inquiry"):
        lines.append(
            "Set next_question to the proposed scientific question for the next goal "
            "review. Goal review may revise or decline it using completed evidence "
            "already available."
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
        f"Training allocation: {context.timesteps} steps per run; a run may extend to "
        f"{context.max_timesteps} steps."
    )


def _submission_guidance(availability: dict, transition: Transition | None) -> str:
    if transition is not None:
        return (
            "Use the scientific session record contract in contracts/instruments.md in "
            "the campaign reference and preserve the transition decision, evidence, "
            "remaining goal gap, and next direction."
        )
    contracts = "; ".join(
        f"{text(kind)} in {_CONTRACT_FILES[text(kind).lower()]}"
        for kind in availability.get("allowed_operations") or []
        if text(kind).lower() in _CONTRACT_FILES
    )
    return (
        "When ready to act, use the request envelope in contracts/instruments.md and the "
        f"contract for the operation you choose: {contracts}. Both are in the campaign "
        "reference. Submit one scientific action."
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
        "No durable PI synthesis has been recorded yet.",
    )
    gap = _checkpoint_text(
        checkpoint,
        "current_goal_gap",
        "No PI-interpreted goal gap has been recorded yet.",
    )
    frontier = (
        text(field(checkpoint, "decision_frontier"))
        if pstext.truthy(checkpoint)
        else "No scientific decision frontier has been recorded yet."
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
    role_line = "You are the Principal Investigator described in your system prompt."
    if model_file:
        role_line += " The scientific model of the system you study follows."
    source_guidance = (
        "Begin with campaigns/brief.md and the latest scientific session record. "
        "Consult other evidence as the scientific question requires."
    )
    context_note = None
    if included:
        characters = len("".join(model_file + included))
        context_note = (
            "CONTEXT | first message includes pi_workspace/scientific_model.md, "
            f"{', '.join(context_files)} ({(characters + 500) // 1000}k chars)"
        )
        source_guidance = (
            "The scientific model is included at the start of this message and "
            "campaigns/brief.md at the end; the latest scientific session record is "
            "summarized above. Consult other evidence as the scientific question requires."
        )
    sections = [
        role_line,
        *model_file,
        *_handoff_context(state, kind, checkpoint, synthesis),
        (
            "From the decision-relevant synthesis of the scientific model, select the "
            "scientific distinction or capability question that should determine the "
            "initial direction. State which findings would change that decision, and how "
            "the first action follows. Treat the model as revisable in light of evidence. "
            "Do not require a measurement only to restate the model."
            if pstext.same(kind, "startup")
            else ""
        ),
        f"Current scientific understanding: {synthesis}",
        (
            "Completed evidence relative to the goal and its recorded interpretive limits: "
            f"{_best_evidence(state, checkpoint)} {latest_session_result(state)}"
        ),
        f"Current goal gap: {gap}",
        f"Scientific decision frontier: {frontier}",
        (
            f"Active inquiry: {_inquiry_line(state, transition)}"
            if not pstext.same(kind, "startup")
            else ""
        ),
        f"Current objective: {objective}",
        *([] if transition else _decision_guidance(state, kind)),
        *_legal_operations(state, session, availability, transition),
        _training_allocation(kind, transition, context),
        (
            f"The proposed action could not be accepted: {validation_error} Correct it "
            "without discarding valid scientific work."
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
                "This is execution history, not scientific evidence. Diagnose and correct the "
                "scientific implementation or choose another action. Call submit_operation "
                "with request=null to reaccept the corrected pending action, or supply a "
                "replacement request."
            ),
        ]
    )


def scientific_model_prompt(goal: str) -> str:
    return "\n\n".join(
        [
            "You are the robotics and simulation analyst described in your system prompt.",
            f"Human goal: {goal}",
            f"Current objective: {SCIENTIFIC_MODEL_OBJECTIVE}",
            (
                "Base the model on contracts/scenario.md and on the human-owned definitions of "
                "the robot, the simulator, and the task in the campaign reference."
            ),
            (
                "Code under robot_learning/ is the current recipe. Its rewards, training "
                "environments and observation construction are design choices, not properties "
                "of the robot; label any statement drawn from them as such."
            ),
            (
                "The document has four registers, with these headings: Established facts, "
                "Physical consequences, Unknowns, and Decision-relevant synthesis. Write each "
                "register as a level-two heading (##). Put all its content under that heading. "
                "Use level-three headings (###) for topics inside a register. Mark each "
                "statement as a repository fact, a reasoned implication, or an unresolved "
                "quantity. Keep source references for later verification."
            ),
            (
                "Include only what is justified before campaign evidence exists. Write the "
                "result to pi_workspace/scientific_model.md."
            ),
        ]
    )


def scientific_model_retry_prompt(goal: str, feedback: str) -> str:
    return "\n\n".join(
        [
            f"Human goal: {goal}",
            f"The scientific model could not be accepted: {feedback}",
            (
                "Correct pi_workspace/scientific_model.md. Keep the valid content. Make all "
                "four required registers substantive and source-recoverable. Make the "
                "synthesis decision-relevant. Each register is a level-two heading (##) with "
                "its content directly under it. Move topic sections inside a register and "
                "change their headings to level three (###)."
            ),
        ]
    )
