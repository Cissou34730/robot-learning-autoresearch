# Why recipe development does not end: root-cause analysis

Date: 3 November 2026. Author: maintainer session. Audience: maintainer.

Scope: the three `harness` campaigns launched at 13:32 on 3 November
(inherited recipe v4, restored run-14 prompts, isolated delivery), compared
with the no-recipe campaigns of runs 14, 15, 18 and 19. Times in the tables
are UTC unless marked local. This is an analysis of recorded evidence. It does
not propose changes.

## Bottom line

Recipe development (RD) stalls in a **chain trap**:

1. The PI's best RD result almost always comes from a **transfer chain**:
   a policy trained, then continued under changed settings.
2. Isolated delivery cannot carry that policy. Startup retrains the delivered
   source **from scratch**.
3. So the PI tries to rebuild the chain as a recipe that learns from scratch,
   and tests it with **one training seed** at a time.
4. Seed-to-seed variation is as large as, or larger than, the design effects
   being tested. A from-scratch run can land far below the chain by chance.
5. Nothing in the harness tells the PI when the recipe is good enough
   ("You judge whether the recipe is adequate for delivery"). The chain's
   score becomes the implicit bar, and the PI keeps iterating.

RD ends quickly only when a single from-scratch run happens to match the
chain (harness campaign 2, no-recipe R15 c1/c3/c4, R19 c2). It does not end
when it does not (harness campaign 1, no-recipe R15 c2, R18 c2).

The trap does not exist without isolation: in run 14 the chain itself went to
startup, and RD took 23-51 min instead of 83-160 min.

## What happened on 3 November

| Campaign | RD length | Best RD result | How it was obtained | From-scratch rebuild | Outcome |
|---|---|---|---|---|---|
| 1 `50ac690b` | 115 min, not ended | 390/400 | chain: 100k full-range, then 100k mixed-range | 213-225/400 (static), 268/400 (staged), new seed pending | stopped in RD |
| 2 `40e24676` | 89 min, delivered | 389/400, 195/200 TR | chain first (376/400), then **one fresh 100k run matched it** (seed 45) | succeeded first time | startup retrain 374/400, 192/200 TR |
| 3 `85c86117` | 107 min, not ended | 266/400 | chain: 50k full-range, then 50k continuation | not reached yet | stopped in RD |

TR = protected task-reference panel (200 episodes). Research panel = 400 episodes.

Time spent in RD (minutes):

| Campaign | Training | Measurement | PI reasoning and coding |
|---|---|---|---|
| 1 | 41 | 35 | 39 |
| 2 | 26 | 26 | 37 |
| 3 | 25 | 56 (one measurement took 34) | 27 |

## The mechanism, step by step

### 1. Chains are the natural way to improve in RD

The training instrument lets every variant continue from its own saved
checkpoint, and the restored RD text says so ("Each variant can continue from
its own saved training checkpoint"). Continuing a learned policy is cheaper
and usually scores higher than training again from zero. All three PIs built
chains within the first hour.

### 2. Isolation turns the best result into something that cannot be delivered

Delivery carries only canonical source and parameters. The RD text states that
startup "does not receive … training checkpoints, optimizer state or
normalization state". The PIs draw the logical conclusion:

- Campaign 1, 13:43: "Startup receives no weights, optimizer state or
  normalization state, so fresh learning with the delivered recipe must be
  demonstrated."
- Campaign 2, 13:25: "The strongest evidence is still the two-stage pattern …
  so I'll test that as a fresh, reproducible curriculum."
- No-recipe R19 c1, T4 rationale: "tests whether the recipe learns from
  scratch rather than only succeeding after transfer from T2."

RD therefore contains a second research problem: rebuild the chain as a
from-scratch recipe and show it learns. The harness does not state this as a
rule. It follows from isolation.

### 3. One seed cannot tell a bad recipe from an unlucky run

The same unchanged inherited recipe, at about 50k steps, scored:

| Campaign 2 | Campaign 1 | Campaign 3 |
|---|---|---|
| 315/400 | 245/400 | 92/400 |

The same full-range change, trained from scratch for 100k steps, scored
389/400 in campaign 2 and 266/400 in campaign 1. No-recipe runs show the same
spread (R19 c2: 189 vs 35/400 for one recipe on two seeds; R15 c1: 145, 97
and 0 out of 160).

The training instrument gives all variants of one operation the **same
seed**. A seed replicate needs a separate operation (7-12 min of training plus
measurement), so PIs compare designs on one seed and add a caveat ("one seed
cannot establish …") instead of replicating. Campaign 1 started its first
seed replicate only at 14:36, 1 h 52 into RD, after three from-scratch
rebuilds had failed.

### 4. Nothing defines "good enough"

The only completion rule is "You judge whether the recipe is adequate for
delivery." With a chain at 98%, a from-scratch recipe at 56-73% does not look
adequate, so the PI keeps trying (campaign 1: static mix, staged schedule,
continuation of the staged run, new seed). The chain's score is a
single-seed result itself, so the bar may be unreachable on most seeds.

In run 14 this question did not arise: the PI chose the strongest candidate,
chain or not, and startup continued from it.

### 5. Conditions that make it worse

- **Short screening on the inherited recipe.** Campaign 3 screened every
  variant at 50k steps on a seed where the unchanged recipe only reached
  92/400. All four variants looked worse; full-range training looked like a
  trade-off (76/400). In campaign 2 the same full-range idea reached 389/400 at
  100k. The analyst and RD text ask for "quick learning tests" and "short
  training tests". These were written for the no-recipe skeleton.
- **Measurement cost.** Measurement took as long as training or longer in
  12 of 14 no-recipe RDs and in campaign 3 (56 vs 25 min). One 8-checkpoint,
  400-episode measurement took 34 min.
- **Load.** Five campaigns ran at once (three `harness`, two no-recipe), the
  current maximum.

## Correlation with the no-recipe campaigns

| | Run 14 (not isolated) | Isolated runs 15, 18, 19 |
|---|---|---|
| RD length | 23-51 min, all ended | 83-124 min when ended; 3 of 9 not ended (R15 c2 160 min, R18 c2 101 min, R19 c1 108+ min) |
| Best RD result from a chain | 5 of 5 | 6 of 9 |
| From-scratch rebuild needed | no; the chain went to startup | yes, whenever the best was a chain |
| Rebuild matched the chain | n/a | 4 of 5 attempts (R15 c1 twice, R15 c3, R19 c1); R18 c1 lower (119 vs 142/400) but delivered |
| Explicit seed replicates | none | 7 of 9 |
| Startup first action | continue from RD candidate (4 of 5 trained nothing) | always a 120k from-scratch retrain |
| Official assessment | 4 of 5 passed | none requested yet |

What carries over to the inherited recipe:

- **The chain trap is general.** It appears in both scenarios and only under
  isolation. The two no-recipe RDs that never ended (R15 c2, R18 c2) were both
  holding an un-rebuilt chain when stopped.
- **The isolation cost is general.** RD is 2-3 times longer in both scenarios.
- **The rebuild failed only on the inherited recipe** (campaign 1). On the
  skeleton, rebuilds matched the chain in 4 of 5 attempts. Whether the inherited
  recipe is harder to rebuild, or campaign 1 had unlucky seeds, is not
  established; its seed replicate (T6) was still running when the campaign
  was stopped.
- **Startup retrains reproduce RD well when RD ended on a from-scratch
  result**: R15 c1/c4 400/400 and 200/200; R15 c3 194/200 then 200/200;
  harness campaign 2 192/200 against 195/200 in RD.

## What is established and what is not

Established by the records:

- Isolation makes chained RD results undeliverable, and PIs respond by
  rebuilding them from scratch (quotes above).
- Seed variation of this size exists in both scenarios, and the instrument
  forces one seed per operation.
- RD ended in every case where a single from-scratch run reached the chain's
  level, and did not end where it stayed below.
- RD is 2-3 times longer with isolation than in run 14.

Not established:

- That the restored wording caused or prevented any of this. Campaign 2 used
  the same text and delivered in 89 min.
- Why campaign 1's from-scratch rebuilds failed (recipe design or seed).
- Whether longer screening would have changed campaign 3's conclusions.

## Secondary finding

After an accepted `checkpoint`, the reply to the PI always reads "No
operation has completed in the current session"
(`runner/launcher/operation_bridge.py:204` calls `latest_session_result` on
a state whose session is already closed). PIs in 11 no-recipe campaigns and
harness campaign 2 quoted it; harness campaign 2 wrote "I cannot verify that
the session record was saved". It does not block RD, but it is misleading.

## Evidence

- Harness campaigns: `robot-learning-campaigns\campaign-1..3`
  (`campaigns\results.jsonl`, `reports\tui_observations\<id>.events.v2.jsonl`);
  campaign 2's RD archive under
  `.recipe-development-private\cd6ff06dad610e485d85f018\`.
- No-recipe facts per campaign (operations, seeds, quotes):
  `robot-learning-campaigns-norecipe-run14`, `-run15`, `-run18`, and the live
  `robot-learning-campaigns-norecipe` (run 19).
- Harness version under test: `13b6d576d` (`harness`), `88cc649c2`
  (`experiment/no-recipe`).
