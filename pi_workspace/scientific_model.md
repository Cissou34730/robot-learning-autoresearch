# Scientific model of the two-joint reach-and-hold system

## Established facts

### Robot morphology and coordinates

**Repository fact.** The robot is a fixed-base planar serial arm with two
hinge joints. The shoulder is at the base and the elbow is at the end of the
0.12 m upper arm; the forearm is 0.10 m long and carries the
`end_effector` site at its distal end. Both hinge axes are the world
z-axis, so the kinematic motion is in the x-y plane at z = 0.02 m. The base
has no free joint. The nominal end-effector position at
`q = (0, 0)` is `(0.22, 0, 0.02)` m. [Sources:
`contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`, `forearm`,
`end_effector`); `contracts/robots/two_joint_arm.py`
(`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`, `MAX_REACH`).]

**Repository fact.** The shoulder and elbow ranges are each -170 to +170
degrees. The configured link lengths give an unconstrained planar workspace
annulus with outer radius 0.22 m and inner radius 0.02 m; joint limits and
link geometry determine the actually admissible subset. The arm, base, and
target are not translated by task dynamics: the target is a mocap body and
the base is fixed in the world. [Sources:
`contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`
(`_end_effector_position`, `_sample_target_position`).]

**Repository fact.** The visible base and plane do not collide
(`contype="0"`, `conaffinity="0"`), and the target sphere also does not
collide. The link capsules do not have explicit collision-disable attributes
or explicit contact parameters in the XML. [Source:
`contracts/robots/two_joint_arm.xml`.]

### Actuation, timing, and dynamics definition

**Repository fact.** MuJoCo advances at a 0.002 s simulation timestep. A
policy action is converted by the frozen policy I/O to a two-element physical
command, clipped to [-1, 1] per joint, written to `data.ctrl`, and held for
10 MuJoCo steps. The policy therefore receives one control opportunity every
0.020 s. [Sources:
`contracts/robots/two_joint_arm.xml` (`timestep`, `motor`);
`robot_learning/scenario/policy_io.py` (`physical_action`);
`robot_learning/scenario/environment.py` (`step`, `frame_skip`);
`contracts/task_spec.py` (`FRAME_SKIP`).]

**Repository fact.** Each joint has a MuJoCo motor with `gear="5"` and
`ctrlrange="-1 1"`. Under MuJoCo motor semantics, an unclipped command
produces a generalized motor torque of approximately `tau_i = 5 u_i` N m
within the command range; no separate `forcerange` is specified. Each joint
also has damping 0.5 and armature 0.01 in the XML. Gravity is explicitly
zero. [Source:
`contracts/robots/two_joint_arm.xml`; the torque interpretation is the
native MuJoCo motor contract for the pinned `mujoco>=3.12.0` stack in
`AGENTS.md` and `pyproject.toml`.]

**Repository fact.** Reset first resets MuJoCo data, then sets both joint
positions and velocities to zero, forwards the model, samples a target, and
forwards again. There is no reset randomization of robot pose or velocity.
The target has the current end-effector z coordinate, so target and arm share
the same plane. [Source:
`robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`).]

### Task geometry and outcome

**Repository fact.** Official targets have radius 0.06--0.20 m from the
base and cover the full angle. The environment samples radius and angle
independently and uniformly from those intervals, with a seeded Gymnasium
random generator. The target is stationary during an episode. [Sources:
`contracts/scenario.md`; `contracts/task_spec.py`
(`TARGET_RADIUS_RANGE`); `robot_learning/scenario/environment.py`
(`_sample_target_position`).]

**Repository fact.** The success tolerance is Euclidean distance at most
0.01 m between the end-effector site and the target. The implementation
increments a hold counter only when this condition is true at the end of
each 20 ms control interval and resets it to zero on an outside sample.
With a 2.0 s hold duration this requires 100 consecutive successful control
checks. An episode is truncated at 500 control steps, so it lasts at most
10 s absent earlier success. [Sources:
`contracts/scenario.md`; `contracts/task_spec.py`;
`robot_learning/scenario/environment.py` (`hold_steps_required`, `step`).]

**Repository fact.** The official final assessment uses one frozen policy on
200 fixed-panel episodes from the official distribution. The objective is at
least 196 successes, or 98 percent. Development panels are distinct from
that official panel. [Source: `contracts/scenario.md`.]

### Kinematics and alternative solutions

**Repository fact.** For joint coordinates `q1` (shoulder) and `q2` (elbow),
the end-effector forward kinematics are
`x = 0.12 cos(q1) + 0.10 cos(q1+q2)`,
`y = 0.12 sin(q1) + 0.10 sin(q1+q2)`, and `z = 0.02` m. [Sources:
`contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/observations.py`
(`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`); direct serial-chain kinematics.]

**Repository fact.** The observation code computes
`cos(q2) = (r^2 - 0.12^2 - 0.10^2)/(2*0.12*0.10)` and exposes both
`q2 = +acos(cos(q2))` and `q2 = -acos(cos(q2))`, together with the
corresponding shoulder angles. These are the open/elbow-up and
folded/elbow-down inverse-kinematic branches. [Source:
`robot_learning/scenario/observations.py` (`shoulder_for_elbow`,
`elbow_open`, `elbow_folded`).]

**Reasoned implication.** The official radial interval lies strictly inside
the unconstrained annulus, so exact planar inverse-kinematic solutions exist
for every sampled radius. In particular, the required elbow magnitudes vary
from approximately 49 degrees near 0.20 m to approximately 151 degrees near
0.06 m, both below the 170-degree elbow limit. The two branches are distinct
throughout this interval; shoulder limits must still be checked for each
target angle, and the usable solution can be branch-dependent. [Assumptions:
the XML lengths and joint coordinates are the complete kinematic model and
MuJoCo range limits are active as configured. Sources:
`contracts/robots/two_joint_arm.xml`; `contracts/task_spec.py`;
`robot_learning/scenario/observations.py`. Discriminating evidence: an
analytic or numerical sweep of both IK branches over radius and angle,
including the joint-limit and 1 cm-tolerance boundaries.]

### Sensing and control interface

**Repository fact.** The default observation has 11 float32 entries:
2 joint positions, 2 joint velocities, the 3-vector from target to
end-effector, and four wrapped angular errors to the two inverse-kinematic
solutions (two errors per branch). There is no observation of acceleration,
motor torque, contact force, actuator state, held-step count, or episode step
count. [Sources:
`robot_learning/scenario/observations.py` (`OBSERVATION_SIZE`,
`reach_observation`); `robot_learning/scenario/policy_io.py`.]

**Reasoned implication.** Joint position and velocity are direct simulator
state; end-effector position, target-relative displacement, and IK errors
are derived quantities. Given the known link lengths, q, and the
target-relative vector, the target x-y position is reconstructible even
though absolute target coordinates are not a separate observation field.
The target is static, so target velocity is not needed for this task. The
physical state relevant to deterministic rigid-body evolution is therefore
largely observable, but contact/actuator internals and the task's accumulated
hold history are not. [Assumptions: the default `PolicyIO` is used and no
unmodeled external force or hidden actuator state matters. Sources:
`robot_learning/scenario/observations.py`;
`robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/environment.py`. Discriminating evidence:
reconstruct target coordinates from observations and compare them to the
reset mocap coordinates; compare policies using only the published vector
with policies given additional internal diagnostics.]

**Repository fact.** The environment clips actions after the policy I/O
mapping, not before it, and the default mapping is identity. The controller
therefore chooses two bounded joint commands, not Cartesian position,
velocity, or torque setpoints exposed through a separate low-level loop.
The reward supplies progress, closeness, hold-progress, completion, and
action-cost terms to training, but reward is not the official success
criterion. [Sources:
`robot_learning/scenario/environment.py` (`step`);
`robot_learning/scenario/policy_io.py`;
`robot_learning/training/reward.py`;
`contracts/scenario.md`.]

### Behavior-level quantities that carry physical meaning

**Reasoned implication.** Across a complete episode, the scientifically
meaningful physical quantities are target radius and angle; q, qdot, and
their limits; end-effector position and target distance; branch errors and
branch occupancy; command magnitude and saturation; first-reach time; peak
velocity; settling time; maximum held run; interruptions; and, where
available, substep distance and contact/limit events. Together these
quantities distinguish geometric infeasibility, slow or saturated motion,
overshoot, and loss of a stable hold. Aggregate reward or success alone
cannot identify those mechanisms. [Assumptions: diagnostics are collected
without changing the official interaction semantics. Sources:
`robot_learning/scenario/evaluation.py`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/observations.py`;
`robot_learning/training/reward.py`. Discriminating evidence: synchronized
episode traces containing these quantities and comparisons that hold target
geometry and policy runtime fixed.]

**Decision relevance.** The first campaign measurements should preserve
mechanism-level traces sufficient to locate the dominant failure class before
attributing an outcome to a learning method. [Assumptions: the PI can
measure diagnostics in a research evaluation without changing the frozen
official evaluator. Sources: `contracts/instruments.md`;
`robot_learning/scenario/evaluation.py`. Discriminating evidence: whether
the added trace fields separate failure modes that have identical binary
success outcomes.]

## Physical consequences

### Reachability is a configuration problem followed by a stabilization problem

**Reasoned implication.** Because the target is stationary and the arm starts
from one known pose, a successful episode can be decomposed physically into
(i) selecting an admissible IK branch, (ii) moving through joint space to a
configuration whose end-effector lies inside the 1 cm ball, and (iii)
removing enough joint velocity and correcting residual error to remain in the
ball for 100 checks. Reaching the ball once is insufficient: an overshoot or
oscillation resets the complete hold. [Assumptions: success is evaluated by
the environment's counter and no external disturbances are introduced.
Sources: `contracts/scenario.md`;
`robot_learning/scenario/environment.py`; `robot_learning/scenario/observations.py`.
Discriminating evidence: per-episode first-reach step, minimum and final
distance, maximum held steps, and hold interruptions as recorded by
`robot_learning/scenario/evaluation.py`.]

### The reset pose determines the initial motion demand

**Reasoned implication.** Reset places the end effector at radius 0.22 m on
the positive x-axis with zero velocity, while the target can be anywhere from
0.06 to 0.20 m at any angle. The initial Cartesian distance is therefore
target-dependent, ranging from as little as 0.02 m to as much as 0.28 m.
The arm begins at its maximum-radius, zero-elbow configuration, so inner
targets require contraction and targets at large angular offsets require
substantial shoulder motion before stabilization can begin. [Assumptions:
the site and body transforms in the XML are exactly the reset transforms and
the target is sampled as specified. Sources:
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`).
Discriminating evidence: seeded initial target geometry, initial distance,
first-reach time, peak joint displacement, and peak joint velocity.]

**Decision relevance.** A radius- or angle-dependent first-reach failure
points to trajectory coverage or control authority, whereas a radius- and
angle-independent late failure points more strongly to terminal
stabilization. This distinction changes whether the first campaign work
should alter target exposure, motion planning, or local regulation.
[Assumptions: target geometry and transient diagnostics are retained for the
same episodes. Sources: `contracts/scenario.md`;
`robot_learning/scenario/evaluation.py`. Discriminating evidence: a
two-dimensional failure map over target radius and angle, conditioned on
first-reach and hold interruption.]

### The embodied dynamics couple the two joint commands

**Reasoned implication.** Away from contacts and active limits, the motion
has the rigid-body form
`M(q) qdd + C(q,qdot) qdot + D qdot = tau`,
with `tau` supplied by the two motors, zero gravity, and damping represented
in `D`; armature contributes to the effective generalized inertia. Because
the links form one serial body, `M(q)` and the endpoint Jacobian vary with
configuration, so a command intended to brake one joint can change
end-effector motion through both joints. A Cartesian distance error alone is
not a complete dynamic state; q and qdot are needed to predict convergence.
[Assumptions: no contact or limit impulse is active and MuJoCo's standard
joint-space rigid-body equations apply. Sources:
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`;
`robot_learning/scenario/environment.py`. Discriminating evidence: compare
single-joint and paired-joint step responses at multiple q, and regress
endpoint acceleration on q, qdot, and command.]

**Decision relevance.** If coupling and configuration-dependent inertia are
strong, independent per-joint action heuristics can be unstable or
inefficient and a model-aware or velocity-aware policy becomes more
valuable. If they are weak at the visited postures, simple joint-space
regulation may be adequate. [Assumptions: the candidate's action mapping is
the default two-joint identity mapping and the compiled model is unchanged.
Sources: `robot_learning/scenario/policy_io.py`;
`contracts/robots/two_joint_arm.xml`. Discriminating evidence: cross-joint
response matrices, endpoint settling under matched commands, and action
ablation with qdot retained versus removed.]

**Decision relevance.** If failures are predominantly late hold
interruptions, improving trajectory damping, terminal velocity, or local
feedback is more physically relevant than improving global target search. If
failures are predominantly no-reach episodes, branch selection, workspace
coverage, and gross motion authority matter first. [Assumptions: the
evaluation diagnostics separate first reach from interruption without
confounding target geometry. Sources:
`robot_learning/scenario/evaluation.py`; the success counter in
`robot_learning/scenario/environment.py`. Discriminating evidence: stratified
failure counts by first reach, maximum hold, interruption, radius, and angle.]

### Branch choice changes both geometry and dynamics

**Reasoned implication.** The open and folded IK solutions reach the same
Cartesian target with different joint angles, link orientations, and
velocity mappings. Near the inner target radius the folded geometry can
require a large elbow rotation and can bring the links into a
collision-sensitive posture; near the outer radius the two branches are
closer to an extended configuration and have different Cartesian
conditioning. A controller need not use the branch suggestions as a
setpoint, but it must either select a branch or continuously regulate in a
way that avoids switching-induced motion. [Assumptions: link self-contact
is possible under the unspecified collision defaults and the controller's
trajectory passes through the selected branch neighborhood. Sources:
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`. Discriminating evidence:
joint trajectories, branch-error trajectories, endpoint Jacobian condition
versus target radius, and contact/limit events for both branches.]

**Decision relevance.** A robust solution may benefit from branch-aware
control or from learning a consistent posture convention, but a branch
intervention is not justified as the cause of failure until failures
correlate with branch geometry rather than merely with radius or angle.
[Assumptions: branch identity can be inferred from the four IK-error
entries and the candidate does not already discover an equally stable
alternative. Sources: `robot_learning/scenario/observations.py`;
`robot_learning/scenario/environment.py`. Discriminating evidence:
matched-target comparisons of branch occupancy, convergence time, hold
interruptions, and final distance.]

### Timing, damping, and control authority constrain convergence

**Reasoned implication.** A command remains constant for 20 ms while the
simulator integrates ten 2 ms steps. The 1 cm tolerance is therefore tested
at a relatively coarse control boundary compared with the physics timestep.
With nonzero joint damping and zero gravity, a static interior configuration
with zero velocity and zero motor command is an equilibrium in the absence of
contact; nevertheless, a policy must actively brake the transient motion
created during the approach. Saturation at approximately 5 N m per actuator,
unknown effective inertia, and the 0.5 damping terms jointly set the
fastest safe approach and the amount of overshoot. [Assumptions: native
MuJoCo motor semantics apply and the final posture is not at a joint limit.
Sources: `contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`. Discriminating evidence:
step-response trajectories under bounded commands, peak joint velocity,
settling time, action saturation fraction, and distance excursions after
first entry.]

**Decision relevance.** If control updates are too slow relative to the
arm's natural response, a policy can reach but fail to stabilize; if torque
authority is ample, a simpler setpoint-like policy may suffice. These
possibilities change whether startup work should emphasize dynamic
characterization, action/observation design, or policy optimization.
[Assumptions: inferred masses and solver settings are stable across training
and evaluation. Sources: XML dynamics fields; `FRAME_SKIP` and `step`.
Discriminating evidence: controlled action-response measurements and
sub-control-step traces, not aggregate reward alone.]

### The official distribution is harder than the baseline training exposure

**Repository fact.** The default training environment samples radii only
from 0.14--0.20 m, while research evaluation uses 0.06--0.20 m. The
official angular range is full in both the task contract and evaluation
environment. [Sources:
`robot_learning/training/environment.py`;
`contracts/task_spec.py`;
`robot_learning/scenario/environment.py`.]

**Reasoned implication.** A policy trained only with the default recipe is
not physically tested on the inner 0.06--0.14 m annulus during training.
Those targets demand more folded geometry and generally larger joint
reconfiguration from the initial extended pose. High performance on the
outer training range therefore does not establish 98 percent performance
over the official distribution. [Assumptions: the default training
constructor is used and target radius, rather than only angle, drives the
observed difficulty. Sources: the three files above and
`contracts/scenario.md`. Discriminating evidence: evaluation diagnostics
stratified by radius, with matched policies trained on the same compute.]

### The hold is sampled and history-dependent

**Repository fact.** The environment does not expose the held-step counter
to the policy and only tests distance once after each ten-step integration
block. The counter is reset by any sampled distance above 1 cm, so the
required hold is uninterrupted in the sequence of control checks.
[Source: `robot_learning/scenario/environment.py` (`step`).]

**Reasoned implication.** The policy must infer local stability from q, qdot,
and target error rather than from explicit hold progress. A successful
episode can contain unmeasured distance excursions inside a control block;
the implemented outcome is consequently a discrete-time operationalization
of the contract's continuous hold. This distinction matters most for fast
oscillations near the tolerance boundary. [Assumptions: the shown scenario
environment is the official interaction semantics and no protected evaluator
adds substep checks. Sources:
`contracts/scenario.md`; `robot_learning/scenario/environment.py`.
Discriminating evidence: log end-effector distance at every MuJoCo substep
and compare its maximum excursion with the 100 sampled checks.]

## Unknowns

### Inferred inertial and solver parameters

**Unresolved quantity.** The XML specifies lengths, geometry radii, damping,
armature, timestep, and gravity, but no explicit body mass, center of mass,
full inertia tensor, integrator, solver tolerances, or contact solver
parameters. MuJoCo will compile values from its defaults and geoms, but the
compiled numbers and their numerical consequences are not stated in the
human-owned robot contract. [Sources:
`contracts/robots/two_joint_arm.xml`;
`AGENTS.md` (pinned native MuJoCo version);
`pyproject.toml`.]

**Decision relevance.** These quantities can change acceleration for a given
command, coupled joint response, settling time, and whether a learned
controller transfers between training and official evaluation. They determine
whether action saturation or damping, rather than policy expressivity, is the
limiting resource. **Assumptions:** the compiled model is the only source of
physical parameters and the learning method is sensitive to response
scaling. **Source references:** the XML and `TwoJointArmReachEnv` model
construction. **Discriminating evidence:** a compiled-model parameter
inventory plus repeatable bounded-torque step responses and free-decay
measurements.

### Contact and joint-limit behavior in alternate postures

**Unresolved quantity.** Link collision filtering, the actual occurrence of
self-contact, contact friction, and the exact limit/contact response are not
explicitly characterized by the repository sources. The base, plane, and
target are explicitly noncontacting, but link geoms retain default contact
configuration. **Source references:** `contracts/robots/two_joint_arm.xml`;
the branch construction in `robot_learning/scenario/observations.py`.

**Decision relevance.** If folded solutions create contacts or limit impulses,
they can be dynamically inferior despite being kinematically valid, changing
branch-aware control and the value of inner-radius targets. **Assumptions:**
the policy visits folded configurations and default link contact is active
enough to affect endpoint error. **Discriminating evidence:** contact
counts/forces, joint-limit activations, and matched open/folded trajectories
at the same target coordinates.

### Between-check hold fidelity

**Unresolved quantity.** The maximum continuous distance during each 20 ms
block is not recorded by the environment's outcome or current evaluation
diagnostics. It is therefore unknown whether successful policies remain
inside the 1 cm ball continuously or only at the ten-step sample boundaries.
**Source references:** `contracts/scenario.md`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.

**Decision relevance.** This can change the interpretation of stabilization
failures and whether a controller's apparent 98 percent behavior is robust
to a finer hold check. **Assumptions:** substep excursions are plausible
given the unknown response time and the tolerance boundary is physically
meaningful between observations. **Discriminating evidence:** substep
distance traces during every claimed hold, summarized by maximum distance,
time outside tolerance, and the sampled counter trajectory.

### Official distribution and evaluation implementation boundary

**Unresolved quantity.** The public contracts specify the official
distribution and fixed-panel size, while the protected final evaluator is
not part of the accessible source. The public environment explicitly samples
uniform radius and angle, but any evaluator-level detail not stated in
`contracts/scenario.md` is not independently verifiable here. **Source
references:** `contracts/scenario.md`; `contracts/task_spec.py`;
`robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.

**Decision relevance.** A difference in reset sampling, observation/runtime
semantics, or success checking would invalidate direct extrapolation from
development measurements to the official 196-of-200 threshold. **Assumptions:**
the contract, rather than an unobserved implementation guess, is the
authoritative boundary and the protected evaluator honors it. **Discriminating
evidence:** evaluator-recorded episode seeds, target geometry, frozen
runtime identity, and per-episode success under the official panel; before
that, public seeded reset/evaluation traces can test only the accessible
semantics.

### Policy temporal memory and task-history use

**Unresolved quantity.** The default observation omits held steps and prior
distance, while the runtime contract permits a policy I/O object with an
optional reset and a recurrent model state. The pre-campaign definitions do
not establish whether a candidate will use recurrence or whether memory
materially improves stabilization. **Source references:**
`robot_learning/scenario/observations.py`;
`contracts/policy_runtime.py` (`PolicyIO`, `PolicyRuntime`);
`robot_learning/scenario/environment.py`.

**Decision relevance.** If the Markov physical state is sufficient, recurrence
adds complexity without recovering missing physics; if sampled hold history
or transient phase is consequential, memory may improve action timing.
**Assumptions:** policies are evaluated with the frozen runtime associated
with their weights and use only the declared observation interface.
**Discriminating evidence:** matched feed-forward/recurrent candidates,
runtime action traces, and hold-interruption rates conditioned on qdot and
distance.

## Decision-relevant synthesis

### Stabilization versus reach is the first physical distinction

**Decision relevance.** This determines whether initial work should target
global IK/trajectory coverage or terminal damping and local feedback; the
98 percent objective counts only complete holds. **Assumptions:** episode
diagnostics reliably distinguish first reach from interruption and the
official interaction is the public environment. **Source references:**
`contracts/scenario.md`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`. **Discriminating evidence:**
first-reach step, maximum held steps, interruption count, final distance,
and their radius/angle stratification.

### Inner-radius generalization is a known exposure gap

**Decision relevance.** The default training range omits 0.06--0.14 m,
where folded configurations and larger reconfiguration are likely; this can
make an apparently strong recipe unsuitable for the official distribution.
**Assumptions:** the default training environment is the starting recipe and
radius is a causal difficulty factor. **Source references:**
`robot_learning/training/environment.py`;
`contracts/task_spec.py`; `contracts/scenario.md`.
**Discriminating evidence:** matched development panels partitioned by
target radius and joint-branch occupancy, followed by the official fixed
panel only for the selected frozen policy.

### Dynamic authority and compiled inertia are not yet quantified

**Decision relevance.** The 20 ms action hold, 5 N m nominal saturation,
0.5 damping, and 1 cm tolerance may make braking/settling the bottleneck;
inferred inertia and solver defaults determine whether that is true. This
changes the priority between system characterization and direct policy
optimization. **Assumptions:** native MuJoCo compilation supplies material
parameters not visible in the XML and the policy cannot bypass actuator
saturation. **Source references:**
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/environment.py`; `AGENTS.md`.
**Discriminating evidence:** compiled inertial/solver values and controlled
step, saturation, free-decay, and settling measurements.

### Branch and contact feasibility may change the preferred posture

**Decision relevance.** Both IK branches are geometrically available, but
their joint limits, conditioning, and possible link contacts can create
different convergence and hold reliability. This can change whether a
branch-aware policy is physically warranted. **Assumptions:** the policy
visits both branches or the inner-radius task requires folded postures, and
default link contact affects motion. **Source references:**
`contracts/robots/two_joint_arm.xml`;
`robot_learning/scenario/observations.py`. **Discriminating evidence:**
an IK limit sweep plus matched-target joint, endpoint-error, contact, and
hold traces for open and folded solutions.

### Sampled hold semantics need explicit robustness interpretation

**Decision relevance.** A policy can pass the implemented 100-check criterion
while making an unmeasured substep excursion; this determines whether
development success is evidence of physical continuous holding or only of
the official discrete interaction. **Assumptions:** no hidden evaluator
substep check exists beyond the public contract and 20 ms sampling.
**Source references:** `contracts/scenario.md`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.
**Discriminating evidence:** substep end-effector distance traces aligned
with every hold check, with maximum excursion and time-outside summaries.
