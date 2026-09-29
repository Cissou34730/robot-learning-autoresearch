# Scientific model of the two-joint reach-and-hold system

This is the pre-campaign physical model. Repository facts are separated from
their physical implications and from quantities that cannot be established
without campaign evidence. The official task is a planar manipulation problem,
but success is a temporal property of the complete closed loop: reaching the
target is necessary and maintaining the reach without a sampled escape is also
necessary.

## Established facts

The authored system is a deterministic, planar two-link arm with fixed geometry,
direct joint-motor commands, state-derived observations, and a fixed target
sampled at reset. The official contract defines a 1 cm spatial tolerance, a
two-second uninterrupted hold, a 500-step episode limit, and a 98% objective
over the complete target distribution.

### Robot, coordinates, and geometry

The human-authored MuJoCo model has a fixed base at the world origin and two
hinge joints whose axes are the world \(z\) axis. The shoulder joint angle
\(q_1\) rotates the 12 cm upper arm from the positive \(x\) axis; the elbow
angle \(q_2\) is relative to the upper arm, and the 10 cm forearm points at
angle \(q_1+q_2\). Both joint ranges are -170 to 170 degrees. The joints and
links lie at \(z=0.02\) m. The end-effector site is at the forearm tip, so,
ignoring its small visual radius, its position is

\[
p(q)=
\begin{bmatrix}
0.12\cos q_1+0.10\cos(q_1+q_2)\\
0.12\sin q_1+0.10\sin(q_1+q_2)\\
0.02
\end{bmatrix}.
\]

The XML defines capsule link radii of 1.5 cm and 1.2 cm and a 4 cm radius,
4 cm high base cylinder. The plane is visual only: it has both collision
classes disabled. The target is a mocap sphere, not a contact object.

### Actuation and simulation

The two actions are independently clipped to [-1, 1] and passed unchanged to
two MuJoCo motor actuators. Each actuator is attached to one joint with gear 5,
so an action value commands a corresponding generalized motor torque of up to
approximately 5 N m; there is no position-servo or actuator activation state.
An action is held constant for ten physics steps.

The native model timestep is 0.002 s, and the locked MuJoCo model resolves the
unspecified integrator to Euler. The environment therefore updates the policy
at 0.020 s intervals (50 Hz). Each joint has damping 0.5 and armature 0.01 in
MuJoCo units. With the native default density, the resolved moving-link masses
are approximately 0.0990 kg for the upper arm and 0.0525 kg for the forearm;
the effective inertia seen at a joint is configuration-dependent and also
includes the armature. Gravity is explicitly zero. The plane, base, and target cannot supply contact forces because their
collision masks are disabled; the link geoms retain the native collision masks.
There are no external loads, so the relevant plant is a two-link inertial
system with damping, velocity-dependent coupling, joint limits, and direct
torque input (with any link self-collision governed by MuJoCo's native rules).

### Reset, target distribution, and outcome

Every reset sets both joint positions and velocities to zero, then samples
radius and angle independently and uniformly. The official radius is 0.06 to
0.20 m and the angle covers the full \(-\pi,\pi\) range. The target is placed
at the arm's \(z=0.02\) plane and remains fixed. Thus the initial arm is
straight along \(+x\), with end effector at (0.22, 0, 0.02), and its initial
velocity is zero. There is no randomized physical initial state other than
the target.

After each 20 ms action interval, success distance is the three-dimensional
Euclidean distance between the end-effector site and the target. A sample is
inside when this distance is at most 0.01 m. The consecutive in-tolerance
counter increments only on inside samples and resets to zero on any outside
sample. Two seconds therefore require 100 consecutive control samples.
Episodes truncate at 500 control steps (10 seconds) if that hold has not
completed. The official assessment uses 200 independently seeded episodes; at
least 196 must succeed for the 98% campaign objective.

### Observation and policy interface

The policy receives an 11-element deterministic state-derived observation:
the two joint positions, two joint velocities, the three-dimensional
end-effector-to-target displacement, and four wrapped angular differences to
the two nominal inverse-kinematic branches. The branch features are computed
from the known 12 cm and 10 cm lengths as the positive-elbow and
negative-elbow solutions. There is no observation noise, image processing,
target velocity, force sensing, or direct actuator-state observation. The
physical action mapping is the identity.

The research training environment currently samples only radii 0.14 to
0.20 m, although its evaluation environment and the protected benchmark use
the official 0.06 to 0.20 m range. Its shaped reward uses distance progress,
closeness, hold progress, an action cost, and a completion bonus. The
protected final environment assigns zero reward and judges only the physical
hold criterion; reward shaping is not itself an official success condition.

## Physical consequences

The target annulus is statically reachable, but an episode requires more than
an inverse-kinematic pose: the controller must reach, shed motion, and keep the
end effector inside the tolerance for 100 consecutive control observations.
Because any outside observation resets the hold, transient dynamics and
closed-loop stabilization determine success.

### Reachability and alternative configurations

For a target radius \(r\), planar inverse kinematics gives

\[
\cos q_2=\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)},
\]

with the two signs of \(q_2\) giving elbow-open and elbow-folded branches.
The unconstrained radial workspace is 2 to 22 cm. With the actual 170-degree
elbow limits, the smallest radius is about 2.8 cm, so every official radius
is inside the radial workspace. At 6 cm the branches require an elbow angle
of about +/-150 degrees; at 20 cm they require about +/-49 degrees. The
shoulder angle is the target bearing minus the corresponding link-direction
offset. Analytic inspection of these branches shows that at least one branch
is within both joint limits for every official bearing and radius, although
the two branches are not equally available near shoulder-limit bearings.
Consequently, official failure is not forced by a missing target position in
the static kinematic workspace. The policy may choose either branch, and
different torque trajectories can reach the same endpoint without any
orientation requirement.

The target and end effector share a plane, so the three-dimensional tolerance
is physically a 1 cm disk in the \(x,y\) plane. The tolerance is small
relative to link lengths and is evaluated after, rather than continuously
between, the ten internal physics steps. A trajectory can therefore pass
through the disk between observations and still fail to accumulate a hold.
Conversely, entering with nonzero velocity can produce an apparent reach
followed by an immediate counter-reset.

### Coupled reaching, convergence, and holding

The action-to-outcome chain is

\[
u_k \longrightarrow \tau_k \longrightarrow
(q_{k+1},\dot q_{k+1}) \longrightarrow p(q_{k+1})
\longrightarrow \|p-target\| \longrightarrow \text{hold counter}.
\]

The torque changes both joints simultaneously, and the effective inertia and
link coupling vary with configuration. A policy must therefore coordinate
coarse motion from the straight reset, select a feasible branch, reduce
position error, remove residual velocity, and regulate within the tolerance
for 100 observations. The same action magnitude that shortens an approach can
create overshoot or persistent oscillation during the hold. Damping helps
remove energy but does not by itself make the end-effector stationary, and
there is no gravity to provide a passive restoring direction.

The 10-second horizon leaves finite time for this sequence. Since one outside
sample destroys all accumulated hold progress, success probability is governed
by the weakest part of the complete trajectory, not just by minimum distance
or by the fraction of samples spent near the target. The lower official radii
are especially important scientifically: they require strongly folded
postures and are absent from the current training distribution, so performance
on the current training support cannot establish performance over the official
distribution.

### Observability and ambiguity

For this deterministic model, joint position and velocity plus the
end-effector-to-target displacement contain the instantaneous mechanical state
and target relationship needed for a Markov control decision. Since the
observation includes joint position and known link geometry, the target
relationship can be reconstructed even though absolute target coordinates are
not separately reported. The two branch errors make the principal static
solution ambiguity explicit.

There is no hidden sensor noise or unmodeled actuator lag in the authored
interface. However, wrapped angular differences are representations rather
than additional physical measurements, and their numerical transitions near
the wrap boundary can make equivalent angular relationships look
discontinuous. The observation also omits forces, torque margins, contact
events, and future target information. These omissions matter mainly for
diagnosing why a policy leaves the tolerance, not for identifying the
instantaneous target position.

### Quantities that describe the physical behavior

Meaningful trajectory quantities are target radius and bearing; both joint
positions, velocities, and joint-limit margins; commanded torques; Cartesian
distance and radial/tangential error; first-entry and settling time; peak
speed near entry; longest consecutive in-tolerance run; number and timing of
hold interruptions; and distance at timeout. These distinguish static
reachability failure, slow convergence, overshoot, branch or limit effects,
and loss of stabilization. They are more informative for the human objective
than an undifferentiated return because only the longest uninterrupted run
determines episode success.

## Unknowns

The following are unresolved before campaign evidence and should not be
treated as established policy capabilities:

* The closed-loop settling time, overshoot, and residual end-effector speed
  achievable across the full radius-bearing distribution are unknown. The
  XML fixes the plant parameters, but it does not establish that a learned
  policy can exploit the available torque authority with sufficient margin.
* It is unknown whether one branch is materially easier to stabilize than the
  other once configuration-dependent inertia, coupling, damping, action
  discretization, and the joint limits are combined. Static inverse
  kinematics alone cannot answer that question.
* The distribution of failures between initial approach, first entry,
  intermittent boundary crossings, and late hold loss is unknown. In
  particular, no evidence yet shows whether the difficult cases are the
  folded low-radius targets, bearings near the shoulder limits, or another
  dynamical class.
* It is unknown whether the current 0.14--0.20 m training support produces a
  policy that extrapolates reliably to 0.06--0.14 m, where the required
  posture and branch geometry differ substantially.
* The observation is physically sufficient for a deterministic Markov
  controller in the authored model, but it is unknown whether its wrapped
  branch features and lack of force or torque information make learning a
  robust 100-sample regulator. No campaign evidence yet supports a claim of
  98% episode success.
