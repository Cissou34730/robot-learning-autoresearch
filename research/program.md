# Robot autoresearch

Each research session prepares exactly one experiment, then exits. The runner
owns training, checkpoints, evaluation, rollback, and commits, and starts the
next research session automatically. The overall research loop continues until
the human stops it.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay
within 1 cm for 2 seconds. With the fixed control timestep, those 2 seconds are
currently 100 consecutive control steps; the duration is the source of truth
and the step count is derived from it. Never edit `robot_learning/benchmark/`,
the robot, physics, environment mechanics, evaluator, runner, or
`tests/benchmark/`.
The protected evaluation target is always the final 1 cm / 2 s goal, not a
restriction on training.

## Research surface

You may modify the research training surface, including
`robot_learning/train.py` and the tunable configuration. Any training method is
fair game. Do not follow a prescribed list of techniques: use the evidence to
decide what to try.

Test one identifiable hypothesis per experiment. It may require multiple
coherent edits. Write `research/proposal.json`, make the corresponding
research-surface edits when needed, then exit. Use `"kind": "training"` for a
model or training-recipe experiment and `"kind": "method"` for a change to the
research method. Use `"kind": "calibration"` only for an unchanged A/A
measurement across the runner-owned training seeds. Do not launch training or the runner: `run_research.ps1`
verifies the protected files and executes the proposal after your process
exits.

At the start of each session, read `research/brief.md` and, when a previous
experiment exists, `research/last_train_summary.md`. Analyze that result before
choosing the next hypothesis. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, `run_research.ps1` runs the unchanged
control first; no LLM decision is needed.

Every proposal after the first result must include
`previous_experiment_postmortem` with the previous experiment number and four
short fields: `result`, `behavior`, `learned`, and `next_class`. The runner
records this memory and rejects an amnesiac proposal. Consult the compact
"hypotheses already tested" index before proposing a change.

## Selection method v3

During training, evaluate the policy after completed learning updates on 50
fixed development episodes. Rank checkpoints by success count, then—only for
failed episodes—longest consecutive in-circle hold, steps inside the best
100-step window, and cumulative distance outside the 1 cm boundary in that
window. Keep the top three checkpoints with their normalization and optimizer
state.

After 120,000 steps, run one tournament containing those three checkpoints and
the accepted champion. Evaluate every contender on the same 200 episodes for
three tournament seeds that are disjoint from development selection and the
fixed reported benchmark. Retain episode-level outcomes and compare each
candidate with the champion as a paired experiment: candidate-only successes,
champion-only successes, net wins, and an exact McNemar/sign-test probability.
Aggregate success and failed-episode progress remain descriptive ranking data.
Extend close or positive-but-uncertain decisions with more seeds.

Promote only a candidate with positive paired net wins, an exact p-value at or
below 0.05, and an improvement larger than the measured training-seed noise
floor. An exact tie or insufficient evidence keeps the incumbent. After model
selection, report the winner once on the untouched fixed benchmark seed; that
reported score never participates in selection. Archive the best candidate
from every completed experiment.

The runner owns compute fairness. Transfer experiments receive 120,000 steps.
A fresh initialization competing with an accumulated champion receives the
same cumulative training budget already invested in the accepted champion
lineage. An A/A calibration trains the unchanged champion recipe from the
same checkpoint with three independent training seeds, stores the resulting
success spread as the noise floor, and never promotes one of those replicates.
When the brief says the noise floor is not calibrated, the next proposal must
be this unchanged `"kind": "calibration"` experiment; ordinary training
proposals are rejected until it exists.

Training verdicts are `promoted`, `champion retained`, or `invalid`. Research
method verdicts are `method adopted` or `method rejected`. A method decision is
independent from whether the next trained model beats the champion.

The training summary labels its success rate as a stochastic 100-episode
rolling diagnostic and never reports a maximum snapshot as a meaningful peak.
Evaluation artifacts retain the target radius, target angle, hold progress, and
distance trace for each failed episode; use those diagnostics to explain where
the policy fails before changing another optimizer knob.

The tournament decides model promotion. Preserve negative results and archived
challengers. Never change the benchmark.
