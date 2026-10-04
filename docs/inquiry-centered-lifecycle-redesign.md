# Goal-Centered Inquiry Lifecycle Redesign

Status: revised after independent Opus 5.5 challenge and maintainer review.

This document describes a replacement for the current inquiry-centered
lifecycle. It is a design proposal only. It does not preserve compatibility
with the current campaign schema or attempt to resume the current campaign.

## Objective

The human goal is the campaign's only objective.

Scientific inquiry, measurements, methods, tools, training, and evaluations are
instruments for reaching that goal or establishing that no credible route
remains. Producing interesting science, accumulating knowledge, or completing a
method lifecycle is not an independent campaign success.

The redesign must remove training as the recurring center of the campaign
without replacing it with an equally self-serving scientific-process loop.

## Hierarchy

The lifecycle has five levels:

1. **Human goal**
   - Immutable and human-owned.
   - Defined by the protected scenario and official assessment contract.
2. **Campaign**
   - One attempt to satisfy the human goal.
   - Owns the baseline, evidence, model roles, inquiries, resource use, and
     terminal outcome.
3. **Inquiry**
   - A temporary bounded question or obstacle whose resolution is expected to
     change the route toward the human goal.
   - A campaign may contain sequential inquiries.
4. **Scientific session**
   - A bounded period of coherent work by one scientific actor.
   - May span multiple operations and Runner round trips.
5. **Instrument operation**
   - Coding, diagnostic-tool construction, measurement, training, comparison,
     lineage management, or another concrete scientific action.

An inquiry is not the campaign. A scientific session is not the inquiry. An
instrument is not the lifecycle.

## Scientific identity

Replace the ambiguous Researcher/principal-investigator split with one
consistently named scientific actor:

**Principal Investigator (PI)**

The PI owns:

- scientific direction;
- inquiry definition and revision;
- scientific coding within the allowed surface;
- diagnostic-tool construction;
- measurement design;
- training design;
- evidence interpretation;
- goal-progress assessment.

The Runner remains a separate non-scientific actor. It owns:

- lifecycle orchestration;
- validation of operation contracts;
- heavy operation execution;
- state persistence;
- transaction and crash recovery;
- artifact publication;
- protected ownership enforcement.

The PI retains the strong multidisciplinary persona that previously produced
the first significant scientific breakthrough. The persona must remain
imperative in the active prompt rather than existing only as informative
documentation.

## Campaign flow

### Campaign startup

1. Produce the scientific model of the robot and task.
2. Start an initial scientific session.
3. Let the PI establish the most credible initial direction from the human
   goal, the scientific model, and available evidence.
4. Let that session use scientific work to establish or refine that direction.

A baseline is not an architectural phase. A campaign may choose to train and
measure an initial reference policy, but `working` and `best_known` remain empty
until evidence supports assigning those roles. Future scenarios may begin with
tool, reward, representation, or method design before any training exists.

### Campaign-level goal review

At campaign level the PI chooses one of:

- request the official assessment because the goal is expected to be met;
- open a bounded inquiry addressing a credible obstacle to the goal;
- conclude that no credible route remains.

A goal-review session cannot checkpoint without making one of those decisions.
When it opens an inquiry, it checkpoints that decision and transitions to a
fresh inquiry session.

Opening an inquiry requires:

- a bounded question;
- a direct connection to the current gap from the human goal;
- a closure condition;
- a reason resolving the inquiry could change the route to the goal.

Scientific novelty or the possibility of learning more is insufficient.

### Inquiry work

An active inquiry is advanced through bounded scientific sessions. Training and
measurement are peer instruments. Neither has a privileged follow-up phase.

A scientific session may perform several coherent operations:

1. inspect evidence and implementation;
2. modify PI-owned scientific code;
3. build or revise diagnostic tools;
4. run permitted lightweight analysis;
5. request a Runner measurement;
6. receive and interpret the result;
7. revise a tool and measure again;
8. request training;
9. receive and interpret the training result;
10. update, reframe, or close the inquiry.

Every Runner result returns to the same bounded scientific session until that
session reaches a scientific checkpoint.

There is no mandatory post-training-analysis phase and no mandatory
experiment-bound method decision.

### Inquiry closure

An inquiry closes when:

- its closure condition is met;
- evidence redirects the campaign away from its question;
- it is no longer a credible route toward the human goal;
- or it produces the actionable result it was opened to obtain.

Inquiry closure is independent of method state.

After closure, the campaign returns to goal review. It does not automatically
open another inquiry or allocate training.

## Bounded multi-operation scientific sessions

A session is bounded by a coherent scientific objective, not by an arbitrary
operation count.

A session ends when:

- its bounded objective is answered;
- the inquiry must be materially reframed;
- it reaches a stable goal-level decision;
- a different perspective is required;
- or the PI chooses to preserve the work and continue later.

The lifecycle introduces no token threshold, SDK compaction controller, or
other session-management machinery. The PI writes a durable checkpoint at the
scientific boundary. A later fresh session continues from durable artifacts
rather than depending on campaign-long conversational memory.

This avoids both failed extremes:

- one session spanning an entire campaign or inquiry;
- one fresh session for every individual operation.

Validation correction and implementation repair may remain in the current
scientific session when they serve the same bounded objective. Otherwise a
fresh session receives the durable checkpoint and the factual error.

Remove:

- campaign-long inquiry session persistence;
- allocated/starting/started PI session state;
- resume-or-create as a campaign-science mechanism;
- silent context compaction;
- separate post-training scientific sessions.

## Durable inquiry checkpoint

Scientific continuity lives in an explicit PI-authored checkpoint, not in
conversation memory.

The checkpoint contains:

- the human-goal connection and current goal gap;
- inquiry question and closure condition;
- current synthesis grounded in evidence references;
- unresolved distinction or decision frontier;
- completed operations and factual outcomes;
- current candidates and model-role situation;
- the next credible direction or closure assessment;
- cumulative resource use relevant to campaign judgment.

The Runner validates structure and evidence references only. It never validates
scientific merit and never requires particular measurements, mechanisms, or
interventions.

## Goal-directed continuation and stopping

`MaxExperiments` becomes `MaxInquiries`, with a default of 15.

`MaxInquiries` is only an unattended safety guard against endless inquiry
creation. It is not:

- the human goal;
- a target number of inquiries;
- a scientific stopping rule;
- a reason to conclude;
- a training budget.

The active PI prompt contains imperative rules:

- The human goal is the only campaign objective.
- Choose the operation whose result would most improve the next decision toward
  the human goal.
- If no credible path remains, close the inquiry or conclude the campaign.
- When an inquiry closure condition is met, close or explicitly reframe it; do
  not silently drift.
- Before ending a scientific session, write a durable checkpoint describing
  goal progress, the remaining obstacle, supporting evidence, and the next
  campaign or inquiry decision.

If the PI rationalizes continuation without goal value, the prompt and
protocol are defective. A numeric experiment limit must not be used to hide
that defect.

## Methods

Remove the Runner-owned six-state method lifecycle:

- concept;
- development;
- mature;
- promoted;
- retained;
- abandoned.

Remove mandatory `method_decision` after training.

A method may remain as a PI-authored label grouping related scientific work,
for example:

```text
method: branch_aware_reach_hold
operations: T1, M2, T2
current interpretation: ...
```

It is part of the inquiry checkpoint, not a campaign gate.

Working, best-known, and retained lineages remain explicit evidence-backed
model-role operations. Training never changes them automatically.

## Instruments and scientific tooling

`contracts/instruments.md` remains protected and human/Runner-owned.

It documents:

- which generic instruments are available;
- their invocation contracts;
- accepted inputs;
- produced artifacts;
- execution and recovery behavior.

It does not:

- teach a coding agent how to code;
- prescribe which instrument to use;
- prescribe scientific measurements;
- define scientific priorities.

The PI owns scenario-specific scientific code and diagnostic implementations
within the allowed repository surface.

The Runner owns the lifecycle and heavy execution.

A measurement request is scientifically valid only when the current relevant
tool implementation has already been updated to produce that measurement. If
new evidence is needed, the PI first updates or builds the tool during the same
scientific session, then requests its execution.

This is an imperative responsibility of the PI, not a scientific judgment made
by the Runner. The Runner validates only the ordinary invocation and artifact
contract, executes the tool, and returns its output. It does not know which
scientific quantities are missing. The PI inspects the result in the same
session and corrects or replaces an inadequate tool.

Measurements receive identities independent from training:

- `M1`, `M2`, ... for measurements;
- `T1`, `T2`, ... for training.

All completed operations are recorded as inquiry events.

## Fingerprints

Do not redesign fingerprint or semantic-compatibility machinery as part of this
lifecycle correction if removing it requires moving scientific judgment into
the Runner or expanding the scope of the change.

Do not add any new fingerprint system.

Existing artifact-integrity and semantic mechanisms remain unchanged for now.
They may be simplified in a separate change only when doing so is isolated and
does not make the Runner interpret scientific meaning.

## Training operations

Every training operation explicitly records:

- fresh initialization or transfer from a named parent lineage;
- training seed;
- requested training steps;
- the PI's description and rationale for the scientific change.

The Runner records the exact scientific commit and displays the mechanical Git
delta from the selected parent or prior state. It does not classify the
scientific meaning of that delta and does not require a model to interpret it.

There is no implicit recipe `keep` caused by a method transition.

Training completion:

- records factual learning dynamics;
- records candidate models and exact provenance;
- appends a training event;
- returns control to the active bounded scientific session.

The PI decides what evidence to collect after seeing the training result.
Training requests do not precompose mandatory follow-up measurements.

It does not:

- create `pending_analysis`;
- force evaluation;
- force a method transition;
- change working or best-known;
- allocate another training run.

### Recipe restoration

The Runner retains one simple non-scientific operation that restores the
PI-owned scientific surface from a selected saved artifact's recorded recipe.
This is necessary because mutating Git and recipe restoration remain
Runner-owned. It does not interpret the recipe or decide when restoration is
scientifically appropriate.

## State simplification

Use a strict new schema with no migration or dual execution for the current
campaign.

Preserve:

- campaign and human-goal reference;
- scientific-model state;
- active inquiry;
- durable inquiry checkpoint;
- current bounded scientific-session state;
- working, best-known, retained, and available candidate artifacts;
- complete inquiry-event history;
- one transactional pending Runner operation;
- terminal state.

Remove or consolidate:

- campaign-long `inquiry_session`;
- `pending_analysis`;
- `pending_method_decision`;
- method-decision publication lifecycle;
- method lifecycle gates;
- experiment-specific scientific session state;
- overlapping pending-operation slots where one transaction is sufficient.

## Prompt architecture

The active prompt is imperative. `contracts/program.md` is informative.

Every scientific-session prompt begins with:

1. human goal;
2. current best evidence relative to the goal;
3. current gap;
4. active inquiry and its goal relevance, when one exists;
5. bounded session objective.

The prompt preserves the strong multidisciplinary PI persona and contains the
goal-directed continuation and stopping imperatives.

Control-plane limits, counters, schema versions, backend/session mechanics,
ownership enforcement, retry machinery, and operation catalogs are not
scientific context and are not injected into the active PI prompt. Instrument
formats remain available on demand in `contracts/instruments.md`.

It also acts as a source router:

- `contracts/scenario.md`: human goal, protected task, official assessment;
- `pi_workspace/scientific_model.md`: physical robot/task reference;
- `contracts/instruments.md`: instrument invocation contracts;
- `campaigns/brief.md` and inquiry checkpoint: current evidence and state;
- `contracts/program.md`: deeper lifecycle rationale when needed;
- `AGENTS.md`: ownership, commands, and operational boundaries.

The PI is not forced to reread every document. It queries detailed context when
the current work requires it.

## Documentation redesign

### `contracts/program.md`

Explain:

- human-goal supremacy;
- campaign, inquiry, scientific-session, and instrument hierarchy;
- bounded multi-operation sessions;
- goal-directed continuation and stopping;
- no privileged post-training phase;
- inquiry closure and campaign goal review;
- science as an instrument rather than a target.

### `contracts/scenario.md`

Remain the protected definition of:

- human objective;
- task;
- success contract;
- official assessment;
- protected constraints.

The human goal is extracted prominently into every generated scientific
context.

### `contracts/instruments.md`

Describe invocation mechanics only, including any revised generic measurement
and training instruments. It remains protected and does not prescribe
scientific choices.

### `campaigns/brief.md`

Lead with:

1. human goal;
2. current best-known evidence;
3. current goal gap;
4. active inquiry and why it matters;
5. current scientific-session checkpoint;
6. available evidence and artifacts.

Training history is one evidence section, not the document's organizing
structure.

## Console redesign

Console work follows the lifecycle correction.

### Preserve PI messages

Display normal PI messages, excluding hidden reasoning. These messages allow
the maintainer to understand scientific direction and stop a bad campaign.

Hide or collapse routine tool calls. Immediately show:

- tool failures;
- denied operations;
- changed files;
- measurement and training requests;
- consequential decisions.

### Preserve the training heartbeat

Keep a frequently refreshed single-line heartbeat containing:

- progress and total steps;
- elapsed time and ETA;
- steps per second or FPS;
- rolling reward;
- rolling training success.

Example:

```text
TRAINING T3  84%  101k/120k  357 fps  reward 163  success 54%
```

### Strategic resource reporting

Remove per-turn tool, token, cache, and AIU narration.

Show compact consumption at:

- scientific-session end;
- training end;
- measurement end;
- campaign goal review.

Keep detailed accounting in durable reports.

### Clear boundaries

Visibly mark:

- campaign start and end;
- inquiry open, reframe, and close;
- scientific-session start and end;
- instrument request, start, and completion;
- campaign-level goal review.

Use semantic colors, short human identifiers, wrapped text, and compact
repository-relative paths. Do not print full campaign UUIDs in normal output.

## Known correctness fixes

- Fix phantom measurement results caused by `@($null).Count`.
- Remove stale "measurement completed" prompt state.
- Do not attribute measurements performed before method creation to that
  method.
- Do not number measurements as future experiments.
- Do not announce a measurement result that the produced artifact does not
  contain.

## Validation

Add or update only behavioral tests required by the redesign:

1. A scientific session may survive several Runner round trips.
2. A session ends at a durable scientific checkpoint rather than after one
   operation.
3. Training and measurement return to the same bounded session.
4. Training creates no privileged post-training phase.
5. A later fresh session continues only from durable checkpoint state.
6. Inquiry closure is independent of method state.
7. Campaign-level goal review follows inquiry closure.
8. `MaxInquiries` limits inquiry creation only and is not a scientific stopping
   signal.
9. Measurement results return to the same scientific session so the PI can
   detect and correct an inadequate tool.
10. No new fingerprint or semantic-judgment system is introduced.
11. Fresh and transfer initialization resolve their parent and provenance
    explicitly.
12. Training never changes model roles implicitly.
13. Measurements and training have independent identities and complete event
    history.
14. Prompt-state defects do not announce nonexistent or stale measurements.
15. Default console preserves PI messages and training heartbeat while hiding
    per-turn telemetry and UUID noise.
16. The retired lifecycle and fingerprint tests are removed rather than
    preserved through compatibility code.

## Implementation order after approval

1. Obtain maintainer approval of the challenged and revised design.
2. Lock the strict state schema and deletion map.
3. Rewrite imperative prompts and informative documentation together with the
   control-flow change.
4. Implement bounded multi-operation scientific sessions and durable
   checkpoints.
5. Remove the method/post-training loop and campaign-long session persistence.
6. Restore a lightweight generic measurement-tool execution path without
   adding scientific judgment to the Runner.
7. Make training parent, seed, requested steps, commit, and mechanical delta
   explicit.
8. Update event history and generated context.
9. Redesign the console against the corrected lifecycle.
10. Run targeted validation only.
11. Begin a fresh campaign; do not migrate or resume the failed campaign.

## Explicit non-goals

- No compatibility with the current campaign schema.
- No cross-campaign automated scientific memory.
- No prescribed measurement list.
- No harness-owned scenario diagnostics.
- No new fingerprint or semantic-hash system.
- No campaign-long LLM session.
- No one-operation-per-session rule.
- No training-centered lifecycle.
- No scientific stopping rule based on the value 15.
