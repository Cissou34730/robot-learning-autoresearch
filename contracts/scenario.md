# Task: two-joint arm, reach and hold

This file defines the official scientific task: the official situations, the
success criterion, the official assessment and the immutable limits of the
task. It does not define the research process or describe the research
instruments.

## Official task

A policy controls the two-joint arm of the repository. Each official situation
samples one target uniformly at a distance of 6–20 cm from the robot base, over
the full angular range. The end effector must enter a tolerance of 1 cm around
the target. Then it must stay continuously in this tolerance for 2 seconds.
The duration is authoritative. Under the current official control timing,
2 seconds correspond to 100 consecutive control steps.

A policy is a trained neural network that decides the motor command at each
control step. The saved runtime may construct the observation of the network
freely. But the saved runtime turns the network output into the motor command
of that step through a fixed transformation. This transformation may include
fixed-gain feedback toward a target that the network outputs. It cannot
include a planner, a trajectory generator, inverse kinematics or a robot
model. This definition gives the policy that the official assessment
evaluates.

## Success criterion

An episode succeeds only when the robot achieves the complete uninterrupted
hold. The campaign must produce a policy that succeeds in at least 98% of the
episodes of the official episode distribution.

## Official assessment

The official assessment evaluates one frozen policy on a fixed panel of 200
episodes from the official episode distribution. Each episode has at most 500
control steps. Each episode gives one success or one failure under the success
criterion above.

The official success percentage is the number of successful episodes divided by
200. The campaign reaches the goal when at least 196 episodes succeed, that is
at least 98%. This panel is distinct from the task-reference panel.
Development measurements are not combined with the official result.

## Fixed task limits

The human-authored robot and benchmark contracts fix the official robot, the
physics, the episode distribution, the interaction rules and the definition of
success.
