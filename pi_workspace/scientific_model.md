# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. It distinguishes what the human-authored
contracts and implementation establish from consequences inferred from them and
quantities that remain unresolved before campaign evidence exists. References use
repository paths and line ranges so the claims can be rechecked.

## Established facts

### Task and episode semantics

- The official target is sampled with radius uniformly in `[0.06, 0.20]` m and
  angle uniformly over `[-pi, pi]`. The target is placed in the arm's horizontal
  plane. Success requires the end effector to be no more than `0.01` m from the
  target for 2 uninterrupted seconds, which is 100 control steps at the official
  timing. An episode has at most 500 control steps and the objective is at least
  196 successes in a fixed 200-episode assessment
  `[contracts/scenario.md:7-31]`.
- Reset sets both joint positions and velocities to zero, computes the forward
  state, then samples one fixed target for the episode
  `[robot_learning/scenario/environment.py:102-120]`. The training constructor
  currently samples only `[0.14, 0.20]` m, whereas evaluation uses the official
  `[0.06, 0.20]` m distribution
  `[robot_learning/training/environment.py:14-19]`,
  `[robot_learning/scenario/environment.py:171-178]`.
- A tolerance sample increments the held-step counter; one sample outside resets
  it to zero. Termination occurs only at 100 consecutive in-tolerance samples,
  not on first arrival
  `[robot_learning/scenario/environment.py:134-168]`.

### Morphology and kinematics

- The robot is a planar serial 2R arm. The shoulder is at `(0, 0, 0.02)` m,
  both hinges rotate about world `z`, the upper arm is `0.12` m, and the
  forearm is `0.10` m. The end-effector site is at the forearm tip
  `[contracts/robots/two_joint_arm.xml:9-21]`,
  `[contracts/robots/two_joint_arm.py:5-7]`.
- With shoulder angle `q1` and relative elbow angle `q2`, the endpoint is
  `x = 0.12 cos(q1) + 0.10 cos(q1+q2)`,
  `y = 0.12 sin(q1) + 0.10 sin(q1+q2)`, `z = 0.02` m. Each joint range is
  `[-170, 170]` degrees
  `[contracts/robots/two_joint_arm.xml:12-19]`.
- The unconstrained radial workspace is `[0.02, 0.22]` m. With the actual
  `+-170` degree elbow limit, the most folded radius is about `0.0277` m and the
  straight radius is `0.22` m. The official radial interval is therefore
  interior to the radial workspace, with a 2 cm margin at its outer edge.
- A non-singular target generally has two inverse-kinematic configurations,
  represented in the observation code as positive and negative elbow solutions.
  The observation code computes both shoulder/elbow pairs from the target
  `[robot_learning/scenario/observations.py:14-35]`.

### Dynamics, actuation, and timing

- MuJoCo advances at `0.002` s per physics step with zero gravity. Each action is
  clipped to `[-1, 1]^2`, copied directly into the two motor controls, and held
  for 10 physics steps. The policy therefore acts at `0.020` s intervals
  (50 Hz), while the physical state evolves at 500 Hz
  `[contracts/robots/two_joint_arm.xml:1-3,30-33]`,
  `[robot_learning/scenario/environment.py:122-133]`.
- Each motor has gear 5 and control limits `[-1,1]`, giving a nominal bounded
  joint torque command of magnitude 5 in MuJoCo's motor convention. Each hinge
  has damping `0.5` and armature `0.01`
  `[contracts/robots/two_joint_arm.xml:12-19,30-33]`.
- There is no gravity term, target interaction, or ground interaction in the
  intended task: the target and plane have collision disabled, and the target
  is a mocap body. The available physical effects are thus inertial motion,
  actuator torque, joint damping, armature, and joint limits
  `[contracts/robots/two_joint_arm.xml:4-7,25-28]`.

### Observation and action interface

- The policy receives 11 values: two joint positions, two joint velocities, the
  three-dimensional endpoint-to-target vector, and four wrapped angular errors
  to the positive- and negative-elbow inverse-kinematic solutions
  `[robot_learning/scenario/observations.py:11-49]`.
- The physical action mapping is identity; it is not a position target,
  velocity target, or learned inverse dynamics controller
  `[robot_learning/scenario/policy_io.py:11-16]`.
- The scalar learning signal rewards distance reduction and a short-range
  closeness potential, gives linear progress for consecutive in-tolerance
  steps, adds a completion bonus at 100 steps, and applies a small action cost.
  Leaving the tolerance after a partial hold receives only the configured
  outside-band penalty; the hold-progress forfeiture fraction is zero
  `[robot_learning/training/reward.py:16-25,47-108]`.
- In the nominal simulator this is effectively a fully observed Markov state:
  joint state is exact, the target-relative vector is exact, and the target can
  be reconstructed from forward kinematics plus that vector. No sensor noise,
  delay, contact uncertainty, or actuator-state observation is implemented.
  Policy normalization may transform the numerical observation for the learned
  model, but does not add physical information
  `[robot_learning/scenario/observations.py:27-49]`,
  `[contracts/policy_runtime.py:153-177]`.

## Physical consequences

### Reachability is feasible but not uniform in control difficulty

The target interval is inside the arm's reachable workspace, and the two
inverse-kinematic branches provide alternative endpoint configurations. However,
the endpoint Jacobian has determinant proportional to
`0.12 * 0.10 * sin(q2)`: configurations near a straight or fully folded arm
convert joint motion into endpoint motion less favorably in one direction.
The official interval avoids the exact singular radii, but its outer targets
are closer to the straight-arm condition than its inner targets. Joint limits
also make targets near a world angle of `+-pi` a question of branch and
shoulder-margin selection rather than simple rotational symmetry.

This can change whether an early decision treats failures as coverage,
inverse-kinematic branch selection, or endpoint conditioning. It assumes the
standard 2R forward kinematics and that the XML joint ranges are enforced by
MuJoCo. Supporting references are
`[contracts/robots/two_joint_arm.xml:12-20]` and
`[robot_learning/scenario/observations.py:18-35]`. Evidence supporting the
implication would show radius/angle-dependent endpoint error, joint travel, or
branch occupancy; uniform performance across those bins would weaken it.

### The task is a trajectory-and-stabilization problem, not just positioning

From the reset state the arm is straight along `+x`, stationary, with endpoint
`(0.22, 0, 0.02)` m. The nearest possible sampled target is still 2 cm away,
and the farthest initial separation is about 42 cm for a 20 cm target behind the
base. A successful policy must accelerate toward the target, remove residual
joint velocity, enter a 1 cm disk, and keep the endpoint there for 100
post-action observations. A fast arrival with oscillation or an exit on the
100th interval is a failure under the authoritative semantics.

This can change the first campaign decision between studying arrival and
studying hold loss. It assumes the reset and target sampling code is used
without alteration. Sources are
`[robot_learning/scenario/environment.py:83-119,134-159]` and
`[contracts/scenario.md:9-20]`. Evidence is the joint/endpoint time series:
first in-tolerance step, endpoint velocity at entry, longest uninterrupted run,
and the number and timing of exits. A high first-arrival rate with low success
would support a stabilization explanation; failure before tolerance would
weaken it.

### Direct torque control couples speed, precision, and saturation

An action persists for 20 ms, so the controller cannot correct continuously at
the physics timestep. A large action can reduce initial error quickly but
inject joint velocity that must be dissipated by later actions and damping.
Near an endpoint, the same joint-space correction produces different Cartesian
effects depending on configuration. The 5-unit torque bound and joint damping
therefore couple time-to-reach, overshoot, and hold robustness. There is no
separate low-level position servo to hide this coupling.

This can change whether learning behavior is interpreted as an observation or
representation problem versus a control-bandwidth problem. It assumes MuJoCo's
motor gear is the only actuator scaling and that actions are held
zero-order. Sources are
`[contracts/robots/two_joint_arm.xml:1-3,12-19,30-33]` and
`[robot_learning/scenario/environment.py:125-133]`. Supporting evidence would
be action saturation fraction, endpoint speed, torque-to-error phase plots, and
performance when targets are grouped by required joint travel; weak saturation
and low endpoint speed would weaken this explanation.

### The observation makes branch choice possible without making it automatic

The policy knows the current joint state and receives both IK branch residuals,
so the nominal simulation does not force it to infer the target from pixels or
remember hidden target motion. It still must choose a continuous route from
`q=(0,0)` to one of the two configurations, avoid overshoot, and regulate in
the selected configuration. The four branch errors are derived features, not
constraints or commands; either branch remains physically available.

This can change whether branch-specific behavior is a meaningful scientific
distinction or merely an implementation artifact. It assumes the serialized
policy uses the same observation and action functions as training
`[contracts/policy_runtime.py:69-87]`. Evidence is branch occupancy, joint
trajectory, and matched-target performance after separating by branch; no
branch dependence would weaken the need to distinguish them.

### The current training/evaluation geometry creates a coverage question

Training excludes the official inner radii below 14 cm, while assessment includes
them down to 6 cm. Inner targets require more folded configurations and may have
different branch travel and conditioning. Consequently, a policy can appear
successful on the current training distribution while failing on an official
subpopulation. This is a distributional physical consequence, not evidence that
the inner region is intrinsically unreachable.

This can change the first decision about whether a candidate's deficit is
learning coverage or closed-loop control. The source distinction is
`[robot_learning/training/environment.py:14-19]` versus
`[contracts/task_spec.py:6-11]`. Evidence is success and hold diagnostics
binned by radius, with angle and branch reported separately; a flat radius
profile would weaken the coverage explanation.

### The reward is an imperfect physical objective

The official outcome is an uninterrupted binary hold, while the current reward
also pays for getting closer, staying close, and accumulating partial hold
progress. Thus a policy can be locally rewarded for a near-target oscillation
or for repeatedly re-entering tolerance even when that behavior cannot complete
the hold. The zero hold-progress forfeiture further means that an interrupted
partial hold does not erase its accumulated reward, although the environment
does reset the actual success counter.

This can change the first research decision about whether a training plateau is
an optimization failure or a mismatch between shaped reward and complete-hold
behavior. It assumes the current reward remains the active training signal;
the protected outcome remains independent of reward. Sources are
`[robot_learning/training/reward.py:47-108]` and
`[robot_learning/scenario/environment.py:136-168]`. Evidence is the joint
distribution of reward components, re-entry count, longest uninterrupted run,
and final success. High shaped return with frequent re-entry and low success
would support reward-outcome mismatch; aligned return and success would weaken
it.

## Unknowns

### Effective inertial model

The XML specifies link geometry, damping, armature, and actuation, but does not
state link mass, density, or explicit inertia. MuJoCo's compiled defaults and
capsule geometry determine the effective mass matrix, yet their numerical values
are not established by the human-authored XML alone
`[contracts/robots/two_joint_arm.xml:9-20]`. This matters because acceleration,
overshoot, and the torque needed to settle depend on configuration-dependent
inertia. The relevant discriminating evidence is the compiled `MjModel` mass
and inertia arrays plus torque-to-acceleration and free-response measurements.
Those measurements would support the present control-bandwidth interpretation
or revise it if damping dominates and inertia is small.

### Feasible branch and limit margins over the whole distribution

Analytic geometry indicates that the official annulus is reachable, but the
exact minimum joint-limit margin, Jacobian conditioning, and shortest feasible
branch for every radius-angle pair have not been measured. This matters if
failures cluster at particular angles or if one nominally valid branch is
effectively unusable under the 5-unit torque bound. Evidence would be a
workspace sweep recording both IK solutions, joint-limit margins, Jacobian
condition measures, and reachable trajectories. A nonzero margin with
angle-independent control effort would weaken the limit explanation.

### Closed-loop hold mechanism

The task implementation defines the hold counter, but it does not establish
whether likely exits are caused by endpoint velocity, action quantization,
policy noise, an unstable branch, or numerical sampling at the tolerance
boundary. The relevant quantities are endpoint velocity and radial/tangential
error at tolerance entry and exit, action changes at those times, and the
longest held run. Repeated exits with near-zero velocity would weaken a purely
dynamic explanation; exits aligned with high speed or saturated corrections
would support it.

### Numerical and policy-state details that can affect reproducibility

The physical environment is deterministic conditional on the sampled seed and
action sequence, but the exact observation normalization statistics and
serialized policy runtime are part of a candidate's executable behavior
`[contracts/policy_runtime.py:61-87,153-177]`. It is not yet known whether
normalization, rather than physical state, creates scale-sensitive behavior
across the 6-20 cm interval. Comparing raw observation ranges, normalized
ranges, and candidate diagnostics by target radius can support or revise that
possibility. This is an implementation uncertainty, not evidence of partial
physical observability.

### Scientifically meaningful quantities

Across a complete episode, the most informative physical record is target
radius/angle; both joint positions and velocities; endpoint error vector and
norm; radial and tangential error; first-entry time; endpoint velocity at entry;
action/torque magnitude and saturation; joint-limit margin; selected IK branch;
longest uninterrupted hold; exit count and exit state; and time to success or
timeout. These quantities connect morphology, actuation, observation, and the
binary outcome. The current research evaluator already records target geometry,
minimum/final distance, first reach, maximum held steps, in-tolerance steps, and
interruptions
`[robot_learning/scenario/evaluation.py:40-125]`; the remaining quantities are
not established as recorded evidence before campaign measurements.

## Decision-relevant synthesis

1. **Success is controlled stabilization after reach, not proximity alone.**
   This changes the first interpretation of a candidate: a high first-arrival
   rate does not imply a route to 98% success unless 100 consecutive samples
   remain inside tolerance. Assumes the reset, 50 Hz action loop, and counter
   semantics are authoritative. Sources:
   `[contracts/scenario.md:9-20]`,
   `[robot_learning/scenario/environment.py:122-168]`. Discriminating evidence:
   entry velocity, uninterrupted-run length, exit state, and success by target
   geometry.

2. **The official annulus is reachable, but radius and angle can alter
   conditioning and branch/limit margins.** This can change whether the first
   campaign decision prioritizes generalization coverage, branch behavior, or
   control precision. Assumes standard planar 2R kinematics and enforced
   `+-170` degree ranges. Sources:
   `[contracts/robots/two_joint_arm.xml:9-20]`,
   `[robot_learning/scenario/observations.py:18-35]`. Discriminating evidence:
   an analytic workspace/conditioning sweep paired with radius-angle success,
   effort, and joint-limit diagnostics.

3. **The learned controller directly commands bounded torques at 50 Hz.**
   Therefore speed, overshoot, and hold stability are one coupled control
   problem; no low-level position controller separates them. This could change
   the initial scientific direction if saturation or endpoint velocity explains
   most failures. Assumes standard MuJoCo motor semantics and zero-order action
   hold. Sources:
   `[contracts/robots/two_joint_arm.xml:1-3,30-33]`,
   `[robot_learning/scenario/environment.py:125-133]`. Discriminating evidence:
   compiled inertia, torque/acceleration response, action saturation, and
   error-velocity traces.

4. **The current training distribution does not cover the full official radial
   distribution.** This makes an official failure ambiguous between physical
   difficulty and untrained coverage, especially for folded inner targets. It
   can change the first campaign comparison and cannot be resolved from aggregate
   training reward. Sources:
   `[robot_learning/training/environment.py:14-19]`,
   `[contracts/task_spec.py:6-11]`. Discriminating evidence: matched diagnostic
   panels stratified by radius, angle, and IK branch.

5. **The shaped reward is not identical to complete-hold success.** This can
   change whether an apparent training improvement is treated as meaningful
   progress or as exploitation of partial proximity/hold credit. Assumes the
   current reward implementation is used. Sources:
   `[robot_learning/training/reward.py:47-108]`,
   `[robot_learning/scenario/environment.py:136-168]`. Discriminating evidence:
   reward-component totals compared with re-entry count, longest hold, and
   binary success.

6. **The exact inertial and normalization effects remain unresolved.** The XML
   fixes the qualitative dynamics but not the numerical mass matrix, while
   candidate runtime normalization can alter policy sensitivity without changing
   physics. This matters only if response or performance patterns cannot be
   explained by geometry and explicit actuator parameters. Sources:
   `[contracts/robots/two_joint_arm.xml:9-20]`,
   `[contracts/policy_runtime.py:61-87]`. Discriminating evidence: compiled-model
   parameters, controlled physical response measurements, and raw-versus-
   normalized observation diagnostics.
