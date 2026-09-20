# Research postmortems

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a useful reach-and-hold
policy. Task measurements support substantial progress, but the strongest
candidate's performance is geometry-sensitive: checkpoint-100352 scored
99.5% on the reused comparison panel and 97.0% on each of two disjoint
research panels. The measured evidence supports selecting checkpoint-100352
over the later endpoint, while not supporting terminal assessment yet.

**Lessons and limits:** Training success and reward are useful for locating
promising checkpoints but are not interchangeable with complete task success.
The reward peak at checkpoint-86016 (163.854, training success 0.42) measured
95.0%, whereas checkpoint-100352 reached 97.83% pooled success over 600
distinct research episodes. The first panel was reused for the initial
comparison and is selection-contaminated; the panels at seeds 10200 and 10400
provide disjoint episode coverage under the same research-evaluation
semantics. No task-reference or official benchmark measurement was made, so
the official 98% result remains unknown.

**Open questions:** The remaining failures are concentrated mainly at
negative target angles and include both failure to reach tolerance and
interrupted holds after reaching it. It remains unresolved whether a changed
training recipe can raise this geometry-sensitive behavior to the human
objective.

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
