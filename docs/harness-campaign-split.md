# Harness / campaign repository split

Approved maintainer plan (2026-10-19). Resume work from this file.

## Decisions

- **Safeguard:** `C:\Users\cyril.beurier\code\robot-learning-inquiry-centered-lifecycle`
  (branch `inquiry-centered-lifecycle`, commit `b01fb9a`) is never modified.
- **Harness repository:** `C:\Users\cyril.beurier\code\robot-learning-harness`,
  branch `harness`, started as one root commit snapshot of `b01fb9a`. It holds
  the harness only and is pushed to GitHub `origin` after every validated
  harness change.
- **Campaign repository:** `C:\Users\cyril.beurier\code\robot-learning-campaigns`,
  a separate local Git repository with no GitHub remote. Campaign commits are
  never pushed anywhere.
- **PI-owned code lives in the campaign repository.**
- **Initial campaign content:** the result of a reset from baseline v3
  (`baseline-distinct-episodes-v3`, commit `8256c8c`).

## Ownership of top-level paths

| Campaign repository | Harness repository |
|---|---|
| `robot_learning/` (PI-owned code, lab, protected package initializers) | `runner/` (except `runner/state/`) |
| `campaigns/` (history, brief, checkpoints, logs, evaluations) | `contracts/`, `benchmark/` |
| `pi_workspace/` | `tools/`, `tests/`, `docs/`, `typings/` |
| `runner/state/` (Runner campaign state and markers) | `AGENTS.md`, `README.md`, `main.py` |
| `models/` (disposable candidates, ignored) | launch, reset and session scripts |
| | `pyproject.toml`, `uv.lock` |

## Design

- **One logical path namespace.** Repository-relative paths keep their current
  meaning (`robot_learning/train.py`, `campaigns/results.jsonl`,
  `contracts/program.md`, ...). Contracts, prompts, ownership rules and state
  records do not change. `runner/paths.py` maps each logical path to its
  physical location: campaign-owned prefixes resolve below the campaign root,
  everything else below the harness root.
- **Campaign root selection:** environment variable
  `ROBOT_LEARNING_CAMPAIGN_ROOT`, set by the launch and reset scripts from their
  `-CampaignRoot` parameter (default: sibling `robot-learning-campaigns`).
  Without it, the campaign root equals the harness root (single-folder mode,
  used by existing tests).
- **Git:** campaign commits, deltas, recipe restoration and baseline lookup run
  in the campaign repository. Split-mode publication never pushes, even if a
  remote is accidentally added. The local campaign repository has no remotes.
- **Python:** the campaign root is placed first on `sys.path` and `PYTHONPATH`
  so `robot_learning` resolves from the campaign repository while `contracts`,
  `benchmark` and `runner` resolve from the harness. `uv` always runs with the
  harness project.
- **PI agents:** the Copilot working directory is the campaign root. Harness
  files the PI may read (`AGENTS.md`, `contracts/`) are addressed through the
  logical namespace; path policy evaluates logical paths.
- **Reset:** recipe and baseline references resolve in the campaign repository.
  Task compatibility compares a task fingerprint recorded by the campaign
  commit with the current harness task files.

## Stages

Each stage is validated with targeted tests, committed and pushed on `harness`.

1. Path layer: logical/physical mapping in `runner/paths.py`; all Runner file
   access routed through it. Single-folder mode unchanged.
2. Git layer: campaign Git operations in the campaign root; optional push.
3. Python execution: import path and subprocess environment.
4. Copilot agent layer: working directory and path policy.
5. Launch and reset scripts: `-CampaignRoot`, per-campaign mutex.
6. Reset: campaign-repository references and task fingerprint.
7. Physical split: remove campaign-owned paths from the harness repository;
   create the campaign repository; initialize it with a baseline v3 reset.
8. Documentation: `AGENTS.md`, `README.md`, reset documentation.

## Progress

- [x] Harness snapshot `c085e98` pushed to `origin/harness`.
- [x] Stage 1: separate roots and logical path mapping. Targeted validation:
  55 passed; three baseline-reset failures match the saved pre-refactor baseline.
- [x] Stage 2: campaign Git working directory and local-only publication.
- [x] Stage 3: campaign imports and child-interpreter environment; a real child
  process resolves scientific code from the campaign and contracts/Runner from
  the harness. Targeted checks: 42 passed; four unchanged lifecycle failures.
- [ ] Stage 4
