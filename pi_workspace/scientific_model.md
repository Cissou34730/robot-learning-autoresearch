# Scientific model of the two-joint arm reach-and-hold task

The system is a planar, two-degree-of-freedom manipulator whose only
task-relevant interaction is the Euclidean distance between its end-effector
site and a stationary target. Success is therefore not a grasp or contact
problem: it is a coupled motion-control problem in which the arm must select
and reach a valid configuration, remove its residual motion, and remain inside
a small Cartesian tolerance for the full hold interval.

## Established facts

### Morphology and kinematics

**Repository fact:** The fixed robot has a base at the world origin, a 0.12 m
upper arm, and a 0.10 m forearm. The shoulder and elbow are revolute joints
with parallel z axes, so both joint coordinates act in the horizontal x-y
plane. The arm plane is z = 0.02 m. The end-effector site is at the distal
end of the forearm. The base is fixed to the world.

With shoulder angle q1 and relative elbow angle q2, the end-effector position
in that plane is

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2)

The nominal maximum reach is 0.22 m and the two-link geometric inner radius
is 0.02 m. Each joint has a stated range of -170 to +170 degrees.

**Repository fact:** The target is a mocap body with no physical contact
interaction. The task code places it at the same z coordinate as the
end-effector, samples angle uniformly over [-pi, pi], and samples scalar
radius uniformly over [0.06, 0.20] m for the official environment constants.
The current training constructor instead samples radius over [0.14, 0.20] m.

For a target radius r, the inverse-kinematic elbow magnitude is

    e = acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10)).

The two nominal solutions use q2 = +e and q2 = -e, with the corresponding
shoulder angle adjusted by the target direction. Over the official radius
range, e is approximately 49.5 to 150.3 degrees, so both elbow branches are
inside the elbow limits. The associated shoulder offsets are approximately
22 to 56 degrees from the target direction; consequently at least one branch
also remains inside the shoulder limits for every target direction in this
radius range.

### Actuation, simulation, and initialization

**Repository fact:** Each joint is driven by a MuJoCo motor with control range
[-1, 1] and gear 5. The policy action is passed through unchanged and clipped
to that range before being written to `data.ctrl`; there is no position or
velocity command layer. The motors therefore supply a bounded generalized
effort whose nominal scale is 5 actuator-force units at full command, subject
to the joint dynamics and configuration-dependent coupling.

The MuJoCo timestep is 0.002 s. The environment holds each action for 10
simulation steps, giving a 0.020 s control interval. The joints have damping
0.5 and armature 0.01 in the XML. Gravity is zero. The plane and target
geometries have collision disabled, so there are no contact impulses,
support reactions, or obstacle constraints in the task.

**Repository fact:** Reset sets q = [0, 0], qdot = [0, 0], forwards the model,
and then samples the target. Thus the arm initially points along +x at full
extension, with its end effector at approximately (0.22, 0, 0.02) m. The
target is stationary for the episode. An episode lasts at most 500 control
steps, or 10 s, unless success terminates it earlier.

The XML does not explicitly provide body inertials or a density. MuJoCo
therefore constructs the link mass and inertia from its model defaults and
geometries. The authored damping and armature are known, but the resulting
complete mass matrix and exact acceleration response are not specified by the
human-authored source alone.

### Success and learning loop

**Repository fact:** After each 0.020 s action interval, the environment
computes the three-dimensional distance from the end-effector site to the
target. A sample is in tolerance when this distance is at most 0.01 m.
`held_steps` increments on an in-tolerance sample and resets to zero on an
out-of-tolerance sample. Success occurs at 100 consecutive in-tolerance
control samples, corresponding to 2 s. An out-of-tolerance sample after a
partial hold interrupts that hold; truncation at 500 steps is failure.

The current operational check is made at the post-interval state, after the
ten MuJoCo substeps. It does not inspect the intervening substeps for a
temporary excursion. Thus the implemented sampled criterion is the available
measurement of the contract's uninterrupted hold.

The observation has 11 values: q, qdot, the end-effector-to-target vector,
and four wrapped errors to the two inverse-kinematic elbow branches. The
target is not supplied as a separate raw radius/angle, but q and the relative
vector together determine it in this known geometry. There is no observation
noise, target motion, force sensing, contact sensing, acceleration sensing, or
actuator-state observation.

Training reward combines distance progress, an exponential closeness
potential, incremental hold-progress reward, an action-square cost, a small
penalty after leaving tolerance, and a completion bonus. The reward is a
training signal; the binary episode outcome remains the uninterrupted
100-sample hold. The current policy recipe is a feed-forward PPO policy, so it
does not receive the hold counter, episode time, or the post-hold interruption
flag.

## Physical consequences

The arm has enough nominal workspace for the official targets: the target
annulus lies strictly inside the 0.02 to 0.22 m two-link reach envelope, and
the joint limits leave at least one inverse-kinematic branch available across
the full angular distribution. Reachability is therefore not expected to fail
because a target has no geometric solution. It can still fail through poor
branch selection, joint-limit approach, actuator saturation, or transient
motion.

The reset pose is a kinematic singularity. For a planar two-link arm the
Jacobian determinant is proportional to sin(q2), so q2 = 0 makes the
instantaneous Cartesian Jacobian rank deficient. At reset, both joint torques
initially produce motion primarily transverse to the arm; radial motion is
second-order until the elbow bends. The policy must therefore first create a
useful bent configuration or otherwise execute a coordinated trajectory before
it can efficiently correct all target directions. This reset difficulty is
distinct from the target configurations themselves, which are away from the
fully extended singularity over the official radius range.

The two IK branches provide alternatives rather than redundant labels. They
have different joint angles, inertial coupling, and distances from the joint
limits, so they can have different transient cost and stabilization behavior
even when they produce the same target position. A policy can also move
between branches, but doing so requires a finite joint-space excursion and is
not a free change of representation.

With gravity and contact absent, a target configuration at zero velocity is a
valid static equilibrium without a required supporting force. The central
dynamic problem is consequently acceleration, braking, and residual velocity.
Damping removes velocity, while armature and link inertia resist changes and
the bounded motors limit how quickly the arm can reverse. Because the action
is held for 20 ms, a command chosen from a sampled state can overshoot the
1 cm band before the next decision. Holding is therefore a stabilization
problem, not merely repeated point-to-point reaching; low velocity and a
trajectory that remains inside the tolerance are required simultaneously.

The 1 cm tolerance is measured in Cartesian space, while control is in joint
space. The same joint error can produce different Cartesian errors depending
on the Jacobian, and coupled shoulder/elbow motion changes both coordinates.
Near a singular configuration, a direction that is weakly represented by the
Jacobian requires larger joint motion and is more sensitive to timing and
inertia. Near joint limits, available corrective torque and branch choices can
also become asymmetric.

The observation is sufficient to reconstruct the nominal physical Markov state
(joint positions, joint velocities, and stationary target position) under the
deterministic model. It is not sufficient to reconstruct the success
automaton's history: the policy does not know how many consecutive samples
have already been held or whether a previous hold was interrupted. This does
not prevent a stationary hold, but it removes direct information about the
remaining hold time and can make behavior around first entry and exit depend
on the physical state alone.

The current training radius range excludes the inner 0.06 to 0.14 m portion of
the official distribution. A policy can therefore learn a successful
outer-annulus strategy while remaining scientifically untested on the
shorter-radius targets. Also, uniform scalar radius and uniform angle produce
more target probability per unit area near the base than an area-uniform
annulus; the sampling convention matters when interpreting aggregate
success.

## Unknowns

The following quantities are unresolved before campaign evidence or direct
model measurement:

- The compiled link masses, centers of mass, full configuration-dependent
  inertia matrix, and exact actuator acceleration authority are not stated
  explicitly because inertials and density are absent from the XML.
- The numerical effect of MuJoCo's integration and constraint handling on
  damping, motor saturation, and near-limit motion has not been measured over
  the relevant trajectories.
- It is unknown whether a learned controller will consistently use the open
  or folded IK branch, switch branches, approach joint limits, or exploit a
  common trajectory family across target angles.
- It is unknown how much of the failure rate, if any, will arise during the
  initial reach, during braking/convergence, or from sampled hold
  interruptions. The 1 cm band and 20 ms action interval make these distinct
  mechanisms.
- It is unknown how often continuous physical excursions between the 20 ms
  checks would occur, since the current success logic records only sampled
  distances.
- The observation contains no direct estimate of actuator torque, energy,
  work, or model uncertainty. Any claim about efficiency, robustness, or
  dynamic margin therefore requires derived measurements rather than the
  policy input alone.

## Scientifically meaningful quantities

Across complete episodes, the most informative physical measurements are target
radius and angle; selected IK branch and branch switches; q, qdot, joint-limit
margin, and actuator command/saturation; end-effector Cartesian error separated
into radial and tangential components; Jacobian determinant or conditioning;
time and distance at first tolerance entry; peak velocity and braking
distance; minimum distance; total in-tolerance time; maximum consecutive hold;
number and timing of hold interruptions; and whether failure was truncation or
an interrupted hold. Configuration-dependent work, action variation, and
velocity decay would additionally distinguish a dynamically efficient stable
solution from one that succeeds only through high-frequency corrective effort.
