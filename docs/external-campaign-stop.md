# External campaign stop contract

Current launcher behavior, reviewed 27 October 2026. The launcher is the
Python module `runner.launcher`; older descriptions of a PowerShell launcher,
a per-run `-StopRequestPath` or console-interrupt exit codes do not describe it.

Every campaign has one cooperative stop request: the file `stop-request` in
the campaign's Git administration directory (`<campaign>\.git\stop-request`,
or the directory a `.git` file points to). It is outside the worktree, so it is
never published or seen by campaign agents. Whoever started the launcher, any
maintainer tool can stop it by creating that file. `runner.paths.stop_request_path`
returns the path.

A controller that owns the launcher process should also hold it in a Windows
Job Object. The request gives the active operation time to save state and close
its remote session; the Job Object is the independent guarantee that no
descendant survives a failed or hung graceful stop.

## Launch

Run the launcher from the harness with `uv`:

```powershell
uv run --project C:\Users\cyril.beurier\code\robot-learning-harness --group researcher `
    python -m runner.launcher `
    --campaign-root C:\Users\cyril.beurier\code\robot-learning-campaigns\campaign-1 `
    --stop-timeout-seconds 180
```

At start the launcher deletes a stop request older than its own start time, so
a request left by an earlier run does not stop it. A request created or
refreshed after the start is honored. It passes the request path to each Runner
or PI-adapter child as `ROBOT_RESEARCH_STOP_REQUEST` and deletes the request
when it exits.

The launcher writes no console output. Its progress is the campaign's typed
event feed; a failure that ends the launch is written to standard error and to
`<campaign>\reports\launcher\<UTC time>-<pid>.log`, which also captures the
children's output. The per-campaign mutex refuses a second launcher or a reset
for the same campaign.

## Request

Create (or refresh) the request file. Writing an empty file is enough:

```powershell
$request = uv run python -c "from pathlib import Path; from runner.paths import stop_request_path; print(stop_request_path(Path(r'C:\path\to\campaign-1')))"
Set-Content -LiteralPath $request -Value '' -NoNewline
```

The request is level-triggered. The launcher polls it with child completion
every 100 ms. The active child also polls it:

- `runner/run_experiment.py` raises `KeyboardInterrupt` on its main thread.
  Existing runner handling stops training or evaluation cooperatively, persists
  partial state, writes `RECOVERY_PENDING` or `RESTART_PENDING` when applicable,
  and returns 130.
- `runner/copilot/copilot_adapter.py` calls `session.abort()`, then always
  disconnects. OpenCode Zen/Go use the same adapter.

After an interrupted child exits, the launcher checks the request before
deliverable validation or retry. It then leaves the campaign loop, shuts down
its owned persistent Copilot runtime and releases the campaign mutex. A request
seen while the Copilot runtime is still starting ends that bootstrap without
sending a session.

## Wait and fallback

Wait for the launcher process, not merely the active child:

- Exit `130`: the cooperative request was observed, the supervised child
  returned normally with exit 0 or 130, and launcher cleanup completed.
- Exit `124`: the active child did not return before `--stop-timeout-seconds`.
  The launcher killed that child's process tree; recovery markers are not
  guaranteed.
- Exit `0`: the campaign completed or paused normally before the request took
  effect.
- Any other exit: launcher or child failure.

The timeout begins when the launcher first observes the request. The
180-second default allows for the runner's 15-second status wait, its 30-second
cooperative child interrupt, its 10-second forced child fallback, and recovery
persistence. It is a bound, not a guarantee: a blocking OS or Git operation can
consume it. A controller should therefore wait at least the timeout plus five
seconds after creating the request. If the launcher has not exited by then, or
exits with 124 or another failure, an owning controller closes its Job Object
and waits until the job is empty.

A successful Runner training interrupt follows its existing recovery-marker
path. It does not promise that a recoverable checkpoint exists: an early
interruption can produce `RESTART_PENDING`. Inspect durable pending/completed
state before resuming; never blindly resubmit completed work.

Closing the Job Object guarantees process-tree termination, but it is an
unclean fallback. It cannot guarantee runner recovery markers, SDK
abort/disconnect, persistent-runtime cleanup, or any other `finally` block. Do
not start another invocation for the campaign until the old job is empty,
because a killed launcher releases its named mutex even if an uncontained
descendant would otherwise still be running.

## Operator console implementation

The console TUI (`uv run python -m tui`, `tui/console.py`, issue #68)
implements this contract:

- every owned launcher runs through `tui/process.py`: `uv` on PATH starts
  `python -m runner.launcher`, created suspended in a new process group with a
  private hidden console (`CREATE_NEW_CONSOLE`, `SW_HIDE`), assigned to a
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` job, then resumed. The Windows
  desktop-app child policy
  (`PROCESS_CREATION_DESKTOP_APP_BREAKAWAY_DISABLE_PROCESS_TREE`) keeps native
  descendants of packaged executables in the job; attribute failure aborts
  before the child runs. Standard output and error go to a per-run control
  directory under `%TEMP%\robot-learning\tui`;
- initializer and reset helpers (`python -m tools.initialize_campaign`,
  `python -m runner.launcher.reset`) use the same contained boundary. An
  unfinished helper may finish during console shutdown, but no later reset or
  launch starts; a helper that misses the shutdown bound is terminated and
  reported as interrupted;
- `stop` writes the campaign's stop request. For a campaign the console did
  not start but whose mutex is held (for example one launched by
  `tools.run_parallel`), `stop` writes the same request and reports that the
  campaign is not owned; there is no process handle to wait on or force;
- exit classification follows the wait rules above: 130 is a cooperative
  stop, 0 is a normal return that requires inspecting durable state, 124 and
  any other exit are failures; a missed cooperative deadline escalates to
  `TerminateJobObject` and is reported as a failed campaign;
- ordinary `stop` reports stopping immediately and shows elapsed/remaining
  wait. The deadline belongs to the invocation: changing shared settings does
  not change an existing campaign's deadline. A successful cooperative stop
  does not call forced termination;
- closing the console or pressing `Ctrl+Q` asks every owned launcher to stop
  concurrently, waits up to its stop timeout plus five seconds from request
  creation, escalates only when needed to the forced fallback and only then
  exits, so an owned campaign cannot outlive the console (the kill-on-close
  job handle is the backstop);
- `Ctrl+C` copies the current text selection or does nothing; it never
  reaches the campaign processes because the launchers are in their own
  process group with redirected input;
- stop requests are not queued behind an initializer/reset batch. In-flight
  helpers have a separate 15-second finish grace on console shutdown,
  followed by owned-job cleanup if necessary;
- a reset records `reset-incomplete.json` in the campaign's Git directory at
  its first mutation and removes it on success; the console refuses `start`
  while the record exists;
- one named-mutex instance lock (`Local\RobotLearningTui-<hash>`) refuses a
  second TUI (including read-only reports) against the same canonical harness
  directory.

## Parallel monitor

`tools.run_parallel` starts each launcher detached without a console window
(`CREATE_NO_WINDOW`) and a detached monitor. The monitor creates a campaign's
stop request when its active-time or AIU cap is reached, waits for every
launcher to release its campaign mutex, then writes one report per campaign.
These launchers are not in a Job Object; stop them through their request.
