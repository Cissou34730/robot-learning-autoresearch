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

The human goal defined by `research/scenario.md` is the campaign's only
objective. Science, methods, training, measurements, and tools are instruments
for reaching that goal or establishing that no credible route remains.

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
constructs `research/scientific_model.md` from the human-authored robot,
physics, sensing, task, and assessment implementation. The model separates
established facts, physical consequences, and unknowns, then remains fixed as
the campaign's initial physical model. It is not passive background: later
scientific sessions test its interpretation against observed behavior and
carry forward what the campaign learns.

The first scientific session establishes the most credible initial direction
from the human goal and the scientific model. Its physical consequences and
unknowns support competing mechanistic explanations. When an unresolved
mechanism could change the scientific direction, the PI seeks evidence that
discriminates between those explanations rather than merely citing the model
or defaulting to a local adjustment. Evidence produced during that work can
refine the direction before the session ends with a checkpoint and the
campaign enters goal review.

Working and best-known roles remain empty until the PI explicitly assigns
candidates using completed evidence.

## Goal review

When no inquiry is active, a bounded goal-review session reaches one of three
campaign-level decisions:

- request the official assessment for the explicit best-known model;
- open one bounded inquiry connected directly to the current goal gap; or
- conclude that no credible route remains.

Opening an inquiry records its question, connection to the human goal, closure
condition, and rationale. The opening goal-review session then ends at a
durable checkpoint, and a fresh inquiry session continues from that state.
Goal review permits model-role assignment, inquiry opening, campaign conclusion,
and checkpoint. Model roles may be assigned before the campaign-level decision,
including when no further inquiry can be opened.

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

Measurement and training are peer instruments. Either returns factual results
to the same active bounded session without implying a required successor
action.

An inquiry reframe is a scientific-session boundary: after recording the
reframe, the PI checkpoints before any further operation and resumes the
reframed inquiry in a fresh bounded session.

An inquiry closes when its closure condition is met, evidence redirects the
campaign, the question is no longer a credible route, or it has produced the
actionable result for which it was opened. After the closing session
checkpoints its decision, the campaign returns to goal review.

## Bounded scientific sessions

A scientific session is bounded by one coherent objective rather than by an
operation count. It may span several evidence-producing actions and ends when
the PI records a durable checkpoint or makes a terminal goal-level decision.

The checkpoint preserves the human-goal connection, current synthesis,
supporting evidence, remaining gap, decision frontier, and next direction or
closure assessment. A later fresh session continues from that durable state.

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
result that ends the campaign. The PI may instead conclude that no credible
route remains, ending the campaign without assessment.

## Context routing

`research/brief.md` is the compact current context. Its source references route
deeper inspection:

- `research/scenario.md` defines the human goal and protected assessment;
- `research/scientific_model.md` is the campaign-start physical reference;
- `research/instruments.md` defines mechanical operation contracts;
- the PI checkpoint and referenced artifacts preserve current evidence;
- `AGENTS.md` defines ownership, commands, and operational boundaries.

Detailed sources remain available on demand; every session need not reread
every document.
