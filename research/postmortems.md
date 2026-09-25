# Research postmortems

## ce95d72f-a17e-402c-aa10-459f2b8ccecf / Scientific strategy

**Current synthesis:** The baseline has learned a strong but not yet officially
validated reach-and-hold policy. `checkpoint-100352` is currently the best
measured candidate: it achieved 196/200 successes on the disjoint research
panel and 347/360 across the two distinct research panels. The result is
consistent with the frozen physical model in which approach, tolerance entry,
settling, and uninterrupted hold form one coupled behavior; a tolerance entry
alone is not sufficient.

**Lessons and limits:** The training proxy and reward are useful for locating
the transition to competent behavior but do not rank complete task behavior:
the reward peak at checkpoint-86016 was weaker than the later checkpoints, and
the proxy peak at checkpoint-100352 was followed by lower measured performance
at checkpoint-120832. On the disjoint panel, the selected checkpoint had one
failure without recorded tolerance entry and three failures after entry with
hold interruption. These stage labels describe observations, not causes. The
fixed task-reference panel also returned 98% for this checkpoint, but it is
permanently reused and is not independent confirmation. Development evidence
therefore supports terminal assessment readiness but does not establish the
official objective.

**Open questions:** The remaining failures do not distinguish whether the
limiting dynamics arise from approach geometry, branch choice from the
singular initial posture, torque timing, settling transients, or their
interaction during the hold. It is also unresolved how stable the observed
angle- and radius-specific pattern is under other target draws; the current
panels are insufficient to make those behavioral distinctions causal.

## ce95d72f-a17e-402c-aa10-459f2b8ccecf / Experiment 1

**Result:** The baseline produced a useful saved policy. `checkpoint-100352`
is selected as both working lineage and best known, with the scientific recipe
kept unchanged, and the official benchmark is requested.

**Observed behavior:** Training proxy success rose to 0.97 at checkpoint-100352
and declined to 0.95 at checkpoint-120832; the earlier reward maximum at
checkpoint-86016 did not identify the strongest complete behavior. On the
first research panel, checkpoints 100352 and 120832 each achieved 151/160.
On the disjoint panel they achieved 196/200 and 194/200 respectively, while
checkpoint-86016 achieved 192/200. The selected checkpoint therefore pooled
347/360 successes across the two distinct research panels. Its four disjoint
panel failures comprised one episode without tolerance entry and three
episodes that entered tolerance but later interrupted the hold. The fixed
task-reference panel measured it at 196/200, but that panel is reused.

**Hypothesis assessment:** Partially supported. The baseline prediction that
the late training-proxy peak would identify a strong complete reach-and-hold
policy is supported by the selected checkpoint's leading disjoint-panel
result and by its transfer to the protected task reference. It is weakened by
the non-monotonic relationship between proxy or reward metrics and measured
success, by the remaining coupled reach/settling/hold failures, and by the
fact that development measurements cannot establish the official result.

**Interpretation:** The selected policy is the best available evidence-backed
lineage for the human task, but the 98% development result is a readiness
signal rather than a declared objective achievement. The independent panel
reduces concern that the selection is only panel-specific, while the small
number of failures leaves their physical mechanism unresolved. No alternative
checkpoint has comparable evidence for a better designation, so retaining
additional candidates is not justified for this closure.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/ce95d72f-a17e-402c-aa10-459f2b8ccecf/experiment-1/inventory.json`;
`research/evaluations/ce95d72f-a17e-402c-aa10-459f2b8ccecf/evaluation-ce95d72f-a17e-402c-aa10-459f2b8ccecf-experiment-1-checkpoint-86016-200ep-seed5200-48e4acc98c39.json`;
`research/evaluations/ce95d72f-a17e-402c-aa10-459f2b8ccecf/evaluation-ce95d72f-a17e-402c-aa10-459f2b8ccecf-experiment-1-checkpoint-100352-200ep-seed5200-48e4acc98c39.json`;
`research/evaluations/ce95d72f-a17e-402c-aa10-459f2b8ccecf/evaluation-ce95d72f-a17e-402c-aa10-459f2b8ccecf-experiment-1-checkpoint-120832-200ep-seed5200-48e4acc98c39.json`;
the corresponding 160-episode seed-4200 research artifacts; and the three
`task-reference-v1` artifacts for checkpoints 86016, 100352, and 120832.
