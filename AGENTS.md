# AGENTS.md

Instructions for human-directed maintainer sessions on this harness.

Campaign agents (PI, preliminary analyst, coder and reviewer) cannot read this
file. Their permissions are defined in `contracts/authority.md`, their
lifecycle in `contracts/program.md`, their task in `contracts/scenario.md` and
their operation formats in `contracts/instruments.md`.

## Before starting

Read `docs/harness-campaign-split.md` first. It records the approved
harness/campaign repository split, completed stages and follow-up corrections.

## Audience separation

Keep three audiences separate:

- Maintainer: `AGENTS.md`, `README.md`, `docs/` and `.github/`. These are
  reserved from every campaign agent.
- Runner: `runner/`, `benchmark/`, `tools/` and the launch scripts. These are
  reserved from campaign reads.
- Campaign agents: `contracts/`, `campaigns/brief.md`, session prompts in the
  launch scripts and tool descriptions in `runner/copilot/`. The coder and
  reviewer receive fixed excerpts from `contracts/authority.md`,
  `contracts/instruments/coding.md` and `contracts/instruments/measurement.md`
  (see `load_task_context`).

Text that campaign agents receive states the current rules only. Keep
maintainer reasoning, change history, incident references and launcher
guardrails out of it. The unattended inquiry cap (`-MaxInquiries`) is a
maintainer guardrail: never expose it, its value or its remaining count to
campaign agents.

When `contracts/authority.md`, `contracts/instruments/coding.md` or
`contracts/instruments/measurement.md` changes its excerpt boundaries, update
`runner/copilot/coding_contracts.py`.
`tests/autoresearch/test_ownership_registry.py` checks its human-owned list
against enforcement.

## Maintainer authority

Maintainer sessions may edit harness code, scripts, tests and documentation
within the approved task, run targeted checks through `uv run`, and commit and
push harness changes when requested. This grants campaign agents no additional
permission.

## Repositories

The harness repository contains `runner/`, `contracts/`, `benchmark/`,
`tests/`, `tools/`, `docs/`, launch scripts and the locked Python project.
The separate local campaign repository contains `robot_learning/`,
`campaigns/`, `pi_workspace/`, `runner/state/`, `models/`, reports and agent
session data. Contract paths are logical paths: `runner/paths.py` resolves them
to the owning repository. Protected scientific package initializers stay
protected although they are stored with the campaign.

The launch and reset scripts accept `-CampaignRoot` and default to the sibling
`robot-learning-campaigns` folder. Direct maintainer Python commands select it
with `ROBOT_LEARNING_CAMPAIGN_ROOT` and use the harness Python environment.
Campaign Git operations run only in the campaign repository and never push.
Harness development is committed and pushed separately and requires no merge
into the campaign. See `README.md` for initialization, launch limits and
commands.

## Environment

The locked stack is native `mujoco==3.12.0`, `gymnasium==1.3.0`,
`stable-baselines3==2.9.0` and `github-copilot-sdk==1.0.26`. Dependencies are
human-owned. Run all project Python through `uv run`. Never invoke system
`python`, `python3`, `pytest` or `ruff`, or the interpreter inside `.venv`.

Agent-runtime internals (tool binding, coding handoff, read policy, recovery)
are described in `docs/runtime-mechanics.md`.

## Validation

Do not run repository-wide lint or format passes. Format only touched files.

Keep validation proportional to the change. Every test or check must cover
changed behavior or a directly affected regression risk. Prefer existing
targeted tests or a minimal reproduction; do not add speculative, redundant,
or unrelated cases or build new test infrastructure for a minor fix.
If an unrelated environment problem blocks validation, report it instead of
expanding the task into a test-environment repair.

Tests cover executable behavior and explicit machine-readable contracts, never
documentation wording, headings, labels, source fragments, ordering, or
enumeration counts.

## Persistence and Git

Campaign artifacts are the authoritative scientific evidence:
`campaigns/brief.md`, the scientific session records, completed operation
records and their artifacts. Failed operations are execution history, not
evidence.

Raw measurements have the fixed local archive root
`campaigns/evaluations/<campaign-id>/`, which Runner publication excludes. Git
publishes source, campaign state, compact results and artifact identities, not
raw measurement contents. Training logs also stay local and ignored. No reset
backups are kept: a Fresh reset deletes the old campaign's ignored
measurements and logs. A Prepared Baseline reset carries only the selected
baseline's evaluation files across cleanup in a temporary directory. Git alone
is not a complete backup or transfer of raw campaign measurements.

## Layout

- `contracts/` - human-owned contracts that campaign agents read.
- `benchmark/` - final and task-reference contracts and evaluators, hidden
  from campaign agents.
- `runner/` - lifecycle runner, protocol enforcement and Copilot integration,
  hidden from campaign agents.
- `tests/` - maintainer validation, hidden from campaign agents.
- `tools/` - maintainer utilities.
- `docs/` - maintainer documents and campaign reports.
- Campaign repository: `robot_learning/` (PI-owned scientific code, protected
  package initializers and `robot_learning/lab/`), `campaigns/` (Runner-written
  evidence, `results.jsonl`, `EXPERIMENTS.md`, `brief.md`, `evaluations/`,
  `checkpoints/`), `pi_workspace/` (scientific model and Runner exchange),
  `runner/state/` and `models/candidates/`.
