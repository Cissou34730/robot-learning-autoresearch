# Task: two-joint arm, reach and hold

This file defines the task: the official situations, the success criterion, the
official assessment and the fixed limits of the task. It does not define the
research process or the instruments.

## Official task

A policy controls the two-joint arm of the repository. Each official situation
samples one target uniformly at a distance of 6–20 cm from the robot base, over
the full angular range. The end effector must enter a tolerance of 1 cm around
the target. Then it must stay in this tolerance without interruption for
2 seconds. The duration is the requirement. With the current official control
timing, 2 seconds are 100 consecutive control steps.

A policy is a trained neural network that decides the motor command at each
control step. The saved runtime can build the observation of the network
freely. The saved runtime turns the network output into the motor command of
that step with a fixed transformation. This transformation can include
fixed-gain feedback toward a target that the network gives. It cannot include a
planner, a trajectory generator, inverse kinematics or a robot model. This
definition gives the policy that the official assessment evaluates.

## Success criterion

An episode succeeds only when the complete hold occurs without interruption.
The campaign must produce a policy that succeeds in at least 98% of the
episodes of the official episode distribution.

## Official assessment

The official assessment evaluates one frozen policy on a fixed panel of 200
episodes from the official episode distribution. Each episode has at most 500
control steps. Each episode gives one success or one failure under the success
criterion above.

The official success percentage is the number of successful episodes divided by
200. The campaign reaches the goal when at least 196 episodes succeed, that is
at least 98%. This panel is different from the task-reference panel. The
official result does not include development measurements.

## Fixed task limits

The human-authored robot and benchmark contracts fix the official robot, the
physics, the episode distribution, the interaction rules and the definition of
success.
