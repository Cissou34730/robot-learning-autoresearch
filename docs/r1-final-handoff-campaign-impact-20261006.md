# Final R1 handoff campaign impact — 2026-10-06

## Scope and identification

This report preserves a read-only maintainer review of campaign
`796c9c1e-8adc-4d24-8983-a45f48051d68`, started from base commit
`9ff3dafe99dae43b3cca3d40a2e2d1e5950a20e8`. That base includes the final R1
implementation, commit `8c0a25b264370457e069936e0b5040a85b55cd0b`
(`Complete R1 scientific handoff`). This campaign therefore exercised final
R1, not the earlier startup reminder or core/partial handoff alone.

The review used the campaign scientific model, completed-operation history,
Runner state, durable M1-M3 evaluation artifacts, and the relevant PI session
record. Inspection was read-only. No pending request was consumed, and no
training, measurement, assessment, role assignment, or other campaign
operation was executed during this review.

## What R1 was intended to establish

Final R1 is a continuity mechanism. It carries a concise, PI-selected,
source-recoverable decision-relevant synthesis from preliminary modeling into
startup, then requires consequential conclusions, limitations, and unresolved
alternatives to be preserved or revised through checkpoints.

R1 is not:

- verification that the scientific model is true;
- a causal-inference guarantee;
- an action-selection gate that forbids training or chooses the next
  intervention for the PI; or
- a guarantee that all evidence used in later reasoning will be durably
  persisted.

The relevant question is therefore whether the selected synthesis changed and
remained visible in campaign reasoning, not whether every later scientific
claim or action was correct.

## Observed startup and continuity sequence

The startup sequence showed direct uptake of the final-R1 synthesis:

1. Before any candidate or training run existed, the PI requested M1, a
   candidate-free compiled kinematics and local-dynamics probe.
2. The PI interpreted M1 by revising globally weak actuator authority and
   severe inertial coupling from plausible leading explanations to secondary
   hypotheses.
3. E1 preserved the measured findings, their local and disturbance-free
   limits, and the competing explanations of branch/radius-conditioned
   acquisition versus insufficient hold margin.
4. I1 was then opened around that distinction. E3 carried the same revised
   synthesis and decision frontier into the inquiry transition.
5. Only after this sequence did the PI request T1, a fresh full-annulus PPO
   baseline designed to separate acquisition failures from post-entry hold
   failures.

This is materially different from a baseline-first startup: the initial
training decision followed an embodied, candidate-free measurement that tested
claims selected in the scientific-model handoff.

## M1: findings and limits

M1 exhaustively checked both analytic IK branches over 141 radii from 0.06 m
through 0.20 m and 360 angles:

- open branch: 47,940 of 50,760 branch-target samples legal (94.44%);
- folded branch: 47,940 of 50,760 branch-target samples legal (94.44%);
- minimum measured joint-limit margin: approximately `4.05e-05 rad`;
- local pulse velocity settling below `0.01 rad/s`: 7-9 control steps;
- maximum cross-joint displacement: approximately `0.00252 rad`; and
- maximum endpoint displacement: approximately `0.03996 m`.

These measurements supported agreement between the compiled geometry and the
preliminary physical model and weakened a global weak-authority explanation.
They did not establish nonlinear behavior near joint limits, closed-loop hold
quality, reward-to-success alignment, or robustness under disturbances. The
dynamic probe was local and disturbance-free.

The original M1 artifact recorded legality per branch and radius/angle rows,
but did not itself persist target-wise unions across the two branches. E1 and
E3 correctly stated that artifact-level limitation.

### Late-log correction: target-wise union was derived

The later T2/T3 rationale referred to target-wise branch-union coverage. That
statement must not be characterized as unsupported. Before T2, the PI
separately reconstructed branch legality and found that at representative
radii 0.06, 0.10, 0.14, 0.18, and 0.20 m, at least one branch was legal for
all 360 of 360 sampled angles at each radius.

The scientific reasoning was therefore backed by a valid derivation. The
evidence-fidelity issue is narrower: this derived union result was not written
back into the M1 artifact or a durable checkpoint. A future reader restricted
to those durable records would see the earlier limitation but not its later
resolution.

## T1 and M2: equal totals concealed a changed failure mode

T1 trained for 120,832 effective steps. M2 evaluated its terminal checkpoint
and an earlier late checkpoint on the same 160 episodes with seed 4200:

| T1 checkpoint | Successes | First reaches | No first reach | Failures after entry |
| --- | ---: | ---: | ---: | ---: |
| 105,472 steps | 98/160 | 116 | 44 | 18 |
| 120,832 steps | 98/160 | 102 | 58 | 4 |

The aggregate success result was identical, with no discordant episode
outcomes, but the behavior was not equivalent. The terminal policy reached 14
fewer targets while also producing 14 fewer post-entry failures. Later
training therefore traded acquisition breadth for more reliable completion
after entry; it did not improve the 98/160 episode total. This is exactly the
kind of acquisition-versus-stability distinction that the R1-carried model and
I1 required the campaign to retain.

M2 localized the terminal policy's main observed gap to missed acquisition,
especially at outer radii, while showing that only four of its 102 reaches
failed after entry. That evidence motivated T2's coverage-balanced radius
sampler.

## T2 and M3: complementary policies, limited causal attribution

T2 was a fresh PPO run with equal probability assigned to the 0.06-0.14 m and
0.14-0.20 m radius ranges. It also trained for 120,832 effective steps. M3
compared terminal T2 and terminal T1 on the same 160 development episodes with
seed 4360:

| Policy | Successes | First reaches | Failures after entry | Reached branch |
| --- | ---: | ---: | ---: | --- |
| T1 | 89/160 | 93 | 4 | open in all 93 reaches |
| T2 | 98/160 | 100 | 2 | folded in all 100 reaches |

The paired outcomes contained 44 T2-only wins and 35 T1-only wins, for a net
advantage of nine episodes to T2. The result supports a descriptive conclusion:
the two learned policies had complementary acquisition patterns and different
branch selection, while both had relatively few failures after entry.

It does not support a clean causal claim that the balanced sampler produced
those differences. T1 and T2 were independently trained with different
training seeds. The PI explicitly identified that confound before M3. Shared
evaluation seeds reduce evaluation-panel noise and characterize policy
differences, but they do not remove training-seed variation or isolate the
sampler's causal effect.

## T3 and the uncompleted M4

T3 was an embodied, branch-guided intervention: balanced radius exposure plus
potential-based guidance toward the open branch below 0.14 m and the folded
branch above 0.14 m. Its rationale attempted to combine the complementary
acquisition modes observed in M3 rather than treating PPO return alone as the
decision variable.

T3 completed 120,832 effective training steps. It was not development-evaluated
before the campaign stopped. The proposed M4 comparison of T3, T1, and T2 was
not executed and must not be represented as completed evidence. Consequently,
the campaign establishes that T3 was trained, not that branch guidance
improved, preserved, or degraded development performance.

## Resource and lifecycle accounting

- Training runs: 3 (T1, T2, T3).
- Requested training steps: 360,000.
- Effective completed training steps: 362,496.
- Completed measurements: 3 (M1, M2, M3).
- Failed operations: 0.
- Official assessments: 0.
- Assigned model roles: none (`best_known`, `working`, and retained roles
  remained unset).
- Pending Runner operation at inspection: none.

The unexecuted M4 request existed only as a workspace request after the stop;
this review did not execute or modify it.

## Compact comparison with earlier R1 behavior

The comparison below is observational across separate campaigns and prompt
versions, not a controlled causal experiment.

| Handoff version | Supported observed behavior |
| --- | --- |
| Partial startup reminder | A prior campaign still proceeded directly to baseline training; merely telling startup to read the model did not preserve a selected decision frontier. |
| Core/partial R1 | A later campaign preserved physical reasoning into startup and checkpoints, but broad section carryover also propagated a physical interpretation error and evidence distortions. |
| Final R1 in this campaign | Startup received a selected, source-recoverable synthesis; the PI performed M1 before training, revised an interpretation, retained limitations and competing explanations through E1/E3, and framed I1/T1 around discriminating diagnostics. |

The current sequence is stronger evidence of mechanism delivery than the prior
campaigns, but campaign differences prevent controlled attribution of the
startup improvement to R1 alone.

## Maintainer judgment

**Mechanism delivery: strong evidence.** Final R1's selected synthesis reached
startup, influenced the first operation, and remained active through
checkpoints and the initial inquiry. The campaign did not merely quote the
model: it tested a selected physical uncertainty before training and revised
the interpretation in response.

**Causal impact on startup quality: moderate confidence.** The startup was more
embodied, inquiry-centered, and evidence-calibrated than the observed
baseline-first and broad-carryover campaigns. However, this is one campaign
without a contemporaneous control, and other campaign, model, or stochastic
differences could contribute.

**Retention decision: retain R1.** The evidence supports keeping final R1
rather than reopening its continuity design. The remaining harness questions
are downstream:

- persist derived evidence and revisions at the point they become
  decision-relevant;
- improve causal calibration so paired policy evaluation is not mistaken for
  intervention attribution;
- strengthen action selection around when a new training run is worth its
  confounds and cost; and
- control resource use, especially before a prior intervention's causal effect
  is isolated or a new intervention is development-evaluated.

These are evidence persistence/fidelity, causal calibration and action
selection, and cost-control concerns. They do not negate the observed delivery
or use of final R1.

## Evidence basis

- `pi_workspace/scientific_model.md`
- `campaigns/results.jsonl`
- `runner/state/research_state.json`
- `campaigns/evaluations/796c9c1e-8adc-4d24-8983-a45f48051d68/initial_physics_probe.json`
- `campaigns/evaluations/796c9c1e-8adc-4d24-8983-a45f48051d68/evaluation-796c9c1e-8adc-4d24-8983-a45f48051d68-m2-T1-checkpoint-105472-160ep-seed4200-539ca3aa03dd.json`
- `campaigns/evaluations/796c9c1e-8adc-4d24-8983-a45f48051d68/evaluation-796c9c1e-8adc-4d24-8983-a45f48051d68-m2-T1-checkpoint-120832-160ep-seed4200-539ca3aa03dd.json`
- `campaigns/evaluations/796c9c1e-8adc-4d24-8983-a45f48051d68/evaluation-796c9c1e-8adc-4d24-8983-a45f48051d68-m3-T1-checkpoint-120832-160ep-seed4360-539ca3aa03dd.json`
- `campaigns/evaluations/796c9c1e-8adc-4d24-8983-a45f48051d68/evaluation-796c9c1e-8adc-4d24-8983-a45f48051d68-m3-T2-checkpoint-120832-160ep-seed4360-539ca3aa03dd.json`
- PI session log for scientific session S3, including the pre-T2 branch-union
  reconstruction and the pre-M3 training-seed confound statement.
