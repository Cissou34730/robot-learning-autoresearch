# Research postmortems

## 5befb592-3256-436e-bf6a-a4733c512ad9 / Scientific strategy

**Current synthesis:** The fresh PPO baseline produced a useful but incomplete
learned policy. The endpoint checkpoint-120832 achieved 90% success on the
100-episode research evaluation and 92% on the fixed task-reference preview,
improving over checkpoint-100352's 75% research success. It is the strongest
measured candidate and should remain the working and best-known lineage, but it
does not yet support the 98% human objective or terminal assessment.

**Lessons and limits:** Training proxies improved from an episode reward of
-3090 at 1024 steps to -168.489 at the endpoint, and training success reached
0.11 late in the run, but these proxies are not acceptance evidence. The
research evaluation and paired comparison support real progress for the saved
endpoint under the tested semantics: 15 additional successes and no
checkpoint-100352 wins on the shared 100 episodes. The task-reference failures
were all 500-step truncations and were descriptively concentrated in the
positive-angle portion of that reused panel, but this is selection-contaminated
development evidence and does not establish a causal failure mechanism or
official-task generalization. One fresh training run, one research seed, and
two measured checkpoints leave learning variance and neighboring-checkpoint
behavior unresolved.

**Open questions:** Whether unchanged training can close the remaining success
gap, whether the observed geometry pattern recurs on independent panels, and
which learning or task-facing intervention could improve robustness remain
unknown.

## 5befb592-3256-436e-bf6a-a4733c512ad9 / Experiment 1

**Result:** The baseline made substantial task progress, but the endpoint is
below the 98% objective; checkpoint-120832 is selected as working and
best-known for continued development.

**Observed behavior:** Training completed at 120,832 steps. The logged mean
episode reward improved from -3090 at 1,024 steps to -168.489 at the endpoint;
training success stayed at zero through the earlier checkpoints and reached
0.11 at the endpoint. On the shared 100 research episodes,
checkpoint-100352 succeeded on 75 episodes and checkpoint-120832 on 90.
The paired comparison recorded 15 endpoint wins and zero earlier-checkpoint
wins among 15 discordant episodes. The endpoint succeeded on 184 of 200
episodes (92%) in the task-reference-v1 preview. Its 16 failures all ran to
500 steps; within that fixed panel, 37 of 53 targets with angles from 90 to
180 degrees succeeded, compared with 100% success in each of the other three
angle bins. This panel also showed lower success for the longest-radius bin
(26 of 32).

**Hypothesis assessment:** Partially supported. The baseline hypothesis was to
establish an initial policy for the human objective. The measured endpoint is
clearly useful and the late training improvement translated into higher
research-task success than the pre-onset checkpoint, but the result remains
8 percentage points below the research-task objective and the protected
preview is not terminal evidence. The single fresh run cannot establish that
training proxies caused the evaluation improvement or that the observed
geometry pattern generalizes.

**Interpretation:** The endpoint is the best available saved policy and a
sound parent for a subsequent investigation, while the baseline recipe is
worth keeping because it produced measured progress. The remaining failures
show that progress is not yet sufficient for acceptance; further development
should treat the fixed-panel geometry pattern as a diagnostic clue rather than
an acceptance threshold or causal explanation.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/training_logs/5befb592-3256-436e-bf6a-a4733c512ad9/experiment-1-attempt-1.log`;
`research/checkpoints/challengers/5befb592-3256-436e-bf6a-a4733c512ad9/experiment-1/inventory.json`;
`research/evaluations/5befb592-3256-436e-bf6a-a4733c512ad9/evaluation-5befb592-3256-436e-bf6a-a4733c512ad9-experiment-1-checkpoint-100352-100ep-seed0-a69293a214ad.json`;
`research/evaluations/5befb592-3256-436e-bf6a-a4733c512ad9/evaluation-5befb592-3256-436e-bf6a-a4733c512ad9-experiment-1-checkpoint-120832-100ep-seed0-a69293a214ad.json`;
`research/evaluations/5befb592-3256-436e-bf6a-a4733c512ad9/task-reference-5befb592-3256-436e-bf6a-a4733c512ad9-experiment-1-checkpoint-120832-task-reference-v1.json`.
