# Research postmortems

## ce7088a6-9b68-48ed-ba20-e78305640721 / Scientific strategy

**Direction:** Establish a reliable measured baseline for the two-joint
reach-and-hold objective, then target the remaining directional failures. The
baseline evidence supports strong general task competence but does not identify
a causal mechanism or test an intervention; failures observed so far cluster at
negative target angles and continued training past the proxy peak did not
improve measured research success.

**Lessons and limits:** The training proxy rose from 0 through 70k steps to
0.97 at checkpoint-100352, then declined to 0.95 at checkpoint-120832. Saved
policy research evaluations measured 95.5% at checkpoint-95232 and 97.0% at
both checkpoint-100352 and checkpoint-120832. The paired comparisons therefore
show a 1.5 percentage-point advantage for checkpoint-100352 over
checkpoint-95232 (3 discordant episodes, exact p=0.25) and no advantage over
checkpoint-120832 (0 percentage-point difference, exact p=1.0); these are
development-panel comparisons, not causal evidence about training. The
protected task-reference panel measured checkpoint-100352 at 98.0%, but this
is also development evidence rather than the official result. All six
research-evaluation failures for checkpoint-100352 had negative target angles,
and all four task-reference failures were between -116 and -128 degrees.
The task-reference 98.0% versus research-evaluation 97.0% discrepancy may
reflect their distinct panels and semantics; it does not establish robustness
or explain the failure mechanism. Training reward and proxy success remain
training facts, not task-performance claims. The automatic baseline recorded
no explicit expected_observation or contradicting_observation; its result
therefore establishes calibration rather than supporting or refuting an
intervention hypothesis.

**Open questions:** Whether the negative-angle residual persists under the
official distribution and at what rate; whether it is caused by observation,
control, reward shaping, or training coverage; and whether a targeted change
can remove it without reducing success elsewhere. Success variability across
training seeds is also unmeasured.

**Conditional next steps:** The immediate next step is the requested official
benchmark of checkpoint-100352. If development continues in a later ordinary
experiment, prioritize a hypothesis aimed at the negative-angle failures and
measure it against the unchanged baseline with task success as the primary
outcome; use diagnostics only to distinguish plausible mechanisms. No further
same-panel measurement is needed before this terminal assessment.

## ce7088a6-9b68-48ed-ba20-e78305640721 / Experiment 1

**Result:** The fresh baseline produced a strong candidate but did not itself
establish the official objective. Checkpoint-100352 is selected for closure
and official assessment.

**Observed behavior:** The training proxy was 0.97 at 100352 steps and 0.95
at the 120832-step endpoint. Research evaluation success was 95.5% at
checkpoint-95232 and 97.0% at both checkpoint-100352 and checkpoint-120832
on 200 episodes with seed 1000. The paired comparison favored
checkpoint-100352 over checkpoint-95232 by 1.5 percentage points but found no
difference from checkpoint-120832. The protected task-reference panel gave
checkpoint-100352 98.0% success on 200 episodes. Research-evaluation failures
for checkpoint-100352 and task-reference failures were concentrated at
negative target angles.

**Hypothesis assessment:** The baseline hypothesis was a calibration objective,
not a falsifiable intervention hypothesis, so there is no recorded
expected_observation or contradicting_observation to classify as supported or
contradicted. It is partially informative: it establishes a measured
development baseline and identifies checkpoint-100352 as the strongest
candidate under the available evidence. The 98.0% task-reference result
supports requesting the official assessment, but one development panel and
97.0% research evaluation do not prove that the policy meets the official
98% criterion.

**Interpretation:** The unchanged PPO recipe learned the task well enough to
reach high development success, with a repeatable-looking directional
residual in the inspected panels. Continuing from the proxy peak did not
improve measured research success, so checkpoint-100352 is preferred over the
endpoint without claiming that the difference is causal. The final objective
remains unresolved until the protected official benchmark is run.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/query_training_log.py` output for experiment 1 steps 5120-120832,
`research/evaluations/ce7088a6-9b68-48ed-ba20-e78305640721/evaluation-ce7088a6-9b68-48ed-ba20-e78305640721-experiment-1-checkpoint-95232-200ep-seed1000-6ba3ba6d7654.json`,
`research/evaluations/ce7088a6-9b68-48ed-ba20-e78305640721/evaluation-ce7088a6-9b68-48ed-ba20-e78305640721-experiment-1-checkpoint-100352-200ep-seed1000-6ba3ba6d7654.json`,
`research/evaluations/ce7088a6-9b68-48ed-ba20-e78305640721/evaluation-ce7088a6-9b68-48ed-ba20-e78305640721-experiment-1-checkpoint-120832-200ep-seed1000-6ba3ba6d7654.json`,
and `research/evaluations/ce7088a6-9b68-48ed-ba20-e78305640721/task-reference-ce7088a6-9b68-48ed-ba20-e78305640721-experiment-1-checkpoint-100352-task-reference-v1.json`.
