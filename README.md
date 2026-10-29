# Robot AutoResearch

Read the [Robot-learning research process](docs/research-overview/robot-learning-overview-20261002.html).

## Documentation map

Current operating guidance, reviewed 27 October 2026:

- [HTML overview](docs/research-overview/robot-learning-overview-20261002.html):
  architecture, lifecycle, status and links to historical evidence. Its filename
  is retained so existing links continue to work.
- [Repository split](docs/harness-campaign-split.md): physical ownership,
  implementation stages, validation and migration corrections.
- [Reset guide](docs/reset-research.md), [external stop contract](docs/external-campaign-stop.md)
  and [saved-policy runtime](docs/policy-runtime.md): operator procedures.
- [Terminal report](docs/tui-report.md): the multi-campaign operator console
  (`python -m tui`) and the read-only single-screen campaign report.
- [Maintainer instructions](AGENTS.md) and [runtime mechanics](docs/runtime-mechanics.md):
  maintainer conventions and agent-runtime internals, reserved from campaign agents.
- [Authority](contracts/authority.md), [scientific program](contracts/program.md)
  and [instruments](contracts/instruments.md): PI-facing role boundaries,
  lifecycle and operation contracts.
- [Change tracker](docs/harness-experiment-log.md): current state, campaign results,
  issue register and change ledger.
- `uv run python -m tools.run_parallel --count N`: the standard way to run 1 to 5
  campaigns at once, with maintainer-only time and AIU caps (see [Run campaigns](#run-campaigns-standard)).

Dated RCAs, plans and reviews are in [docs/archive](docs/archive/), program
proposals in [docs/proposals](docs/proposals/), campaign HTML reports in
[docs/research-overview](docs/research-overview/). They, and the
[old integration notes](docs/archive/INTEGRATION_NOTES.md), describe the revisions and
campaigns named in them, not the current repository layout or current campaign.
[Protocol decisions](docs/protocol-decisions.md) retain superseded decisions
as history; the latest dated entry identifies the current storage design.

## Harness and campaign repositories

The two repositories have different contents:

| Repository | Contents | Publication |
|---|---|---|
| `robot-learning-harness` | Runner, contracts, benchmark, tools, tests, documentation and launch scripts | Standalone repository; `harness` is the GitHub default branch |
| `robot-learning-campaigns\campaign-<n>` | PI-owned `robot_learning/`, campaign state, models, logs and measurements | One independent local Git repository per campaign slot (1 to 5) under one plain folder; campaign commits never push |

Run commands from the harness folder. Campaign repositories live under the
sibling folder `robot-learning-campaigns`, one per slot: `campaign-1` to
`campaign-5`. The launcher and reset default to `campaign-1`; use
`--campaign-root <path>` to select another initialized campaign repository. No
harness merge or copy is needed when the harness evolves: subsequent operations
use the current harness with the selected campaign's scientific code.
The launcher and reset are Python processes (`runner.launcher` and
`runner.launcher.reset`); they change folder only inside their own process, so
the calling terminal's folder never changes.
Errors that end a launch go to standard error and to the launcher log
`<campaign>\reports\launcher\<UTC time>-<pid>.log`. The
[terminal report](docs/tui-report.md) shows the progress of a campaign.
The harness has its own Git storage and no longer depends on the old reference
repository or its worktrees. Existing historical branches remain on GitHub.

### Run campaigns (standard)

Run 1 to 5 campaigns at once from the harness folder:

```powershell
uv run python -m tools.run_parallel --count 3
```

The tool uses `robot-learning-campaigns\campaign-1` to `campaign-<count>`,
initializes missing slots from an existing one (adding a global Git
`safe.directory` entry for the new folder), resets each to the recipe
(`--recipe-ref`, default `baseline-distinct-episodes-v3-robot`; `--no-reset`
skips this), launches each campaign as a hidden background process without a
console window and starts a hidden monitor. The monitor stops a campaign
cooperatively, through its stop request, at `--max-hours` of active time
(default 6) or `--max-aiu` (default 120); campaign agents never see these caps.
Launcher logs, the monitor log and one report per campaign go to
`%TEMP%\robot-learning\parallel-<UTC time>`. Watch the campaigns with
`.\campaign_tui.ps1`; it can also stop them.

### Operator console

The console starts the launcher, the reset and the initializer with `uv` on
PATH, each in a hidden private console inside a Windows Job, so native
descendants remain contained. A launcher survives the console (see below); a
reset or initializer does not. No PowerShell host is needed for campaign
work. Missing `uv` fails preflight before initialization/reset; opening the
interface still starts nothing.

`.\campaign_tui.ps1` (or `uv run python -m tui`) opens the first visible campaign report
with one information line below it. Tabs hide automatically after two hours
with no running launcher; log silence never hides a running campaign.
`/show 3` and `/hide 3` override tab visibility for this console session without
changing execution. `/start` and `/run` show their targets again. Hidden campaigns
still take `stop all`, `kill all` and the usual shutdown actions.
The idle countdown survives console restart; show/hide overrides do not.
If a previous exit time is unknown, the countdown starts when the console first
confirms the campaign is stopped. Press **`/`** to open the
command list: type to filter, Up/Down to choose, Tab to complete, Enter to run,
Esc to close. There is no separate Commands tab. Campaigns only run when a
command is submitted (`run 1-3`, `reset campaign-1 campaign-2`,
`start campaign-2`, `stop all`); each batch sends the exact same shared
launcher options to every selected campaign, defaulting to the launcher's
own defaults for any field left empty. `run` initializes a missing standard
folder, resets it to the v3 recipe and launches it, skipping the rest of the
batch if a step fails. `Ctrl+C` copies text selection only. `Alt+Q` (or `/quit`)
leaves the console and keeps every campaign running; `Ctrl+Q` (or `/quit stop`)
stops every console-owned campaign first and, for one that does not stop in 30 s,
asks whether to kill it or leave it running. `/kill 1` ends a launcher
immediately. Only one console may run against a harness directory, and the
launcher's dirty-worktree refusal applies. See
[console details](docs/tui-report.md#operator-console-multi-campaign-control)
and the [stop contract](docs/external-campaign-stop.md).

Press **F2** (or `/settings`) for labelled shared launch/reset settings;
**F1** opens help and **F3** shows recent commands and their step outcomes.
Type `/start` and press Enter to resume the active campaign
without resetting it. Untargeted commands follow the active campaign tab;
an explicit range or folder list selects a batch. Numbers are identities:
`start 2` starts only campaign-2, `start 1-2` selects campaigns 1 and 2, and
`start 2-3` selects campaigns 2 and 3. This also applies to run/reset/stop;
`stop all` still stops every owned campaign. A campaign the console did not
start (for example one launched by `tools.run_parallel`) can be stopped too:
the console writes the campaign's stop request and the launcher ends
cooperatively.
**Ctrl+F** (or `/search`) searches the log.
**Tab / Shift+Tab** switch campaign tabs; inside the command list, Tab completes,
and inside dialogs it navigates fields normally. F6/Shift+F6 move focus between
report controls.
Ctrl+Tab remains an optional alias when the terminal passes it through.
Stop commands remain available while another batch is preparing/resetting.
A reset that stops after it starts changing the campaign leaves a
Git-administration record; TUI `start` is blocked until a reset succeeds.

Reset controls retain Fresh/Baseline, Clean and recipe/baseline references.
The default is Fresh + Clean + `baseline-distinct-episodes-v3-robot` + Force;
measurements and logs may be deleted without a reset backup. `start` resumes
without resetting and leaves completed scientific outcomes unchanged. `stop`
is cooperative; the invocation's 180-second default timeout plus five seconds
is a maximum wait, not a delay before every stop. `diagnostics campaign-1`
opens raw launcher logs. `--read-only --campaign-root <path>` monitors without
owning or stopping external campaigns; the same-directory instance lock applies.

### Initialize a campaign repository once

`tools.run_parallel` creates missing slots itself. To create one by hand,
choose a destination that does not exist:

```powershell
uv run python -m tools.initialize_campaign `
  --campaign-root C:\Users\cyril.beurier\code\robot-learning-campaigns\campaign-4 `
  --source-repository C:\Users\cyril.beurier\code\robot-learning-campaigns\campaign-1 `
  --recipe-ref baseline-distinct-episodes-v3-robot
```

The source repository must contain the selected recipe reference. Initialization
reads that repository without changing it, imports the scientific files into a
new local repository, records the current task fingerprints and performs a
Fresh recipe reset. It does not start training or an agent session. The new
repository has no remotes. Keep its local baseline tag for future resets.

### Reset to v3 or launch one campaign

The campaign repository's `baseline-distinct-episodes-v3-robot` tag is the v3
recipe importing the renamed robot contract (`contracts/robots/robot.py`); the
older `baseline-distinct-episodes-v3` tag no longer matches the task contract.

Stop any active campaign before resetting. These commands act on `campaign-1`
unless `--campaign-root` selects another slot:

```powershell
uv run python -m runner.launcher.reset --mode fresh --recipe-ref baseline-distinct-episodes-v3-robot --force
uv run --group researcher python -m runner.launcher --provider github-copilot
```

`.\run_research.ps1` is a shortcut for the second command and passes its
arguments through. A reset followed by a launch:

```powershell
uv run python -m runner.launcher.reset --mode fresh --clean --recipe-ref baseline-distinct-episodes-v3-robot --force ; .\run_research.ps1
```

Use `--clean` only when you intend to discard eligible uncommitted campaign
changes. It is not needed merely to resume a stopped campaign.
The semicolon is not a success-only condition: if reset fails, inspect the error
before launching.

The launcher refuses to start, including a resume, while the harness
worktree has uncommitted or untracked changes. Commit or discard them first.

Baseline v3 is a scientific recipe, not a trained model. Its reset initializes
empty campaign history and leaves scientific-model preparation pending. The
harness stays unchanged. See [reset details](docs/reset-research.md).

Campaign Git tracks source and compact state. Large measurements, disposable
models and other ignored artifacts stay in the campaign folder but are not
backed up by Git. No reset backups are kept.
Runner training logs under `campaigns/training_logs/` also remain local and
ignored; they are Runner-owned output, not scientific source changes.

### Campaign limits

`--max-inquiries` (default 15) limits the inquiries opened in one unattended
run. It is a maintainer guardrail: neither the limit nor its value is shown to
the PI. After the final permitted inquiry closes and its session record is
saved, the launcher pauses before the next goal review. It records no campaign
conclusion and requests no official assessment. Launch again with a higher
`--max-inquiries` to continue the same campaign; the value can only increase.

`--timesteps` (default 120,000) sets the training allocation per run. During an
inquiry a run may extend up to `--max-timesteps` (default 360,000). The PI sees
both values in its session context and cannot change them.

### Known restart limitation

A launcher restart resumes the persisted backend conversation; it is not always
a fresh context. After `validation_fatal`, that conversation may refuse further
submissions even when the underlying file problem has been repaired and Runner
still records an active session. This mismatch was observed after the migrated
training-log failure and is not repaired by the directory-restoration changes.
See the [issue tracker](docs/harness-experiment-log.md#outstanding-issue-register).

Do not assume repeated restarts recover such a session, automatically replay
operations, or reset a campaign merely to clear the error. Recovery needs a
maintainer decision based on durable state. A reset deliberately starts a new
campaign; it does not resume the old one.

### Maintainer validation

Select the campaign's scientific code when running tests from the harness:

```powershell
$env:ROBOT_LEARNING_CAMPAIGN_ROOT = 'C:\Users\cyril.beurier\code\robot-learning-campaigns\campaign-1'
$env:PYTHONPATH = "$env:ROBOT_LEARNING_CAMPAIGN_ROOT;$PWD"
uv run pytest tests\autoresearch\test_campaign_paths.py -q
```

The Python environment and dependency lock belong to the harness. Campaign PI
agents cannot install dependencies or run maintainer tests.

The Copilot harness integration uses Python SDK 1.0.26. Install the locked
scientific stack and agent runtime with `uv sync --locked --group researcher`.
Native coding subagents, permissions and custom evidence tools remain in that
runtime. Inference can use GitHub Copilot, OpenCode Zen or OpenCode Go.

### Select inference at launch

`--provider` accepts `github-copilot`, `opencode` (Zen), or `opencode-go`.
`--model` accepts a catalogue model ID or a provider-qualified ID.
Conflicting provider/model prefixes fail explicitly.
Without `--provider`, the default is GitHub Copilot `gpt-6-luna`.
With an OpenCode provider and no `--model`, the default is
`opencode/deepseek-v4.1-flash-free`.

List choices without starting or changing campaign state:

```powershell
.\run_research.ps1 --provider opencode --list-models
.\run_research.ps1 --provider opencode-go --list-models
```

For an authorized campaign launch, select the provider and model:

```powershell
.\run_research.ps1 --provider opencode
.\run_research.ps1 --model opencode-go/kimi-k3
```

One `OPENCODE_API_KEY` authorizes both Zen and Go.
Configure it locally, never in repository files or chat.

The public OpenCode catalogue supplies model protocols, endpoints and limits.
The cache refreshes after 24 hours; without any saved catalogue the free
DeepSeek model remains available. Every model uses the protocol and endpoint
listed in the catalogue. SDK 1.0.26 supports
Chat Completions, Responses and Anthropic routes, not native Google transport.
Unsupported selections never substitute another model.

OpenCode serves the PI and the preliminary analyst. Their requests carry the
OpenCode client identity headers and a scoped `read` tool.
The native coder and reviewer always run on GitHub Copilot: the campaign model
on Copilot campaigns, `gpt-6-luna` with high reasoning on OpenCode campaigns.
OpenCode campaigns therefore also require a Copilot sign-in.
Copilot scientific-model preparation retains `max` reasoning.

OpenCode token usage and catalogue prices remain separate from Copilot AIU.
Unknown external charges remain unavailable, not zero.

See [contracts/authority.md](contracts/authority.md) for ownership and execution
boundaries,
[scientific instruments](contracts/instruments.md) for tool contracts, and
the [harness tracker](docs/harness-experiment-log.md) for implementation status.
Campaign launches, resets and scientific execution require explicit maintainer
authorization.
