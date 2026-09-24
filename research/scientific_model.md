# Scientific model of the robot and task

## Physical system and kinematics

**Established fact.** The robot is a planar serial arm with two revolute joints.
The shoulder rotates about the world \(z\) axis and the elbow rotates about the
same axis relative to the upper arm. The link lengths are 0.12 m and 0.10 m.
The arm lies at \(z=0.02\) m. The shoulder and elbow angles are both limited to
\([-170^\circ,170^\circ]\), and the reset state is
\(q=(0,0)\), \(\dot q=(0,0)\).

**Physical consequence.** With \(q_1\) the shoulder angle and \(q_2\) the
relative elbow angle, the end-effector position is

\[
x = 0.12\cos q_1 + 0.10\cos(q_1+q_2),\qquad
y = 0.12\sin q_1 + 0.10\sin(q_1+q_2),\qquad z=0.02.
\]

The reset posture is fully extended along \(+x\), so the end effector starts at
\((0.22,0,0.02)\). The unconstrained radial workspace is the annulus from
\(|0.12-0.10|=0.02\) m to \(0.22\) m. With the stated joint limits, the
smallest radial distance attainable at the limit is approximately 0.0277 m.
The official target radii, 0.06--0.20 m, therefore lie inside the reachable
workspace and avoid exact full extension.

**Established fact.** Targets are placed in the same horizontal plane as the
end effector, with angle uniformly sampled over the full circle and radius
uniformly sampled from 0.06 to 0.20 m. The target is a mocap body, and both the
target and visual ground plane have collisions disabled.

**Physical consequence.** The task is pure planar positioning rather than
contact, lifting, obstacle avoidance, or force interaction. The target
distribution is uniform in angle but not uniform in area. The radial margin
from 0.20 m to the 0.22 m maximum reach leaves a nonzero margin from the
straight-arm singularity, while inner targets require a substantially folded
posture.

## Kinematic alternatives and geometry

**Established fact.** For a target at polar coordinates \((r,\phi)\), the
standard inverse-kinematic elbow solutions satisfy

\[
\cos q_2=\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)},\qquad
q_1=\phi-\operatorname{atan2}(0.10\sin q_2,\,
0.12+0.10\cos q_2).
\]

The observation code explicitly constructs both \(q_2=+\arccos(\cdot)\) and
\(q_2=-\arccos(\cdot)\) solutions.

**Physical consequence.** Most targets have two geometrically valid elbow
configurations: the arm can bend on either side of the shoulder-to-target
line. The shoulder limit can remove one branch for some target directions, but
at least one branch remains available throughout the official radius and
angular range. Thus reaching is not just selecting a Cartesian direction; it
also involves selecting and stabilizing one of multiple joint-space postures.
Different joint paths can reach the same target and can have different
configuration-dependent inertia and sensitivity.

**Unknown.** The implementation does not determine which branch a learned
controller will use, whether it will switch branches during an episode, or
whether its path will pass close to a joint limit.

## Actuation, timing, and dynamics

**Established fact.** Each action has two components in \([-1,1]\). The
scenario action mapping is the identity, and each component is applied to a
MuJoCo motor whose gear is 5 and whose control range is \([-1,1]\). The motor
acts directly on the corresponding hinge; there is no commanded position,
velocity target, or explicit low-level servo in the model.

**Physical consequence.** The action is a bounded direct joint-torque command
(up to the motor's approximately \(\pm5\) hinge-torque scale), not a desired
joint angle. The shoulder actuator moves the whole downstream chain, whereas
the elbow actuator primarily changes the forearm relative to the upper arm.
Cartesian motion is therefore coupled and configuration dependent.

**Established fact.** MuJoCo advances at 0.002 s per physics step. One policy
action is held for 10 physics steps, giving a 0.020 s control interval and a
50 Hz decision rate. Each episode can contain at most 500 control steps
(10 seconds).

**Physical consequence.** The controller must shape a continuous trajectory
using piecewise-constant torques. It must account for motion occurring between
observations; an action is not an instantaneous displacement. Braking and
settling are part of reaching because residual joint velocity changes the
end-effector position after the next action.

**Established fact.** Gravity is explicitly zero. Each joint has damping 0.5
and armature inertia 0.01. The loaded model assigns approximately 0.099 kg to
the upper-arm body and 0.0525 kg to the forearm body; the resulting joint-space
inertia varies with configuration because the links are coupled.

**Physical consequence.** There is no gravitational sag or preferred
orientation. Damping dissipates velocity, and with zero velocity and zero
command any collision-free posture can remain stationary; there is no passive
stiffness that pulls the arm toward a target. A controller can consequently
settle by dissipating momentum and then use little or no torque, but it must
first avoid arriving with enough velocity to drift outside the 1 cm band.

**Unknown.** The XML and simulator specify the equations and parameters, but
they do not determine the actual transient trajectory, overshoot, settling time,
or torque sequence of a policy.

## Initial state and task geometry

**Established fact.** On reset, all generalized positions and velocities are
zero, MuJoCo is forwarded, and the target is sampled afterward at \(z=0.02\).
The target is fixed during an episode. The initial target-to-end-effector
distance is therefore determined by the sampled radius and angle; across the
official distribution it ranges from 0.02 m to 0.42 m.

**Physical consequence.** Every official episode starts outside the 0.01 m
success band, including the closest case. The controller must produce a
nontrivial approach before it can accumulate hold time. The initial arm pose is
not adapted to target direction, so initial motion may need to be clockwise or
counterclockwise and may use either elbow branch.

**Unknown.** The reset rules determine the physical initial condition but not
which direction or branch a policy will choose, nor how consistently it will
reach the target from different initial angular relationships.

## Observation and observability

**Established fact.** The policy receives an 11-element observation consisting
of, in order:

1. the two joint positions \(q\);
2. the two joint velocities \(\dot q\);
3. the three-dimensional end-effector-to-target displacement;
4. wrapped shoulder and elbow errors to the open-elbow inverse-kinematic
   solution; and
5. wrapped shoulder and elbow errors to the folded-elbow solution.

The observation is computed from exact simulator state. There is no sensor
noise, camera rendering, occlusion, contact sensing, or actuator-state
observation.

**Physical consequence.** The target-relative displacement directly supplies
distance and direction, while the joint state supplies the current posture and
velocity. Since the end-effector position is determined by the known joint
angles and link lengths, the target position in the task plane is recoverable
from the observation. The four IK errors make the two principal posture
alternatives explicit. The instantaneous observation is therefore sufficient
in principle for a Markov torque controller under this deterministic model;
end-effector velocity and acceleration can be derived from \(q,\dot q\) and the
known kinematics, even though they are not reported as separate fields.

The \(z\) displacement is always zero after reset because both objects remain
in the arm plane. The IK computation clips its cosine argument, which protects
the representation numerically even though official targets are reachable.

**Unknown.** This observability statement does not establish how a learned
policy interprets the branch features, angle wrapping, or velocity information.
It also does not reveal any internal memory or preprocessing used by a saved
policy runtime.

## Success semantics and required capabilities

**Established fact.** After each 0.020 s control interval, success distance is
the Euclidean distance between the end-effector site and the mocap target. A
sample is inside when the distance is at most 0.01 m. Inside samples increment
a consecutive hold counter; one outside sample resets that counter to zero.
The required hold is 2 seconds, exactly 100 control samples. An episode
succeeds only when this uninterrupted count is reached, and otherwise ends at
500 control samples.

**Physical consequence.** The task contains distinct phases even though the
benchmark reports one binary outcome:

- **Reach:** generate coordinated joint motion to enter a 1 cm Cartesian
  disk.
- **Converge:** reduce both positional error and residual velocity before
  crossing the disk boundary.
- **Stabilize:** keep the end effector inside the disk for 100 observations;
  transient oscillation or drift causes a complete loss of accumulated hold
  time.

The tolerance is Cartesian while actuation is joint-space, so the acceptable
joint-error region depends on the Jacobian and on posture. The same joint
perturbation can produce different Cartesian errors at different
configurations, and near poorly conditioned folded or extended configurations
small joint changes can have substantially different task effects.

**Established fact.** The official final assessment uses 200 fixed-seed
episodes from this distribution, and the objective is at least 196 successes
(98%). The benchmark evaluates the complete hold rather than merely the
closest distance achieved.

**Physical consequence.** A controller that reaches quickly but cannot stop,
maintain a posture, or recover from a boundary crossing is physically
different from one that converges more slowly and holds reliably. Time-to-first
entry alone is not equivalent to task completion.

**Unknown.** The contract does not determine the policy's distribution of
reach times, hold exits, final errors, branch choices, or success probability.

## Scientifically meaningful physical quantities

The quantities most directly tied to this embodied system are joint angles and
velocities; target-relative \(x,y\) error and its norm; end-effector speed;
joint torques and torque changes; the Jacobian and its conditioning at the
chosen posture; time to first enter the tolerance; longest uninterrupted
inside streak; number and timing of hold exits; distance margin to the 1 cm
boundary; and the selected inverse-kinematic branch. These distinguish
kinematic reachability, dynamic trajectory shaping, convergence, and sustained
stabilization without conflating them into a single success bit.

**Established fact.** The implementation records distance and hold state during
evaluation, while the simulator exposes the joint state, end-effector
position, and applied controls used to compute the observation and dynamics.

**Physical consequence.** Those state and control quantities can describe the
robot's actual motion and the geometric cause of a success or failure more
faithfully than reward or terminal outcome alone.

**Unknown.** No implementation-only analysis can say which of these quantities
will dominate observed behavior for a particular learned policy.
