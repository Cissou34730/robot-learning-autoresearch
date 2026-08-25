# RL Research Program

You are an autonomous research agent. This file is your complete instructions.
Execute **exactly one experiment** per session, following the protocol below,
then stop.

## Environment notes

- You are on **Windows PowerShell**, not bash: there is no `head`, `tail`,
  `grep` or `&&`. Use `Select-Object -First 20`, `Select-String`, and separate
  commands instead.
- A modified `research/program.md` or `research/EXPERIMENTS.md` in git status
  is normal and expected; never revert them.

## Repository map (do NOT waste turns re-discovering this)

```
robot_learning/
├── rewards/reach_reward.py        # THE REWARD — your main editing surface
├── train.py                       # PPO_HYPERPARAMETERS, POLICY_KWARGS, env kwargs (editable)
│                                    also: VecNormalize setup, checkpointing, save logic (do NOT edit)
├── environments/reach_env.py      # obs/action/episode logic — READ ONLY (context for hypotheses)
├── robots/two_joint_arm.xml       # arm morphology — READ ONLY
├── evaluate.py                    # the metric: 200 episodes, fixed seeds 1000+ — READ ONLY
├── play.py                        # viewer — irrelevant to research
└── training/                      # normalization/viewer plumbing — READ ONLY
tests/test_reach_env.py             # must keep passing after any edit
```

## Mission

Improve the PPO policy for the `reach` task until it reaches:

> **success rate >= 98%** measured by
> `uv run python -m robot_learning.evaluate --model models/<run>/model.zip --episodes 200`
> (fixed evaluation seeds, threshold 3 cm)

## Hard rules (violating any of these invalidates the experiment)

1. You may ONLY edit these:
   - `robot_learning/rewards/reach_reward.py` — reward function, its coefficients
     and structure. The function receives the applied `action`, so energy or
     stability penalties are possible via the action argument.
   - `robot_learning/train.py` — ONLY these parts:
     - the `PPO_HYPERPARAMETERS` dict (any valid SB3 PPO parameter)
     - the `POLICY_KWARGS` dict (network architecture, activation function)
     - the env construction kwargs in `main()` (e.g. `max_episode_steps`,
       `frame_skip`)
2. NEVER edit: `environments/`, `robots/`, `evaluate.py`, `play.py`,
   `normalization.py`, `viewer_callback.py`, `tests/`, this file, the driver script.
3. NEVER change: success threshold, target radius range, training timesteps
   (30000), seed (0), number of evaluation episodes (200), or evaluation seeds.
   These define the task and the metric — changing them is cheating.
4. No new files except inside `research/`. No new dependencies. No comments-heavy
   rewrites: keep changes small, targeted, readable.
5. One variable change per experiment. If you want to try two things, that is two
   experiments.

## Protocol (follow in order)

1. Run `git status`. If anything outside `research/EXPERIMENTS.md` is modified,
   run `git checkout -- robot_learning/` first. Always start from committed state.
2. Read the last ~10 entries of `research/EXPERIMENTS.md` and `git log --oneline`.
   Understand what has been tried and what worked.
3. Choose ONE change. Write your entry in `research/EXPERIMENTS.md` FIRST:
   experiment number, date, the change, and your hypothesis.
4. Make the actual code edit, then verify it exists: run `git diff --stat`.
   If the diff is empty, you have NOT made the change — do not train.
   Record the diff summary in your EXPERIMENTS.md entry before training.
5. Train:
   `uv run python -m robot_learning.train --timesteps 30000 --seed 0`
6. Evaluate using the model path printed at the end of training:
   `uv run python -m robot_learning.evaluate --model models/<run-dir>/model.zip --episodes 200`
7. Immediately append the results to your EXPERIMENTS.md entry: success rate,
   mean distance, median distance.
8. Apply the ratchet:
   - **Improvement over best so far** → `git add robot_learning/rewards/reach_reward.py robot_learning/train.py`
     then `git commit -m "exp N: <one-line description> -> <X>%"`
   - **Equal or worse** → revert with `git checkout -- robot_learning/` AND delete
     the losing run directory under `models/`.
9. Update the "Best so far" line at the top of `research/EXPERIMENTS.md`.
10. If the new best is >= 98%: write a short summary to `research/GOAL_REACHED`
   and stop. The outer loop will not start new sessions after seeing this file.

## Log discipline (keeps iterations fast — read this before writing anything)

- `EXPERIMENTS.md` is read by EVERY future session. Its size slows down all
  research. Keep your additions tight:
  - Hypothesis: **max 3 sentences**.
  - Post-mortem note: **max 5 sentences**, only when a result teaches something
    non-obvious.
  - Exactly ONE table row per experiment, appended at the END of the table.
    No prose between rows; notes go after the full table.
- Long-form analysis belongs in `research/archive.md`, never in the main log.
- Do not re-read files you have already read this session.

## Failure handling

- A command fails or crashes? Record what happened as the experiment result,
  revert your code changes (`git checkout -- robot_learning/`), update
  EXPERIMENTS.md, and stop. The next session will pick up from clean state.
- Never leave the repo in a modified state when stopping.

## Research taste

- Prefer structural insights over parameter jitter: if three coefficient tweaks
  all failed, propose a *different kind* of change (observation design, reward
  structure, exploration).
- Small consistent gains beat rare big gambles: the ratchet only keeps wins.
- Read the reward function before touching it; understand why the current shape
  produces the observed behavior.
