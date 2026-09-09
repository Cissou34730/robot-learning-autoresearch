# Research postmortems

## 3f02f914-505c-481f-b995-e040c009974f / Scientific strategy

**Direction:** Retain full-range target exposure as a plausible but
unvalidated recipe component, but shift from asking whether one fresh seed was
an unstable draw to testing recurring angular/control failures and training
stability. Two fresh seeds now weaken the claim that the experiment-2 result is
reliably produced by the unchanged full-range recipe. Checkpoint selection and
the training proxy remain unreliable selectors, and no causal mechanism has
been isolated.

**Lessons and limits:** Experiment 2's transfer run reached 197/200 (98.5%)
with 55/57 successes below 10 cm and 94/95 at 14-20 cm on
task-reference-v1. Experiment 3's fresh seed reached 127/200, 131/200, and
133/200 at checkpoints 105472, 110592, and 120832; experiment 4's fresh seed
reached 128/200, 127/200, and 127/200 at the same checkpoints. Experiment
4's strata were 38/57 below 10 cm, 32/48, 33/48, and 32/48 at 10-14 cm, and
58/95, 56/95, and 57/95 at 14-20 cm. The expected experiment-4 observation
(at least 196/200, at least 55/57 near-target successes, and at least 94/95
far-target successes at a late checkpoint) therefore did not occur; the
contradicting observation occurred at all three measured checkpoints.

The factual failure sets overlap substantially across the two fresh seeds:
61 failed episode identities are shared at checkpoint-120832, while the
angle-sign balance differs (experiment 3: 36 negative-angle and 31
nonnegative-angle failures; experiment 4: 30 and 43). Failures therefore recur
across radii and angle signs, but these are repeated measurements of one fixed
development panel, not independent held-out confirmation or official benchmark
evidence. The second fresh run makes seed variance alone a less adequate
explanation, but cannot distinguish initialization, PPO trajectory, reward
interaction, representation, or control limitations. Twenty-one checkpoints in
each fresh run remain unmeasured and are not failed policies.

Experiment 4's training proxy rose from 0 to 0.26 and its training reward
peaked before the final checkpoint, yet task-reference success stayed between
63.5% and 64.0%. This is a partial learning signal in the training process,
not measured policy progress, and provides no reliable checkpoint selector.

**Open questions:** Do the recurring fixed-panel failures reflect an angular
or control/representation limitation that survives seed changes, or a
training-recipe interaction that the successful transferred policy happened
to avoid? Can an intervention improve both task success and the shared failure
geometry without sacrificing the far-radius behavior? What training
diagnostic would separate optimization instability from a systematic
control limitation? The current evidence does not support causal attribution
to full-range exposure, fresh initialization, or any single PPO component.

**Conditional next steps:** Keep experiment-2 checkpoint-120832 as working and
best-known, and do not request official assessment from either fresh
replication. If development continues, prioritize an angular-robustness or
representation/control intervention, evaluated with paired task success and
failure-geometry evidence. An unchanged fresh run is lower value unless it
adds diagnostics capable of changing the seed-versus-mechanism decision.
Do not claim radial causality from the repeated fixed-panel measurements.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 1

**Result:** The baseline reached the development threshold at checkpoints
100352 and 110592, but the final checkpoint regressed below it; checkpoint
100352 is selected as the working and best-known policy.

**Observed behavior:** The automatic baseline trained 120,832 steps. The
task-reference-v1 panel used 200 deterministic episodes with seed 7300:
checkpoint-100352 and checkpoint-110592 each achieved 98.0% (196/200), and
checkpoint-120832 achieved 97.0% (194/200). Checkpoints 100352 and 110592
failed on the same episodes (0, 10, 84, 102); each failure truncated at 500
steps. The final checkpoint retained those four failures and added episodes
121 and 152. The shared failures had target radii 6.7, 7.2, 9.9, and 9.4 cm
and angles from -128 to -116 degrees. The training log's proxy success rose
from 0 through 70,656 steps to 0.97 at 100,352, then varied between 0.93 and
0.96 through the end; these are training measurements, not task-reference
results.

**Hypothesis assessment:** The baseline proposal snapshot supplied no
intervention-specific `expected_observation` or `contradicting_observation`;
the relevant baseline expectation was to establish an initial measured policy
for the human-defined objective. That expectation is **partially supported**:
two intermediate checkpoints met 98% on the fixed development panel, but the
final checkpoint did not, and no checkpoint has official benchmark status.
The result is therefore insufficient to claim stable attainment of the 98%
campaign objective or to attribute the outcome to any scientific mechanism.

**Interpretation:** The best measured task behavior occurs before the final
training checkpoint, so selecting by training proxy and continuing unchanged
is not justified by this run. The concentration of failures below 10 cm is
consistent with the training environment's 14-20 cm radial range, making
full-range target exposure a useful next hypothesis. This is an interpretation
of one baseline and one repeated development panel, not a causal conclusion.

**Evidence inspected:** `research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-1-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-1/inventory.json`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 2

**Result:** Full-range target-radius training partially supported the
intervention hypothesis. The final checkpoint reached 197/200 (98.5%) on the
fixed development panel and is selected as the working and best-known policy.

**Observed behavior:** The transferred parent reached 196/200 (98%). The
experiment-2 checkpoint at 105472 steps also reached 196/200, with 54/57
under-10-cm successes and 94/95 at 14-20 cm. The final checkpoint at 120832
steps reached 197/200, with 55/57 under-10-cm successes, 48/48 at 10-14 cm,
and 94/95 at 14-20 cm. It changed the parent outcomes on three episodes: it
fixed parent failures at 6.7 cm/-116.4 degrees and 7.2 cm/-125.4 degrees,
left the 9.9 cm/-122.9 degrees and 9.4 cm/-127.9 degrees failures unchanged,
and changed a successful 18.2 cm/-154.8 degrees episode to failure. All
failures truncated at 500 steps. The training proxy peaked at 1.0 at 105472
steps and ended at 0.94; this is not task-reference performance.

**Hypothesis assessment:** The hypothesis is **partially supported**. The
expected reduction in the shared near-target failures occurred and the final
panel score improved by one episode, while 10-14 cm performance was preserved.
However, the final checkpoint did not eliminate the near-target geometry and
introduced a far-target failure, reducing 14-20 cm performance by one episode.
The result supports retaining full-range exposure as a useful intervention
under this panel, but does not establish that radius alone caused the change or
that the 98.5% result generalizes.

**Interpretation:** Exposure to 6-14 cm targets plausibly addressed part of the
baseline's radial gap because two of four shared near-target failures were
repaired. The persistent negative-angle failures and the new far-target
failure mean angular control, PPO drift, and checkpoint selection remain viable
explanations. The selected checkpoint is better measured task behavior than the
parent on this panel, not official attainment of the campaign objective.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-2-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-2/inventory.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-working-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 3

**Result:** The fresh replication contradicted its reproducibility hypothesis.
None of the three measured checkpoints approached the experiment-2 task
behavior, so the experiment-2 working and best-known lineage is preserved.

**Observed behavior:** The seed-1 full-range run completed 120832 training
steps. On the same 200-episode task-reference-v1 panel, checkpoint-105472
achieved 127/200 (63.5%), checkpoint-110592 achieved 131/200 (65.5%), and
checkpoint-120832 achieved 133/200 (66.5%). Below 10 cm the checkpoints
achieved 33/57, 35/57, and 35/57; at 10-14 cm they achieved 30/48, 33/48,
and 32/48; at 14-20 cm they achieved 64/95, 63/95, and 66/95. The measured
failures span near, middle, and far radii and include positive and negative
angles. The training proxy was 0.01 at its best reported point and at the
end. Three checkpoints were measured and 21 remained unmeasured; an
unmeasured checkpoint is not treated as a failed policy.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was at least 55/57 below 10 cm while
preserving 95/95 at 14-20 cm, with a similar qualitative failure pattern.
The observed checkpoints instead reached 33-35/57 and 63-66/95, with a broad
failure pattern. This establishes that the experiment-2 behavior was not
reproduced by this fresh seed at the measured checkpoints. It does not
establish whether seed variance, optimization trajectory, checkpoint timing,
or another coupled factor caused the discrepancy.

**Interpretation:** The replication weakens the claim that full-range target
exposure reliably produces the experiment-2 improvement and makes process
stability a higher-value question. The modest increase from 63.5% to 66.5%
across the measured checkpoints is an unexpected partial learning signal, but
it remains far below the parent result and cannot support policy progress
relative to the selected working lineage. Because the run was a fresh
initialization and only one seed, the evidence is diagnostic of
non-reproducibility in these tested conditions, not a causal comparison of
initialization or a refutation of the recipe in general.

**Evidence inspected:** `research/research_state.json`;
`research/brief.md`; `research/results.jsonl`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-3-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-3-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-3-checkpoint-120832-task-reference-v1.json`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 4

**Result:** The second fresh replication contradicted its reproducibility
hypothesis, so the experiment-2 working and best-known lineage is preserved.

**Observed behavior:** Seed 2 completed 120832 training steps. On the same
200-episode task-reference-v1 panel, checkpoints 105472, 110592, and 120832
achieved 128/200 (64.0%), 127/200 (63.5%), and 127/200 (63.5%). Their
near/middle/far strata were 38/57, 32/48, 58/95; 38/57, 33/48, 56/95; and
38/57, 32/48, 57/95. The measured failures covered multiple radii and both
angle signs. At checkpoint-120832, 61 failed episode identities were shared
with experiment 3's checkpoint-120832 measurement. The training proxy was
0.22, 0.24, and 0.26 at the measured checkpoints and 0.26 at the end; these
are training measurements, not task-reference results.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was a late checkpoint near 196/200 with
at least 55/57 near-target and 94/95 far-target successes, which would have
supported treating experiment 3 as an unstable draw. Instead, all three
measured checkpoints remained near 63.5-64.0%, with 38/57 near-target and
56-58/95 far-target successes. This strengthens the conclusion that the
experiment-2 behavior was not reproduced by either tested fresh seed. It does
not prove that full-range exposure is ineffective or identify whether seed,
optimization, reward interaction, representation, or control caused the gap.

**Interpretation:** The repeated broad deficit and substantial overlap in
failed fixed-panel episodes make a purely one-off seed explanation less
plausible, while the differing angle-sign balance prevents a simple claim of
one fixed angular failure mode. The small checkpoint movement and the rise in
the training proxy are unexpected partial process signals, but they do not
constitute policy progress relative to the 98.5% working lineage. The evidence
supports changing the next scientific question toward angular/control
robustness and diagnostic separation, not selecting or retaining a fresh
candidate.

**Evidence inspected:** `research/research_state.json`;
`research/brief.md`; `research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-4-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-4/inventory.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-4/parameters.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-4-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-4-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-4-checkpoint-120832-task-reference-v1.json`.
