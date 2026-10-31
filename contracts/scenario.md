# Task: two-joint arm, reach and hold

## Purpose

Develop a trained neural policy that controls the arm through the complete
reach-and-hold task. The required capability covers the official target
distribution, not a selected subset.

This file defines the task, known system facts, policy limits and starting
recipe. It does not prescribe a learning method or research process.

## Robot and control interface

The simulated robot has two revolute joints: shoulder and elbow.
Both joint axes are parallel. The arm moves in a horizontal plane.
The upper arm is 0.12 m long. The forearm is 0.10 m long.
Each joint has limits of -170 to 170 degrees.

The MuJoCo model has zero gravity. Each joint has damping of
0.5 N·m·s/rad and armature inertia of 0.01 kg·m².
The motor gear is 5. Each motor command is bounded between -1 and 1.

The simulation step is 0.002 seconds. One control step contains ten
simulation steps, so the policy supplies a command every 0.02 seconds.
That command remains fixed during those ten simulation steps.

Joint positions and velocities use radians and radians per second.
Positions and distances use metres. Joint state, end-effector position
and target position are available to the scientific code.
The robot definitions are authoritative for physical properties.

## Official task and assessment

Each official episode samples one target with radius uniformly distributed
from 0.06 to 0.20 m around the robot base, over the full angular range.
The target remains fixed during the episode.

The end effector must enter a tolerance of 0.01 m around the target.
It must then remain continuously inside that tolerance for 2 seconds.
The duration is authoritative. At the official control timing, this requires
100 consecutive control steps. An interrupted hold does not satisfy the task.

The official assessment evaluates one frozen policy on a fixed panel of
200 episodes. Each episode has at most 500 control steps and gives one
success or failure. The campaign reaches its goal with at least 196 successes.
The task-reference panel is separate. Development results do not contribute
to the official score.

## Policy and fixed limits

The policy is a trained neural network that decides the motor command
at each control step. Its saved runtime may construct network observations
freely. A fixed transformation converts the network output into that step's
motor command. This transformation may use fixed-gain feedback toward a
network-output target. It cannot contain a planner, trajectory generator,
inverse kinematics or robot model.

The human-authored robot and benchmark contracts fix the official physics,
episode distribution, interaction rules and success criterion.
The protected evaluators define the official episode start and target placement.

## Starting recipe

The campaign starts with scientific code in robot_learning/.
Its docstrings define the training, evaluation and saved-runtime interfaces.
The starting method uses joint positions, joint velocities and relative
end-effector position as observations. Network output is the motor command.
Training uses Stable-Baselines3 PPO with observation normalization.
The recipe supplies training parameters, periodic checkpoints and reward logging.

The recipe has no reward until you implement one. The scientific model
proposes a first reward. Every part of the starting method is a design choice
that you can change, not a property of the robot or an official task requirement.

The research environment starts at zero joint positions and velocities,
with targets in the arm's plane. These are starting-recipe choices.
They do not establish the protected evaluators' episode-start conditions.
