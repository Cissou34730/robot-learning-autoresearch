# Scientific model of the two-joint reach-and-hold system

This is a planar, torque-actuated, two-link robot whose task is not merely to
reach a point. It must enter a small endpoint-tolerance disk and keep its
moving endpoint in that disk without interruption for the complete two-second
hold. The relevant object of study is therefore the coupled transient and
settling behavior of the arm, not just the existence of an inverse-kinematic
configuration.

## Established facts

The robot has two serial revolute joints, both rotating about the world z axis.
The upper arm and forearm lengths are 0.12 m and 0.10 m. The end-effector site
is at the forearm tip, so with shoulder and elbow angles \(q_1,q_2\), its
planar position is

\[
x = 0.12\cos q_1 + 0.10\cos(q_1+q_2),\qquad
y = 0.12\sin q_1 + 0.10\sin(q_1+q_2).
\]

Its z coordinate is fixed at 0.02 m. Each joint is limited to -170 to 170
degrees. The ideal unconstrained radial workspace is 0.02 to 0.22 m; the
joint limits trim that workspace, but the official target annulus of 0.06 to
0.20 m lies inside the useful two-link workspace.

The official target is stationary, lies in the arm's plane, and is sampled
with radius uniformly from 0.06 to 0.20 m and angle uniformly over the full
circle. Success uses the Euclidean endpoint-to-target distance, with a 0.01 m
tolerance. The official simulator timestep is 0.002 s and each policy action
is held for 10 MuJoCo steps, giving a 0.02 s control interval. The two-second
hold therefore requires 100 consecutive in-tolerance control observations,
within a maximum of 500 control steps.

At reset, both joint positions and velocities are zero. The arm consequently
starts fully extended along positive x, with its endpoint at (0.22, 0, 0.02).
The target is then placed at its sampled polar position at z=0.02. The target
is a mocap body with collisions disabled; the plane also cannot generate
contact. The task is thus a distance constraint, not grasping, contact, or
force interaction.

The action is a two-element value in [-1, 1]. It is passed through unchanged
to two MuJoCo motor actuators, clipped to that interval, and applied as motor
input throughout the ten physics steps. Each motor has gear 5, so the
commanded generalized torque is bounded in magnitude by 5 in the simulator's
torque units. There is no position servo, action-rate limit, actuator state, or
action smoothing in the authored interface.

The model has zero gravity. Each joint has damping 0.5 and armature 0.01.
Link and base shapes define the geometry from which MuJoCo constructs mass and
inertia; no explicit body masses or inertias are authored. The dynamics are
therefore those of a damped, inertially coupled two-link system with direct,
saturated torque input and no gravitational load.

The policy receives 11 noiseless, simulator-state-derived values: the two joint
positions, two joint velocities, the three-dimensional endpoint-to-target
error, and four wrapped angular errors to the two inverse-kinematic elbow
branches. The target position is not separately exposed, but it is recoverable
from the endpoint position and endpoint error. Target velocity, contact
quantities, actuator torque, acceleration, and compiled inertial parameters are
not observations. The observation is measured after each held action has
advanced the simulator.

## Physical consequences

The reset is dynamically and kinematically special. At \(q_1=q_2=0\), the
endpoint Jacobian has rank one: infinitesimal joint motion initially produces
mostly tangential motion and cannot produce first-order inward/outward
endpoint motion. The controller must first bend the arm before it can
efficiently change its radius. A target on the opposite side or near the
minimum radius also starts far from the endpoint, so its solution requires a
large transient before stabilization can begin.

For a target with polar angle \(\theta\) and radius \(r\), the two nominal
inverse-kinematic branches are

\[
q_2 = \mathord{\pm}\arccos
\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)},\qquad
q_1 = \theta -
\operatorname{atan2}(0.10\sin q_2,\;0.12+0.10\cos q_2).
\]

They correspond to opposite elbow signs. Across the official annulus,
\(|q_2|\) is approximately 49 to 150 degrees, so both signs are within the
elbow limit. The shoulder limit means that near some angular edges only one
branch is admissible; in central angular regions both can be admissible.
Consequently, the same endpoint can have distinct joint configurations and
distinct transient dynamics. The observation exposes errors to both branches,
but does not force the policy to choose one.

The endpoint Jacobian, link inertia, and torque limits couple the two control
requirements. Shoulder torque moves both links and has broad endpoint
authority; elbow torque moves only the forearm. Near a straight or folded
configuration, the Jacobian becomes poorly conditioned, so a small Cartesian
correction can require a disproportionate joint motion or a branch change.
The official targets avoid the exact radial workspace boundaries, but the
initial straight configuration is itself singular. Joint-limit proximity and
motor saturation create additional qualitatively different behavior: a policy
may reach the tolerance disk but be unable to arrest its velocity before
leaving it.

With gravity absent, a stationary configuration at the target requires no
steady gravitational torque. The difficult part of holding is therefore
settling the coupled inertial system and rejecting residual motion, not
supporting the arm's weight. Damping dissipates motion, while saturated torque
determines how quickly the controller can brake and correct. Because the
command is constant for 20 ms between observations, late corrections are
quantized in time; a trajectory that looks acceptable at one control sample
can leave the tolerance disk between samples and re-enter later. The success
logic nevertheless resets the hold counter on any sampled out-of-tolerance
endpoint, so oscillatory reachers do not accumulate partial success.

The observation, action, and outcome form a deterministic feedback loop:
current joint state and endpoint error determine the policy action; the held
torques advance the damped two-link dynamics; the resulting endpoint distance
updates both the next observation and the hold counter. Success is consequently
the intersection of reachability, transient control, and 100-step robustness.
Distance alone is insufficient to characterize a successful controller:
endpoint velocity and the controller's remaining braking margin determine
whether an apparent entry is a stable hold or a pass-through.

The physically meaningful trajectory quantities are target radius and angle;
joint positions, velocities, accelerations and limit margins; endpoint
position and error decomposed into radial and tangential components; Jacobian
conditioning and inverse-kinematic branch; commanded and realized joint
torques; time to first entry; endpoint speed and maximum excursion during the
hold; number, timing, and duration of hold interruptions; and the distance
between the final state and the tolerance boundary. These quantities connect
mechanism to episode outcome and distinguish reaching failure, overshoot,
branch/limit failure, and loss of stabilization.

## Unknowns

The XML does not state the compiled masses, centers of mass, full inertia
tensors, actuator transmission details beyond gear, or the numerical
integrator configuration. MuJoCo resolves these from geometry and defaults at
model compilation. Their exact values, and therefore the configuration-
dependent acceleration and braking authority, must not be inferred from link
lengths or damping alone.

Before campaign evidence exists, it is unresolved how much of the official
distribution is limited by the initial singular transient, by torque
saturation, by joint-limit margin, or by post-entry endpoint velocity. It is
also unresolved whether one inverse-kinematic branch has a systematic
stability or sample-efficiency advantage, and whether a policy will switch
branches unintentionally during correction.

The noiseless state observation makes the simulated control problem
Markovian under the authored dynamics, but it does not reveal the actuator
torque actually produced or the compiled dynamics explicitly. The practical
identifiability of those quantities from the observation stream, and whether
the 20 ms feedback rate is sufficient for reliable 100-step holds throughout
the annulus, are empirical questions.

Finally, no pre-campaign claim can be made about the learned policy's success
probability or its failure distribution. The relevant scientific test is not
high average proximity or occasional two-second holds, but at least 196
complete, uninterrupted successes out of the protected 200-episode official
assessment.
