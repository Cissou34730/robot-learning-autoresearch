# No-Recipe Run 9: Results And Decisions

Maintainer report, 30 October 2026. All times are UTC.
Run numbers follow the sibling archive folders, not the earlier parallel rounds.
The [run ledger](../harness-experiment-log.md#no-recipe-next-run-work-30-october)
records runs 1-9 and the stopped attempts.

## Main Result

The quick-test wording produced smaller initial comparisons and two useful iterations.
All five campaigns completed recipe development and the original startup.
They then paused before inquiries, as the maintainer launch configuration required.
No official assessment ran. No campaign established the 196/200 official goal.

Campaign-1 was strongest: its mirror candidate scored 279/400 in research and
138/200 on the task reference. The matched plain candidate scored 110/400 and
54/200. The intervention improved both panels by about 42 percentage points.
This is a measured method improvement, not an official pass.

The batch requested 1,130,000 training steps across 20 variant runs.
Completed training added 1,144,832 steps after PPO rollout rounding.
Run 8 requested 2,600,000 steps across 20 variants before the maintainer stopped it.
Run 9 requested 56.5% fewer steps. Run 8 did not finish, so this is not a measured runtime saving.

Campaigns 2, 3 and 5 selected after one training operation, despite weak results.
The phase permits a weak provisional recipe. Completion does not establish that
the comparisons resolved the important alternatives or supplied enough learning exposure.

## Configuration And Changes

| Item | Run 9 configuration |
|---|---|
| Harness | Local `715ae5be2`, branch `feature/prepared-recipe-analysis` |
| Changed wording | Brief comparison plan and quick variant tests |
| Unchanged limits | No new training cap, minimum-first-run rule or fixed comparison count |
| Recipe | Per-slot `skeleton-v4-analyzed` references, based on `skeleton-v4` |
| Analysis | Immutable DeepSeek analyses from archived run 7, reused without new analyst calls |
| Analyst source | `opencode-go/deepseek-v4.1-flash`, reasoning `max` |
| Current PI, coder and reviewer | `gpt-6-luna`, reasoning `high` |
| Lifecycle | Reused analysis, recipe development, original startup, then pause before inquiries |
| Launch | Batch started at about 14:28:48, with launches about five seconds apart |
| End state | All five: phase `research`, no active session, no pending operation, official assessment null |

Implementation history, before this batch:

| Commit | Completed work |
|---|---|
| `d618312cf` | Recipe-development phase, full variant definition and coherent campaign instructions |
| `74d6fb697` | Independent parent candidates for transfer variants |
| `356c8a47c` | TUI and legacy report support |
| `87a2d938f` | Final compatibility repairs |
| `79e671a` | Separate skeleton commit and `skeleton-v4` tag, with a required training-step argument |
| `3e1d86b94` | Harness documentation state at the initial run 6 attempt |
| `5dc489ffe` | Variant write authorization and Windows path-case repair |
| `cb7ee1bbc` | Prepared per-slot references that preserve and reuse the completed analysis |
| `715ae5be2` | Comparison-plan and quick-test wording used for run 9 |

The [implementation record](../proposals/recipe-development-implementation-20261030.md)
preserves the design and offline validation history.
Its pending follow-up commit and no-live-run statements are historical.
They are not the current implementation status.

The last known origin revision is `cb7ee1bbc`.
The push attempt for the later local revision returned GitHub HTTP 500.
The maintainer then explicitly prohibited further pushes.
This report neither retries publication nor authorizes another campaign.

## Batch Identities

The live root is the sibling `robot-learning-campaigns-norecipe` folder.
Each row names its `campaign-N` slot and recorded recipe-source commit.

| Slot | Run 9 campaign ID | Recipe source |
|---|---|---|
| 1 | `d973b23f-c745-49d1-9b11-ce651006c14f` | `7ed34711ab96` |
| 2 | `9103b1a9-d22a-43af-8327-1393ee1f707e` | `fd125474b10d` |
| 3 | `17dba7bd-8577-4c8f-9cd9-cf68cbba3d9c` | `98279fa11007` |
| 4 | `b7e42218-7048-4207-bb48-3348c3e9cf51` | `922656bf168c` |
| 5 | `059e0ae2-8a9a-49d7-9756-f83a6196fd07` | `4a2c92b5cbdf` |

## Training Decisions

Each requested step count applies to every variant in that operation.
Seeds are training seeds. Fresh variants have no parent.
Completed steps below are new steps per variant, not a cumulative ancestry total.

| Slot / operation | Initialization / seed | Requested / completed steps per variant | Variants and parents |
|---|---|---|---|
| 1 / T1 | Fresh / 17 | 100,000 / 100,352 | `full_reward`, `reward_abl` |
| 1 / T2 | Fresh / 17 | 100,000 / 100,352 | `plain`, `mirror` |
| 2 / T1 | Fresh / 17 | 50,000 / 51,200 | `base`, `servo`, `scaled` |
| 3 / T1 | Fresh / 17 | 20,000 / 20,480 | `dense_torque`, `scaled_torque`, `credit_long` |
| 4 / T1 | Fresh / 17 | 50,000 / 51,200 | `direct`, `joint_pd`, `torque_scale`, `small_std` |
| 4 / T2 | Transfer / 17 | 100,000 / 100,352 additional | `direct_cont` from `T1:direct-checkpoint-51200`, `small_std_cont` from `T1:small_std-checkpoint-51200` |
| 5 / T1 | Fresh / 23 | 30,000 / 30,720 | `torque_pot`, `jpd_pot`, `sparse_success`, `low_std` |

| Slot | Variant runs | Total requested steps | Total completed new steps |
|---|---:|---:|---:|
| 1 | 4 | 400,000 | 401,408 |
| 2 | 3 | 150,000 | 153,600 |
| 3 | 3 | 60,000 | 61,440 |
| 4 | 6 | 400,000 | 405,504 |
| 5 | 4 | 120,000 | 122,880 |
| Total | 20 | 1,130,000 | 1,144,832 |

Campaign-4's transferred candidates each inherited 51,200 steps and added 100,352.
Each lineage therefore received 151,552 steps of training exposure.
The `checkpoint-100352` suffix names the continuation's new steps, not the full lineage.
The batch total counts parent training once, when T1 executed.

## Completed Measurements

Research evaluation, task-reference evaluation and PI-written diagnostics are distinct instruments.
Task-reference scores are not official assessments.
All candidates below use the completed step suffix in the training table.
The labels and operation IDs resolve the full candidate identity in the state record.

| Slot / operation | Candidate label | Instrument | Successes / episodes | Percent |
|---|---|---|---:|---:|
| 1 / M1 | T1 `full_reward` | Research | 0/400 | 0 |
| 1 / M1 | T1 `reward_abl` | Research | 114/400 | 28.5 |
| 1 / M3 | T2 `plain` | Research | 110/400 | 27.5 |
| 1 / M3 | T2 `mirror` | Research | 279/400 | 69.75 |
| 1 / M5 | T2 `plain` | Task reference | 54/200 | 27 |
| 1 / M5 | T2 `mirror` | Task reference | 138/200 | 69 |
| 2 / M1 | T1 `base` | Research | 37/400 | 9.25 |
| 2 / M1 | T1 `servo` | Research | 10/400 | 2.5 |
| 2 / M1 | T1 `scaled` | Research | 108/400 | 27 |
| 2 / M2 | T1 `scaled` | Task reference | 50/200 | 25 |
| 3 / M1 | T1 `dense_torque` | Research | 15/160 | 9.375 |
| 3 / M1 | T1 `scaled_torque` | Research | 0/160 | 0 |
| 3 / M1 | T1 `credit_long` | Research | 3/160 | 1.875 |
| 4 / M1 | T1 `direct` | Research | 2/100 | 2 |
| 4 / M1 | T1 `joint_pd` | Research | 0/100 | 0 |
| 4 / M1 | T1 `torque_scale` | Research | 0/100 | 0 |
| 4 / M1 | T1 `small_std` | Research | 6/100 | 6 |
| 4 / M2 | T2 `direct_cont` | Research | 55/160 | 34.375 |
| 4 / M2 | T2 `small_std_cont` | Research | 21/160 | 13.125 |
| 5 / M1 | T1 `torque_pot` | Research | 0/100 | 0 |
| 5 / M1 | T1 `jpd_pot` | Research | 0/100 | 0 |
| 5 / M1 | T1 `sparse_success` | Research | 0/100 | 0 |
| 5 / M1 | T1 `low_std` | Research | 3/100 | 3 |
| 5 / M2 | T1 `low_std` | Research | 7/400 | 1.75 |
| 5 / M2 | T1 `low_std` | Task reference | 5/200 | 2.5 |

Campaign-3 and campaign-4 have no task-reference measurement.
Missing measurements are not zero scores.
Campaign-4 M3's PI-written trajectory diagnostic reports 139/400 (34.75%).
That result is inside a module artifact, not the standard success-metric fields.
It remains diagnostic evidence and is not another protected or official score.

Other completed module diagnostics were campaign-1 M2, M4 and M6,
campaign-2 M2 and campaign-3 M2.
They do not supply additional standard research scores in the table.

## What Worked And Failed

### Campaign-1: Evidence Changed The Method

#### Reward: What Changed And Why It Matters

The accepted T1 scientific commit is `e0931e82e014f1fa5cc3341e0b69f88689b9a4b5`.
It defines these rewards:

$$
r_{\mathrm{full}} = 10(d_{\mathrm{prev}}-d) + 0.05 I_{\mathrm{inside}}
+ 50 I_{\mathrm{success}} - I_{\mathrm{hold\_break}} - 0.005\sum_i u_i^2
$$

$$
r_{\mathrm{abl}} = 10(d_{\mathrm{prev}}-d) + 50 I_{\mathrm{success}}
$$

Here, $d_{\mathrm{prev}}$ and $d$ are the previous and current end-effector distances to the target.
Each $I$ is an indicator for being inside the target, terminal success or a hold break.
The $u_i$ values are clipped action commands. The ablation sets the other three components to zero.

T1 compared the full reward with an ablation at matched exposure and seed.
Both candidates used fresh PPO training with seed 17 and 100,352 completed steps from a 100,000-step request.
Both used seven observations and two 64-unit tanh layers.
Their PPO settings matched: gamma 0.99, lambda 0.95, learning rate 0.0003, rollout length 2,048 and batch size 64.
Both normalized observations, but neither normalized rewards.

The last logged rolling reward terms give a reason to question the full reward's calibration:

| T1 candidate | Progress | Action | Inside / hold break / success | Policy standard deviation |
|---|---:|---:|---|---:|
| `full_reward` | +1.43 | -1.91 | 0 / 0 / 0 | 0.56 |
| `reward_abl` | +1.56 | 0 | 0 / 0 / 0 | 0.645 |

The full reward's action penalty exceeded its progress contribution in that logged window.
These training summaries do not establish how the deterministic policy moved or performed.
The ablation also logged zero training success, yet succeeded on 28.5% of M1's evaluation episodes.
M1 recorded 114 ablation-only successes and no full-reward-only successes on the paired episodes.
Its 114/400 against 0/400 supports selecting the tested reward bundle.
The comparison removed three terms together, so it does not identify which individual term caused the gain.

#### Mirror: The Network Learns In Reflected Coordinates

M2 then found a large angular difference in the ablation candidate's outcomes.
The PI used that evidence and the task's reflection symmetry to propose T2.
The accepted T2 scientific commit is `fa6e1a606658491caaba3613f24eb6408560439e`.
Its mirror interface chooses sign $s=+1$ when the target's $y$ coordinate is nonnegative, and $s=-1$ otherwise.
It multiplies joint positions, joint velocities and the relative end-effector/target vector's $y$ coordinate by $s$.
The relative vector's $x$ and $z$ coordinates stay unchanged.
It then multiplies the network's output commands by $s$ before applying them.
The interface resets its sign to $+1$.

Thus reflected targets share one input convention, with commands mapped back to the physical side.
The environment uses this interface during training and evaluation, not only after training.
The saved interface contains no inverse kinematics, planner or robot model. The network still chooses the commands.
Both T2 variants used the selected reward, fresh seed 17 and 100,000 requested steps.
Each completed 100,352 steps. Neither transferred weights from T1.

On M3's shared 400 episodes, mirror gained 169 successes and lost none against plain.
Both succeeded on 110 episodes. Mirror scored 279/400 against plain's 110/400, a 42.25-percentage-point gain.
M5's task reference also favored mirror: 138/200 against 54/200.
That gain was 42 percentage points.
These records support a real improvement for the tested trained candidates.
They do not establish training-seed robustness or complete task coverage.

This was a newly trained candidate comparison, not a frozen-weight diagnostic promoted into a candidate.
The coordinate change provides a mechanism for the gain. This single-seed comparison does not isolate every learning effect.

#### Remaining Work And Historical Context

The PI's next investigation concerns target geometry and reach failures, recorded in the
[M6 diagnostic](#evidence-and-limits).
Selected traces can motivate that investigation, but do not establish the cause of all remaining failures.
They also do not show that longer training cannot help.
The 138/200 result remains 58 successes short of the 196/200 goal. No official assessment ran.

The 69% task-reference score leads this batch, not all prior runs.
The [run 5 report](no-recipe-run-5-2026-10-30.html) records campaign-1's gain-0.1 candidate at 171/200 (85.5%) after 301,056 steps.
The current fresh mirror candidate received 100,352 steps. These are not matched training comparisons.

### Campaign-4: Continuation Changed The Ranking

The initial screen favored `small_std`: 6/100 against direct's 2/100.
The PI continued both candidates from their own parents rather than selecting on four wins.
After additional training, direct led 55/160 against 21/160.
The later startup diagnostic reported 139/400 for direct.

This is useful evidence for selective continuation and independent parents.
The PI changed its selection after further learning instead of treating the first ranking as final.
The small first panel did not establish the final ordering.
The selected recipe remained weak, and no task-reference result followed.

### Campaign-2: A Useful Screen, Not A Developed Recipe

Scaled output led the matched screen: 108/400 against base's 37/400 and servo's 10/400.
The task reference gave 50/200 for scaled.
The screen supplied a measured provisional choice, but no second training comparison followed.
The observed 25% task-reference rate remains far below the goal.

### Campaign-3: Early Evidence Remained Limited

Dense torque led at 15/160 after only 20,480 completed steps.
The PI selected it without further training during this batch.
The other outcomes do not show that those methods cannot learn with more exposure.
There was no task-reference result.

### Campaign-5: Selection Was Weakly Supported

Only low exploration scored successes in the first screen: 3/100 against zero for each alternative.
The exact paired sign test against the direct baseline gave p=0.25 in the PI record.
That comparison does not establish a reliable method ranking.
The startup panel gave 7/400 and the task reference gave 5/200.
No second training comparison followed.

Across the batch, short tests supplied useful evidence when later decisions remained responsive to it.
They did not by themselves determine how much learning a method needed.
The unresolved issue is the quality of that decision, not a missing mandatory score threshold.

## Time And Tokens

Elapsed time runs from the first launcher log entry to the final startup checkpoint.
It includes coding, review, Runner work and launcher overhead.
Final brief generation ended three to five seconds later.
The batch's final checkpoint was at 15:16:55.

Usage includes only rows whose `campaign_id` matches the current slot's ID.
All current rows use Luna/high. No reused analyst tokens enter these totals.
Input tokens include cache reads. Do not add cached tokens to input tokens again.
AIU is the recorded current Copilot usage, not a converted DeepSeek charge.

| Slot | Launcher start | Recipe-development checkpoint | Startup checkpoint | Elapsed | Input tokens | Output tokens | Luna AIU |
|---|---|---|---|---:|---:|---:|---:|
| 1 | 14:28:49 | 15:00:47 | 15:16:55 | 48m 06s | 7,384,512 | 147,160 | 21.682 |
| 2 | 14:28:55 | 14:46:23 | 14:57:34 | 28m 39s | 2,822,947 | 63,535 | 8.975 |
| 3 | 14:29:00 | 14:44:11 | 14:52:01 | 23m 01s | 2,588,911 | 64,958 | 9.065 |
| 4 | 14:29:05 | 14:51:38 | 14:58:35 | 29m 30s | 2,458,023 | 61,729 | 8.641 |
| 5 | 14:29:10 | 14:45:36 | 14:55:22 | 26m 12s | 1,854,581 | 65,503 | 8.193 |
| Total | | | | Not additive in parallel | 17,108,974 | 402,885 | 56.557 |

| Current role | Input tokens | Output tokens | Luna AIU |
|---|---:|---:|---:|
| PI | 12,542,100 | 217,227 | 34.361 |
| Scientific coder | 3,641,857 | 131,220 | 14.915 |
| Scientific reviewer | 925,017 | 54,438 | 7.281 |
| Reused analyst, new calls only | 0 | 0 | Not applicable |

The current records contain 15,429,526 cache-read tokens and 1,675,303 cache-write tokens.
These are usage fields, not separate additions to the input total.
The original run 7 analyses had a real token and time cost.
This report does not reconstruct that earlier cost or assign it zero.

## Comparison With Runs 7 And 8

The archived pending requests correct a mistaken handover attribution.
The 4.1-million-step, 18-variant figure belongs to run 7, not run 8.
Neither archive contains a completed training or measurement operation record.
Their pending training progress is `training_dispatched`.
Some execution could occur before interruption, but these records do not quantify completed exposure.

| Batch | First requested steps per variant, slots 1-5 | Initial variant counts | Total requested steps, including follow-up |
|---|---|---|---:|
| Run 7 | 500k / 200k / 100k / 200k / 200k | 3 / 4 / 4 / 4 / 3 | 4,100,000, no completed follow-up |
| Run 8 | 200k / 100k / 100k / 150k / 100k | 4 / 4 / 4 / 4 / 4 | 2,600,000, no completed follow-up |
| Run 9 | 100k / 50k / 20k / 50k / 30k | 2 / 3 / 3 / 4 / 4 | 1,130,000, including four follow-up variant runs |

Run 9's initial requests totaled 730,000 steps across 16 variants.
Its follow-up comparisons added 400,000 requested steps across four variants.
The initial exposure fell 71.9% relative to run 8, while the completed batch requested 56.5% less.
The comparison therefore includes later iteration, not just smaller first budgets.

Run 8 launcher logs span about 10m 36s to 11m 58s per slot and end with exit 130.
Those are interrupted durations, not completion times or training time budgets.
They cannot establish how long run 8 would take to complete both phases.
Run 9 completed both phases in 23-48 minutes per slot.

Runs 8 and 9 reused the same per-slot analyses.
However, PI choices also differed in variant sets and some training seeds.
The replay isolates the wording change at launch, not every realized experiment afterward.
The observed behavioral change is smaller comparisons with selective follow-up in two campaigns.
It does not yet establish a better final score or total completion cost than the interrupted run 8.

| Slot | Archived run 7 ID | Archived run 8 ID |
|---|---|---|
| 1 | `9388d200-ad1e-440e-a1e0-46c1eaf46592` | `e998d39b-322c-4d0d-bff3-dd11afdb47bd` |
| 2 | `11cda59e-7712-44db-9dde-a654f157cf35` | `026eafa7-facd-4ede-ac25-679214828718` |
| 3 | `aafc2365-9fa3-4e5a-8780-236a6b7de7bb` | `41072b1e-1975-4ed8-8391-43e7aceedabc` |
| 4 | `30d1c0a4-b8a5-490d-bae5-cc225bca448b` | `74beb698-b053-4f0f-973e-a97fd3d8816a` |
| 5 | `85187fdf-d496-4027-8caf-32e6492d2596` | `72ebb9b2-4357-4134-9d45-2930569c30b4` |

## Evidence And Limits

For each slot, the authoritative record is below that campaign root:

- `runner/state/research_state.json`: campaign identity, requests, results, parents, roles and checkpoints.
- `reports/session_usage/<campaign-id>.jsonl`: current-campaign tokens, roles, model settings and AIU.
- `reports/launcher/`: launch times, exit status and final brief completion.
- `campaigns/evaluations/<campaign-id>/`: local measurement and diagnostic artifacts.

Campaign-1's diagnostic artifacts include `python-module-M2-1-reward_strata_m1.json`,
`python-module-M4-1-reward_strata_m3.json` and
`python-module-M6-1-mirror_left_trajectory_diagnostic.json`.
Campaign-4's diagnostic artifact is
`python-module-M3-1-trajectory-diagnostics-T2-direct_cont-checkpoint-100352-400ep-seed300000.json`.
These files remain local. This documentation task does not export raw measurements.

Archives 1-8 remain under the sibling `robot-learning-campaigns-norecipe-runN` roots.
The [run 5 report](no-recipe-run-5-2026-10-30.html#history) is the source for
the maintainer history of runs 1-4 and the earlier interrupted DeepSeek attempt.
Exact early harness revisions and model settings not stated there remain unverified here.
The current audit checked archive campaign identities and operation counts.
It did not repeat training, evaluation or source-level mechanism tests.

All ten locks were free before this documentation work and again before adding this report.
Only the maintainer tracker section and this report changed.
No runtime, campaign file, branch, commit or push forms part of this update.
