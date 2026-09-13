# Research postmortems

## 285f0407-8cc3-401d-bdcd-2af73de9a61c / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned strong reach-and-hold behavior, but the best measured checkpoint remains just below or at the objective depending on the development panel: checkpoint-100352 scored 97.0% on the research panel and 98.0% on the distinct task-reference panel. Its task-reference failures cluster in a narrow negative-angle region, so the policy is promising but not yet robustly established at the human objective.

**Lessons and limits:** Measured task success, rather than training reward or the training success proxy, is the relevant progress signal. Later training did not improve the measured policy: checkpoint-120832 scored 97.0% on both available panels, while checkpoint-100352 scored 98.0% on task-reference. The measurements are development panels, not the official 200-episode assessment, and the common failure patterns do not establish their cause.

**Open questions:** Whether the negative-angle failure cluster persists on the official panel and whether a subsequent intervention can improve it without degrading the rest of the task distribution remain unresolved.

## 285f0407-8cc3-401d-bdcd-2af73de9a61c / Experiment 1

**Result:** The baseline produced a useful learned policy, with checkpoint-100352 selected as the working and best-known candidate for continued development; terminal assessment is deferred.

**Observed behavior:** Training success was 0 through step 70,656, rose to 0.93 at step 95,232 and 0.98 at step 99,328, then declined to 0.95 at the completed 120,832 steps; the recorded reward likewise peaked before the final checkpoint. On the 200-episode research panel, success was 95.5% at checkpoint-95232 and 97.0% at both checkpoint-100352 and checkpoint-120832. On the distinct 200-episode task-reference panel, the same checkpoints scored 96.0%, 98.0%, and 97.0%, respectively. The four failures for checkpoint-100352 all used target angles from -116.4 to -127.9 degrees and target radii from 6.7 to 9.9 cm; checkpoint-120832 retained those four failures and added failures at -132.4 degrees and 169.1 degrees. All failed episodes truncated at 500 steps.

**Hypothesis assessment:** The baseline hypothesis to establish an initial learned policy is supported: learning produced high measured task performance and a useful candidate. Progress toward the human objective is only partial and panel-dependent, however; the best development result is 98.0% on one panel while the independent researcher panel is 97.0%, and neither is the official assessment. The training-proxy peak and later training did not provide evidence that the final checkpoint was better, so the result does not support treating continued unchanged training as an improvement.

**Interpretation:** The policy has learned the core reach-and-hold behavior, but the repeated negative-angle failures indicate a residual distributional weakness in the measured task behavior. The evidence identifies where the current candidate fails, not why; it does not establish a causal explanation or an official success rate.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/checkpoints/challengers/285f0407-8cc3-401d-bdcd-2af73de9a61c/experiment-1/inventory.json`; `research/checkpoints/challengers/285f0407-8cc3-401d-bdcd-2af73de9a61c/experiment-1/checkpoint-100352/artifact.json`; `research/checkpoints/challengers/285f0407-8cc3-401d-bdcd-2af73de9a61c/experiment-1/checkpoint-120832/artifact.json`; the three `research/evaluations/285f0407-8cc3-401d-bdcd-2af73de9a61c/evaluation-*.json` artifacts; the three `research/evaluations/285f0407-8cc3-401d-bdcd-2af73de9a61c/task-reference-*.json` artifacts.
