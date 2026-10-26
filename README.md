# Robot AutoResearch

Read the [Robot-learning research process](docs/research-overview/robot-learning-overview-20261002.html).

## Documentation map

Current operating guidance, reviewed 19 October 2026:

- [HTML overview](docs/research-overview/robot-learning-overview-20261002.html):
  architecture, lifecycle, status and links to historical evidence. Its filename
  is retained so existing links continue to work.
- [Repository split](docs/harness-campaign-split.md): physical ownership,
  implementation stages, validation and migration corrections.
- [Reset guide](docs/reset-research.md), [external stop contract](docs/external-campaign-stop.md)
  and [saved-policy runtime](docs/policy-runtime.md): operator procedures.
- [Terminal report](docs/tui-report.md): the read-only single-screen campaign
  report (`tools\run-report.ps1`, `-Demo` for synthetic rendering).
- [Maintainer instructions](AGENTS.md) and [runtime mechanics](docs/runtime-mechanics.md):
  maintainer conventions and agent-runtime internals, reserved from campaign agents.
- [Authority](contracts/authority.md), [scientific program](contracts/program.md)
  and [instruments](contracts/instruments.md): PI-facing role boundaries,
  lifecycle and operation contracts.
- [Change tracker](docs/harness-experiment-log.md): issue status and maintenance history.

Dated RCAs, campaign HTML reports, implementation proposals and
[old integration notes](docs/archive/INTEGRATION_NOTES.md) describe the revisions and
campaigns named in them, not the current repository layout or current campaign.
[Protocol decisions](docs/protocol-decisions.md) retain superseded decisions
as history; the latest dated entry identifies the current storage design.

## Harness and campaign repositories

The two repositories have different contents:

| Repository | Contents | Publication |
|---|---|---|
| `robot-learning-harness` | Runner, contracts, benchmark, tools, tests, documentation and launch scripts | Standalone repository; `harness` is the GitHub default branch |
| `robot-learning-campaigns` | PI-owned `robot_learning/`, campaign state, models, logs and measurements | Independent local Git repository; campaign commits never push |

Run commands from the harness folder. The launch and reset scripts default to
the sibling `robot-learning-campaigns` folder. Use `-CampaignRoot <path>` to
select another initialized campaign repository. No harness merge or copy is
needed when the harness evolves: subsequent operations use the current harness
with the selected campaign's scientific code.
The launch and reset scripts work inside the campaign folder while running and
restore the calling terminal's original folder on exit, including on failure.
The harness has its own Git storage and no longer depends on the old reference
repository or its worktrees. Existing historical branches remain on GitHub.

### Initialize a campaign repository once

The existing local campaign repository is already initialized from baseline v3.
To create another one, choose a destination that does not exist:

```powershell
uv run python -m tools.initialize_campaign `
  --campaign-root C:\Users\cyril.beurier\code\another-campaign `
  --source-repository C:\Users\cyril.beurier\code\robot-learning `
  --recipe-ref baseline-distinct-episodes-v3
```

The source repository must contain the selected recipe reference. Initialization
reads that repository without changing it, imports the scientific files into a
new local repository, records the current task fingerprints and performs a
Fresh recipe reset. It does not start training or an agent session. The new
repository has no remotes. Keep its local baseline tag for future resets.

### Reset to v3 or launch

The campaign repository's `baseline-distinct-episodes-v3-robot` tag is the v3
recipe importing the renamed robot contract (`contracts/robots/robot.py`); the
older `baseline-distinct-episodes-v3` tag no longer matches the task contract.

Stop any active campaign before resetting:

```powershell
.\reset_research.ps1 -Mode Fresh -RecipeRef baseline-distinct-episodes-v3-robot -Force
.\run_research.ps1 -Provider github-copilot
```

The reset script also restores the folder before the next command, so this
sequence works from the harness folder:

```powershell
.\reset_research.ps1 -Mode Fresh -Clean -RecipeRef baseline-distinct-episodes-v3-robot -Force ; .\run_research.ps1
```

Use `-Clean` only when you intend to discard eligible uncommitted campaign
changes. It is not needed merely to resume a stopped campaign.
The semicolon is not a success-only condition: if reset fails, inspect the error
before launching.

`run_research.ps1` refuses to start, including a resume, while the harness
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

`-MaxInquiries` (default 15) limits the inquiries opened in one unattended
run. It is a maintainer guardrail: neither the limit nor its value is shown to
the PI. After the final permitted inquiry closes and its session record is
saved, the launcher pauses before the next goal review. It records no campaign
conclusion and requests no official assessment. Launch again with a higher
`-MaxInquiries` to continue the same campaign; the value can only increase.

`-Timesteps` (default 120,000) sets the training allocation per run. During an
inquiry a run may extend up to `-MaxTimesteps` (default 360,000). The PI sees
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
$env:ROBOT_LEARNING_CAMPAIGN_ROOT = 'C:\Users\cyril.beurier\code\robot-learning-campaigns'
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

`-Provider` accepts `github-copilot`, `opencode` (Zen), or `opencode-go`.
`-Model` accepts a catalogue model ID or a provider-qualified ID.
Conflicting provider/model prefixes fail explicitly.
Without `-Provider`, the default is GitHub Copilot `gpt-6-luna`.
With an OpenCode provider and no `-Model`, the default is
`opencode/deepseek-v4.1-flash-free`.

List choices without starting or changing campaign state:

```powershell
.\run_research.ps1 -Provider opencode -ListModels
.\run_research.ps1 -Provider opencode-go -ListModels
```

For an authorized campaign launch, select the provider and model:

```powershell
.\run_research.ps1 -Provider opencode
.\run_research.ps1 -Model opencode-go/kimi-k3
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
