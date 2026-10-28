# Autoresearch terminal report specification

Date: 2026-10-23

Audience: harness maintainers and a future implementation agent

Status: report-view specification, implemented in `tui/report.py`. Issue #68
extends the application shell with explicit multi-campaign controls. Its
approved specification and `docs/tui-report.md` govern the controller; the
read-only data, scientific meaning and layout rules below still govern each
campaign report panel and standalone read-only monitoring.

## 1. Product contract

Build one read-only terminal report with Textual for Windows Terminal.
The PI remains autonomous. The operator reads the report and scrolls the output.
The report does not direct, approve, or interrupt campaign work.

The operator needs to see:

1. The scientific question and the latest recorded scientific understanding.
2. The campaign stage and the activity that is executing now.
3. Campaign age, stage duration, and current execution duration.
4. Recorded resource usage, including Copilot AIU where available.
5. Models with PI-assigned roles, with their recorded reward and success.
6. Training progress, steps, and duration while training executes.
7. Evaluation progress, episode counts, and duration while evaluation executes.
8. Chronological output, including full PI messages.

Use one screen. Keep the report above a scrollable output region.
Do not require navigation to another screen to obtain these facts.
Design the primary experience for a spacious Windows Terminal window, using 160x45 as the reference size.
Use the actual available terminal dimensions. Do not impose an 80-column application width.
Small layouts are compatibility fallbacks, not the primary design or visual style.

### Explicit exclusions

- Report facts remain on one campaign panel. The maintainer's updated issue #68
  direction puts command entry alongside the first campaign report, not on a
  separate Commands tab. Campaign tabs, shared-settings and error/diagnostic
  dialogs belong to the application shell.
- Campaign commands and shared launch/reset settings belong to that controller,
  never to scrolling, copying, searching or selecting scientific report content.
- No agent-operation approval gates, manual operation submissions or custom
  replay/repair workflow. Standalone `--read-only` monitoring owns no campaign.
- No monetary amounts, currency, prices, or conversions from usage to money.
- No automatic leaderboard or model-role assignment.
- No campaign completion percentage or predicted scientific completion time.
- No permanent hardware dashboard, file browser, or learning-curve panels.
- No browser, SSH, tmux, or non-Windows platform work in this implementation.

Scrolling and focus changes are reading actions. They must not affect execution.

## 2. Existing implementation and constraints

Read `AGENTS.md` and `docs/harness-campaign-split.md` before implementation.
Load the `tui-design` and `textual-tui` skills for the implementation task.
Load the Python ecosystem reference from `tui-design` before selecting Textual APIs.

Inspect these sources instead of treating this document as an execution contract:

| Source | Relevant behavior |
|---|---|
| `runner/launcher/` | Campaign loop, stage transitions, launcher events, durable recovery, and shutdown behavior (formerly `run_research.ps1`, `researcher_session.ps1` and `runner/copilot/copilot_controller.ps1`) |
| `runner/launcher/copilot_runtime.py`, `operation_bridge.py` | Persistent adapter process and trusted operation control channel |
| `runner/reporting.py`, `runner/copilot/reporting.py` | Runner notices, PI message assembly, tool results, file changes and usage; the former console renderers `runner/console.py` and `runner/copilot/copilot_console.py` were removed on 27 October 2026 |
| `runner/copilot/session_events.py` | Observable SDK messages, tools, usage, and session errors |
| `runner/copilot/coding_session.py` | Coder/reviewer activity and separate usage accounting |
| `runner/copilot/usage.py` | Durable usage rows and unavailable values |
| `runner/execution.py` | Training counters, evaluation counters, and elapsed execution time |
| `runner/run_experiment.py` | Accepted transactions, partial results, publication, and official assessment callbacks |
| `runner/repository.py` | State schema, model roles, candidates, results, and atomic writes |
| `runner/paths.py` | Resolution of campaign and harness paths |
| `docs/external-campaign-stop.md` | Existing interrupt, external stop, and process ownership contracts |

### Audit findings that affect the design

- The current stream mixes scientific context, PI messages, tools, progress, and failures.
- Context scrolls away. Returning operators must reconstruct the current state.
- Runner already separates accepted transactions, completed execution, and publication.
- A successful tool or process does not establish a completed scientific operation.
- Runner progress rewrites its line only when its stream is a terminal.
- Redirected Runner progress emits occasional snapshots instead of rewriting a line.
- PowerShell redirects both Runner streams on some execution paths.
- The persistent PI adapter can inherit terminal output instead.
- PI reasoning events are intentionally excluded. Preserve that exclusion.
- Detailed child chatter is already suppressed. Do not enable it by default.
- `campaigns/results.jsonl` is atomically rewritten during upserts. It is not an append-only live event stream.

The reviewed campaign snapshot contained no completed operations.
A model document and successful analyst usage record existed while Runner readiness remained `pending`.
This observation does not establish a failure or a currently running process.
Do not infer acceptance from a file's presence or a process exit code.

## 3. Single-screen structure

Use one vertical composition at every supported width:

1. Campaign context and status.
2. PI-selected models.
3. Conditional execution progress.
4. Scrollable output.
5. One compact reading-status line.

Keep sections in this order. Do not add side panes on wide terminals.
When progress disappears, give its rows to the output region.
Do not move the models above the scientific context.

### 3.1 Campaign context and status

Show these facts in a readable report band, using approximately six rows at 160 columns:

- Campaign identity and observed run status.
- Scientific stage, session identity, current activity, and relevant operation identity.
- Active inquiry question, or the preparation/startup objective when no inquiry exists.
- Latest recorded PI synthesis, attributed to its scientific session.
- Campaign age, stage duration, and recorded usage.

Use the width to separate status, duration, and usage values without cryptic abbreviations.
Allow the scientific question and PI synthesis more space at the primary size.
Compress this band to approximately five rows only for the 80-column fallback.

Use the existing identifiers without redefining them:

| Identifier | Meaning |
|---|---|
| `I...` | Inquiry |
| `S...` | Scientific session |
| `T...` | Training operation |
| `M...` | Measurement operation |
| `E...` | Other operation event, such as a checkpoint or model-role change |

Separate the scientific stage from current activity. For example:

```text
Stage: Inquiry I3 / S7              Stage elapsed: 18m
Now: M6 measurement / task reference
```

Scientific stages include preparation, startup, goal review, inquiry, and terminal state.
Activities include PI analysis, coding, review, training, measurement, checkpoint publication, and artifact publication.
An accepted request alone does not establish that execution started.

Limit the question and synthesis excerpts to the available report rows.
Keep their complete recorded text accessible in the output on the same screen.
On initial load, append an attributed snapshot of the current question, synthesis, and model assignments.
Append attributed context when it changes, not on every refresh.
Do not generate a new scientific summary or expose private reasoning.

### 3.2 Duration rules

- Label time since `campaign.started_at` as `Campaign age`.
- Read-only campaign age includes periods when execution was inactive. For
  TUI-owned campaigns, label the counter `Campaign elapsed`, freeze it after an
  acknowledged stop and exclude paused intervals observed in the current TUI
  session on resume. Do not change recorded timestamps or infer offline pauses.
- Stage elapsed measures the current stage/session interval, not campaign age.
- Training elapsed measures the current execution attempt.
- Evaluation elapsed identifies whether it covers the current panel or the whole measurement.
- Restart an attempt timer when a new execution attempt starts.
- Do not reset a timer when the report reconnects or the terminal resizes.
- Do not infer exact start times from file modification times or operation identifiers.
- Show `unavailable` when the required start observation does not exist.
- If reporting only time since attachment, label it `Observed for`, not `Elapsed`.

Use existing runtime clocks where available. Add observation timestamps where necessary.
Do not change campaign state schemas merely to support presentation timers.

### 3.3 Resource usage

Show resource usage, not monetary cost.
Prioritize campaign Copilot AIU. Include session usage when the width permits.
Use labeled token counts when a provider does not report AIU.
Do not relabel external-provider usage as Copilot AIU.

Label totals as `recorded` when they exclude an active invocation.
Unknown usage is `unavailable`, not zero.
Live observations must replace or reconcile with their durable accounting rows.
Do not add the same invocation twice.
Do not add native child lifetime totals again for every correction.
Do not deduplicate valid correction records solely by child session identity.
PI, coder, and reviewer accounting must retain their existing scopes.

Do not remove existing accounting fields or change their storage formats.
Simply exclude price and currency fields from the report.

### 3.4 PI-selected models

Read roles from `model_roles`. Show working, best-known, and retained assignments.
Use `Working` for the existing current scientific model role.
Do not confuse a learned policy with the inference model that serves the PI.

- Show only role-assigned candidates in this table, not the complete candidate pool.
- Preserve retained labels chosen by the PI.
- Combine roles on one row when they identify the same candidate.
- Show `none assigned` for an empty role.
- Do not infer a working or best-known role from a high metric.
- Keep a new training artifact unassigned until the PI assigns a role.

Each candidate row includes:

- Candidate identity.
- Training reward when recorded.
- Training success when recorded.
- Development success when measured, with its operation and instrument/panel source.

Use explicit headings such as `Reward(tr)`, `Success(tr)`, and `Success(dev)`.
Convert a success fraction to percent only when the source defines that unit.
Do not combine training, development, and official success values.

For development success, show the latest completed evaluation for that candidate in recorded operation order.
Identify its source. Do not select the highest score or average unrelated evaluations.
Use `not measured` when no suitable completed evaluation exists.
Keep the official assessment separate in campaign status and output.
Do not treat failed operations or incomplete panels as completed development evidence.

At the primary size, show complete candidate identities and explicit metric headings.
Use available height to show more PI-assigned models when they exist.
Do not cap the table at three rows on a large window.
With three assignments, use three rows and give the remaining height to the output.
Preserve at least half the terminal height for output at the primary size.
Show approximately three candidate rows in the 80x24 fallback.
If assignments exceed the available table height, scroll within this table on the same screen.
Keep its heading visible and show the visible row range.
Do not create a model-details screen or silently omit retained assignments.
Make complete clipped identities and measurement sources available in the output when assignments change.

## 4. Conditional execution progress

Use one progress area. It appears only during training or evaluation execution.
Do not show empty progress frames during PI analysis, coding, review, or publication.
Do not use the area's visibility as an execution or recovery signal.

### 4.1 Training

```text
Training T4 | Attempt 1 | Elapsed 12m 08s
Steps 72,000 / 120,000  [############--------] 60%
```

Required fields are operation identity, attempt when known, observed steps, target steps, percentage, and elapsed attempt duration.
Use the accepted request and existing training progress semantics for the denominator.
Do not substitute the launcher default when the accepted startup allocation differs.
Preserve the distinction between cumulative steps and steps in the current execution.
Do not reinterpret continuation counters.

Before the first counter, show `Starting - no step count yet`.
Do not fabricate a measured zero.
Show the runner's ETA when available. For older feeds, estimate only from
advancing observations in the same attempt; otherwise show unavailable. FPS
remains optional. TUI numeric targets are identities, not counts: `start 2`
selects only campaign-2; `start 1-2` and `start 2-3` select inclusive ranges.

### 4.2 Evaluation

```text
Evaluation M6 | Task reference | Panel 2/3 | Panel elapsed 4m 12s
Episodes 64 / 100       [############--------] 64%
```

Required fields are operation identity, instrument, panel position when applicable, episode counts, percentage, and labeled elapsed duration.
Keep completed-panel counts separate from current-panel episode progress.
Partial results identify preserved work, not a completed measurement operation.

An official assessment uses an explicit `Official assessment` label.
Use its existing progress callback. Do not assign it a fabricated measurement identifier.

A module measurement without counters shows `Running - progress unavailable` and elapsed duration when known.
Do not invent episode counts or percentages for that instrument.

### 4.3 Progress lifecycle

1. Show the area when execution starts.
2. Refresh counters from execution observations.
3. Append a completion, failure, or interruption entry to the output.
4. Remove the area when that execution ends.

A step counter reaching its target does not complete operation publication.
After training, the activity can become archiving or publishing without retaining a misleading training bar.

Distinguish the latest counter observation from the latest counter advancement.
An unchanged durable state file does not establish a stalled operation.
Report stale observations without introducing new execution timeouts.

If observation disconnects, label the last progress as stale or unknown.
Do not present a frozen bar as live execution.

## 5. Output region and console behavior

Keep full PI messages in chronological output.
Preserve paragraphs and line breaks. Do not replace messages with generated summaries.
Handle streaming deltas without printing the final message twice.
Keep the existing exclusion of private reasoning events.

Include inquiry changes, operation boundaries, results, role assignments, checkpoints, errors, and useful coding/review summaries.
Give routine tool calls a quieter style and compact presentation.
Do not expand child output beyond its existing visibility contract.
Do not repeat campaign context before every routine output entry.

### Reading behavior

- Follow new output while the reader is at the bottom.
- Scrolling upward preserves the reader's position while new output arrives.
- Show `Reading history - N newer entries` when following is inactive.
- Returning to the bottom resumes following.
- Support the mouse wheel, Page Up, Page Down, Home, and End.
- Use Tab and Shift+Tab to move between the output and an overflowing model table.
- Do not show campaign action hints or command input.

Use bounded rendering for long output. Do not discard PI messages silently to bound memory.
Use an existing suitable history source or a small additive presentation archive when required.
If older history is unavailable, state that limit in the output.

### Progress is not narrative output

In Textual mode, update a widget instead of replaying in-place console progress.
Do not append every heartbeat to the visible output.
Keep execution boundaries and outcomes in the output.
Preserve existing archived progress snapshots and training logs.

Never replay carriage-return rewrites or cursor-erase sequences into the output widget.
Do not suppress arbitrary lines that contain words such as `TRAIN` or `MEASURE`.
Identify progress through structured observations, not message-text matching.
Render untrusted text as text. Do not interpret embedded markup or terminal control sequences as UI commands.

## 6. Layout and visual rules

All wireframe values are illustrative. The wireframes are not campaign evidence or tested Textual frames.
Spacing is explanatory, not a requirement for absolute widget coordinates.
ASCII is only the documentation sketch format.
The implementation uses Textual styling, semantic colors, clear spacing, and responsive widgets.
Do not reproduce a small ASCII mockup as a fixed-size box inside a large terminal.

### Primary reference: 160x45

Use the full window. Keep the scientific report, selected models, progress, and output on this single screen.
This example gives the output 28 rows. Extra height extends the output instead of adding empty panels.

```text
Autoresearch | RUNNING | campaign example                                            Campaign age 2h 14m | Stage elapsed 18m
Stage: Inquiry I3 / scientific session S7                                            Current activity: M6 measurement
Inquiry: Does longer settling improve hold stability, or do the remaining failures require a different control intervention?
PI record S6: The policy reaches the target, but its hold behavior remains unreliable. The existing measurements do not establish
              whether slower convergence or limited control authority explains the remaining failures.
Recorded usage: Campaign 7.4 Copilot AIU | Current session accounting pending

PI-assigned role    Candidate                   Training steps    Reward (training)    Success (training)    Success (development) / source
Best-known         T2:checkpoint-90000                 90,000                 82.1                   96%    94% / M5, task reference
Working            T4:checkpoint-120000               120,000                 86.3                   97%    Not measured
Retained: baseline T1:checkpoint-60000                 60,000                 75.2                   91%    89% / M2, task reference

Evaluation M6 | Task reference | Current panel 2 of 3 | Completed panels 1 of 3        Current panel elapsed 4m 12s
Episodes 64 / 100  [################################------------------] 64%

Output ---------------------------------------------------------------------------------------------------------------------------------
12:29 PI: The current best-known policy reaches the target consistently, but the remaining hold failures need a controlled comparison.
         A higher training reward does not establish better development performance.

         I will retain the earlier policy as a reference. The working candidate needs a measurement under the same task conditions
         before I can decide whether the change improves the behavior that matters for this inquiry.

12:32 E12: PI assigned best-known to T2:checkpoint-90000 and retained baseline T1:checkpoint-60000.
12:33 E13: Scientific session S6 checkpoint saved.
12:34 S7: Inquiry session started for I3.
12:35 PI: I will compare the working candidate against the best-known policy and the retained baseline.
         The measurement will separate whether the latest change improves continuous hold behavior or only changes training reward.
         I will use the completed comparison to decide which candidate should remain the working model.

12:36 Coding: Scoped implementation request accepted.
12:38 Coding: Source changes returned to the PI.
12:39 Review: Independent implementation review completed. PI source review remains required.
12:40 PI: The implementation is ready for the requested comparison.
         I will measure the three selected candidates and preserve each panel result in the operation transaction.
         An incomplete panel will not count as completed evidence for the model-role decision.

12:41 M6: Measurement accepted, three panels requested.
12:41 M6: Panel 1 started.
12:42 M6: Panel 1 completed. Result preserved in the pending transaction.
12:43 M6: Panel 2 started.




Following live output | Mouse wheel / Page Up / Page Down to read history | End to return to live output
```

### Compatibility fallback: 80x24

```text
Autoresearch | RUNNING | example                       Campaign age 2h 14m
Stage Inquiry I3 / S7 | Now M6 measurement              Stage elapsed 18m
Question: Does longer settling improve hold stability?
PI record S6: Hold failures remain the main unresolved issue.
Usage recorded: campaign 7.4 AIU | S7 accounting pending

Role       Model                 Reward(tr)  Success(tr)  Success(dev)
Best-known T2:checkpoint-90000          82.1          96%  94% M5/ref
Working    T4:checkpoint-120000         86.3          97%  not measured
Ret:base   T1:checkpoint-60000          75.2          91%  89% M2/ref

Evaluation M6 | Task reference | Panel 2/3 | Panel elapsed 4m 12s
Episodes 64 / 100       [############--------] 64%
Output -----------------------------------------------------------------
12:40 PI: The remaining failures suggest that the policy reaches the
      target but does not stabilize reliably.
      I will compare the two policies under the same measurement panel.
12:41 M6: Measurement started.
12:42 M6: First panel completed. Result preserved in the transaction.
12:43 M6: Second panel started.
      Full earlier PI messages remain available by scrolling.


Following live output | Wheel / PgUp / PgDn | Home / End
```

### Narrow compatibility fallback: 60x24

```text
Autoresearch | RUNNING | example
Inquiry I3 / S7 | M6 measurement | Stage elapsed 18m
Q: Does longer settling improve hold stability?
PI record S6: Hold failures remain unresolved.
Campaign age 2h 14m | Recorded usage 7.4 AIU

PI-selected models
Best-known T2:checkpoint-90000
  Reward(tr) 82.1 | Success(tr) 96% | Dev 94% M5/ref
Working T4:checkpoint-120000
  Reward(tr) 86.3 | Success(tr) 97% | Dev not measured
Retained base T1:checkpoint-60000
  Reward(tr) 75.2 | Success(tr) 91% | Dev 89% M2/ref

Eval M6 | Task reference | Panel 2/3 | Panel time 4m 12s
Episodes 64/100 [############--------] 64%
Output -----------------------------------------------------
12:40 PI: The remaining failures suggest that...
      Full PI messages wrap in this output region.
12:42 M6: First panel completed.
12:43 M6: Second panel started.


Following | Wheel / PgUp / PgDn | Home / End
```

### Responsive behavior

- At 160x45, use the primary layout above with full model identities and approximately 25-30 output rows for three assigned models.
- At 120x35, retain the same composition with shorter excerpts and at least half the height for output where the data permits.
- At 80x24, keep all four content sections visible with approximately nine output rows.
- At 60 columns, use labeled model records instead of an overflowing table.
- Reserve at least five readable output rows at the proposed minimum of 48x16.
- Reduce model viewport height and excerpt lengths before removing required status facts.
- Keep all model assignments accessible through local scrolling.
- Below 48x16, show a compact `Terminal too small - need 48x16` message.
- Resize must not change campaign state, follow state, or selected model identity.
- Larger windows use the available width and height. Do not center a capped 80-column report within them.
- Wider windows extend context, table columns, progress bars, and output capacity. They do not introduce more screens or panes.

The minimum size is a proposal to validate during implementation.

### Visual design and clutter limits

- Use semantic colors for text, selection, activity, warning, error, and success.
- Pair status color with explicit status text.
- Respect `NO_COLOR` and the terminal's color capabilities.
- Provide readable light, dark, and monochrome presentation.
- Use no decorative outer frame or nested panel borders.
- Use at most one simple separator before the output.
- Use no repeated per-line markers that carry no information.
- Require no emoji, icons, or special font.
- Measure terminal cells, including wide and combining characters.
- Wrap prose. Avoid wrapping table cells.
- Use no blinking or decorative animations.

The existing console has no nested card borders. Preserve that restraint.
A minimal training-request card uses about 14 rows before wrapping, including eight blank or section-label rows.
Remove that repeated framing from the report output.
The wireframes reserve only two rows for output separation and reading hints.
Do not add a large header, footer menu, or repeated status badges.

## 7. State and error reporting

| Condition | Required presentation |
|---|---|
| Initial load | Loading state, without launching or changing a campaign |
| Fresh campaign | Preparation pending, no completed evidence, no assigned models |
| Process state unknown | Explicit unknown status, not an inferred running or stopped status |
| Active operation | Current activity plus conditional progress where applicable |
| PI correction or implementation repair | Factual activity and error output, without an operator approval prompt |
| Publication failure | Execution/publication distinction, preserved transaction, and original error |
| Observation failure | Last-known facts marked stale, without claiming the campaign stopped |
| Missing metric or accounting | `unavailable` or `not measured`, according to the source |
| Inquiry-cap pause | Existing launcher pause, not a scientific conclusion |
| Official assessment failed | Campaign ended without reaching the goal, not an execution crash |
| Official assessment passed | Campaign ended with the recorded successful assessment |

Show important errors in campaign status and output.
Do not use disappearing notifications as the only error report.
Do not clear an underlying error because the reader scrolls or changes focus.
Do not add recovery actions or attempt recovery from the report.

## 8. Data sources and necessary instrumentation

| Information | Existing source | Additional presentation work |
|---|---|---|
| Campaign, inquiry, session, synthesis, roles, pending stage | `runner/state/research_state.json` | Read-only projection |
| Completed operations and candidate metrics | State, `campaigns/results.jsonl`, referenced artifacts | Join by recorded identities |
| Training counters and metrics | Training log and execution variables | Export observations or incrementally read existing records |
| Evaluation episodes | Temporary progress files and execution variables | Export observations or read the active progress file |
| Official assessment progress | Existing callback | Export callback observations |
| PI messages and tools | SDK event callbacks | Forward presentation events without changing protocol behavior |
| Coder/reviewer activity | Coding handler events and state | Export actor transitions |
| Recorded usage | `reports/session_usage/<campaign-id>.jsonl` | Correct aggregation and scope labels |
| Live usage | Existing SDK usage callbacks | Optional export with durable-row reconciliation |
| Exact stage start and current process activity | Launcher/controller runtime | Small observation events |
| Complete readable output history | Console/SDK sources, depending on invocation | Additive capture only where existing sources are insufficient |

Resolve paths through the existing harness/campaign ownership rules.
Scope every source to the selected campaign.
Handle atomic file replacement, incomplete reads, transient missing progress files, and reconnects.
Treat state as authoritative for scientific roles and accepted/completed operations.
Treat runtime observations as the source for current execution activity.

Use a small, one-way observation path. Do not create a second control channel or campaign state database.
Keep that path separate from authenticated operation-submission messages.
Include campaign/run identity, source identity, timestamps, and enough correlation to reject stale activity.
Include attempt and panel identity with progress.
Preserve event order within each source. Do not invent a total order across independent output streams.
Deduplicate replayed observations and streamed/final PI message forms.

Observation failure must not cause operation acceptance, execution, interruption, or replay.
Preserve durable truth and display unavailable observations explicitly.
Do not turn this feature into a general telemetry platform.

## 9. Terminal ownership, redirection, and compatibility

Only the Textual report may render into its active terminal screen.
Launcher, Runner, and PI output must not write around Textual's renderer.
The report panel must not become the owner or controller of campaign execution.
The issue #68 application controller separately owns its explicit launches,
using the existing scripts and external-stop contract.

Do not embed Textual in a Runner child whose stdout or stderr is redirected.
Do not force `isatty()` or add a pseudo-terminal to repair that arrangement.
Use structured progress observations rather than scraping formatted console lines.
Drain redirected stdout and stderr concurrently, including chunks without newlines.
Preserve separate machine-readable validation and operation-state responses.
Keep stdout/stderr source identity where it matters for diagnostics.

The exact launch arrangement is an implementation decision within these constraints.
Do not add user-facing launch modes to solve it.
If an arrangement requires new process ownership or interrupt semantics, obtain maintainer approval before implementing that change.
Do not assume that wrapping PowerShell inside Textual preserves those semantics.

### Non-interactive execution

- Keep a linear, non-TUI path for redirected output and non-interactive execution.
- Do not start a full-screen report when its rendering terminal is unavailable.
- Keep existing launch arguments and machine-output commands compatible.
- Emit no cursor movement, alternate-screen commands, or spinner frames into pipes.
- Retain occasional progress snapshots and meaningful execution boundaries.
- Do not add prompts to unattended execution.
- Do not silently change established stdout/stderr placement or exit codes.

### Lifecycle

Use framework-managed cleanup for raw mode, cursor state, mouse reporting, and the alternate screen.
Keep file reads and process/event ingestion outside blocking UI handlers.
Restore the terminal after report exit or failure.

Standalone read-only report exit closes presentation only. It never writes a
stop request or stops external campaigns. In the controller, Ctrl+Q requests
cooperative stop for all owned campaigns and exits after cleanup.
Ctrl+C copies selection only, with no stop or exit fallback.
Do not reinterpret Ctrl+C as a new cooperative-stop protocol.
Preserve the existing launcher and external-controller shutdown contracts.
Do not claim that closing Windows Terminal stops the campaigns: launchers run
in their own hidden console and survive the console (see
`docs/external-campaign-stop.md`).

## 10. Persistence and authority invariants

Implementation may change presentation and add the minimum observation instrumentation.
It must preserve:

- PI autonomy, permissions, prompts, and scientific decision rules.
- Request validation and the trusted operation controller.
- Durable transaction stages and recovery behavior.
- Scientific checkpoint and candidate identities.
- Measurement contents and evidence distinctions.
- Training logs, raw measurements, operation records, and accounting records.
- Publication behavior, campaign mutexes, and process ownership.
- Existing timeouts, execution allocations, and exit-code meanings.

Do not infer campaign completion from process exit code zero.
Do not infer scientific evidence from a failed operation.
Do not reaccept or retrain a result-ready operation to refresh the report.
Do not modify state or regenerate evidence as a side effect of viewing it.

Keep presentation archives and caches separate from scientific evidence.
Do not create generated files in the harness worktree during a campaign.
Do not expose maintainer-only guardrails or report metadata to campaign agents.
This specification belongs in maintainer documentation, not campaign prompts or contracts.

## 11. Implementation and verification handoff

Implement this design, not the earlier multi-screen supervision proposal.
Do not add rejected features because a framework supplies them by default.
Textual is the chosen framework. It is not currently a declared project dependency.
Dependency changes remain human-owned and require maintainer authorization.

Keep the state projection separate from rendering.
Prefer the smallest existing source or widget that owns each behavior.
Do not introduce unrelated abstractions or new scientific APIs.

Use targeted checks. Run project Python only through `uv run`.
Do not start a real campaign, agent session, training run, or assessment without explicit authorization.
Use synthetic observations and existing targeted fixtures for normal validation.
Do not create tests for documentation wording or source fragments.

### Acceptance checks

1. One screen exposes context, usage, role-assigned models, conditional progress, and PI output.
2. No report action sends a campaign command or writes campaign control state.
3. Inquiry, session, and operation identities retain their existing meanings.
4. Training and evaluation counters update without flooding visible output.
5. Progress appears only for the corresponding execution and disappears when it ends.
6. Publication remains visible as a separate activity after execution finishes.
7. PI streaming produces each complete message once, without losing paragraphs.
8. Scrolling preserves the reader's position while updates continue.
9. All PI-assigned roles remain accessible on the same screen, including overflow cases.
10. Reward and success show source labels and distinguish unavailable values.
11. Usage excludes monetary fields and avoids duplicate accounting.
12. Fresh, loading, partial, failed, terminal, and disconnected states remain readable.
13. Reconnects reject stale run events and retain valid timers when start observations exist.
14. Frames use the available space at 160x45 and 120x35. Fallbacks remain usable at 80x24, 60x24, and the validated minimum.
15. Wide characters, combining characters, monochrome, and resize do not corrupt layout.
16. Real PowerShell redirection emits no terminal-control corruption into captured output.
17. Report lifecycle cleanup preserves existing execution and exit behavior.
18. Linear execution retains existing records, progress snapshots, and machine-output compatibility.

Test the state projection first. Then use Textual's headless app harness for rendering and scrolling.
Use a small Windows integration check for terminal ownership and real redirected streams.
Do not build a large end-to-end suite for this presentation change.
