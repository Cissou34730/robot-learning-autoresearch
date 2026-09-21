# Research postmortems

## 7624cdd2-25fb-489d-ab70-a31be819d2a1 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned the reach-and-hold
behavior and produced a strong measured policy. Checkpoint-100352 is the
current best-known lineage: it scored 199/200 (99.5%) on a disjoint
research-evaluation panel after scoring 196/200 on the reused task-reference
panel. This is strong development evidence of progress toward the human
objective, but it is not the official benchmark verdict.

**Lessons and limits:** Training proxies identify a sharp learning transition
and later fluctuation, but they are not task measurements. The three
task-reference results are comparable development measurements but are
selection-contaminated because the panel was reused. The disjoint result is
independent confirmation for checkpoint-100352 under the research evaluator,
not a replacement for the protected final assessment. The confirmed residual
failure was a hold-stability failure after briefly reaching tolerance.

**Open questions:** Whether one of the retained, later checkpoints improves on
checkpoint-100352 is unresolved because those candidates were not measured.
The official benchmark outcome for the selected lineage is also unresolved.

## 7624cdd2-25fb-489d-ab70-a31be819d2a1 / Experiment 1

**Result:** The fresh PPO baseline made substantial task progress. Closure
selects checkpoint-100352 as both working and best-known, keeps the unchanged
recipe, and retains plausible late-training alternatives.

**Observed behavior:** The training log reports zero training success through
70,656 steps, then a rise to 0.93 at 95,232 and a peak of 0.98 at 99,328;
training success fluctuated between 0.93 and 0.96 through the 120,832-step
endpoint. These are training proxies rather than task measurements. On the
reused task-reference-v1 panel, checkpoint-95232 achieved 192/200 (96%),
checkpoint-100352 achieved 196/200 (98%), and checkpoint-120832 achieved
194/200 (97%). On the disjoint research-evaluation panel with seeds
10000-10199, checkpoint-100352 achieved 199/200 (99.5%). Its one failure
briefly reached the target tolerance but held for only one step, had one hold
interruption, and truncated at 500 steps.

**Hypothesis assessment:** Supported for the baseline question of whether the
unchanged method can produce a useful learned policy: measured reach-and-hold
performance is high and the disjoint panel confirms the selected checkpoint's
behavior beyond the reused selection panel. This does not establish that the
policy satisfies the human objective on the official panel, and it does not
show that the baseline recipe is optimal or that later unmeasured checkpoints
are inferior.

**Interpretation:** Checkpoint-100352 is the best-supported working lineage
because it is the strongest of the measured task-reference candidates and the
only candidate with disjoint-panel confirmation. The single independent-panel
failure suggests a residual hold-stability issue, but one diagnostic failure
does not establish its frequency or cause. No causal claim is made about why
this checkpoint is better than the others.

**Evidence inspected:** `research/training_logs/7624cdd2-25fb-489d-ab70-a31be819d2a1/experiment-1-attempt-1.log`,
`research/query_training_log.py`,
`research/checkpoints/challengers/7624cdd2-25fb-489d-ab70-a31be819d2a1/experiment-1/inventory.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/task-reference-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-95232-task-reference-v1.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/task-reference-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/task-reference-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-120832-task-reference-v1.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/evaluation-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-100352-200ep-seed10000-f48545f83637.json`,
`research/results.jsonl`,
`research/research_state.json`.
