# Current scenario: two-joint arm reach-and-hold

This file defines the current scientific problem and its immutable boundary.
The protocol and available instruments are defined separately in
`research/program.md` and `research/instruments.md`.

## Objective

The robot must reach targets sampled uniformly from 6–20 cm from its base over
the full angular range. Its end effector must enter a 1 cm tolerance and remain
continuously within it for 2 seconds, currently 100 control steps under the
official timing. Success requires at least 98% over the fixed 200-episode
official benchmark.

Only the human-owned official benchmark can declare this objective reached.

## Robot and task

The task uses the repository's two-joint arm. Its geometry, joints, actuators,
actuator limits, action semantics and control limits are fixed. The MuJoCo
timestep, frame skip, reset behavior, initial state, target distribution,
success tolerance, hold duration, episode horizon and success computation are
also fixed.

These properties define the physical problem. A learned policy may preprocess
its observations or actions, but it must control the same robot under these
semantics.

## Human-owned panels

The official benchmark evaluates the objective on its fixed 200-episode panel.

The task-reference panel is a separate fixed 200-episode development panel with
its own seed. It measures the same 6–20 cm uniform target radius, full angular
range, 1 cm tolerance, 2 seconds of continuous hold, official control timing and
episode horizon. Its result is not the objective verdict.

The panels, their seeds, distributions, episode counts, timing and success rules
are immutable parts of this scenario.

## Mutable scientific choices

Training conditions and learned-policy design are outside the fixed task
boundary. They may differ from the official task provided the resulting policy
still controls the official robot without redefining its physics or objective.

Research measurements are development evidence. They do not alter the fixed
objective or declare it reached.
