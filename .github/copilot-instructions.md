# GitHub Copilot repository instructions

All project rules, commands, architecture and conventions for AI coding agents
live in the root [AGENTS.md](../AGENTS.md) file — the cross-tool standard read by
Codex and Copilot.

**Follow AGENTS.md as if its contents were written here.**

## Maintainer-directed engineering

Treat the approved scope as a strict boundary, not an invitation to improve
adjacent things. Make the smallest complete change that solves the stated
problem.

Do not add adjacent fixes, refactors, abstractions, agents, speculative tests,
or new test infrastructure without explicit approval. Validate proportionally
with existing targeted checks or a minimal reproduction.

If validation encounters an unrelated environment problem, report the blocker
and stop. Do not turn it into another investigation or repair task.

Any expansion of scope requires explicit approval before work starts. Once
the requested change is complete, commit and push when required, then stop.

These engineering rules do not narrow the PI's scientific authority within
the owned surface defined by AGENTS.md.
