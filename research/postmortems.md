# Research postmortems

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Scientific strategy

**Current synthesis:** The campaign objective is a policy with at least 98%
success on the fixed 200-episode official assessment, meaning at least 196
complete reach-and-hold episodes. Measured development success rose from 61.5%
for the fresh baseline to 85.0% after uniform-radius training, 89.0% after the
first unchanged continuation, and 94.0% after the second. The strongest
measured policy remains the experiment 4 endpoint at 188/200; experiment 5
measured 187/200, 187/200, and 188/200. Thus the current policy is eight
development-panel episodes below the objective equivalent, and this panel is
not the official assessment.

**Lessons and limits:** Uniform 0.06-0.20 m training-radius sampling coincided
with the largest early gain and reduced no-reach failures, but the single
transferred comparison does not isolate distribution causality. Later unchanged
transfer remained useful through experiment 4 and then produced no measured
gain in experiment 5. At the experiment 5 endpoint, one failure was an
acquisition failure and eleven reached tolerance without completing the
uninterrupted 100-step hold; most of those hold failures left tolerance after
only 1-6 held steps, with a few lasting 77-98 steps. Training proxies are not
reliable selection criteria: experiment 5 reached a proxy of 1.00 before
fluctuating to 0.97 while task-reference success stayed at 93.5-94.0%. The
retained policy and unchanged recipe share PPO, tanh [64, 64], the existing
observation/action mapping, normalization contract, and uniform-radius
distribution, which supports transfer only for that unchanged representation
and task semantics. These observations do not establish a hard plateau, a
single causal mechanism, or readiness for the official verdict.

**Open questions:** It remains unresolved whether the residual hold failures
reflect insufficient state representation, control behavior, or optimization,
and whether a changed method has useful headroom beyond the 94.0% policy. It is
also unknown whether explicit end-effector motion information can improve
stability without sacrificing acquisition across the official geometry range.
The relative contributions of radius sampling and transfer dynamics remain
uncertain because there is no radius-only control. Experiment 3's
task-reference records lack the diagnostic fields used by the earlier
research-evaluation artifacts, and development-panel evidence remains distinct
from the official final verdict.

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Experiment 1

**Result:** The fresh PPO baseline produced meaningful but incomplete progress.
`checkpoint-120832` reached 61.5% (123/200) on the task-reference development
panel, up from 49.5% (99/200) for `checkpoint-115712`; neither is close to the
98% objective.

**Observed behavior:** The training log starts with zero reported success and
`ep_rew_mean` -421 at 1024 steps, then rises to `success_rate` 0.89 and
`ep_rew_mean` 169.5 at 120832 steps. The task-reference measurements used the
same 200 episode identities: the endpoint changed 44 failures to successes and
20 successes to failures, for a net gain of 24 episodes (12 percentage
points). All 77 endpoint failures truncated at 500 steps. Research diagnostics
classify 55 as never reaching tolerance and 22 as reaching tolerance without
completing the hold; the latter had maximum held time below 100 steps, with a
maximum of 99. Endpoint success was 32/57 near-radius versus 91/143
far-radius, and 46/95 front-half versus 77/105 back-half.

**Hypothesis assessment:** Partially supported. The baseline established that
the unchanged method can learn the task and that its late training improvement
corresponds to a 12-point gain in measured task success. It did not establish a
policy satisfying the human objective. The 0.89 training proxy versus 0.615
protected-task success is an important discrepancy; code inspection confirms
that training uses a radius-band curriculum while research evaluation uses the
official uniform radius range. This observation guides the next investigation
but does not by itself show that the distribution difference caused the gap.

**Interpretation:** `checkpoint-120832` is the best available measured policy
and is useful as the working and best-known lineage for further development.
The strongest direct residual signal is acquisition failure rather than a
general inability to hold after reaching, although the 22 incomplete holds
remain relevant. The measured policy is not ready for terminal assessment, and
the earlier checkpoint is not retained because it is strictly weaker on the
shared task panel without a distinct measured advantage.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/experiment-1/inventory.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-1-checkpoint-115712-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-1-checkpoint-115712-200ep-seed7300-17df57dc1c67.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-1-checkpoint-120832-200ep-seed7300-17df57dc1c67.json`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Experiment 2

**Result:** The transferred policy trained with uniform 6-20 cm target-radius
sampling reached 85.0% (170/200) on the task-reference development panel. This
is a substantial improvement over the experiment 1 endpoint at 61.5% and over
the experiment 2 proxy-peak checkpoint at 72.0%, but it does not satisfy the
98% objective.

**Observed behavior:** The training log was non-monotonic: `success_rate`
reached 1.0 and `ep_rew_mean` reached 194.17 at 50176 steps, then the endpoint
recorded `success_rate` 0.96 and `ep_rew_mean` 187.0. On the same 200 episode
identities, the experiment 2 endpoint changed 65 experiment 1 failures into
successes and 18 successes into failures, for a net gain of 47 episodes. Its
30 failures comprised 12 no-reach failures and 18 reached-but-incomplete-hold
failures, versus 55 and 22 for experiment 1. Success increased from 56.1% to
87.7% near radius and from 48.4% to 83.2% on the front half; it was 83.9% far
radius and 86.7% back half. The proxy-peak checkpoint was weaker at 72.0%
despite its higher training proxy. All measurements are development-panel
evidence, not the official assessment.

**Hypothesis assessment:** Partially supported. The expected improvement in
task-reference success occurred, and the previously weak near-radius geometry
improved while no-reach failures fell from 55 to 12. Reached-but-incomplete-hold
failures did not increase in count, so the measured intervention did not trade
away complete holds on this panel. However, the result comes from one
transferred training run without a control that changes only the radius
distribution; it supports the usefulness of the tested recipe, not a
distribution-only causal claim. The remaining 15% failure rate also leaves the
human objective unresolved.

**Interpretation:** The experiment 2 endpoint is the most useful available
policy and should become both working and best-known for continued development.
The discrepancy between its lower late training proxy and higher task success
shows that training metrics are not a sufficient policy-selection criterion
under this task-distribution change. The evidence favors further work on the
residual failures rather than terminal assessment, while retaining the uniform
radius recipe.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/experiment-2/inventory.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-2-checkpoint-50176-200ep-seed7300-c5b54f36dc64.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-2-checkpoint-120832-200ep-seed7300-c5b54f36dc64.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-2-checkpoint-50176-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-2-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-1-checkpoint-120832-200ep-seed7300-17df57dc1c67.json`;
`research/scenario.md`; `robot_learning/scenario/environment.py`.

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Experiment 3

**Result:** Continuing the unchanged uniform-radius PPO recipe from the
experiment 2 endpoint produced the strongest measured policy in the campaign:
178/200 successes (89.0%) at checkpoint-120832 on the task-reference
development panel. This is an 8-episode net improvement over the parent at
170/200, but it remains 18 successes short of the 196/200 development-panel
equivalent of the objective.

**Observed behavior:** The training log reached a proxy success rate of 1.00
from 29,696 through 40,960 steps, with `ep_rew_mean` peaking at 195.21 at
40,960. The proxy then declined and fluctuated, reaching 0.94 at 115,712 and
0.95 with `ep_rew_mean` 183.34 at the 120,832-step endpoint. Protected
task-reference success was 177/200 (88.5%) at 40,960, fell to 160/200 (80.0%)
at 95,232 after a proxy rebound, and recovered to 178/200 (89.0%) at 120,832.
On the shared panel, the endpoint changed 21 parent failures into successes and
13 parent successes into failures. The endpoint had 83/92 near-radius
successes, 95/108 far-radius successes, 90/95 front-half successes, and 88/105
back-half successes. All 22 endpoint failures were truncated at 500 steps in
the task-reference artifact; that artifact does not identify whether each
failure missed acquisition or failed the complete hold.

**Hypothesis assessment:** Partially supported. The expected later checkpoint
improvement occurred: the endpoint exceeded the parent by 4 percentage points
on the same development panel and was slightly above the measured 40,960
checkpoint. However, the 95,232 checkpoint was substantially worse, and the
endpoint remained below the objective, so continued unchanged optimization did
not produce monotonic or sufficient progress. The measurements support the
usefulness of this continuation under the tested recipe, but they do not
establish why the endpoint improved or whether further continuation would do
so.

**Interpretation:** The experiment 3 endpoint is the best available measured
policy and should replace the parent as both working and best-known for further
development. The endpoint's measured gain is task evidence, while the
non-monotonic training proxies are an orthogonal warning against selecting
checkpoints by training metrics alone. The task-reference panel does not
provide enough diagnostic detail to attribute the remaining failures to
acquisition or hold robustness. The unchanged scientific recipe should be
kept; terminal assessment is not justified because the development result is
89.0% and is not the official final verdict.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/experiment-3/inventory.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-3-checkpoint-40960-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-3-checkpoint-95232-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-3-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-2-checkpoint-120832-task-reference-v1.json`;
`research/results.jsonl`; `research/scenario.md`.

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Experiment 4

**Result:** Continuing the unchanged uniform-radius PPO recipe improved the
measured policy to 188/200 successes (94.0%) on task-reference-v1, up from the
experiment 3 endpoint's 178/200 (89.0%), but it did not reach the 98% objective
or justify terminal assessment.

**Observed behavior:** The training proxy reached 1.00 from 29,696 through
40,960 steps, with the highest listed reward of 194.48 at 35,840 steps. That
proxy-peak checkpoint measured 178/200 (89.0%) on task-reference-v1. At 120,832
steps, the proxy was 0.96 with reward 186.89, but task-reference success was
188/200 (94.0%). The endpoint's research evaluation likewise measured 94.0%;
of its 12 failures, 2 never entered tolerance and 10 entered tolerance but did
not complete a continuous 100-step hold. The task-reference endpoint had 86/92
near-radius successes, 102/108 far-radius successes, 89/95 front-half
successes, and 99/105 back-half successes; all 12 failures truncated at 500
steps.

**Hypothesis assessment:** Partially supported. The expected later checkpoint
exceeding 178/200 occurred, providing measured task evidence that this
continuation was useful under the tested recipe. The result is still 8
episodes short of the 196/200 development-panel equivalent of the objective,
and the non-monotonic proxy remained a poor selection signal. The endpoint
diagnostics identify hold completion as the larger residual failure category,
but they do not establish why continued optimization improved task success or
whether further continuation will improve it.

**Interpretation:** The endpoint is the strongest measured policy in the current
campaign and is suitable as the working and best-known lineage for further
development. Keeping the unchanged scientific recipe is appropriate for this
closure because the measured continuation improved task performance and no
code change was made. The endpoint is not ready for terminal assessment:
94.0% is development-panel evidence, not the official benchmark, and the
remaining hold failures leave a material gap to the human objective.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/experiment-4/inventory.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-4-checkpoint-35840-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-4-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-4-checkpoint-120832-200ep-seed7300-c5b54f36dc64.json`;
`research/results.jsonl`; `research/scenario.md`;
`robot_learning/scenario/evaluation.py`.

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Experiment 5

**Result:** The unchanged continuation did not improve the measured policy.
Task-reference-v1 success was 187/200 (93.5%) at checkpoints 35,840 and
105,472, and 188/200 (94.0%) at checkpoint 120,832. The experiment 4 working
policy also measured 188/200, so experiment 5 did not close the eight-episode
gap to the development-panel equivalent of the objective.

**Observed behavior:** The experiment 5 training log reported proxy
`success_rate` 1.00 from 27,648 through 39,936 steps, then fluctuated between
0.94 and 0.99, including 0.95 around 109,568-115,712 steps, before ending at
0.97 with `ep_rew_mean` 188.10 at 120,832 steps. The three protected
task-reference measurements were 187/200, 187/200, and 188/200; all failures
ran to the 500-step limit. The endpoint research evaluation identified 1
acquisition failure and 11 failures that reached tolerance but did not complete
the uninterrupted 100-step hold. Against the experiment 4 endpoint under the
same research-evaluation semantics, both policies had 188 successes, with six
episode outcomes changing in each direction; the experiment 4 endpoint had 10
incomplete holds and 2 acquisition failures versus 11 and 1 for experiment 5.
The other 21 experiment 5 checkpoints were not measured and are not treated as
failures.

**Hypothesis assessment:** Weakened. The expected observation, a later
checkpoint exceeding 188/200, did not occur in any of the three measured
checkpoints. This supports a plateau interpretation for this single unchanged
continuation under the tested measurement scope, while the endpoint tie and
limited sampling do not establish that all further optimization or other
methods will fail.

**Interpretation:** Experiment 5 provides no measured task-performance reason
to replace the experiment 4 working and best-known policy. The unchanged
scientific recipe remains internally consistent, but this continuation is not
evidence of additional headroom and the residual hold failures remain
material. The 94.0% development result is not the official benchmark and is
not sufficient to request terminal assessment, so closure keeps the existing
working and best-known lineage and leaves further development as a later
experiment decision.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/experiment-5/inventory.json`;
`research/training_logs/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/experiment-5-attempt-1.log`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-5-checkpoint-35840-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-5-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/task-reference-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-5-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-5-checkpoint-120832-200ep-seed7300-c5b54f36dc64.json`;
`research/evaluations/cc96dcb7-74bb-41d4-8c53-0f9afd26aa75/evaluation-cc96dcb7-74bb-41d4-8c53-0f9afd26aa75-experiment-4-checkpoint-120832-200ep-seed7300-c5b54f36dc64.json`;
`research/results.jsonl`; `research/scenario.md`.
