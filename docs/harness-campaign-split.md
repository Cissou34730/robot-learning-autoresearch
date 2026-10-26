# Harness / campaign repository split

Approved maintainer plan (2026-10-19). Resume work from this file.

## Decisions

- **Safeguard:** `C:\Users\cyril.beurier\code\robot-learning-inquiry-centered-lifecycle`
  (branch `inquiry-centered-lifecycle`, commit `b01fb9a`) is never modified.
- **Harness repository:** `C:\Users\cyril.beurier\code\robot-learning-harness`,
  branch `harness`, started as one root commit snapshot of `b01fb9a`. It holds
  the harness only and is pushed to GitHub `origin` after every validated
  harness change. It is now a standalone repository with its own `.git`
  directory, and `harness` is the GitHub default branch.
- **Campaign repository:** `C:\Users\cyril.beurier\code\robot-learning-campaigns`,
  a separate local Git repository with no GitHub remote. Campaign commits are
  never pushed anywhere. *Since 26 October 2026 this folder is a plain root that
  holds one campaign repository per slot (`campaign-1` to `campaign-5`); the
  original repository is `campaign-1`.*
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
| `models/` (disposable candidates, ignored), `reports/`, `.copilot/` | launch, reset and session scripts |
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
  files the PI may read (`contracts/`) are addressed through the
  logical namespace; path policy evaluates logical paths. Read/search requests
  that expand those logical paths under the campaign root are routed to their
  harness location before authorization, but existing shadow files are rejected.
  Write authorization does not use these read aliases.
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
- [x] Stage 4: PI reads/searches map logical contract paths to the harness;
  campaign writes remain scoped and harness/shadow writes stay denied. Native
  view argument rewriting is supported by the installed SDK. Targeted checks:
  51 passed.
- [x] Stage 5: launch/reset accept `-CampaignRoot`, select the harness uv
  project, and share a per-campaign mutex. PI trust snapshots protect both Git
  roots. PowerShell parsing and 14 targeted trust checks passed.
- [x] Stage 6: reset references resolve in campaign Git; versioned task-file
  fingerprints bind the recipe to the harness task. Protected runtime checks
  verify each repository against its own HEAD. Targeted checks: 70 passed.
- [x] Stage 7: campaign-owned files removed from the harness; wheel packages
  contain only harness packages. The independent local campaign has the v3
  recipe tag and a Fresh-reset state, with no remotes. Full suite against
  physically separated science: 500 passed, 44 failures identical to the saved
  pre-refactor baseline, no new failures. A separate initializer smoke attempt
  under the session folder was blocked by Windows/Git directory ownership.
- [x] Stage 8: README, agent instructions and reset documentation describe
  initialization, campaign selection, evolving the harness without merges, and
  strictly local campaign commits. Documented ownership checks: 14 passed.
  A real MuJoCo environment loaded the v3 science from the campaign repository
  and robot XML from the harness, reset and stepped successfully. No training
  or PI session was started.

## Post-split corrections

- Both launch (`3ce7063`) and reset (`2c4bfde`) now restore the caller's
  working directory in `finally`, including on failure. A relative
  reset-then-launch sequence is covered without executing campaign work;
  13 shell/stop-control checks passed.
- A restart after the repaired training-log error resumed the original
  conversation's `validation_fatal` result, while durable S1 still held
  completed T1 and no pending operation/checkpoint. The ownership gate passed,
  but the PI refused further submissions. This mismatch was recorded as
  OI-037. The maintainer closed it on 21 October without claiming a verified
  recovery. A later maintainer Fresh reset starts a new campaign;
  it is not recovery or evidence that the mismatch is repaired.
- Audited the generated-file migration after the T1 log failure: training and
  disposable model outputs; evaluation, reference, official, progress and
  sealed module artifacts; Runner requests and markers; briefs; usage records;
  SDK session/output files; durable state and candidate/retained checkpoints.
  Real-Git regression coverage creates 24 ignored output paths, verifies their
  physical campaign ownership, checks that only scientific edits enter the
  scientific delta, and checks that memory publication commits only the eight
  selected durable state/checkpoint paths. Unexpected campaign edits remain
  rejected. Combined publication, campaign-boundary, split-path and Copilot
  checks: 78 passed. No additional normal-output leak was found; this is not a
  claim that every live lifecycle path has been exercised.
- Restored the campaign initializer's missing `campaigns/training_logs/` ignore
  rule and explicitly classified that prefix as Runner memory. Without it,
  the first completed training left an untracked log that the next operation
  incorrectly rejected as a scientific edit. The existing campaign ignore
  file was repaired in a local-only commit; no training, measurement or state
  history was replayed. Regression checks: 56 passed. The actual S1 scientific
  ownership gate accepts the campaign, with completed T1 and its log preserved.
- The maintainer confirmed a live campaign runs successfully in the separated
  campaign repository.
- With the campaign stopped, the harness was detached from the old worktree
  storage without changing its code, environment or untracked files. Its own
  Git storage contains only the new harness history. GitHub now defaults to
  `harness`; old branches and the safeguard were retained without history
  rewriting. The campaign repository still has no remotes.
- Fixed preliminary contract reads using absolute campaign-root paths. The
  original split routed relative paths only; the view hook now routes missing
  absolute aliases before checking permissions, and scoped search uses the
  same resolver. Split/Copilot checks: 45 passed. All eight failing contract and
  AGENTS requests from the reported session were verified against the actual
  harness files without starting or changing a campaign.
