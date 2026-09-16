# Harness-Induced Bias Audit

Five-method elicitation audit of the full research harness, not of individual
files. Worktree: `C:\Users\cyril.beurier\code\robot-learning`, branch
`issue-30-decision-quality-remediation`. Date: 2026-09-16.

The target is the whole apparatus that produces the official verdict: official
contract, protected evaluators, research environment/evaluation, training and
checkpointing, the runner protocol, lineage selection, statistics, and the
campaign evidence they generated. Methods applied one by one, in sequence:

1. Cascading Failure Simulation
2. Map Is Not the Territory
3. Inversion Analysis
4. Pre-mortem Analysis
5. Fishbone Root-Cause Analysis

No security framing is used. Every finding is about measurement validity and
decision bias.

Evidence status is marked per finding:

- **verified** — confirmed by reading code/tests or by executing a read-only
  probe (the one probe run is noted in Method 1).
- **inferred** — follows from code by construction but was not executed.
- **reported** — documented in the campaign's own plans/decisions.

---

## 0. The harness under audit

The pipeline that turns research decisions into an official result:

```
target distribution (6-20 cm, full angular range)
        |
        v
scenario/environment.py  TwoJointArmReachEnv   <-- training env AND eval env
  - reward.py (training only)                   <-- same file, same sampling
        |
        v
train.py  PPO + VecNormalize
  - training/candidate_checkpoint_callback.py  saves checkpoint-<steps> every N
    rollouts + terminal checkpoint, with training_success / ep_rew_mean
        |
        v
research/current_params.json  (active config)
        |
        v
research/proposal.json, evaluation_request.json, postmortems.md  (Researcher)
        |
        v
research/run_experiment.py + runner_*.py  (Runner: validate, execute, record)
        |
        v
scenario/evaluation.py  research_evaluation  (researcher-owned, mutable)
benchmark/reference_evaluation.py  task_reference (protected, seed 7300)
        |
        v
training/comparison.py  paired evidence / McNemar in metrics
        |
        v
research_state.json  working_lineage / best_known_lineage / retained
        |
        v
benchmark/final_benchmark.py  official verdict (seed 1000, 200 episodes)
```

Ownership is enforced by `research/runner_protocol.py`. Key fact for the audit:
the surface that defines **how a saved policy is measured** is partly protected
and partly researcher-owned, and the boundary between them is where several
biases live.

Campaign evidence used to ground findings (campaign
`052b98fa-ee96-41c6-ae7e-1c2ad99cfc0a`, `research_state.json`,
`research/results.jsonl`, `research/postmortems.md`):

| Item | Value |
| --- | --- |
| Exp 1 (baseline, lr 0.0003), checkpoint-105472 | 97.5% task-reference (195/200) |
| Exp 1, checkpoint-115712 | 95.5% |
| Exp 1, checkpoint-120832 | 92.0% |
| Exp 1 late training proxy | training_success 0.02 -> 0.53, ep_rew 24.4 |
| Exp 2 (transfer, lr 0.0001) | 96.0 / 95.0 / 96.5 / 94.0 % |
| Exp 2 late training proxy | training_success 0.98 - 0.99 |
| Objective | >= 196/200 = 98.0% on the official panel |

---

## Method 1 - Cascading Failure Simulation

**Procedure.** Inject a small, plausible failure at one stage and trace how it
propagates and amplifies downstream. Five injections were traced end to end.

**Injection A - the same seed on both sides of the wall.**
Set `research_evaluation` seed to 1000 with 200 episodes. Propagate:

- `research/runner_protocol.py:502-504` and `robot_learning/evaluate.py:18-19`
  default the runner/CLI research-evaluation panel to `RESEARCH_EVALUATION_SEED`
  and `RESEARCH_EVALUATION_EPISODES`.
- `robot_learning/training/research_config.py:22-23` sets those to `1000` and
  `200`.
- `robot_learning/benchmark/final_contract.py:7,13` sets the official panel to
  the same `EVALUATION_SEED = 1000` and `EVALUATION_EPISODES = 200`.
- `robot_learning/scenario/environment.py:87-110` samples
  `angle ~ U(-pi, pi)` then `radius ~ U(0.06, 0.20)` from `self.np_random`,
  seeded by `super().reset(seed=...)`.
- `robot_learning/benchmark/final_benchmark.py:80-86` samples the target with
  **the identical two draws in the identical order** from the same
  `np_random`.

**Verified probe** (read-only, run in this worktree):

```
official_seed==research_eval_default_seed targets identical for all 200: True
first5: [(0.1432, 0.0194), (0.0473, 0.0404), (0.0806, -0.0749),
         (-0.0366, -0.0887), (-0.0782, -0.0004)]
```

The 200 official targets are byte-for-byte reproducible by the researcher-owned
development instrument. Because both evaluators feed the frozen artifact through
the artifact's own `io.observe` and `deterministic=True` prediction, and the only
other stochastic input is target sampling, the per-episode success vector is also
reproduced. **The official panel is not held out.** Propagation continues into
lineage selection: `best_known` can be chosen directly against the official
metric, and the terminal verdict becomes confirmatory rather than independent.
Severity: critical. Status: verified (targets), inferred (outcomes).

**Injection B - checkpoint cadence at rollout boundaries.**
`candidate_checkpoint_callback.py:50-55` saves at the first rollout start where
`num_timesteps >= next_checkpoint` and names the directory with the actual step
count. With `checkpoint_every_steps=5000` and `n_steps=1024`, the effective
spacing is 5120 (confirmed by the recorded candidate set: 5120, 10240, 15360,
...). Propagation: a nominal "5000-step grid" yields ~24 correlated snapshots
per 120k-step run; each is a selection candidate; the terminal checkpoint is
arbitrary. Amplifies Injection D. Severity: low. Status: verified.

**Injection C - the training proxy is a rolling, off-panel statistic.**
`candidate_checkpoint_callback.py:30-48` writes `success_rate` from
`model.ep_success_buffer` and `ep_rew_mean` from `model.ep_info_buffer`. These
SB3 buffers are bounded rolling windows (<=100 completed training episodes), not
an evaluation of the saved checkpoint. Propagation to the brief: these proxies
sit beside real measurements and are the only per-checkpoint signal available
without paying for evaluation, so they steer attention. In experiment 1 proxies
rose monotonically through 90k-120k steps while the measured panel fell
97.5 -> 92.0; in experiment 2 proxies reached 0.98-0.99 while task success was
94.0-96.5. Severity: high. Status: verified (code) + reported (campaign).

**Injection D - selecting the maximum of many correlated panel scores.**
The researcher measures subsets of the pool on one deterministic 200-episode
panel and designates `best_known`. At 200 episodes, one episode is 0.5%, and the
distance from 97.5% to the 98.0% gate is exactly one episode. Selecting the top
of ~24 correlated scores biases the selected score upward relative to the
policy's true rate, and the official panel being the same panel (Injection A)
means the bias transfers directly to the verdict. Status: inferred, supported by
exp 1's 97.5/95.5/92.0 spread. Severity: high.

**Injection E - training-only identity leaks into evaluation identity.**
`runner_protocol.py:114-117` declares `TRAINING_ONLY_PATHS =
{scenario/reward.py, scenario/training_environment.py}`. The second file does
**not exist** in this worktree (`robot_learning/scenario/` contains
`environment.py`, not `training_environment.py`). Therefore
`evaluation_semantics_fingerprint()` (`runner_protocol.py:1079-1119`) still
includes `scenario/environment.py`, which holds `TRAINING_TARGET_RADIUS_RANGE`
and the training mechanics. Propagation: any training-only environment edit
changes the measurement fingerprint and invalidates all prior comparable
measurements, even though it cannot change how a saved policy is replayed.
Severity: medium-high. Status: verified.

**Cascade summary.** One seed coincidence (A) feeds one maximization pressure
(D) computed over a proxy-prone, correlated pool (B, C) on a shared panel, and
the identity layer that would normally quarantine training-only edits is only
half-installed (E). The failure does not need a bad policy; it needs only the
normal workflow.

---

## Method 2 - Map Is Not the Territory

**Procedure.** Treat the harness as a lossy map of the real objective and list
what it structurally cannot represent. Each gap is a standing bias in every
decision made from the map.

The real objective is: *a learned policy reaches a uniformly random target
6-20 cm away and holds within 1 cm for 2 s, in at least 98% of the true
distribution of such situations, on the real task.*

What the map cannot represent:

1. **The distribution beyond 200 fixed episodes.** `final_contract.py` fixes
   one 200-episode draw (`seed=1000`). The objective is stated as a distribution
   over the continuous annulus; the verdict is a single deterministic point
   sample with no confidence interval. The harness reports `success_percent`,
   mean/median/worst final distance, and nothing about sampling uncertainty
   (`final_benchmark.py:174-183`). Status: verified.
2. **Any second official panel.** The verdict has exactly one realization. There
   is no held-out official panel, and the development panel collides with it
   (Method 1A). `reference_contract.py` provides a distinct seed (7300), but it
   is development evidence and is itself a single fixed panel. Status: verified.
3. **Run-to-run learning variability.** `program.md:67-79` states replication is
   what varies the learning process, but the campaign ran one baseline and one
   transfer; `best_known` was designated on a single fresh run. Status: reported.
4. **Causal structure.** Single runs with no controls cannot separate update
   dynamics, reward incentives, and distribution effects; the postmortem
   explicitly leaves this unresolved. Status: reported.
5. **Reward and optimization internals.** `reward_total` is deliberately removed
   from comparable success identity (`instruments.md:150-158`), so cross-reward
   behavioral comparison has no accepted channel; the map is silent there.
   Status: verified.
6. **Between-step and physical reality.** Control runs at `frame_skip=10`
   (0.02 s); success is measured per control step. Sub-step contact/settling,
   actuator saturation, and the real robot are outside the map. The frozen
   `two_joint_arm.xml` is a single nominal model. Status: verified.
7. **The target geometry that was never drawn.** `research_evidence` records
   per-episode radius/angle, but coverage is whatever the seed produced;
   nothing enforces stratification over the annulus. Status: verified map
   capability, coverage unverified.
8. **The observation's own information content.** `scenario/observations.py:19-58`
   includes an analytic inverse-kinematics hint (`shoulder_open`, `elbow_open`,
   `shoulder_folded`, `elbow_folded`) relative to `qpos`. The map can show high
   task success while saying nothing about whether the policy learned
   intent-versus-inverse-kinematics: the observed "learning" is partly supplied
   as input. This is researcher-owned science, not harness code, but it bounds
   how much the harness's learning claim can mean. Status: verified.

**Map conclusion.** The harness can answer "did this saved policy score >= 98%
on the one panel it was selected against?" It cannot answer "is this policy at
98% on the task distribution?" Those are different questions, and the panel
identity collapse (Method 1A) removes the one gap that would normally separate
them.

---

## Method 3 - Inversion Analysis

**Procedure.** Ask "how would we *guarantee* a harness-wide false win?" and
check each answer against the real pipeline. Answers marked PRESENT are live
paths.

1. **Make the development instrument and the official instrument the same
   panel.** PRESENT. `research_config.py:22-23` vs `final_contract.py:7,13`;
   identical sampling verified. This is the single highest-leverage inversion.
2. **Select the maximum over many correlated candidates on that panel.**
   PRESENT. ~24 checkpoints/run at 5120-step spacing; per-round limit of 3
   distinct models (`runner_protocol.py:849-854`) is small, but rounds
   accumulate, and the chosen maximum is what enters lineage.
3. **Let a lagging proxy decide which candidates look promising.** PRESENT.
   Rolling training buffers are the cheap default signal (Method 1C).
4. **Keep training and evaluation on the identical target distribution so no
   generalization gap can ever be observed.** PRESENT. `TRAINING_TARGET_RADIUS_RANGE
   = (0.06, 0.20)` equals the official range (`environment.py:30`).
5. **Preserve a single fixed deterministic panel forever, with no
   multi-seed aggregation, so panel-specific luck is permanent.** PRESENT.
   `reference_contract.py:12-16`; campaign used one seed.
6. **Reproduce the official success threshold to the episode.** PRESENT. The
   gate is one episode; the panel is the same panel; the score is the panel.
7. **Write the official seed and constants into readable, researcher-accessible
   files so the collision is findable.** PRESENT. `final_contract.py` is
   readable and `tests/benchmark/test_task_contract.py:32` asserts it.
8. **Let the protected evaluator's default observation contract come from
   researcher-owned code.** PRESENT. See Method 5, F6.
9. **Tune the reward to shape behavior, then point the blame at the algorithm
   when measurement disagrees.** Half-present. Reward is training-only by
   design; the campaign observed the divergence and could not attribute it.
10. **Weaken the trust path by editing the checker.** PRESENT in principle but
    explicitly cooperative-only (`full-scenario` trust model). Not used in this
    audit.

Nine of ten inversion paths exist. The harness cannot prevent an outcome it
would itself categorize as a mistaken `goal_reached`; it can only record the
decisions that produced it.

---

## Method 4 - Pre-mortem Analysis

**Premise.** The campaign ends `goal_reached` and, later, the "true" success of
the frozen policy is materially lower, or the campaign never reaches the goal
and abandons a policy that would have. Work backward from each failure.

**Pre-mortem X - false `goal_reached`.**
The official run reported >= 196/200 on seed 1000. Backward chain:

1. The policy was selected as the max over the checkpoint pool on seed 1000
   (Method 1D).
2. Seed 1000 is the official panel (Method 1A), so the selection and the
   verdict share the same episodes and the same lucky targets.
3. The proxy signals that would have flagged instability were either ignored or
   already saturated, because they are rolling training statistics, not
   evaluations (Method 1C).
4. `best_known` was designated from one fixed development panel with no
   multi-seed confirmation (Method 2, items 1-3).
5. The verdict is terminal and, per `program.md:228-244`, a failed official
   verdict is never development feedback - so even a failure could not be
   turned into a corrected second attempt.
Root cause: panel identity collapse plus max-selection on a shared fixed panel.
This is the most probable false-positive path in the current design. Status:
inferred; direct evidence is the campaign's own 97.5 -> 95.5 -> 92.0 spread on
the distinct task-reference panel, which shows how panel-sensitive checkpoint
ranking is.

**Pre-mortem Y - false negative / abandoned progress.**
The campaign is at 97.5% task-reference and below the gate; experiment 2 finds
96.5% at a later step under a lower learning rate, despite training proxies of
0.98-0.99. Backward chain: the only trusted development panel is a single fixed
200-episode draw; the late-proxy decline in experiment 1 made later checkpoints
look bad; the transfer was judged on the same panel; a policy that might exceed
98% on the true distribution but is unlucky on seed 7300 (or on seed 1000) is
never recognized. Status: reported (postmortem open questions).

**Pre-mortem Z - the audit is wrong because the panels are actually
independent.** Ruled out for the research-evaluation default: verified identical
targets for seeds 1000-1199. The task-reference panel (7300) is independent and
is the campaign's main protection; the pre-mortems above therefore apply most
sharply to the runner/CLI default path and to any round that reuses seed 1000.

**Pre-mortem W - decision-quality drift.** The branch name and the plan docs
(issue 27, fresh-replication regression) document repeated no-progress
experiments: "after the restored baseline, eight of eleven experiments repeated
unchanged fresh training." The harness's cognitive steering (anchoring on
`best_known`, binary expected/contradicting vocabulary, minimization language,
proxy prominence) is the root; parts are remediated on this branch
(`program.md` now uses a graded assessment vocabulary), parts remain as
documentation/implementation drift. Status: reported.

---

## Method 5 - Fishbone Root-Cause Analysis

**Procedure.** Spread the whole harness across causal categories and trace each
defect to a shared root.

```
                       HARNESS-INDUCED BIAS
                                |
   MEASUREMENT     PANEL/SAMPLING   SELECTION    STATISTICS    IDENTITY      INCENTIVES   GOVERNANCE
        |               |              |             |             |             |            |
   panel==panel    fixed 200-ep   max-of-pool   no CI / 1ep    fingerprint    proxy vs     researcher
   (F1)            (F1,F4,F16)    (F2)          gate (F2,F4)   drift (F5)     measured(F3) owned on
        |               |              |             |             |             |         trust path(F6)
   dup metrics     cadence 5120   proxy steers  single-seed    dead path     reward_total  test fabricates
   (F11,F12)       (F10)          (F3)          (F4)           (F5)           (F15)        module (F5,F13)
```

**Category: Measurement / instrument.**
- F1 official panel reproducible by the development instrument (verified).
- F11 success is computed twice and independently: `benchmark/final_benchmark.py:120-141`
  (`_hold_progress`) and `benchmark/metrics.py:10-60` (`episode_hold_progress`).
  Duplicate logic can drift; tests in `test_task_contract.py` cover metrics, not
  that the two agree. Status: verified divergence risk (currently consistent).
- F12 `reference_evaluation.py:185` defines success as `bool(terminated)` while
  `scenario/evaluation.py:75-76` uses `info["is_success"]`. Both derive from
  `held_steps`, so they agree now, but the protected panel's verdict depends on
  a different expression than the mutable one. Status: verified.
- F16 no confidence interval or worst-seed aggregation on the official verdict
  (`final_benchmark.py:174-183`). Status: verified.

**Category: Panel / sampling.**
- F1, F4 single fixed deterministic panel per instrument.
- F10 checkpoint spacing is 5120, not 5000 (verified from the recorded pool).
- Coverage of the annulus is unstratified; nothing guarantees the 200 draws
  span the radius/angle space.

**Category: Selection / decision.**
- F2 max-of-pool selection on a shared panel; winner's curse with a one-episode
  gate.
- F3 rolling training proxy steers candidate attention.
- F7 harness cognitive steering (anchors, binary vocabulary, minimization
  language, proxy prominence) - partially remediated.
- F8 the runner/CLI default research panel *is* the official panel, so the
  biased path is the default path.

**Category: Statistics / aggregation.**
- F2 no correction for selection.
- F4 no sampling uncertainty.
- F15 `reward_total` is recorded per episode but not comparable across reward
  changes (`instruments.md:150-158`); the residual caveat is explicit but is a
  footgun for any aggregate a human computes later.

**Category: Identity / provenance.**
- F5 `TRAINING_ONLY_PATHS` names a non-existent module; `environment.py` stays
  in the fingerprint (verified).
- F13 the protected-surface test asserts
  `PROTECTED_BENCHMARK_PATHS == OFFICIAL_TASK_PATHS`
  (`tests/benchmark/test_benchmark_trust_path.py:19-52`) but that set excludes
  the researcher-owned observation fallback used by the protected evaluators.
- F14 `evaluation_semantics_fingerprint` scope is the researcher-owned
  `scenario/` tree (`runner_protocol.py:104`), so the measurement-identity
  boundary can be moved by the same party being measured.

**Category: Incentives / reward.**
- F3, F15; plus the observation-level IK hint (`observations.py:19-58`) that
  supplies part of the solution as input - an incentive to look learned.
- The non-potential `distance_cost` term (`reward.py:55`) and full hold-exit
  forfeit (`reward.py:62-68`) shape a centering policy. This is training-only
  and legitimate, but it is the mechanism most likely to produce a policy that
  scores well on training-shaped behavior while the pass/fail gate (hold) and
  the reward disagree.

**Category: Governance / trust.**
- F6 the protected `benchmark/final_benchmark.py:18-25` and
  `benchmark/reference_evaluation.py:35-42` resolve their default observation
  contract from `robot_learning/training/observations`, which is a
  researcher-owned re-export of researcher-owned `scenario/observations.py`.
  `MODEL_CONTAINED_RUNTIME_PATHS` (`runner_protocol.py:120-125`) lists
  `scenario/observations.py` but not `training/observations.py`, and the latter
  is outside the scanned `scenario/` root. The real evaluation loads the
  artifact's frozen `io.observe`, so the practical exposure is the runtime-less
  path used by the protected benchmark's own contract test. Still a trust-path
  seam. Status: verified.
- F13 test-vs-production drift masks F5: `test_research_protocol.py:710-799`
  fabricates `scenario/training_environment.py` in a synthetic tree and asserts
  it is excluded, while the real repository never creates it. The test therefore
  certifies a remediation (issue 27, L6) that is not installed. Status: verified.

**Shared roots.**
- **RC1 - Panel identity collapse.** One seed, one episode count, one sampling
  routine on both sides of the development/official wall.
- **RC2 - Single fixed deterministic panels and maximum selection.** No
  multi-panel or multi-seed decision rule; the selected max is reported as the
  policy's score.
- **RC3 - Proxy signals decoupled from measurement but displayed together.**
  Rolling training buffers are the cheap signal and the misleading one.
- **RC4 - Leaky ownership boundaries.** Researcher-owned code sits inside the
  protected trust path and inside the evaluation-identity decision.
- **RC5 - Documentation/test/implementation drift.** Contracts assert modules
  and behaviors (training-only isolation, protected observation contract) that
  the shipped tree does not have.

---

## Consolidated findings register

| ID | Finding | Severity | Status | Primary evidence |
| --- | --- | --- | --- | --- |
| F1 | Official panel (seed 1000, 200 ep) is exactly reproducible by the development `research_evaluation`; targets verified identical for seeds 1000-1199 | Critical | verified (targets) + inferred (outcomes) | `final_contract.py:7,13`; `research_config.py:22-23`; `environment.py:87-110`; `final_benchmark.py:80-86`; probe |
| F2 | `best_known` chosen as max over ~24 correlated checkpoints on one 200-ep panel; gate is 1 episode | High | inferred + reported | callback cadence; exp1 97.5/95.5/92.0; brief 24 lines/22 unmeasured |
| F3 | Training proxy is a rolling <=100-episode buffer, displayed beside measurements, and diverges from task behavior | High | verified + reported | `candidate_checkpoint_callback.py:30-48`; exp1/exp2 numbers |
| F4 | One fixed deterministic panel per instrument; no CI, no multi-seed rule for `best_known` | High | verified | `reference_contract.py:12-16`; `final_benchmark.py:174-183` |
| F5 | `TRAINING_ONLY_PATHS` references a non-existent `scenario/training_environment.py`; `environment.py` stays in the eval fingerprint; the test fabricates the module | Medium-High | verified | `runner_protocol.py:114-117,1079-1119`; `test_research_protocol.py:710-799` |
| F6 | Protected evaluators resolve their default observation contract from researcher-owned `training/observations`; not protected and not in the fingerprint | Medium | verified | `final_benchmark.py:18-25`; `reference_evaluation.py:35-42`; `runner_protocol.py:120-125` |
| F7 | Harness cognitive steering (anchors, binary vocabulary, minimization, proxy prominence) partially remediated | Medium | reported | issue-27 plan, fresh-replication plan, `program.md` |
| F8 | Runner/CLI default research panel equals the official panel, making the leak the default path | Medium | verified | `runner_execution.py:502-504`; `evaluate.py:18-19` |
| F9 | Training and evaluation env share one file, so training-only changes cannot be made without invalidating measurements | Medium | verified | `environment.py:30,184-198` |
| F10 | Checkpoint cadence is 5120 steps at n_steps=1024, not 5000; terminal checkpoint arbitrary | Low | verified | callback; recorded pool |
| F11 | Hold-success logic duplicated in two modules with no cross-check test | Low | verified | `final_benchmark.py:120-141`; `metrics.py:10-60` |
| F12 | Protected reference panel defines success as `terminated`; mutable evaluator uses `info["is_success"]` | Low | verified | `reference_evaluation.py:185`; `evaluation.py:75-76` |
| F13 | Protected-surface test does not include the observation fallback on the trust path | Medium | verified | `test_benchmark_trust_path.py:19-52` |
| F14 | Measurement-identity scope is inside the researcher-owned tree | Medium | verified | `runner_protocol.py:104,1086-1106` |
| F15 | `reward_total` retained per episode but non-comparable across reward changes; residual caveat only | Medium | reported | `instruments.md:150-158` |
| F16 | Official verdict is a point sample with no uncertainty quantification | Medium | verified | `final_benchmark.py:174-183`; `scenario.md:24-32` |

---

## Cross-method convergence

All five methods independently land on the same two anchors.

1. **Panel identity collapse (RC1) is the dominant systematic bias.** Method 1
   found it by seed propagation and verified it; Method 2 found it as the missing
   gap between "panel score" and "task distribution"; Method 3 ranked it the
   top inversion; Method 4 made it the top false-positive pre-mortem; Method 5
   placed it in Measurement and Panel simultaneously.
2. **Selection on a single fixed panel (RC2) is the dominant stochastic bias.**
   It is what converts the collapse into an inflated number.

The ownership/fingerprint seam (RC4/RC5) is the second cluster: the harness's
own trust boundary is partly enforced by researcher-owned code and partly
asserted by tests that do not exercise the shipped tree.

## Adversarial validation experiments (designed, not run)

These are the cheapest experiments that would confirm or falsify each critical
finding. None has been executed.

1. **Panel-identity proof (F1).** Evaluate one frozen retained policy via
   `research_evaluation` seed 1000 / 200 episodes and via the official benchmark;
   expect an identical per-episode success vector.
2. **Selection-inflation estimate (F2).** Evaluate the top and median
   checkpoints from one run on >= 3 disjoint 200-episode seeds; report
   max-minus-mean and best-of-panel success versus pooled success.
3. **Proxy calibration (F3).** Correlate checkpoint `training_success` and
   `ep_rew_mean` against task-reference success across the recorded pool; the
   existing exp1/exp2 data already suggest near-zero late-run correlation.
4. **Fingerprint probe (F5).** Change only `TRAINING_TARGET_RADIUS_RANGE` in
   `environment.py`, then read `evaluation_semantics_fingerprint()`; expect no
   change if training-only isolation were installed, but expect a change today.
5. **Trust-path probe (F6).** Modify `training/observations.py`, run
   `tests/benchmark`, and observe the protected task contract change without any
   protected-path edit.
6. **Multi-panel decision rule (F4).** Designate `best_known` by worst-case
   success over >= 3 disjoint panels, then compare the official verdict to the
   single-panel selection.

## Limits of this audit

- The audit reasons over this branch's tree; it does not run campaigns or
  training.
- The target-identity claim is verified empirically; the outcome-identity claim
  follows by construction (identical targets plus deterministic artifact
  prediction) and was not executed against a policy.
- Historical cognitive-steering findings are drawn from the repository's own
  plan and decision documents and are marked `reported`, not re-derived here.
- Severity ranks impact on the validity of the official verdict, not effort to
  fix.
