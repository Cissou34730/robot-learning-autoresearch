# Scientific model of the robot and task

## System interpretation

This is a planar two-link manipulator whose controller must move a point
end-effector to a stationary target and then keep that point inside a small
disk for a sustained interval. The task is not contact manipulation: the target
is a kinematic mocap reference, and success is determined by the Euclidean
distance between the end-effector site and the target center. The scientifically
important transition is therefore from transient interception to low-velocity,
closed-loop regulation. A policy that reaches the target but crosses the
tolerance boundary once has not solved the task.

## Morphology and kinematics

The shoulder and elbow are revolute joints about the world \(z\)-axis. The
upper arm length is \(l_1=0.12\) m and the forearm length is \(l_2=0.10\) m.
The link centerlines and the end-effector site lie in the horizontal plane
\(z=0.02\) m. With joint coordinates \(q_1,q_2\), the site position relative
to the base is

\[
p(q)=\left[
l_1\cos q_1+l_2\cos(q_1+q_2),\
l_1\sin q_1+l_2\sin(q_1+q_2),\
0.02
\right].
\]

Both joints are limited to \([-170^\circ,170^\circ]\). Ignoring those angular
limits, the centerline workspace is the annulus from
\(\lvert l_1-l_2\rvert=0.02\) m to \(l_1+l_2=0.22\) m. The configured elbow
limit raises the minimum centerline radius to approximately
\[
\sqrt{l_1^2+l_2^2+2l_1l_2\cos(170^\circ)}\approx0.0277\ {\rm m}.
\]
The official target radii, 0.06--0.20 m, are inside this workspace; angular
joint limits still couple feasible radius and direction. Link capsule
thickness is visual/physical geometry, but the task measures the site
position, not the capsule surface.

For a target \((x,y)\), the two ordinary inverse-kinematic branches use

\[
\cos q_2=\frac{x^2+y^2-l_1^2-l_2^2}{2l_1l_2},
\qquad
q_1=\operatorname{atan2}(y,x)-
\operatorname{atan2}(l_2\sin q_2,l_1+l_2\cos q_2).
\]

The positive and negative choices of \(q_2\) are the elbow-open and
elbow-folded alternatives. The observation explicitly computes errors to both
branches. A branch may become unavailable near a joint limit even when the
other branch remains usable.

The planar Jacobian has columns
\[
\left[
 -l_1\sin q_1-l_2\sin(q_1+q_2),\
 l_1\cos q_1+l_2\cos(q_1+q_2)
\right]^T
\]
and
\[
\left[
-l_2\sin(q_1+q_2),\
l_2\cos(q_1+q_2)
\right]^T.
\]
Its determinant is \(l_1l_2\sin q_2\). Thus the manipulator loses instantaneous
Cartesian rank when the links are collinear, and becomes poorly conditioned
near that configuration.

## Actuation, dynamics, and timing

The two actuators are MuJoCo hinge motors. The policy supplies two normalized
commands in \([-1,1]\); the identity policy action mapping passes them directly
to the actuators, whose gear value is 5. They are direct joint-torque
commands, not position or velocity targets, so the policy must create its own
feedback behavior. The command is held constant for ten simulator integrations:
the model timestep is 0.002 s and the control interval is therefore 0.020 s.
The 2 s hold is evaluated at 100 such control boundaries.

Gravity is explicitly zero. Each joint has damping 0.5 and armature 0.01.
Masses and link inertias are not specified as body parameters in the XML; they
are inferred by MuJoCo from the capsule geometry and compiler defaults. The
resulting inertia, actuator torque saturation, damping, and joint-limit
constraints determine the transient response. There is no target contact force
or mechanical stop at the target, and the disabled plane does not support or
perturb the arm. At a stationary configuration with zero velocity, zero
command can be an equilibrium because gravity is absent, but it is not a
position hold: disturbances and residual velocity must be corrected by
feedback, while damping only dissipates motion.

The fixed 20 ms zero-order hold makes the physical plant evolve between
observations. A command can therefore produce appreciable position and
velocity change before the next correction. Near a Jacobian singularity, joint
torque has weak or directionally coupled Cartesian effect; near a joint limit,
constraint forces can further change the response. Saturation and damping make
the same action-state relationship dependent on velocity and configuration,
not just on instantaneous positional error.

## Initial state and target geometry

Every official reset sets both joint positions and velocities to zero, then
places the target at the sampled radius and angle in the arm plane. The arm
starts fully extended at
\(p(0,0)=(0.22,0,0.02)\) m, while every official target is at most 0.20 m
from the base. Consequently the initial state is on the outer workspace
boundary and is generally not a solution. It is also a kinematic singularity:
the first-order effect of either joint is tangential there, whereas moving
inward requires first bending the elbow (or otherwise leaving the singular
configuration). This makes initial convergence a coupled trajectory problem,
not a simple Cartesian translation.

The official implementation samples angle uniformly over \([-\pi,\pi)\) and
radius uniformly over [0.06, 0.20] m, rather than sampling area uniformly.
The target is stationary and has no physical collision interaction. The
end-effector must be within 0.01 m of its center at every one of 100
consecutive control observations. Any outside sample resets the consecutive
counter; an episode can run for at most 500 control steps (10 s). The official
assessment uses 200 fixed-distribution episodes and requires at least 196
complete holds.

## Observation, control, and outcome

The policy receives an 11-element float observation consisting of the two joint
positions, two joint velocities, the three-dimensional end-effector-to-target
vector, and four wrapped angular errors to the two inverse-kinematic branches.
Because both points are always in the same plane, the relative \(z\) component
is structurally zero. The target position is not presented as a separate
absolute sensor value, but the current joint state determines the current site
position and the relative vector consequently determines the target location.
The branch errors provide a redundant, task-oriented representation of
configuration error and expose the elbow-configuration ambiguity.

There is no configured observation noise, target motion, actuator state, or
observation delay. The observation is read after the ten physics substeps
driven by the previous command. The hold counter, episode clock, previous
distance, and whether a prior hold was interrupted are not observed. The
physical state \((q,\dot q)\) together with the fixed target is sufficient for
the deterministic plant dynamics, but the unobserved hold counter matters to
the episode outcome rather than to the instantaneous mechanics.

The action changes joint accelerations through the coupled inertia, damping,
armature, and actuator limits; those accelerations change the next joint state
and end-effector error. The resulting distance is the task predicate. Thus
reaching requires selecting a viable inverse-kinematic basin and shedding
enough motion to enter the tolerance, while holding requires maintaining a
stable error/velocity relationship despite discrete control and the nonlinear
Jacobian. The same control authority that enables fast convergence can create
overshoot or boundary crossings during the hold.

## Coupled capability and failure classes

The complete behavior requires four physically coupled capabilities:

1. **Workspace acquisition:** leave the fully extended singular state and
   generate the required angular and radial displacement within the torque and
   time limits.
2. **Trajectory selection:** approach through one of the valid elbow branches
   without exhausting joint-limit margin or entering a poorly conditioned
   configuration.
3. **Convergence:** reduce Cartesian error and joint velocity together. Small
   position error with residual velocity is not a successful arrival.
4. **Regulation:** keep the end-effector inside the 1 cm disk for 2 s. A
   one-step excursion is a complete hold failure even if the average error is
   small.

These mechanisms create distinguishable physical failure classes: unreachable
or limit-constrained configurations; slow or poorly directed escape from the
initial singularity; branch or angle-dependent trajectory errors; overshoot
before first entry; and hold interruptions caused by residual velocity,
oscillation, saturation, or insufficiently stable feedback. A high minimum
distance does not establish success, and a long cumulative time inside the
tolerance does not substitute for one uninterrupted interval.

## Scientifically meaningful physical quantities

Across a complete episode, the quantities most directly tied to mechanism are
joint position and velocity trajectories; commanded and realized actuator
torques; torque saturation and damping losses; end-effector position, velocity,
and target-relative radial/tangential error; Jacobian singular values and
joint-limit margins; selected inverse-kinematic branch and branch switching;
time to first tolerance entry; longest consecutive in-tolerance interval;
entry velocity; distance excursions and hold interruptions; and these measures
stratified by target radius and angle. Together they separate reachability and
trajectory generation from convergence and sustained regulation.

## Registers

### Established facts

- The robot has two planar hinge degrees of freedom with 0.12 m and 0.10 m
  links, \([-170^\circ,170^\circ]\) joint ranges, zero gravity, 0.5 damping,
  0.01 armature, and motor gear 5.
- The initial state is \(q=(0,0)\), \(\dot q=(0,0)\); the target is stationary,
  sampled in the same plane with radius 0.06--0.20 m and full angular range.
- Actions are two clipped normalized motor commands, held for ten 0.002 s
  MuJoCo steps. The official control interval is 0.020 s.
- Success is distance at most 0.01 m for 100 consecutive control steps, within
  a 500-step episode. The final panel has 200 episodes and the objective is
  196 or more successes.
- The observation contains \(q\), \(\dot q\), relative end-effector/target
  position, and errors to both analytic inverse-kinematic branches.

### Physical consequences

- The starting posture is maximally extended and singular, so inward motion
  must first create a bent configuration; Cartesian reach and control
  authority are configuration dependent.
- The task has no contact or gravity-based support. Holding is active
  regulation of a free planar mechanism, not passive placement against a
  surface.
- Multiple elbow configurations can solve a target, but joint limits and the
  target direction can remove one branch. Branch choice changes the Jacobian,
  required motion, and available limit margin.
- Position accuracy and velocity regulation cannot be treated independently:
  momentum during a 20 ms command interval can carry the site outside the
  tolerance after apparent arrival.
- Episode success is governed by the worst continuity event in the hold, not
  by average distance, cumulative in-tolerance time, or final distance alone.

### Unknowns

- The compiled MuJoCo masses, center-of-mass locations, full link inertias,
  and the exact effective inertia seen at each configuration are not explicit
  in the human-authored XML.
- The quantitative transient limits—settling time, maximum reachable
  displacement within 500 controls, overshoot under saturation, and damping
  time constants—are not established analytically from the source alone.
- The practical basin sizes and costs of the elbow-open and elbow-folded
  trajectories, including where joint-limit or singularity effects dominate,
  are unresolved.
- It is not yet known which target radii and angles are hardest for the
  coupled reach-and-hold dynamics, or whether failures will be dominated by
  initial acquisition, convergence velocity, or hold interruptions.
- The policy's effective use of the 11 observations, its branch-selection
  consistency, and its robustness to the discrete control interval are
  campaign quantities, not pre-campaign facts.
