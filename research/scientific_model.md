# Scientific model of the two-joint reach-and-hold system

This is a pre-campaign model. It separates facts fixed by the human-authored
task and simulator from physical implications inferred from them. No policy
behavior or performance is assumed.

## Established facts

### Robot morphology and kinematics

**Repository fact.** The robot is a planar serial arm with two revolute joints.
Both joint axes are the world/body \(z\)-axis, so the generalized coordinates are
the shoulder angle \(q_1\) and the elbow angle \(q_2\), in radians. The upper arm
length is 0.12 m and the forearm length is 0.10 m. The end-effector site is at
the forearm tip. The arm plane is \(z=0.02\) m; the base is fixed at the
origin.

**Repository fact.** Both joints have active limits of \([-170^\circ,170^\circ]\).
With the base frame as origin, the end-effector position is
\[
p(q)=\begin{bmatrix}
0.12\cos q_1+0.10\cos(q_1+q_2)\\
0.12\sin q_1+0.10\sin(q_1+q_2)\\
0.02
\end{bmatrix}.
\]
The unrestricted two-link workspace is an annulus from 0.02 m to 0.22 m,
with the usual loss of manipulability at the fully folded and fully extended
boundaries.

**Repository fact.** At reset, \(q=(0,0)\) and \(\dot q=(0,0)\), so the
end-effector starts at \((0.22,0,0.02)\). The target is a static mocap body
whose \(z\) coordinate is set to the end-effector plane. The official target
radius is sampled from 0.06--0.20 m and its angle spans the full circle. The
implementation samples radius and angle independently and uniformly.

### Actuation, timing, and simulated dynamics

**Repository fact.** Each action has two components in \([-1,1]\), is mapped
unchanged to physical commands, and is held for 10 MuJoCo steps. The physics
timestep is 0.002 s, giving a 0.020 s control interval (50 Hz) and a 0.010 s
physics interval (500 Hz). The compiled model uses MuJoCo's default Euler
integrator.

**Repository fact.** Each joint is driven by a direct motor actuator with gear
5 and no explicit actuator dynamics, force limit beyond the control range, or
action-rate limit. Thus a saturated command produces a joint generalized
actuator torque of magnitude 5 in the simulator's torque units, with sign set
by the action. The model has joint damping 0.5 and armature 0.01 for each
joint.

**Repository fact.** Gravity is exactly zero. The plane, base geom, and target
geom have collisions disabled, so there is no ground support or physical target
interaction. The arm capsules retain their default collision settings, but no
external object can contact them; any self-contact behavior is therefore a
simulator detail rather than a task interaction. The compiled link masses are
approximately 0.09896 kg (upper arm) and 0.05248 kg (forearm), with the
corresponding geometry-derived inertias; the fixed base is approximately
0.20106 kg. The target is mocap-controlled and its mass does not dynamically
couple to the arm.

### Task and observation semantics

**Repository fact.** Success is evaluated after each 0.020 s control interval
using the Euclidean distance between the end-effector site and the target.
Distance must be at most 0.01 m for 100 consecutive control observations,
which represents 2 s. A single sampled distance outside the tolerance resets
the hold counter. Episodes truncate at 500 control steps if they have not
terminated.

**Repository fact.** The policy observation has 11 values: \(q_1,q_2\),
\(\dot q_1,\dot q_2\), the three-dimensional end-effector-to-target vector, and
four wrapped joint errors to the two inverse-kinematic branches. The branch
errors are computed from
\[
\cos q_2 =
\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)},
\]
using \(q_2=+\arccos(\cdot)\) and \(q_2=-\arccos(\cdot)\), with the
corresponding shoulder angle for each branch. The target is static, so no
target velocity is observed. The target's vertical error is always zero.

**Repository fact.** The current action mapping is identity. Training may
normalize observations for the policy, but the physical observation source and
physical action semantics remain those above. The research reward supplies
distance-progress, closeness, incremental hold-progress, completion, and small
action-cost terms; the binary task outcome remains the uninterrupted hold.

## Physical consequences

### Reachability and configuration structure

The official annulus lies inside the arm's 0.22 m maximum reach and outside its
0.02 m fully folded radius. For every official radius, the two geometric
solutions are an elbow-open and an elbow-folded configuration. At the inner
official radius, the elbow magnitude is about \(150^\circ\); at the outer
radius it is about \(49^\circ\). Both are within the elbow limits. Across the
full target angle range, at least one of these branches provides a
joint-limit-compatible configuration; therefore the task is not intrinsically
unreachable, but a policy can still select a branch that approaches a shoulder
or elbow limit.

The two branches are physically distinct trajectories, not merely two labels:
they require different joint velocities, actuator torques, and braking
profiles. The shoulder angle is represented with a wrap convention in the
branch-error features, while raw \(q\) is also present. Consequently, angular
equivalence at the \(-\pi/\pi\) boundary is physically harmless but can create
a numerically discontinuous coordinate unless the policy uses the wrapped
features and Cartesian error coherently.

### Coupled reach, convergence, and hold

The task is a rest-to-rest motion followed by disturbance-free stabilization.
Reaching requires coordinated shoulder and elbow torques because each joint
moves the end effector and changes the moment arm of the other. The arm has no
gravity to compensate, but it has inertia, joint damping, and direct torque
authority; an action that reaches the target quickly can therefore leave
nonzero joint velocity and overshoot the 1 cm disk.

Convergence is not equivalent to minimizing instantaneous distance. The policy
must brake before or at the target, reduce residual joint velocity, and then
apply either near-zero or compensating torques so the Cartesian position stays
inside the disk. The 20 ms action hold means that a command selected for
stabilization persists through ten physics steps, so a command that is
appropriate at the beginning of an interval may carry the arm outside the
tolerance before the next decision.

The Jacobian
\[
J(q)=\begin{bmatrix}
 -0.12\sin q_1-0.10\sin(q_1+q_2)&-0.10\sin(q_1+q_2)\\
  0.12\cos q_1+0.10\cos(q_1+q_2)& 0.10\cos(q_1+q_2)
\end{bmatrix}
\]
maps joint motion into planar end-effector motion, with determinant
\(0.12(0.10)\sin q_2\). Thus configurations with an elbow angle near zero or
\(\pm\pi\) have reduced manipulability: small Cartesian corrections can require
large or poorly conditioned joint changes. The official inner-radius targets
are closer to the folded singularity than typical mid-range targets, while
the largest targets are closer to the extended side of the workspace. This
creates geometry-dependent differences in correction sensitivity even though
the target is stationary and reachable.

Success is a temporal property of the coupled state, not just a terminal
position property. A transient reach can earn shaped reward without producing
success; conversely, a policy can remain successful with different joint
configurations or small motion as long as every sampled Cartesian distance
stays within tolerance. The environment checks the hold at control samples,
so sub-interval excursions that return before the next check are not separately
observable to the success logic.

### Observation, control, and outcome

The observation contains enough ideal simulator state to identify the current
mechanical configuration and velocity, and it gives the target relative to the
end effector. The two inverse-kinematic error pairs expose both available
solutions and make branch proximity explicit. There is no sensor noise,
latency, actuator measurement, contact sensing, or external disturbance in the
specified system. The policy therefore faces a deterministic controlled
dynamical system conditional on the sampled target, with uncertainty arising
from the target distribution and from its own learned action mapping rather
than from unmodeled sensing.

The hold counter is not part of the observation. A policy cannot directly know
whether it has accumulated, for example, 70 valid hold samples, although it can
observe the physical state that determines whether the next sample will count.
An interruption resets the counter even if the arm immediately returns to the
tolerance disk. This makes low-velocity, margin-rich stabilization scientifically
more relevant than merely crossing the tolerance boundary.

The baseline training distribution uses radii 0.14--0.20 m, whereas the
official distribution includes 0.06--0.20 m. The learned controller therefore
may encounter the more folded, lower-manipulability part of the reachable
workspace only during evaluation unless the training configuration is changed.

## Unknowns

These quantities are not established by the pre-campaign implementation and
must not be inferred from the task definition alone:

- the actual time-to-first-entry, peak joint speed, peak torque, overshoot, and
  settling time for either inverse-kinematic branch;
- the Cartesian position and velocity margins achieved during a complete
  2-second hold, including how those margins vary with target radius and angle;
- whether the available saturated torque and damping permit reliable braking
  within the 20 ms decision interval for all official targets;
- which branch a learned policy will select, whether it switches branches, and
  whether branch or angle-boundary behavior produces distinct failure classes;
- the sensitivity of hold success to the target's radial and angular location,
  especially near the folded and extended regions and near joint limits;
- whether the shaped research reward and the observation representation induce
  a policy that prioritizes complete holds over fast but underdamped arrivals;
- the distribution of hold interruptions, late exits, and truncations under any
  learned policy; and
- the resulting episode-success probability under the official distribution.

The decisive physical measurements are therefore not only minimum distance or
terminal distance. They are the complete distance trace, longest consecutive
in-tolerance duration, first-entry time, joint positions and velocities,
action/torque saturation, branch identity, and their dependence on target
radius and angle. None of these measurements is campaign evidence yet.
