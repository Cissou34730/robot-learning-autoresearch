# RL Research Program — Scenario 2: "Reach and Hold"

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
├── environments/reach_env.py      # ONLY _observation() editable (see Hard rules);
│                                    hold logic, target sampling, physics: READ ONLY
├── robots/two_joint_arm.xml       # arm morphology — READ ONLY
├── evaluate.py                    # the metric — READ ONLY
└── training/                      # normalization/viewer plumbing — READ ONLY
tests/test_reach_env.py             # must keep passing after any edit
research/run_experiment.py          # executes experiments — never run with arguments,
                                    # never edit
```

## Mission

Scenario 2 is harder than scenario 1 (which reached 100% at 3 cm touch):

> Success = the end-effector stays within **1.0 cm** of the ball for
> **2 seconds** (100 consecutive control steps). Episodes last up to 500 steps.
> Goal: **>= 98% success rate** over the standard 200-episode evaluation.

Key differences from scenario 1, decided by the experimenter:
- threshold 0.03 -> 0.01 m; episode 200 -> 500 steps; hold counter added
- reward now pays an escalating per-step DWELL bonus inside the band plus a
  HOLD_COMPLETE_BONUS instead of a one-shot touch bonus
- observation gained one dim: held_steps / hold_steps_required
- training budget doubled again: 120000 steps

All scenario 1 scores are retired. The first experiments here establish new
reference numbers.

## Hard rules

1. **Two experiment modes - never mix them in one experiment:**

   **Parameter mode (PREFERRED - fastest)**: no code edits at all. Put your
   change under `"params"` in `research/proposal.json`, using ONLY these keys:
   - `"reward"`: PROGRESS_COEFFICIENT, CLOSENESS_COEFFICIENT,
     CLOSENESS_LENGTH_SCALE, ACTION_COST_COEFFICIENT, DWELL_BONUS_PER_STEP,
     HOLD_COMPLETE_BONUS
   - `"ppo"`: learning_rate, gamma, gae_lambda, n_steps, batch_size, n_epochs,
     clip_range, ent_coef, vf_coef, max_grad_norm, target_kl
   - `"policy"`: net_arch (list of ints), activation (tanh | relu | elu)
   - `"env"`: max_episode_steps

   Params are DELTAS from the champion config; the runner merges them with
   `research/current_params.json` automatically. No ruff/pytest needed.

   **Code mode (structural changes only)**: edit allowed files directly:
   - `robot_learning/rewards/reach_reward.py` - reward *structure* (new terms).
     Coefficient VALUES belong in parameter mode.
   - `robot_learning/environments/reach_env.py` - **ONLY `_observation()`**
     (and observation_space shape if needed). Hold logic, target sampling,
     success/termination, physics: READ ONLY.
   Code mode runs the full lint+test gates. Do not touch
   PPO_HYPERPARAMETERS/POLICY_KWARGS in train.py - parameter mode supersedes
   them; train.py is otherwise READ ONLY now.

2. NEVER change: success threshold (0.01), hold requirement (2 s), target
   radius range, training timesteps (120000), seed (0), evaluation episodes
   (200), evaluation seeds.
3. No new files except `research/proposal.json`. No new dependencies.
4. One variable change per experiment.
5. Never run training or evaluation yourself; never edit EXPERIMENTS.md.
6. Observation changes must keep tests passing; update
   `tests/test_reach_env.py` if your change requires it.

## Protocol

**Phase 1 - decide**

0. If `research/GOAL_REACHED` or `research/STAGNATED` exists, stop immediately.
1. Read `research/EXPERIMENTS.md` and `git log --oneline`. Understand what was
   tried, what worked, what remains untried.
2. Choose ONE change. If it can be expressed as parameter values, use
   **parameter mode**: write `research/proposal.json` as:
   ```json
   {"change": "<one line>", "hypothesis": "<max 3 sentences>",
    "params": {"ppo": {"gamma": 0.995}}}
   ```
3. Otherwise use **code mode**: make the structural code edit in the allowed
   files and write proposal.json WITHOUT the params key.
4. Verify your intent: parameter mode needs a non-empty params object; code
   mode needs a non-empty `git diff --stat robot_learning`.

**Phase 2 - execute (hands off)**

5. Run exactly: `uv run python research/run_experiment.py`
   It validates input, runs gates when needed (ruff+pytest in code mode only),
   trains 120000 steps, evaluates 200 episodes, appends the results row,
   applies the ratchet (commit on improvement, revert + cleanup otherwise),
   updates Best so far, and writes GOAL_REACHED / STAGNATED sentinels when
   appropriate.
6. Read the `SUMMARY:` line it prints. If status is "error", fix only trivially
   wrong input (e.g. malformed proposal.json) and rerun once; otherwise stop.
7. Stop. The outer loop starts the next session.

## Research taste

- The binding constraint here is likely PRECISION + STOPPING, not speed:
  flying into the band overshoots and resets the hold counter.
- Reward shaping must stay continuous in distance (scenario 1 lesson).
- If three coefficient tweaks fail in a row, propose a different KIND of change.
- Understand why the current reward produces the observed behavior before
  reshaping it.
