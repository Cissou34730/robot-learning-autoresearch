# Robot AutoResearch

Read the [Robot-learning research process](docs/research-overview/robot-learning-overview-20261002.html).

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

Stop any active campaign before resetting:

```powershell
.\reset_research.ps1 -Mode Fresh -RecipeRef baseline-distinct-episodes-v3 -Force
.\run_research.ps1 -Provider github-copilot
```

Baseline v3 is a scientific recipe, not a trained model. Its reset initializes
empty campaign history and leaves scientific-model preparation pending. The
harness stays unchanged. See [reset details](docs/reset-research.md).

Campaign Git tracks source and compact state. Large measurements, disposable
models and other ignored artifacts stay in the campaign folder but are not
backed up by Git. No reset backups are kept.

### Maintainer validation

Select the campaign's scientific code when running tests from the harness:

```powershell
$env:ROBOT_LEARNING_CAMPAIGN_ROOT = 'C:\Users\cyril.beurier\code\robot-learning-campaigns'
$env:PYTHONPATH = "$env:ROBOT_LEARNING_CAMPAIGN_ROOT;$PWD"
uv run pytest tests\autoresearch\test_campaign_paths.py -q
```

The Python environment and dependency lock belong to the harness. Campaign PI
agents cannot install dependencies or run maintainer tests.

The Copilot harness integration uses Python SDK 1.0.19. Install the locked
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
listed in the catalogue. SDK 1.0.19 supports
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

See [AGENTS.md](AGENTS.md) for ownership and execution boundaries,
[scientific instruments](contracts/instruments.md) for tool contracts, and
the [harness tracker](docs/harness-experiment-log.md) for implementation status.
Campaign launches, resets and scientific execution require explicit maintainer
authorization.
