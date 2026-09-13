# Research postmortems

## 2738e82e-bbbc-4913-9291-011003c48377 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior. The strongest measured checkpoint, `checkpoint-100352`, achieved
98.0% on the protected task-reference panel and 98.5% on the researcher panel.
The final checkpoint did not improve this: it tied the researcher-panel result
at 98.5% but fell to 97.0% on the same task-reference panel. The peak
checkpoint is therefore the best-supported candidate for the human objective,
while only the official benchmark can establish the campaign result.

**Lessons and limits:** Training reward and rollout success were useful for
locating a late-training candidate but were not interchangeable with measured
task success. The two measured checkpoints had identical three failures on the
research panel; on the fixed task-reference panel, the final checkpoint kept
the four peak failures and added two. The residual failures cluster on
negative-angle targets in both panels, but the panels use different episode
sets and evaluation contexts, so this is a behavioral characterization rather
than a causal explanation. The development panels provide strong but limited
evidence and are not the official 200-episode verdict.

**Open questions:** The official panel may differ from the development panels,
and the residual negative-angle behavior remains unexplained. Further training
or an intervention could target those failures, but this baseline's measured
candidate is ready for terminal assessment.

## 2738e82e-bbbc-4913-9291-011003c48377 / Experiment 1

**Result:** The fresh baseline produced a useful learned policy, with
`checkpoint-100352` selected as working and best known for official assessment.

**Observed behavior:** Training ran for 120,832 completed steps. The raw log
shows rollout success rising from 0 through the early and middle run to
0.97 at step 100,352, with a logged 0.98 at step 99,328, then fluctuating
between 0.93 and 0.96 through the endpoint. Research evaluation gave both
`checkpoint-100352` and `checkpoint-120832` 197/200 successes (98.5%) on the
same seed-9100 episode identities. Both had the same three failures: two never
reached tolerance and one reached it for only one held step. On the protected
task-reference-v1 panel, `checkpoint-100352` achieved 196/200 (98.0%), while
`checkpoint-120832` achieved 194/200 (97.0%); the endpoint added failures at
seeds 7421 and 7452 without recovering a peak failure. The four peak
task-reference failures were all negative-angle targets between -116.4 and
-127.9 degrees.

**Hypothesis assessment:** The baseline hypothesis, to establish an initial
policy for the human-defined objective, is **supported** as a useful
establishment result: measured task performance reached the objective level on
the development reference panel. It does not establish the official result,
and the endpoint regression means continued training was not supported as a
selection rule in this run. No intervention-specific causal claim is warranted
because this was a fresh baseline.

**Interpretation:** `checkpoint-100352` is preferred over the endpoint because
it is at least as strong on research evaluation and stronger on the unchanged
task-reference panel. The evidence justifies requesting the official benchmark
for this frozen candidate, not claiming that the development measurements are
the final verdict.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/training_logs/2738e82e-bbbc-4913-9291-011003c48377/experiment-1-attempt-1.log`;
`research/evaluations/2738e82e-bbbc-4913-9291-011003c48377/evaluation-2738e82e-bbbc-4913-9291-011003c48377-experiment-1-checkpoint-100352-200ep-seed9100-6ba3ba6d7654.json`;
`research/evaluations/2738e82e-bbbc-4913-9291-011003c48377/evaluation-2738e82e-bbbc-4913-9291-011003c48377-experiment-1-checkpoint-120832-200ep-seed9100-6ba3ba6d7654.json`;
`research/evaluations/2738e82e-bbbc-4913-9291-011003c48377/task-reference-2738e82e-bbbc-4913-9291-011003c48377-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/2738e82e-bbbc-4913-9291-011003c48377/task-reference-2738e82e-bbbc-4913-9291-011003c48377-experiment-1-checkpoint-120832-task-reference-v1.json`.
