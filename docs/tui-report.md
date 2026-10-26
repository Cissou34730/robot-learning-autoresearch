# Autoresearch campaign console and terminal report

Implementation of `docs/autoresearch-terminal-report-spec.md`: one read-only
Textual screen for Windows Terminal that shows campaign context, PI-selected
models, conditional execution progress and chronological output. The PI stays
autonomous; scrolling is a reading action and never touches campaign
execution.

## What this pass changed

- New maintainer package `tui/` in the harness repository:
  - `tui/sources.py` - resilient read-only file access (atomic rewrites,
    torn JSONL tails).
  - `tui/projector.py` - pure projection of research state, accepted
    transactions and usage rows into a display snapshot.
  - `tui/observations.py` - consumer for a structured one-way observation
    JSONL feed (see below), plus the synthetic feed used by `--demo`.
  - `tui/report.py` - the single-screen report application.
  - `tui/demo.py` - synthetic campaign material for `--demo` and tests.
- `tools/run-report.ps1` - launcher helper.
- `tests/autoresearch/test_report_projector.py` and
  `tests/autoresearch/test_report_app.py` - projection and headless
  rendering tests.
- `textual` added to the `dev` dependency group (authorized dependency change).

The campaign repository and all `runner/` code are untouched. The report
never writes; it reads durable campaign files under the selected campaign
root only.

## Running the report

The default entry point is now the multi-campaign operator console (see the
next section). The single-campaign report stays unchanged:

```powershell
uv run python -m tui --report                      # legacy report
.\tools\run-report.ps1 -CampaignRoot <path>        # legacy report
.\tools\run-report.ps1 -Demo                       # legacy report, synthetic
.\tools\run-report.ps1                             # console (campaigns + commands)
```

For parallel campaigns, use the console tabs. To monitor one campaign without
control, use `uv run python -m tui --read-only --campaign-root <path>`.
Only one TUI, including a read-only report, may use a canonical harness directory.
Each campaign panel follows only that repository's campaign state and event feed.
The parallel launcher clears inherited observation-file overrides so its
campaign processes use their own per-campaign feed paths.

Directly: `uv run python -m tui --help` (options: `--report`, `--read-only`, `--campaign-root`,
`--events`, `--demo`, `--light`).

## Operator console (multi-campaign control)

Issue #68 implementation. `uv run python -m tui` (or
`.\tools\run-report.ps1` with no arguments) opens one Textual console with
one report tab per installed campaign folder, initially showing the first
installed campaign (normally campaign-1). Command entry is alongside the report,
not on a separate Commands tab, following the maintainer's updated UX direction
on 26 October. The standard folders are `robot-learning-campaigns\campaign-1`
through `campaign-5`; Tab/Shift+Tab cycle their tabs. Launching the console starts
nothing; campaigns run only when a command is submitted.

Controlled execution uses the existing PowerShell 7 on PATH, including
Store/MSIX installations. The launcher sets the inherited Windows desktop-app
child policy to keep packaged native descendants contained; no reinstall or
manual shell instance is required. Windows PowerShell 5.1 lacks the launcher's
required .NET APIs. Missing PowerShell 7 fails preflight before initialization,
reset or launch, without preventing the interface from opening.

- The bottom command composer has a permanent label, an editable field,
  **Execute** and **Settings**, plus a one-line target/status preview. Press
  Enter or click Execute to submit. `start` resumes the active campaign without
  resetting; `run` resets and starts it. The destructive preview leads with a
  warning and the no-backup consequence. No action runs just from typing.
- **F2 / Settings** opens one labelled, scrollable dialog for Model, Provider,
  Reasoning, Timesteps, MaxTimesteps, MaxInquiries and StopTimeoutSeconds, plus
  reset options. Apply affects future commands only; Cancel/Esc discards edits.
  Empty launch fields preserve launcher defaults and argument omission.
  Every campaign in one batch receives the same settings snapshot.
- **Ctrl+L** toggles the bottom command area in every campaign tab. It starts
  open; opening focuses the input, and closing returns focus and four rows to
  the active report. The command draft and shared settings survive the toggle.
  The footer remains visible. Tab changes and applying/cancelling settings do
  not reopen a collapsed command area; toggling is inactive inside a dialog.
  Untargeted campaign actions select that folder only. A number selects that
  identity (`start 2` means only campaign-2); inclusive ranges (`start 1-2`,
  `start 2-3`, `run 1-3`) or folder lists select batches. Overlapping/duplicate,
  descending and out-of-bounds selections are refused before any action.
  Without any installed campaign, an empty state requires
  explicit targets and shows no fake campaign tab. `models` lists available models
  through the existing launcher. `diagnostics campaign-1` shows the last 64 KiB
  of each run-private console log, separately from scientific observations.
  **F1** opens command help; **F3** opens recent commands and persistent step
  details from this TUI session. The main report does not repeat help as activity.
- Reset controls select Fresh/Baseline, Clean and RecipeRef/BaselineRef. The
  default remains Fresh + Clean + `baseline-distinct-episodes-v3-robot` + Force.
  Targets and options are logged before execution. Measurements/logs may be
  deleted; ignored measurements have no reset backup.
  Only the reference field for the selected reset mode is visible. `-Clean`
  is labelled as cleaning eligible changes, not merely cleaning logs.
- `run` initializes a missing standard folder from the recipe (same as
  `tools\run_parallel.ps1`), resets it (`-Mode Fresh -Clean -RecipeRef
  baseline-distinct-episodes-v3-robot -Force`) and launches it. `start`
  launches without resetting; `reset` resets without launching; `stop`
  sends the cooperative stop request. All selected resets complete before
  any batch launcher starts. An initialization/reset failure stops further
  preparation and all launches in that batch, with a popup and persistent
  details. Earlier successes are not rolled back. A launch failure does not
  stop other successfully launched campaigns.
- `start` leaves recorded final outcomes untouched. An official assessment
  request without a recorded result remains resumable through the launcher.
- The launcher refuses to run while the harness worktree is dirty, so the
  console reports that refusal and skips the batch.
- Campaign tabs are the single-campaign report (above) bound to that
  folder explicitly.
- `Ctrl+C` copies the current text selection or does nothing; it never
  stops campaigns. `Ctrl+Q` sends the cooperative stop request to every
  console-owned launcher, waits up to its stop timeout (default 180 s) plus
  five seconds from request creation, and exits promptly when cleanup finishes.
  Only failed/timed-out cleanup requires forced termination. Closing the
  console process triggers the kill-on-close Job Object directly.
- One console per harness directory: a second console instance refuses to
  start. Campaign processes owned by the console run in separate job
  objects (see `docs/external-campaign-stop.md`); by-runner windows launched
  outside the console remain untouched.

The machinery lives in `tui/process.py` (Job Objects, suspended creation,
instance lock, per-run control directories with captured console logs) and
`tui/controller.py` (command parsing, per-folder stage machines, batch
orchestration); both are terminal-free and tested with fake executors in
`tests/autoresearch/test_campaign_controller.py` and
`tests/autoresearch/test_campaign_console.py`.

### Controller validation status (26 October 2026)

Review follow-up: stop requests are accepted during another batch. Reset helpers
have a separate 15-second shutdown grace, not the scientific stop timeout. Before
reset, the TUI writes `.git/tui-reset-incomplete.json` (or the worktree's Git
administration directory); only a successful matching reset clears it. A new
TUI session displays incomplete resets as failed and blocks start until an
explicit reset/run succeeds. This administrative record is not scientific
evidence or a reset backup. A failure stopping one owned process does not skip
cleanup attempts for the others.

Owned launchers have a private hidden console with redirected standard handles.
A native Windows check confirms a distinct, non-visible child console; this is
not a physical Windows Terminal rendering test. Tab/Shift+Tab switch campaign
tabs; inside dialogs they retain normal focus navigation. F6/Shift+F6 move
focus between report controls. Ctrl+Tab is only an alias if the host delivers it;
its physical Windows Terminal delivery remains unverified. Tool-path shortening
uses each report's root, and normal exit classification reads recorded terminal
outcomes immediately. Cancellation before the Copilot message channel exists
cleans up the owned bootstrap without pretending a scientific session ran.

- The report-first UX revision passes 102 focused controller, headless console
  and report-app checks. Synthetic rendered frames cover 160x45, 178x33,
  80x24, 60x24 and 48x16: actual report space, command/editor/button bounds,
  non-overlapping feedback/footer, contextual submission, settings Apply/Cancel,
  reset-mode fields and narrow-screen scrolling. This revision did not launch,
  reset or mutate a real campaign.
- 152 targeted controller, headless console, report/projection/timeline and
  stop-control tests pass. Windows boundary checks use the installed packaged
  PowerShell 7.6.8 and native Windows PowerShell 5.1 dummy scripts. They verify
  native child membership, forced cleanup, failed assignment, creation-policy
  failure and owner-process exit. A separate installed-PowerShell test verifies
  the `pwsh → uv → Python` chain and cooperative exit 130 without forced cleanup.
  Stop requests before or during the persistent Copilot runtime's initial
  connection return 130 without submitting a session. A genuine connection
  failure without a stop request remains a failure.
- An earlier real headless campaign attempt used the Windows PowerShell 5.1
  fallback, which failed in the existing launcher's `.ArgumentList` API before
  scientific work. That fallback and the subsequent unpackaged-only restriction
  have been removed. The existing packaged PowerShell is now used with the
  inherited Windows child policy; there is no runtime reinstall requirement.
- The real headless TUI exercised default `run 1` → `stop campaign-1` →
  `start campaign-1` → Ctrl+Q using the installed packaged PowerShell 7.6.8.
  Reset succeeded; both launchers returned 130 cooperatively, the first stop
  in 2.23 seconds. Resume preserved campaign ID
  `ecc45677-789c-42fe-b261-68dc326c3458`. The reset helper returned 0; all three
  jobs were empty at cleanup, with no forced termination. Campaign-2 and
  campaign-3 retained their state hashes, modification times, Git HEADs and
  clean Git status. The smoke driver's final bookkeeping assertion initially
  counted the reset helper as a launcher; its audit now separates the two.
  The application lifecycle assertions had completed before that driver error;
  no extra reset was performed for the bookkeeping correction.
- No operations completed during the observation window (campaign preparation),
  so this does not establish recovery of completed scientific work or a saved
  checkpoint. Physical Windows Terminal Ctrl+Tab delivery and terminal
  restoration still need an interactive check; headless tests cannot establish
  those physical-terminal behaviors.

Reference size is 160x45; the layout adapts down to an 80x24 and 60-column
fallback. The console keeps seven rows for tabs and open controls (38 report
rows at 160x45), or three with commands collapsed (42 report rows). It adds no
nested report frames or repeated state badges. At 80x24
and 60x24 the report retains context/models/last-training and hides its output
first, while commands and settings remain accessible. The settings dialog
stacks fields on narrow screens and scrolls without losing Apply/Cancel.
Controls remain available at 48x16, but the embedded report then truthfully
names 48x23 as its minimum window size. Below 48x16 the console shows the
terminal-too-small state without changing campaign execution.
At 80x24 the report keeps the header, the PI role table and the last-training
line, and hides the output log first. `NO_COLOR` and the terminal's color
capability are respected; `--light` selects the light theme.

Reading keys: Up/Down or `j`/`k` move, `Enter`/`Space` expand or collapse,
`Left`/`Right` collapse or expand, `/` searches, `f` filters by kind, `r`
opens the raw event payload, `End` returns to live follow, mouse wheel scrolls,
In the controller, Tab/Shift+Tab switch campaigns and F6/Shift+F6 move local
focus. In dialogs and standalone read-only reports, Tab/Shift+Tab move focus.
Ctrl+C copies selected output text or does nothing.
Ctrl+Q closes a read-only report without affecting external campaigns; in
the console it first stops all owned campaigns.

The durable snapshot and elapsed clocks refresh every 15 seconds. Terminal
campaigns freeze at recorded completion. For a TUI-owned launcher, acknowledged
stop/failure also freezes displayed campaign/stage elapsed clocks. Resume
excludes the paused intervals observed in this TUI session; a new stage excludes
only pauses overlapping that stage. The display is labelled `Campaign elapsed`
for owned runs, versus wall-clock `Campaign age` for read-only/unknown ownership.
Pause accounting is presentation-only and session-local: it does not alter
scientific timestamps or infer historical offline pauses. Reset clears it.
The header retains recorded start times, in local time; earlier days include
the date and unknown times are unavailable.

Active training shows elapsed duration and ETA in the progress panel and
timestamped timeline. New observations carry the existing runner ETA; older
feeds can estimate from two advancing observations in the same attempt. Missing,
stale, stopped or non-advancing data does not produce a fabricated zero ETA.
Live and reconstructed candidate announcements share a candidate identity, so
each checkpoint appears once and its identifier is not repeated in the row.

The observation feed is drained every second so PI messages and console lines
stay live; training progress events arrive every 15 seconds, matching the
console heartbeat.

## Data the report reads now

| Facts | Source (read-only) |
|---|---|
| Campaign, human goal, counters, stage IDs, inquiry, session, synthesis, roles, pending operation | `runner/state/research_state.json` |
| Completed operations, training dynamics, measurement panels, last-training proxy | `campaigns/results.jsonl` |
| Recorded usage (AIU / token rows) | `reports/session_usage/<campaign-id>.jsonl` |
| Live training reward/success and progress | `reports/tui_observations/<campaign-id>.jsonl` (written by `runner/observation_feed.py` and the launcher) |

Projection rules follow the specification: roles come only from
`model_roles`; development success is the latest completed evaluation for a
candidate in recorded order with its source shown; official panels never
become development evidence; usage excludes price and currency and keeps the
PI, coder and reviewer scopes; missing values render as `unavailable` or
`not measured`, never zero.

The header shows the latest allocated operation IDs (`I / S / T / M / E`),
the recorded human goal with the best development success and gap, the
recorded counters and the pending operation. The last-training line shows the
checkpoint with the highest recorded training success (falling back to reward
and then to the last checkpoint by steps). The development-success interval is
deferred and is not shown.

## Structured operator log

The output region is a virtualized `Tree` of collapsible timeline items:

- campaign → session → inquiry → operation → leaf event;
- backend PI sessions, scientific sessions, inquiries and operations are
  distinct groups, so a coding child never hides the operation that requested
  it;
- the active chain is expanded by default, older groups are collapsed;
- warnings and errors are expanded by default;
- every row has a fixed `HH:MM:SS` clock column at the left edge, independent of
  tree depth, separated by `│`; an event with no timestamp leaves the clock
  column blank rather than showing a placeholder, group headers add duration,
  and `r` shows the full recorded timestamp;
- training progress rows show the interval since the previous row, steps
  delta and steps per second when derivable;
- tool actions use the console's summaries and factual result lines, paired by
  `tool_call_id`; paths, search patterns and API targets wrap naturally instead
  of opening argument dumps; routine completed/zero-duration labels are omitted;
- PI messages appear once, in full, without Copilot session UUIDs; long actions
  and messages are open by default, can be collapsed, update as events arrive
  and reflow when the terminal is resized;
- raw arguments, patch payloads and session metadata are available through `r`,
  not mixed into the normal reading view;
- semantic colours follow the console: cyan PI/execution activity, magenta
  session context and ordinary result lines, emphasized scientific tool names,
  green success/created files, yellow warnings and red failures/deleted files;
  result assessments retain their individual success/warning/error colours;
- the reading area stays black (white in the light theme) while the fixed time
  column and its separator share a lighter grey band;
- coding handoffs show phase, agent, status and their structured detail;
- file changes show the repository-relative path, operation marker (`+`, `~`,
  `-`) and whether the PI operation request changed;
- measurement panel rows show episodes, seed and instrument on start, and
  episodes, duration and success on completion;
- the sticky `Now` line names the active or pending operation and its summary.

`Enter`/`Space` toggles the selected row, `Left`/`Right` collapse or expand,
`/` searches the full event text (including collapsed detail), `f` filters by
kind/category while keeping ancestors, and `r` opens the selected event's full
payload in a modal. `Esc` clears search or filter. Hovering a block marks its
visible rows with an accent `▌` in the left gutter. When the mouse leaves the
log, the marker returns to the keyboard cursor. There is no underline or pane
outline. Dragging across output text paints a text-selection background that
remains after release; `Ctrl+C` copies that selection.

The log renders typed events when `reports/tui_observations/<campaign-id>.events.jsonl`
exists. Otherwise it renders the legacy `console_line` feed and the durable
history synthesized from `research_state.json` and `results.jsonl`. The
reducer (`tui/timeline.py`) is terminal-free and tested with synthetic events.

## Observation feed (producer and consumer)

The Runner appends presentation events to
`reports/tui_observations/<campaign-id>.jsonl` under the campaign root (that
directory is presentation-only, ignored by campaign Git, and refused to PI and
analyst reads). One file per campaign means a reset cannot surface earlier
events. `runner/observation_feed.py` owns the writer: it is best-effort,
appends one JSON object per line, binds the campaign identity from durable
state (also in the Copilot adapter process), and swallows every failure so
presenting can never alter acceptance, execution, publication or recovery.
Setting `TUI_OBSERVATIONS` to another path moves the file; setting it to `off`
disables the feed. The report follows the current campaign's file
automatically, by byte offset: only appended complete lines are read, and a
shrunken or replaced file restarts from the beginning.

Observations are produced by neutral reporting facades and execution handlers,
before optional terminal rendering:

- Launcher (`researcher_session.ps1`, `run_research.ps1`) - the status lines
  and cards the launcher displays, including session start and resume
  identity; `session_start` supplies the live stage timer.
- `runner/reporting.py` `announce()` and `card()` - every Runner message
  and lifecycle card, with its existing scope classification (`pi`,
  `operation`, `warning`, `error`, ...) as the color channel.
- `runner/copilot/reporting.py` `SessionReporter` - tool calls, results,
  failures and coder/reviewer facts; `delta()`/`_close_message()` -
  PI text published while it is still being written (whole-word snapshots at
  most every 2 s, immediately on a paragraph break) and a final snapshot at
  turn end.
- `runner/execution.py` training and evaluation loops - structured
  `training_progress` and `eval_progress` (the progress panels never read
  formatted console text), plus `liveness` every status interval.
- `runner/run_experiment.py` - `execution_end` for completed, failed,
  interrupted and official-assessment operations; official assessment progress
  comes from its existing callback.

Events follow this shape (one JSON object per line):

```json
{"campaign_id": "...", "ts": "2026-10-24T12:41:04+00:00", "kind": "training_progress",
 "operation_id": "T4", "steps": 72000, "target": 120000, "elapsed_seconds": 728,
 "ep_rew_mean": 86.3, "scenario_metric": "success 97%"}
```

Kinds: `pi_message {text, final, turn}` (whole-word snapshots while the PI
writes, `final: true` at turn end; the report appends only the new text, so a
growing message never duplicates), `console_line {scope, text}`,
`training_progress` (`operation_id, steps, target, elapsed_seconds, eta_seconds,
ep_rew_mean, scenario_metric`), `eval_progress` (`operation_id, instrument,
official, episodes, episodes_total, elapsed_seconds`), `execution_end
{operation_id, status, text}`, `liveness {}`. The consumer still tolerates the
optional `session_start`, `activity` and `tool` kinds for future emitters.

Without an event file the report still renders the durable state, the
reconstructed operation timeline and recorded usage; the output states the
live-observation limitation on attachment. Foreign-campaign events are
rejected; replayed events are deduplicated.

### Typed event feed

`runner/typed_events.py` writes the maintainer-only typed stream to
`reports/tui_observations/<campaign-id>.events.jsonl`:

```json
{"schema_version": 1, "event_id": "...", "campaign_id": "...",
 "ts": "2026-10-24T12:41:04+00:00", "kind": "training_progress",
 "scope": "training", "severity": "info", "operation_id": "T4",
 "session_id": "S7", "inquiry_id": "I3",
 "payload": {"steps": 72000, "target": 120000, "ep_rew_mean": 86.3,
             "scenario_metric": "success 97%"}}
```

The writer is best-effort and never raises into the Runner. `TUI_TYPED_EVENTS`
moves the file or disables it with `off`. A domain handler owns the typed fact
and calls the reporting facade with `typed=False` to avoid a duplicate typed
copy. Generic `console_line`/`console_card` records are produced by the reporting
facade, not by a console renderer, and remain available without console output.
The launcher writes typed and legacy transports independently: disabling or
failing the legacy sink does not stop typed observations.

Domain emitters:

- launcher (`researcher_session.ps1`, `run_research.ps1`): `session_start` and
  status lines, written to both feeds;
- `runner/run_experiment.py`: `session_started`, `session_ended`,
  `campaign_goal_review`, `inquiry_opened`, `inquiry_reframed`,
  `inquiry_closed`, `checkpoint_saved`, `campaign_concluded`,
  `operation_requested`, `operation_started`, `operation_completed`,
  `operation_failed`, `role_assigned`, `candidate_created`,
  `scientific_model_validated`, and campaign/session usage totals;
- `runner/execution.py`: `training_checkpoints` (one record per saved
  candidate), `measurement_panel_started`, `measurement_panel_completed`,
  training/evaluation progress, `liveness` and structured warnings for stalls,
  timeouts and stops;
- `runner/repository.py`: `publication_retry` and `publication_recovered`;
- `runner/copilot/reporting.py` and `session_events.py`:
  `pi_message`, `pi_context`, `tool_call_started`, `tool_call_completed`,
  `tool_call_failed`, `tool_denied`, `file_changed`, `coding`,
  `operation_submitted`, `warning` and `error`;
- `runner/copilot/usage.py`: `usage_update` per durable accounting row;
- `runner/copilot/copilot_adapter.py`: `session_usage` at session end.

`typed_events.context()` binds `operation_id`, `session_id` and `inquiry_id`
for one execution scope, so progress and publication events inherit identity
without threading it through presentation functions. Lifecycle event IDs are
deterministic (`domain:<kind>:<id>:<state>`), so a resumed operation or a
replayed feed does not duplicate a fact the reducer has already seen.

Training progress carries the scenario-owned metric as the rendered
`scenario_metric` fragment; the Runner and the live progress path never read
the scenario's success field directly.

The TUI prefers the typed file and falls back to the legacy feed. Durable
history is folded into the same reducer, so a late attach still rebuilds the
campaign timeline.

### Parity with the console

The console stays fully functional and remains the presentation reference.
`runner/console.py` and `runner/copilot/copilot_console.py` are optional terminal
renderers only. They do not produce observations. The TUI imports shared
descriptions from the neutral reporting modules, never from either renderer.

Observation production can run with `reporting.rendering(None)` and
`SessionReporter(renderer=None)`. These are internal composition interfaces,
not a new launcher mode or a cutover. Default execution still uses the console.
The tests assert that:

- `announce()`, `card()` and `boundary()` print identical text with the typed
  emitter on and off;
- domain-owned lifecycle cards write their typed fact and no duplicate
  `console_card`;
- tool, coding, file and usage domain events carry the same numbers the console
  prints, before compaction;
- typed and legacy observations and accounting remain identical when both
  console renderer modules are unavailable;
- the TUI starts with imports of both console renderer modules blocked;
- launcher facts survive absent renderers and a disabled or broken legacy sink.

Historical feed compatibility remains. Transport redesign, controls and the
eventual console cutover are separate work, not part of this pass.

## Validation

```powershell
uv run pytest tests/autoresearch/test_reporting_independence.py tests/autoresearch/test_observation_feed.py tests/autoresearch/test_report_projector.py tests/autoresearch/test_report_app.py tests/autoresearch/test_report_timeline.py tests/autoresearch/test_campaign_controller.py tests/autoresearch/test_campaign_console.py
```

The tests cover the legacy and typed feed writers, console stdout identity
with the typed emitter on/off and with domain-owned `typed=False` funnels,
context merging, the projector contracts, the timeline reducer and the
headless rendering behavior:
single-screen composition, stage IDs, goal gap, counters, pending chip,
last-training proxy, live training reward/success, streamed/final PI
deduplication, timeline grouping, default collapse, search/filter, timestamps
and training intervals, paired tool calls with duration, coding/file/usage
rows, measurement-panel and training-checkpoint numbers, the progress lifecycle
(training and evaluation, official assessment label, module measurement with
unavailable counters, end-of-execution removal), reading position while new
output arrives, the 80x24 compact floor, the too-small fallback and stale
counter labeling. Real campaign state is exercised read-only by starting the
report against the campaign root; no integration check starts execution.
