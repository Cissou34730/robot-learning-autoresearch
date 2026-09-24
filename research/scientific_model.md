# Scientific model of the robot and task

## System-level model

**Established fact.** The system is a planar, two-revolute-joint arm in MuJoCo.
Both hinge axes are the world `z` axis. The shoulder is at the base origin and
the elbow is at the end of a 0.12 m upper arm. A 0.10 m forearm terminates at
the end-effector site. The arm lies at `z = 0.02 m`; the target is a
non-contacting mocap body placed in that same plane. Gravity is explicitly zero.

**Physical or scientific consequence.** The task is planar point positioning, not
object interaction or forceful manipulation. The relevant configuration is
`q = (q_shoulder, q_elbow)`, and the end-effector position is determined by

```text
x = 0.12 cos(q_shoulder) + 0.10 cos(q_shoulder + q_elbow)
y = 0.12 sin(q_shoulder) + 0.10 sin(q_shoulder + q_elbow)
z = 0.02
```

The target has no dynamics and cannot be pushed or grasped. Success depends only
on the geometric distance between this site and the target.

**Unknown.** The implementation does not reveal which trajectories a learned
controller will actually choose, which inverse-kinematic branch it will prefer,
or how much transient motion it will use.

## Morphology, workspace, and kinematic alternatives

**Established fact.** Each joint declares a range of -170 to +170 degrees.
The link lengths give a maximum radial reach of 0.22 m and a minimum radial
reach of 0.02 m for an unconstrained planar two-link chain. The official target
radius is sampled uniformly from 0.06 to 0.20 m, with angle uniformly spanning
`[-pi, pi]`. This is uniform in radius, not uniform in disk area. The initial
configuration is `q = (0, 0)`, so the end effector starts at
`(0.22, 0, 0.02)`.

**Physical or scientific consequence.** The target annulus lies strictly inside
the arm's geometric annulus, away from both the fully folded and fully extended
radial boundaries. For a target at polar coordinates `(r, phi)`, the two
inverse-kinematic solutions are

```text
q_elbow = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q_shoulder = phi - atan2(0.10 sin(q_elbow),
                         0.12 + 0.10 cos(q_elbow)).
```

Thus the target generally has an elbow-up and an elbow-down solution. Across
the official annulus these solutions are compatible with the declared joint
limits. The controller can therefore solve the same point with qualitatively
different joint postures and velocities. The target range also keeps the
solutions away from the two-link Jacobian singularities at `q_elbow = 0` and
`q_elbow = +/- pi`; both branches retain nonzero local task-space authority.

The initial target distance can range from approximately 0.02 m for a nearby
target in the initial direction to 0.42 m for a target at radius 0.20 m in the
opposite direction. The initial state therefore combines zero joint velocity
with a target-dependent position error and may require either a short correction
or a large planar reorientation.

**Unknown.** The declared joint limits and kinematics determine feasible
configurations, but not whether a controller will cross through a particular
posture, switch branches, or avoid unnecessary revolutions.

## Actuation and dynamics

**Established fact.** Each joint is driven by a direct MuJoCo motor with
`ctrlrange = [-1, 1]` and gear value 5. The action has two components and is
passed unchanged to the physical command interface before environment clipping.
There is no actuator activation filter, action smoothing, or learned action
mapping in the human-defined interface. The compiled model has 0.5 joint
damping and 0.01 joint armature at each degree of freedom. With the XML's
default geom density, the compiled upper-arm and forearm masses are
approximately 0.099 kg and 0.052 kg respectively. The motor transmission
therefore supplies a bounded signed joint torque proportional to the command,
with nominal magnitude 5 in MuJoCo torque units at full command.

MuJoCo integrates at 0.002 s. The environment holds one action for 10 physics
steps, then exposes the resulting state and computes task distance. The
effective control interval is therefore 0.020 s, or 50 control decisions per
second.

**Physical or scientific consequence.** This is a sampled-data torque-control
problem. A command affects acceleration and velocity over ten integration
steps, rather than teleporting either joint or end effector. Damping dissipates
velocity, while armature and link inertia oppose rapid changes. The same
command has configuration-dependent end-effector effect because the
two-link Jacobian maps joint torque and motion into task space. Near a target,
successful behavior requires both reducing Cartesian error and reducing
residual joint velocity; stopping at the right position is not equivalent to
arriving there with momentum.

There is no gravity torque to compensate and the target does not exert contact
forces. With the arm at rest, zero command is a possible force-free equilibrium;
during approach, braking and small corrective torques are needed to remove
velocity and keep the end effector inside the tolerance. The plane, base, and
target explicitly have contact disabled, so environmental support or collision
reaction is not part of the required solution.

**Unknown.** The implementation fixes the equations, masses, damping, and
timing, but does not determine the realized acceleration profile, peak torque,
settling time, overshoot, or steady-state motion of a policy. Those quantities
depend on the policy's actions and the resulting simulator trajectory.

## Initial state and task mechanics

**Established fact.** Reset sets all joint positions and velocities to zero,
forwards the model, then samples one target. The target remains fixed for the
episode. The target is sampled in the arm's plane at a radius from 0.06 to
0.20 m and a full angular range. An episode allows at most 500 control steps.
After each control interval, the environment measures the three-dimensional
end-effector-to-target distance. A sample is inside the success region when
that distance is at most 0.01 m.

Success requires 100 consecutive inside samples, corresponding to 2.0 s at
0.020 s per control interval. Leaving the tolerance resets the hold counter.
The official benchmark evaluates one frozen policy on 200 fixed-seed episodes;
the objective threshold is at least 196 successes, or 98 percent.

**Physical or scientific consequence.** Reaching the target is only the first
phase of the task. The full behavior has four coupled requirements: select a
feasible posture, move the end effector through a controlled trajectory, reduce
both position error and motion before or while entering the 1 cm ball, and
stabilize there for a long interval. A brief crossing of the tolerance is not
enough. Because distance is checked at control boundaries after ten physics
steps, the operational hold condition is 100 consecutive sampled measurements;
motion between those measurements is simulated but not separately declared a
success or failure.

The tolerance is small relative to the 0.22 m reach, so a few millimeters of
Cartesian motion can determine whether a hold sample is retained. A single
boundary crossing destroys the accumulated streak, making convergence and
stability physically distinct from merely minimizing average distance.

**Unknown.** The task definition does not say which part of the 500-step
horizon will contain the first entry into the tolerance, whether entry will be
monotonic, or how often a trajectory will leave and re-enter before a complete
hold.

## Observation and control information

**Established fact.** The policy receives an 11-element observation consisting
of:

* the two joint positions;
* the two joint velocities;
* the three-dimensional vector from the target to the end effector; and
* four wrapped angular residuals to the analytical elbow-up and elbow-down
  inverse-kinematic solutions.

The target and end-effector geometry are therefore represented relative to one
another, while the exact joint state is also visible. The action is a
two-element value in `[-1, 1]`, directly interpreted as the two motor controls.
The next observation arrives only after the ten internal MuJoCo steps.

**Physical or scientific consequence.** The observation contains enough
instantaneous information to reconstruct the current planar target geometry
from the joint state and relative end-effector vector, and it explicitly
exposes both kinematic alternatives. It does not force one branch: the current
joint state and the four residuals allow the controller to decide how to
approach either solution. Joint velocity supplies the principal observable
needed for damping and braking decisions.

The observation does not directly expose acceleration, applied torque, hidden
constraint or contact forces, model mass matrix, future target information,
or the hold counter. The hold counter is also not needed to identify the
instantaneous mechanics, but it is part of the task state that determines
whether the next inside sample completes the episode.

**Unknown.** From the implementation alone it is not possible to know whether
the controller internally estimates unobserved accelerations or remembers hold
progress, nor whether it uses the explicit inverse-kinematic residuals,
forward-kinematic information, or both.

## Behaviorally meaningful physical quantities

**Established fact.** The benchmark outcome is defined from sampled
end-effector distance and consecutive in-tolerance samples, while the simulator
state exposes joint positions and velocities and the control exposes bounded
motor commands.

**Physical or scientific consequence.** The quantities that directly describe
the robot's behavior are joint configuration and velocity, target radius and
angle, Cartesian error vector and distance, end-effector speed, signed motor
commands and their transmitted torques, entry time, overshoot, settling time,
maximum and steady-state error, and the longest uninterrupted in-tolerance
streak. The selected inverse-kinematic branch, Jacobian conditioning, and
distance from joint limits describe the geometric context. Control effort,
torque saturation, and accumulated motion describe the dynamic cost of a
trajectory even though they do not alter the official binary success rule.

**Unknown.** These quantities can be computed from an observed trajectory, but
their values, distributions, and relationships for an actual learned policy
are not determined by the robot and task implementation alone.
