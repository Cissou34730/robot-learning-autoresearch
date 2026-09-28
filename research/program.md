# Robot AutoResearch

## Scientific identity

The campaign has one scientific actor: the **Principal Investigator (PI)**.
The PI combines robotics, reinforcement learning, control, simulation, system
identification, experimental design, and scientific software. Scientific
direction, inquiry design, scientific implementation, tool construction,
measurement and training design, evidence interpretation, and goal-progress
assessment belong to that one role.

The Runner is separate. It validates operation shapes and protected
boundaries, executes requested heavy operations, records facts, publishes
artifacts, and recovers transactions. It does not judge scientific adequacy.

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
training is not the campaign structure, and an inquiry is not the campaign.

## Campaign startup

A fresh schema-6 campaign begins with a dedicated preliminary PI session. That
session constructs `research/scientific_model.md` from the human-authored robot,
physics, sensing, task, and assessment implementation. The model separates
established facts, physical consequences, and unknowns. The Runner publishes
the exact validated document before any scientific session or operation begins.

There is no mandatory baseline phase. Working and best-known roles remain empty
until the PI explicitly assigns candidates using completed evidence.

## Goal review

When no inquiry is active, a bounded goal-review session reaches one of three
campaign-level decisions:

- request the official assessment for the explicit best-known model;
- open one bounded inquiry connected directly to the current goal gap; or
- conclude that no credible route remains.

Opening an inquiry records its question, connection to the human goal, closure
condition, and rationale. The opening goal-review session then ends at a
durable checkpoint, and a fresh inquiry session continues from that state.

`MaxInquiries` defaults to 15. It is an unattended guard on creation of another
inquiry only. It is not a training limit, scientific stopping rule, target, or
automatic conclusion.

## Inquiry work

An inquiry is a temporary question or obstacle whose resolution can change the
route toward the human goal. Its bounded sessions can inspect evidence, change
PI-owned scientific code, build diagnostics, request measurements, request
training, manage model roles, restore a saved recipe, reframe the inquiry, or
close it.

Measurement and training are peer instruments. Either returns factual results
to the same active bounded session. There is no mandatory post-training phase,
forced evaluation, experiment-bound decision, or Runner-owned method
lifecycle. A PI-authored method label may organize related work in a
checkpoint, but it creates no lifecycle gate.

An inquiry closes when its closure condition is met, evidence redirects the
campaign, the question is no longer a credible route, or it has produced the
actionable result for which it was opened. Closure is independent of method
state. After the closing session checkpoints its decision, the campaign returns
to goal review.

## Bounded scientific sessions

A scientific session is bounded by one coherent objective rather than by an
operation count. It can span several Runner round trips under the same backend
session identity while active. The session ends only when the PI submits a
durable checkpoint or makes a terminal goal-level decision.

The checkpoint carries the human-goal connection, current gap and synthesis,
evidence references, decision frontier, completed operations, candidate and
model-role situation, next direction or closure assessment, and cumulative
resource use. A later fresh session continues from that durable state rather
than from campaign-long conversation memory.

The lifecycle has no SDK token guard, compaction controller, or persisted
campaign-long conversation.

## Evidence and model roles

Operation identities are independent: measurements use `M#`, training uses
`T#`, and other lifecycle events use `E#`. Completed events and artifacts form
the factual campaign record.

Development measurements support PI judgment but do not declare the official
goal reached. Working, best-known, and retained roles are explicit,
evidence-backed operations. Training never changes a role implicitly.

The official assessment is a one-time Runner-owned transition after the PI
requests it. Its recorded pass or fail result ends the campaign. A conclusion
that no credible route remains also ends the campaign without assessment.

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
