# Research postmortems

## 05f1c25c-20bb-41be-871e-6b451acb9d93 / Scientific strategy

**Current synthesis:** The fresh baseline learned the reach-and-hold behavior and
reached 98% on the development task-reference panel at 100,352 steps. The
120,832-step endpoint reached 97%, while the reward-peak checkpoint at 86,016
steps reached 94%. The measured 100,352-step checkpoint is therefore the
strongest current policy evidence, despite the absence of an intervention that
would support causal attribution.

**Lessons and limits:** Training reward and rollout success were useful for
locating checkpoints but did not predict task success monotonically: the
highest reward checkpoint underperformed the later proxy-peak checkpoint.
Measured development task success, not the training proxy, supports the policy
progress claim. The two development instruments agree on the 94%, 98%, and 97%
ordering, but both use development evidence rather than the fixed official
panel. The selected policy's four failures share the same episode identities
across the two measurements and are descriptively concentrated at negative
target angles; this is a failure characterization, not evidence of a causal
geometric mechanism.

**Open questions:** Whether the selected policy reaches at least 98% on the
distinct official panel remains unresolved. The late decline from the
100,352-step checkpoint to the endpoint and the cause of the remaining
failures are also unresolved; this baseline does not distinguish training
instability from ordinary checkpoint variation.

## 05f1c25c-20bb-41be-871e-6b451acb9d93 / Experiment 1

**Result:** The fresh baseline made substantial task progress. Candidate
`candidate-5e10ac53` at 100,352 steps achieved 98% (196/200) on both the
research evaluation and the protected task-reference development panel. It is
selected as working and best-known, and the official benchmark is requested.

**Observed behavior:** The run completed 120,832 steps against a 120,000-step
budget. In the raw training log, `success_rate` was 0 through 70,656 steps,
rose to 0.42 at 86,016, reached 0.97 at 100,352, and ended at 0.95. The
training `ep_rew_mean` rose from -24.5 at 1,024 steps to 163.85 at 86,016,
then fell to 117.32 at 100,352 and 112.02 at the endpoint. The measured
checkpoint at 86,016 steps scored 94%, and the endpoint scored 97%, so the
highest reward and the final checkpoint were not the best measured policies.
On the common development panel, the selected checkpoint failed seeds 7300,
7310, 7384, and 7402; the endpoint failed those plus 7421 and 7452. The
selected failures had target radii from about 6.7 to 9.9 cm and negative
angles from about -116 to -125 degrees.

**Hypothesis assessment:** Supported within the limited scope of a baseline:
the unchanged fresh method produced a policy at the campaign objective level
on the development panel and established a useful initial reference. This
baseline had no type-specific intervention prediction or causal comparison;
the evidence therefore does not show that any component caused the measured
result, nor does 98% on a development panel establish the official result.
The reward/proxy decline after 100,352 steps is an unexpected training signal
that justifies selecting the earlier measured checkpoint rather than the
endpoint, but it does not by itself explain the task failures.

**Interpretation:** The learned policy is sufficiently promising for terminal
assessment, with two independent development measurements at the 98% target
and a lower-performing endpoint. The remaining uncertainty is appropriately
resolved by the distinct official panel rather than by treating development
success as final validation.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/05f1c25c-20bb-41be-871e-6b451acb9d93/experiment-1/inventory.json`;
`research/training_logs/05f1c25c-20bb-41be-871e-6b451acb9d93/experiment-1-attempt-1.log`;
the six measurement artifacts under
`research/evaluations/05f1c25c-20bb-41be-871e-6b451acb9d93/`.
