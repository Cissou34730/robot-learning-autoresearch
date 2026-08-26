# Autoresearch Report — Scenarios 1 & 2

*Autonomous RL experimentation on the two-joint reach arm, 2026-08-25/26.
Agent: ox-alpha (opencode/x-preview-f-free), driven by `run_research.ps1` +
`program.md`, one experiment per session, ratchet-protected git history.*

---

## Scenario 1 — "Reach": SOLVED (100%)

**Task**: touch a randomly placed ball (radius 6–20 cm, any angle) — 3 cm
threshold, 200-step episodes.

### The arc: 6% → 100% in 19 experiments

| Phase | Experiments | Result |
|---|---|---|
| Gold rush | 2, 3, 5, 6 | 6% → 48%: energy tax, reward-scale rebalance, smooth potential shaping |
| Scraping | 7, 8 | 53%, 55%: coefficient scaling exhausted |
| The wall | 9–14, 16, 18 | Five lever classes falsified: epochs, entropy range, shaping width, network width (×2 budgets), gSDE exploration |
| **Breakthrough** | **19** | **100%**: analytic IK deltas added to the observation |

### The three lessons that mattered most

1. **Reward scale balance beats reward magnitude** (exp 3, +26 pts): a huge
   one-shot success bonus made the value function unpredictable; shrinking it
   stabilized learning overnight.
2. **Shaping must be continuous** (exp 4 −, exp 5 +): a hard gate at 10 cm
   poisoned advantage estimates; the same idea as a smooth exponential
   potential worked immediately.
3. **Observation design dominates everything** (exp 19, +45 pts): when the
   network finally received *where the joints should go* (both inverse-
   kinematics solutions, precomputed), a plateau that had survived budget
   doubling, capacity doubling, and five reward rewrites dissolved instantly.
   Verified at 100% on fresh, never-evaluated targets.

### Honest caveat

Experiment 19 handed the network part of the solution analytically. That was
legal under the rules and mirrors real robotics practice — but it means the
task was solved with expert hints, not reinvented kinematics.

---

## Scenario 2 — "Reach and Hold": FAILED (plateau at 0%)

**Task upgrade**: stay within **1.0 cm** (was: touch 3 cm) for **2 seconds**
(100 consecutive control steps); episodes up to 500 steps; escalating dwell
reward; budget doubled to 120k steps. All scenario-1 scores retired.

### What happened

Five experiments, five different strategies, one identical outcome:

| # | Strategy | Result |
|---|---|---|
| 20 | Longer credit horizon (γ 0.99→0.995) | 0%, median 2.1 cm |
| 21 | Dwell bonus ×10 (0.5→5.0/step) | 0%, median 2.1 cm |
| 22 | Continuous "proximity rent" near target | 0%, mean 6.1 cm |
| 23 | Second sharper exponential at 1 cm scale | 0%, median 2.2 cm |
| 24 | Task-space velocity added to observation | 0%, median 2.0 cm |

Stagnation rule fired after five consecutive failures; loop stopped cleanly.

### Root cause: an unsampleable reward

Every experiment shared the same tell, visible from the first one:

- **Training rollouts: success rate exactly 0.** In 120k steps of noisy
  exploration, the stochastic policy *never once* held the 1 cm band long
  enough to sample the completion bonus.
- **Evaluation: hover at 2.0–2.1 cm.** The deterministic policy parks just
  *outside* the band — precisely where scenario 1 taught it to stop (the old
  3 cm habit), and where parking is value-neutral versus entering.

This creates a chicken-and-egg failure that reward redesign cannot break:

```
hold bonus exists → but is only earned after a 100-step clean hold
clean holds require precision → but exploration noise (std ≈ 0.8 torques)
makes 1 cm station-keeping statistically impossible during training
no sampled experience → value function assigns the hold zero predictive value
→ no incentive to develop precision
```

Experiments 21–24 were attempts to buy the way past this with denser rewards.
They could not work: **when the target event is never sampled, no amount of
magnification creates signal.** Meanwhile the deterministic policy's hover
point (~2 cm) appears to be a genuine precision floor set by the same noise
scale baked into how the policy is trained.

### What would plausibly fix it (recommendations, untested)

1. **Curriculum** (strongest candidate): start at 3 cm / 0.5 s hold and tighten
   automatically as success rate climbs. Guarantees the hold event is sampled
   early and often.
2. **Noise scheduling**: anneal exploration std aggressively, or condition std
   on distance-to-target (fine control = low noise). Directly attacks the
   precision floor.
3. **Auxiliary non-consecutive credit**: pay small reward per in-band step even
   if the band is left again — converts the all-or-nothing hold into partial
   signal from the very first episode.
4. **Budget**: secondary; exp 15 already showed asymptotes are real for this
   config, and 0%-runs finished their 120k steps without sampling success once.

### Process meta-lesson

Scenario 2's difficulty jump (touch → hold-still-precisely) crossed a
*qualitative* boundary: scenario 1 rewarded transient contact (achievable under
noise), scenario 2 rewards sustained precision (destroyed by noise). The loop's
falsification machinery worked perfectly — five clean refutations, best-so-far
never corrupted, diagnosis written automatically — but no reward engineering can
rescue a reward that training cannot experience. Difficulty increases need
curricula when they change what *kind* of behavior succeeds, not just its degree.

---

## The autoresearch loop itself: what the run proved

- **Ratchet integrity**: 24+ experiments, zero regressions persisted, every win
  committed with its score.
- **Honest measurement**: fresh-seed audits matched selection-set scores
  (54% vs 55%; 100% vs 100%) — no winner's curse detected.
- **Self-governance worked**: phantom-edit guard, stagnation stop, sentinel
  files, automatic revert-and-clean on failure — all exercised for real.
- **Cost**: ~15–25 min per iteration end-to-end; the decisive breakthroughs
  came from *observation design*, which was also the cheapest lever per point
  gained.

## State at close

- Best scenario-1 policy: 100% reach (models/reach-20260825-230136)
- Scenario 2: unsolved; codebase reverted to the scenario-1 champion config;
  full experiment history in `research/EXPERIMENTS.md` and `archive.md`
- Next session recommendation: implement the curriculum (experimenter decision,
  env changes required) before resuming autonomous optimization.
