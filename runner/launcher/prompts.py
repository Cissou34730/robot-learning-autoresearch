"""PI and analyst prompts. The wording is campaign-facing and must not drift."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runner import protocol
from runner.execution import training_step_range
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
    "Establish the initial scientific direction, as the section 'Startup session' "
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
SCIENTIFIC_MODEL_OBJECTIVE = """Construct the scientific model of the robot, the task and the learning problem. The scientific model exists before training or campaign evidence.

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
* the alternative physical configurations or solutions available to the robot, for example multiple kinematic solutions.
* the invariances of the definitions, for example symmetries and conserved quantities, and what each makes equal or different across configurations, targets and behavior.
* the physical, kinematic, dynamic, control and observability constraints that create qualitatively different classes of behavior or failure.
* the physical quantities, across the complete behavior, that are scientifically meaningful for understanding the robot.

Analyze the learning problem that the task and the starting recipe create. Explain what the policy must infer from its observations. Relate network outputs to motor commands, robot motion and task behavior. Distinguish what the policy must learn from what the method supplies.

Explain how exploration and the initial state affect the experience available to the policy. Relate the training distribution to the task. Explain how the training dynamics can inform the training length. State what a short training result can establish and what remains uncertain.

Relate the reward to the discount factor, episode-end conditions and complete task behavior. Identify incentives that can increase return without task success. State the assumptions that make each proposed learning mechanism credible.

For each consequential physical implication and each unknown, state:

1. The research decisions that it could change.
2. The assumptions on which that relevance depends.
3. The source references in the implementation or in the contracts.
4. The observation or the evidence that would support it, weaken it or revise it.

The scientific model separates physical consequences, learning hypotheses and design proposals. The PI selects the interventions.

End with a substantive section with the heading `## Decision-relevant synthesis`. Select the physical consequences and learning questions most likely to change the first decisions of the campaign. Include the design and interpretation of the first measurements.

Include the invariances of the definitions. State which outcomes the definitions predict to be equal under a common transformation. Apply that transformation to the episode start and target. A difference beyond sampling variation is evidence about the policy, not the task. For each selected item, state its decision relevance, assumptions, source references and discriminating evidence.

Under `### Proposed first reward`, propose a reward for the starting recipe that contracts/scenario.md describes. Give the formula and weight of each term. Use quantities available to robot_learning/training/reward.py. Explain how the terms favor complete task behavior with the actual discount factor and episode-end conditions. The proposal can retain the existing reward when the analysis supports it.

Under `### Proposed design variants`, propose designs that test the learning hypotheses. For each design, state the recipe question, source and parameter changes, physical or learning reason, and expected robot behavior. State the observations that can distinguish the designs. A variant can change any PI-owned source file and any parameter. These proposals are hypotheses, not evidence. The PI decides which proposals to implement and can revise them.""".replace(
    "\n", "\r\n"
)
_SCIENTIFIC_MODEL_HANDOFF = {
    "included": """Propose a recipe-development question that the first variants can test. Explain how its answer can support the recipe decision. The PI receives the scientific model and proposals in the recipe-development session. The PI selects the interventions.

The recipe uses knowledge across all tested variants. The PI combines design choices supported by the results. The PI measures the resulting recipe to demonstrate learning progress.

The startup session then receives the same scientific model and the delivered recipe. It starts with fresh scientific state and no recipe-development evidence. The PI establishes the initial scientific direction and the first useful investigation from the delivered recipe.""",
    "skipped": """Propose an initial scientific question for startup from the starting recipe and the analysis. The PI receives the scientific model and proposals in the startup session. The PI decides which proposals to use and selects the initial direction.""",
}
_SCIENTIFIC_MODEL_RESULT = "The result is a scientific model with physical and learning analysis, initial recipe proposals and a scientific question. It separates established facts from hypotheses."


def scientific_model_objective(recipe_phase: str) -> str:
    return "\r\n\r\n".join(
        [
            SCIENTIFIC_MODEL_OBJECTIVE,
            _SCIENTIFIC_MODEL_HANDOFF[recipe_phase].replace("\n", "\r\n"),
            _SCIENTIFIC_MODEL_RESULT,
        ]
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


def _recipe_files(campaign_root: Path) -> list[str]:
    from runner.copilot.copilot_scoped_search import linked_path

    package = campaign_root / "robot_learning"
    files = []
    for source in sorted(package.rglob("*.py")):
        relative = source.relative_to(campaign_root).as_posix()
        if any(
            part in {"variants", "lab", "__pycache__", ".mypy_cache", ".pytest_cache"}
            for part in source.relative_to(package).parts
        ) or linked_path(campaign_root, source):
            continue
        if (
            protocol.is_researcher_owned(relative)
            or relative in protocol.PROTECTED_BENCHMARK_PATHS
        ):
            files.append(relative)
    parameters = "robot_learning/training/current_params.json"
    if (campaign_root / parameters).is_file() and not linked_path(
        campaign_root, campaign_root / parameters
    ):
        files.append(parameters)
    return files


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
    if pstext.same(kind, "startup") and state.get("recipe_phase") == "included":
        return [
            (
                "Startup begins from the delivered recipe and the same accepted "
                "scientific model. Its scientific state is fresh. "
                "Recipe-development records and artifacts are not available in "
                "this session. For the first training run, use the delivered recipe "
                "from fresh initialization. The session's allocation applies to "
                "each training run."
            )
        ]
    if pstext.same(kind, "startup"):
        return [
            (
                "The inherited recipe is the reference for your first comparison. A "
                "first experiment that changes several parts of the recipe at once "
                "gives a result that you cannot attribute to any one of them. After "
                "the first comparison, choose the size of a change from the "
                "explanation that it tests."
            )
        ]
    inquiry = field(state, "active_inquiry")
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
                "training to resolve that uncertainty. State the remaining "
                "uncertainty before you attribute differences to a design choice."
            ),
            (
                "Deliver a recipe that learns and supports the startup phase. "
                "Build it from the knowledge gained across all tested variants. "
                "Combine the design choices supported by the results. "
                "Measure the resulting recipe to demonstrate learning progress."
            ),
            (
                "Consolidate the recipe in the canonical Python source files and "
                "parameters. Encode each training stage and its transitions in "
                "the recipe source. The delivered recipe must train from fresh "
                "initialization without recipe-development artifacts. "
                "Recipe development ends when you select the method for startup "
                "from the completed evidence. You judge whether the evidence "
                "supports this selection. "
                "The Runner checks the files, not scientific adequacy."
            ),
            (
                "Startup receives only the delivered recipe and the same accepted "
                "scientific model. It does not receive trial scores, alternatives "
                "or session records. It does not receive training checkpoints, "
                "optimizer state or normalization state. Development candidates "
                "remain usable for tests and explicit recipe restoration during "
                "recipe development. They are unavailable after delivery."
            ),
            (
                "Compare the task behavior of saved candidates from different "
                "training points as needed to show learning. State what improved. "
                "Use this evidence to judge the learning progress of the resulting "
                "recipe."
            ),
            (
                "In `current_synthesis`, record the resulting recipe and the "
                "evidence of learning. State which contributions from "
                "the tested variants the evidence supports and which remain "
                "unresolved. State the questions that the tests "
                "answered. Cite supporting operations in `evidence_references`."
            ),
            (
                "Use `decision_frontier` for open questions and discriminating "
                "evidence. Set `next_question` to a remaining recipe-development "
                "question. This question belongs to the development record, not "
                "the startup plan. In `next_direction_or_closure`, explain how "
                "the delivered recipe supports startup."
            ),
            (
                "These fields preserve "
                "your validation and recipe-development history. "
                "Startup does not receive this record."
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
    if pstext.same(kind, "inquiry"):
        lines.append(
            "Before training, state what the run needs to reveal for the active "
            "inquiry. State the training length and justify it for this test. "
            "Use the available learning evidence to inform that choice. "
            "Explain how the results will change your next decision."
        )
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
    minimum, maximum = training_step_range(
        text(kind).lower(), context.timesteps, context.max_timesteps
    )
    if pstext.same(kind, "startup"):
        return f"Training allocation: up to {maximum} requested steps per run."
    if pstext.same(kind, "inquiry"):
        return (
            f"Training length: for each run, you choose `steps` between "
            f"{minimum:,} and {maximum:,}."
        )
    return (
        f"Training length: for each run, you choose `steps` between "
        f"{minimum:,} and {maximum:,}. One "
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
    if (
        state.get("campaign_phase") == "startup"
        and state.get("recipe_development") is not None
    ):
        raise RuntimeError("Recipe delivery must finish before a startup prompt.")
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
    if context_files and kind in {"recipe_development", "startup", "inquiry"}:
        context_files += _recipe_files(context.campaign_root)
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
        recipe_count = max(0, len(included) - 1)
        characters = len("".join(model_file + included))
        context_note = (
            "CONTEXT | first message includes pi_workspace/scientific_model.md, "
            "campaigns/brief.md"
            + (f", {recipe_count} recipe files" if recipe_count else "")
            + f" ({(characters + 500) // 1000}k chars)"
        )
        source_guidance = (
            "This message includes the scientific model and the current campaign "
            "files. The summary of the latest session "
            "record is above. Read other evidence when the scientific question "
            "needs it."
        )
    sections = [
        role_line,
        *model_file,
        *_handoff_context(state, kind, checkpoint, synthesis),
        (
            "Build the first recipe through quick iterations on variants. "
            "Start from the scientific model and the analyst's proposals. "
            "You decide the first recipe question and the variants that test it. "
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
            "From the decision-relevant synthesis of the scientific model, select the "
            "scientific distinction or the capability question that should determine "
            "the initial direction. State which findings would change that decision, "
            "and how the first action follows from it. Treat the interpretations of "
            "the scientific model as revisable in light of evidence. Do not require a "
            "measurement only to restate the scientific model."
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


def scientific_model_prompt(goal: str, recipe_phase: str) -> str:
    return "\n\n".join(
        [
            (
                "You are the robotics and simulation analyst that your system prompt "
                "describes."
            ),
            f"Goal: {goal}",
            f"Session objective: {scientific_model_objective(recipe_phase)}",
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
                "Separate source facts, physical implications and untested design "
                "proposals. Write the result to pi_workspace/scientific_model.md."
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
