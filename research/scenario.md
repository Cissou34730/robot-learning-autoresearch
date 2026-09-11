# Current scenario: two-joint arm reach-and-hold

This file defines the official scientific task, what counts as success, and the
immutable task boundary. It does not define the research process or describe
research instruments.

## Official task

A learned policy controls the repository's two-joint arm. Official situations
sample a target uniformly from 6–20 cm from the robot base over the full angular
range. The end effector must enter a 1 cm tolerance around the target and remain
continuously within it for 2 seconds. Duration is authoritative; under the
current official control timing this corresponds to 100 consecutive control
steps.

## Success criterion

An episode succeeds only when the complete uninterrupted hold is achieved. The
campaign objective is a learned policy that achieves at least 98% episode
success under the official task distribution.

## Official final assessment

The official final assessment evaluates one frozen policy over a fixed panel of
200 episodes sampled from the official task distribution. Each episode has at
most 500 control steps and contributes one success or failure under the success
criterion above.

The official success percentage is the number of successful episodes divided by
200. The objective is reached when at least 196 episodes succeed, corresponding
to at least 98%. This panel is distinct from the task-reference development
panel; development measurements are not combined with the official result.

## Immutable task boundary

The official robot, physics, task distribution, interaction semantics, and
success definition are human-owned. The Researcher must not redefine them to
make the result easier to achieve.

## Scientific freedom

The Researcher owns the learning method and training conditions, including the
training target distribution and curriculum. Training conditions may differ
from the official task; the resulting learned policy must still operate on the
unchanged official task.
