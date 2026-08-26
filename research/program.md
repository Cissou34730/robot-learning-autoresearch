# RL Research Program - Scenario 2: "Reach and Hold"

You are an autonomous research agent. Execute **exactly one experiment** per
session following this protocol, then stop.

## Environment notes

- Windows PowerShell: no `head`, `tail`, `grep`, `&&`. Use `Select-Object
  -First 20`, `Select-String`, separate commands.
- Modified `research/EXPERIMENTS.md` / `research/postmortems.md` in git status
  is normal; never revert them. You never edit EXPERIMENTS.md - the runner owns it.
- Do NOT read `run_experiment.py`, `train.py`, or `research_config.py` source:
  this document fully specifies the proposal format, allowed parameter keys,
  boundaries, and error semantics, and is kept in sync with them. If SUMMARY
  reports an input error, its message is authoritative - fix per the message,
  not by re-reading source.
- A previous scenario solved the same arm at "touch 3 cm" (100%). This scenario
  requires precision (1 cm) and stability (2 s hold): a different kind of skill.

## Repository map (do not re-discover)

```
robot_learning/
├── rewards/reach_reward.py        # reward structure (editable, code mode)
├── environments/reach_env.py      # ONLY _observation() editable (code mode);
│                                    curriculum, hold logic, physics: READ ONLY
├── training/research_config.py    # config loader + boundaries - READ ONLY
├── train.py                       # READ ONLY (all parameters come from JSON)
tests/test_reach_env.py            # must keep passing; update if obs changes
research/current_params.json       # ALL tunable parameters (single source of truth)
research/run_experiment.py         # executes experiments - READ ONLY
research/postmortems.md            # researcher-owned scientific memory
```

## Mission & goal (immutable)

Success = end-effector within 1.0 cm of the ball for 100 consecutive steps
(2 s), episodes up to 500 steps, random targets (radius 6-20 cm).
Goal: >= 98% success over the standard 200-episode evaluation.
A training-time curriculum eases intermediate stages; candidates are always
evaluated on this unchanged final task.

## Escalation ladder

Experiments belong to a class. After 5 consecutive failures in one class, the
runner writes `ESCALATION_REQUEST` and you MUST move to the next class:

1. coefficient and hyperparameter tuning
2. reward structure
3. observation representation
4. training curriculum
5. policy architecture and training schedule
6. learning algorithm (e.g. PPO vs SAC)
7. broader goal-preserving training-method changes

If an `ESCALATION_REQUEST` exists, your session must propose an experiment in
the requested next class.

## Hard rules (machine-enforced by the runner)

1. One coherent hypothesis per experiment. Coordinated edits across areas are
   allowed IF they serve that single hypothesis.
2. Parameter mode (preferred): no code edits; change values only, via `"params"`
   in proposal.json. Allowed keys:
   - reward: PROGRESS_COEFFICIENT, CLOSENESS_COEFFICIENT,
     CLOSENESS_LENGTH_SCALE, ACTION_COST_COEFFICIENT, DWELL_BONUS_PER_STEP,
     HOLD_COMPLETE_BONUS
   - ppo: learning_rate, gamma, gae_lambda, n_steps, batch_size, n_epochs,
     clip_range, ent_coef, vf_coef, max_grad_norm, target_kl
   - policy: net_arch, activation ("tanh"|"relu"|"elu")
   - env: max_episode_steps
3. Code mode (for structural changes): edits allowed ONLY in
   `rewards/reach_reward.py`, `environments/reach_env.py` (`_observation()`
   only), `tests/test_reach_env.py`. The runner REJECTS any other file and
   verifies immutable task invariants after every code-mode edit.
4. NEVER touch: robot morphology/physics, success threshold, hold duration,
   target distribution, evaluator, seeds, episode count, or the goal itself.
   Training-time curricula may ease intermediate stages only.
5. Never mix parameter mode and code mode in one experiment.
6. Never run training/evaluation yourself; never edit EXPERIMENTS.md.

## Protocol

Phase 1 - decide:
0. If GOAL_REACHED exists, stop. If ESCALATION_REQUEST exists, read it: your
   experiment must come from the requested class.
1. Read EXPERIMENTS.md, the last sections of postmortems.md, git log --oneline.
2. Form ONE coherent hypothesis. Choose its class and mode.
3. Parameter mode: write proposal.json with "change", "hypothesis", "class",
   "params". Code mode: make the structural edit first, then proposal.json
   WITHOUT params. Every proposal requires a "class" field.

Phase 2 - execute:
4. Run exactly: `uv run python research/run_experiment.py`
5. Read the SUMMARY line. On error, fix trivial input problems and rerun once.

Phase 3 - research (mandatory):
6. Inspect `research/last_train.log` (training dynamics) and think about what
   the result means beyond the number.
7. Append to `research/postmortems.md`:
   - experiment number and whether the hypothesis was supported
   - what behavior changed (approach distance, hold steps reached, stability)
   - the likely current binding constraint
   - what was learned and what should NOT be retried
   - recommended next experiment class
8. Stop.

## Budget

Fixed 120000 training steps per experiment (seed 0). This optimizes sample
efficiency and comparability between experiments; unlike Karpathy's wall-clock
budget it does not optimize performance per unit of compute. Only the
experimenter may change it, between sessions.
