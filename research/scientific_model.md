# Scientific model of the robot and task

## Physical system and geometry

**Established fact:** The robot is a planar serial two-revolute-joint arm. The
shoulder and elbow axes are parallel to the world z axis, the shoulder is at
z = 0.02 m, and the link lengths are 0.12 m and 0.10 m. The end-effector site
therefore has, for joint angles q1 and q2,

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
    z = 0.02

Both joints are limited to -170 to +170 degrees. The target is a noncontact
mocap body in the same horizontal plane. The target and the visual plane have
collisions disabled, so the task is free-space motion rather than physical
contact or manipulation.

**Physical/scientific consequence:** With unrestricted joint angles, the
reachable radial interval is 0.02 to 0.22 m. The official target radii,
0.06 to 0.20 m, lie inside this annulus, and every target direction is
geometrically represented. The joint limits can remove one posture for some
directions, but the target region retains at least one inverse-kinematic
posture. The endpoint Jacobian has determinant proportional to
`sin(q2)`: the initially straight arm is a kinematic singularity for planar
motion, while the non-boundary target radii require a bent elbow and have
full-rank local endpoint control at their exact inverse-kinematic postures.

**Unknown:** The implementation does not determine which valid posture a
closed-loop policy will use, how it will travel between postures, or whether it
will cross a joint limit during a particular trajectory.

## Actuation, timing, and dynamics

**Established fact:** Each action is a two-element value in [-1, 1] and is
passed unchanged to a MuJoCo motor. The motor gear is 5, giving a bounded
generalized motor torque of approximately +/-5 in the model's torque units.
The MuJoCo integration timestep is 0.002 s, gravity is zero, and the default
integrator is used. Joint damping is 0.5 and joint armature is 0.01 for both
joints. An action is held constant for 10 simulator steps, so the policy
updates every 0.020 s. There is no authored low-level position controller,
action smoothing, gravity compensation, or contact force.

The loaded model obtains link inertias from the capsule geometry and MuJoCo
defaults rather than explicit inertial tags. In the current loaded model the
upper-arm and forearm masses are approximately 0.099 kg and 0.052 kg. At the
straight configuration, the effective generalized inertia, including the
specified armature, is approximately

    [[0.01210, 0.00051],
     [0.00051, 0.01019]] kg m^2.

**Physical/scientific consequence:** The action is direct torque control with
zero-order hold. In the absence of gravity, motion is governed primarily by
configuration-dependent inertia, commanded torque, and viscous damping.
Torque can create large angular accelerations relative to the small arm
inertias, while damping removes velocity but does not create a positional
restoring force. Consequently, a stationary endpoint is not maintained by
zero torque after a perturbation unless the state is already at rest; feedback
torque is needed to reject position and velocity errors. The 20 ms action
interval means that braking and endpoint corrections are discrete control
decisions over several 2 ms physical integration steps.

**Unknown:** Actual speed, acceleration, torque saturation, and transient
settling time are trajectory-dependent. They cannot be inferred from the
model parameters alone without observing the policy's actions and resulting
state evolution.

## Initial state and target construction

**Established fact:** Every episode resets both joint positions and velocities
to zero. The initial endpoint is therefore (0.22, 0, 0.02) m, the straight
outstretched posture. A target is then sampled with angle uniform on
[-pi, pi] and radius uniform on [0.06, 0.20] m, and its z coordinate is set to
the endpoint's z coordinate. The target is fixed during the episode.

**Physical/scientific consequence:** The initial arm is at the outer radial
boundary and at a Jacobian singularity, whereas most targets require a
nonzero elbow angle. The first part of a trajectory must therefore combine
breaking the straight posture with moving toward the target; infinitesimal
endpoint motion initially cannot independently command both planar Cartesian
directions. Initial endpoint-to-target distance ranges from about 0.02 m to
0.42 m under the official target distribution. The initial condition is
directionally asymmetric even though target directions are sampled over the
full circle, because the arm always starts pointing along +x.

**Unknown:** The reset code specifies the physical initial state and target
distribution but not the resulting approach direction, time to enter the
tolerance region, or amount of transient energy.

## Task geometry and success semantics

**Established fact:** Success is based on the Euclidean distance between the
end-effector site and the target mocap position. The threshold is 0.01 m.
The control period is 0.020 s, so the required two-second hold is 100
consecutive control steps. Any sampled distance outside the threshold resets
the held-step counter. An episode may run for at most 500 control steps,
equivalent to 10 s, unless the hold completes earlier. The official assessment
uses 200 independently seeded target episodes and requires at least 196
successes.

The implementation tests distance after each block of 10 MuJoCo integration
steps. Thus the operational success condition is 100 consecutive
post-block distance checks; it does not test the distance at each 2 ms
substep. The target sphere itself is not a physical obstacle or contact
constraint.

**Physical/scientific consequence:** Approach, entry, settling, and holding
are one coupled control problem. Reaching the target posture with nonzero
endpoint velocity is not sufficient: the velocity must be dissipated or
actively controlled so that the sampled endpoint remains inside a 1 cm disk.
The tolerance is small relative to the link lengths, and the hold counter
resets on one outside sample, so oscillation, overshoot, and delayed braking
are physically coupled to success rather than separate post-processing
stages. A faster approach can leave less time for braking; braking changes
the state from which fine endpoint regulation begins. Conversely, a stable
posture and low endpoint velocity can make sustained holding possible without
requiring continued large motion.

The environment's task state includes the held-step counter, but that counter
is not part of the observation. Therefore identical physical states and target
geometry can have different remaining success requirements depending on prior
history, even though the robot's instantaneous dynamics are the same.

**Unknown:** The implementation does not establish whether a given policy
will enter early and settle, approach slowly, leave and re-enter, or complete
the full uninterrupted hold. Those are observations about closed-loop
behavior, not consequences that can be assigned to a task-stage label alone.

## Sensing and control interface

**Established fact:** The physical observation has 11 float components:

1. shoulder and elbow positions;
2. shoulder and elbow velocities;
3. the three-dimensional vector from the target to the end effector;
4. four wrapped angular errors to the two analytic inverse-kinematic
   solutions: positive-elbow and negative-elbow postures.

The inverse-kinematic elbow magnitude is computed from the target radius by
the cosine law, and the corresponding shoulder angles are computed
analytically. The action mapping is the identity, so the policy directly
selects the two motor controls. There is no sensor noise, target motion,
contact sensing, acceleration sensing, or direct observation of applied
torque in this interface.

**Physical/scientific consequence:** The observation contains the instantaneous
configuration, velocity, and target-relative endpoint error needed to
describe the free-space task. Because link lengths and forward kinematics are
fixed, the target position relative to the base can be reconstructed from
the joint positions and the endpoint-target vector; its distance is also the
norm of that vector. The four angular residuals make the two posture
families explicit and allow the controller to regulate toward either branch.
The observation is therefore rich about instantaneous geometry but does not
encode the accumulated hold history, the intervening substep trajectory, or
the physical quantities that are not measured directly.

**Unknown:** Whether a policy uses the velocity information for active
damping, follows the analytic posture cues, or relies on another internal
representation cannot be determined from the observation contract.

## Alternative configurations and constraint classes

**Established fact:** For a target of radius r, the two unconstrained
inverse-kinematic elbow angles are

    q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10)).

The shoulder angle changes with the selected elbow sign. Over the official
radius interval the elbow magnitude is approximately 49 to 150 degrees, so
both elbow signs are within their joint limits; the corresponding shoulder
postures are generally valid, although a target near an angular edge can
make one branch violate the +/-170 degree shoulder limit.

**Physical/scientific consequence:** A target normally has two discrete
postural solutions rather than a continuous redundancy. The branches have
different joint excursions, Jacobians, inertial coupling, and joint-limit
margins. Choosing a branch is therefore also choosing a distinct dynamic
trajectory and stabilization problem. Near a joint limit, the available
motion directions become constrained; near the initial straight posture, the
endpoint Jacobian becomes poorly conditioned; near the tolerance boundary,
small Cartesian deviations determine whether the hold continues. These are
different physical constraint classes even though the benchmark reports them
through the same distance and success variables.

**Unknown:** Which branch and which constraint class a particular episode
actually occupies during its full closed-loop behavior is not fixed by the
task definition.

## Scientifically meaningful quantities

**Established fact:** The simulator exposes the state, target, action, and
distance at each control step, and the benchmark records the uninterrupted
hold outcome.

**Physical/scientific consequence:** A complete physical description of an
episode can use the target radius and angle; joint positions, velocities and
accelerations; commanded and saturated torques; joint-limit margins; endpoint
position and velocity; target distance and signed planar error; Jacobian
conditioning; path length; entry time; peak speed and acceleration; torque
saturation and control effort; settling time; the number and duration of
outside excursions; longest consecutive in-tolerance run; and final hold
state. Together these quantities distinguish geometric reachability,
trajectory generation, braking, local regulation, and sustained completion
without treating those stages as independent capabilities.

**Unknown:** The numerical values and relationships among these quantities
for any learned controller require actual closed-loop trajectories. The
human-authored implementation defines what can be measured and how success
is judged, but it does not supply behavioral measurements.
