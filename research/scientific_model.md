# Scientific model: two-joint arm reach-and-hold

This is a planar, fully actuated, deterministic reaching problem with a
nontrivial temporal requirement. The policy must move a two-link serial chain
from a fixed, initially extended state to a target-dependent configuration,
then regulate the end effector tightly enough that every sampled control state
remains inside the tolerance for the full hold. Reaching and holding are
therefore one coupled control problem: a fast approach that leaves residual
motion is not a successful behavior.

## Established facts

### Morphology and kinematics

The robot has two revolute joints, both rotating about the world z axis. The
upper arm is 0.12 m long and the forearm is 0.10 m long, so the end-effector
position in the arm plane is

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
    z = 0.02 m

Here `q1` is the shoulder angle and `q2` is the elbow angle relative to the
upper arm. The joint ranges are +/-170 degrees. The link geometry is
represented by capsules with radii 0.015 m and 0.012 m. The base is fixed to
the world; it does not add a controllable degree of freedom.

Without joint limits, the planar workspace is the annulus from
`|0.12 - 0.10| = 0.02 m` to `0.12 + 0.10 = 0.22 m`. Official targets have
radii from 0.06 m to 0.20 m and lie in the same z plane, so their radial
locations are inside this annulus.

For a target with polar coordinates `(r, phi)`, the two geometric inverse
kinematic branches are represented by

    q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
    q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2)).

The observation implementation explicitly computes these open- and
folded-elbow alternatives. At the official radii, at least one branch is
compatible with the joint limits throughout the intended angular range, but
the other branch is often excluded by the shoulder or elbow limit. The
branches become less distinct toward the outer workspace boundary.

### Actuation and simulated dynamics

Each joint is driven by a MuJoCo motor with control in `[-1, 1]` and gear 5.
The action mapping is currently identity, so the command is a bounded
joint-torque command with nominal magnitude up to 5 in simulator torque units.
There is no actuator state or rate limiter. A command is held constant for
10 physics steps before the policy receives another observation.

The physics timestep is 0.002 s, giving a 0.020 s policy control interval.
Gravity is exactly zero. There are no task contacts: the plane and target
visual geometry have collisions disabled, and the target is a mocap body.
Joint damping is 0.5 at both joints and joint armature is 0.01 at both
joints. The loaded MuJoCo model resolves the upper-arm and forearm masses to
approximately 0.09896 kg and 0.05248 kg, with local diagonal inertias
approximately `(0.0001683, 0.0001683, 0.00001081)` and
`(0.00006110, 0.00006110, 0.000003674)` kg m^2, respectively. There is no explicit gravity, joint stiffness, or joint friction mechanism in
the model, and no external task contact is specified.

The resulting acceleration is not determined by torque alone. The effective
inertia changes with configuration because the shoulder moves both links and
the elbow moves the distal link; damping removes energy while armature adds
joint-side inertia. Thus the same action can produce different motion during
approach, near an extended posture, and near a folded posture.

### Initial state, target, and verdict

Every reset sets both joint positions and both joint velocities to zero. The
arm therefore begins fully extended along positive x, with its end effector at
approximately `(0.22, 0, 0.02)` m. A target is then sampled with angle
uniform over the full circle and radius uniform from 0.06 m to 0.20 m. Its z
coordinate is set to 0.02 m, so the target is stationary and coplanar with
the end effector.

After each 0.020 s control interval, the simulator measures the Euclidean
end-effector-to-target distance. A sample is inside when that distance is at
most 0.01 m. Success requires 100 consecutive inside samples, equivalent to
2 s under the official timing. An outside sample resets the consecutive hold;
the episode is truncated after 500 control intervals. The official assessment
uses 200 fixed-seed episodes and requires at least 196 successes.

The implementation's continuous-hold test is therefore continuous in the
sequence of control observations, not continuously monitored at all ten
physics substeps. Motion that exits and re-enters the tolerance between
sampled verdicts is not separately visible to the success counter.

### Sensing and policy interface

The policy receives 11 values:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional end-effector minus target displacement; and
4. four wrapped angle errors to the two analytic IK branches.

The target is fixed, so target velocity is not a missing dynamic input. The
target's absolute position is not sent directly, but the displacement together
with the known forward kinematics and observed joint positions makes the
relevant target geometry reconstructible. The observation contains no
acceleration, applied torque, actuator state, hold counter, or explicit
in-tolerance flag. Distance can be computed from the displacement, and the
policy can infer physical end-effector position from joint positions, but
hold progress is not directly observable from one observation.

The action is clipped to the physical control range, written to both motor
controls, and integrated for ten simulator steps. The next observation is
then generated from the resulting state. This is a sampled-data feedback loop
with zero-order-held control, not continuous torque feedback.

## Physical consequences

The initial condition makes the task asymmetric in time. A target near the
initial forward direction requires little reorientation, while a target at a
different azimuth requires coordinated shoulder and elbow motion from rest.
The policy must choose a valid inverse-kinematic branch, accelerate the links,
and then remove kinetic energy before entering the 1 cm region. Because the
hold band is small relative to the link lengths, small angular errors and
residual velocities can move the end effector outside the band even after
the target has been reached geometrically.

Two capabilities are coupled rather than independently sufficient:

- **Reachability and trajectory control:** the shoulder sets the global
  orientation while the elbow changes both radius and orientation. Their
  inertial coupling means that braking one joint can perturb the other and
  shift the end effector tangentially or radially.
- **Convergence and stabilization:** entering the tolerance is only the start
  of success. The controller must maintain a low-velocity configuration for
  100 sampled intervals despite damping, discrete action updates, torque
  saturation, and any residual oscillation. A branch switch or correction
  during the hold can be physically valid yet still reset the hold.

The two IK branches create qualitatively different behaviors. An elbow-up
solution may have a different shoulder angle, path length, and braking
requirement from the elbow-folded solution. Joint limits can eliminate one
branch for a target while leaving the other available. Near configurations
where the branches approach one another, the geometric choice itself becomes
less informative and local feedback and damping become more important.

The observation is sufficient in principle to form state feedback for this
deterministic second-order plant: it contains both configuration and velocity,
and the target displacement. It does not directly expose the temporal
requirement, so a memoryless policy must infer a stabilization objective from
velocity and distance, while a recurrent policy could additionally remember
recent hold history. The absence of gravity and external task contact removes several failure modes
found in physical manipulators, but also means that success is primarily a
test of inertial trajectory shaping, damping utilization, and sampled-data
regulation.

The physically meaningful quantities for explaining complete behavior are:
target radius and azimuth; joint positions, velocities, and distance to each
joint limit; end-effector radial and tangential error; commanded torque and
torque saturation; approach time; speed and acceleration at tolerance entry;
the longest uninterrupted inside interval; exits from the band; and the
inverse-kinematic branch used. These quantities distinguish a failure to
reach, a late or inaccurate approach, an underdamped crossing, and a hold
that fails only because of sampled control or residual motion.

## Unknowns

No campaign evidence yet establishes:

- the configuration-dependent effective inertia and acceleration margins
  experienced under the bounded motors, or the time required to brake from
  typical approach speeds;
- whether failures, when they occur, will be dominated by branch selection,
  shoulder/elbow coordination, torque saturation, discrete-time overshoot,
  or persistent end-effector oscillation;
- how much stabilizing authority remains inside the 1 cm band across target
  radii and azimuths, especially for targets requiring large reorientation;
- whether the policy will discover a consistent IK branch or switch branches
  in ways that create long paths and discontinuous control demands;
- how often the state exits the tolerance between the 20 ms observations,
  which the official hold counter cannot detect;
- how training distribution, reward shaping, policy memory, and optimization
  interact with the physical problem, including whether good reaching
  performance transfers to the full-radius, full-angle official distribution;
- whether a policy that appears stable on development episodes sustains the
  complete 2 s hold on the independent official panel.

These are unresolved scientific quantities, not evidence that the 98% goal is
achieved or that it is impossible. The model establishes the mechanism that
must be learned; campaign measurements must determine which parts of that
mechanism limit episode success.
