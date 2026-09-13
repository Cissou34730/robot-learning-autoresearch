# Research postmortems

## 285f0407-8cc3-401d-bdcd-2af73de9a61c / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the official 6–20 cm, full-angle reach-and-hold distribution. The unchanged PPO baseline learned strong behavior, with checkpoint-100352 reaching 97.0% on the research panel and 98.0% on the distinct task-reference panel, but neither is the official assessment. Repeated failures include a negative-angle cluster, and the baseline training environment sampled only 14–20 cm targets; the available evidence therefore supports a distribution-coverage concern without proving it is causal.

**Lessons and limits:** Measured task success, rather than training reward or the training success proxy, is the relevant progress signal. Later unchanged training did not improve the measured policy: checkpoint-120832 scored 97.0% on both available panels, while checkpoint-100352 scored 98.0% on task-reference. The checkpoint-100352 task-reference failures were all at -116° to -128° and 6.7–9.9 cm; research-panel failures also repeatedly included negative angles and several 7–9 cm targets. These are development panels, not the official assessment, and failure clustering does not establish whether radius coverage, angle, control, or hold dynamics is causal.

**Open questions:** Whether broader near-base training coverage improves the negative-angle failures while preserving performance across the full official distribution remains unresolved, as does whether the residual failures instead arise from control or hold stability.

## 285f0407-8cc3-401d-bdcd-2af73de9a61c / Experiment 1

**Result:** The baseline produced a useful learned policy, with checkpoint-100352 selected as the working and best-known candidate for continued development; terminal assessment is deferred.

**Observed behavior:** Training success was 0 through step 70,656, rose to 0.93 at step 95,232 and 0.98 at step 99,328, then declined to 0.95 at the completed 120,832 steps; the recorded reward likewise peaked before the final checkpoint. On the 200-episode research panel, success was 95.5% at checkpoint-95232 and 97.0% at both checkpoint-100352 and checkpoint-120832. On the distinct 200-episode task-reference panel, the same checkpoints scored 96.0%, 98.0%, and 97.0%, respectively. The four failures for checkpoint-100352 all used target angles from -116.4 to -127.9 degrees and target radii from 6.7 to 9.9 cm; checkpoint-120832 retained those four failures and added failures at -132.4 degrees and 169.1 degrees. All failed episodes truncated at 500 steps.

**Hypothesis assessment:** The baseline hypothesis to establish an initial learned policy is supported: learning produced high measured task performance and a useful candidate. Progress toward the human objective is only partial and panel-dependent, however; the best development result is 98.0% on one panel while the independent researcher panel is 97.0%, and neither is the official assessment. The training-proxy peak and later training did not provide evidence that the final checkpoint was better, so the result does not support treating continued unchanged training as an improvement.

**Interpretation:** The policy has learned the core reach-and-hold behavior, but the repeated negative-angle failures indicate a residual distributional weakness in the measured task behavior. The evidence identifies where the current candidate fails, not why; it does not establish a causal explanation or an official success rate.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/checkpoints/challengers/285f0407-8cc3-401d-bdcd-2af73de9a61c/experiment-1/inventory.json`; `research/checkpoints/challengers/285f0407-8cc3-401d-bdcd-2af73de9a61c/experiment-1/checkpoint-100352/artifact.json`; `research/checkpoints/challengers/285f0407-8cc3-401d-bdcd-2af73de9a61c/experiment-1/checkpoint-120832/artifact.json`; the three `research/evaluations/285f0407-8cc3-401d-bdcd-2af73de9a61c/evaluation-*.json` artifacts; the three `research/evaluations/285f0407-8cc3-401d-bdcd-2af73de9a61c/task-reference-*.json` artifacts.
