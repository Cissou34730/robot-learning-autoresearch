# Research postmortems

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 6-20 cm, full-angle reach-and-hold task. The unchanged PPO baseline
learned a useful policy, and checkpoint-100352 is the best-supported current
lineage: it reached 587/600 pooled success, including 97.0% on each of two
disjoint research panels. The evidence therefore supports substantial progress
but leaves the official objective unresolved.

**Lessons and limits:** Training success and reward locate promising checkpoints
but are not interchangeable with complete task success. Checkpoint-86016 had
the observed reward peak and measured 95.0%, while checkpoint-100352 measured
97.83% pooled; the later endpoint was also weaker than checkpoint-100352 on the
available comparison. The current training distribution samples only 14-20 cm,
whereas the official task samples 6-20 cm. In the inspected checkpoint-100352
panels, all 13 failures were at negative angles; five never reached tolerance
and eight reached it only briefly. The first panel was reused and
selection-contaminated, while seeds 10200 and 10400 provide disjoint coverage.
No task-reference or official benchmark measurement exists, so the official
98% result remains unknown. These observations do not establish that radial
coverage causes the geometry failures.

**Open questions:** It is unresolved whether exposure to the full official
radial range improves the negative-angle reach-and-hold failures without
reducing performance at already learned outer radii. It is also unresolved
whether the interrupted holds reflect a training-distribution limitation,
angle-dependent control, or a reward/holding limitation. The official result
for the current best-known policy remains unmeasured.

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Experiment 1

**Result:** The fresh baseline produced a useful candidate. Checkpoint-100352
is selected as both the working and best-known lineage; the unchanged
scientific recipe is kept, and terminal assessment is deferred.

**Observed behavior:** Training success was 0 through 70,656 steps, rose to
0.42 at step 86,016, 0.93 at step 95,232, and 0.97 at step 100,352. The
highest training reward was 163.854 at step 86,016, then reward declined to
117.320 at step 100,352 and 112.017 at the 120,832-step endpoint. On the
first 200-episode research panel, checkpoint-100352 achieved 199/200
(99.5%), checkpoint-120832 achieved 197/200 (98.5%), and checkpoint-86016
achieved 190/200 (95.0%). On disjoint panels, checkpoint-100352 achieved
194/200 (97.0%) at seed 10200 and 194/200 (97.0%) at seed 10400, for
587/600 (97.83%) pooled. Checkpoint-120832 achieved 193/200 (96.5%) on the
seed-10400 panel, for 390/400 (97.5%) pooled. The paired comparison on the
shared disjoint panel favored checkpoint-100352 by 3 to 0 discordant wins.
The leader's disjoint failures were mostly at negative angles, including
targets around -116 to -152 degrees and radii from about 6.9 to 19.3 cm;
some reached tolerance only briefly while others never reached it. One
endpoint failure accumulated 287 in-tolerance steps but only 89 consecutive
held steps, showing that substantial partial behavior can still fail the
uninterrupted two-second criterion.

**Hypothesis assessment:** Partially supported. The baseline question was
whether late training-time success and reward signals would transfer to
complete reach-and-hold success and identify a working checkpoint. High
training success did transfer to high measured task success, and
checkpoint-100352 was better supported than the endpoint and the reward-peak
checkpoint. The result is not a complete transfer to the human objective:
the leader fell from 99.5% on the reused panel to 97.0% on each disjoint
panel, and no measurement was an official benchmark. The reward peak did not
predict the best measured policy. These conclusions are limited to this
recipe, its saved checkpoints, and the research-evaluation panels; they do
not establish a causal explanation for the geometry failures.

**Interpretation:** Checkpoint-100352 is the most useful current policy and
should anchor the next scientific intervention, but the independent
97.0% panels make terminal assessment premature. The evidence supports
closure of this baseline and further development, not rejection of the
learned policy.

**Evidence inspected:** `research/results.jsonl`;
`research/checkpoints/challengers/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-1/inventory.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-100352-200ep-seed10000-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-100352-200ep-seed10200-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-100352-200ep-seed10400-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-120832-200ep-seed10000-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-120832-200ep-seed10400-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-86016-200ep-seed10000-543af51fd137.json`.

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Experiment 2

**Result:** Expanding the training radius range to 6-20 cm did not improve
measured reach-and-hold success on the matched disjoint panel. The retained
baseline remains the working and best-known lineage; the experiment recipe is
reverted and terminal assessment remains deferred.

**Observed behavior:** The changed recipe reached training success 0.99 at
100352 steps and 1.0 at 105472 steps, but those training proxies measured
192/200 successes (96.0%) at both checkpoints on episodes 10600-10799. The
retained baseline measured 193/200 (96.5%) on the same panel. Paired
comparisons recorded no discordant wins for either changed checkpoint against
the baseline, with one baseline win; the two changed checkpoints had no
discordant wins against each other. The changed checkpoint-100352 and
checkpoint-105472 failures were the baseline's seven failures plus episode 42,
whereas the baseline failed on episodes 75, 140, 165, 185, 196, 197, and 199.
Training reward was an orthogonal proxy: it was 121.367 at 10240 steps and
110.176 at 105472 steps, while the measured task success stayed at 96.0% for
both measured changed checkpoints. The research-evaluation artifacts report
success, reward, steps, termination and truncation, but not target geometry or
held-step diagnostics for this round.

**Hypothesis assessment:** Weakened. The confirmatory prediction that broader
radial coverage would reduce the observed failure pattern without sacrificing
performance was not observed on the matched disjoint panel: the changed
policies were slightly worse in aggregate and added a failure while retaining
the baseline failures. This is evidence against this intervention under the
tested transferred run and panel, not proof that radial coverage can never
help; because target geometry and hold subdiagnostics were not emitted here,
the result cannot distinguish radial effects from angle-dependent control or
hold dynamics.

**Interpretation:** The saved baseline policy remains useful progress toward the
98% official objective, but this intervention does not provide a stronger
candidate or evidence that the negative-angle and interrupted-hold failures
were caused by the 14-20 cm training-radius restriction. The matched control
and disjoint episode coverage are directly comparable for this decision, while
the measured 96.0%/96.5% values are development evidence rather than an
official verdict. Reverting the changed training distribution preserves the
best-supported policy and leaves further training as a separate future
experiment.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/checkpoints/challengers/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-2/inventory.json`;
`research/training_logs/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-2-attempt-1.log`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-2-checkpoint-100352-200ep-seed10600-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-2-checkpoint-105472-200ep-seed10600-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-2-working-200ep-seed10600-543af51fd137.json`;
`robot_learning/scenario/training_environment.py`.
