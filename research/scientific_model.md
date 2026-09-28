# Scientific model of the two-joint reach-and-hold system

## Scope

This is a pre-campaign model: it uses the human-authored scenario, robot model,
and benchmark execution semantics, but no trained behavior or campaign
measurements. The task is free-space planar manipulation. The target is not
grasped or contacted; success is a geometric relationship maintained while the
arm's inertial and damped dynamics continue to evolve.

## Established facts

The human-authored implementation fixes the robot, simulator timing, reset
state, observation construction, target distribution, and complete-hold
success semantics described below.

### Morphology and kinematics

The robot has two serial revolute joints in the horizontal \(x\)-\(y\) plane.
The shoulder angle is \(q_1\), the elbow angle is the relative joint angle
\(q_2\), the upper arm is \(l_1=0.12\) m, and the forearm is \(l_2=0.10\) m.
The end effector is therefore

\[
x=l_1\cos q_1+l_2\cos(q_1+q_2),\qquad
y=l_1\sin q_1+l_2\sin(q_1+q_2),\qquad z=0.02\ {\rm m}.
\]

Both joints are limited to \([-170^\circ,170^\circ]\). Without those angular
limits, the reachable radial interval is
\([|l_1-l_2|,l_1+l_2]=[0.02,0.22]\) m. The official target radii
\([0.06,0.20]\) m lie strictly inside this annulus, away from both radial
singular boundaries. Target angle is uniform over the full circle and target
radius is uniform over its interval (not uniform by area).

For a reachable target, inverse kinematics generally has two configurations:
\[
q_2=\pm\arccos\left(
\frac{r^2-l_1^2-l_2^2}{2l_1l_2}\right),
\]
with the corresponding shoulder angle chosen to point the two-link chain at
the target. Over the official radius range, \(|q_2|\) is approximately
49.5--150.1 degrees, so the elbow limit does not remove these mathematical
branches. The shoulder limit can remove a branch near some angular boundaries,
but the other branch remains available over the stated target distribution.

### Actuation, timing, and physical state

Each joint is driven by a direct MuJoCo motor. The policy action is clipped to
\([-1,1]^2\), passed unchanged as the physical command, and multiplied by a
gear of 5; hence the available generalized motor torque is nominally up to
5 N m in either direction. There is no position or velocity servo hidden
between the policy and the joints.

The XML timestep is 0.002 s. One policy action is held for 10 MuJoCo steps,
giving a 0.020 s control interval and a 50 Hz policy loop. The model has
gravity disabled. The compiled geometry-derived moving-body masses are about
0.099 kg for the upper arm and 0.0525 kg for the forearm; each joint has
0.5 N m s/rad damping and 0.01 kg m2 armature. The compiled principal
inertias of those two bodies are approximately
\((1.68\mathord{\times}10^{-4},1.68\mathord{\times}10^{-4},
1.08\mathord{\times}10^{-5})\) and
\((6.11\mathord{\times}10^{-5},6.11\mathord{\times}10^{-5},
3.67\mathord{\times}10^{-6})\) kg m2, respectively; these values are derived
from capsule geometry and density rather than explicitly specified. The plane,
target, and arm do not provide a task-relevant contact constraint: the plane
and target are non-colliding, and the task is intended to be solved through
inertial motion and damping.

At reset, both joint positions and velocities are zero. The arm is straight
along positive \(x\), placing the end effector at \((0.22,0,0.02)\) m. A
target is then sampled at its radius and angle in the same \(z=0.02\) plane.
The initial target is at least 0.02 m from this end-effector configuration,
so no official reset is already inside the 0.01 m success tolerance.

### Task and observation-to-action relationship

The official tolerance is a 0.01 m three-dimensional Euclidean distance. After
each 0.020 s control interval, the distance is tested. A successful episode
requires 100 consecutive in-tolerance samples, corresponding to 2 s, and an
episode can run for at most 500 control steps. A sample outside the tolerance
resets the consecutive hold count.

The policy receives 11 values: the two joint positions, two joint velocities,
the three-dimensional end-effector-to-target displacement, and four wrapped
angular errors to the open and folded inverse-kinematic solutions. Thus the
target is not supplied as an absolute coordinate, but its relative position is
observed and, together with known robot geometry and joint state, determines
the relevant target geometry. Joint velocity is observed, while acceleration,
motor torque, contact force, and any unmodeled disturbance are not.

The action changes joint torque; torque changes joint acceleration through the
coupled two-link inertia, damping, and armature; the resulting joint state
changes the end-effector position and the next observation. The current
research reward adds distance progress, a closeness potential, hold-progress
increments, a small action cost, and a completion bonus. Those terms can shape
learning, but only the uninterrupted geometric hold is the task outcome.

## Physical consequences

The reachable target set is well matched to the arm, but not all target
directions are dynamically equivalent. The shoulder limit makes configurations
near the negative \(x\) direction approach a joint boundary, while the
two-branch structure offers a choice of elbow posture and shoulder
configuration. That choice changes the Jacobian, inertial coupling, and
distance to joint limits even when the end-effector target is identical.

The controller must solve a coupled sequence rather than a single positional
command. It must leave the straight initial posture, select or transition
toward a valid inverse-kinematic branch, reduce Cartesian error, and then
regulate both joints so that the end effector stays inside a very small disk.
Near a kinematic singularity the map from joint motion to Cartesian motion
loses authority in one direction; the official radii avoid the exact
singularities, but the outer and inner ends of the range can still have
different conditioning. A posture that reaches quickly may be a poor hold
posture if its Jacobian or joint-space damping converts small torque or
velocity errors into Cartesian boundary crossings.

The arm is underactuated only in the practical control sense that each action
is a bounded torque applied to a second-order system; it is not position
teleported. The shoulder torque affects the whole chain, whereas elbow torque
primarily changes the distal relative motion. Because gravity and contact do
not stabilize the endpoint, holding requires active cancellation of residual
velocity and management of the coupled inertia. Damping helps dissipate
motion but does not by itself place the endpoint at the target. The same
action magnitude can produce different endpoint accelerations at different
postures, so a fixed action-to-position heuristic is physically incomplete.

The 20 ms zero-order-held action creates a meaningful sampled-data constraint:
the policy cannot react inside an interval. The benchmark checks the distance
after each ten-substep interval, so its operational definition of an
uninterrupted hold is 100 consecutive checked samples. Motion between those
checks is not separately recorded by the success counter; consequently,
within-interval overshoot is a control risk for the subsequent sample rather
than an independently measured failure.

The observation contains enough nominal state and target-relative geometry for
feedback control in this deterministic model, but it does not expose the
instantaneous mass matrix, actuator torque, or future target motion. The
inverse-kinematic error channels make the two nominal postures explicit, yet
they do not force the policy to choose one. Wrapped angles also make equivalent
representations at the \(-\pi/\pi\) boundary, so branch choice and joint-limit
margin must be inferred from the complete observation rather than one angle
alone.

Meaningful physical measurements of complete behavior are: target radius and
angle; joint position, velocity, and distance to each joint limit; Cartesian
position error and its radial/tangential components; endpoint speed and
acceleration; commanded torque and torque changes; first entry time; minimum
distance; longest consecutive in-tolerance interval; distance margin during
the hold; and whether an interruption follows overshoot, residual velocity,
branch transition, or a joint boundary. These quantities separate reach,
convergence, stabilization, and hold failures even though the official metric
collapses them to one episode success bit.

## Unknowns

Before training there is no evidence for which inverse-kinematic branch a
learned policy will prefer, whether it will switch branches during approach,
or whether its preferred posture remains well conditioned throughout the
target distribution. The reachable set therefore cannot be treated as a
prediction of learned success.

The model specifies nominal inertia, damping, torque limits, and integration
timing, but the resulting transient response is posture-dependent and has not
been measured. In particular, the maximum practical angular acceleration,
settling time, overshoot under a held action, and endpoint motion caused by
small residual joint velocities are unresolved. The effect of the 50 Hz
sampling interval on the 1 cm boundary is likewise a quantitative question,
not something established by reachability.

It is also unresolved whether the 11-dimensional representation is used
efficiently: the relative target vector is sufficient in principle, while
the four inverse-kinematic error channels may help branch selection or may
create competing local control strategies. No pre-campaign claim can be made
about robustness to target angles near joint-limit margins, about the
distribution of hold margins after convergence, or about the relationship
between shaped reward and complete-hold probability. Those are behavioral
quantities to be measured without replacing the official success definition.
