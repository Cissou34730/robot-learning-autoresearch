# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. It separates facts fixed by the
human-authored contracts and implementation from deductions and unresolved
quantities. No campaign training or evaluation evidence is included.

## Coupled physical model

The robot is a planar serial two-revolute-joint arm. Let `q1` be the shoulder
angle and `q2` the elbow angle, both measured about the world z axis. The
shoulder is at `(0, 0, 0.02)`, the upper arm has length `l1 = 0.12 m`, and
the forearm has length `l2 = 0.10 m`. Thus, in the arm plane,

```
p(q) = [l1 cos(q1) + l2 cos(q1 + q2),
        l1 sin(q1) + l2 sin(q1 + q2),
        0.02]
```

The initial state is `q = (0, 0)` and zero velocity, so the end effector
starts at `(0.22, 0, 0.02)` in a straight, fully extended configuration. Each
joint is limited to -170 to 170 degrees. Without those angular limits, the
two-link radial workspace is 0.02 to 0.22 m; the official target annulus,
0.06 to 0.20 m, is inside that geometric range. For a target at radius `r`,
inverse kinematics requires
`cos(q2) = (r^2 - l1^2 - l2^2)/(2 l1 l2)`, giving two elbow branches when
the value is interior to [-1, 1]. The corresponding shoulder angle changes
with the branch. At the official radial endpoints the elbow magnitudes are
approximately 150 degrees (`r = 0.06 m`) and 49.5 degrees (`r = 0.20 m`).
Consequently, the target is not just a radial reaching problem: the policy
must select or move between legal elbow configurations while respecting both
joint limits. The position Jacobian has determinant
`l1*l2*sin(q2)`, so the straight initial state is a rank-deficient
configuration for planar motion. Tangential motion initially requires creating
elbow bend rather than relying on a locally invertible position controller.

The controls are direct MuJoCo motor commands. The action has two components,
is clipped to [-1, 1], is passed through unchanged, and is applied with gear
5 to the shoulder and elbow motors. The XML sets a physics step of 0.002 s
and the environment advances ten such steps per action, so the policy acts at
50 Hz with a 20 ms zero-order-held command. Gravity is zero. Each joint has
0.5 damping and 0.01 armature. The plane, target, and arm geoms have
collisions disabled, so contact, friction, and support from the plane cannot
stabilize the arm. A useful local description is
`M(q) qddot + D qdot + limit_constraints = B (5 u)`, with serial-link
inertial coupling in `M(q)` and no gravity term. The exact mass matrix,
actuator response, integrator behavior, and limit-constraint response remain
properties of the compiled MuJoCo model rather than quantities stated
explicitly in the XML.

At reset, the target is a kinematic mocap body in the same z plane as the end
effector. Its angle is sampled over the full circle and its radius is sampled
uniformly from the configured interval. The shared evaluation environment uses
0.06-0.20 m. The target does not move during an episode. The distance used by
success is the 3-D Euclidean end-effector-to-target distance, although the
target and end effector are constructed in one plane.

An action is evaluated after the ten physics substeps. If the sampled
distance is at most 0.01 m, the internal hold counter increases by one;
otherwise it resets to zero. Success is exactly 100 consecutive in-tolerance
control observations, corresponding to 2 seconds at 50 Hz. The episode can
run for at most 500 control steps (10 seconds), and a late reach cannot
succeed unless 100 steps remain. The implementation therefore tests
uninterrupted hold at control-sample resolution, not at every internal
0.002 s physics step.

The 11-element observation contains the two joint positions, two joint
velocities, the three-vector from the end effector to the target, and four
wrapped angular residuals to the open and folded inverse-kinematic solutions.
Given known geometry, joint position and the relative vector together expose
the target position; the branch residuals expose two useful goal
representations. There is no sensor noise or actuator-state observation in
the implementation. The observation does not contain the hold counter,
previous distance, episode step, or whether the last in-tolerance interval
was interrupted. Physical state and target are therefore largely observable,
but the task-success automaton is history-dependent.

The reward supplies progress and closeness shaping, linear hold-progress
credit, a completion bonus, a small action cost, and a small penalty after
leaving the tolerance band. Exiting the band resets task success immediately,
but `HOLD_EXIT_FORFEIT_FRACTION = 0` means previously accumulated hold reward
is not clawed back. Reward is consequently related to, but not equivalent to,
the binary complete-hold outcome.

The quantities most useful for understanding the complete behavior are:
target radius and angle; joint position, velocity, and distance-to-limit;
elbow branch and inverse-kinematic residual; end-effector position and
velocity; first entry time; settling time and distance margin inside the
1 cm band; maximum consecutive hold and every hold interruption; action
magnitude and change; and whether failures occur before reaching, during
convergence, or after apparently stable holding.

## Established facts

| Register | Established fact | Source |
| --- | --- | --- |
| F1 | Official targets span radius 0.06-0.20 m and all angles; success is a continuous 2 s hold, 100 control steps; the official objective is at least 196/200 successes. | `contracts/scenario.md:9-31` |
| F2 | The arm has two hinge joints, 0.12 m and 0.10 m links, joint ranges of +/-170 degrees, damping 0.5, armature 0.01, zero gravity, and timestep 0.002 s. | `contracts/robots/two_joint_arm.xml:1-20` |
| F3 | Motor controls have range +/-1 and gear 5; the target is a non-contact mocap body. | `contracts/robots/two_joint_arm.xml:25-33` |
| F4 | Reset sets positions and velocities to zero, samples a stationary target in the arm plane, and starts with no held steps. | `robot_learning/scenario/environment.py:83-120` |
| F5 | Ten physics steps are taken per action; actions are clipped and held through those steps; distance is checked only after them. | `robot_learning/scenario/environment.py:122-168`, `contracts/task_spec.py:6-11` |
| F6 | The observation is qpos, qvel, relative end-effector error, and four wrapped IK residuals. | `robot_learning/scenario/observations.py:14-49` |
| F7 | Evaluation records first reach, minimum/final distance, in-tolerance steps, maximum hold, and interruptions, while success remains episode-level. | `robot_learning/scenario/evaluation.py:40-125` |
| F8 | The current training constructor samples only radii 0.14-0.20 m, unlike shared official evaluation. | `robot_learning/training/environment.py:14-19`, `contracts/task_spec.py:6-11` |

## Physical consequences

### P1. Geometry supports multiple solutions, but legality is target-dependent

**Decision relevance:** The first campaign decisions may differ depending on
whether robust behavior should be judged as branch selection, branch
transitions, or branch-agnostic Cartesian stabilization. Inner targets demand
large elbow bends, while targets near full reach have different sensitivity
and may favor the other branch. Joint limits can remove one nominal solution
for some angular sectors even when another solution remains.

**Assumptions and sources:** This follows from the 2R equations, the link
lengths and +/-170 degree limits in `contracts/robots/two_joint_arm.xml:12-20`,
and the two explicit IK residuals in
`robot_learning/scenario/observations.py:18-47`. It assumes the compiled
forward kinematics match the XML geometry and that no unlisted joint offset
changes the angle convention.

**Discriminating evidence:** Enumerating both IK branches over the official
radius-angle domain and checking the compiled model's joint limits would
support the claim of full target coverage. Target-conditioned reach failures,
limit contacts, or branch-specific success gaps would weaken it and identify
the relevant configuration class.

### P2. The initial straight configuration creates a reach-phase bottleneck

**Decision relevance:** The choice of early learning representation and
diagnostics depends on whether failures are dominated by escaping the
rank-deficient start, by long-distance translation, or by final convergence.
A policy that appears poor on off-axis targets may be failing to generate
elbow bend rather than lacking target information.

**Assumptions and sources:** The initial state is explicit in
`robot_learning/scenario/environment.py:109-118`; the Jacobian implication
comes from the kinematic model above and the XML link placement. This assumes
standard planar revolute kinematics and no unmodeled external force.

**Discriminating evidence:** Measure early elbow motion, end-effector
tangential velocity, and time to enter a broad neighborhood, conditioned on
target angle. Improvement when the elbow first moves, or a strong angular
pattern at equal radius, supports the bottleneck; uniformly slow radial
progress would weaken it.

### P3. Reaching and holding are coupled but distinct control problems

**Decision relevance:** A first decision about policy evaluation and learning
progress can change if high first-reach rates coexist with low complete
success. The campaign must distinguish acquisition from low-velocity,
margin-preserving stabilization; a single episode reward or minimum distance
cannot establish the latter.

**Assumptions and sources:** The one-centimeter threshold and counter reset are
implemented at `robot_learning/scenario/environment.py:134-159`; diagnostic
fields are available at `robot_learning/scenario/evaluation.py:51-105`.
This assumes the target is stationary as specified by the mocap setup.

**Discriminating evidence:** Compare first reach, time in band, hold
interruptions, distance margin, end-effector velocity, and action magnitude.
Many near-perfect reaches followed by exits support a stabilization limitation;
large minimum distances and no meaningful holds support a reach limitation.

### P4. The success boundary is sampled, delayed, and unforgiving

**Decision relevance:** Decisions about temporal credit, policy determinism,
and what constitutes convincing development evidence depend on the difference
between being inside the band at 50 Hz and being physically quiet enough to
remain there. A reach at step 400 is physically plausible but cannot satisfy
the episode contract.

**Assumptions and sources:** `contracts/task_spec.py:7-11` and
`robot_learning/scenario/environment.py:131-159` define the 20 ms sampling,
100-step hold, and 500-step cap. The inference assumes no hidden benchmark
override of these shared semantics.

**Discriminating evidence:** Plot distance at every control step, not only
minimum and final distance, and record the first entry step and each exit.
Short oscillations or exits between samples would revise the interpretation
only if the protected evaluator measures more frequently; under the visible
contract they do not change success.

### P5. Dynamic authority and damping may make the same geometry easy or hard

**Decision relevance:** The choice between treating the task primarily as
kinematic target selection or as dynamic trajectory control depends on
settling time, overshoot, and cross-joint coupling. It also affects whether
action cost is behaviorally meaningful rather than negligible.

**Assumptions and sources:** Gear, damping, armature, timestep, and gravity
are in `contracts/robots/two_joint_arm.xml:1-3,12-19,30-32`; the held-action
interval is in `robot_learning/scenario/environment.py:125-133`. Exact
inertia and solver behavior are not stated, so no numerical torque-to-motion
prediction is assumed.

**Discriminating evidence:** Controlled small-action and saturated-action
responses at representative configurations, including joint velocities,
settling time, overshoot, and cross-joint motion, would identify effective
authority. Large variation by configuration or limit proximity would support
a dynamic, not purely geometric, explanation.

### P6. The policy sees the physical target but not the success automaton

**Decision relevance:** Decisions about memory, recurrent state, or explicit
hold-oriented diagnostics depend on whether current physical state is enough
to produce stable behavior despite the unobserved hold counter. The target
itself is not a fundamental partial-observability problem because qpos and
relative error determine it under the known model.

**Assumptions and sources:** The observation layout is fixed by
`robot_learning/scenario/observations.py:27-49`; hold state is maintained
privately by `robot_learning/scenario/environment.py:70-73,136-144`.
This assumes observations are delivered without noise and the target remains
fixed.

**Discriminating evidence:** Test identical physical observations reached
with different hold histories and compare actions or outcomes. If outcomes
differ only by hidden history, the automaton is decision-relevant; if a
stable physical margin makes history irrelevant, the missing counter is less
important.

### P7. The current training domain omits the most folded official targets

**Decision relevance:** Early campaign decisions about generalization and
development measurements can change because radii 0.06-0.14 m are official
but absent from the current training constructor. A high result on the
current training range does not establish performance over the official
annulus, especially where elbow bend and branch geometry differ.

**Assumptions and sources:** The mismatch is explicit in
`robot_learning/training/environment.py:14-19` versus
`contracts/task_spec.py:6-11`. This assumes the training constructor remains
the active recipe and the protected final sampler follows the scenario
contract.

**Discriminating evidence:** Stratify development outcomes by target radius
and branch, with particular attention to 0.06-0.14 m. A sharp inner-radius
drop supports distribution-induced failure; radius-independent failures
would weaken that explanation.

### P8. Shaped reward can favor approach without guaranteeing completion

**Decision relevance:** Decisions about which learning curves or checkpoints
are scientifically trusted depend on whether reward tracks uninterrupted
success. The zero hold-exit forfeiture and small outside-band penalty make
repeated near-holds potentially more attractive in reward than their binary
episode outcome suggests.

**Assumptions and sources:** The reward terms are defined in
`robot_learning/training/reward.py:16-107`, while the environment resets the
actual hold counter in `robot_learning/scenario/environment.py:136-154`.
This assumes the current reward remains active.

**Discriminating evidence:** Correlate return with complete success,
interruption count, maximum consecutive hold, and final distance. Weak
correlation or high-return failures would support reward-outcome mismatch;
tight correlation would weaken its importance for the first decisions.

## Unknowns

| Unknown | Decision relevance | Assumptions and source | Evidence that would resolve it |
| --- | --- | --- | --- |
| U1: Compiled link masses, inertias, and exact motor torque convention | Determines whether dynamic model identification is necessary and how much authority exists near different configurations. | Geometry and gear are explicit, but masses are not specified in `contracts/robots/two_joint_arm.xml:9-20,30-32`; this assumes MuJoCo defaults are not treated as scientific measurements. | Inspect the compiled `MjModel` and compare predicted and measured acceleration under known controls. |
| U2: Integrator and joint-limit constraint response | Changes predictions of overshoot, boundary behavior, and reproducibility near +/-170 degrees. | The XML sets timestep but not an explicit integrator or limit solver parameters (`contracts/robots/two_joint_arm.xml:1-3,12-18`). | Record model options and limit reactions, then apply repeatable near-limit trajectories. |
| U3: Whether every official target has a legal, numerically stable IK branch | Changes whether failures can be attributed to learning rather than feasibility. | Analytic geometry predicts feasibility over the stated annulus, but compiled joint-limit conventions must agree with it (`contracts/scenario.md:9-12`; XML joint ranges). | Exhaustive angle-radius IK checking plus forward simulation of both branches. |
| U4: Settling and hold robustness across radius, angle, and branch | Determines whether the main limiting capability is reach, convergence, or disturbance-free stabilization. | The target is stationary and contacts are disabled, but dynamic coefficients are only partly explicit (`contracts/robots/two_joint_arm.xml`; environment hold logic). | Use the evaluation diagnostics with end-effector velocity, margin, and interruption timing stratified by geometry. |
| U5: Practical sufficiency of the 11-D observation for a feed-forward policy | Changes decisions about policy memory and whether hidden hold progress matters. | Physical target is inferable from qpos and relative error, but hold history and episode time are omitted (`robot_learning/scenario/observations.py:27-49`; environment state). | Counterfactual identical-state episodes with different prior hold histories, followed by outcome comparison. |
| U6: Exact protected official sampling measure | Changes weighting of radius-conditioned evidence and the interpretation of 98% performance. | The visible scenario and shared environment specify uniform angle and radius construction, but the final evaluator is human-owned (`contracts/scenario.md:9-12`; `robot_learning/scenario/environment.py:83-97`). | Verify the protected benchmark sampler or compare its emitted target geometry with the visible sampler before pooling results. |

## Decision-relevant synthesis

1. **Feasibility and branch structure come first.** The official annulus lies
   inside the nominal 2R workspace, but inner targets require approximately
   150-degree elbow configurations and joint limits can make branch legality
   angle-dependent. This matters for whether early failures are treated as
   learning failures or configuration/branch failures. It assumes the XML
   geometry is the compiled geometry; verify by exhaustive IK and forward
   checks. Sources: `contracts/scenario.md:9-12`,
   `contracts/robots/two_joint_arm.xml:12-20`,
   `robot_learning/scenario/observations.py:18-47`.

2. **The success bottleneck must be localized in time.** A policy can reach
   within 1 cm and still fail through one sampled exit during the 100-step
   hold. First campaign comparisons therefore depend on separating first
   reach, convergence, margin, and interruption behavior rather than using
   return or minimum distance alone. This assumes the visible 50 Hz sampled
   semantics are authoritative. Sources:
   `robot_learning/scenario/environment.py:134-168`,
   `robot_learning/scenario/evaluation.py:51-105`,
   `contracts/task_spec.py:7-11`.

3. **Dynamic uncertainty is material despite simple geometry.** Zero gravity
   and disabled contacts remove major complications, but serial-link inertia,
   damping, action zero-order hold, and limit response determine whether
   holding is easy or oscillatory. The first method choice can change if
   measured settling is configuration-dependent. The exact compiled model
   quantities and responses remain unresolved. Sources:
   `contracts/robots/two_joint_arm.xml:1-3,12-19,30-32`,
   `robot_learning/scenario/environment.py:125-133`.

4. **Official coverage is broader than the current training domain.** The
   active training constructor omits 0.06-0.14 m targets, precisely where
   folded configurations become important. Any early evidence that does not
   stratify by radius and angle cannot establish the human goal. This
   conclusion depends on the current training constructor and the protected
   evaluator honoring the official range. Sources:
   `robot_learning/training/environment.py:14-19`,
   `contracts/scenario.md:9-12`.

5. **Reward and success must remain separate scientific quantities.** The
   reward grants incremental hold credit and does not forfeit prior hold
   credit on exit, whereas the task outcome resets immediately. Whether this
   mismatch is consequential is an empirical question best decided by
   correlating reward with complete success and interruption statistics.
   Source: `robot_learning/training/reward.py:65-91`,
   `robot_learning/scenario/environment.py:136-154`.
