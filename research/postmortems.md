# Research postmortems

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Scientific strategy

**Current synthesis:** The campaign objective remains a policy with at least
98% success on the fixed 200-episode official assessment. The fresh PPO
baseline learned substantial reach-and-hold competence, and
`checkpoint-120832` is the strongest measured artifact at 61.5% (123/200),
improving by 12 percentage points over `checkpoint-115712` on the shared
development panel, but it is not close to the objective.

**Lessons and limits:** Training proxies rose from zero success early in the run
to `success_rate` 0.89 and `ep_rew_mean` 169.5 at 120832 steps, while the
protected task-reference result was 61.5%. Of the endpoint's 77 failures, 55
never entered tolerance and 22 entered but did not complete the 100-step hold.
Success was lower for near-radius targets (56.1%, 32/57) and front-half targets
(48.4%, 46/95) than for far-radius (63.6%, 91/143) and back-half targets
(73.3%, 77/105). Code and evaluation artifacts show that training samples the
6-10 cm band with probability 0.50, whereas the protected task uses a uniform
6-20 cm radius; this is a plausible mismatch, not proof of cause. The paired
checkpoint comparison supports within-panel improvement only, and all
measurements are development evidence rather than the official result.

**Open questions:** It remains unresolved whether the radius-sampling mismatch
is materially responsible for the near-radius and no-reach failures, or whether
the limiting factors are instead the policy representation or control behavior.
It is also unresolved whether changes that improve acquisition preserve the
complete 100-step hold across the official geometry distribution.

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
