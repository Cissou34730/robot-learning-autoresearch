# External campaign stop contract

Current launcher behavior, reviewed 19 October 2026. Older descriptions of a
separate TypeScript OpenCode runtime and dedicated first/second Ctrl-C exit
codes do not describe the current launcher.

An external controller must combine the repository's cooperative stop request
with a Windows Job Object. The request gives the active operation time to save
state and close its remote session; the Job Object is the independent guarantee
that no descendant survives a failed or hung graceful stop.

## Launch

For every launcher invocation, Hermes must:

1. Create a new, private control directory and never reuse it for another run.
2. Choose an absolute request path inside it, conventionally `stop.request`.
   The parent directory must exist. The request file may not be a directory.
3. Create a Windows Job Object with
   `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, disallow breakaway, create the launcher
   suspended, assign it to the job, then resume it. Hermes must retain the job
   handle until the launcher has exited and all job processes are gone.
4. Launch PowerShell with the request path and the cooperative timeout:

   ```powershell
   $runId = [guid]::NewGuid().ToString()
   $controlDirectory = Join-Path $env:TEMP "robot-learning\$runId"
   New-Item -ItemType Directory -Path $controlDirectory | Out-Null
   $stopRequest = Join-Path $controlDirectory "stop.request"

   # Hermes performs the suspended creation, Job Object assignment and resume.
   # Run from robot-learning-harness, not the campaign folder.
   pwsh -NoProfile -File .\run_research.ps1 `
       -CampaignRoot C:\Users\cyril.beurier\code\robot-learning-campaigns\campaign-1 `
       -StopRequestPath $stopRequest `
       -StopTimeoutSeconds 180
   ```

Use an unpackaged PowerShell executable for contained launches. The TUI skips
Microsoft Store `WindowsApps` execution aliases: a native child launched through
the installed package was observed outside the owning job, including when
started by its full executable path. The TUI requires unpackaged PowerShell 7;
Windows PowerShell 5.1 lacks .NET APIs used by the existing launcher. If the
supported runtime is unavailable, command preflight fails before initialization,
reset or launch rather than running without containment. This does not change
which shell an operator uses for direct, unsupervised script invocations.

The request path is inherited only by the supervised Runner or PI-adapter
process as `ROBOT_RESEARCH_STOP_REQUEST`. It is not a repository or campaign
state file.
The harness supplies the Python project and scripts; the selected campaign
folder is the child's working directory. The mutex is per campaign, so two
launchers cannot own the same campaign concurrently. The launcher restores
its caller's folder on exit.

## Request

Raise the level-triggered request by atomically creating the file. `CreateNew`
is idempotence-safe because a second request fails instead of replacing
anything:

```powershell
$stream = [System.IO.File]::Open(
    $stopRequest,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::Read
)
$stream.Dispose()
```

Use the explicit stop-request file for supervised cooperative stopping. Manual
Ctrl-C uses PowerShell and child-process interrupt behavior; the current
launcher has no separate first/second console-interrupt handler or dedicated
exit-125 escalation contract. Do not infer that recovery markers were saved
merely because an operator pressed Ctrl-C. A forced stop cannot guarantee
Runner persistence or SDK cleanup.

An external controller does not need to send a console control signal. The
launcher polls child completion and both stop inputs every 100 ms. The active
child also polls the external request:

- `runner/run_experiment.py` raises `KeyboardInterrupt` on its main thread.
  Existing runner handling stops training or evaluation cooperatively, persists
  partial state, writes `RECOVERY_PENDING` or `RESTART_PENDING` when applicable,
  and returns 130.
- `runner/copilot/copilot_adapter.py` calls `session.abort()`, then always disconnects.
- OpenCode Zen/Go use that same Copilot SDK adapter, not a separate
  `researcher_opencode` process.

After an interrupted PI session exits, the launcher checks the request before
deliverable validation or retry. It then leaves the campaign loop, shuts down
its owned persistent Copilot runtime, and releases the campaign mutex.

## Wait and fallback

Hermes must wait for the launcher process, not merely the active child:

- Exit `130`: the cooperative request was observed, the supervised child
  returned normally with exit 0 or 130, and launcher cleanup completed.
- Exit `124`: the active child did not return before `StopTimeoutSeconds`.
  The cooperative process helper attempts to kill its owned process tree.
  Hermes must still close the Job Object; recovery markers are not guaranteed.
- Exit `0`: the campaign completed normally before the request took effect.
- Any other exit: launcher or child failure. Hermes must close the Job Object
  before reporting the failure.

The timeout begins when the launcher first observes the request, not when
Hermes creates it. The 180-second default allows for the runner's 15-second
status wait, its 30-second cooperative child interrupt, its 10-second forced
child fallback, and recovery persistence. It is still a bound, not a guarantee:
a blocking OS or Git operation can consume it. Hermes should therefore wait at
least `StopTimeoutSeconds + 5` seconds after creating the request. If the
launcher has not exited by then, or exits with 124 or another failure, Hermes
closes its Job Object handle and waits until the job is empty.

The launcher's cooperative exit path runs its cleanup, but the external
controller must still confirm the Job Object is empty. A successful Runner
training interrupt follows its existing recovery-marker path. It does not
promise that a recoverable checkpoint exists: an early interruption can produce
`RESTART_PENDING`. Inspect durable pending/completed state before resuming;
never blindly resubmit completed work.

Closing the Job Object guarantees process-tree termination, but it is an
unclean fallback. It cannot guarantee runner recovery markers, SDK
abort/disconnect, persistent-runtime cleanup, or any other `finally` block. Hermes
must not start another invocation for the campaign until the old job is empty,
because a killed launcher releases its named mutex even if an uncontained
descendant would otherwise still be running.

## Operator console implementation

The console TUI (`uv run python -m tui`, `tui/console.py`, issue #68) is an
external controller that implements this contract directly:

- every owned launcher runs through `tui/process.py`: suspended creation in a
  new process group, assignment to a `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` job,
  per-run private control directory under `%TEMP%\robot-learning\tui` with
  captured launcher stdout/stderr and the `stop.request` file;
- initializer and reset helpers use the same contained boundary. An unfinished
  helper may finish during console shutdown, but no later reset or launch starts;
  a helper that misses the shutdown bound is terminated and reported as interrupted;
- `run`, `reset`, `start` and `stop` commands delegate to the existing
  `run_research.ps1` / `reset_research.ps1` entry points with the launcher's
  own options; launch batches carry `-StopRequestPath` and stop with a
  cooperative deadline of 180 seconds (configurable per command through
  `-StopTimeoutSeconds`);
- exit classification follows the wait rules above: 130 is a cooperative
  stop, 0 is a normal return that requires inspecting durable state, 124 and
  any other exit are failures; a missed cooperative deadline escalates to
  `TerminateJobObject` and is reported as a failed campaign;
- ordinary `stop` reports stopping immediately and shows elapsed/remaining wait.
  The deadline belongs to the invocation: changing shared settings does not
  change an existing campaign's deadline. A successful cooperative stop does
  not call forced termination;
- closing the console or pressing `Ctrl+Q` asks every owned launcher to stop
  concurrently, waits up to its stop timeout plus five seconds from request
  creation, escalates only when needed to the forced
  fallback and only then exits, so an owned campaign cannot outlive the
  console (the kill-on-close job handle is the backstop);
- `Ctrl+C` copies the current text selection or does nothing; it never
  reaches the campaign processes because the launchers are in their own
  process group with redirected input;
- one named-mutex instance lock (`Local\RobotLearningTui-<hash>`) refuses a
  second TUI (including read-only reports) against the same canonical harness
  directory. The owner releases job, process, thread and diagnostic handles
  after verifying cleanup, before the campaign folder is available for reuse.
