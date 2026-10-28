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
  - `tui/observations.py` - the observation record the report consumes, plus
    the synthetic feed used by `--demo`; `tui/journal.py` follows the event
    journal (see below).
  - `tui/report.py` - the single-screen report application.
  - `tui/demo.py` - synthetic campaign material for `--demo` and tests.
- `campaign_tui.ps1` - launcher helper in the harness root.
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
.\campaign_tui.ps1 -CampaignRoot <path>            # legacy report
.\campaign_tui.ps1 -Demo                           # legacy report, synthetic
.\campaign_tui.ps1                                 # console (campaigns + commands)
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
`.\campaign_tui.ps1` with no arguments) opens one Textual console with
one report tab per installed campaign folder, initially showing the first
installed campaign (normally campaign-1). Command entry is alongside the report,
not on a separate Commands tab, following the maintainer's updated UX direction
on 26 October. The standard folders are `robot-learning-campaigns\campaign-1`
through `campaign-5`; Tab/Shift+Tab cycle their tabs. Launching the console starts
nothing; campaigns run only when a command is submitted.

Controlled execution starts `python -m runner.launcher`, the reset and the
initializer with `uv` on PATH; no PowerShell host is involved. Each child gets
a private hidden console in a kill-on-close Job; the inherited Windows
desktop-app child policy keeps packaged native descendants contained. Missing
`uv` fails preflight before initialization, reset or launch, without preventing
the interface from opening.

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
  Only the reference field for the selected reset mode is visible. `--clean`
  is labelled as cleaning eligible changes, not merely cleaning logs.
- `run` initializes a missing standard folder from the recipe (same as
  `tools.run_parallel`), resets it (`--mode fresh --clean --recipe-ref
  baseline-distinct-episodes-v3-robot --force`) and launches it. `start`
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
  objects (see `docs/external-campaign-stop.md`). A campaign launched outside
  the console (`tools.run_parallel`, `run_research.ps1`) has no window; its tab
  follows its feed, and `stop` writes its stop request without owning it.

The machinery lives in `tui/process.py` (Job Objects, suspended creation,
instance lock, per-run control directories with captured console logs) and
`tui/controller.py` (command parsing, per-folder stage machines, batch
orchestration); both are terminal-free and tested with fake executors in
`tests/autoresearch/test_campaign_controller.py` and
`tests/autoresearch/test_campaign_console.py`.

### Controller validation status (26 October 2026)

This subsection records the PowerShell-launcher revision; see the
[27 October update](#python-launcher-27-october-2026) for the current launcher.

Review follow-up: stop requests are accepted during another batch. Reset helpers
have a separate 15-second shutdown grace, not the scientific stop timeout. The
reset itself, after it holds the campaign mutex and passes its checks, writes
`.git/reset-incomplete.json` (or the worktree's Git administration directory)
before its first campaign change; only a successful reset, from the TUI or the
console, removes it. A refused reset leaves no record. The TUI displays a
folder with this record as failed and blocks start until a reset succeeds.
This administrative record is not scientific
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

### Python launcher (27 October 2026)

The launcher, the reset entry point and the parallel tool are Python
(`runner.launcher`, `runner.launcher.reset`, `tools.run_parallel`); the
PowerShell launcher, session helpers, Copilot controller and reset script were
removed, and `run_research.ps1` is a thin wrapper. The console starts them with
`uv` directly. Every campaign has one stop request in its Git directory, so the
console can stop a campaign it did not start. The console terminal renderers
and the legacy `<campaign-id>.jsonl` feed were removed: launches write no
console output, and the typed feed is the only observation stream. Windows
containment tests now run dummy PowerShell scripts only as arbitrary native
children, and the `uv → Python` chain test verifies a cooperative exit 130
without forced cleanup.

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

One master tick runs every second. It drains the observation feed, advances the
elapsed and ETA clocks locally between Runner samples, and draws everything once.
The durable files (state, results, usage) are re-read only when they change. A
console tab that is not shown does no work and catches up when it is shown. Terminal
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

The Runner publishes one training sample every 30 seconds. It polls evaluation
progress every second and publishes a sample when the counters change, and at
least every 15 seconds. PI text is
published at most once per second. Timeline progress rows are kept one per
30 seconds for training and one per 15 seconds for evaluation; the newest row
updates in place. A widget is redrawn only when its content changes: a header
counter that ticks does not re-lay out the screen, and a refresh of unchanged
durable data redraws nothing. A tick with no new event does no work on the log
except the counter of a running tool, so its cost does not grow with the length
of the campaign. A finished session is shown folded with its number of events;
its rows are built only when you open it. Each campaign tab starts with a dot,
for every tab, shown or not. State beats phase: red for failed, amber for
stopping, resetting or stale counters, grey-blue for completed, muted for idle
or stopped. While a campaign runs, the dot shows its phase: blue for training,
cyan for evaluating, magenta for coding, gold for the official assessment (these
four pulse between a full and a half dot once a second), violet for the campaign
preparation, and green for the PI working or waiting between operations. When the
campaign is not running and the final benchmark has a result, the dot becomes a
diamond: bright green (`◆`) when the goal was reached, orange (`◆`) when it was
not. It comes from the durable `official_assessment` status, so it holds after a
restart, and the status line adds `official assessment: goal reached` or `goal
not reached`. A tab
that is not shown keeps reading its events and draws nothing until you open it.
A hidden tab also follows a new campaign that appears in its folder (a reset or
a new run), and a campaign started outside the console (for example with
`tools.run_parallel`) is detected through its campaign lock every two seconds,
so its tab shows the same phase colour and pulse as a console-started one.
Every row has exactly one owner, named by the event itself (see "Event journal"
below): the log is a fold of the journal alone and never infers, merges or
reorders. Siblings are shown in the order the journal recorded them.

## Data the report reads now

| Facts | Source (read-only) |
|---|---|
| Campaign, human goal, counters, stage IDs, inquiry, session, synthesis, roles, pending operation (header and model table only) | `runner/state/research_state.json` |
| Completed operations, training dynamics, measurement panels, last-training proxy (header only) | `campaigns/results.jsonl` |
| Recorded usage (AIU / token rows) | `reports/session_usage/<campaign-id>.jsonl` |
| The event log, live training reward/success, progress and every other live fact | `reports/tui_observations/<campaign-id>.events.v2.jsonl` (event journal, `runner/typed_events.py`) |

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
- tool actions use shared summaries and factual result lines, paired by
  `tool_call_id`; paths, search patterns and API targets wrap naturally instead
  of opening argument dumps; routine completed/zero-duration labels are omitted;
- PI messages appear once, in full, without Copilot session UUIDs; long actions
  and messages are open by default, can be collapsed, update as events arrive
  and reflow when the terminal is resized;
- raw arguments, patch payloads and session metadata are available through `r`,
  not mixed into the normal reading view;
- semantic colours: cyan PI/execution activity, magenta
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
- the sticky `Now` line names the active or pending operation and its summary;
- the official assessment is a top-level group of its own, last, open by
  default, shown where it happened. Its header carries the model and, once done,
  the outcome (`passed`/`failed`, success rate over the episodes, the required
  cutoff and the margin). Its rows are the start, the progress, a result row
  (red when the goal was not reached, green when it was), the campaign
  conclusion and the final usage. The benchmark adapter reports the required
  cutoff and the Runner copies it into the official events;
- campaign usage and the PI's request to conclude show in the session that wrote
  them. A usage row also shows how many AIU the campaign used since the last one,
  for example `33.57 AIU (+5.70)`;
- a run-state change adds no row (each one repeats an operation row); it drives
  the `Now` line and the tab. The pinned Campaign group keeps only the start of
  the campaign and notices that no session owns.

`Enter`/`Space` toggles the selected row, `Left`/`Right` collapse or expand,
`/` searches the full event text (including collapsed detail), `f` filters by
kind/category while keeping ancestors, and `r` opens the selected event's full
payload in a modal. `Esc` clears search or filter. Hovering a block marks its
visible rows with an accent `▌` in the left gutter. When the mouse leaves the
log, the marker returns to the keyboard cursor. There is no underline or pane
outline. Dragging across output text paints a text-selection background that
remains after release; `Ctrl+C` copies that selection.

The log renders the events of
`reports/tui_observations/<campaign-id>.events.v2.jsonl` and nothing else. The
durable files feed the header and the model table only. The reducer
(`tui/timeline.py`) is terminal-free, deterministic and tested with events
written by the real writer.

## Event journal (producer and consumer)

`runner/typed_events.py` writes the maintainer-only journal to
`reports/tui_observations/<campaign-id>.events.v2.jsonl` under the campaign root
(that directory is presentation-only, ignored by campaign Git, and refused to PI
and analyst reads). One file per campaign means a reset cannot surface earlier
events; the version in the file name means an older runner's file is never read
as this one (a campaign started before this schema shows "waiting for events").
The writer is best-effort: it appends each record with one binary write to a
file opened for append, binds the campaign identity from durable state (also in
the Copilot adapter process), and swallows every failure so presenting can never
alter acceptance, execution, publication or recovery. `TUI_TYPED_EVENTS` moves
the file or disables it with `off`. The report follows the current campaign's
file by byte offset: only appended complete lines are read, an unfinished last
line waits for its newline, and a shrunken or replaced file restarts from the
beginning. A complete line that cannot be decoded, a foreign campaign and a
wrong schema are reported in the header, never in the log. It is the only
observation stream; nothing is written to a console.

### Identity contract

`runner/event_contract.py` is the one statement of the contract, shared by the
writer, the reader and the tests. Every record has the envelope
`schema_version, event_id, campaign_id, ts, kind, scope, severity, session_id,
operation_id, inquiry_id, attempt, actor, payload`.

| Field | Meaning |
|---|---|
| `session_id` | The durable session key: `S<n>`, or `preparation` for the campaign preparation (one group, whatever the number of PI restarts). Never a backend conversation id; that id stays in the payload. |
| `operation_id` | `T3`, `M2`, `E5`, or `official` for the official assessment (an operation of the campaign, with no session). |
| `inquiry_id` | The inquiry. An inquiry spans sessions, so it never owns an operation by itself. |
| `attempt`, `actor` | The PI invocation and the speaker (`pi`, `coder`, `reviewer`, `runner`, `launcher`). They keep rows of different invocations apart. |

`RULES` in that module lists, for each event kind, the identities it must carry
and whether it belongs to a session, an operation or the campaign. The reducer
attaches a row to the owner the event names and to nothing else. An event that
lacks a required identity is not guessed: it shows as a diagnostic row. A kind
that is not in `RULES` has no requirement and shows under the most specific
owner it names, or under the Campaign group, so a new step appears without any
change to the reducer.

```json
{"schema_version": 2, "event_id": "...", "campaign_id": "...",
 "ts": "2026-10-24T12:41:04+00:00", "kind": "training_progress",
 "scope": "training", "severity": "info", "operation_id": "T4",
 "session_id": "S7", "inquiry_id": "I3", "attempt": "", "actor": "runner",
 "payload": {"steps": 72000, "target": 120000, "ep_rew_mean": 86.3,
             "scenario_metric": "success 97%"}}
```

Emitters:

- launcher (`runner/launcher/events.py`): `session_start` (live stage timer; it
  carries the backend id in its payload), launcher status lines and cards as
  `notice`, and `error` when a launch ends in failure;
- `runner/reporting.py` `announce()`, `card()` and `boundary()`: `notice`
  events (`{text, scope}` or `{title, body, scope}`), with the scope (`pi`,
  `operation`, `warning`, `error`, ...) as the colour channel; `diagnostic()`
  writes an `error` event and adds the message to the Runner's structured
  result for the launcher;
- `runner/run_experiment.py`: `session_started`, `session_ended`,
  `campaign_goal_review`, `inquiry_opened`, `inquiry_reframed`,
  `inquiry_closed`, `checkpoint_saved`, `campaign_concluded`,
  `operation_requested`, `operation_started`, `operation_completed`
  (including interrupted operations), `operation_failed`, `role_assigned`,
  `candidate_created`, `scientific_model_validated`, campaign/session usage
  totals and official-assessment progress;
- `runner/execution.py`: `training_checkpoints` (one record per saved
  candidate), `measurement_panel_started`, `measurement_panel_completed`,
  `training_progress`, `eval_progress`, `liveness` and structured warnings for
  stalls, timeouts and stops;
- `runner/repository.py`: `publication_retry` and `publication_recovered`;
- `runner/copilot/reporting.py` and `session_events.py`: `pi_message` (whole-word
  snapshots at most every 2 s or at a paragraph break, `final: true` at turn
  end; the report appends only new text), `pi_context`, `tool_call_started`,
  `tool_call_completed`, `tool_call_failed`, `tool_denied`, `file_changed`,
  `coding`, `operation_submitted`, `warning` and `error`;
- `runner/copilot/usage.py`: `usage_update` per durable accounting row;
- `runner/copilot/copilot_adapter.py`: `session_usage` at session end.

`typed_events.context()` binds the owner (`session_id`, `operation_id`,
`inquiry_id`, `attempt`, `actor`) for one scope, so progress, publication and
PI events inherit it without threading it through presentation functions. The
owner is process-wide, not task-local: the Copilot SDK calls its handlers from
its own tasks, and each process owns one piece of work at a time. The adapter
binds the durable session, the invocation and the actor once per PI invocation,
before anything is reported, so the failure and accounting paths carry them too.
Lifecycle event IDs are deterministic (`domain:<kind>:<id>:<state>`), so a
resumed operation or a replayed journal does not duplicate a fact the reducer
has already seen.

Training progress carries the scenario-owned metric as the rendered
`scenario_metric` fragment; the Runner and the live progress path never read
the scenario's success field directly.

Without a journal file the report renders the header and the model table from
durable state and the log states "Now: waiting for events". It rebuilds no
history from durable records.

When the launcher stops on a failure (a trust refusal, a failed bounded session,
a Runner error it cannot recover from), it writes an `error` event with code
`launcher_failed` or `stop_deadline_exceeded`, owned by the session in progress
(`preparation`, or `S<n>`) and carrying the full reason. The log shows it in
that session. The header's attention line repeats it until a new launch writes
`campaign_started`, `session_start` or `operation_started`. When the launcher
stops before it can write events (a dirty harness, a busy lock, an argument
error), the console tab shows the last line the launcher wrote to standard
error after "launcher exited with code".

### Decision: one journal file, followed by the console; no live connection

Decided 2026-10-28 by the maintainer. Asked again later? Start here.

**Question.** The journal is a file that the TUI polls. Should the TUI instead
receive events directly from the processes that produce them, with no file?

**Decision.** Keep the file as the one journal. Producers append to it; the
console follows its end. Do not add a second, live path from the producers to
the console.

**Options considered.**

- *No file; the launcher runs inside the console.* Rejected: impossible. The
  campaign folder is fixed once per process (`runner/paths.py`, read at import
  by the launcher, the Runner and the adapter). The console shows up to five
  campaigns, so five launchers in one process would share one folder. This is
  why each campaign has its own launcher process.
- *No file; each process sends its events to a listener in the console.*
  Rejected: a campaign started with `tools.run_parallel` has no console, so
  its processes have nobody to send to, and a console opened afterwards cannot
  connect to processes that are already running. For such campaigns the file is
  the only place the events exist, so the console must read it in any case.
- *File as a record plus a live connection to the console.* Rejected for now:
  the file reader must stay for the case above, so the connection would be a
  second path for the same facts. It would add a local listener with a token,
  a short settle-and-sort window (events of two processes can arrive a few
  milliseconds apart), and a catch-up step at start-up that drops duplicates by
  `event_id`. Its only gain is a delay of a few hundred milliseconds instead of
  up to one second, for campaigns started from the console. The defects this
  work removed came from several paths carrying the same fact.
- *File only (chosen).* One writer path, one reader path, the same for a
  campaign started by the console, by `run_parallel`, or before the console
  opened. A restart of the console loses nothing, because the log is rebuilt
  from the file.

**What a file-only design already gives.** The source writes each event once,
in order, with its owners named. The console is a subscriber that follows the
end of an append-only log. Ordering is the file's order, so a replay is exact.

**Facts behind the decision.**

- Before the Python launcher (2026-10-27) the launcher and the Runner printed
  to the terminal. That output was recorded nowhere: closing the terminal lost
  it. The TUI of #67 and #68 already read a per-campaign `.jsonl` feed.
- A closed console already stops the campaigns it started (they run in a
  kill-on-close job object), but campaigns started elsewhere keep running and
  must stay observable.
- Measured on recorded campaigns before this change: records up to 253 KB,
  no torn line seen, six concurrent writers kept every record intact. This is
  an observation, not a guarantee of append atomicity on Windows.

**If the one-second delay matters.** Replace the poll with a file-change
notification so the console wakes when the file grows. It needs no server and
no second path, and it works for every way of starting a campaign. The one
second tick stays for the clocks (elapsed time, ETA, the running-tool counter,
the tab dots), which change without any event.

**When to reopen.** If campaigns are always started from the console, or if a
console that is not on the same machine is needed. Then a live connection with
the file kept as the record (catch-up from the file, drop by `event_id`) is the
design to build; the identity contract and the fold do not change, because they
work on events whatever the transport.

## Validation

```powershell
uv run pytest tests/autoresearch/test_reporting_independence.py tests/autoresearch/test_observation_feed.py tests/autoresearch/test_event_journal_contract.py tests/autoresearch/test_journal_panel_rules.py tests/autoresearch/test_timeline_ownership.py tests/autoresearch/test_report_projector.py tests/autoresearch/test_report_app.py tests/autoresearch/test_report_timeline.py tests/autoresearch/test_campaign_controller.py tests/autoresearch/test_campaign_console.py tests/autoresearch/test_launcher.py tests/autoresearch/test_stop_control.py
```

The tests cover the writer and reader, the identity contract (every emitted
kind is listed; strict mode rejects an event without its owner), concurrent
writers, the absence of console output from every producer, the real panel
following a journal written by the real writer in several chunk sizes (one
group per session, operations under their own session, the official assessment
as its own last group, every row timed and unique, a step unknown to the
panel still shown, panel equal to a fresh fold), the projector contracts, the
timeline reducer, the launcher's exclusion, stop and external-stop behaviour,
and the headless rendering behavior:
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
