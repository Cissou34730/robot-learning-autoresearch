# Autonomous Robot Learning Research

Run one experiment per session, then stop. The outer PowerShell loop starts a
fresh session for the next experiment. Do not create subagents.

## Goal

Train the two-joint MuJoCo arm to reach a random target 6–20 cm away and remain
within 1.0 cm for 100 consecutive control steps (2.0 s). The fixed evaluation is
200 deterministic episodes. The goal is at least 98% success.

The evaluator is ground truth. Never change robot physics, target distribution,
final threshold, final hold duration, evaluation seeds or episode count, or the
500-step episode limit.

## Curriculum

Keep the training curriculum. It transfers from the experiment-19 policy that
already solved 3 cm touch, then tightens position before extending the hold.
The final curriculum stage must remain the exact 1 cm / 2 s task.

Curriculum performance is training evidence, not the score. All keep/discard
decisions use the unchanged final evaluator.

## Context

Read only:

- `research/brief.md`
- `research/last_train_summary.md` after a run
- `git log --oneline -8`

Do not dump full logs or histories into context. Read a targeted raw section
only when a specific missing fact changes the next decision.

Do not read `research/run_experiment.py`, `robot_learning/train.py`, or
`robot_learning/training/research_config.py` during ordinary experiments.
The runner's error message is authoritative.

## What can change

Prefer the smallest useful change.

Parameter mode uses `params` in `research/proposal.json`:

- reward coefficients
- PPO hyperparameters
- policy architecture
- training-curriculum advancement settings

Code mode may edit:

- `robot_learning/rewards/reach_reward.py`
- observation or curriculum code in
  `robot_learning/environments/reach_env.py`
- corresponding focused tests
- for a genuine learning-algorithm experiment only:
  `train.py`, `evaluate.py`, and `play.py`

Never edit the runner, evaluator criteria, or task invariants during an
experiment. Never mix parameter and code mode.

Transfer is the default initialization. Use `"initialization": "fresh"` only
when an observation-size, policy-architecture, or learning-algorithm change is
incompatible with the transfer checkpoint. Account for that changed
initialization when interpreting the result.

## Baseline

If `research/BASELINE_PENDING` exists, the next run is the unchanged control:
the transfer checkpoint, current default parameters, and current curriculum.
Write a proposal with `"baseline": true` and no params or code edits. Run it
before proposing improvements. Its measured score becomes the initial best.

## Experiment loop

1. Read the compact context and inspect git status.
2. If baseline is pending, run it unchanged.
3. Otherwise, identify one promising idea. Use prior failures to avoid repeats.
4. Write `research/proposal.json`:

   ```json
   {
     "change": "short, precise description",
     "hypothesis": "why it may work and what observable should change",
     "class": "short research-area label",
     "initialization": "transfer"
   }
   ```

   Add `params` only in parameter mode.

5. Run exactly:

   `uv run python research/run_experiment.py`

6. Read SUMMARY and `research/last_train_summary.md`.
7. If the score improved, the runner keeps and commits the change. Otherwise it
   restores the previous code/configuration. Crashes are failures unless a
   trivial typo can be corrected once.
8. Append 5–8 concise lines to `research/postmortems.md`:

   - result and keep/discard verdict
   - what behavior or training dynamic changed
   - what the result rules out
   - the best next idea

9. Run `uv run python research/build_research_brief.py`, then stop.

## Research taste

- The score decides; explanations do not.
- Training reward can rise while deterministic behavior gets worse.
- Early noise-driven contacts are not a learned controller.
- Prefer deletion and simplification when results are equal.
- Do not repeat a failed mechanism with cosmetic coefficient changes.
- When stuck, change the level of attack: reward, observation, curriculum,
  architecture, or algorithm.
- Keep descriptions short. Spend tokens choosing and testing ideas, not
  narrating them.
- Preserve negative results because they narrow the search.
- Continue until `GOAL_REACHED` exists or the human stops the outer loop.

## Budget

Every experiment trains for exactly 120000 steps with seed 0. This fixed sample
budget makes runs comparable for this CPU-first robot task.
