## Established facts

### Robot morphology and kinematics

**Repository fact.** The robot is a planar serial chain with two hinge joints,
shoulder `q1` and elbow `q2`, both rotating about the world z axis. The upper
arm length is 0.12 m and the forearm length from elbow to the end-effector site
is 0.10 m. The arm plane is z = 0.02 m. Sources:
`contracts/robots/two_joint_arm.xml:9-22`;
`contracts/robots/two_joint_arm.py:5-7`.

**Repository fact.** With the base at the origin, the end-effector position is

`x = 0.12 cos(q1) + 0.10 cos(q1 + q2)`,
`y = 0.12 sin(q1) + 0.10 sin(q1 + q2)`,
`z = 0.02`.

This follows from the body offsets and site position in
`contracts/robots/two_joint_arm.xml:12-20`.

**Repository fact.** The XML declares both joint ranges as -170 to +170
degrees. No other joint or Cartesian constraint is declared. The plane and
target geoms have collision disabled, so task behavior does not include contact
with either of them; the arm capsules do not explicitly disable collision, so
self-collision behavior is not established here. Source:
`contracts/robots/two_joint_arm.xml:6-19,25-27`.

**Repository fact.** The ideal unconstrained two-link workspace is the annulus
from `|0.12 - 0.10| = 0.02 m` to `0.12 + 0.10 = 0.22 m`. The official target
radii are 0.06-0.20 m, and targets are placed in the same z plane as the
end-effector. Sources: `contracts/scenario.md:7-13`;
`contracts/task_spec.py:6-11`; `robot_learning/scenario/environment.py:83-97`.

### Initialization and task geometry

**Repository fact.** Every reset sets `q1 = q2 = 0` and both joint velocities to
zero, forwards the model, then samples an angle uniformly over `[-pi, pi]` and
a radius uniformly over `[0.06, 0.20]`. The target is a mocap body at that
radius and angle with z equal to the end-effector z. Source:
`robot_learning/scenario/environment.py:83-120`.

**Repository fact.** The reset arm is fully extended along +x, at radius
0.22 m. Consequently, the initial target-center distance ranges from 0.02 m
to 0.42 m over the official distribution. This is a direct consequence of
the reset state, link lengths, and target radius range. Sources:
`robot_learning/scenario/environment.py:102-120`;
`contracts/robots/two_joint_arm.xml:12-20`;
`contracts/task_spec.py:6`.

**Repository fact.** The visible target is a 0.012 m-radius sphere, but success
uses distance from the end-effector site to the target center; the target geom
cannot collide because its contact type and affinity are zero. The target is
therefore a geometric reference, not a physical object to grasp or contact.
Sources:
`contracts/robots/two_joint_arm.xml:25-27`;
`robot_learning/scenario/environment.py:75-80,134-168`.

**Repository fact.** Official success requires distance at most 0.01 m for
100 consecutive control steps, which is 2 seconds at the official timing.
Leaving the tolerance resets the held-step count to zero. An episode has at
most 500 control steps, and the official assessment uses 200 episodes with at
least 196 successes required. Sources: `contracts/scenario.md:7-31`;
`contracts/task_spec.py:7-11`;
`robot_learning/scenario/environment.py:55-58,136-168`.

### Actuation, simulation, and timing

**Repository fact.** The action is a two-element vector in `[-1, 1]`; the
scenario action mapping is identity and the environment clips the received
action before writing it to `data.ctrl`. Each motor has gear 5, so the
commanded generalized torque is nominally `tau_i = 5 u_i` in the joint
coordinate, subject to the action and actuator limits. Sources:
`robot_learning/scenario/environment.py:122-133`;
`robot_learning/scenario/policy_io.py:11-16`;
`contracts/robots/two_joint_arm.xml:30-33`.

**Repository fact.** MuJoCo advances ten internal steps per policy action.
The XML timestep is 0.002 s, giving a 0.020 s zero-order-held control period.
Gravity is explicitly zero. Each joint declares damping 0.5 and armature
0.01. Sources: `contracts/robots/two_joint_arm.xml:2,13-18`;
`contracts/task_spec.py:8`;
`robot_learning/scenario/environment.py:56-58,125-132`.

**Repository fact.** The control loop observes the current state, predicts one
action, holds that action through ten `mj_step` calls, measures the resulting
distance, updates hold state, and returns the next observation. Source:
`robot_learning/scenario/environment.py:99-168`.

### Sensing and observation

**Repository fact.** The policy observation has 11 float32 values: two joint
positions, two joint velocities, the three-dimensional vector from target to
end-effector, and four wrapped angular errors to the two analytic inverse
kinematic branches (open and folded elbow). Source:
`robot_learning/scenario/observations.py:11-49`.

**Repository fact.** The target is stationary and its x and y coordinates are
used to compute the two inverse-kinematic branches. The observation does not
expose forces, torques, actuator state, contact state, images, or compiled
mass/inertia. Source: `robot_learning/scenario/observations.py:18-47`;
`contracts/robots/two_joint_arm.xml:25-33`.

**Repository fact.** Given the known link geometry, `q1` and `q2` determine
end-effector position. Therefore the observed end-effector-minus-target vector
together with joint positions is sufficient to reconstruct the target
Cartesian position in the fixed task plane. The wrapped branch errors are
redundant geometric guidance rather than independent physical sensors. Source:
`robot_learning/scenario/observations.py:27-47`;
`contracts/robots/two_joint_arm.py:5-7`.

### Training and assessment boundary

**Repository fact.** The baseline training environment samples radii only from
0.14 to 0.20 m, while the fixed evaluation environment uses 0.06 to 0.20 m.
Training mechanics are shared with evaluation, but the training target
distribution is separately defined and can be changed by research code.
Sources: `robot_learning/training/environment.py:3-19`;
`robot_learning/scenario/environment.py:171-178`;
`contracts/scenario.md:34-38`.

**Repository fact.** The current reward combines distance progress, exponential
closeness, linear hold-progress credit, a small action cost, a small penalty
after leaving the hold band, and a completion bonus. The reward is a training
signal and is not the official success definition. Sources:
`robot_learning/training/reward.py:16-25,47-107`;
`robot_learning/scenario/environment.py:145-168`;
`contracts/scenario.md:18-31`.

## Physical consequences

### Reachability and inverse-kinematic multiplicity

**Reasoned implication.** The official target set lies inside the two-link
workspace and away from the ideal inner and outer boundaries. For a target
with polar angle `phi` and radius `r`, the two geometric solutions are

`q2 = +/- acos((r^2 - 0.12^2 - 0.10^2)/(2*0.12*0.10))`,

with `q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2))`.
For the official radii, both elbow signs are real and the resulting shoulder
angles remain within the declared +/-170 degree range. Thus the task has two
ordinary kinematic branches, not one uniquely correct posture. Assumptions:
the declared joint ranges are active and the standard planar forward-kinematic
interpretation applies. Sources: `contracts/robots/two_joint_arm.xml:13-20`;
`robot_learning/scenario/observations.py:18-35`.

**Reasoned implication; decision relevance.** Early policy design or diagnosis
can change depending
on whether a controller is expected to select one branch, use both, or cross
between them. Evidence that separates these cases is branch-conditioned
success, joint trajectories, and the four branch-error channels over complete
episodes. The relevant source references are
`robot_learning/scenario/observations.py:18-47` and
`robot_learning/scenario/evaluation.py:90-125`.

### Conditioning and trajectory control

**Reasoned implication.** The planar Jacobian has determinant
`0.12 * 0.10 * sin(q2)`. The official radii imply elbow magnitudes from about
49 to 150 degrees, so the target solutions do not require the exact
fully-extended or fully-folded singular configurations. Position control is
therefore kinematically feasible with finite local velocity authority, but
the 1 cm Cartesian tolerance still requires progressively finer joint
regulation as the end-effector approaches the target. Assumptions: the
closed-form solutions above describe the active branches and no unmodeled
contact changes the Jacobian. Sources: `contracts/robots/two_joint_arm.xml:12-20`;
`contracts/task_spec.py:6,10`.

**Reasoned implication; decision relevance.** This favors separating gross reach failures from
near-target regulation failures when choosing the first scientific direction.
Discriminating evidence is time-to-first-entry, minimum distance, end-effector
velocity at entry, and joint velocity during the hold, conditioned on target
radius and angle. Sources: `robot_learning/scenario/evaluation.py:51-106`;
`robot_learning/scenario/observations.py:36-49`.

### Stabilization as the actual bottleneck

**Reasoned implication.** A single successful entry is insufficient: any one
of the next 99 sampled control states outside the 1 cm ball restarts the
streak. The policy must therefore reach a target, reduce residual motion, and
maintain a robust margin against dynamics and sampling-time drift for 2
seconds. Assumptions: the official evaluator uses the stated consecutive
sample semantics and the target remains fixed. Sources:
`contracts/scenario.md:7-20`;
`robot_learning/scenario/environment.py:134-168`.

**Reasoned implication; decision relevance.** A high first-reach rate can coexist with low episode
success, changing whether initial work should emphasize acquisition or
stabilization. Evidence is the joint distribution of first-reach step,
maximum uninterrupted hold, in-tolerance steps, and hold interruptions, not
aggregate reward alone. Sources: `robot_learning/scenario/evaluation.py:51-106`.

### Actuation and transient dynamics

**Reasoned implication.** The policy has bounded torque, 20 ms action updates,
viscous joint damping, and armature inertia. The physical response is governed
approximately by `M(q) qdd + C(q,qdot) qdot + B qdot = tau`, with gravity and
contact terms absent. The configuration-dependent two-link inertia and
velocity-dependent coupling therefore matter in addition to the explicit
damping and armature; with gravity and contact absent, there is no gravity or
collision restoring force. A fixed action can therefore produce overshoot or
residual oscillation, and a successful hold requires feedback rather than
merely reaching a static inverse-kinematic pose.
Assumptions: native MuJoCo motor transmission and rigid-body dynamics apply.
Sources: `contracts/robots/two_joint_arm.xml:2,13-18,30-33`;
`robot_learning/scenario/environment.py:125-133`.

**Reasoned implication; decision relevance.** The first campaign comparison can change if failures
are torque-limited, timing-limited, or caused by poor damping of the learned
controller. Discriminating evidence is action saturation, joint position and
velocity traces, end-effector velocity, and response to matched target
geometries. The current evaluator records distance and hold summaries but not
all of these dynamic quantities; a dedicated scenario measurement would be
needed. Sources: `robot_learning/scenario/evaluation.py:90-125`;
`contracts/instruments.md:149-170`.

### Observation-to-control relation

**Reasoned implication.** For this fixed, stationary-target task, the
observation is effectively Markov with respect to target position, joint
position, and joint velocity: the target can be reconstructed from the
relative vector and the arm pose, and no actuator memory is specified. The
branch errors expose two candidate terminal postures, which can reduce the
need for the policy to solve inverse kinematics from scratch. The observation
does not reveal the physical parameters that determine the next-state response,
so a policy can be state-complete yet dynamically miscalibrated. Assumptions:
the compiled model is fixed across episodes and no hidden actuator state is
introduced. Sources: `robot_learning/scenario/observations.py:27-49`;
`robot_learning/scenario/policy_io.py:11-16`;
`contracts/robots/two_joint_arm.xml:30-33`.

**Reasoned implication; decision relevance.** If performance is geometry-dependent but not
state-dependent, the issue is likely representation or generalization; if
performance changes with velocity and action saturation, it is likely
closed-loop dynamic regulation. Evidence is paired analysis of observations,
actions, qvel, target geometry, and hold interruptions. Sources:
`robot_learning/scenario/evaluation.py:90-125`;
`robot_learning/scenario/observations.py:36-49`.

### Training signal versus official capability

**Reasoned implication.** The baseline learner is exposed to only the outer
0.14-0.20 m radial band, although official episodes include the inner
0.06-0.14 m band. A policy can therefore optimize the current reward and
still have an untested distribution-shift failure, especially because the
inverse-kinematic elbow configuration changes materially with radius.
Assumptions: the baseline training environment remains the active recipe and
the official distribution is the contract distribution. Sources:
`robot_learning/training/environment.py:14-19`;
`contracts/scenario.md:7-13`;
`robot_learning/scenario/observations.py:29-35`.

**Reasoned implication; decision relevance.** The first campaign decision can change between
investigating policy dynamics and investigating radial generalization.
Discriminating evidence is success and hold diagnostics binned by radius over
the full official range, with the same target-angle coverage. Sources:
`robot_learning/scenario/evaluation.py:90-125`;
`contracts/instruments.md:112-147`.

## Unknowns

### Compiled mass, inertia, and torque authority

**Unresolved quantity.** The XML gives link geometry, damping, armature, and
motor transmission but no explicit body mass or inertial tensors. The compiled
MuJoCo mass matrix, actuator torque in physical units after transmission, and
resulting acceleration are therefore not established by the source text alone.
Source: `contracts/robots/two_joint_arm.xml:9-20,30-33`.

**Reasoned implication; decision relevance.** This could change whether observed failures are
reachable with the available torque and whether action smoothing or stronger
feedback is scientifically justified. Assumptions for relevance: the
inferred geom mass properties materially affect the 20 ms response. Evidence:
compiled `body_mass`, `body_inertia`, joint-space mass matrix, and measured
q/qvel response to known actions, obtained through an allowed
`python_module` measurement. Source: `contracts/instruments.md:149-170`.

### Effective joint-limit semantics

**Unresolved quantity.** The XML declares ranges but does not explicitly show
the compiled limit flags. The scientific model treats +/-170 degrees as the
intended kinematic bounds, while the exact runtime enforcement and any
limit-force behavior remain to be confirmed from the compiled model. Source:
`contracts/robots/two_joint_arm.xml:13-18`.

**Reasoned implication; decision relevance.** If limits are soft, inactive, or dynamically enforced,
branch availability, near-boundary control, and failure interpretation differ.
Assumptions for relevance: target angles can drive a legal branch near a
declared shoulder boundary. Evidence: compiled joint-limit fields and
trajectories for targets near the angular seam and shoulder extrema. Source:
`contracts/instruments.md:149-170`.

### Dynamic response and hold margin

**Unresolved quantity.** Before evidence, it is unknown how much residual
end-effector motion remains after nominal convergence, how much torque is
typically saturated, and how sensitive the 1 cm margin is to target angle,
radius, and branch. Sources:
`contracts/robots/two_joint_arm.xml:2,13-18,30-33`;
`contracts/scenario.md:7-20`.

**Reasoned implication; decision relevance.** This determines whether the first useful explanation
is acquisition error, overshoot, weak damping, branch switching, or stochastic
policy behavior. Assumptions for relevance: these mechanisms produce
distinguishable qvel, action, or distance signatures. Evidence: per-control-step
distance, end-effector velocity, qvel, action, saturation, and uninterrupted
hold streaks, stratified by target geometry. Sources:
`robot_learning/scenario/evaluation.py:51-106`;
`contracts/instruments.md:149-170`.

### Observability and hidden-state risk

**Unresolved quantity.** The observation reconstructs target position and exposes
q and qvel, but it does not expose compiled physical parameters, applied
torque after any internal processing, or a direct end-effector velocity. It is
therefore unknown whether a policy can infer enough dynamic state from the
available qvel and recent action history for robust 2-second holding. Sources:
`robot_learning/scenario/observations.py:36-49`;
`robot_learning/scenario/environment.py:125-168`.

**Reasoned implication; decision relevance.** If the required stabilizing variables are unavailable,
memory or an observation change could become more consequential than reward
changes; if q and qvel suffice, representation changes may be low value.
Assumptions for relevance: the response contains hidden or parameter-dependent
state not recoverable from one observation. Evidence: matched-state action
response comparisons and hold success conditioned on qvel and recent action
history. Sources: `robot_learning/scenario/policy_io.py:11-16`;
`contracts/instruments.md:149-170`.

### Generalization to the official inner-radius band

**Unresolved quantity.** It is not established that a policy trained on
0.14-0.20 m targets will solve 0.06-0.14 m targets at the required rate, even
though those targets are kinematically reachable. The smaller-radius branch
geometry and different initial-to-target trajectories may change both
acquisition and stabilization difficulty. Sources:
`robot_learning/training/environment.py:14-19`;
`contracts/scenario.md:7-20`.

**Reasoned implication; decision relevance.** This can change the first campaign direction toward
distribution coverage, representation, or dynamics rather than generic
training continuation. Assumptions for relevance: the radial gap is large
enough to produce systematic rather than sampling noise. Evidence: an
angle-balanced official-distribution panel reporting success, first-reach,
minimum distance, and hold interruptions by radius. Sources:
`robot_learning/scenario/evaluation.py:90-125`;
`contracts/instruments.md:112-147`.

### Reward-to-goal alignment

**Unresolved quantity.** The current reward supplies incremental hold credit
and a completion bonus, but the scientific record does not yet establish
whether optimizing it reliably produces the binary complete-hold outcome.
In particular, the zero hold-exit forfeiture and small outside-band penalty may
make some near-boundary behavior reward-compatible without being success
robust. Sources: `robot_learning/training/reward.py:20-25,65-91`;
`contracts/scenario.md:18-20`.

**Reasoned implication; decision relevance.** A reward change is relevant only if failures show a
repeatable divergence between reward accumulation and complete uninterrupted
hold. Assumptions for relevance: the learned method is sensitive to the
relative shaping terms. Evidence: paired reward-component and official
hold-streak diagnostics for policies with comparable exposure. Sources:
`robot_learning/scenario/environment.py:145-168`;
`robot_learning/scenario/evaluation.py:78-125`;
`contracts/instruments.md:174-189`.

## Decision-relevant synthesis

### Hold stability is the primary physical requirement

**Reasoned implication; decision relevance.** The goal is not point reaching; it is 100 consecutive
in-tolerance samples, so first-reach performance must not be treated as
episode capability. **Assumptions.** The official 1 cm, 2-second, uninterrupted
criterion and 20 ms control period remain fixed. **Source references.**
`contracts/scenario.md:7-20`; `contracts/task_spec.py:7-11`.
**Discriminating evidence.** Per-radius and per-angle first-reach step,
maximum uninterrupted hold, qvel at entry, and hold interruptions from
complete episodes. Sources: `robot_learning/scenario/evaluation.py:51-106`;
`contracts/instruments.md:149-170`.

### Official coverage is broader than baseline training coverage

**Reasoned implication; decision relevance.** The baseline recipe omits official targets below
0.14 m, so early aggregate training performance cannot establish the human
goal. **Assumptions.** The current baseline training distribution is used
without compensating exposure and official success is evaluated on 0.06-0.20 m.
**Source references.** `robot_learning/training/environment.py:14-19`;
`contracts/scenario.md:7-13`. **Discriminating evidence.** Radius-binned
official-distribution success and hold diagnostics with matched angular
coverage, especially for 0.06-0.14 m. Sources:
`robot_learning/scenario/evaluation.py:90-125`.

### The task has two usable kinematic branches

**Reasoned implication; decision relevance.** A policy may succeed by consistently selecting one
branch, and branch switching could create avoidable transients; branch behavior
should be separated from generic reach failure. **Assumptions.** Declared
joint ranges are active and the analytic IK equations describe the runtime
geometry. **Source references.** `contracts/robots/two_joint_arm.xml:12-20`;
`robot_learning/scenario/observations.py:18-47`. **Discriminating evidence.**
Branch-conditioned joint trajectories, branch-error channels, qvel, and hold
interruptions over target geometry. Source:
`robot_learning/scenario/evaluation.py:90-125`.

### Compiled dynamics remain the highest-impact physical unknown

**Reasoned implication; decision relevance.** Without compiled mass/inertia and response data, it is
not possible to distinguish torque authority, transient overshoot, and damping
from policy or representation causes. **Assumptions.** The omitted inertial
properties materially affect the 20 ms response. **Source references.**
`contracts/robots/two_joint_arm.xml:2,13-18,30-33`;
`robot_learning/scenario/environment.py:125-133`. **Discriminating evidence.**
Compiled inertial quantities plus action-to-q/qvel/end-effector response and
action saturation, recorded by an allowed scientific measurement.
Source: `contracts/instruments.md:149-170`.

### The observation is geometrically rich but dynamically incomplete

**Reasoned implication; decision relevance.** The policy can reconstruct target position and receives
qvel, yet lacks direct force, torque, and end-effector-velocity channels; this
could limit robust boundary holding if dynamic state is not inferable.
**Assumptions.** No hidden actuator state is introduced and q/qvel do not
fully determine the relevant response under the compiled dynamics.
**Source references.** `robot_learning/scenario/observations.py:27-49`;
`robot_learning/scenario/policy_io.py:11-16`. **Discriminating evidence.**
Matched-state response and hold comparisons conditioned on qvel, recent actions,
and saturation, rather than observation-only aggregate reward.
Source: `contracts/instruments.md:149-170`.
