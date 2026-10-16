# Robot AutoResearch

Read the [Robot-learning research process](docs/research-overview/robot-learning-overview-20261002.html).

The Copilot harness integration uses Python SDK 1.0.19. Install the locked
scientific stack and agent runtime with `uv sync --locked --group researcher`.
Native coding subagents and custom evidence tools are Copilot-specific;
OpenCode retains its legacy interface.

Copilot scientific-model preparation uses the selected PI model with `max`
reasoning, including continuations. Ordinary PI sessions use the launcher's
`-Reasoning` setting. The coding reviewer remains at `high`.

See [AGENTS.md](AGENTS.md) for ownership and execution boundaries,
[scientific instruments](contracts/instruments.md) for tool contracts, and
the [harness tracker](docs/harness-experiment-log.md) for implementation status.
Campaign launches, resets and scientific execution require explicit maintainer
authorization.
