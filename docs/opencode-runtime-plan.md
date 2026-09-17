# Optional OpenCode TypeScript SDK Implementation Plan

Status: implemented on branch `feature/opencode-researcher-backend`. Offline
verification is green; the live-provider checks under "Verification And
Acceptance" are still outstanding. The runtime itself is documented in
[opencode-runtime.md](opencode-runtime.md).

## Objective

Add the official OpenCode TypeScript SDK, using OpenCode Go, as a selectable
alternative alongside the existing Copilot Python SDK adapter. Both backends
remain available; this is not a migration or replacement. Preserve the bounded
Researcher workflow and existing console experience. The research engine remains
Python and the orchestrator remains PowerShell. Do not introduce a
Python-to-TypeScript bridge or implement a custom REST/SSE client.

## Required Behavior

- Keep Copilot as the default for existing launcher commands. Select OpenCode
  explicitly; do not remove or rewrite the working Copilot adapter or dependency.
- Work in the invoking process's current directory, including linked worktrees.
  The OpenCode option must never hardcode a checkout path or derive its work
  directory from the adapter's source location.
- Run unattended. Do not add permission prompts or require human approvals
  during Researcher execution. Preserve the existing automatic command denials.
- Preserve streamed prose, hidden reasoning, tool starts and failures, file
  notices, turn summaries, phase labels, and invocation summaries.
- Preserve phase-specific continuation, bounded execution, and process exit
  codes. A retry must never resume another backend's, phase's, or worktree's
  session. Do not automatically fall back to the other backend on failure.
- Keep OpenCode responsible for provider authentication, provider headers,
  conversation storage, replay, compaction, and tool execution.
- Keep deliverables and their protected validators authoritative. Neither
  printed prose nor runtime success determines scientific phase completion.
- Do not change training, evaluation, lineage decisions, campaign evidence, or
  the scientific Python dependency stack.

## Existing Integration Points

| Surface | Current contract | Planned treatment |
| --- | --- | --- |
| [run_research.ps1](../run_research.ps1) | `Invoke-ResearcherSession` creates a UUID per phase and reuses it on retry; invokes the adapter and reads its exit code | Add explicit backend selection; keep the existing Copilot command as default and preserve phase arguments and retry decisions |
| [researcher_session.ps1](../researcher_session.ps1) | Observes process result, deliverable presence, and validity independently | Keep behavior unchanged |
| [researcher_copilot.py](../researcher_copilot.py) | Runtime lifecycle, command guardrails, console, usage recording | Retain the adapter; use its behavior as the reference for the separate OpenCode adapter |
| [research/runner_protocol.py](../research/runner_protocol.py) | Explicitly protects the Python adapter and dependency metadata | Retain existing protection and additionally protect the OpenCode runtime and its dependency/configuration surface |
| [tools/campaign_report.py](../tools/campaign_report.py) | Reads per-invocation usage, currently including AIU | Support legacy Copilot and new OpenCode accounting without conflating units |
| [pyproject.toml](../pyproject.toml) | Researcher group contains Copilot SDK and `jello` | Retain both dependencies and the fixed Python stack; add OpenCode dependencies separately |

The launcher currently executes `Set-Location $PSScriptRoot`. Consequently,
invoking another checkout's launcher by absolute path changes the target
worktree. For the OpenCode option, capture the invocation directory before any
such redirection, require launch from the intended worktree root, resolve the
adapter and campaign paths there, and fail clearly if expected repository files
are absent. Sourcing launcher helpers must not redirect OpenCode to the script's
worktree. Preserve existing Copilot launch behavior; do not bundle a Copilot
working-directory refactor into this addition.

The existing machine-wide campaign/reset mutex is independent of SDK server
ports. Preserve it. Multiple worktrees must be selectable and isolated, but
enabling simultaneous campaign loops is outside this addition.

## Backend Selection

- Add a launcher parameter such as `-ResearcherBackend copilot|opencode`, defaulting
  to `copilot`. Both options run the same Researcher phase protocol and validators.
- Dispatch Copilot to the existing Python adapter through `uv run`; dispatch
  OpenCode directly to its TypeScript adapter through Node. No adapter calls the
  other, and there is no Python/TypeScript bridge.
- Resolve omitted model/reasoning defaults for the selected backend. Preserve
  current Copilot defaults; use a verified provider-qualified OpenCode Go model
  and supported reasoning setting for OpenCode. Never pass a Copilot default
  model to OpenCode by accident or reinterpret explicit model choices silently.
- Check prerequisites only for the selected backend. Copilot execution must not
  require Node, OpenCode, or OpenCode authentication; OpenCode execution must not
  require Copilot authentication. Shared scientific Python prerequisites remain.
- Bind the backend and resolved model configuration to the phase's session and
  reuse them on retry. A backend change starts a new session at a phase boundary,
  not a cross-runtime resume or transcript conversion.

## Architecture

The existing Copilot execution path remains. For an OpenCode invocation:

1. PowerShell starts one TypeScript adapter for the bounded invocation.
2. The adapter captures `process.cwd()` once and uses it for all worktree-local
   paths, command observations, accounting, and session binding.
3. The official SDK starts a dedicated loopback OpenCode server, inheriting that
   directory. Request a dynamically assigned port and use the returned URL;
   never silently attach to an existing server on the default port.
4. An SDK client targets that URL with `directory` set to the captured current
   directory. The SDK handles any directory header/query encoding. There is no
   manually implemented directory router or provider-header management.
5. A typed event reducer translates OpenCode updates into the console's small
   presentation API. It also maintains invocation counters and completion state.
6. Cleanup aborts active work when necessary, closes the event subscription, and
   closes only this invocation's server. Persisted OpenCode history survives.

Proposed runtime: Node.js 24 LTS with native TypeScript execution, erasable type
syntax, and the built-in test runner. Add a minimal package manifest, lockfile,
and no-emit TypeScript configuration. Use a local, pinned SDK dependency, not an
on-demand `npx` download. Start with OpenCode CLI/SDK `1.18.23` and the `/v2`
client surface, subject to the compatibility gate below. Do not install or
upgrade anything during ordinary campaign execution.

Keep the implementation compact: a root TypeScript adapter, with a separate
console/policy module only if needed to keep lifecycle and event logic readable.
Keep the existing Python adapter alongside it. A small launcher dispatch is
sufficient; do not introduce a reusable multi-provider framework or automatic
cross-backend fallback.

## Compatibility Gate

Before enabling the OpenCode launcher option, verify the selected CLI and matching published
SDK together in a disposable directory. This is an implementation gate, not a
request to run training or a campaign.

- Confirm Windows server startup, inherited working directory, dynamic port
  selection, SDK cleanup, optional server authentication, and version checking.
- Verify the configured OpenCode Go provider/model is connected and available.
  Do not reuse Copilot's bare model ID or silently strip the provider prefix.
- Map the existing reasoning argument to a supported model variant or provider
  option. Reject unsupported combinations instead of silently ignoring them.
- Verify v2 text-delta, tool-state, step, usage, permission, error, retry, and
  idle schemas against actual emitted events. The earlier discussion used
  legacy generated types; do not copy its event names into production code.
- Confirm the shell tool(s) exposed on Windows and the full command available
  before execution. Do not assume Copilot's PowerShell tools or argument schema.
- Confirm OpenCode's large-output truncation/offload behavior and whether its
  metadata supports truthful invocation-level offload counts.

If a required behavior is missing, document the gap before expanding scope.
Do not fall back to custom transport, silently switch backends, or weaken
enforcement. The existing Copilot option remains available independently.

## Session Identity

Preserve the launcher's UUID as the harness session key. OpenCode assigns its
own session ID; creation is not a drop-in equivalent of Copilot's caller-supplied
session ID API. Leave Copilot session handling intact; the following mapping is
specific to OpenCode.

- On a new phase, create an OpenCode session and atomically record its ID,
  backend identity, canonical worktree directory, harness UUID, resolved model
  configuration, and available campaign/phase identity in an ignored,
  worktree-local OpenCode runtime mapping.
- Persist this mapping before sending a prompt. Reject an unexpected existing
  mapping on a fresh invocation rather than overwriting or selecting by title.
- On `--resume`, require that mapping, retrieve the exact OpenCode session, and
  validate its backend, directory, model configuration, and invocation identity.
  Missing, invalid, or mismatched mappings are explicit failures; never use the
  latest session or a Copilot session as a fallback.
- Do not copy or reconstruct conversation messages. Resume by prompting the
  existing OpenCode session after the new server has started.
- Use the harness UUID in the existing accounting `session_id` field; add the
  OpenCode ID separately for diagnostics.
- Keep mappings out of scientific artifacts, injected context, and Git commits.
  Check reset interaction and stale mappings without deleting unrelated OpenCode
  sessions or global credentials.

## Console Translation

Keep rendering independent of SDK event classes. The reducer owns identity,
state transitions, deduplication, and accounting; the console owns text layout.

| Existing console behavior | OpenCode translation and constraints |
| --- | --- |
| Stream prose behind its gutter | Route assistant text deltas by message/part ID; distinguish snapshots from deltas and never print the final snapshot twice |
| Hide reasoning | Ignore reasoning content for presentation while preserving its separate usage metadata |
| Turn banners and summaries | Use model-step start/finish boundaries; verify their order relative to tool execution and document that a step is not necessarily a Copilot turn |
| Tool start details | Observe the first relevant tool-state transition by call ID; use actual OpenCode tool names and argument keys |
| Tool failures and denials | Print each terminal failure once; suppress a duplicate tool error for an already reported automatic denial |
| File notices | Use applicable tool metadata/file events with worktree filtering; retain before/after Git status observations for shell-written files |
| Phase label and elapsed time | Keep experiment/phase attribution, monotonic timing, ANSI/TTY behavior, and plain redirected output |
| Usage summaries | Apply the accounting contract below before printing the final step/invocation summary |
| Session completion | Handle idle for the selected active session only; errors remain errors even when followed by idle |

The current Git-status comparison detects status changes, not every content
change to a file already modified before invocation. Preserve that limited
meaning; do not describe it as a complete edit audit or add an unrelated audit
subsystem in this addition.

Subscribe before submitting the prompt and distinguish initial idle from
completion of this invocation. Filter parent/child and unrelated session events.
Handle repeated updates idempotently. On stream loss, use SDK state retrieval to
reconcile completion, pending requests, and final usage; never blindly resend a
prompt or count replayed history as new work. Exact replay of text lost during a
disconnect is not guaranteed by the presence of an SSE client alone.

## Unattended Guardrails

Permissions are internal runtime plumbing, not a new user workflow.

- Port the existing prohibited-execution, mutating-Git, repository-wide pytest,
  and dependency-management rules with their explanatory denial messages.
- Configure relevant shell operations to wait for the adapter's automatic
  decision. Approve permitted operations once and reject prohibited operations;
  do not use a remembered broad approval that bypasses later command checks.
- Configure other allowed capabilities to run without human interaction and
  disable unwanted tools, interactive questions, delegation, and external tools
  that would escape the intended Researcher profile.
- Verify native permission metadata and rejection feedback support the current
  policy. If they cannot enforce it, stop at the compatibility gate and propose
  a narrowly scoped pre-tool hook; do not silently set every tool to allow.
- Preserve the current policy's guardrail nature. It is not an OS sandbox and
  does not prevent arbitrary actions through inline code.
- Carry over harness instructions and explicitly control ambient agents, skills,
  MCP tools, plugins, automatic formatters, and extra model calls. The same model
  in a different agent runtime will not have identical scientific behavior.

## Accounting

Append one row per invocation to the existing campaign usage JSONL location in
the current worktree. Never write conversation text, commands, credentials, or
tool arguments into that record.

- Preserve experiment, phase, attempt, duration, exit code, and tool counters.
- Add runtime/provider identity, runtime session ID, and a usage-schema version.
- Count completed usage once, using either step records or assistant aggregates,
  never both. On resume, exclude previously recorded history; reconcile partial
  failures without treating missing usage as zero.
- Normalize token fields to the report's documented meaning. Verify whether
  OpenCode input excludes cache reads/writes before producing the legacy
  inclusive `input_tokens` value. Preserve raw components where normalization
  would otherwise lose information, including reasoning and cache writes.
- Leave Copilot `aiu` unavailable for OpenCode rows. Record any OpenCode cost
  with its unit and source as a runtime estimate, not as Go subscription billing.
  A zero estimate must not be advertised as proof of free usage.
- Preserve legacy rows unchanged. Update report aggregation and wording so AIU
  and monetary estimates remain separate and incomplete coverage is visible.
- Keep new Copilot rows and their existing AIU reporting supported, not merely
  historical rows. Recognize the current Copilot row format without requiring a
  rewrite of that adapter. Attribute mixed-backend reports explicitly.
- Report offload counts/bytes only when they can be measured; otherwise mark
  them unavailable rather than retaining Copilot-specific directory assumptions.
- Accounting failure must not invalidate a scientific deliverable or replace
  the actual runtime exit code.

## Implementation Sequence

1. **Establish the SDK boundary.** Add minimal Node/TypeScript dependency setup
   and a standalone adapter skeleton. Complete the compatibility gate, including
   a harmless prompt followed by continuation in a disposable directory.
2. **Implement lifecycle and identity.** Add CLI argument parity, current-directory
   binding, session mapping, startup errors, timeouts, interruption, abort,
   stream-loss handling, and guaranteed cleanup. Preserve exit codes `0`, `2`,
   `3`, `4`, `5`, `6`, and `130` with their existing meanings.
3. **Implement presentation and guardrails.** Port console formatting and command
   policy through the typed reducer; verify event ordering, duplicate handling,
   automatic denials, and the restricted tool/configuration profile.
4. **Implement accounting compatibility.** Record OpenCode invocation deltas and
  update report readers/formatting for existing Copilot, new OpenCode, and mixed
  rows. Leave Copilot's accounting writer intact.
5. **Add launcher selection and protection.** Add the optional OpenCode command,
  backend-specific defaults/prerequisites, current-directory handling, and
  retry binding. Retain Copilot as the default. Register additional runtime
  source, configuration, and dependency files as human-owned while preserving
  existing protection, scientific phase logic, and the reset mutex.
6. **Document and verify both options.** Retain Copilot tests and add OpenCode
  coverage plus launcher-selection regression checks. Document choosing either
  backend, prerequisites, authentication, worktree use, supported versions,
  usage differences, and troubleshooting. Keep the Copilot SDK and `jello`;
  do not remove either adapter or upgrade scientific Python dependencies.

## Verification And Acceptance

Tests and live checks below are planned implementation work, not actions run
while writing this plan. Keep checks scoped; no training, generic evaluator,
final benchmark, repository-wide lint, or full campaign is needed for this addition.

- **Offline TypeScript checks:** argument parsing; captured working directory;
  mapping validation; text snapshot/delta deduplication; hidden reasoning; tool
  transitions; step/idle ordering; failures; automatic command decisions; usage
  deduplication; interruption and cleanup using a fake SDK client.
- **Console fixtures:** representative multi-tool success, denial, retry, error,
  timeout, and resumed invocation streams in both TTY and redirected modes.
- **Existing Python contract tests:** retain Copilot adapter unit tests and extend
  relevant tests under `tests/autoresearch`, including researcher-session,
  research-context, protocol, scenario-boundary, and campaign-report tests.
  Add OpenCode adapter unit cases in TypeScript rather than replacing Copilot
  tests or spawning Node from campaign-time Python tests.
- **Backend-selection checks:** omitted selection still invokes Copilot with its
  existing defaults; explicit selection invokes only that backend and checks
  only its prerequisites. Verify model/default separation, same-backend retries,
  rejection of cross-backend resume, and no silent fallback after a failure.
- **Integration location:** real Git worktrees, PowerShell entry points, and
  server-process lifecycle tests belong under `tests/e2e`, outside campaign-time
  suite selection. Keep any real provider checks separately opt-in.
- **Worktree checks:** invoke from two disposable directories/worktrees, including
  a path with spaces/non-ASCII characters. Verify the intended directory, local
  files, accounting, and session mappings; reject cross-worktree resume. Check
  that occupying the default server port does not attach to that server.
- **Opt-in live check:** with OpenCode Go authenticated, exercise a harmless text
  stream, temporary-file edit, permitted shell command, prohibited command,
  process restart and resume, timeout, and Ctrl+C. Do not involve campaign
  deliverables or trained policies. Confirm blocked commands never execute and
  no human approval prompt occurs.
- **Failure checks:** unavailable CLI/model/authentication; unsupported reasoning;
  server startup/stream failure; missing resume session; late idle/error events;
  unavailable usage; accounting write failure; no orphaned server/tool process.
- **Regression checks:** report historical and new Copilot rows, OpenCode rows,
  and mixed-backend usage honestly; protect both runtimes; retain
  deliverable-based phase completion and existing reset semantics. No
  console-output parsing is added to PowerShell.

The addition is complete when these checks pass, both backends remain selectable,
existing commands still use Copilot, and OpenCode operates in the invoking
worktree with no interactive approval workflow. Document differences in native
tool names, step boundaries, usage semantics, and agent-runtime behavior. Do not
promise byte-for-byte Copilot event timing or identical model actions.

## SDK Evidence

Inspection baseline: OpenCode `v1.18.23`, the installed
`@opencode-ai/sdk@1.18.23` package, and the current repository source.

- [Official SDK documentation](https://opencode.ai/docs/sdk/)
- [Official server documentation](https://opencode.ai/docs/server/)
- [Pinned SDK server lifecycle](https://github.com/anomalyco/opencode/blob/v1.18.23/packages/sdk/js/src/server.ts)
- [Pinned root client directory handling](https://github.com/anomalyco/opencode/blob/v1.18.23/packages/sdk/js/src/client.ts)
- [Pinned root generated contracts](https://github.com/anomalyco/opencode/blob/v1.18.23/packages/sdk/js/src/gen/types.gen.ts)
- [Pinned `/v2` client, evaluated and not used](https://github.com/anomalyco/opencode/blob/v1.18.23/packages/sdk/js/src/v2/client.ts)

The pinned server helper inherits the launching process cwd and returns a server
URL plus a close function. The root client accepts a `directory` option and
handles request encoding itself.

### Compatibility gate outcome

Resolved by reading the installed package rather than assuming:

- **The `/v2` surface is the wrong one.** In `1.18.23` it is a
  workspace/control-plane API (`Workspace`, `ControlPlane`, `Adapter`, `/api/`
  routes). The root export is the documented `/session`, `/event` and permission
  surface the design assumed, so the runtime uses the root client.
- **The published package ships compiled JavaScript plus declarations.** This
  matters because Node refuses to strip types inside `node_modules`; only the
  adapter's own files are type-stripped.
- **Server startup and cwd** are confirmed from the pinned helper, which spawns
  `opencode serve --hostname= --port=` and resolves on its listening line.
- **Reasoning** is expressed as a provider model option
  (`provider.<id>.models.<model>.options.reasoningEffort`) injected through the
  server's inline config, not as part of a model name.
- **Model verification** uses `config.providers()`, because the root client's
  `Global` class exposes only `event`, not `health`.

Still requiring a live authenticated provider: event ordering, whether the
injected `reasoningEffort` is accepted, which permission field carries the shell
command, file-change event names, idle/busy timing, and resume, timeout and
interrupt behaviour end to end.