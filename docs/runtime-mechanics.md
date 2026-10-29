# Runtime mechanics

Maintainer reference for the agent runtime behind the PI-facing contracts.
Campaign agents cannot read this file. PI-facing rules live in
`contracts/authority.md`, `contracts/program.md` and `contracts/instruments.md`.

## Agent runtime

The Copilot agent runtime uses `github-copilot-sdk==1.0.26`. Its native
subagents, hooks and custom tools are the agent runtime. The scientific stack
and Runner operations stay separate from the SDK.

The main PI session has `view`, `rg` and `glob`, the custom evidence tools,
`scientific_api_reference`, `scientific_coding` and `submit_operation`. The
permission handler denies every main-session file write. The trusted launcher
validates each structured request through Runner and returns factual results
and the current state to the same conversation.

The preliminary analyst has `view`, `rg`, `glob` and `apply_patch` (with
`create` and `edit` on external-provider routes) and no shell. Coding delegation
is not exposed in that phase.

## Launcher and observations

The campaign launcher is the Python package `runner/launcher/`
(`python -m runner.launcher`). Small modules own one concern each: options and
command line (`options`, `cli`), campaign exclusion (`campaign_lock`),
cooperative stop (`stop`), child processes and the run log (`child`), the trust
gate (`trust`), Runner invocations (`runner_client`), PI prompts and objectives
(`prompts`), the persistent Copilot runtime and its control channel
(`copilot_runtime`), PI sessions (`pi_session`), operation submissions
(`operation_bridge`), campaign phases (`phases`) and the loop (`campaign`);
`assembly` composes them. `pstext` reproduces the PowerShell text rendering the
earlier launcher used, so the PI's prompts and tool results are unchanged.

Runner invocations write their data to a JSON result file (`--result-path`,
`runner/invocation_result.py`): validation verdicts, errors and failure
summaries. Standard output and error of every child go only to the launcher
log `<campaign>\reports\launcher\<UTC time>-<pid>.log`; nothing is parsed from
them. The launcher writes nothing to a console.

`runner/reporting.py` and `runner/copilot/reporting.py` own observations and
shared display descriptions. SDK callbacks and coding/operation handlers use
`SessionReporter` and `CodingReporter`, which keep accounting and message
assembly and publish facts to the campaign's typed event feed
(`runner/typed_events.py`). Runner and launcher announcements are `notice`
events. There is no terminal renderer and no second feed; the TUI reads the
typed feed. See [the report documentation](tui-report.md).

This separation does not add campaign controls, change transport or change
agent authority.

## Write protection

Copilot hooks refuse PI and coder writes outside the PI-owned paths. Code the
PI writes runs in Runner child processes that no hook sees: training,
research evaluation, task-reference assessment and `robot_learning.*` lab
modules start through `runner.pi_code_guard`. Its Python audit hook refuses
file writes, deletes, renames and links that the trust gate would reject:
campaign files outside the PI-owned and Runner-written paths, the Runner's
own records and any file of the separate harness. It is not an operating-system
sandbox: processes the PI code starts do not inherit it.

The launcher's trust gate stays as the backstop. In the campaign it compares
HEAD and every gated file; in the separate harness it compares only the files a
campaign loads (`runner/`, `benchmark/`, `contracts/`, `tools/`,
`pyproject.toml`, `uv.lock`, see `runner.paths.is_harness_runtime`). The
Runner's clean-worktree check before protected evaluation uses the same harness
scope, so maintainer documents and commits do not stop a campaign. The
pre-commit hook `.githooks/pre-commit` (`tools/commit_guard.py`) refuses a
commit of those runtime files while any campaign holds its lock.

The maintainer console orchestrates explicit initialize/reset/start/stop commands
through `tui/controller.py`; it does not add scientific execution or recovery
logic. Each tab has an explicit campaign root and independent readers.
`tui/process.py` starts launchers and command helpers with `uv` inside Windows
jobs (helpers kill on close; launchers do not, so the console can leave them
running). A Windows desktop-app creation policy keeps native
descendants of packaged executables in the same boundary. Normal stopping uses
the campaign's stop request in its Git directory; timeout/failure cleanup is
separate. See [the stop contract](external-campaign-stop.md) for deadlines and
persistence limits. A campaign started without the console
(`tools.run_parallel`, `run_research.ps1`) runs without any console window and
can be stopped from the console or by writing its stop request.

## Coding handoff

`scientific_coding` dispatches a native coding subagent. Its readable and
writable files are bound mechanically to the explicit request. Native start
instructions state the locked scientific API versions. Coder and reviewer
receive fixed task context from `load_task_context` in
`runner/copilot/coding_contracts.py`: the scenario, an excerpt of
`contracts/authority.md` and excerpts of `contracts/instruments/coding.md` and
`contracts/instruments/measurement.md`.

Each new assignment receives an independent native review with high
reasoning. The coder uses the PI's model. The reviewer uses the PI's model on
Copilot and Copilot gpt-6-luna when the PI runs on an external provider; there
the coder edits with `create` and `edit` instead of `apply_patch` (OI-063).
Corrections reuse that reviewer to check only the reported problems
and errors introduced by the repair. The reviewer has exactly scoped reads and
no write or execution authority. A failed review goes unchanged to the same
coder within the original intent and file scope. The PI receives the final
package or a blocked requirement (`needs_pi`).

A correction may supply intent and handle alone; the handler keeps and
revalidates the immutable stored file scope. A handle from another bounded
context does not authorize attaching a coder. Lifecycle hooks and change
reports support PI review; they do not certify scientific validity.

Reviewer usage is recorded separately from coder and PI usage.

## Read and search policy

Read restrictions are tool-level, not an operating-system sandbox. The shared
reserved-script policy in `runner/copilot/path_policy.py` applies to `view`
and scoped search. Searches apply it to
descendants before reading content or returning paths. Maintainer documents
(`AGENTS.md`, `README.md`, `docs/`), tests, Runner, benchmark and launch
scripts are reserved in every phase. The preliminary phase can read all of
`robot_learning/`; later phases read only PI-owned scientific files there.
No session has a shell.

## Contexts and recovery

The Copilot runtime stays alive across operations and bounded contexts.
Ordinary results continue in the same context. Checkpoints end it, and the
launcher starts a fresh context from durable state. An interrupted or lost
response is recovered from pending or completed Runner state, not by blind
resubmission. Publication failures stop for repair; they do not authorize
reacceptance or re-execution.

The controller recovers accepted or completed transactions after channel loss.
It does not replay a tool call or fabricate checkpoint content. Main SDK
resumes disable automatic unfinished-work continuation; the resume prompt
includes current durable Runner metadata.

## Operation submission

`submit_operation` is bound by the trusted launcher to the active campaign and
bounded session and validated with Runner's schema-6 acceptance checks. No
model-supplied Runner arguments or exchange paths are accepted; the main PI
never authors `pi_workspace/operation_request.json`. Validation capture is
silent. Execution stdout and stderr stream live to the console; only bounded
tails are kept for error feedback. Two rejected submissions stop the bounded
session (one retry).

Stop requests are cooperative. When the launcher deadline expires, it stops
only its own process tree and preserves the pending transaction for recovery.

## Deadline and usage accounting

The PI deadline (default 30 minutes) measures active session time, which
includes coding and review and excludes Runner execution waits. Runner waits
use no model polls. Usage reports are separate: PI usage excludes delegated
coding and review, and reviewer usage has its own `scientific_reviewer` role,
configured model and reasoning, and reported actual models. SDK native-task
lifetime totals are labeled separately and are not added again for each
correction.

## Coding handler details

- The handler resolves and validates the SDK model and tool configuration
  before dispatch; unavailable capabilities are reported, with no fallback to
  manual coding sessions.
- Permission callbacks use the native permission event identity and the
  current file binding, not the arrival of a tool-start event. Unknown or stale
  identities fail closed with a harness authorization error.
- Completion handling challenges an incomplete engineering handoff, not
  scientific adequacy. The stop hook applies to corrections as well as the
  initial invocation. The handler waits for the stop handoff and native task
  idle state before unlocking operation submission.
- Corrections send the correction intent and context, incremental changes and
  the previous review to the same reviewer, without resending the original
  request, unchanged contracts or duplicate repair instructions.
- A missing or non-idle stored reviewer rejects correction dispatch; no
  replacement reviewer is created for that assignment. The handler verifies
  the reported reviewer model and reasoning.
- File permissions are enforced by the binding, not by parsing the review
  `where` field. Cancellation preserves review output.

## Evidence reader internals

Large JSON artifacts use a temporary, fingerprint-verified file-backed view,
removed after each request; original-byte paging uses the recorded source
bytes. The reader process keeps bounded byte-span metadata: validation results
are keyed by fingerprint and validation limits, container end offsets by
fingerprint and start offset. Concurrent requests share these scans. Neither
cache keeps snapshots or decoded trees.

## Publication

Runner commits scientific code and compact operation records to campaign Git
and never pushes. Raw measurements under `campaigns/evaluations/<campaign-id>/`
and training logs stay local and ignored; a Git checkout alone does not hold
the full measurement data. Publication failures keep Git's specific error and
stop without re-execution.
