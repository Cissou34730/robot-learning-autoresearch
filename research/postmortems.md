# Research postmortems

## cc96dcb7-74bb-41d4-8c53-0f9afd26aa75 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
competence, but the best measured checkpoint is well below the 98% campaign
objective. `checkpoint-120832` is the strongest measured artifact and improves
on the immediately preceding checkpoint on the shared development panel.

**Lessons and limits:** Training proxies rose from zero success early in the run
to `success_rate` 0.89 and `ep_rew_mean` 169.5 at 120832 steps, while the
protected task-reference result was 61.5% (123/200). Research diagnostics show
that 55 of the endpoint's 77 failures never entered tolerance and 22 entered
but did not complete the 100-step hold. The endpoint is weaker on the
near-radius subset (56.1%, 32/57) and on the front half of the angular panel
(48.4%, 46/95) than on the corresponding far-radius (63.6%, 91/143) and back
half (73.3%, 77/105) subsets. These are development measurements, not the
official benchmark, and the paired result supports within-panel improvement
only. The training environment also overweights the 6-10 cm radius band
relative to the official uniform radius distribution; this is a plausible
source of evaluation mismatch, not an established cause.

**Open questions:** A subsequent investigation could target the dominant
no-reach failures, especially in the front and near-radius subsets, while
checking that complete-hold reliability is preserved. The current measurements
do not establish whether the training-distribution difference, policy
representation, or control behavior causes those failures.

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
