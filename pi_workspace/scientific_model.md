## Established facts

### Robot morphology and coordinates

[Repository fact] The robot is a fixed-base, planar two-joint serial arm. The
base is fixed at the world origin. A shoulder hinge rotates about the world
`z` axis, the upper arm has length `0.12 m`, and an elbow hinge at its distal
end rotates about the same axis. The forearm has length `0.10 m`; the
end-effector site is at its distal endpoint. The arm plane is `z = 0.02 m`.
The only generalized coordinates and velocities are the shoulder and elbow
hinge coordinates, so the articulated robot has two degrees of freedom.
Sources: `contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`,
`forearm`, `end_effector`); `contracts/robots/two_joint_arm.py`
(`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`).

[Repository fact] The joint ranges in the model are `[-170, 170]` degrees for
both shoulder and elbow. The two links are capsules with radii `0.015 m` and
`0.012 m`; the base is a non-contact cylinder. The end-effector site has a
visual size of `0.008 m`, but the task measures the site position rather than
the visible site radius. Sources: `contracts/robots/two_joint_arm.xml`.

[Repository fact] With shoulder angle `q_s` and relative elbow angle `q_e`,
the end-effector position in the arm plane is, from the body hierarchy,

`p(q) = [0.12 cos(q_s) + 0.10 cos(q_s + q_e),`
`       0.12 sin(q_s) + 0.10 sin(q_s + q_e), 0.02]`.

This is the kinematic map used to reason about the model; the observation
code independently uses the same two link lengths when constructing inverse
kinematic residuals. Sources: `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`.

### Workspace, target distribution, and task geometry

[Repository fact] Ignoring joint limits, the planar two-link workspace is the
annulus from `|0.12 - 0.10| = 0.02 m` to `0.12 + 0.10 = 0.22 m`, with
orientation-dependent coverage once the `±170` degree limits are applied. At
each reset, the official target radius is sampled uniformly from `0.06 m` to
`0.20 m`, independently of an angle sampled uniformly over `[-pi, pi]`.
The target is placed at the current end-effector height, so the three-
dimensional distance reduces to planar distance for a reset arm. Sources:
`contracts/scenario.md`; `contracts/task_spec.py`
(`TARGET_RADIUS_RANGE`); `robot_learning/scenario/environment.py`
(`_sample_target_position`); `contracts/robots/two_joint_arm.py`.

[Repository fact] The target is a mocap body and its sphere has collision
type and affinity zero. The ground plane is also non-contact. Thus the task
does not require grasping, contact, force regulation, or object transport:
success is based on the Euclidean distance between the end-effector site and
the target mocap position. Sources: `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py` (`_distance_to_target`, `step`).

[Repository fact] The tolerance is `0.01 m`. A hold counter increments only
when the post-control-step distance is at most that value; one outside sample
resets the counter to zero. The required duration is `2 s`, represented by
`100` control steps under the current timing. An episode succeeds only when
the counter reaches 100 without interruption, and an episode is truncated
after at most 500 control steps. Sources: `contracts/scenario.md`;
`contracts/task_spec.py`; `robot_learning/scenario/environment.py`
(`hold_steps_required`, `step`).

[Repository fact] The official final panel contains 200 fixed-distribution
episodes and requires at least 196 successes for the stated 98% result.
Development panels are separate from that official result. Source:
`contracts/scenario.md`.

### Simulation, timing, and initial state

[Repository fact] MuJoCo integrates this model with zero gravity and an
internal timestep of `0.002 s`. One policy action is held while ten MuJoCo
steps execute, giving a `0.020 s` control interval and a nominal 50 Hz
policy-to-simulator update rate. The 100-step hold is therefore 2 s and the
500-step horizon is 10 s. Sources: `contracts/robots/two_joint_arm.xml`
(`<option>`); `contracts/task_spec.py` (`FRAME_SKIP`, `HOLD_SECONDS`,
`MAX_EPISODE_STEPS`); `robot_learning/scenario/environment.py`.

[Repository fact] Reset sets both joint positions and velocities to zero,
forwards the model, and then samples a new target. The initial end-effector
position is consequently `(0.22, 0, 0.02)`. If the target has radius `r` and
angle `phi`, the initial planar distance is
`sqrt(0.22^2 + r^2 - 2*0.22*r*cos(phi))`; over the official range it can
vary substantially with target geometry. Sources:
`robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`);
`contracts/robots/two_joint_arm.xml`.

[Repository fact] Each joint has explicit damping `0.5` and armature
`0.01`. The motor actuators have control ranges `[-1, 1]` and gear `5`.
There is no explicit body `<inertial>` element, gravity, or actuator
dynamics element in the XML. Sources: `contracts/robots/two_joint_arm.xml`.

### Actuation and control loop

[Repository fact] The policy action is a two-element floating-point vector
whose declared range is `[-1, 1]`. The current policy I/O applies no
transformation, the environment clips the result to that range, writes it to
`data.ctrl`, and advances the simulator for ten internal steps. The XML
motor actuators are attached directly to the shoulder and elbow joints with
gear 5. Sources: `robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/environment.py` (`step`);
`contracts/robots/two_joint_arm.xml` (`actuator`).

[Repository fact] The environment exposes a scalar reward built from distance
progress, closeness, hold progress, an optional outside-band penalty, a
completion bonus, and action magnitude cost. This reward is not the official
success definition; the environment's `terminated` flag and `is_success`
reflect completion of the uninterrupted hold. Sources:
`robot_learning/training/reward.py`;
`robot_learning/scenario/environment.py`;
`contracts/scenario.md`.

[Repository fact] The observation has 11 `float32` values: two joint
positions, two joint velocities, the three-dimensional end-effector-minus-
target vector, and four wrapped residuals to the open-elbow and folded-elbow
inverse-kinematic solutions. Sources:
`robot_learning/scenario/observations.py` (`OBSERVATION_SIZE`,
`reach_observation`).

### Observability and alternative configurations

[Repository fact] The observation directly exposes joint configuration,
joint velocity, and relative Cartesian error. It does not directly expose
motor torque, acceleration, mass, inertia, damping force, contact force, or
the target's absolute coordinates. Given the known kinematic model, the
target position is reconstructable from the observed joint configuration and
relative error; the target radius and angle are therefore derived rather than
separate sensor channels. Sources: `robot_learning/scenario/observations.py`;
`contracts/robots/two_joint_arm.xml`.

[Repository fact] For an in-workspace target with radius `r`, the elbow
inverse-kinematic equation has the two branches
`q_e = ±acos((r^2 - 0.12^2 - 0.10^2)/(2*0.12*0.10))`, with the corresponding
shoulder angle computed from the target bearing and the forearm offset. The
observation reports residuals to both branches, so it preserves the
branch alternatives rather than forcing one inverse-kinematic choice.
Sources: `robot_learning/scenario/observations.py`;
`contracts/robots/two_joint_arm.py`.

### Training exposure and measurable physical quantities

[Repository fact] The evaluation environment uses the official `0.06--0.20 m`
radius range, while the baseline training environment uses only
`0.14--0.20 m`. This is a learning-exposure difference, not a change to the
official task contract. Sources: `robot_learning/scenario/environment.py`;
`robot_learning/training/environment.py`; `contracts/scenario.md`.

[Repository fact] Quantities already retained by the research evaluator
include target radius and bearing, minimum and final distance, first
in-tolerance step, maximum consecutive held steps, total in-tolerance steps,
hold interruptions, episode steps, and binary success. For physical
interpretation, the corresponding state/action quantities are joint angles,
joint velocities, Cartesian error decomposed into radial and tangential
components, commanded controls, control saturation, and the duration of each
in-tolerance run. Sources: `robot_learning/scenario/evaluation.py`;
`robot_learning/scenario/environment.py`.

## Physical consequences

### Reachability and inverse-kinematic branch choice

[Reasoned implication] The official radial interval lies inside the
unlimited two-link annulus and stays `0.04 m` above the inner radius and
`0.02 m` below the outer radius. The arm therefore has a geometric solution
for every official target radius in the unconstrained planar model; the
joint limits must still be respected for every bearing. There are generally
two distinct elbow configurations for the same target, so a policy can
approach from an elbow-open or elbow-folded posture. **Decision relevance:**
initial policy representations, diagnostics, and any comparison of
configuration-space versus Cartesian control can change depending on whether
branch selection is treated as a source of variation. **Assumptions:** the
declared joint ranges are enforced as MuJoCo hinge limits; the target height
matches the arm plane; no unmodeled collision blocks a branch. **Sources:**
`contracts/robots/two_joint_arm.xml`; `contracts/scenario.md`;
`robot_learning/scenario/observations.py`. **Discriminating evidence:** compute
both IK branches for a dense bearing/radius grid after compiling the model,
record limit violations and Jacobian determinant, and compare observed
failures by branch and target bearing.

[Reasoned implication] The target near `0.20 m` radius requires an arm posture
closer to extension than the target near `0.06 m` radius, while the latter
requires a more folded elbow posture. The same Cartesian tolerance maps to
different joint-space tolerances through the configuration-dependent Jacobian,
so equal position accuracy does not imply equal control difficulty. **Decision
relevance:** target-stratified evaluation and whether to prioritize
workspace-boundary robustness can change. **Assumptions:** the end-effector
site position is the relevant point and the stated link lengths are the
compiled kinematic lengths. **Sources:** `contracts/robots/two_joint_arm.xml`;
`contracts/robots/two_joint_arm.py`; `robot_learning/scenario/evaluation.py`.
**Discriminating evidence:** measure the Jacobian singular values and
Cartesian error/hold success by target radius and bearing.

### Bounded actuation and trajectory control

[Reasoned implication] Each policy command is bounded before simulation and is
held for 20 ms. With MuJoCo motor semantics, the gear maps the bounded
control to joint actuation; the command is therefore not an instantaneous
position setpoint. Motion depends on the current configuration, velocity,
coupled link inertia, damping, and the ten internal integration steps.
**Decision relevance:** a policy that reaches by aggressive saturated motion
may have inadequate authority or braking margin for the subsequent hold;
control-rate and action-saturation diagnostics can change the choice between
trajectory shaping and purely reactive targeting. **Assumptions:** the
compiled default motor gain and actuation semantics are the standard MuJoCo
ones and no hidden policy action transform is present. **Sources:**
`contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/policy_io.py`. **Discriminating evidence:** log
command saturation, joint acceleration, velocity, and realized actuator
forces/torques over approach and hold phases; compare commanded action with
the compiled model's actuator output.

[Reasoned implication] Explicit damping and armature make velocity and
acceleration matter even though gravity is absent. The two joint torques also
produce coupled end-effector motion, so correcting one Cartesian error
component can change both joints and can inject tangential velocity. A
successful controller must coordinate reaching, deceleration, convergence,
and low-error stabilization rather than merely point the end effector toward
the target. **Decision relevance:** a reach-only proxy or a policy selected
only by minimum distance may be misleading for the actual 2 s objective.
**Assumptions:** the compiled dynamics retain the XML damping and armature and
the omitted inertial quantities are finite and configuration dependent.
**Sources:** `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`; `contracts/scenario.md`.
**Discriminating evidence:** align distance, velocity, action, and hold
interruptions in time; a repeated pattern of low minimum distance followed by
boundary crossings supports a stabilization limitation rather than a
reachability limitation.

### Hold semantics and sampled stability

[Reasoned implication] The task requires 100 consecutive post-control-step
distance checks, not a terminal pose alone. Leaving the 1 cm ball at any
checked step erases all accumulated hold progress. The effective success
problem is therefore a hybrid reach-and-stay problem: continuous simulator
dynamics produce the state, while a discrete counter determines termination.
**Decision relevance:** candidate selection must privilege uninterrupted
hold success and interruption statistics over reward or minimum distance.
**Assumptions:** the environment implementation is the authoritative
interaction semantics for the campaign and no hidden within-step check exists.
**Sources:** `contracts/scenario.md`;
`robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.
**Discriminating evidence:** compare maximum consecutive hold, total
in-tolerance time, interruption count, and final distance; inspect sampled
trajectories for excursions between control boundaries where available.

[Reasoned implication] Distance is checked only after the ten internal
MuJoCo steps. An excursion outside the tolerance between checks can remain
unrecorded if the state is back inside at the next check, whereas an
endpoint crossing resets the hold. The official criterion is consequently a
sampled operational hold, not a continuous-time invariant of the entire
internal trajectory. **Decision relevance:** conclusions about physical
stability and the value of faster control updates cannot be transferred
without preserving this timing. **Assumptions:** no separate protected
evaluator adds substep checks; the shown environment is the relevant
interaction implementation. **Sources:** `robot_learning/scenario/environment.py`
(`for _ in range(self.frame_skip)`, distance check); `contracts/task_spec.py`.
**Discriminating evidence:** record distance at every internal MuJoCo step
alongside the official post-step distance and quantify hidden excursions.

[Reasoned implication] No velocity or force threshold appears in success.
A controller may succeed while moving slowly through the tolerance boundary
as long as every sampled position remains inside; conversely, a visually
stationary pose can fail from a small position excursion. Stabilization is
therefore defined by positional occupancy under the simulator timing, not by
mechanical equilibrium. **Decision relevance:** diagnostics and any
interpretation of “stable hold” should report velocity and action as
mechanisms, but must not replace the binary task criterion. **Assumptions:**
the position-only `distance <= success_threshold` test remains unchanged.
**Sources:** `robot_learning/scenario/environment.py`; `contracts/scenario.md`.
**Discriminating evidence:** examine velocity/action distributions during
successful holds and compare them with near-successful interrupted holds.

### Observation-to-action-to-outcome relation

[Reasoned implication] The observation is sufficient to reconstruct the
current two-joint kinematic state and relative target displacement under the
declared model, so a memoryless policy has access to the principal
position/velocity variables needed for deterministic Markov control. The
four IK residuals additionally make both posture alternatives explicit.
However, the observation omits dynamics parameters and realized actuator
torque; the policy must infer their effect from state transitions if they
matter. **Decision relevance:** a failure can be caused by representation,
dynamic adaptation, or actuation authority, and these require different
research directions. **Assumptions:** no hidden actuator state materially
affects future motion and the target remains fixed during an episode.
**Sources:** `robot_learning/scenario/observations.py`;
`robot_learning/scenario/environment.py`; `contracts/robots/two_joint_arm.xml`.
**Discriminating evidence:** test whether repeated identical observed
state/action pairs have consistent next states, and correlate residual,
velocity, and action histories with hold interruptions.

[Reasoned implication] The policy receives a shaped scalar reward during
training, but the official outcome is binary and requires the complete hold.
Distance progress can reward approach without proving convergence, while
hold-progress terms provide a signal only after entering tolerance. The
training objective can therefore select behavior that improves reward while
remaining unreliable at the final hold boundary. **Decision relevance:**
training diagnostics and candidate selection should retain the official
success decomposition rather than use reward as a success proxy. **Assumptions:**
the current reward implementation is used for the candidate under
consideration. **Sources:** `robot_learning/training/reward.py`;
`robot_learning/scenario/evaluation.py`; `contracts/scenario.md`.
**Discriminating evidence:** compare reward totals with binary success,
first-reach time, maximum held steps, and interruption counts across the same
episodes.

### Distribution coverage and failure classes

[Reasoned implication] The baseline training exposure omits official targets
from `0.06 m` to below `0.14 m`, although evaluation includes them. A policy
can therefore appear competent on the exposed outer annulus while lacking
the folded-posture and associated stabilization behavior needed for the full
official distribution. **Decision relevance:** the first campaign comparison
must distinguish a learning-coverage gap from a controller/dynamics gap;
aggregate success alone cannot identify that cause. **Assumptions:** the
baseline training environment is actually used and policy behavior does not
generalize across the omitted radii. **Sources:**
`robot_learning/training/environment.py`;
`robot_learning/scenario/environment.py`; `contracts/scenario.md`.
**Discriminating evidence:** bin development outcomes and reach/hold
diagnostics by radius, especially below `0.14 m`, while keeping the official
panel definition separate.

[Reasoned implication] The main physically distinct failure classes are:
unreachable or limit-infeasible target posture; insufficient or poorly timed
actuation during approach; overshoot or slow convergence; and a hold
interruption caused by residual velocity, damping/inertia interaction,
branch switching, or observation-to-action error. These classes can have the
same final failure label but different signatures in minimum distance,
first-reach step, velocity, saturation, and interruption timing. **Decision
relevance:** mechanism-focused evidence can change whether the next work
targets coverage, policy representation, action timing, or stabilization.
**Assumptions:** the recorded diagnostics are augmented with state/action
traces when causal attribution is needed. **Sources:**
`robot_learning/scenario/evaluation.py`;
`robot_learning/scenario/environment.py`;
`contracts/robots/two_joint_arm.xml`. **Discriminating evidence:** classify
episodes jointly by target geometry, minimum distance, first reach, maximum
held run, velocity, command saturation, and number/timing of interruptions;
retain competing explanations when these measurements do not separate them.

## Unknowns

### Compiled inertial and actuator quantities

[Unresolved quantity] The XML does not state the numerical mass, center of
mass, or inertia tensor of either link, nor the compiled actuator gain,
force range after gear transmission, or whether any default actuator
dynamics/friction contributes. Geom-based MuJoCo compilation may derive
inertial properties, but the resulting `MjModel` values are not present in
the repository contract. **Decision relevance:** these values determine
acceleration, braking distance, control authority, and how much a reach
controller must learn rather than infer. **Assumptions:** omitted MuJoCo
defaults are not treated as scientifically known from the XML alone.
**Sources:** `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`; the compiled MuJoCo model is not
inspected by this pre-campaign model.
**Discriminating evidence:** inspect the compiled model's body masses,
inertias, actuator transmission/gain/force fields and one-step state
transitions under known controls; revise the model with those values.

### Numerical integration and contact/self-collision defaults

[Unresolved quantity] The XML fixes timestep and frame skip but does not
explicitly specify the integrator, solver tolerances, joint friction loss,
contact solver settings, or self-collision exclusions. The plane and target
cannot contact the arm under their declared contact masks, but the exact
effect of any remaining default geometry/contact behavior is not established
by the source text alone. **Decision relevance:** these settings could alter
high-speed overshoot, repeatability, and the interpretation of “stable”
holds, especially if links can contact one another. **Assumptions:** default
MuJoCo settings are active exactly as compiled and no protected wrapper
changes them. **Sources:** `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`; installed MuJoCo compilation is not
inspected by this pre-campaign model. **Discriminating evidence:** read the
compiled option, joint, geom, and contact fields and run controlled
zero-command and saturated-command trajectories with and without potential
self-contact.

### Exact limit feasibility over the official angular distribution

[Unresolved quantity] The two-link geometric workspace calculation does not
by itself prove that both or even one legal `q_s, q_e` branch exists for
every sampled bearing after the `±170` degree limits and any compiled limit
semantics are applied. The interval is plausibly designed to be reachable,
but the exact feasible subset has not been enumerated here. **Decision
relevance:** if a nonzero target subset is limit-infeasible, the 98% objective
would include failures unrelated to policy quality and target-stratified
analysis would be essential. **Assumptions:** joint ranges are the only
kinematic constraints and the target is exactly in the arm plane. **Sources:**
`contracts/scenario.md`; `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`. **Discriminating evidence:** solve
both IK branches over a dense official radius/bearing grid using compiled
joint ranges, then sample the exact reset procedure and count infeasible
targets.

### Within-step behavior and effective stability

[Unresolved quantity] The environment records distance after each 20 ms
control interval, but no repository diagnostic establishes whether trajectories
leave the tolerance ball during the ten internal integration steps. The
actual continuous-time-like path, peak speed, peak acceleration, and
substep overshoot are therefore unknown. **Decision relevance:** this
determines whether endpoint hold statistics adequately describe physical
stabilization and whether a policy exploits the sampled criterion. **Assumptions:**
the internal MuJoCo states are not otherwise captured by the current
evaluator. **Sources:** `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`; `contracts/task_spec.py`.
**Discriminating evidence:** capture substep site positions and velocities
for representative successful and interrupted episodes and compare them with
the official counter.

### Policy-state and normalization realization

[Unresolved quantity] The runtime contract permits a recurrent policy state
and optional observation normalization, but the scientific model does not
identify whether a particular future candidate uses either. A recurrent state
could supply history that compensates for omitted dynamics; normalization can
change the numerical scale seen by the learned controller without changing
the physical observation definition. **Decision relevance:** comparisons
between policies may otherwise attribute a memory or preprocessing effect to
morphology or actuation. **Assumptions:** candidate runtime artifacts are
valid and may differ in algorithm, recurrence, or normalization. **Sources:**
`contracts/policy_runtime.py`; `robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/observations.py`. **Discriminating evidence:** record
the saved runtime I/O, recurrent-state behavior, normalization statistics,
and deterministic actions for matched observations before interpreting
mechanism differences.

### Physical causes of failure before campaign evidence

[Unresolved quantity] No pre-campaign evidence establishes the relative
frequency of reach failure, slow convergence, overshoot, branch switching,
action saturation, or hold interruption, nor whether failures concentrate
by radius or angle. The source definitions constrain the possible causes but
do not rank them. **Decision relevance:** this is the central uncertainty
for choosing the first goal-linked research direction; an intervention aimed
at the wrong class may improve a proxy without improving the official
success rate. **Assumptions:** the evaluator's retained diagnostics are
adequate to separate at least some of these classes. **Sources:**
`robot_learning/scenario/evaluation.py`; `contracts/scenario.md`;
`robot_learning/scenario/environment.py`. **Discriminating evidence:** obtain
completed episode-level state/action diagnostics on the official geometry,
including target-stratified success, first-reach, maximum hold, interruption,
velocity, and saturation measures; retain ambiguity where signatures overlap.

## Decision-relevant synthesis

### Official success is a sampled, uninterrupted position hold

[Reasoned implication] **Decision relevance:** the first campaign decision
should be based on complete success and hold-interruption structure, not on
minimum distance or reward alone. **Assumptions:** the shown environment
implements the official interaction semantics and the 20 ms sampling remains
fixed. **Sources:** `contracts/scenario.md`; `contracts/task_spec.py`;
`robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.
**Discriminating evidence:** maximum consecutive held steps, total
in-tolerance steps, interruption count, final distance, and substep distance
traces for successful and failed episodes.

### Actuation authority and omitted compiled dynamics may control the outcome

[Unresolved quantity] **Decision relevance:** whether failures are principally
learned-control failures or physical authority/timing failures can change the
first research direction; action saturation and braking margin are more
diagnostic than the command value alone. **Assumptions:** the unreported
compiled masses, inertias, motor gains, and solver defaults materially affect
the observed transition dynamics. **Sources:**
`contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/policy_io.py`. **Discriminating evidence:** compiled
model fields plus synchronized command, realized torque, joint velocity,
Cartesian error, and acceleration traces under controlled actions.

### Full-distribution coverage includes an omitted inner-radius regime

[Reasoned implication] **Decision relevance:** the baseline's `0.14--0.20 m`
training range does not cover the official `0.06--0.20 m` range, so the first
performance interpretation must separate target-coverage failure from
general reach-and-hold failure. **Assumptions:** the baseline recipe remains
the exposure being assessed and the omitted inner targets induce different
postures or dynamics. **Sources:** `robot_learning/training/environment.py`;
`robot_learning/scenario/environment.py`; `contracts/scenario.md`.
**Discriminating evidence:** paired target-radius bins, with the same
diagnostics for targets below and above `0.14 m`, while keeping development
panels distinct from the 200-episode official panel.

### Two legal IK branches create a configuration-space alternative

[Reasoned implication] **Decision relevance:** branch-dependent behavior can
change whether policy inputs, initialization, or trajectory selection should
be analyzed in joint space or Cartesian space; it should not be mistaken for
target randomness alone. **Assumptions:** both branches are within the
compiled limits for the relevant target and no collision removes one.
**Sources:** `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`; `contracts/robots/two_joint_arm.py`.
**Discriminating evidence:** compiled-limit IK enumeration and branch-labeled
trajectories, including Jacobian conditioning, peak velocity, action
saturation, and hold interruptions.

### The observation is kinematically rich but dynamically incomplete

[Unresolved quantity] **Decision relevance:** the observation supplies the
state needed for geometric feedback but not direct dynamics or actuator
measurements; if matched state/action transitions are inconsistent, memory or
additional system identification may matter, while consistent transitions
would favor a control/coverage explanation. **Assumptions:** the target is
static and the serialized policy I/O matches the candidate being evaluated.
**Sources:** `robot_learning/scenario/observations.py`;
`contracts/policy_runtime.py`; `robot_learning/scenario/environment.py`.
**Discriminating evidence:** matched-transition repeatability tests, runtime
inspection for recurrence/normalization, and joint/Cartesian state-action
traces aligned to hold interruptions.
