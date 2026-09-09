# Research postmortems

## 3f02f914-505c-481f-b995-e040c009974f / Scientific strategy

**Direction:** Retain full-range target exposure as a plausible but unvalidated
recipe component, and shift the investigation toward seed and training
stability plus angular robustness. The fresh replication weakens a reproducible
radial-exposure claim; checkpoint selection and the training proxy are not
reliable explanations or selectors yet, and no causal mechanism has been
isolated.

**Lessons and limits:** Experiment 2's transfer run reached 197/200 (98.5%)
with 55/57 successes below 10 cm and 94/95 at 14-20 cm on
task-reference-v1. The experiment-3 fresh seed reached only 127/200 (63.5%),
131/200 (65.5%), and 133/200 (66.5%) at checkpoints 105472, 110592, and
120832, respectively. Their strata were 33/57, 35/57, and 35/57 below 10 cm;
30/48, 33/48, and 32/48 at 10-14 cm; and 64/95, 63/95, and 66/95 at 14-20
cm. Thus the replication did not reproduce either the near-target improvement
or far-target preservation expected by its proposal. Its failures covered
multiple radii and both angle signs, an unexpected broad deficit relative to
experiment 2's concentrated negative-angle failures. These are three
measurements from one fixed development panel: they inform seed/process
variability but are not independent held-out confirmation, official benchmark
evidence, or proof that the full-range recipe is intrinsically ineffective.
Twenty-one other experiment-3 checkpoints remain unmeasured, and the training
proxy stayed near zero, so neither the unmeasured checkpoints nor the proxy
supports a broader claim.

**Open questions:** Is the large fresh-seed deficit recoverable with another
seed or longer/stabler optimization, or does it expose a recipe interaction
that the transferred experiment-2 run masked? Can angular failure geometry and
checkpoint dynamics distinguish seed variance from a systematic control
limitation? A single fresh replication cannot attribute the discrepancy to
initialization, PPO stochasticity, checkpoint choice, or any one training
component.

**Conditional next steps:** Keep experiment-2 checkpoint-120832 as working and
best-known, and do not request official assessment from this replication. If
development continues, prioritize an unchanged full-range run with
task-reference checkpoint measurements and training diagnostics that can test
seed/process stability; alternatively test an angular-robustness intervention
only with paired task-success and failure-geometry evidence. Treat another
fresh run as useful only if it could change that distinction, and do not claim
radial causality from the fixed-panel results.

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
