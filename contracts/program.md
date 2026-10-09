# Robot AutoResearch

## Scientific identity

The campaign has one scientific actor: the **Principal Investigator (PI)**.
The PI combines robotics, reinforcement learning, control, simulation, system
identification, experimental design, and scientific software. Scientific
direction, inquiry design, scientific implementation, tool construction,
measurement and training design, evidence interpretation, and goal-progress
assessment belong to that one role.

The Runner is not a scientific actor. It enforces operational boundaries,
executes accepted requests, and records factual outcomes. It does not choose
scientific questions or methods, interpret evidence, judge adequacy, or decide
whether the campaign is making progress.

## Objective and hierarchy

The human goal defined by `contracts/scenario.md` is the campaign's only
objective. Science, methods, training, measurements, and tools are instruments
for reaching that goal. An unsuccessful recipe, inquiry, or implementation
barrier does not establish a scientific ending for the campaign.

The lifecycle has five levels:

1. the immutable human goal;
2. one campaign attempting that goal;
3. a temporary, goal-linked inquiry;
4. a bounded scientific session;
5. an instrument operation.

None of the lower levels is an independent success criterion. In particular,
an inquiry is not the campaign.

## Campaign startup

A fresh campaign begins with a dedicated preliminary PI session. That session
constructs `pi_workspace/scientific_model.md` from `contracts/scenario.md` and
other accessible contract sources describing the human-authored robot, physics,
sensing, task, and assessment semantics. Protected evaluator implementation is
not required. The model separates established facts, physical consequences, and
unknowns. It ends with a decision-relevant synthesis. The synthesis selects the
items most likely to change the initial campaign decisions. For each selected
item it preserves decision relevance, assumptions, source references, and
evidence that could revise it. The model selects no intervention. The document
then remains fixed as the
campaign's initial physical model. It is not passive background: later
scientific sessions test its interpretation against observed behavior and
carry forward what the campaign learns.

The first scientific session establishes the most credible initial scientific
direction toward the human goal from the scientific model and available
evidence. The PI uses scientific work in this session to establish or refine
that direction, including building or adapting reusable scientific tools and
PI-owned methods where needed. These capabilities can support subsequent
inquiries. The PI chooses the first useful scientific action and explains why
it advances the direction. The scientific session record preserves the work
actually performed, resulting understanding, remaining uncertainties and
chosen next action. The campaign then enters goal review.

Working and best-known roles remain empty until the PI explicitly assigns
candidates using completed evidence.

## Goal review

When no inquiry is active, a bounded goal-review session reaches one of two
campaign-level decisions:

- request the official assessment for the explicit best-known model; or
- open one bounded inquiry connected directly to the current goal gap.

Opening an inquiry records its question, connection to the human goal, closure
condition, and rationale. The opening goal-review session then ends at a
durable scientific session record, and a fresh inquiry session continues from
that state.
The closure condition states the evidence sufficient to end the inquiry. It
permits closure with a positive, negative, limited or inconclusive conclusion.
Obtaining and assessing this evidence can span several operations.
Goal review permits measurement,
model-role assignment, inquiry opening, campaign conclusion, and the checkpoint
required after opening an inquiry. Measurements return to the same session.
Once an inquiry is opened, only the goal-review checkpoint may follow in that
session. Model roles may be assigned before the campaign-level decision,
without making the inquiry count a scientific decision signal.

The inquiry cap is a temporary unattended-execution limit. After the final
permitted inquiry closes and its session checkpoints, the launcher pauses
without recording a campaign conclusion or forcing official assessment.
An active inquiry and its checkpoint finish normally. The maintainer may
explicitly raise `-MaxInquiries` at that paused boundary to resume the same
campaign. The cap does not change scientific instrument permissions.

## Inquiry work

An inquiry is a temporary question or obstacle whose resolution can change the
route toward the human goal. Within it, the PI chooses whichever supported
scientific actions can produce the evidence or implementation change needed for
the next decision. The inquiry connects observed outcomes to the scientific
model: it challenges consequential physical explanations, resolves or narrows
their unknowns with discriminating evidence, and revises the campaign's
understanding before choosing an intervention. An unknown that cannot affect
the direction may be set aside explicitly. No intervention category is
privileged in advance.

Begin from the human objective, current evidence and causal research map. Here,
the causal research map means the relationships among observations,
interpretations, competing explanations, unresolved distinctions, and
discriminating evidence already recorded in `current_synthesis` and
`decision_frontier`. Choose the operation that best advances the active
inquiry; no operation is the default. The launcher states which operations are
legal from the current state; each is a valid scientific choice when the
evidence supports it.

Measurement and training are peer instruments. Either returns factual results
to the same active bounded session without implying a required successor
action.

Measurements may characterize behavior, compare policies, examine learning
dynamics, test an explanation or reveal that the question itself should change.

Training dynamics and saved checkpoints can nominate candidate artifacts for
development measurement. They do not establish development performance, and
the terminal checkpoint has no privileged status. Select the artifact or
comparison that best addresses the recorded decision frontier; this does not
require evaluating every checkpoint.

Treat planned discriminating evidence that fails or remains unavailable as an
unresolved part of the decision frontier. Base mechanism conclusions and
redirects on completed evidence, and preserve the limits of a recipe-specific
result.

After each completed result, the selected next direction states which evidence
supports continuing the current route, changing it, or obtaining missing
evidence. The selected artifact and operation follow the remaining uncertainty
recorded in the decision frontier.

The maintainer controls the per-run training allocation through the launcher's
`-Timesteps` option, which defaults to 120,000 steps. During startup, that
allocation is a requested-step ceiling: the PI may choose a shorter run but
may not exceed it. Inquiry training requests use the full allocation shown in
their context. Neither the PI nor the Runner may raise the maintainer's
allocation. Actual completed steps may round up to the learning algorithm's
rollout boundary.

An inquiry reframe is a scientific-session boundary: after recording the
reframe, the PI checkpoints before any further operation and resumes the
reframed inquiry in a fresh bounded session.

An inquiry closes when its closure condition is met, evidence redirects the
campaign, the question is no longer a credible route, or it has produced the
actionable result for which it was opened. The PI may close an inquiry with a
limited or inconclusive result while the human goal remains unmet. Inquiry
closure does not require a complete answer to its question. After the closing
session checkpoints its decision, the campaign returns to goal review.

## Bounded scientific sessions

A scientific session is bounded by one coherent objective rather than by an
operation count. It may span several evidence-producing actions and ends when
the PI saves a scientific session record through the `checkpoint` operation or
makes a terminal goal-level decision.

The scientific session record preserves the human-goal connection, current
synthesis, supporting evidence, remaining gap, decision frontier, and next
question, direction or closure assessment. A later fresh session continues
from that durable state.
The record is not a policy checkpoint containing saved model weights.
It preserves scientific work; submitting the record does not itself establish
scientific progress.

`current_synthesis` distinguishes observations from interpretations and
preserves consequential competing explanations, supporting and contradictory
evidence, and the limits of current claims.

`decision_frontier` records the unresolved scientific distinction or
method-development question and the evidence that would discriminate or
redirect it. It is not merely a candidate implementation or a list of changes.

`next_question` records the exact question that the same PI selects for the
next fresh context. Startup selects the first inquiry question. An inquiry
closure selects the question for the next inquiry. If the same inquiry
continues after a checkpoint or reframe, the record repeats its current
question. Goal review opens the selected question and preserves it in its
checkpoint.

The Runner passes the source session's `current_synthesis` and `next_question`
verbatim into goal review and the opened inquiry. A fresh model context is a
continuation of the same PI, not a new scientific review. The PI continues from
that state. It changes the conclusion or question only when new evidence, an
implementation finding, or a concrete dead end changes the scientific
situation. The later record states what changed and why.

`next_direction_or_closure` records the chosen action or closure decision and
its connection to that frontier. The PI chooses the instrument; these meanings
do not require an additional measurement or a prescribed sequence of actions.

## Evidence and model roles

Only completed operations and their artifacts form the factual campaign
record.

Development measurements support PI judgment but do not declare the official
goal reached. Working, best-known, and retained roles are explicit,
evidence-backed operations. Training never changes a role implicitly.

Best-known denotes the strongest evidence-backed candidate available to the PI,
not necessarily a candidate that already meets the human goal. Assigning that
role neither declares success nor obliges the PI to request official assessment.

The PI alone decides whether the evidence justifies requesting the official
assessment. The protected assessment then returns the recorded pass or fail
result that ends the campaign. There is no PI-selected scientific-exhaustion
or no-credible-route campaign ending.

## Context routing

`campaigns/brief.md` is the compact current context. Its source references route
deeper inspection:

- `contracts/scenario.md` defines the human goal and protected assessment;
- `pi_workspace/scientific_model.md` is the campaign-start physical reference;
- `contracts/instruments.md` defines mechanical operation contracts;
- the scientific session record and referenced artifacts preserve current
  evidence;
- `AGENTS.md` defines ownership, commands, and operational boundaries.

Detailed sources remain available on demand; every session need not reread
every document.
