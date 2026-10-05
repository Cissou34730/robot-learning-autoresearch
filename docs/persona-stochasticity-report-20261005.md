# Previous PI Persona Stochasticity Report

**Date:** 2026-10-05  
**Harness persona:** exact pre-`2971ccb` persona, restored in `ea35499`  
**Protocol:** three fresh campaigns, run sequentially with no harness change
between trials; stop before the first training request from inquiry `I1` is
accepted or dispatched.

## Executive finding

The previous persona produces materially variable scientific openings. Across
the three trials, startup selected training first twice and a physical
measurement first once. The first inquiry also varied: one run crossed the
stop boundary and dispatched a training attempt, one run performed a
measurement before a pending training request, and one clean run requested
training as its first inquiry operation.

This is evidence of stochastic variation, not a causal estimate of the
persona's effect. Only Trial 3 respected the requested stop boundary and
protocol cleanly. Trial 1 crossed the boundary, and Trial 2 modified
PI-owned code during startup. The experiment therefore demonstrates
qualitative instability, but does not support pooling the three runs as a
clean quantitative sample.

## Trials

| Trial | Campaign | Startup opening | First inquiry behavior | Validity |
|---|---|---|---|---|
| 1 | `4a73a283-c537-41d8-a4d8-ea23e48c1aaa` | Training first, followed by startup measurement | Training request `T2` was accepted and dispatched before the stop was observed; the run later advanced to `I2` | Invalid stop boundary |
| 2 | `d5a9984a-1928-4627-9d33-477274fa583e` | Modified `robot_learning/training/environment.py`, then trained and measured | Measurement first in `I1`, followed by a pending training request `T2` | Contaminated by PI-code change |
| 3 | `1fedd446-36b4-41cf-a38d-ff6ec9fcc90d` | Official-annulus physical characterization measurement `M1` before training | Training request `T1` was pending in `I1`; the campaign was stopped before Runner acceptance | Clean boundary-conforming trial |

All three trials used recipe source
`8256c8c7705a5080a722453b26eb13cd85b6e18f`. No fourth trial was launched.

## Trial 1

The campaign began with training, then performed a startup measurement and
entered goal review. Its first inquiry reproduced the familiar baseline
failure-attribution question. The requested stop boundary was missed: inquiry
training `T2` was accepted and dispatched, and the training attempt failed
before the external stop took effect. The launcher subsequently advanced to a
second inquiry.

This run is useful as an operational warning about the stop supervisor, but
not as a valid observation at the requested boundary.

## Trial 2

Startup changed `robot_learning/training/environment.py` to expand radius
coverage, then trained and measured. The first inquiry focused on the
negative-angle failure cluster, performed measurement `M2`, and reached a
pending training request `T2`. The external stop occurred before that request
was dispatched.

The run is not a clean persona trial because startup exercised the PI's
implementation freedom by changing scientific code. Its behavior is still
relevant to the question of what the previous persona permits: it can lead
to immediate method/code intervention rather than passive diagnosis.

## Trial 3

Startup selected a reproducible official-annulus physical characterization
measurement before any policy training. The measurement sampled 2,000 target
configurations and reported open- and folded-elbow joint-limit validity of
95.05% and 93.95%, respectively, with a minimum sampled Jacobian singular
value of approximately 0.0416 m and a maximum condition number of
approximately 5.28.

The resulting inquiry asked whether failures would be dominated by geometric
and branch coverage, finite-time reach and settling, or instability during
the uninterrupted hold. Its first action was a fresh baseline training
request. The campaign stopped with that request pending, before Runner
acceptance or training dispatch.

This is the only trial that fully satisfies the requested experiment
boundary.

## Interpretation

The previous persona does not deterministically force training first. It
allows at least three distinct startup styles under the same harness:

1. immediate baseline training followed by measurement;
2. implementation intervention followed by training and measurement; and
3. physical characterization before any training.

It also does not reliably prevent the first inquiry from selecting training.
In the clean trial, startup was scientifically useful, but the inquiry still
converted directly to a baseline training request once the physical
characterization had been completed.

The strongest conclusion is therefore about **variance**, not direction:
the previous persona leaves the PI's startup method selection highly open to
stochastic interpretation. It can produce useful plant-first work, but does
not make that behavior reproducible. The persona's broad authority also
permits early PI-owned implementation changes, as seen in Trial 2.

The comparison cannot isolate persona causality from one campaign using the
robotics-first persona. The earlier campaign with that persona also began
with training, while this three-run sample contains one clean
measurement-first opening. The result supports further controlled replication,
but it does not justify claiming that either persona is intrinsically
superior from this experiment alone.

## Protocol and evidence limits

- Trial 1 violated the requested stop boundary.
- Trial 2 violated the no-harness-change condition by changing PI-owned
  scientific code during the run.
- Trial 3 is the valid observation for the requested boundary.
- The three launcher logs are retained at
  `C:\Users\cyril.beurier\AppData\Local\Temp\robot-trial1.log`,
  `robot-trial2.log`, and `robot-trial3.log`.
- Exact AIU and token totals were not recoverable from the durable campaign
  artifacts. Wall-clock launcher intervals were approximately 41 minutes,
  34 minutes, and 18 minutes for Trials 1-3, respectively.
- No official assessment was requested and no campaign conclusion was
  recorded.
