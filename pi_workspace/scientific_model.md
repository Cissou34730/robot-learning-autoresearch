# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. Repository statements are recorded as
established facts; deductions are marked as physical consequences; quantities
that cannot be established from the human-authored sources are unresolved
unknowns. There is no campaign evidence yet.

## Established facts

### Embodied morphology and kinematics

The robot is a planar two-revolute-link arm. The shoulder and elbow rotate about
the world `z` axis, so the configuration is \(q=(q_1,q_2)\), with the elbow
angle relative to the upper arm. The upper arm is 0.12 m and the forearm is
0.10 m. The arm plane is at \(z=0.02\) m: the upper-arm body is offset upward
from the base, and both links and the end-effector site lie in that plane
([contracts/robots/two_joint_arm.xml:9-20],
[contracts/robots/two_joint_arm.py:5-7]).

Ignoring the small site offset (the site is at the forearm endpoint), forward
kinematics are

\[
 x=0.12\cos q_1+0.10\cos(q_1+q_2),\qquad
 y=0.12\sin q_1+0.10\sin(q_1+q_2),\qquad z=0.02.
\]

Each joint has a nominal range of -170 to +170 degrees
([contracts/robots/two_joint_arm.xml:13-19]). The unrestricted radial workspace
is the annulus from \(|0.12-0.10|=0.02\) m to \(0.12+0.10=0.22\) m. Official
targets have radii 0.06-0.20 m, so they are inside that annulus rather than
requiring the exact inner or outer singular boundary.

For a target with radius \(r\) and polar angle \(\theta\), inverse kinematics
obey

\[
\cos q_2={r^2-0.12^2-0.10^2\over2(0.12)(0.10)},\qquad
q_1=\theta-\operatorname{atan2}(0.10\sin q_2,\;0.12+0.10\cos q_2).
\]

The two signs of \(q_2\) give the elbow-open and elbow-folded solutions. Over
the official radial interval, \(|q_2|\) is approximately 49.5-150.1 degrees,
and the associated shoulder offset is approximately 22.3-56.3 degrees.
Consequently the official geometry has two analytic branches before joint-limit
filtering; one branch can approach or exceed the shoulder range near certain
directions while the alternative remains interior. The source observation code
explicitly computes both branches
([robot_learning/scenario/observations.py:18-35]).

### Task geometry and episode semantics

At reset, the simulator state is set to \(q=(0,0)\) and
\(\dot q=(0,0)\), then forwarded. The arm therefore begins straight along
positive \(x\), with its end effector at approximately \((0.22,0,0.02)\).
The target is then sampled with angle uniform on \([-\pi,\pi]\) and radius
uniform on [0.06, 0.20] m, and its \(z\) coordinate is set to the arm plane
([robot_learning/scenario/environment.py:83-119]). Initial target distance is
therefore approximately 0.02-0.42 m, depending on target radius and angle.

Success is based on the three-dimensional end-effector-to-target distance. A
control step counts toward the hold when distance is at most 0.01 m; an exit
resets the held count. The MuJoCo timestep is 0.002 s and the environment
advances ten physics steps per action, giving a 0.020 s control interval and
100 required consecutive control observations for the 2 s hold. An episode is
truncated after 500 control steps
([contracts/task_spec.py:6-11],
[robot_learning/scenario/environment.py:52-58,122-168]).

The official distribution covers the full target angle and the 6-20 cm radial
interval. The protected assessment uses 200 episodes and requires at least 196
successes (98%) ([contracts/scenario.md:7-31]). The separate current training
environment samples only radii 0.14-0.20 m
([robot_learning/training/environment.py:14-19]).

### Actuation, simulator, and timing

The two actuators are MuJoCo motors attached directly to the shoulder and elbow.
Each accepts control in [-1,1] and has gear 5
([contracts/robots/two_joint_arm.xml:30-33]). The scenario passes the policy
action through unchanged, clips it to the action bounds, writes it to
`data.ctrl`, and holds it constant for all ten `mj_step` calls
([robot_learning/scenario/policy_io.py:11-17],
[robot_learning/scenario/environment.py:122-133]). Thus the controller is a
50 Hz zero-order-held command source; it is not a joint-position or
velocity-servo interface. In MuJoCo actuator convention the gear sets the
generalized motor scale to 5 times the bounded control, subject to the
compiled actuator semantics.

The XML sets gravity to zero, shoulder and elbow damping to 0.5, and armature
to 0.01; it defines no task contact or collision interaction. The plane,
base, and target geometries have contact disabled, and the target is a
non-colliding mocap body ([contracts/robots/two_joint_arm.xml:2-6,9-27]).
The resulting motion is therefore an internally coupled, damped two-link
system driven by bounded joint torques, without gravitational loading,
external contact, or target reaction forces. The current runtime uses PPO with
a 64-64 tanh MLP, one environment, and observation normalization
([robot_learning/training/current_params.json:1-23],
[robot_learning/train.py:83-136]).

### Sensing and policy interface

The policy receives 11 values: two joint positions, two joint velocities, the
three-dimensional Cartesian error (end effector minus target), and four
wrapped angular errors to the two inverse-kinematic branches
([robot_learning/scenario/observations.py:11-49]). The target position is not
sent as a separate field, but it is recoverable from end-effector position
minus the reported error; the current target is static and its plane is known.
There is no force, contact, acceleration, actuator-state, or explicit
within-interval trajectory sensing. The action is not included in the
observation.

For this deterministic simulator, joint position, joint velocity, and target
error contain the physical state needed for prediction of the next state,
apart from any unexposed compiled simulator state. The four branch errors make
the two principal geometric alternatives explicit rather than forcing the
policy to discover the inverse-kinematic sign only from Cartesian error. The
observation has dependent quantities: Cartesian error and branch errors are
derived from the same configuration and target.

### Outcome and current learning signal

The scalar reward combines distance progress, an exponential closeness
potential, linear hold-progress credit, a small action cost, and a completion
bonus. Leaving the tolerance after any positive held count triggers the
outside-band bookkeeping, but the configured hold-exit forfeiture fraction is
zero ([robot_learning/training/reward.py:16-25,47-107]). The RL algorithm
sees only the scalar total, while evaluation separately records target
geometry, minimum and final distance, first reach step, maximum held steps,
in-tolerance steps, and hold interruptions
([robot_learning/scenario/environment.py:145-168],
[robot_learning/scenario/evaluation.py:40-125]).

## Physical consequences

### 1. Reach is feasible, but branch choice and conditioning matter

**Implication.** The official task is not blocked by gross workspace
infeasibility: every target radius lies between the two-link radial limits, and
the two analytic branches generally satisfy the joint ranges. The controller
must nevertheless select or move toward a branch while coordinating both
joints. Near the inner and outer radial boundaries, the Jacobian loses
conditioning as the arm approaches folded or straight configurations. Near
the shoulder range, one branch can require a large shoulder excursion even
when the other is comfortably interior.

**Decision relevance and assumptions.** This can change whether the first
scientific decision treats failures as target coverage, inverse-kinematic
branch selection, or dynamic trajectory control. It assumes the site is
effectively at the forearm endpoint and that the XML joint ranges are enforced
as ordinary hinge limits. The conclusion is supported by the link geometry,
joint ranges, and branch construction
([contracts/robots/two_joint_arm.xml:13-20],
[robot_learning/scenario/observations.py:18-47]); it would weaken if compiled
kinematics or the site transform differed materially.

**Discriminating evidence.** For each target, compare the realized
configuration to both analytic solutions, joint-limit margin, Jacobian
singular values, and distance by target radius/angle. A high success rate for
one branch but failures concentrated at small or large radii would support a
conditioning explanation; failures independent of geometry would redirect
attention to actuation, learning, or stabilization.

### 2. The dominant control problem is likely braking and stabilization, not
static reachability

**Implication.** A bounded motor command held for 20 ms changes velocity as well
as position. The arm has no gravity to pull it away from a reached target, but
it does have inertia, configuration-dependent coupling, and viscous damping.
A policy that reaches the 1 cm ball with residual velocity or continues to
apply poorly timed torque can cross the boundary and reset the hold. A
successful trajectory therefore needs approach, deceleration, convergence, and
then low-excursion maintenance; endpoint accuracy alone is insufficient.

**Decision relevance and assumptions.** This can change the first choice between
investigating reach efficiency and investigating closed-loop hold behavior. It
assumes the motor gear scale is meaningful as a direct generalized torque and
that the compiled inertias are not negligible. The source support is the
zero-gravity, damping, armature, direct motor, and action-hold configuration
([contracts/robots/two_joint_arm.xml:2-3,13-19,30-33],
[robot_learning/scenario/environment.py:125-143]); the exact authority-to-
inertia ratio is unresolved.

**Discriminating evidence.** Record joint velocity, action/torque, distance,
distance derivative, and the maximum distance during each ten-substep control
interval. Distinctive evidence is rapid first entry followed by repeated
hold interruptions with nonzero velocity; slow failure to enter with low
velocity instead supports a reach or authority limitation.

### 3. The success boundary is a sampled 50 Hz path constraint

**Implication.** The implementation checks distance only after each ten-step
action interval and requires 100 consecutive positive checks. The operative
hold is therefore a 2 s sequence of sampled states, not a separate terminal
pose test. The current checker can miss an excursion that leaves and re-enters
the tolerance within one 20 ms interval, while a boundary-crossing endpoint
resets all accumulated hold time. The 500-step horizon permits at most 10 s
of control time.

**Decision relevance and assumptions.** This can change whether a candidate is
judged to have a convergence problem, an overshoot problem, or a true
steady-hold problem, and whether evaluation diagnostics need substep detail.
It follows directly from the control loop and hold counter
([robot_learning/scenario/environment.py:52-58,130-159]) and the official
timing contract ([contracts/scenario.md:9-14]). It assumes the benchmark uses
the same endpoint semantics as the shared scenario, as stated by the
contract.

**Discriminating evidence.** Compare endpoint distances with all ten
within-action MuJoCo distances and report the longest uninterrupted in-band
interval in physics time. If substep excursions occur without endpoint
interruptions, the sampled semantics are materially masking physical
oscillation; if not, endpoint diagnostics are adequate for this task.

### 4. Observations make the nominal task Markov and branch-aware, but not
control-complete

**Implication.** The policy can infer target geometry and current kinematics
from the observation, and receives explicit errors to both IK alternatives.
For a static target and deterministic simulator this is sufficient in principle
to implement feedback. It cannot directly observe actuator torque after
clipping, acceleration, hidden compiled actuator state, or motion between
control observations. It must infer those from successive position and velocity
observations.

**Decision relevance and assumptions.** This can change whether a poor result
should prompt a sensing/representation decision or a policy/control decision.
The inference assumes no unmodeled state in the motor or simulator affects
future motion; the runtime source guarantees only the listed observation
construction ([robot_learning/scenario/observations.py:27-49]) and action
mapping ([robot_learning/scenario/policy_io.py:11-17]).

**Discriminating evidence.** Check one-step prediction error from identical
observations and actions, compare performance with and without branch-specific
errors, and correlate hold failures with unobserved action saturation or
substep velocity. Prediction error or a strong branch-feature effect would
revise the assumed sufficiency of the representation.

### 5. Official coverage is broader than the current training geometry

**Implication.** The official policy must handle 6-20 cm uniformly in radius
and all angles, while the current training constructor samples only 14-20 cm.
The 6-14 cm region is physically reachable but is not represented by the
current baseline target sampler. Observation normalization is also learned
from the training experience, so inner-target states may be numerically
out-of-distribution even though their kinematics are valid.

**Decision relevance and assumptions.** This can change the first campaign
decision between preserving the current recipe and prioritizing distribution
coverage or evaluating geometry-conditioned generalization. It assumes the
training constructor and saved normalization are used as shown
([robot_learning/training/environment.py:10-19],
[robot_learning/train.py:103-116]) and that the official evaluator samples the
contract distribution ([contracts/scenario.md:7-14]). No claim about the size
of the resulting performance gap is justified before evidence.

**Discriminating evidence.** Use shared-seed success and trajectory diagnostics
binned by radius and angle, with particular separation of 6-14 cm from
14-20 cm. A sharp inner-radius deficit supports distribution coverage as a
first-order issue; uniform performance with failures tied to speed or hold
interruptions weakens that explanation.

### 6. The current reward is only an indirect proxy for robust official success

**Implication.** Progress and closeness rewards encourage entering the target
region, and hold-progress credit rewards consecutive in-band steps. However,
the scalar reward does not explicitly measure velocity margin, distance margin,
joint-limit margin, or substep excursions. Because hold-exit forfeiture is
configured to zero, leaving the tolerance erases the counter in the task
semantics but does not erase prior hold-progress capital in the reward design.

**Decision relevance and assumptions.** This can change whether learning
behavior is interpreted as a policy-capability problem or as a mismatch between
optimization signal and the uninterrupted-success objective. It depends on the
current reward being active in the training environment
([robot_learning/scenario/environment.py:145-154],
[robot_learning/training/reward.py:65-86]); a changed PI-owned reward would
require re-establishing the claim.

**Discriminating evidence.** Compare reward components against actual success,
hold interruptions, minimum distance, and velocity at first entry. If reward
continues to improve while success remains limited by repeated exits, the
proxy is not identifying the relevant robustness variable.

## Unknowns

1. **Compiled mass, inertia, and effective torque authority.** Link geometry is
   specified, but explicit geom density, body mass, full inertia tensors, and
   the compiled actuator-force interpretation are not stated in the human
   sources. This determines acceleration, braking distance, coupling strength,
   and the relative importance of damping and armature. It can change the
   choice between a dynamics-identification measurement and a learning-recipe
   experiment. Source references are
   [contracts/robots/two_joint_arm.xml:13-19,30-33] and
   [robot_learning/scenario/environment.py:52-58]. Extract compiled `model`
   masses/inertias/actuator gains and measure bounded-step response; agreement
   with predicted acceleration supports the model, while unexplained response
   changes revise it.

2. **Settling time and safe approach envelope across the workspace.** The
   equations establish feasibility, not how quickly each target can be reached
   and stopped under ±5-scale commands. Configuration-dependent inertia,
   Jacobian conditioning, damping, and branch choice may make the 500-step
   horizon easy or restrictive. This can change whether the first policy must
   optimize speed, margin, or only stable convergence. Relevant sources are
   [contracts/task_spec.py:7-11],
   [contracts/robots/two_joint_arm.xml:13-19,30-33], and
   [robot_learning/scenario/environment.py:157-159]. Measure time-to-first-
   entry, velocity at entry, overshoot, and hold success over radius, angle,
   and both IK branches; a geometry-dependent settling envelope supports the
   conditioning explanation.

3. **Whether the joint range becomes active in successful trajectories.** The
   analytic alternatives usually avoid the ±170 degree limits, but the
   observation does not expose a joint-limit flag and the source does not
   establish the compiled limit behavior beyond the XML range. This can change
   branch-selection and action-saturation decisions. Sources:
   [contracts/robots/two_joint_arm.xml:13-18] and
   [robot_learning/scenario/observations.py:36-47]. Record minimum limit
   margins and compare the two branch solutions; limit contact clustered in
   failures supports this mechanism, while large margins weaken it.

4. **How much physical motion is hidden between control observations.** The
   endpoint checker and policy operate at 50 Hz, but MuJoCo integrates ten
   substeps. The current evaluation diagnostics record endpoint-derived
   distances, not the substep maximum. This can change whether a stable-looking
   policy is genuinely robust or only exploits sampled checks. Sources:
   [robot_learning/scenario/environment.py:130-168] and
   [robot_learning/scenario/evaluation.py:51-105]. A substep trajectory
   measurement is decisive; no material endpoint/substep discrepancy would
   retire this concern.

5. **The size and mechanism of the training-distribution generalization gap.**
   The gap between official and current training radii is factual, but its
   effect on a learned policy is unknown. It can change the first campaign
   direction toward geometry coverage, representation, or dynamics. Sources:
   [contracts/scenario.md:7-14] and
   [robot_learning/training/environment.py:14-19]. A shared-seed radial
   performance map, including diagnostics for first reach and hold
   interruptions, distinguishes inner-target coverage failure from a
   distribution-independent control failure.

6. **Whether branch features are used as intended by the learned policy.** The
   four branch-relative angles are available, but availability does not prove
   that the policy selects a consistent branch or uses a branch with better
   limit and conditioning margins. This can change the value of interpreting
   failures as inverse-kinematic ambiguity. Sources:
   [robot_learning/scenario/observations.py:18-47] and
   [robot_learning/scenario/evaluation.py:90-106]. Reconstruct branch
   proximity along trajectories and compare branch-consistent versus
   branch-switching paths; stable branch selection with lower interruption
   rates supports the branch mechanism.

## Decision-relevant synthesis

1. **Dynamic authority versus stabilization is the first physical
   distinction.** The task is kinematically feasible, but the policy must
   brake a direct, bounded motor command and keep a moving two-link system
   inside a 1 cm region for 100 control checks. This matters if the first
   decision is to investigate reach or hold capability. It assumes the
   compiled motor scale and inertias materially affect response
   ([contracts/robots/two_joint_arm.xml:30-33],
   [robot_learning/scenario/environment.py:125-159]). Joint velocity, action,
   distance derivative, and substep distance distinguish slow reach failure
   from fast-entry/overshoot failure.

2. **Workspace feasibility does not imply uniform difficulty.** Two analytic IK
   branches exist across the official radial range before joint-limit
   filtering, but inner/outer conditioning and occasional shoulder-limit
   proximity can make target geometry and branch choice decisive. This can
   change whether early work should be interpreted by target geometry rather
   than pooled success
   ([contracts/robots/two_joint_arm.xml:13-20],
   [robot_learning/scenario/observations.py:18-47]). Analytic branch error,
   Jacobian conditioning, joint-limit margin, and success by radius/angle are
   the discriminating evidence.

3. **The official distribution exposes a known coverage risk before any
   policy exists.** The current trainer omits 6-14 cm targets even though the
   official task includes them, so a later success deficit could be
   generalization rather than an inability to control the arm
   ([contracts/scenario.md:7-20],
   [robot_learning/training/environment.py:14-19]). A shared-seed radial
   performance map and the saved normalization statistics' state coverage
   would support or weaken that interpretation.

4. **The observation is plausibly sufficient, but the evaluation view is not
   yet a complete physical diagnosis.** It exposes state, target error, and
   both IK branches, while the current research artifact separates reach and
   hold outcomes but does not expose velocity, torque, limits, or substep
   excursions ([robot_learning/scenario/observations.py:27-49],
   [robot_learning/scenario/evaluation.py:90-125]). This matters when choosing
   between representation, control, and learning explanations. One-step
   prediction, branch usage, velocity-at-entry, and substep trajectories are
   the evidence needed to preserve or revise the nominal Markov and
   endpoint-diagnostic assumptions.

5. **The contract objective is uninterrupted sampled holding, not merely
   reaching.** A policy should be scientifically assessed by the full sequence
   of tolerance membership, including interruptions and convergence margin,
   because a single endpoint exit resets the hold even though prior reward
   credit is not fully forfeited
   ([robot_learning/scenario/environment.py:136-159],
   [robot_learning/training/reward.py:65-91]). If reward improves without a
   corresponding reduction in interruptions, the first decision should be
   guided by the hold mechanism rather than by pooled episode reward.
