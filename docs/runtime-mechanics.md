# Runtime mechanics

Maintainer reference for the agent runtime behind the PI-facing contracts.
Campaign agents cannot read this file. PI-facing rules live in
`contracts/authority.md`, `contracts/program.md` and `contracts/instruments.md`.

## Agent runtime

The Copilot agent runtime uses `github-copilot-sdk==1.0.19`. Its native
subagents, hooks and custom tools are the agent runtime. The scientific stack
and Runner operations stay separate from the SDK.

The main PI session has `view`, `rg` and `glob`, the custom evidence tools,
`scientific_api_reference`, `scientific_coding` and `submit_operation`. The
permission handler denies every main-session file write. The trusted launcher
validates each structured request through Runner and returns factual results
and the current state to the same conversation.

The preliminary analyst keeps its publication tools and a restricted shell.
`runner/copilot/command_policy.py` permits read-only Git there and denies
mutating Git, dependency changes, direct test runs and reserved scripts.
Coding delegation is not exposed in that phase.

## Coding handoff

`scientific_coding` dispatches a native coding subagent. Its readable and
writable files are bound mechanically to the explicit request. Native start
instructions state the locked scientific API versions. Coder and reviewer
receive fixed task context from `load_task_context` in
`runner/copilot/coding_contracts.py`: the scenario, an excerpt of
`contracts/authority.md` and excerpts of `contracts/instruments.md`.

Each new assignment receives an independent native review with high
reasoning. Corrections reuse that reviewer to check only the reported problems
and errors introduced by the repair. The reviewer has exactly scoped reads and
no write or execution authority. A failed review goes unchanged to the same
coder within the original intent and file scope. The PI receives the final
package or a blocked requirement (`needs_pi`).

A correction may supply intent and handle alone; the handler keeps and
revalidates the immutable stored file scope. A handle from another bounded
context does not authorize attaching a coder. Lifecycle hooks and change
reports support PI review; they do not certify scientific validity.

Reviewer usage is recorded separately from coder and PI usage.

## Read and search policy

Read restrictions are tool-level, not an operating-system sandbox. The shared
reserved-script policy in `runner/copilot/path_policy.py` applies to `view`,
explicit shell-reader targets and scoped search. Searches apply it to
descendants before reading content or returning paths. Maintainer documents
(`AGENTS.md`, `README.md`, `docs/`), tests, Runner, benchmark and launch
scripts are reserved in every phase. The preliminary phase can read all of
`robot_learning/`; later phases read only PI-owned scientific files there.
Preliminary shell traversal and wildcard readers are denied.

## Contexts and recovery

The Copilot runtime stays alive across operations and bounded contexts.
Ordinary results continue in the same context. Checkpoints end it, and the
launcher starts a fresh context from durable state. An interrupted or lost
response is recovered from pending or completed Runner state, not by blind
resubmission. Publication failures stop for repair; they do not authorize
reacceptance or re-execution.
