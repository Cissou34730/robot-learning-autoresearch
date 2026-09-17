# The OpenCode Researcher runtime

An optional second runtime for a bounded Researcher session.

`researcher_copilot.py` is unchanged and remains the default. The OpenCode
runtime lives beside it and is selected explicitly, so an existing command
behaves exactly as it did before. Neither adapter knows about the other: both
accept the same argument list and produce the same console, and the launcher
chooses between them.

## Choosing a runtime

```powershell
.\run_research.ps1                                   # Copilot (default)
.\run_research.ps1 -ResearcherBackend opencode       # OpenCode, its default model
.\run_research.ps1 -ResearcherBackend opencode -Model opencode-go/kimi-k3
```

Each runtime carries its own default model, because a model identifier is only
meaningful to the runtime that resolves it:

| Runtime | Default model |
| --- | --- |
| `copilot` | `gpt-5.6-luna` |
| `opencode` | `opencode-go/deepseek-v4.1-flash` |

An explicit `-Model` always wins. The defaults differ because each runtime
resolves models against its own provider; pass a model explicitly to hold the
model constant across runtimes.

Reasoning effort maps to the provider's `reasoningEffort` option for the selected
model. `max` is a Copilot-only effort and the launcher refuses it for OpenCode
rather than silently substituting `xhigh`.

## Prerequisites

- **Copilot**: unchanged from the existing setup.
- **OpenCode**: Node.js on `PATH` and the `opencode` CLI available. Node 23.6
  and later strip TypeScript types by default; earlier versions (including 22.x)
  are invoked with `--experimental-strip-types`.

Credentials are established before the runtime starts, never during a session.

## Authentication

Authentication is one environment variable:

```powershell
$env:OPENCODE_API_KEY = "<your OpenCode Go key>"
```

Verified against the installed CLI: both the `opencode-go` and `opencode`
providers read exactly `OPENCODE_API_KEY`. Take the key from
[opencode.ai/auth](https://opencode.ai/auth) after subscribing to Go.

The harness deliberately implements nothing else. OpenCode owns provider
authentication, so the runtime never prompts, never stores a credential, and
never reads or logs the key. It passes the environment through unchanged when it
starts the server, which is all the variable needs.

Set the variable in whatever launches the loop. Credentials do not belong in
`opencode.json`, which the runtime does not use for them.

## Layout

```text
researcher_opencode/
  package.json          pinned @opencode-ai/sdk, no build step
  package-lock.json
  tsconfig.json         no-emit; erasable-syntax-only checking
  src/main.ts           entry point and accounting
  src/adapter.ts        server lifecycle, session identity, event reduction
  src/policy.ts         the command policy, ported from the Copilot adapter
  src/console.ts        the human-visible console
  src/session-map.ts    harness session id to OpenCode session id
  src/accounting.ts     invocation usage rows
  src/args.ts           argument parity with the Copilot adapter
  src/git.ts            worktree status observation
  tests/                unit tests, run with the Node test runner
```

The runtime executes TypeScript directly. There is no compilation step and no
emitted JavaScript; `node_modules` holds only the pinned SDK and dev tooling.

## Worktree behaviour

The runtime uses the invoking process's current directory. The launcher sets that
to its own directory, so the OpenCode server's project is the worktree you
launched from, and linked worktrees work without configuration. Nothing is
derived from the adapter's source location.

Each invocation starts its own loopback server on a dynamically assigned port
(`port: 0`) and closes only that server. Two worktrees therefore never silently
share a server, and persisted OpenCode history is left intact.

## Session identity and resume

The launcher owns the phase identity and creates one UUID per phase, reusing it on
retry. OpenCode assigns its own session ids, so the mapping is recorded in
`reports/opencode-sessions.json` (ignored, never committed, never injected into
Researcher context). The mapping is written before the first prompt.

A resume requires that mapping and validates the recorded worktree, model and
reasoning effort. A missing, mismatched or cross-worktree mapping is an explicit
failure: the runtime never falls back to the most recent session, and it never
resumes a Copilot session.

## Console

The console is deliberately the same as the Copilot adapter's: the same gutter for
the model's own words, the same markers, turn banners with per-turn tool/file/time
and token deltas, file-change notices, and one `[session]` summary line.

Two differences are inherent to the runtime and are not compensated for:

- Usage reports an estimated monetary cost from OpenCode rather than Copilot AIU.
- Tool names and turn boundaries are OpenCode's, so a step is not necessarily a
  Copilot turn.

Reasoning text stays hidden, exactly as before: the console reports the work a
session did, not the text it thought through on the way there.

## Accounting

Rows are appended to the same campaign-scoped `reports/session_usage/<campaign-id>.jsonl`
file the Copilot adapter uses, and are distinguished by `runtime: "opencode"`.

`aiu` is always `null` for OpenCode rows, because AIU is a Copilot billing unit.
OpenCode's own cost estimate is recorded separately under `reported_cost_usd`, and
its token components (`cache_write_tokens`, `reasoning_tokens`) are recorded
alongside the shared fields. An estimate of zero is not evidence of free usage.

When the runtime reports no usage at all, the token and cost fields are `null`
rather than zero, so the report shows the gap instead of inventing a value.
Accounting failure never changes the exit code or invalidates a deliverable.

## Guardrails

The command policy is a faithful port of the Copilot adapter's, with the same
denial messages: no experiment execution, no mutating Git, no repository-wide
pytest, no dependency management. Reading or grepping a protected path remains
ordinary research.

Permissions are answered automatically, never by a human. A permitted operation is
approved once rather than remembered, so a broad approval cannot bypass a later
command check, and a refused command is rejected with its reason. Delegation and
the wider network are disabled, and the harness policy is carried over as session
instructions.

The server is configured with `permission.bash: "ask"`. OpenCode `1.18.23`
emits these requests as `permission.asked`; the adapter also accepts the legacy
`permission.updated` event. Without the explicit `ask` setting, shell commands
execute without reaching the harness policy.

## Verification status

Verified offline:

- Unit tests for the policy port, argument parsing, session mapping, worktree
  path handling, change filtering and accounting (`npm test`).
- A clean no-emit type check (`npm run typecheck`).
- The complete human-owned AutoResearch suite, unchanged and passing.
- The launcher parses cleanly and still routes every phase through the single
  researcher process boundary.

Verified against a locally started OpenCode server (`1.18.23`):

- The server starts and reports its listening URL after roughly five seconds.
  This is why the runtime sets a 30 s startup timeout: the SDK's own 5 s default
  is not sufficient on this machine.
- `config.providers()`, `app.agents()` and `session.create()` / `delete()` all
  work through the pinned SDK.
- `OPENCODE_API_KEY` is the environment variable for both `opencode-go` and
  `opencode`.
- `opencode-go/deepseek-v4.1-flash` is present in the provider's 28-model
  catalog, so the runtime's availability check passes with the default. The
  DeepSeek family is `deepseek-v4.1-flash`, `deepseek-v4-flash`,
  `deepseek-v4-pro`, `deepseek-v4-flash-vision-exp`; GLM is `glm-5.1`,
  `glm-5.2`, `glm-5.3`, `glm-5.3-flash`.
- `build` exists as a primary agent, so agent selection resolves.
- An authenticated `opencode-go/deepseek-v4.1-flash` prompt completed with exit
  code 0, streamed `LIVE_OK` once, emitted step usage and a cost estimate, and
  accepted the injected `reasoningEffort: high` option.
- A permitted `pwd` shell call was approved automatically and completed without
  a human prompt.
- A restarted adapter resumed the exact mapped session. Its attempted `git init`
  produced a `permission.asked` event, was rejected with the harness denial, and
  did not create `.git`.
- The timeout path aborted a waiting session and returned exit code 5 during the
  permission compatibility diagnosis.

Not yet verified live:

- Exact event ordering and whether text arrives as deltas, snapshots or both.
- The file-change event names and idle/busy transition timing.
- Ctrl+C interruption end to end.

These are the compatibility-gate items recorded in
[the implementation plan](opencode-runtime-plan.md). The core provider and
guardrail path is now live-verified; the remaining items are robustness checks.

## Troubleshooting

| Symptom | Meaning |
| --- | --- |
| `ProviderAuthError`, or the session fails immediately | `$env:OPENCODE_API_KEY` is missing, expired, or belongs to an account without Go. |
| `The OpenCode runtime needs Node.js on PATH` | Install Node.js, or use the default Copilot runtime. |
| `The OpenCode runtime entry point is missing` | The `researcher_opencode` directory is incomplete. |
| `no OpenCode session is recorded for harness session ...` | A resume was requested for a session this worktree never created. |
| `the recorded session belongs to a different worktree` | Launch the retry from the worktree that created the session. |
| `a model change starts a new session` / `a reasoning change ...` | The retry requested a different configuration than the recorded session. |
| `Model '...' is not available to OpenCode` | The provider id or model id is wrong; the message lists what the provider offers. |
| `OpenCode has no 'max' reasoning effort` | Use `low`, `medium`, `high` or `xhigh`. |
