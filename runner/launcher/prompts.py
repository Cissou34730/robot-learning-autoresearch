"""PI and analyst prompts. The wording is campaign-facing and must not drift."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from runner.launcher import pstext
from runner.launcher.pstext import field, items, text
from runner.launcher.summaries import completed_events, latest_session_result

RECIPE_DEVELOPMENT_OBJECTIVE = (
    "Deliver a recipe that learns and supports the startup phase. "
    "Build it from the knowledge gained across all tested variants. "
    "Combine the design choices supported by the results. "
    "Measure the resulting recipe to demonstrate learning progress. "
    "The section 'Recipe-development session' of "
    "contracts/program.md defines this phase."
)
STARTUP_OBJECTIVE = (
    "Establish the initial scientific direction, the tools and the first useful "
    "investigation from the selected recipe. The section 'Startup session' "
    "of contracts/program.md defines this session."
)
GOAL_REVIEW_OBJECTIVE = (
    "Use the completed evidence to update the scientific direction toward the "
    "goal. Correct inherited interpretations, research constraints or proposed "
    "questions when the existing evidence warrants it. Request measurements when "
    "they resolve an uncertainty or develop the method. Compare the two actions "
    "that the section 'Goal-review session' of contracts/program.md defines, and "
    "choose one: request the official assessment, whose pass or fail result ends "
    "this campaign, or open one bounded inquiry about the gap to the goal."
)
# The PowerShell here-string carried the checkout's CRLF line endings; keep them.
SCIENTIFIC_MODEL_OBJECTIVE = """Construct the physical and scientific model of the robot, of the task and of the learning problem. The scientific model exists before any training or campaign evidence.

Work from first principles and from the human-owned definitions of the robot, the simulator and the task. Explain the robot as an embodied dynamical system. Show how its morphology, actuation, sensing, control loop, simulator and task geometry together determine the behaviors that are possible, constrained or scientifically uncertain.

Build a scientific model of the system. The scientific model explains mechanisms. It gives the reasons behind the behavior. It goes beyond a list of components or a summary of the repository.

Analyze these items from first principles and from the human-owned definitions:

* the morphology, the degrees of freedom, the geometry, the reachable workspace, the joint constraints and the relevant kinematic structure of the robot.
* the actuation model, and how commanded actions produce physical motion over time.
* the dynamic properties of the simulated robot that materially affect behavior, including timing, damping, inertia and control authority.
* the initial physical state, and how it shapes the problem that the controller must solve.
* the geometry and the physical requirements of the task.
* the coupled physical capabilities that success requires, including reaching, trajectory control, convergence and stabilization, and the physically justified interactions between them.
* the sensing and observation model: which physical state is observable, which is derived, which is ambiguous and which is unavailable.
* the relation between observation, control action, robot motion and episode outcome.
* the alternative physical configurations or solutions available to the robot.
* the invariances of the definitions, and what each makes equal or different across configurations, targets and behavior.
* the physical, kinematic, dynamic, control and observability constraints that create qualitatively different classes of behavior or failure.
* the physical quantities, across the complete behavior, that are scientifically meaningful for understanding the robot.

The PI trains the policy with reinforcement learning, from the starting recipe that contracts/scenario.md describes. Analyze the learning problem that the starting recipe and the task create:

* how the transformation of the network output into the motor command affects exploration, the motion that random network outputs produce and the speed of learning.
* how the next variant decision and the observed learning dynamics inform the training length and the limits of a weak result.
* the quantities in the training log that show progress before task success occurs.
* for each reward term that you consider, the behavior that the term makes cheapest for the policy, including behavior that collects reward without task success.
* the relation between the reward, the end of the episode, the hold requirement and the discount factor.
* the design choices where the analysis cannot tell before training which option the robot learns better.

Propose a first reward under the heading `### Proposed first reward` in the register Decision-relevant synthesis. Give each term as a formula of the quantities that robot_learning/training/reward.py receives, with its weight. For each term, state the behavior that it encourages, the behavior that it makes cheapest and the reason for its weight. State the observations in the first training runs that can show that the reward is wrong. The PI decides whether to implement or revise the proposal. Do not write code.

Propose the first variants for quick learning tests under `### Proposed design variants` in the register Decision-relevant synthesis. A variant is a recipe that tests a proposed method. Differences between variants follow from the scientific question. A variant can change any PI-owned source file and any parameter.

Propose an initial scientific question for startup in this section. Explain how the first variants can help develop a recipe that supports this question.

For each variant, state the recipe question, the proposed differences and their physical or learning reasons. Explain the behavior that you expect and the evidence that can change the next recipe decision. Explain how observed learning can inform the training length for that test. Keep what the definitions establish separate from what only a comparison can resolve.

For each consequential physical implication and each unknown, state:

1. The research decisions that it could change.
2. The assumptions on which that relevance depends.
3. The source references in the implementation or in the contracts.
4. The observation or the evidence that would support it, weaken it or revise it.

The scientific model states consequences, proposals and the evidence that discriminates between them. The PI selects all interventions and the method.

End with a substantive section with the heading `## Decision-relevant synthesis`. Select only the physical consequences and the unknowns that are most likely to change the first decisions of the campaign, including the design and the interpretation of the first measurements. Include the invariances of the definitions, and the outcomes that they predict to be equal when the episode start and the target are transformed the same way. A measured difference between such outcomes, beyond sampling variation, is evidence about the policy, not about the task. For each selected item, give these four points in compact form: the decisions that it could change, its assumptions, its source references and its discriminating evidence.

The PI receives this section and the full scientific model in the recipe-development session. The PI uses quick tests to develop a recipe that learns and supports your initial scientific question. The PI creates further variants from the test results.

The recipe uses knowledge across all tested variants. The PI combines design choices supported by the results. The PI measures the resulting recipe to demonstrate learning progress. The startup session then receives the scientific model and the completed recipe-development record. The PI establishes the initial scientific direction and the first useful investigation from the selected recipe.

The final result is a compact and substantive scientific model. It explains how the complete coupled system works, physically and scientifically.""".replace(
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
        f"Advance {text(inquiry_id)} with a session-sized deliverable. The "
        "deliverable does not need to be a complete answer to the inquiry. Choose "
        "the deliverable from the completed evidence and the remaining scientific "
        "question."
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
        return f"The latest session record cites: {pstext.join(references, ', ')}."
    best_known = field(field(state, "model_roles"), "best_known")
    if pstext.truthy(best_known):
        return (
            f"{text(best_known)} has the explicit best-known role. Read its "
            "referenced measurements in campaigns/brief.md."
        )
    if completed_events(state):
        return (
            "campaigns/brief.md contains the evidence of completed operations. No "
            "candidate has the best-known role."
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
        return (
            "The inquiry is closed. Preserve its outcome and the resulting campaign "
            "decision."
        )
    return (
        "None. Before you choose the official assessment or one bounded inquiry, "
        "you can measure and give roles that the evidence supports."
    )


def _handoff_context(
    state: dict, kind: object, checkpoint: object, synthesis: str
) -> list[str]:
    inquiry = field(state, "active_inquiry")
    recipe_development = field(state, "recipe_development")
    if pstext.same(kind, "startup") and pstext.truthy(recipe_development):
        return [
            (
                "Completed recipe-development session record, unchanged:\n"
                f"{_FENCE}json\n"
                f"{json.dumps(recipe_development, ensure_ascii=False, indent=2)}\n"
                f"{_FENCE}"
            ),
            (
                "Continue from the selected recipe, its measured differences and "
                "the unresolved alternatives in this record. The record stays "
                "fixed. Its scientific judgments remain revisable from evidence."
            ),
        ]
    if pstext.same(kind, "goal_review") and pstext.truthy(checkpoint):
        return [
            (
                "This is the restored scientific handoff from your previous session. "
                "It is the current scientific state, not the opinion of another PI. "
                "The current scientific understanding below is the synthesis of that "
                "session, word for word."
            ),
            (
                "Proposed question for this goal-review session, word for word:\n"
                f"{text(field(checkpoint, 'next_question'))}"
            ),
            (
                "Continue from the completed evidence. Treat inherited "
                "interpretations, research constraints, priorities and proposed next "
                "actions as revisable scientific judgments. Correct an interpretation "
                "that the evidence does not support, or a question that the available "
                "evidence already settles. Record the correction and its basis."
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
        lines.append("Continue the bounded work from the completed evidence.")
        return lines
    return []


def _decision_guidance(state: dict, kind: object) -> list[str]:
    if pstext.same(kind, "recipe_development"):
        return [
            (
                "Before training, state your comparison plan. Explain the recipe "
                "question, why you chose each variant and the behavior you expect. "
                "State the observations of robot behavior needed to answer the "
                "recipe question. "
                "State what the comparison can distinguish and what it cannot.\n\n"
                "State the training length and justify it for this test. Explain "
                "how the results will change your next decision. Use observed "
                "behavior to test your predictions and guide the explanation and "
                "the next recipe decision."
            ),
            (
                "Identify the conditions in which each change can affect robot "
                "behavior. Before you interpret its effect, check that the "
                "implementation includes the intended change. Check from existing "
                "evidence that the test reached those conditions. An inactive "
                "change does not establish that the change has no benefit. "
                "An active change with no benefit is a valid null result."
            ),
            (
                "Use short training tests. After each test, state what you "
                "learned and why you keep or revise each variant. Update the plan "
                "before further training. Create further variants from the test "
                "results. Each variant can continue from its own saved training "
                "checkpoint."
            ),
            (
                "Fresh training of the same recipe can vary. If this variation "
                "can affect candidate selection or your next decision, repeat "
                "training to resolve that uncertainty. Match the effort to the "
                "uncertainty that affects the decision. State the remaining "
                "uncertainty before you attribute differences to a design choice."
            ),
            (
                "Deliver a recipe that learns and supports the startup phase. "
                "Build it from the knowledge gained across all tested variants. "
                "Combine the design choices supported by the results. "
                "Measure the resulting recipe to demonstrate learning progress."
            ),
            (
                "Compare the task behavior of saved candidates from different "
                "training points as needed to show learning. State what improved. "
                "Use this evidence to judge the learning progress of the resulting "
                "recipe."
            ),
            (
                "In `current_synthesis`, record the resulting recipe and the "
                "evidence of learning. Separate the candidate choice from "
                "conclusions about design choices. State which contributions from "
                "the tested variants the evidence supports and which remain "
                "unresolved. You can choose the strongest candidate while a design "
                "choice's benefit remains uncertain. State the questions that the tests "
                "answered. Cite supporting operations in `evidence_references`."
            ),
            (
                "Use `decision_frontier` for open questions and discriminating "
                "evidence. Set `next_question` to the next investigation for "
                "startup. In `next_direction_or_closure`, explain how the recipe "
                "supports the analyst's initial scientific investigation."
            ),
        ]
    goal_review = pstext.same(kind, "goal_review")
    lines = [
        "Compare the risk of the official assessment, given the residual failures "
        "that you have not explained, with what one more inquiry can learn about "
        "them. Use the completed evidence and its limits for both actions. Explain "
        "why the chosen action is preferable now."
        if goal_review
        else "State the explanation or the unresolved distinction that the operation "
        "tests. A development step states the explanation that motivates it. State "
        "how its result could produce or select a better candidate.",
        (
            "Review the completed evidence, the relevant learning trajectory and the "
            "unmeasured candidates."
        ),
        (
            "Choose the candidate and the operation whose result would most improve "
            "your next decision toward the goal."
        ),
    ]
    if goal_review:
        lines += [
            (
                "For a measurement, explain how its possible results would affect your "
                "choice between the two actions."
            ),
            (
                "Record the chosen action, the official assessment or the inquiry, and "
                "its reason from the evidence."
            ),
            (
                "In the reason of the chosen operation, preserve the relevant residual "
                "failures, the counterevidence and the uncertainty."
            ),
            (
                "In a goal-review session, next_question must be exactly the question "
                "of the inquiry that you opened in this session."
            ),
        ]
    else:
        lines.append(
            "Explain how the consequential possible results of the selected "
            "operation would affect the direction."
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
            "When evidence resolves or redirects the active inquiry, record that "
            "decision explicitly. Do not drift to another question."
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
            "next goal-review session. In that session, you can revise or decline it "
            "with the completed evidence that is already available."
        )
    return lines


def _training_allocation(
    kind: object, transition: Transition | None, context: PromptContext
) -> str:
    if transition is not None or pstext.same(kind, "goal_review"):
        return ""
    return (
        f"Training length: for each run, you choose `steps` between "
        f"{context.timesteps:,} and {context.max_timesteps:,}. One "
        "training operation can train 2 to 4 design variants at the same time, "
        "with the same seed and steps."
    )


def _submission_guidance(availability: dict, transition: Transition | None) -> str:
    if transition is not None:
        return (
            "Use the session record format in contracts/instruments.md in the "
            "campaign reference. Preserve the decision of this transition, the "
            "evidence, the remaining gap to the goal and the next direction."
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
        "No session record contains your interpretation of the goal gap yet.",
    )
    frontier = (
        text(field(checkpoint, "decision_frontier"))
        if pstext.truthy(checkpoint)
        else "No session record contains a scientific decision frontier yet."
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
        "Start with campaigns/brief.md and the latest session record. Read other "
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
            "campaigns/brief.md is at the end. The summary of the latest session "
            "record is above. Read other evidence when the scientific question "
            "needs it."
        )
    sections = [
        role_line,
        *model_file,
        *_handoff_context(state, kind, checkpoint, synthesis),
        (
            "Build the first recipe through quick iterations on variants. "
            "Start from the scientific model and the analyst's proposals. You "
            "decide which proposals to implement and how to revise them. The "
            "proposed first reward has the same status as the other proposals. "
            "A variant can change any PI-owned source file and any parameter. "
            "\n\nStart from the robot and the physical behavior that the task requires. "
            "Use the scientific model to explain how observations and motor commands "
            "relate to that behavior. From this explanation, identify what the policy "
            "must learn and how the recipe can help it. Develop the reward and "
            "training environment together from this explanation. Treat their "
            "current design as a hypothesis.\n\n"
            "Explain how the reward favors progress toward the complete task "
            "behavior. Judge its incentives with the discount factor and "
            "episode-end conditions that training actually uses.\n\n"
            "Explain how the training environment gives the policy the information "
            "and experience needed to learn that behavior. Identify what the policy "
            "must infer from its observations. Predict how the environment design "
            "affects that learning.\n\n"
            "Use observed robot behavior to test these explanations. Predict the "
            "effect of each proposed change on the robot's behavior. Use variant "
            "comparisons to test that prediction and guide the next recipe decision. "
            "Revise the design choices "
            "that observed behavior does not support."
            if pstext.same(kind, "recipe_development")
            else ""
        ),
        (
            (
                "From the selected recipe, the recipe-development record and the "
                "scientific model, establish the initial scientific direction "
                "toward the goal. Develop the tools that this direction needs. "
                "Choose the first useful investigation and explain how its "
                "possible findings can change the direction."
                if pstext.truthy(field(state, "recipe_development"))
                else "From the decision-relevant synthesis of the scientific model, select the "
                "scientific distinction or the capability question that should determine "
                "the initial direction. State which findings would change that decision, "
                "and how the first action follows from it. Treat the interpretations of "
                "the scientific model as revisable in light of evidence. Do not require a "
                "measurement only to restate the scientific model."
            )
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
        f"Scientific decision frontier: {frontier}",
        (
            f"Active inquiry: {_inquiry_line(state, transition)}"
            if kind not in {"recipe_development", "startup"}
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
                "This failure is execution history, not scientific evidence. Diagnose "
                "the cause and correct the scientific implementation, or choose "
                "another action. Call submit_operation with request=null to accept the "
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
                "The code in robot_learning/ is the starting recipe that "
                "contracts/scenario.md describes. Its design choices are not "
                "properties of the robot. Mark each statement that comes from them "
                "as a design choice."
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
