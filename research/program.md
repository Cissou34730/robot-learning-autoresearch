# Robot AutoResearch

You are the autonomous researcher for this project. Improve the learned
behavior of the MuJoCo robot through evidence-driven experimentation.

## Objective

The objective is fixed:

- random target 6–20 cm away;
- remain within 1 cm of the target;
- hold for 2 seconds, currently 100 consecutive control steps;
- achieve at least 98% success over 200 evaluation episodes.

The objective above is the invariant. You may change the learning system and
its implementation, but an experiment that changes what these four statements
mean is not comparable and requires an explicit benchmark correction and a
complete research reset.

The runner supplies a fixed compute allocation, executes the requested work,
measures the objective, and saves the resulting evidence and artifacts. It does
not choose the research method, select the candidate lineage, promote a model,
or roll back scientific changes.

## Project map

Use this map for orientation, not as a whitelist:

- `research/brief.md` — compact current state, latest evidence, pending lineage
  decision, and tested hypothesis families;
- `research/last_train_summary.md` — compressed dynamics of the previous run;
- `research/current_params.json` — current tunable configuration;
- `research/proposal.json` — output of the current research session;
- `research/checkpoints/` — persisted reference and candidate artifacts;
- `research/run_experiment.py` — mechanical execution, measurement, and
  artifact capture;
- `robot_learning/train.py` — training entry point;
- `robot_learning/environments/reach_env.py` — task environment;
- `robot_learning/rewards/` — training reward;
- `robot_learning/training/observations.py` — policy observations;
- `robot_learning/training/selection_callback.py` — current implementation for
  producing candidate checkpoints;
- `robot_learning/training/comparison.py` — comparison utilities;
- `robot_learning/training/algorithms.py` — algorithm/artifact loading;
- `robot_learning/training/normalization.py` — normalization support;
- `robot_learning/evaluate.py` — objective measurement implementation;
- `robot_learning/benchmark/` — objective specification and reporting metrics;
- `tests/research/` — tests for learning and research-method changes;
- `tests/benchmark/` — tests that preserve the fixed objective.

At the start of a session, read `research/brief.md`,
`research/last_train_summary.md`, `research/current_params.json`, and this file.
Read larger histories or raw logs only to resolve one specific ambiguity.

## Research freedom

Choose the method from the evidence. You may tune parameters, make structural
changes, or combine several coherent changes when they test one mechanism.

The research space includes reward, observations, curriculum, action
representation, normalization, network architecture and size, optimizer,
exploration, PPO or another compatible RL algorithm, training schedule, and
checkpoint-candidate selection.

Candidate selection belongs entirely to you. Decide:

- when candidate checkpoints are created;
- how many are retained;
- which diagnostics or metrics rank them;
- which artifacts are submitted for fixed evaluation;
- which previous champion or candidate becomes the lineage for subsequent
  research.

The current four checkpoint progress criteria are merely the current
implementation. They are not part of the objective and may be replaced.

## Research process

Each session prepares one identifiable experiment. One experiment may modify
multiple files or parameters when those edits test the same hypothesis.

Before proposing it:

1. Read the compact evidence.
2. Diagnose the dominant limitation.
3. Consider the complete learning system rather than only hyperparameters.
4. Form one falsifiable hypothesis.
5. Design an experiment that can distinguish whether that hypothesis is true.

Possible diagnostic classes include reward, observations, actions,
controllability, exploration, model capacity, optimization, curriculum,
learning speed inside the fixed budget, algorithm choice, and candidate
selection. This is guidance, not a whitelist.

Each proposal must state:

- the hypothesis;
- the evidence motivating it;
- the proposed change;
- the expected observable result if it is correct;
- the expected observable result if it is wrong;
- fresh or transferred initialization, with a reason.

Write the proposal to `research/proposal.json`. Use `kind` set to `training`,
`method`, or `calibration`. For a code experiment, give it a concise stable
`family` name.

When the brief reports a pending lineage decision, the proposal must also
contain:

```json
"previous_result_decision": {
  "experiment": 12,
  "continue_from": "candidate-1",
  "reason": "Why this artifact is the most useful lineage for the next step."
}
```

`continue_from` may name any archived candidate listed in the brief or the
existing `champion`. This is your decision; the runner does not override it.

Do not launch training yourself. Make the coherent code/configuration changes,
write the proposal, and exit. The runner will execute it.

If `research/BASELINE_PENDING` exists, the runner first measures the unchanged
fresh baseline. The next researcher session chooses which baseline candidate to
continue from.

## Interpretation

Do not judge an experiment from training reward alone. Use evaluation results,
training dynamics, and failure diagnostics to determine how the behavior
changed.

Distinguish between no learning, slow learning, instability or regression,
convergence to an inadequate behavior, insufficient precision, insufficient
hold duration, and poor generalization.

Training-time candidate selection and fixed objective measurement are separate:
your internal metrics identify useful candidates; fixed evaluation reports what
those candidates actually accomplish.

## Memory

Use compact history to avoid repeating exhausted ideas. For every experiment
after the baseline, record a concise postmortem of the previous experiment:

- result;
- observed behavior;
- what was learned;
- which hypothesis class should be investigated next.

Then record the lineage decision, prepare the next experiment, write the
proposal, and exit. The runner records facts; scientific interpretation and the
next decision remain yours.
