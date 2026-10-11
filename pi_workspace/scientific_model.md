## Established facts

### Robot morphology and coordinates

[Repository fact] The robot is a serial two-link arm attached to a fixed world
base. The shoulder and elbow are both hinge joints about the world z axis, so
the mechanism has two generalized coordinates and moves in the x-y plane at
z = 0.02 m. The upper arm length is 0.12 m and the forearm length is 0.10 m;
the end-effector site is at the distal forearm endpoint. The base is not a
free body and there is no floating-base degree of freedom. [Source:
`contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`, `forearm`,
`shoulder`, `elbow`, `end_effector`); `contracts/robots/two_joint_arm.py`
(`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`).]

[Repository fact] The joint coordinates are bounded independently to
-170 to +170 degrees. The XML does not define joint friction, joint
actuator dynamics, gravity, or a transmission other than the two hinge motors.
Each link has a capsule visual/collision geom, while the base cylinder is
non-colliding. [Source: `contracts/robots/two_joint_arm.xml`.]

[Repository fact] With shoulder angle q1 and relative elbow angle q2, the
end-effector position relative to the base is

`p(q) = [0.12 cos(q1) + 0.10 cos(q1+q2), 0.12 sin(q1) + 0.10 sin(q1+q2), 0.02]`.

This follows from the nested body offsets and the site location; the
implementation uses the same lengths when constructing inverse-kinematic
features. [Source: `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py` (`shoulder_for_elbow`,
`FOREARM_LENGTH`, `UPPER_ARM_LENGTH`).]

### Official initial state and target

[Repository fact] Reset sets both joint positions and both joint velocities to
zero, performs forward kinematics, and then samples one fixed target for the
episode. The target angle is uniform on [-pi, pi] and its radius is uniform on
[0.06, 0.20] m. Its z coordinate is copied from the initial end-effector
height, so the target is in the arm's plane. The initial end effector is
therefore at (0.22, 0, 0.02) m, while the target is random. [Source:
`contracts/scenario.md`; `contracts/task_spec.py`
(`TARGET_RADIUS_RANGE`); `robot_learning/scenario/environment.py`
(`reset`, `_sample_target_position`).]

[Repository fact] The target is a mocap body whose position is sampled at
reset and is not changed by `step`. Its sphere and the visual plane are
non-colliding. The success test uses Euclidean distance from the end-effector
site to the mocap position, not contact, force, orientation, or target-body
motion. [Source: `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py` (`_distance_to_target`, `step`).]

### Actuation, simulation clock, and task clock

[Repository fact] The MuJoCo model has zero gravity and a simulation timestep
of 0.002 s. Each motor accepts a control in [-1, 1] and has gear 5. The
environment clips the policy output to that interval, writes the two values to
`data.ctrl`, and advances ten MuJoCo steps before producing the next
observation. The control interval is therefore 0.020 s (50 Hz), with the
same command held over its ten internal steps. [Source:
`contracts/robots/two_joint_arm.xml` (`gravity`, `timestep`, `motor`);
`robot_learning/scenario/environment.py` (`step`, `frame_skip`).]

[Repository fact] Each joint has damping 0.5 and armature 0.01 in the XML.
The motor gear and control limit define a nominal signed motor generalized
force of up to 5 control units at the joint, subject to MuJoCo's compiled
actuator and dynamics semantics. No explicit force limit, actuator time
constant, or controller-side position/velocity servo is declared. [Source:
`contracts/robots/two_joint_arm.xml` (`damping`, `armature`, `motor`).]

[Repository fact] A target hold requires distance at or below 0.01 m for
2.0 s, represented by 100 consecutive environment control steps. An episode
has at most 500 control steps. Official assessment uses 200 independently
sampled episodes and requires at least 196 successes (98 percent). [Source:
`contracts/scenario.md`; `contracts/task_spec.py`; `robot_learning/scenario/environment.py`
(`hold_steps_required`, `terminated`, `truncated`).]

### Sensing and policy interface

[Repository fact] The current policy observation has 11 float32 entries:
two joint positions, two joint velocities, the three-dimensional
end-effector-to-target vector, and four wrapped joint-angle errors to the two
analytic inverse-kinematic branches (open and folded). The observation is
computed from simulator state and known link lengths; it is not a simulated
noisy sensor. [Source: `robot_learning/scenario/observations.py`
(`OBSERVATION_SIZE`, `reach_observation`).]

[Repository fact] The action interface is a two-element float vector. The
current policy I/O maps it identically to physical action, and the environment
performs the authoritative clipping. The policy receives no explicit target
radius, target angle, distance scalar, torque, acceleration, hold counter,
success flag, or contact force. [Source:
`robot_learning/scenario/policy_io.py`; `robot_learning/scenario/environment.py`
(`observation_space`, `action_space`, `step`).]

[Repository fact] The policy runtime may normalize observations and may carry
recurrent state, but it resets its recurrent state at episode start. The
environment owns physical reset; the current policy-I/O reset hook is absent.
[Source: `contracts/policy_runtime.py` (`PolicyRuntime.reset`, `predict`);
`robot_learning/scenario/environment.py` (`reset`);
`robot_learning/scenario/policy_io.py` (`make_policy_io`).]

### Task outcome and measurable physical quantities

[Repository fact] Success is the task outcome, not ordinary Gymnasium
termination. The environment records distance, held-step count, and whether
the hold has completed. The research evaluator additionally records target
radius and angle, minimum and final distance, first in-tolerance step, maximum
held run, total in-tolerance steps, and hold interruptions. [Source:
`contracts/scenario.md`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py` (`episode_diagnostics`).]

[Repository fact] The reward contains distance progress, exponential closeness,
hold progress, an action cost, and a completion bonus. It is researcher-owned
training code and is not the official success definition. [Source:
`robot_learning/training/reward.py`; `contracts/scenario.md`.]

## Physical consequences

### Reachable workspace and inverse-kinematic alternatives

[Reasoned implication] Ignoring collision contacts, the unconstrained radial
workspace of the two-link position is from
`|0.12-0.10| = 0.02 m` to `0.12+0.10 = 0.22 m`. The official radial interval
0.06--0.20 m lies strictly inside those radial limits. The joint limits also
permit both analytic configurations for every official target: the elbow
solutions satisfy approximately q2 in +/-150 degrees at 0.06 m and
approximately +/-49 degrees at 0.20 m, with corresponding shoulder angles
that remain within +/-170 degrees over the full target angle range. Thus
geometry alone does not make any official target unreachable. [Source:
`contracts/scenario.md`; `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`.]

**Decision relevance:** A policy need not learn to reject unreachable targets,
but it must select or implicitly realize one of two valid elbow branches and
control the approach through a branch-dependent joint trajectory. Branch
coverage and target-angle coverage are more meaningful than a single nominal
pose.

**Assumptions:** This conclusion assumes the compiled model follows the XML
kinematic tree, the target remains in the stated plane, and link contact does
not block a mathematically valid branch.

**Source references:** `contracts/scenario.md`;
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py` (`elbow_open`, `elbow_folded`).

**Discriminating evidence:** For representative radii and angles, forward
kinematics of both branch solutions can be checked against the target while
recording joint-limit and contact status. A branch- or angle-dependent
success deficit would weaken the claim that geometry alone explains
performance.

### Singular structure, precision, and trajectory control

[Reasoned implication] The planar Jacobian has determinant
`0.12 * 0.10 * sin(q2)`. The reset pose q2 = 0 is therefore a straight-arm
kinematic singularity: an instantaneous joint perturbation cannot generate
Cartesian velocity in every planar direction. The arm must first leave that
configuration before it can efficiently correct arbitrary target direction.
Near a nonzero target, the mapping from joint error to Cartesian error also
depends on the Jacobian, so the same 1 cm Cartesian tolerance corresponds to
different joint-space tolerances across configurations. [Source:
`contracts/robots/two_joint_arm.xml` (joint tree and reset-compatible zero
pose); `robot_learning/scenario/environment.py` (`reset`);
`robot_learning/scenario/observations.py` (forward/inverse geometry).]

**Decision relevance:** Reaching, stopping, and holding are coupled. A
controller that only drives toward an inverse-kinematic pose can overshoot the
1 cm ball; a controller that damps too early may spend the 500-step horizon
converging. Initial-direction behavior and near-tolerance velocity are
mechanistically relevant diagnostics.

**Assumptions:** The Jacobian argument assumes the site position is the
controlled task point and that no contact or hidden compliance dominates the
motion. It does not by itself predict the time to leave the singularity.

**Source references:** `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/observations.py`.

**Discriminating evidence:** Compare early end-effector velocity and
first-reach time for targets with different initial directions, and relate
distance error to q2, joint velocity, and action. Persistent slow or
direction-specific starts would support a singularity-limited explanation.

### Torque-driven dynamics, damping, and control authority

[Reasoned implication] The action is not a position setpoint: it is a bounded
joint torque command held for 20 ms. Joint acceleration is consequently
limited by the compiled inertia and modified by the 0.5 damping and 0.01
armature terms. With gravity disabled, there is no gravitational torque to
cancel; damping opposes velocity, while motor torque is the principal source
of motion. The same action has configuration-dependent Cartesian effect
because the Jacobian changes with q. [Source:
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/policy_io.py`.]

**Decision relevance:** The first campaign decision may differ between
position-like feedback, velocity-aware feedback, and trajectory shaping.
Action saturation, residual velocity, and command persistence can cause
overshoot even though the nominal target pose is statically easy.

**Assumptions:** The qualitative conclusion assumes the motor gear produces
the expected bounded generalized force and that no unmodeled actuator
dynamics or contacts dominate. Quantitative acceleration and settling-time
claims require compiled inertial parameters.

**Source references:** `contracts/robots/two_joint_arm.xml` (`motor`,
`damping`, `armature`, `gravity`); `robot_learning/scenario/environment.py`
(`frame_skip`, `data.ctrl`).

**Discriminating evidence:** Record q, qdot, action, and end-effector
trajectory at every control boundary, and compare saturated versus
unsaturated episodes. A torque-step response or inverse-dynamics check can
separate inertia/damping limitation from policy timing or target-geometry
effects.

### Passive static equilibria versus dynamic holding

[Reasoned implication] In the stated no-gravity, no-target-contact model, a
stationary configuration with zero joint velocity and zero motor torque has
no declared external generalized load. Therefore the target pose can in
principle be held passively after the arm settles; the controller mainly has
to remove kinetic error and keep disturbances or numerical drift from
reappearing. The 1 cm criterion still makes residual velocity important:
crossing the tolerance boundary resets the uninterrupted hold counter.
[Source: `contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`
(`_distance_to_target`, hold update).]

**Decision relevance:** A policy may succeed by approaching, braking, and
letting damping settle rather than by continuously applying a position
servo. This changes how hold failures should be interpreted: a failure after
first reach can be a braking/settling failure rather than a reachability
failure.

**Assumptions:** This is conditional on absent self-contact, numerical
artifacts, and disturbances. It also assumes the official implementation
does not add a hidden target force or a finer-grained hold test.

**Source references:** `contracts/robots/two_joint_arm.xml` (`gravity`,
target geom); `robot_learning/scenario/environment.py` (`step`).

**Discriminating evidence:** Examine qdot and action around first entry and
through every hold interruption. Stable zero-action dwell with low qdot would
support passive settling; persistent drift or contact impulses would identify
an additional mechanism.

### Sampled observation-action loop and hold semantics

[Reasoned implication] The causal loop is: simulator state produces the
11-dimensional observation; the policy emits a two-dimensional action; the
action is clipped and held for ten internal integrations; the resulting site
position is compared with the fixed target; and only then is the next
observation and hold-counter update produced. The policy therefore acts with
20 ms observation/action granularity and cannot correct an unobserved
within-interval excursion. [Source:
`robot_learning/scenario/environment.py` (`step`, `_observation`);
`robot_learning/scenario/policy_io.py`; `contracts/task_spec.py`.]

**Decision relevance:** The complete task is a reach-and-stabilize problem,
not merely a point-reaching problem. First reach, maximum uninterrupted hold,
interruption count, and final distance should be interpreted jointly rather
than collapsed into reward or minimum distance.

**Assumptions:** This treats the visible environment's control-boundary
checks as the operative measurement granularity; the human contract's use of
“continuously” may impose a stricter protected evaluation interpretation.

**Source references:** `contracts/scenario.md`;
`robot_learning/scenario/environment.py` (`hold_steps_required`, `step`);
`robot_learning/scenario/evaluation.py`.

**Discriminating evidence:** Compare the protected evaluator's outcome with
high-rate site-distance traces inside each 20 ms interval. A success that
contains an intra-interval excursion beyond 1 cm would show that sampled
hold semantics and physical continuous hold are not equivalent.

### Observability and branch representation

[Reasoned implication] The current observation is sufficient in principle to
reconstruct the fixed target position in the base frame: q determines the
end-effector position, and the observed end-effector-minus-target vector
then determines the target vector. It also exposes qdot and both analytic
branch errors. The target is not physically ambiguous once this full
observation is used, but a policy that uses only part of it would face an
avoidable ambiguity between target direction, arm configuration, and motion
state. [Source: `robot_learning/scenario/observations.py`;
`robot_learning/scenario/environment.py` (`_observation`).]

**Decision relevance:** The policy can condition on target geometry and
velocity without a memory-based target estimator. Missing force/contact
sensing means it cannot directly diagnose an impulse; it must infer such
events from q, qdot, and subsequent position error.

**Assumptions:** This assumes the serialized policy runtime uses the current
observation callable and that its normalization, if any, preserves these
features without invalidating their physical interpretation.

**Source references:** `robot_learning/scenario/observations.py`;
`robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`.

**Discriminating evidence:** Inspect the saved runtime contract for the
candidate and correlate policy outputs with each observation component.
Performance that changes when branch-error features are removed would support
their causal usefulness, not merely their availability.

### Contact-free task geometry and physical failure classes

[Reasoned implication] The target sphere is a visual reference, not an object
to grasp or push, and the plane is non-colliding. Consequently, official
success is governed by planar kinematics and joint dynamics rather than
contact establishment, object compliance, or force regulation. The important
failure classes are target-direction/branch choice, joint-limit or contact
interference, torque-limited transit, overshoot, residual-velocity escape,
and horizon truncation. [Source: `contracts/robots/two_joint_arm.xml`;
`contracts/scenario.md`; `robot_learning/scenario/environment.py`.]

**Decision relevance:** A manipulation or force-control explanation should
not be imported into this task without evidence. Geometry-conditioned
diagnostics can distinguish a reach failure from a hold failure and prevent
optimizing an irrelevant contact behavior.

**Assumptions:** The robot link geoms' default collision behavior does not
introduce a dominant self-contact mode; the XML explicitly disables only the
base, plane, and target contacts.

**Source references:** `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/evaluation.py` (`episode_diagnostics`).

**Discriminating evidence:** Record MuJoCo contact count, contact pairs, and
contact forces alongside distance and q. Contact-free failures support the
reduced kinematic-dynamic model; recurrent link contacts require a contact
mode in the explanation.

### Scientifically meaningful trajectory quantities

[Reasoned implication] The minimum sufficient physical description of a
behavior includes q, qdot, action/nominal torque, end-effector position,
target position, Cartesian error, Jacobian or q2, distance-to-target,
first-reach time, uninterrupted hold run length, hold interruptions, and
whether the episode ended by success or horizon. These quantities separate
geometry, actuation, convergence, and stabilization mechanisms; reward alone
does not. [Source: `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`;
`robot_learning/training/reward.py`.]

**Decision relevance:** These observables support mechanism-level comparison
of candidate policies and expose whether a 98 percent result is limited by
rare target geometries, slow convergence, or unstable holds.

**Assumptions:** The recorded state and action are sampled finely enough to
identify the relevant transients; hidden intra-step contacts or excursions
remain a limitation unless the simulator is instrumented at its 0.002 s
clock.

**Source references:** `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`;
`contracts/scenario.md`.

**Discriminating evidence:** Stratify complete trajectories by target radius,
target angle, IK branch, q2, first-reach time, and hold interruption. Stable
conditional patterns support the proposed failure classes; unexplained
residuals identify a missing physical variable.

## Unknowns

### Compiled mass, inertia, and numerical dynamics

[Unresolved quantity] The XML specifies geom shapes, sizes, joint damping, and
armature but does not specify body masses, inertial tensors, geom density,
the numerical integrator, or solver options. MuJoCo compilation supplies
defaults and derived inertial quantities, but their effective values have
not been established here. The 5-gear command limit therefore does not by
itself determine angular acceleration, settling time, or the reachable
trajectory within 500 control steps. [Source:
`contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`
(`MjModel.from_xml_path`).]

**Decision relevance:** This could change whether the first campaign should
prioritize trajectory timing, conservative braking, or direct feedback, and
whether slow failures are physically unavoidable or policy-induced.

**Assumptions:** The uncertainty matters if compiled inertia is large relative
to the motor authority or if numerical integration at 2 ms changes the
transient materially; it matters less if damping dominates all transients.

**Source references:** `contracts/robots/two_joint_arm.xml` (absence of
explicit inertial tags and `option` fields); `robot_learning/scenario/environment.py`.

**Discriminating evidence:** Inspect the compiled `MjModel` mass, inertia,
armature, actuator force range, timestep/integrator, and solver settings;
then compare measured torque-step acceleration and free-decay trajectories
with the resulting model.

### Self-contact and contact solver behavior

[Unresolved quantity] The upper-arm and forearm capsule geoms retain default
contact settings, and the XML contains no explicit contact exclusions. It is
therefore not established whether folded trajectories produce meaningful
link-link contacts in the compiled model or whether adjacent-body collision
handling prevents them. [Source: `contracts/robots/two_joint_arm.xml`.]

**Decision relevance:** If self-contact occurs near one IK branch, it can
create a qualitatively different failure class and make branch symmetry
false. If it never occurs, contact mechanics can be excluded from early
explanations.

**Assumptions:** The issue is consequential only for trajectories whose
capsules approach within their combined radii; it does not affect the
mathematical point workspace by itself.

**Source references:** `contracts/robots/two_joint_arm.xml` (link geoms,
`contype`/`conaffinity`, and lack of `<contact><exclude>`).

**Discriminating evidence:** At both IK branches and the smallest official
radii, inspect compiled contact pairs and log contact count, normal force,
and contact impulse at the 0.002 s simulation rate.

### Continuous-hold enforcement between control boundaries

[Unresolved quantity] The visible environment advances ten internal MuJoCo
steps and tests distance once afterward. Its hold counter consequently
establishes 100 consecutive sampled control-boundary successes, whereas the
scenario contract describes a complete uninterrupted 2 s hold. It is not
established from the accessible contract and scenario code whether the
protected official evaluator additionally checks all internal integration
states. [Source: `contracts/scenario.md`;
`robot_learning/scenario/environment.py` (`for _ in range(self.frame_skip)`,
distance and hold update).]

**Decision relevance:** A policy can appear stable under boundary sampling
while briefly leaving the 1 cm ball inside an interval. This could change the
meaning of development success and the required robustness margin before
official assessment.

**Assumptions:** The distinction matters when the end-effector crosses the
tolerance boundary within 20 ms and returns before the next check. It is
irrelevant for trajectories with a margin well inside the ball at every
internal step.

**Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
`robot_learning/scenario/environment.py`; protected evaluator semantics are
not exposed in the accessible sources.

**Discriminating evidence:** Run the exact official evaluator or obtain its
documented sampling rule; independently log internal-step distance for
episodes that pass the visible environment. Any internal excursion beyond
1 cm revises the sampled-hold interpretation.

### Effective actuator and policy timing details

[Unresolved quantity] The source establishes clipping, gear, and zero-order
hold, but it does not establish measured actuator force after all MuJoCo
transmission limits, nor policy computation latency outside the synchronous
environment call. The serialized runtime may also include algorithm-specific
normalization and recurrent behavior not inferable from the abstract action
space alone. [Source: `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`;
`contracts/policy_runtime.py`.]

**Decision relevance:** Unexpected saturation, scaling, or recurrence can
masquerade as poor physical control and change whether a policy comparison is
about morphology or runtime I/O.

**Assumptions:** This is consequential if candidates use substantially
different normalization, recurrent state, or action distributions, or if the
compiled actuator force differs from the nominal gear interpretation.

**Source references:** `contracts/policy_runtime.py` (`PolicyRuntime`,
normalizer and recurrent state); `robot_learning/scenario/policy_io.py`;
`contracts/robots/two_joint_arm.xml`.

**Discriminating evidence:** Validate each candidate's frozen runtime and
normalizer, log raw policy output and clipped action, and compare action to
compiled actuator force and joint acceleration in a controlled replay.

### Branch usage and route-dependent feasibility

[Unresolved quantity] Both open and folded inverse-kinematic solutions are
represented in the observation, but no contract requires a policy to use
either branch and no current evidence establishes which branch its trajectory
will select. It is also unknown whether branch switching occurs during
episodes or whether any such switch passes through a high-error or
self-contact region. [Source: `robot_learning/scenario/observations.py`;
`contracts/scenario.md`.]

**Decision relevance:** A strong aggregate success rate could conceal a
branch-specific or radius-specific failure mode. The best initial physical
diagnosis may differ for a policy that consistently uses one safe branch and
one that switches branches.

**Assumptions:** Branch identity is meaningful away from q2 near zero or pi;
near singular configurations, small joint changes can make branch labeling
numerically or behaviorally ambiguous.

**Source references:** `robot_learning/scenario/observations.py`
(`elbow_open`, `elbow_folded`, wrapped errors);
`robot_learning/scenario/evaluation.py` (available geometry diagnostics).

**Discriminating evidence:** Reconstruct the nearest IK branch from q at each
time, then stratify success, first reach, and hold interruptions by branch,
radius, and angle. Repeated branch transitions with associated error spikes
would support route-dependent failure.

## Decision-relevant synthesis

### Compiled dynamics versus policy control

[Reasoned implication] The decisive physical control problem is bounded,
sampled torque control of a two-link arm, not position-command tracking.
Geometry makes every official target reachable in two branches, while the
reset starts at a straight-arm singularity and the 1 cm criterion penalizes
transit overshoot and residual velocity. **Decision relevance:** The first
campaign direction could change between improving feedback/trajectory
control and changing the learning recipe if the compiled dynamics are slow or
strongly saturated. **Assumptions:** The XML model and its defaults are the
operative simulator and self-contact is not dominant. **Source references:**
`contracts/robots/two_joint_arm.xml`; `contracts/scenario.md`;
`robot_learning/scenario/environment.py`; `robot_learning/scenario/observations.py`.
**Discriminating evidence:** Compiled mass/inertia/actuator settings plus
q, qdot, clipped action, target error, and torque-step responses across
radius and angle.

### Hold is a separate capability from reach

[Reasoned implication] A first entry into the 1 cm ball is not success:
distance must remain acceptable for the complete two-second hold. With zero
gravity and no target contact, static holding can be passive, but kinetic
overshoot, damping, numerical/contact effects, or within-step excursions can
reset the hold. **Decision relevance:** Candidate selection and diagnosis
should distinguish slow/non-reaching episodes from reached-but-unstable
episodes before changing the policy or reward. **Assumptions:** The visible
hold update represents the protected task, or any stricter evaluator uses the
same physical state. **Source references:** `contracts/scenario.md`;
`contracts/task_spec.py`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`. **Discriminating evidence:** Complete
per-episode first-reach, maximum uninterrupted hold, interruption count,
qdot/action at first reach, and internal-step distance when available.

### Reachability is not expected to be the geometric bottleneck

[Reasoned implication] The official radial interval is inside the annular
workspace and both elbow configurations fit the stated joint limits across
the full target angle range. **Decision relevance:** If failures cluster by
radius or angle, the leading explanations should be dynamic authority,
singular/route effects, contact, or policy observability/use of features,
not an unreachable target set. **Assumptions:** Forward kinematics and
compiled joint constraints match the explicit XML and contacts do not remove
the relevant branch. **Source references:**
`contracts/scenario.md`; `contracts/robots/two_joint_arm.xml`;
`contracts/robots/two_joint_arm.py`;
`robot_learning/scenario/observations.py`. **Discriminating evidence:**
Analytic and simulated branch-pose checks at the radial and angular
boundaries, followed by failure stratification by target geometry and branch.

### The main unresolved semantic risk is sampled versus continuous hold

[Unresolved quantity] The accessible step implementation checks one distance
after each 20 ms block, but the human task says uninterrupted continuous
hold. **Decision relevance:** This can change the robustness margin required
for a policy and the interpretation of any development result near 98
percent. **Assumptions:** The protected evaluator may add checks not visible
in the scenario environment; conversely, boundary sampling may be the
authoritative operational meaning. **Source references:**
`contracts/scenario.md`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`. **Discriminating evidence:** The
official evaluator's exact hold implementation and high-rate distance traces
through otherwise successful episodes.

### The first physical evidence should preserve mechanism variables

[Reasoned implication] Aggregate success and reward cannot identify whether
the limiting mechanism is reach, convergence, braking, branch selection,
contact, or hold interruption. **Decision relevance:** The first campaign
decision should be based on complete trajectory quantities rather than a
single scalar proxy, because the human objective is 196 successful complete
episodes out of 200. **Assumptions:** The simulator can expose internal
state/action/contact traces without changing the policy or task semantics.
**Source references:** `contracts/scenario.md`;
`robot_learning/scenario/evaluation.py`;
`robot_learning/training/reward.py`;
`robot_learning/scenario/environment.py`. **Discriminating evidence:**
Per-episode q, qdot, action, target geometry, Cartesian error, q2/branch,
first reach, maximum held run, interruption events, contacts, and termination
cause, compared against the 98 percent threshold.
