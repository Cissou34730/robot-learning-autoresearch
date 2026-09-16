# Research postmortems

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Scientific strategy

**Current synthesis:** The campaign objective is a policy with at least 98%
success on the fixed 200-episode official assessment. The best measured policy
is now the experiment 3 continuation endpoint, at 89.0% (178/200) on the shared
development panel, improving by 8 episodes over the experiment 2 parent. The
continuation is useful progress but remains below the objective and is not ready
for terminal assessment.

**Lessons and limits:** The unchanged baseline learned the task, while the
uniform 0.06-0.20 m training-radius recipe coincided with improvement from
61.5% to 85.0% on the shared task-reference panel. At the experiment 2
endpoint, 12 of 30 failures never entered tolerance and 18 entered but did not
complete the 100-step hold; near-radius success was 87.7%, far-radius success
83.9%, front-half success 83.2%, and back-half success 86.7%. Training proxies
were non-monotonic: the proxy peak at 50,176 steps measured only 72.0%, whereas
the 120,832-step endpoint measured 85.0%. Thus task measurements, not proxy
peaks, govern policy selection. The evidence is from one transferred run
without a radius-only control, so it supports the usefulness of the tested
recipe but does not establish that radius sampling alone caused the gain.
Experiment 3 likewise shows that a training proxy peak is not an acceptance
criterion: the checkpoint at its 40,960-step proxy peak measured 88.5%, the
95,232-step proxy rebound measured 80.0%, and the lower-proxy endpoint measured
89.0%. The
task-reference artifacts report all failures as truncated at 500 steps but do
not distinguish acquisition failures from incomplete holds, so the residual
failure mechanism is unresolved.

**Open questions:** It is unresolved whether continued optimization of the
experiment 3 policy can reduce the remaining acquisition and hold failures, or
whether the endpoint has plateaued. The relative contributions of radius
sampling, transfer dynamics, and representation or control limitations remain
uncertain. Development-panel evidence is not the official final verdict.

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
