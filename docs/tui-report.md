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
`NO_COLOR` and the terminal's color capability are respected; `--light`
selects the light theme.

Reading keys: mouse wheel, Page Up/Down, Home/End inside the output;
Tab/Shift+Tab move between the output and the model table; Ctrl+Q or Ctrl+C
closes the report (presentation only, never the campaign).

## Data the report reads now

| Facts | Source (read-only) |
|---|---|
| Campaign, inquiry, session, synthesis, roles, pending operation | `runner/state/research_state.json` |
| Completed operations, training dynamics, measurement panels | `campaigns/results.jsonl` |
| Recorded usage (AIU / token rows) | `reports/session_usage/<campaign-id>.jsonl` |
| Live observations | `reports/tui_observations/<campaign-id>.jsonl` (written by `runner/observation_feed.py` and the launcher) |

Projection rules follow the specification: roles come only from
`model_roles`; development success is the latest completed evaluation for a
candidate in recorded order with its source shown; official panels never
become development evidence; usage excludes price and currency and keeps the
PI, coder and reviewer scopes; missing values render as `unavailable` or
`not measured`, never zero.

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
 "operation_id": "T4", "steps": 72000, "target": 120000, "elapsed_seconds": 728}
```

Kinds: `pi_message {text, final, turn}` (whole-word snapshots while the PI
writes, `final: true` at turn end; the report appends only the new text, so a
growing message never duplicates), `console_line {scope, text}`,
`training_progress`, `eval_progress` (`operation_id, instrument, official,
episodes, episodes_total, elapsed_seconds`), `execution_end {operation_id,
status, text}`, `liveness {}`. The consumer still tolerates the optional
`session_start`, `activity` and `tool` kinds for future emitters.

Without an event file the report still renders the durable state, the
reconstructed operation timeline and recorded usage; the output states the
live-observation limitation on attachment. Foreign-campaign events are
rejected; replayed events are deduplicated.

## Validation

```powershell
uv run pytest tests/autoresearch/test_observation_feed.py tests/autoresearch/test_report_projector.py tests/autoresearch/test_report_app.py
```

The tests cover the feed writer and its console emit points, the projector
contracts and the headless rendering behavior:
single-screen composition, streamed/final PI deduplication, the progress
lifecycle (training and evaluation, official assessment label, module
measurement with unavailable counters, end-of-execution removal), reading
position while new output arrives, the too-small fallback and stale counter
labeling. Real campaign state is exercised read-only by starting the report
against the campaign root; no integration check starts execution.
