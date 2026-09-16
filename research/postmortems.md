# Research postmortems

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Scientific strategy

**Current synthesis:** The campaign objective remains a policy with at least
98% success on the fixed 200-episode official assessment. The transferred PPO
policy from experiment 2 is now the strongest measured artifact at 85.0%
(170/200) on the development panel, improving by 23.5 percentage points over
the experiment 1 endpoint, but it remains below the objective and is not ready
for terminal assessment.

**Lessons and limits:** Training proxies rose from zero success early in the run
to `success_rate` 0.96 and `ep_rew_mean` 187.0 at 120832 steps in experiment 2,
while task-reference success reached 85.0%. The training proxy was non-monotonic:
it reached 1.0 and `ep_rew_mean` 194.17 at 50176 steps, but that checkpoint
measured only 72.0%, so proxy peak selection would not have identified the best
measured task policy. At the experiment 2 endpoint, 12 of 30 failures never
entered tolerance and 18 entered but did not complete the 100-step hold,
compared with 55 and 22 respectively for the experiment 1 endpoint. Endpoint
success was 87.7% near-radius (50/57), 83.9% far-radius (120/143), 83.2% on
the front half (79/95), and 86.7% on the back half (91/105). The uniform-radius
training intervention therefore coincided with large gains in the previously
weak near and front geometries and a reduction in acquisition failures, while
the complete-hold failure count did not increase. These are same-panel
development measurements of a transferred policy; they support usefulness of
the tested recipe but do not isolate the radius sampler as the sole cause.

**Open questions:** It remains unresolved whether the radius-sampling mismatch
accounts for most of the gain, versus transfer dynamics or other control and
representation effects. The endpoint still has 30 failures and is 26 successes
short of the 196/200 objective on this development panel, so residual
representation, control, or hold robustness limitations remain unresolved.

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
