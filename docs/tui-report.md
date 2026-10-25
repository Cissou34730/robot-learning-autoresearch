# Autoresearch terminal report (single-screen TUI)

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

```powershell
.\tools\run-report.ps1                 # default sibling robot-learning-campaigns
.\tools\run-report.ps1 -CampaignRoot <path>
.\tools\run-report.ps1 -Demo           # synthetic material, reads nothing
```

Directly: `uv run python -m tui --help` (options: `--campaign-root`,
`--events`, `--demo`, `--light`).

Reference size is 160x45; the layout adapts down to an 80x24 and 60-column
fallback and below 48x16 shows a `Terminal too small - need 48x16` message.
At 80x24 the report keeps the header, the PI role table and the last-training
line, and hides the output log first. `NO_COLOR` and the terminal's color
capability are respected; `--light` selects the light theme.

Reading keys: Up/Down or `j`/`k` move, `Enter`/`Space` expand or collapse,
`Left`/`Right` collapse or expand, `/` searches, `f` filters by kind, `r`
opens the raw event payload, `End` returns to live follow, mouse wheel scrolls,
Tab/Shift+Tab move between the event log and the model table; Ctrl+Q or Ctrl+C
closes the report (presentation only, never the campaign).

The durable snapshot and the elapsed clock refresh every 15 seconds. The
observation feed is drained every second so PI messages and console lines stay
live; training progress events arrive every 15 seconds, matching the console
heartbeat.

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
- the active chain is expanded by default, older groups are collapsed;
- warnings and errors are expanded by default;
- every leaf shows `HH:MM:SS`; group headers show start–end and duration;
- training progress rows show the interval since the previous row, steps
  delta and steps per second when derivable;
- the sticky `Now` line names the active or pending operation and its summary.

`Enter`/`Space` toggles the selected row, `Left`/`Right` collapse or expand,
`/` searches the full event text (including collapsed detail), `f` filters by
kind/category while keeping ancestors, and `r` opens the selected event's full
payload in a modal. `Esc` clears search or filter.

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

Emit points are the existing console funnels and structured counters, never
message-text matching:

- Launcher (`researcher_session.ps1`, `run_research.ps1`) - the status lines
  and cards the launcher displays, including session start and resume
  identity; `session_start` supplies the live stage timer.
- `runner/console.py` `announce()` and `card()` - every visible Runner line
  and lifecycle card, with its existing scope classification (`pi`,
  `operation`, `warning`, `error`, ...) as the color channel.
- `runner/copilot/copilot_console.py` `Console.line()` - tool calls, results,
  failures and coder/reviewer lines; `Console.delta()`/`_close_message()` -
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
 "ep_rew_mean": 86.3, "training_success": 0.97}
```

Kinds: `pi_message {text, final, turn}` (whole-word snapshots while the PI
writes, `final: true` at turn end; the report appends only the new text, so a
growing message never duplicates), `console_line {scope, text}`,
`training_progress` (`operation_id, steps, target, elapsed_seconds,
ep_rew_mean, training_success`), `eval_progress` (`operation_id, instrument,
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
             "training_success": 0.97}}
```

The writer is best-effort and never raises into the Runner. `TUI_TYPED_EVENTS`
moves the file or disables it with `off`. Current emitters:

- the launcher (`researcher_session.ps1`) writes the same status lines to both
  the legacy and typed feeds;
- `runner/console.py` `announce()` and `card()`: full text and card body before
  console compaction;
- `runner/copilot/copilot_console.py`: PI messages and tool/console lines;
- `runner/execution.py`: `training_progress` and `eval_progress` with full
  structured payloads;
- `runner/run_experiment.py`: operation requested/started/completed/failed,
  interrupted operations, and official-assessment progress/completion.

The TUI prefers the typed file and falls back to the legacy feed. Durable
history is folded into the same reducer, so a late attach still rebuilds the
campaign timeline.

## Validation

```powershell
uv run pytest tests/autoresearch/test_observation_feed.py tests/autoresearch/test_report_projector.py tests/autoresearch/test_report_app.py tests/autoresearch/test_report_timeline.py
```

The tests cover the legacy and typed feed writers, console stdout identity
with the typed emitter on/off, the projector contracts, the timeline reducer
and the headless rendering behavior:
single-screen composition, stage IDs, goal gap, counters, pending chip,
last-training proxy, live training reward/success, streamed/final PI
deduplication, timeline grouping, default collapse, search/filter, timestamps
and training intervals, the progress lifecycle (training and evaluation,
official assessment label, module measurement with unavailable counters,
end-of-execution removal), reading position while new output arrives, the
80x24 compact floor, the too-small fallback and stale counter labeling. Real
campaign state is exercised read-only by starting the report against the
campaign root; no integration check starts execution.
