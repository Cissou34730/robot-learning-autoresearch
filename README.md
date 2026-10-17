# Robot AutoResearch

Read the [Robot-learning research process](docs/research-overview/robot-learning-overview-20261002.html).

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
DeepSeek model remains available. Free Zen models use Chat Completions at
`https://opencode.ai/zen/v1`, as the OpenCode client does. SDK 1.0.19 supports
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
