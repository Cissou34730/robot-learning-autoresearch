## Established facts

### Robot morphology and kinematics

**[Repository fact]** The robot is a planar serial arm with two revolute degrees of
freedom. The shoulder and elbow axes are both the world z axis; the upper arm
length is 0.12 m and the forearm length is 0.10 m. The shoulder joint is located
at z = 0.02 m, so the end effector moves in the horizontal plane z = 0.02 m.
The joints are limited to [-170, 170] degrees. Sources:
`contracts/robots/two_joint_arm.xml:9-21` and
`contracts/robots/two_joint_arm.py:5-7`.

**[Repository fact]** With joint coordinates q = (q1, q2), the planar
end-effector position relative to the base is

`x = 0.12 cos(q1) + 0.10 cos(q1 + q2)`,
`y = 0.12 sin(q1) + 0.10 sin(q1 + q2)`.

The nominal radial workspace is therefore 0.02-0.22 m, with the stated joint
limits further restricting its boundary. Source: the link hierarchy and joint
poses in `contracts/robots/two_joint_arm.xml:12-21`.

**[Repository fact]** Reset sets q = (0, 0) and qdot = (0, 0), then performs
forward kinematics. The arm initially lies straight along +x, with its
end-effector at approximately (0.22, 0, 0.02). Source:
`robot_learning/scenario/environment.py:102-120`.

### Actuation and simulation timing

**[Repository fact]** The action is a two-vector in [-1, 1], passed through
unchanged by the policy I/O and clipped again by the environment. Its elements
are assigned to the shoulder and elbow motor controls. Each MuJoCo motor has
gear 5 and control range [-1, 1]. Source:
`robot_learning/scenario/policy_io.py:11-16`,
`robot_learning/scenario/environment.py:122-132`, and
`contracts/robots/two_joint_arm.xml:30-33`.

**[Repository fact]** The XML sets gravity to zero and the integrator timestep to
0.002 s. The environment advances ten physics steps per policy action, giving a
0.020 s control interval (50 Hz). The two-second hold consequently requires 100
post-action observations, and an episode can last at most 500 control steps.
Sources: `contracts/robots/two_joint_arm.xml:2`,
`contracts/task_spec.py:7-11`, and
`robot_learning/scenario/environment.py:52-58,130-159`.

**[Repository fact]** Each motor is a direct MuJoCo motor: there is no explicit
actuator state, transmission delay, or actuator dynamics in the robot XML.
Under the native MuJoCo motor semantics, the control produces a generalized
joint force proportional to gear times control, subject to the control range;
the nominal command authority is therefore +/-5 in the simulator's torque units
per joint. Sources: `contracts/robots/two_joint_arm.xml:30-33` and
`robot_learning/scenario/environment.py:125-132`.

**[Repository fact]** Joint damping is 0.5 and armature is 0.01 for each joint.
No mass or inertia is written explicitly in the XML. The floor, base, and target
geoms explicitly have collision disabled; the arm capsules retain their default
collision attributes, so no external obstacle or target contact is defined, while
the exact self-contact behavior is a simulator-default question. Sources:
`contracts/robots/two_joint_arm.xml:5-6,10-19,25-27`.

### Task geometry and outcome

**[Repository fact]** At reset, a target is sampled with radius uniformly in
[0.06, 0.20] m and angle uniformly over [-pi, pi]. Its z coordinate is copied
from the end effector, so the target and arm share a plane. Success is based on
the three-dimensional point distance between the end-effector site and the
target mocap position, with tolerance 0.01 m. Sources:
`contracts/scenario.md:7-14`,
`contracts/task_spec.py:6-11`, and
`robot_learning/scenario/environment.py:83-97,134-159`.

**[Repository fact]** The hold counter increments only on consecutive control
steps at or inside the tolerance. One outside step resets it to zero; success
terminates the episode only after 100 consecutive in-tolerance steps. A frozen
policy is finally judged on 200 fixed episodes, and at least 196 must succeed for
the 98% objective. Sources: `robot_learning/scenario/environment.py:136-168`
and `contracts/scenario.md:17-32`.

**[Repository fact]** The baseline training environment samples only radii
[0.14, 0.20] m, while the fixed evaluation environment uses [0.06, 0.20] m.
This is a learning-distribution choice, not a change to the official task.
Source: `robot_learning/training/environment.py:3-19` and
`robot_learning/scenario/environment.py:171-178`.

### Sensing and policy interface

**[Repository fact]** The observation has 11 values: q (2), qdot (2), the
three-dimensional end-effector-to-target vector (3), and four wrapped joint
errors to the two analytic inverse-kinematic branches (open and folded). The
inverse-kinematic elbow angle is computed from the law of cosines and clipped
before arccos. Source: `robot_learning/scenario/observations.py:11-49`.

**[Repository fact]** There is no defined sensor noise, quantization, or
observation delay. The policy receives an observation, emits one action, and
that action is held for ten physics steps before the next observation and task
distance check. Source:
`robot_learning/scenario/environment.py:122-168` and
`robot_learning/scenario/observations.py:14-49`.

**[Repository fact]** The training scalar reward combines distance progress,
closeness, hold-progress, a small action cost, an outside-band penalty after a
hold attempt, and a completion bonus. These terms shape learning but do not
alter the binary uninterrupted-hold success definition. Source:
`robot_learning/training/reward.py:16-25,47-107` and
`contracts/scenario.md:17-20`.

## Physical consequences

### Reachability and branch structure

**[Reasoned implication]** For a target at polar coordinates (r, phi), inverse
kinematics gives

`cos(q2) = (r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10)`,

with the two nominal solutions q2 = +/- arccos(cos(q2)) and
`q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2))`. The official annulus is
inside the nominal workspace, and its endpoints imply approximately
|q2| <= 150 degrees and |q1| <= 158 degrees after angle wrapping, so both
elbow branches are nominally compatible with the +/-170 degree limits.

**Decision relevance:** A policy can solve the task by selecting either branch;
branch diversity is a capability, not an inherent infeasibility. A first
learning design can therefore exploit analytic branch information rather than
searching for a unique posture.

**Assumptions:** The conclusion uses the XML link lengths, exact planar
kinematics, the stated joint limits, and no unmodeled tool offset or collision.
It treats the 1 cm tolerance as sufficient to absorb numerical boundary
effects.

**Source references:** `contracts/robots/two_joint_arm.xml:12-21`,
`contracts/robots/two_joint_arm.py:5-7`, and
`robot_learning/scenario/observations.py:18-35`.

**Discriminating evidence:** Compute both IK solutions over a dense grid of
official radii and angles, then compare forward-kinematic residuals and limit
margins. A failure near a boundary would revise the claim from fully branch
feasible to only practically feasible.

### Singular initial posture and motion generation

**[Reasoned implication]** At q2 = 0 the arm is fully extended and the planar
position Jacobian loses rank: small joint changes initially produce motion
primarily along one Cartesian direction, while lateral target error requires
bending the elbow first. The zero-gravity reset removes a passive gravitational
torque, so this departure must be generated by motor torque and then shaped by
damping and inertia.

**Decision relevance:** Targets near the initial +x ray can begin close in
distance but still require a substantial posture change; targets away from that
ray test transient steering from a kinematic singularity. Early performance
should not be interpreted from distance alone.

**Assumptions:** The model uses the exact serial-link Jacobian and treats the
initial state as deterministic. The inferred inertial parameters do not change
the kinematic rank, only the speed and effort needed to leave it.

**Source references:** `robot_learning/scenario/environment.py:109-118`,
`contracts/robots/two_joint_arm.xml:2,12-20`, and the link geometry in
`contracts/robots/two_joint_arm.xml:15-20`.

**Discriminating evidence:** Measure early Cartesian displacement and q2
growth for targets at several angles from reset, with fixed actions or a fixed
controller. A strong direction-dependent delay would support singular-start
dominance; similar transients would shift attention to actuator/dynamic
parameters.

### Dynamic authority, convergence, and stabilization

**[Reasoned implication]** A control value is a piecewise-constant torque command
over 20 ms, not a desired joint position. The arm must therefore accelerate,
brake, and settle within a sampled-data loop. Damping suppresses velocity but
does not guarantee monotonic convergence; coupled two-link inertia means a
shoulder or elbow command can move both Cartesian coordinates. Saturation and
the 1 cm ball make overshoot especially consequential during the hold.

**Decision relevance:** Reaching the target and maintaining it are distinct
control problems. A policy that maximizes rapid approach can fail the official
task through oscillation, and a policy that settles slowly can run out of the
500-step horizon.

**Assumptions:** Native MuJoCo motor semantics apply, the effective torque
authority is not reduced by an omitted actuator force limit, and the inferred
body inertias are physically plausible.

**Source references:** `contracts/robots/two_joint_arm.xml:2,13-18,30-33`,
`robot_learning/scenario/environment.py:125-159`, and
`contracts/scenario.md:9-14`.

**Discriminating evidence:** Record q, qdot, action, distance, first-entry step,
and all hold interruptions under fixed target panels. Fast first entry followed
by repeated exits supports stabilization/overshoot as the limiting mechanism;
slow entry without exits supports authority or horizon limitation.

### Hold semantics as a hybrid failure mode

**[Reasoned implication]** The task is a hybrid reach-and-stay system: continuous
MuJoCo motion is coupled to a discrete counter. One sample outside the tolerance
destroys all accumulated hold progress, even if the end effector remains close
and immediately returns inside. The 100-step requirement is 2 s of continuous
control-time occupancy, not 100 total in-tolerance samples.

**Decision relevance:** Episode success is controlled by the worst excursion
during the hold, not only minimum distance or final distance. Training and
measurement must separate first reach, in-tolerance occupancy, and interruption
rate.

**Assumptions:** The post-action distance check is the authoritative sampled
criterion and no unrecorded continuous-time crossing is used.

**Source references:** `robot_learning/scenario/environment.py:134-168` and
`robot_learning/scenario/evaluation.py:51-75`.

**Discriminating evidence:** Compare first-reach step, maximum held steps,
in-tolerance steps, and hold interruptions on identical targets. If successful
episodes have similar reach times but failures have interruptions, the hold
counter rather than reachability is the active bottleneck.

### Observation, action, and outcome coupling

**[Reasoned implication]** The observation is close to a Markov state for this
deterministic model: q and qdot expose mechanical state, and the relative
position exposes target error. Given the known kinematics, q plus the relative
vector also identifies the target position in the arm plane. The four branch
errors expose both posture choices, but they do not impose a branch; the policy
must choose and maintain one or transition between them.

**Decision relevance:** A memoryless policy has enough nominal information to
condition torque on target geometry and velocity. Failures should first be
attributed to control/dynamics or representation discontinuities, not to missing
target location, unless evidence shows that the exported runtime changes the
observation.

**Assumptions:** The policy receives the exact 11-value observation, the model
kinematics are known to the policy code, and qpos is interpreted consistently
across angle wrapping.

**Source references:** `robot_learning/scenario/observations.py:14-49`,
`robot_learning/scenario/policy_io.py:7-16`, and
`contracts/policy_runtime.py:153-177`.

**Discriminating evidence:** Reconstruct target coordinates from observed q and
relative position and compare them with the sampled mocap target; then test
whether exported-runtime observations match training observations. Systematic
reconstruction or serialization discrepancies would identify observability
rather than control as the cause.

### Training distribution and reward mismatch

**[Reasoned implication]** Baseline training omits the inner 6-14 cm of the
official radius distribution. Inner targets require the more folded
configurations and can have different branch margins and local dynamics.
Distance-progress and hold-progress shaping can teach approach and occupancy,
but reward is not an unbiased proxy for the all-or-nothing official objective.

**Decision relevance:** A high training reward or outer-annulus success rate does
not establish 98% official success. Generalization to inner radii and robustness
to the full angular distribution are first-order campaign concerns.

**Assumptions:** The baseline training constructor is used and no later
research change broadens its target distribution or changes the reward.

**Source references:** `robot_learning/training/environment.py:14-19`,
`robot_learning/training/reward.py:47-107`, and
`contracts/scenario.md:7-20`.

**Discriminating evidence:** Stratify evaluation by radius and angle, retaining
the same seeds across candidates. A sharp inner-radius drop supports coverage
as the explanation; uniform failures across radii point instead to dynamics,
representation, or stabilization.

## Unknowns

### Compiled mass, inertia, and simulator defaults

**[Unresolved quantity]** The XML specifies geometry, damping, armature,
timestep, and gravity, but not body mass, inertia, density, integrator, solver
settings, or actuator force parameters beyond control range and gear. MuJoCo
compilation supplies defaults and inferred inertias, but their exact compiled
values are not established by the source text alone.

**Decision relevance:** These quantities determine acceleration, braking distance,
coupled motion, and whether nominal +/-5 torque is ample or marginal. They can
change whether the first campaign should emphasize policy structure,
stabilization, or system characterization.

**Assumptions:** The runtime uses exactly the native MuJoCo version and XML
without external defaults or post-compilation edits.

**Source references:** `contracts/robots/two_joint_arm.xml:1-33`,
`robot_learning/scenario/environment.py:16-20,52-58`, and the runtime versions
specified in `AGENTS.md`.

**Discriminating evidence:** Inspect the compiled `MjModel` fields for masses,
inertias, actuator gain/force ranges, integrator, and solver options, then
compare predicted and measured short torque-response trajectories.

### Arm self-contact behavior

**[Unresolved quantity]** The base, floor, and target are non-colliding, but the
upper-arm and forearm capsules do not explicitly set contact masks. Whether
MuJoCo's compiled body-pair exclusions prevent self-contact, and whether any
remaining contacts occur in official postures, is not established from the XML
alone.

**Decision relevance:** If self-contact is possible, it can create a discrete
force or sticking failure mode near folded solutions and make branch choice
matter for reasons unrelated to actuator authority. If it is absent, contact
need not be part of the initial physical explanation.

**Assumptions:** Native MuJoCo collision filtering is used without runtime
exclusions or additional contact parameters.

**Source references:** `contracts/robots/two_joint_arm.xml:5-6,10-27` and
`robot_learning/scenario/environment.py:52-53`.

**Discriminating evidence:** Inspect compiled geom contact masks and generated
contact pairs, then sweep both IK branches over the official annulus while
recording contact counts and contact forces.

### Effective dynamic response and numerical stability

**[Unresolved quantity]** The source establishes a 2 ms physics step and ten-step
action hold, but does not establish the resulting closed-loop settling time,
overshoot, numerical energy behavior, or sensitivity to target direction.

**Decision relevance:** If ten substeps are dynamically well resolved, policy
design can focus on sampled control. If response is stiff or poorly resolved,
the apparent policy difficulty may be a simulation-timing artifact and the
control interval becomes a critical research variable that cannot be changed for
official assessment.

**Assumptions:** The simulator's default numerical settings remain fixed and
the direct motor command is held constant through all ten substeps.

**Source references:** `contracts/robots/two_joint_arm.xml:2`,
`contracts/task_spec.py:8`, and
`robot_learning/scenario/environment.py:125-132`.

**Discriminating evidence:** Apply reproducible step, pulse, and braking
commands from several postures; measure q/qdot response, overshoot, and
repeatability at 2 ms and 20 ms reporting intervals.

### Practical branch preference and branch switching

**[Unresolved quantity]** Both analytic IK branches are nominally available, but
it is not known whether one branch has materially better torque margin,
settling behavior, representation continuity, or robustness across the full
annulus. It is also unknown whether a learned policy will switch branches near
angle wrapping or during correction.

**Decision relevance:** A stable single-branch strategy may be easier to learn
than branch switching; conversely, a branch-specific weakness could make
diversity necessary for the 98% target.

**Assumptions:** Branch errors are consumed as represented, and no policy
architecture or action postprocessor enforces branch selection.

**Source references:** `robot_learning/scenario/observations.py:18-47`,
`robot_learning/scenario/policy_io.py:11-16`, and
`contracts/robots/two_joint_arm.xml:13-18`.

**Discriminating evidence:** Evaluate matched open- and folded-branch
controllers on the same target panel and log q2 sign, branch transitions,
distance, and hold interruptions. A reproducible branch-dependent success gap
would establish a meaningful branch choice.

### Target-dependent time and effort margin

**[Unresolved quantity]** The maximum initial distance is set by the reset
geometry and target sample, but the time and torque margin required to enter and
hold the 1 cm ball are not known. The 500-step horizon may bind only for a
subset of angles or radii.

**Decision relevance:** Horizon-bound failures call for faster convergence;
hold-interruption failures call for damping or stabilization; neither can be
distinguished from episode success alone.

**Assumptions:** The action bounds and dynamics remain fixed and the target is
stationary throughout the episode.

**Source references:** `robot_learning/scenario/environment.py:83-118,157-168`,
`contracts/task_spec.py:6-11`, and
`contracts/scenario.md:24-32`.

**Discriminating evidence:** Bin episodes by target radius and angle and compare
first reach, final distance, maximum held steps, interruptions, and truncation.
Evidence concentrated at 500 steps supports a horizon bottleneck; early entry
with later exits supports stabilization.

### Observation sufficiency under exported execution

**[Unresolved quantity]** The source representation is physically rich, but it is
not yet established that normalization, recurrent-state reset, and serialized
policy I/O preserve the same numerical observation and action semantics used
during training.

**Decision relevance:** A mismatch would make learning changes irrelevant to
official performance and could masquerade as distribution shift or poor control.

**Assumptions:** The saved runtime is the artifact used for evaluation and its
normalization statistics are part of the intended policy.

**Source references:** `contracts/policy_runtime.py:61-87,153-181`,
`robot_learning/scenario/policy_io.py:1-16`, and
`robot_learning/scenario/evaluation.py:37-60`.

**Discriminating evidence:** Compare training-environment and exported-runtime
observations/actions on identical reset seeds and fixed model states, including
episode reset behavior. Any numerical mismatch revises the model from
control-limited to interface-limited.

## Decision-relevant synthesis

### Official success is a stabilization problem as well as a reaching problem

**[Reasoned implication]** The discrete criterion requires 100 consecutive
20-ms samples inside a 1-cm ball; one excursion resets the complete hold.

**Decision relevance:** First campaign decisions should distinguish approach
failure from post-entry oscillation rather than using reward or final distance
as the primary explanation.

**Assumptions:** The sampled post-action distance and hold counter are
authoritative.

**Source references:** `contracts/scenario.md:9-20` and
`robot_learning/scenario/environment.py:134-168`.

**Discriminating evidence:** Episode-level first-reach, maximum-held, interruption,
and truncation measurements on a fixed target panel.

### The arm starts at a kinematic singularity with direct, saturated torque control

**[Reasoned implication]** q = (0, 0) is fully extended; the policy does not
command positions but holds +/-5-nominal-torque motor commands for 20 ms.

**Decision relevance:** Early steering and braking behavior can dominate
performance even when the target is geometrically reachable; dynamic response
should be separated from kinematic coverage.

**Assumptions:** Native MuJoCo motor semantics and compiled inertial defaults are
as specified by the runtime.

**Source references:** `robot_learning/scenario/environment.py:102-132`,
`contracts/robots/two_joint_arm.xml:2,12-18,30-33`.

**Discriminating evidence:** Fixed-action pulse/braking characterization from
reset and representative postures, including q2 growth and Cartesian
overshoot.

### Both IK branches are available, but the practical branch policy is unknown

**[Reasoned implication]** The full official annulus is nominally reachable by
open and folded elbow solutions within the joint limits, while the observation
exposes both branch errors without selecting one.

**Decision relevance:** The first policy direction may depend on whether a
single branch is robust enough or whether branch-aware behavior is needed.

**Assumptions:** The analytic IK and joint-limit calculations remain valid for
the compiled model and no hidden collisions exist.

**Source references:** `robot_learning/scenario/observations.py:18-49`,
`contracts/robots/two_joint_arm.xml:13-21`.

**Discriminating evidence:** Matched branch-conditioned trials across the
official radius-angle panel, with branch transitions and hold interruptions.

### The baseline learning distribution does not cover the official inner radii

**[Reasoned implication]** Training on 14-20 cm leaves 6-14 cm targets to
generalization, although the official distribution samples the whole 6-20 cm
range.

**Decision relevance:** Outer-radius training success cannot justify an official
98% claim; radius-stratified behavior is needed before choosing whether the
initial campaign focus is coverage or control.

**Assumptions:** The baseline training environment remains the active recipe and
the official task distribution is unchanged.

**Source references:** `robot_learning/training/environment.py:14-19`,
`contracts/task_spec.py:6`, and `contracts/scenario.md:7-20`.

**Discriminating evidence:** Paired, fixed-seed success and diagnostic metrics
stratified by radius and angle, with inner-radius failures compared to
outer-radius failures.

### Compiled dynamics and interface fidelity are the highest-value unknowns

**[Unresolved quantity]** Exact inferred inertias, numerical defaults, effective
settling response, and exported observation/action fidelity are not established
by the contracts alone.

**Decision relevance:** These unknowns determine whether the first scientific
direction should target controller stabilization, task-coverage/generalization,
or policy-runtime correctness; they can invalidate interpretations of learning
results if left conflated.

**Assumptions:** No hidden benchmark-specific physics differs from the
human-owned XML and native MuJoCo construction path.

**Source references:** `contracts/robots/two_joint_arm.xml:1-33`,
`robot_learning/scenario/environment.py:16-20,52-58`, and
`contracts/policy_runtime.py:61-181`.

**Discriminating evidence:** Compiled-model inspection, open-loop response
measurements, and identical-state train-versus-export runtime comparisons.
