# Scientific model: planar two-joint reach and hold

This is the pre-campaign physical model. It separates facts fixed by the
human-authored task and simulator from consequences inferred from those facts.
There is no campaign evidence yet, so claims about realized policy behavior are
not included.

## Established facts

### Task and physical setup

The robot is a planar serial arm with two revolute degrees of freedom. The
shoulder is anchored at the world origin and rotates about the vertical
(`z`) axis. The upper arm has length 0.12 m and the forearm has length 0.10 m.
The end-effector site is at the distal forearm endpoint. The arm plane is
`z = 0.02 m`; the target is placed in that same plane, so the task distance is
effectively planar even though it is evaluated as a three-dimensional Euclidean
distance. The base and target are visual/non-interacting bodies: the plane and target
sphere are explicitly non-colliding. The arm geoms do not declare collision
filtering overrides, so possible arm self-collision is a compiled-model detail
rather than an assumption here.

Let `q1` be the shoulder angle and `q2` the elbow angle relative to the upper
arm. The endpoint position relative to the base is

```
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2).
```

Both joints have declared ranges of -170 to +170 degrees. The physical arm
therefore has two joint limits, rather than an unrestricted planar two-link
kinematic chain.

The official target has radius uniformly sampled from 0.06 to 0.20 m and angle
uniformly sampled over the full circle. Success requires endpoint distance no
greater than 0.01 m for 100 consecutive control steps. Each control step
holds the action for ten MuJoCo steps of 0.002 s, hence is 0.020 s and the
required hold is 2 s. An episode is truncated after 500 control steps, or
10 s, unless the hold terminates it earlier.

### Actuation and dynamics

Each action has two components in `[-1, 1]`, is clipped to that range, and is
sent unchanged to one motor per joint. Each motor has gear 5, so the nominal
generalized drive is proportional to `5 * action` with saturation at the
actuator control limits. The command is zero-order-held over the ten physics
substeps.

Gravity is zero. Each joint declares damping 0.5 and armature 0.01. The plane
and target cannot contact the arm, and the target has no moving dynamics.
The current MuJoCo compilation gives the base, upper-arm, and forearm body
masses of approximately 0.2011, 0.0990, and 0.0525 kg. The upper-arm and
forearm principal body inertias are approximately
`(1.6827e-4, 1.6827e-4, 1.0815e-5)` and
`(6.1097e-5, 6.1097e-5, 3.6741e-6) kg m^2`, respectively. These values are
compiled consequences of the geometry and MuJoCo defaults, not separately
declared design parameters. The arm capsules retain collision-enabled defaults,
although the plane and target are non-colliding. Reset sets both joint
positions and velocities to zero before forward computation. Thus the initial
arm is straight along positive `x`, with the endpoint at radius 0.22 m, while
every official target is at or inside 0.20 m.

### Sensing and policy interface

The policy receives 11 floating-point values:

* the two joint positions and two joint velocities;
* the three-component endpoint-to-target displacement;
* the four wrapped joint errors to the two analytic inverse-kinematic
  solutions, one elbow-open and one elbow-folded.

The target itself is not a separate observation field, but endpoint position
minus the displacement reconstructs it. The observation contains no explicit
hold counter, previous distance, previous action, episode time, target sample
coordinates, or actuator state. The action is a direct physical command; no
separate low-level position or velocity servo is inserted between policy and
MuJoCo.

The analytic inverse-kinematic branches use

```
q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
```

and the corresponding shoulder angle. Both branch errors are exposed, so the
policy is given an explicit representation of the available elbow choices,
not merely a Cartesian error.

The recorded success state is an environment-level task state. After each
control interval, an in-tolerance endpoint increments a hold streak; one
out-of-tolerance interval resets it. The implementation tests at control
boundaries, not at every 0.002 s substep. The scalar reward combines distance
progress, a closeness potential, linear hold-progress credit, a completion
bonus, action cost, and a small penalty on the first interval outside the band
after a hold has started. The hold exit forfeiture is zero. These terms shape
learning but do not alter the physical success definition.

The training constructor samples radii only from 0.14 to 0.20 m, whereas the
evaluation constructor uses the official 0.06 to 0.20 m range. Evaluation is
deterministic for a frozen policy and reports episode success plus diagnostics
including target geometry, minimum and final distance, first in-tolerance
step, longest hold, in-tolerance time, and hold interruptions.

## Physical consequences

### Reachability and inverse-kinematic multiplicity

For a two-link arm, the unconstrained reachable radii are the annulus
`|0.12 - 0.10| <= r <= 0.12 + 0.10`, or 0.02 to 0.22 m. The official interval
0.06 to 0.20 m is strictly inside that annulus, so radius alone does not make
an official target unreachable. Over this interval the two nominal elbow
solutions range from a moderately bent configuration to a strongly bent one,
and the shoulder range restriction can reject one branch near angular wrap
while leaving the other available. The full official circle therefore appears
kinematically coverable by at least one branch, but the valid branch set is
configuration-dependent.

**Decision relevance:** If failures concentrate on one angular sector, the
scientific choice is between a branch/limit explanation and a general control
explanation; changing the learning method should not be inferred from success
rate alone. **Discriminating evidence:** compute both IK solutions and their
joint-limit margins for every target, then compare those margins with endpoint
error, first reach, and hold interruption. A sector effect that persists after
conditioning on branch feasibility weakens a purely kinematic explanation.

### Initial condition and approach geometry

The reset state is the fully extended, straight configuration at radius
0.22 m. It is outside the official target-radius interval and is a kinematic
singularity for first-order tangential motion: at `q2 = 0`, the endpoint
Jacobian loses the independent direction normally supplied by elbow bending.
Targets near the initial positive-`x` ray are close in Cartesian distance but
still require shortening the chain; targets elsewhere require both shortening
and reorientation. The controller must therefore first leave the straight
configuration before it can efficiently generate arbitrary tangential motion.

**Decision relevance:** This can change whether an apparent slow-reach problem
is treated as an initialization/transient problem or as a broad policy-capacity
problem. **Discriminating evidence:** measure early `q2`, radial and tangential
endpoint errors, action saturation, and time to first reach as a function of
target angle. Rapid loss of the singular configuration with persistent
tangential error would support this mechanism; comparable errors after the arm
is well bent would weaken it.

### Hold is a stabilization problem, not only a reach problem

The 1 cm Cartesian band corresponds approximately to an angular tolerance of
0.01/`r` radians for tangential motion: about 9.5 degrees at 6 cm but only
about 2.9 degrees at 20 cm. The outer targets consequently demand tighter
angular and velocity regulation even though they are closer to the initial
fully extended radius. With no gravity or contact, the main forces that must be
balanced during a hold are actuator torque, link inertia, and joint damping.
Residual velocity, delayed action updates, and overshoot can repeatedly cross
the band. An uninterrupted 100-step streak therefore couples arrival,
convergence, and low-velocity stabilization.

**Decision relevance:** A policy that reaches often but fails the campaign
objective may need to be understood as a stabilizer failure rather than a
reach failure; that distinction changes which scientific hypothesis is tested
next. **Discriminating evidence:** compare first-reach rate with longest hold,
hold interruptions, final distance, joint velocities, and action magnitude,
stratified by radius. Long reaches followed by short streaks support a
stabilization limitation; failure to enter the band supports reach or branch
selection instead.

### Timing and sampled success semantics

The policy has only 50 opportunities per second to change the command, while
the plant integrates at 500 Hz. A command can therefore create an unobserved
within-interval excursion that returns inside the tolerance before the next
task check. Conversely, a boundary sample just outside the band resets the
entire hold streak even if the continuous trajectory was close for most of the
interval. The authoritative task is consequently a discrete 100-sample
streak at the specified control timing, not a separately measured 2 ms
continuous-in-time invariant.

**Decision relevance:** This determines whether a failure is interpreted as
physical instability or as sensitivity to the control/evaluation sampling
boundary. **Discriminating evidence:** retain substep endpoint distances and
velocities alongside control-step distances for diagnostic runs. Substep
crossings without control-boundary crossings would revise the physical
interpretation of "continuous"; repeated boundary-only exits would support a
sampling-sensitive hold failure.

### Observation, action, and task-state coupling

For this deterministic, static-target plant, joint position, joint velocity,
and target displacement are sufficient to describe the physical state needed
for torque control, assuming no hidden actuator dynamics. The two IK-error
pairs also make branch selection directly legible. However, the environment's
hold streak is not observable. Two episodes can present the same physical
state and require the same stabilizing action while differing in how close
they are to termination. A memoryless policy can still solve the physical
stabilization problem, but the observation is not a complete state for the
combined physical-plus-success automaton.

**Decision relevance:** This separates a potentially adequate physical
representation from a possible temporal-credit or recurrent-state issue in
learning. **Discriminating evidence:** compare behavior after entering the
band for the first time with behavior after long successful streaks, and test
whether the same physical observation induces materially different actions or
exit rates. No such difference would weaken the need for explicit hold memory.

### Training distribution and reward incentives

The learned controller is exposed during baseline training to only the outer
0.14 to 0.20 m radial interval, although the official distribution includes
0.06 to 0.14 m. This is a physical generalization gap, not a change to the
official task. The reward gives dense approach signals and positive hold
progress, but because hold exit forfeiture is zero, it does not impose a
direct loss of already accumulated hold credit when a streak breaks. Repeated
partial holds can therefore be less costly in the learning signal than in the
binary episode objective.

**Decision relevance:** Poor inner-radius performance can be attributed either
to untrained geometry or to dynamics/control limitations only after those
regions are separately measured. Similarly, a high shaped return does not
establish uninterrupted success. **Discriminating evidence:** evaluate the
same policy by radius and angle with binary success, longest streak, and
reward components kept separate. A sharp performance change at 14 cm supports
coverage failure; smooth degradation across the full annulus supports a
mechanical or control explanation.

### Qualitatively distinct failure classes

The coupled system permits at least four physically distinct outcomes:

1. failure to approach the target or to choose a feasible branch;
2. approach followed by limit interaction or branch switching;
3. entry into the band followed by oscillatory or velocity-driven exits;
4. a long hold that is interrupted at a control boundary before 100 samples.

These classes can have similar episode rewards and identical binary failure
labels. The useful scientific quantities are therefore target radius and
angle, both IK branch feasibility and joint-limit margins, joint positions and
velocities, endpoint radial/tangential error, action/torque saturation, time
to first reach, longest uninterrupted streak, total in-band time, interruption
count, and distance at interruption. These quantities describe the complete
reach-to-hold behavior and identify which physical explanation remains viable;
they are measurements, not evidence that any one failure class currently
dominates.

## Unknowns

The following are unresolved before campaign evidence exists:

* The compiled link masses, centers of mass, and generalized inertias are not
  stated as scientific parameters in the human-authored model. They are
  inferred by MuJoCo from geometry and defaults. Their values determine the
  acceleration and braking authority available from the nominal motor torque.
* The realized transient response is unknown: rise time, maximum useful joint
  speed, overshoot, settling time, and whether actuator saturation or damping
  dominates at each radius and branch.
* The exact practical behavior near the -170/+170 degree limits is unknown,
  including how much control authority and numerical margin remain before a
  limit is encountered.
* It is unknown whether the collision-enabled arm capsules actually contact in
  the valid joint configurations used by successful solutions, and, if they
  do, how much contact response constrains folded solutions.
* It is unknown whether every target sector has comparable dynamic difficulty
  after conditioning on feasible IK branches. Kinematic reachability does not
  imply equally easy approach or stabilization.
* It is unknown how often a policy enters the tolerance band but cannot sustain
  it, how much of that failure is due to velocity/torque regulation, and how
  much is due to the 50 Hz action update.
* It is unknown whether the unobserved hold counter materially affects the
  learned action sequence; the physical state may be sufficient, but the
  combined task state is not fully represented.
* It is unknown how strongly the outer-radius training distribution transfers
  to the official inner-radius region, and whether any apparent transfer is
  uniform over target angle.
* No evidence yet establishes that shaped reward, training return, or a
  particular learning algorithm predicts the binary 98% objective. Only a
  frozen policy's official 200-episode panel can establish that objective.

The first evidence capable of revising this model should preserve the
reach-to-hold trajectory rather than only its final success bit. In particular,
radius/angle-conditioned endpoint error, joint state and velocity, actuator
command, IK-limit margin, first-reach time, uninterrupted hold length, and
control-boundary versus substep exits can distinguish the unresolved physical
mechanisms without presupposing an intervention.
