# Scientific model of the robot and task

## Task and physical setting

**Established fact.** The robot is a planar serial arm with two revolute joints.
Both joint axes are the world z axis, so motion is in the horizontal x-y plane.
The upper arm is 0.12 m long and the forearm is 0.10 m long. The arm is mounted
0.02 m above the world origin; the end-effector site therefore remains at
`z = 0.02` for this model. The target is a non-actuated MuJoCo mocap body whose
z coordinate is set to that same plane. The floor and target have collision
disabled, and the XML defines no obstacle or contact interaction for the task,
so the target is a geometric reference rather than a physical object with which
the arm can collide or make contact.

**Established fact.** Each joint is limited to -170 to +170 degrees. The
official target has a uniformly sampled radius from 0.06 to 0.20 m and a
uniformly sampled angle over the full circle. Radius and angle are sampled
independently, so this is not a distribution uniform in planar area.

**Physical or scientific consequence.** With shoulder angle \(q_1\) and relative
elbow angle \(q_2\), the end-effector position relative to the base is

\[
 x = 0.12\cos q_1 + 0.10\cos(q_1+q_2), \qquad
 y = 0.12\sin q_1 + 0.10\sin(q_1+q_2).
\]

Ignoring joint limits, the radial workspace is 0.02 to 0.22 m. The official
annulus lies inside that workspace: its inner radius is well outside the
folded limit and its outer radius is close to, but below, maximum extension.
The complete angular distribution therefore requires orientation-independent
use of the arm, not only motion in the initial +x direction. Joint limits can
remove an individual inverse-kinematic branch near angle wrap boundaries, so
the admissible branch must be considered rather than assuming every algebraic
solution is physically legal.

**Established fact.** For a reachable target at radius \(r\), the observation
code computes two nominal inverse-kinematic elbow choices,

\[
q_2 = \mathord{\pm}\arccos\left(
\frac{r^2 - 0.12^2 - 0.10^2}{2(0.12)(0.10)}
\right),
\]

and computes the corresponding shoulder angles. These are the elbow-open and
elbow-folded configurations, with each angle wrapped when represented as an
error.

**Physical or scientific consequence.** The same target position can generally
be reached with two distinct arm postures: an elbow on either side of the
shoulder-to-target line. The postures have different joint velocities,
Jacobian geometry, and transient torque requirements even though their
end-effector positions coincide. The arm is not redundant for a fixed
planar pose, but it has this discrete inverse-kinematic ambiguity.

**Unknown.** The implementation establishes geometric reachability and the
available branches, but not which branch a learned controller will select,
whether it will switch branches, or how close its realized trajectory will
come to a joint limit.

## Actuation, timing, and dynamics

**Established fact.** MuJoCo integrates the model at a 0.002 s timestep with
gravity set to zero. Each joint has 0.5 damping and 0.01 armature. Each motor
has control range [-1, 1] and gear 5. The environment clips the two policy
outputs to this range, writes them to `data.ctrl`, and holds the same controls
for ten physics steps. Thus the high-level control interval is 0.020 s
(50 Hz), while the physical state is advanced at 500 Hz.

**Established fact.** No explicit body mass, inertial tensor, friction
coefficient, actuator force range, or joint stiffness is specified in the XML.
MuJoCo consequently constructs the body inertias from the modeled geoms and its
defaults; the XML itself does not expose a separately chosen mass or
inertia parameter. There is no position servo: the motor command is a
generalized actuator command transmitted to the hinge.

**Physical or scientific consequence.** Away from contacts, the arm behaves as
a coupled two-link second-order system. A command changes joint torque and
therefore angular acceleration; it does not directly prescribe a joint angle or
end-effector position. The nominal motor torque scale is gear times control,
so the command bounds correspond to a nominal +/-5 torque at each hinge,
subject to the simulator's actuator and transmission conventions. Damping
opposes joint velocity, and armature adds reflected rotational inertia. With
gravity absent, there is no gravitational sag to compensate, but momentum,
coupled link inertia, and damping still determine how quickly the arm can
approach and settle at a target.

**Physical or scientific consequence.** Each policy action is piecewise constant
over 20 ms, and the success distance is evaluated only after those ten
substeps. The controller therefore has authority to shape a continuous
trajectory at the physics rate but receives and changes commands at a slower
sample rate. Reaching is a transient control problem; holding requires
reducing end-effector velocity and applying corrections that do not repeatedly
push the end effector outside the 1 cm band.

**Unknown.** Exact accelerations, settling times, overshoot, and the torque
needed for a given maneuver cannot be determined from the XML constants alone
without the simulator's fully resolved inertial defaults and an executed
trajectory. The implementation also does not reveal the behavior of a policy
under saturation.

## Initial state and success semantics

**Established fact.** On reset, both joint positions and velocities are set to
zero, the model is forwarded, and then a new target is sampled. The initial
configuration is therefore a straight arm along +x, with the end effector at
approximately `(0.22, 0, 0.02)`, and the target is stationary for the episode.
The reach task has no moving-object or contact dynamics.

**Physical or scientific consequence.** Every episode starts from the same
mechanical state but with a different target direction and radius. The initial
motion must turn the arm from the +x reference configuration when the target
is elsewhere. The policy must solve both a global repositioning problem and a
local regulation problem; the latter begins only after the end effector enters
the tolerance region.

**Established fact.** The end-effector succeeds at a control step when its
three-dimensional distance from the target is at most 0.01 m. The hold counter
increments only on such a step and resets to zero on any step outside. With a
0.020 s control interval, 2 seconds requires 100 consecutive successful
control samples. An episode can run for at most 500 control steps, and
termination occurs on the complete hold rather than merely on first entry.

**Physical or scientific consequence.** A near-target pass is not sufficient:
the trajectory must enter the disk and remain there for an uninterrupted
sampled dwell. A single excursion beyond the boundary loses all accumulated
hold time. The relevant terminal behavior is therefore convergence plus
low-velocity stabilization, not just endpoint accuracy. Because the benchmark
checks distance after each ten-step block, its operational meaning of
continuous hold is continuity at the 50 Hz control samples; excursions between
checks are not separately recorded by the success logic.

**Unknown.** No observation or implementation-only analysis determines the
policy's actual convergence time, boundary margin, or probability of leaving
the band after entry. Those require observing trajectories.

## Sensing and observation

**Established fact.** The raw observation has 11 values: the two joint
positions, two joint velocities, the three-dimensional vector from the target
to the end effector, and four wrapped joint-space errors to the two computed
inverse-kinematic solutions. There is no sensor noise or latency model in this
observation function. The action, actuator torque, hold counter, episode step
count, and previous distance are not included.

**Physical or scientific consequence.** Joint configuration and velocity are
directly available, so the instantaneous mechanical state relevant to this
no-external-contact model is largely observable. The target is not given
as a separate absolute sensor measurement, but it is reconstructable from the
known end-effector position and the observed end-effector-minus-target vector.
The inverse-kinematic error features make both geometric posture choices
explicit, while the current joint angles identify which side of each choice
the arm occupies.

**Physical or scientific consequence.** The observation supports feedback based
on both task-space error and joint-space regulation. It does not explicitly
tell the controller how long it has held the target, what command is currently
being applied, or how much actuator effort remains before saturation. A
controller must infer any temporal phase such as “approaching” versus
“stabilizing” from configuration and velocity, while the environment—not the
observation—maintains the success counter.

**Unknown.** Whether a particular learned policy uses the direct error,
inverse-kinematic features, velocities, or implicit temporal memory cannot be
inferred from the observation definition. Any policy-side normalization is a
runtime representation of these values, not additional physical sensing.

## Capabilities, constraints, and scientifically meaningful quantities

**Physical or scientific consequence.** Success requires four separable
capabilities: selecting an admissible inverse-kinematic posture, moving both
joints through the coupled dynamics, converging to less than 1 cm task-space
error, and regulating velocity and torque sufficiently to maintain that error
for 2 seconds. Qualitatively different outcome classes follow from the fixed
constraints: a kinematic-limit outcome has no legal branch for the attempted
posture, a dynamic outcome misses or overshoots during transit, a control
outcome remains near the target but crosses the tolerance boundary, and a
timing outcome enters the band but cannot complete the uninterrupted dwell.
These are physical classes of behavior, not claims about which class currently
occurs.

**Established fact.** The benchmark outcome uses only the distance sequence and
the consecutive-hold rule. The training environment may expose distance,
held-step count, and reward attribution, but those signals do not alter the
robot mechanics or the official success definition.

**Scientifically meaningful quantities** for characterizing this system include
target radius and angle; joint position, velocity, and acceleration; end-effector
position and velocity; task-space distance and signed error; the planar Jacobian
and its conditioning; selected inverse-kinematic branch; commanded and realized
joint torque; saturation fraction; approach time; overshoot; boundary margin;
longest consecutive in-band duration; and the number and timing of exits from
the tolerance region. Together these quantities distinguish geometric
reachability, transient control, and stabilization without conflating them with
the binary episode result.

**Unknown.** The implementation alone cannot establish empirical distributions
of those quantities, the controller's selected posture, or the causes of any
individual unsuccessful episode. Those are properties of realized behavior,
not deductions from the robot and task definitions.
