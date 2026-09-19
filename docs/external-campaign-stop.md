# External campaign stop contract

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
   pwsh -NoProfile -File .\run_research.ps1 `
       -StopRequestPath $stopRequest `
       -StopTimeoutSeconds 180
   ```

The request path is inherited only by the supervised runner or researcher
process as `ROBOT_RESEARCH_STOP_REQUEST`. It is not a repository or campaign
state file.

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

Manual Ctrl-C in the launcher's console is supported:

1. The first Ctrl-C raises the launcher stop state and starts the same
   cooperative deadline as an external request. The inherited console event
   still reaches the active child, while the launcher keeps supervising it
   instead of aborting its PowerShell pipeline. If no child is being
   supervised, the launcher stops the campaign at its next control point
   instead of starting or continuing campaign work. The operator sees
   `Console interrupt requested; waiting up to ... seconds for cooperative
   shutdown.`, followed by the child's normal interruption and recovery output.
   The launcher completes its `finally` cleanup and exits 130, or exits 124 if
   the cooperative deadline expires.
2. A second or later Ctrl-C is not handled by the native launcher handler, so
   PowerShell cancels the pipeline immediately. The launcher stops waiting for
   the active child, prints `Additional console interrupt requested; escalating
   immediately.`, runs its `finally` cleanup, and exits 125. Exit 125 is the
   stable operator-escalation code, distinct from cooperative interruption
   (130) and cooperative-deadline expiry (124).

Immediate escalation does not wait for runner persistence. `RECOVERY_PENDING`
or `RESTART_PENDING` is therefore not guaranteed, nor are SDK abort/disconnect
or child-process cleanup. The launcher's own OpenCode server stop and mutex
release still run. The Windows Job Object is the only process-tree containment
guarantee on this path, so its owner must close the job after exit 125.

An external controller does not need to send a console control signal. The
launcher polls child completion and both stop inputs every 100 ms. The active
child also polls the external request:

- `research/run_experiment.py` raises `KeyboardInterrupt` on its main thread.
  Existing runner handling stops training or evaluation cooperatively, persists
  partial state, writes `RECOVERY_PENDING` or `RESTART_PENDING` when applicable,
  and returns 130.
- `researcher_copilot.py` calls `session.abort()`, then always disconnects.
- `researcher_opencode/src/adapter.ts` resolves its existing interrupt outcome,
  calls `session.abort()`, and drains its runtime handles.

After an interrupted researcher exits, the launcher checks the request before
deliverable validation or retry. It then leaves the campaign loop, stops the
OpenCode campaign server in `finally`, and releases the worktree mutex.

## Wait and fallback

Hermes must wait for the launcher process, not merely the active child:

- Exit `130`: the cooperative request was observed, the supervised child
  returned normally with exit 0 or 130, and launcher cleanup completed.
- Exit `124`: the active child did not return before `StopTimeoutSeconds`.
  The launcher did not kill it. Hermes must immediately close the Job Object.
- Exit `125`: the operator pressed Ctrl-C again, cancelling the cooperative
  wait. Launcher cleanup completed, but runner recovery markers are not
  guaranteed. Hermes must immediately close the Job Object.
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

Exit 130 guarantees that the launcher's `finally` block ran and no supervised
runner or researcher remains. For an interrupted training operation it also
means the runner reached its existing recovery-marker path. It does not promise
that a recoverable checkpoint exists: an early interruption correctly produces
`RESTART_PENDING`.

Closing the Job Object guarantees process-tree termination, but it is an
unclean fallback. It cannot guarantee runner recovery markers, SDK
abort/disconnect, OpenCode server cleanup, or any other `finally` block. Hermes
must not start another campaign in the worktree until the old job is empty,
because a killed launcher releases its named mutex even if an uncontained
descendant would otherwise still be running.
