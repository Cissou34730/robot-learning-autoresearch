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
| Live observations | optional JSONL event file (below) |

Projection rules follow the specification: roles come only from
`model_roles`; development success is the latest completed evaluation for a
candidate in recorded order with its source shown; official panels never
become development evidence; usage excludes price and currency and keeps the
PI, coder and reviewer scopes; missing values render as `unavailable` or
`not measured`, never zero.

## Observation feed (consumer implemented; producers intentionally out of this pass)

Per the maintainer's direction this pass changed no campaign-side code, so no
runner/PI producer writes observation events yet. The consumer is ready and
events follow this shape (one JSON object per line):

```json
{"campaign_id": "...", "ts": "2026-10-23T12:41:04Z", "kind": "training_progress",
 "operation_id": "T4", "attempt": 1, "steps": 72000, "target": 120000,
 "elapsed_seconds": 728}
```

Kinds: `session_start {session_id, stage_started_at}`, `activity {label}`,
`pi_message {session_id, text}` (full message text once, deduplicated by the
consumer against streamed/final replays), `tool {agent, name, detail}`,
`console_line {scope, text}`, `training_progress`, `eval_progress`
(`operation_id, instrument, official, panel_index, panel_total,
completed_panels, episodes, episodes_total, elapsed_seconds`,
`execution_end {operation_id, status, text}`, `liveness {}`.

Without an event file the report still renders the durable state, the
reconstructed operation timeline and recorded usage; the output states the
live-observation limitation on attachment, and progress panels appear only
from structured events, never from message-text matching. Foreign-campaign
events are rejected; replayed events are deduplicated.

Future work authorized later: small emit taps (console cards, the structured
training/evaluation heartbeat call sites and the copilot Console stream) that
append this JSONL under the campaign's `reports/` directory when an
environment variable selects it, plus launcher wiring.

## Validation

```powershell
uv run pytest tests/autoresearch/test_report_projector.py tests/autoresearch/test_report_app.py
```

The tests cover the projector contracts and the headless rendering behavior:
single-screen composition, streamed/final PI deduplication, the progress
lifecycle (training and evaluation, official assessment label, module
measurement with unavailable counters, end-of-execution removal), reading
position while new output arrives, the too-small fallback and stale counter
labeling. Real campaign state is exercised read-only by starting the report
against the campaign root; no integration check starts execution.
