# Scientific model of the two-joint arm reach-and-hold task

## System and task

The robot is a planar, fully actuated two-revolute-joint arm. Both joint axes
are the world z axis, so the relevant motion is in the xy plane at fixed
`z = 0.02 m`. The shoulder is at the world origin in xy; the upper arm has
length `l1 = 0.12 m` and the forearm has length `l2 = 0.10 m`. The end
effector is the end of the forearm, giving the forward kinematics

```text
x = l1 cos(q1) + l2 cos(q1 + q2)
y = l1 sin(q1) + l2 sin(q1 + q2).
```

Each joint is limited to -170 to +170 degrees. The target is a fixed mocap
point in the same plane, sampled with radius uniformly from 0.06 to 0.20 m
and angle uniformly over the full circle. The success band is a 0.01 m
three-dimensional Euclidean distance, which is planar here because target and
end effector have the same z coordinate. The end effector must be in that
band for 100 consecutive control steps, corresponding to two seconds, before
the episode terminates successfully. An episode otherwise has at most 500
control steps (ten seconds).

## Embodied dynamics and control loop

The MuJoCo model advances with a 0.002 s timestep. One policy action is
applied for 10 simulator steps, so the policy receives feedback and can change
commands only every 0.020 s. The action has two components, is clipped to
[-1, 1], and is passed directly to one motor on each joint. The motor gear is
5, so the commanded generalized motor effort is proportional to `5 * action`
until the command limit is reached. There is no action filtering, actuator
state, target motion, contact interaction, or gravity in the authored model.

The joints have damping 0.5 and armature 0.01. Thus the arm is a second-order,
configuration-coupled system with bounded direct torque authority, viscous
dissipation, and configuration-dependent inertia. The two actuators provide
independent control of the two degrees of freedom, but changing either joint
changes the end-effector position and changes the inertia coupling seen by the
other joint. With gravity absent, a stationary exact inverse-kinematic posture
does not require a gravity-compensation torque; nonzero velocity still has to
be removed, and any tracking error must be corrected without leaving the
1 cm band. The arm and target do not provide a force or contact mechanism that
could passively constrain the end effector.

At reset, `q = (0, 0)` and joint velocities are zero. The arm is therefore
straight along positive x and the end effector starts at `(0.22, 0, 0.02)`.
This is the maximum-extension configuration and its planar position Jacobian
has rank one: initially, infinitesimal joint motion produces only first-order
motion along the arm's tangent direction, not sideways motion. A target can be
behind the base or substantially off this initial ray, so reaching generally
requires first creating a useful bent configuration rather than simply
tracking a local Cartesian error. Initial target distance varies with both
target radius and angle and can be as large as about 0.42 m.

## Kinematic alternatives and coupled requirements

For a target at polar coordinates `(r, phi)`, the two mathematical inverse
kinematic branches are

```text
q2 = +/- acos((r^2 - l1^2 - l2^2) / (2 l1 l2))
q1 = phi - atan2(l2 sin(q2), l1 + l2 cos(q2)).
```

The official radii lie inside the two-link annulus
`|l1-l2| = 0.02 m` to `l1+l2 = 0.22 m`, so both elbow-up and elbow-down
solutions exist geometrically before joint limits are applied. The smallest
official radius requires an elbow angle of about +/-150 degrees; the largest
requires about +/-49 degrees. Joint limits can exclude a branch for particular
target angles, so branch symmetry must not be assumed even though the
distribution generally offers an alternative feasible posture. Near maximum
extension the Jacobian becomes poorly conditioned and small Cartesian errors
can require comparatively large joint changes.

Success is consequently a coupled sequence, not a reach-only problem:

1. select or discover a joint posture that reaches the target while respecting
   the joint limits;
2. accelerate the arm through the initial singular posture and move toward that
   posture;
3. brake so that the end effector enters the tolerance with sufficiently small
   residual velocity;
4. continually correct joint and Cartesian error for two seconds without an
   excursion.

The reach and hold stages interact. Arriving quickly with residual joint
velocity causes overshoot; a conservative arrival reduces hold interruptions
but consumes the ten-second horizon. During a hold, the useful control objective
is local stabilization in joint space and Cartesian space, with effort bounded
by the motor limits and sampled only every 20 ms. Because there is no gravity,
the physically simplest final state is a stationary inverse-kinematic posture,
but either branch and any small control oscillation can determine whether the
1 cm margin is preserved.

The environment calculates distance after each 10-step MuJoCo batch. Its
`held_steps` counter is reset on an out-of-band sample and success is declared
after 100 consecutive in-band samples. Thus the human requirement is
operationalized as an uninterrupted sequence at the control sampling rate;
the shared implementation does not test the distance at each 2 ms substep.
An excursion that begins and ends between two distance checks is therefore not
observable to the success counter.

## Observation, action, and outcome

The policy observes 11 values:

- the two joint positions and two joint velocities;
- the three-dimensional end-effector minus target position;
- wrapped angular errors from the current posture to each of the analytic
  elbow-up and elbow-down inverse-kinematic solutions.

The target is fixed during an episode and there is no sensor noise. The joint
state and forward kinematics make the physical end-effector position known;
combined with the relative position, the target position is recoverable even
though the target's absolute coordinates are not separately included. The
observation contains no force, torque, acceleration, actuator saturation,
substep trajectory, or target-velocity measurement. The four branch errors
provide explicit alternatives but are still angle-wrapped, and a branch
suggested by the analytic formula may not satisfy both joint limits.

At each control boundary, the policy maps this state representation to the two
bounded motor commands. MuJoCo evolves the state for 10 substeps, after which
the new distance determines the hold counter, reward, and termination. The
policy therefore has enough state information for a deterministic Markov
description of the authored mechanics, but it must infer from successive
observations whether its current posture and velocity are safe for continued
holding. Reward terms provide progress, closeness, incremental hold progress,
and completion signals, but the episode outcome is the binary uninterrupted
hold, not accumulated reward.

## Established facts

- The human task samples radii 6--20 cm over all angles, uses a 1 cm tolerance,
  requires a two-second uninterrupted hold, and allows 500 control steps.
- The authored robot has two planar hinge joints, link lengths 12 cm and 10 cm,
  joint limits of +/-170 degrees, and two direct motor actuators.
- MuJoCo uses a 2 ms timestep; `frame_skip = 10` gives 20 ms action and
  observation intervals and 100 control samples for the required hold.
- Gravity is explicitly zero; joint damping is 0.5, armature is 0.01, motor
  gear is 5, and action commands are clipped to [-1, 1].
- Reset sets both joint positions and velocities to zero, then samples one
  stationary target in the arm plane.
- The policy receives joint position, joint velocity, relative end-effector
  position, and four wrapped analytic IK branch errors; actions are not
  transformed beyond the physical clipping in the environment.
- The environment updates distance and hold state once per control step and
  terminates on 100 consecutive in-band updates or truncates at 500 steps.

## Physical consequences

- The target set is geometrically inside the reachable annulus, but the
  straight reset posture is singular for first-order Cartesian control and
  makes large-angle targets a transient maneuver rather than a local
  correction.
- The arm is fully actuated but dynamically coupled. Motion planning, braking,
  and stabilization cannot be separated: the velocity acceptable for reaching
  is not necessarily acceptable for entering or maintaining the hold band.
- Two inverse-kinematic postures create a real choice of elbow branch; limits,
  target angle, conditioning, and the transient from the straight reset state
  can make their control difficulty different.
- The 1 cm band is a small positional margin relative to the link lengths, so
  residual velocity, damping, action saturation, and the 20 ms feedback period
  directly affect hold reliability.
- Zero gravity removes one persistent disturbance but does not remove
  inertia, Coriolis coupling, motor limits, or the need to dissipate velocity.
- The discrete distance checks make control-step stability the measured
  requirement, while unmeasured within-batch excursions are a simulator
  semantics limitation relevant to interpreting apparent holds.

## Unknowns

- The XML does not explicitly specify link density, body mass, or inertia
  tensors. MuJoCo derives them from the geoms and defaults at model load; the
  exact resulting configuration-dependent inertial dynamics and acceleration
  limits have not been numerically characterized here.
- The exact feasible IK branch set over every target angle under both +/-170
  degree limits, and the conditioning of each branch across the radius range,
  remain to be mapped quantitatively even though the annulus calculation shows
  geometric reachability.
- The transient time and control effort needed to leave the reset singularity,
  brake at each target class, and reject perturbations are not established
  without trajectory measurements.
- It is not yet known how much residual joint velocity can be present at band
  entry while remaining inside the band for all subsequent control samples, or
  which branch gives the largest hold margin.
- No campaign evidence exists for learned-policy behavior, target-conditioned
  failure rates, branch selection, saturation, or the relationship between
  reward optimization and the binary success criterion. In particular, the
  physical model alone provides no basis for claiming the 98% episode objective.

## Scientifically meaningful quantities

The most diagnostic trajectory quantities are target radius and angle, joint
position and velocity, branch feasibility and selected posture, end-effector
distance and Cartesian velocity, first-entry time, maximum uninterrupted
in-band duration, hold interruptions, final distance, motor command and
saturation, and control effort or work. Separating time-to-first-entry from
maximum hold duration distinguishes reach failure, overshoot/braking failure,
and stabilization failure. Conditioning or manipulability along the trajectory
links those outcomes to kinematics, while velocity at first entry and command
activity during the hold link them to the dynamic and control limits.
