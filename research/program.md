# RL Research Program

You are an autonomous research agent. This file is your complete instructions.
Execute **exactly one experiment** per session, following the protocol below,
then stop.

## Environment notes

- You are on **Windows PowerShell**, not bash: there is no `head`, `tail`,
  `grep` or `&&`. Use `Select-Object -First 20`, `Select-String`, and separate
  commands instead.
- A modified `research/EXPERIMENTS.md` in git status is normal and expected;
  never revert it. You never edit EXPERIMENTS.md yourself — the runner script
  owns it.

## Repository map (do NOT waste turns re-discovering this)

```
robot_learning/
├── rewards/reach_reward.py        # THE REWARD — your main editing surface
├── train.py                       # PPO_HYPERPARAMETERS, POLICY_KWARGS, env kwargs (editable)
│                                    everything else in train.py: do NOT edit
├── environments/reach_env.py      # obs/action/episode logic — READ ONLY (context)
├── robots/two_joint_arm.xml       # arm morphology — READ ONLY
├── evaluate.py                    # the metric — READ ONLY
└── training/                      # normalization/viewer plumbing — READ ONLY
tests/test_reach_env.py             # must keep passing after any edit
research/run_experiment.py          # executes experiments — never run with arguments,
                                    # never edit
```

## Mission

Improve the PPO policy for the `reach` task until the evaluation success rate is
**>= 98%** (200 episodes, fixed seeds, threshold 3 cm). The runner script judges
this automatically.

## Hard rules

1. You may ONLY edit:
   - `robot_learning/rewards/reach_reward.py` — reward structure and coefficients.
     The function receives the applied `action`, so energy/stability penalties
     are possible.
   - `robot_learning/train.py` — ONLY `PPO_HYPERPARAMETERS` (any valid SB3 PPO
     parameter), `POLICY_KWARGS`, and env construction kwargs in `main()`.
2. NEVER change: success threshold, target radius range, training timesteps
   (60000), seed (0), evaluation episodes (200), evaluation seeds.
3. No new files except `research/proposal.json`. No new dependencies.
4. One variable change per experiment.
5. Never run training or evaluation yourself; never edit EXPERIMENTS.md.

## Protocol

**Phase 1 — decide**

0. If `research/GOAL_REACHED` or `research/STAGNATED` exists, stop immediately.
1. Read `research/EXPERIMENTS.md` and `git log --oneline`. Understand what was
   tried, what worked, what remains untried.
2. Choose ONE change to the allowed files.
3. Write `research/proposal.json`:
   ```json
   {"change": "<one-line description>", "hypothesis": "<max 3 sentences>"}
   ```
4. Make the code edit. Verify with `git diff --stat robot_learning`: if empty,
   you have not made the change — do not proceed.

**Phase 2 — execute (hands off)**

5. Run exactly: `uv run python research/run_experiment.py`
   It validates the diff, runs ruff+pytest, trains 60000 steps, evaluates 200
   episodes, appends the results row, applies the ratchet (commit on
   improvement, revert + cleanup otherwise), updates Best so far, and writes
   `GOAL_REACHED` / `STAGNATED` sentinels when appropriate.
6. Read the `SUMMARY:` line it prints. If status is "error", fix only trivially
   wrong input (e.g. malformed proposal.json) and rerun once; otherwise stop.
7. Stop. The outer loop starts the next session.

## Budget notice (2026-08-25 evening)

Budget was doubled 30000 -> 60000 steps because experiments 9 and 13 showed
convergence needs more room. All pre-change scores are retired; the re-baseline
row defines the new reference. Old numbers must not be compared against.

## Research taste

- Prefer structural insights over parameter jitter: if three coefficient tweaks
  fail in a row, propose a different KIND of change (observation design, reward
  structure, exploration mechanism).
- Small consistent wins beat rare big gambles: the ratchet only keeps wins.
- Understand why the current reward shape produces the observed behavior before
  reshaping it.
