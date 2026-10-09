## Established facts

### Human task and assessment

- **[Repository fact]** The official target has radius uniformly sampled from
  0.06 m to 0.20 m and angle spanning the full circle. The implementation
  samples radius and angle independently and uniformly, so this is uniform in
  radius and angle rather than uniform in planar area. The target is fixed for
  an episode. Sources: `contracts/scenario.md#L7-L12`,
  `contracts/task_spec.py#L6-L11`,
  `robot_learning/scenario/environment.py#L83-L97`.
- **[Repository fact]** Success requires the end effector to be at distance at
  most 0.01 m from the target for 2 s without an interruption. The official
  control period is 0.02 s, hence the required hold is 100 control steps. An
  episode has at most 500 control steps, and the official assessment uses 200
  episodes with success required in at least 196. Sources:
  `contracts/scenario.md#L9-L31`, `contracts/task_spec.py#L7-L11`.
- **[Repository fact]** The official objective is episode success, not
  intermediate reach, reward, or average distance. The development panel is
  distinct from the official panel. Source: `contracts/scenario.md#L17-L32`.

### Morphology and coordinates

- **[Repository fact]** The robot is a fixed-base serial planar arm with two
  revolute joints. The shoulder and elbow axes are both the world/body
  z-axis; the upper arm is 0.12 m and the forearm is 0.10 m. The arm plane is
  z = 0.02 m. Source: `contracts/robots/two_joint_arm.xml#L9-L20`,
  `contracts/robots/two_joint_arm.py#L5-L7`.
- **[Repository fact]** Both joints have limits of -170 to +170 degrees. The
  initial state sets both joint positions and velocities to zero, then samples
  the target in the arm plane. Sources:
  `contracts/robots/two_joint_arm.xml#L12-L19`,
  `robot_learning/scenario/environment.py#L102-L120`.
- **[Repository fact]** The target is a mocap body and the arm, target, and
  plane have collision disabled. The plane and target are therefore visual
  geometry, not contact constraints in this task. Sources:
  `contracts/robots/two_joint_arm.xml#L4-L11`,
  `contracts/robots/two_joint_arm.xml#L25-L27`.

### Actuation, simulation, and timing

- **[Repository fact]** Each action has two components in [-1, 1]. The policy
  action is passed through unchanged, clipped to that interval, assigned to
  the two motor controls, and held while MuJoCo advances ten substeps.
  Sources: `robot_learning/scenario/policy_io.py#L11-L16`,
  `robot_learning/scenario/environment.py#L122-L133`,
  `contracts/robots/two_joint_arm.xml#L30-L33`.
- **[Repository fact]** MuJoCo integrates with a 0.002 s timestep, so one
  policy action persists for 0.020 s (50 control updates per second). Each
  motor has gear 5 and control range [-1, 1], while each joint has damping
  0.5 and armature 0.01. There is no gravity. Sources:
  `contracts/robots/two_joint_arm.xml#L1-L2`,
  `contracts/robots/two_joint_arm.xml#L12-L18`,
  `contracts/robots/two_joint_arm.xml#L30-L33`,
  `contracts/task_spec.py#L7-L11`.
- **[Repository fact]** The XML specifies geometric capsules and sites but no
  explicit body masses, inertias, friction losses, or actuator dynamics.
  MuJoCo consequently supplies any omitted compiled defaults and derives
  inertial properties from the model definition and defaults. Source:
  `contracts/robots/two_joint_arm.xml#L1-L33`.
- **[Repository fact]** The environment increments the hold counter only after
  each ten-substep action, resets that counter to zero on an out-of-tolerance
  post-step distance, and terminates when the counter reaches 100. Source:
  `robot_learning/scenario/environment.py#L131-L168`.

### Sensing and policy loop

- **[Repository fact]** The observation has 11 values: two joint positions,
  two joint velocities, the three-dimensional end-effector-minus-target
  vector, and four wrapped errors to the two geometric inverse-kinematics
  branches (open and folded). Source:
  `robot_learning/scenario/observations.py#L11-L49`.
- **[Repository fact]** The observation exposes current joint configuration,
  joint velocity, and relative target displacement, but does not expose the
  hold counter, previous distance, episode step, action history, actuator
  torque, or compiled inertial parameters. The distance is derivable as the
  norm of the relative vector. Sources:
  `robot_learning/scenario/observations.py#L27-L49`,
  `robot_learning/scenario/environment.py#L116-L120`,
  `robot_learning/scenario/environment.py#L157-L168`.
- **[Repository fact]** The baseline trainer uses a feed-forward PPO MLP
  policy with two 64-unit tanh layers; the saved runtime calls the policy
  once per 0.020 s control step. Sources:
  `robot_learning/train.py#L22-L29`,
  `robot_learning/train.py#L128-L135`,
  `robot_learning/scenario/viewer.py#L59-L75`.

## Physical consequences

### Kinematics and reachable workspace

- **[Reasoned implication]** With joint coordinates \(q_1,q_2\), the end
  effector position relative to the base is
  \(x=0.12\cos q_1+0.10\cos(q_1+q_2)\),
  \(y=0.12\sin q_1+0.10\sin(q_1+q_2)\), and z = 0.02 m. The unconstrained
  radial workspace is the annulus 0.02 to 0.22 m; joint limits remove parts
  of its angular boundary. **Decision relevance:** this determines whether
  failures can be geometric or must be control failures. **Assumptions:**
  rigid links, the XML frame convention, and no deflection or contact.
  **Sources:** `contracts/robots/two_joint_arm.xml#L9-L20`,
  `contracts/robots/two_joint_arm.py#L5-L7`. **Discriminating evidence:**
  forward-kinematics enumeration over the joint limits and target samples.
- **[Reasoned implication]** For an official target radius in [0.06, 0.20] m,
  the inverse-kinematics elbow magnitude is approximately 49.5 to 150.4
  degrees, within the +/-170 degree elbow limit. The two signs of \(q_2\)
  provide elbow-open and elbow-folded solutions; their shoulder offsets are
  approximately 22.3 to 56.6 degrees. At least one shoulder representative
  remains inside +/-170 degrees for every target angle in the official annulus,
  so the official distribution is geometrically reachable even though one
  branch can be excluded near a joint-limit sector. **Decision relevance:**
  reach failure should not be attributed to target impossibility without
  checking the actual configuration. **Assumptions:** the planar two-link
  equations and exact stated limits. **Sources:**
  `contracts/robots/two_joint_arm.xml#L12-L20`,
  `robot_learning/scenario/observations.py#L18-L35`,
  `contracts/scenario.md#L7-L12`. **Discriminating evidence:** exact
  constrained IK enumeration with branch-feasibility labels by target radius
  and angle.
- **[Reasoned implication]** The kinematic Jacobian loses rank at a straight
  or folded configuration when \(\sin q_2=0\). The reset is straight
  (\(q_2=0\)) and therefore starts at a kinematic singularity, although the
  official target annulus itself is away from the exact fully extended radius.
  **Decision relevance:** the first motion and targets near the initial
  direction can have poor instantaneous directional leverage, making
  trajectory choice and transient behavior distinct from final reachability.
  **Assumptions:** standard planar 2R Jacobian and the reset being evaluated
  before the first action. **Sources:**
  `robot_learning/scenario/environment.py#L102-L120`,
  `contracts/robots/two_joint_arm.xml#L12-L19`. **Discriminating evidence:**
  measured initial joint accelerations, end-effector velocity, and condition
  number of the Jacobian under representative actions.

### Actuation and dynamic control authority

- **[Reasoned implication]** The action is a direct bounded motor command, not
  a desired position or velocity. Under the standard MuJoCo hinge-motor
  convention, the gear scales the generalized motor force, so the command
  selects a bounded torque-like input with nominal magnitude proportional to
  5 times the normalized control. The command is zero-order-held for 20 ms.
  **Decision relevance:** reaching and holding require both sufficient
  transient torque and sufficiently fine corrective action at the target.
  **Assumptions:** the native MuJoCo motor transmission semantics and no
  replacement policy I/O. **Sources:**
  `contracts/robots/two_joint_arm.xml#L30-L33`,
  `robot_learning/scenario/policy_io.py#L11-L16`,
  `robot_learning/scenario/environment.py#L125-L133`. **Discriminating
  evidence:** controlled single-joint and coupled-joint step responses,
  including torque, velocity, and end-effector displacement per action.
- **[Reasoned implication]** Gravity and contact cannot create disturbance or
  support forces in this model. The relevant passive effects are joint
  damping and armature, while serial-link inertia couples shoulder and elbow
  motion. Thus a stable hold is principally an active regulation problem:
  small alternating actions must counter velocity and configuration error
  without leaving the 1 cm ball. **Decision relevance:** controller
  smoothness and settling behavior matter more than collision avoidance or
  load-bearing. **Assumptions:** disabled contacts remain disabled and
  omitted dynamics do not introduce an external force. **Sources:**
  `contracts/robots/two_joint_arm.xml#L1-L2`,
  `contracts/robots/two_joint_arm.xml#L9-L19`,
  `contracts/robots/two_joint_arm.xml#L25-L27`. **Discriminating evidence:**
  free response with zero input and hold-at-target trials, separated into
  damping, overshoot, and residual-velocity measurements.
- **[Reasoned implication]** Exact acceleration, settling time, and control
  authority cannot be inferred from link lengths and damping alone because
  the compiled masses and inertias are not explicit. The same normalized
  action can therefore produce either a fast, overshooting trajectory or a
  slow, torque-limited trajectory under plausible compiled parameters.
  **Decision relevance:** this can change whether the initial policy problem
  is primarily exploration, trajectory shaping, or stabilization. **Assumptions:**
  the XML is the complete physical definition and no hidden parameter override
  changes it. **Sources:** `contracts/robots/two_joint_arm.xml#L1-L33`.
  **Discriminating evidence:** read-only MuJoCo model introspection followed
  by action-to-acceleration and settling-time measurements.

### Initial state, trajectories, and convergence

- **[Reasoned implication]** Every episode begins from the same zero-angle,
  zero-velocity straight pose while the target varies. The controller must
  first break the same singular initial configuration, then converge to one
  of the feasible IK branches; target angle changes the required shoulder
  travel, and target radius changes the elbow geometry. **Decision relevance:**
  a policy can exploit a fixed start but must cover a global target-angle
  family rather than learn a single local correction. **Assumptions:** reset
  semantics are unchanged and the target is not moved after reset. **Sources:**
  `robot_learning/scenario/environment.py#L102-L120`,
  `robot_learning/scenario/environment.py#L83-L97`. **Discriminating
  evidence:** convergence time and failure rate stratified by target angle,
  radius, and selected IK branch.
- **[Reasoned implication]** The two IK branches are physically distinct
  trajectories, not merely alternate labels: they require opposite elbow
  motion and different joint velocities, damping losses, and transient
  overshoot. Near a target, either branch can be valid, but switching branches
  during convergence would require passing through a high-error configuration
  or making a large joint excursion. **Decision relevance:** a policy may
  benefit from branch consistency and need not reproduce one globally
  preferred posture. **Assumptions:** no obstacle or self-contact cost exists
  and branch switching is not separately rewarded. **Sources:**
  `robot_learning/scenario/observations.py#L18-L47`,
  `contracts/robots/two_joint_arm.xml#L12-L20`. **Discriminating evidence:**
  joint-space trajectories, branch classification at first entry, and
  post-entry branch-switch counts.

### Hold semantics and coupled success requirements

- **[Reasoned implication]** Success is a conjunction of reach, low residual
  motion, and uninterrupted stabilization: a policy can reach the tolerance
  ball quickly yet fail if it overshoots, oscillates, or drifts out during the
  2 s hold. The 1 cm radius is about 4.5% of maximum arm reach, so endpoint
  error leaves little room for unmodeled transient motion. **Decision
  relevance:** first-capture rate alone is not a sufficient progress measure;
  maximum held steps, interruptions, and distance margin are causally
  meaningful. **Assumptions:** the official outcome uses the stated hold
  definition and endpoint distance. **Sources:**
  `contracts/scenario.md#L9-L20`,
  `robot_learning/scenario/environment.py#L134-L168`. **Discriminating
  evidence:** episode traces containing first entry, minimum distance,
  velocity at entry, maximum uninterrupted hold, and every exit.
- **[Reasoned implication]** Because the hold counter is reset by one
  out-of-tolerance control-step sample, robust success requires a distance
  margin, not merely touching the boundary. A policy should converge with
  sufficiently low endpoint velocity that the 20 ms sampling interval does
  not carry it across the tolerance boundary. **Decision relevance:** the
  useful distinction is boundary contact versus a stable invariant region;
  this can change whether learning should emphasize terminal approach or
  local regulation. **Assumptions:** the shared environment's post-step
  counter update represents the assessment semantics. **Sources:**
  `robot_learning/scenario/environment.py#L131-L159`,
  `contracts/task_spec.py#L8-L11`. **Discriminating evidence:** distance and
  velocity sampled at every control step during successful and interrupted
  holds, plus a comparison of boundary margin.

### Observation, control, and outcome

- **[Reasoned implication]** The instantaneous physical state relevant to
  deterministic motion is substantially observable: joint position,
  velocity, and target-relative endpoint error are supplied, and target
  position can be reconstructed from known forward kinematics plus that
  relative vector. The four IK errors provide a direct branch-conditioned
  route to either geometric solution. **Decision relevance:** a failure is
  more plausibly due to control or learning than to target-state
  unobservability. **Assumptions:** model geometry is known exactly to the
  policy implementation and there are no unmodeled disturbances. **Sources:**
  `robot_learning/scenario/observations.py#L27-L49`,
  `contracts/robots/two_joint_arm.py#L5-L7`. **Discriminating evidence:**
  reconstruct target and endpoint from observations and compare them with
  simulator state over all target geometries.
- **[Reasoned implication]** The task state is not fully observable to the
  feed-forward policy because hold progress, episode time, and action history
  are omitted. Two physically identical observations can have different
  accumulated hold counters and different remaining time. The optimal
  action may nevertheless be the same if it is a robust state-feedback
  stabilizer, so hidden hold progress is a constraint on temporal credit and
  termination awareness rather than proof of impossibility. **Decision
  relevance:** this can determine whether to prioritize robust regulation over
  explicit timing-dependent behavior. **Assumptions:** the baseline remains
  nonrecurrent and no hidden observation augmentation is introduced. Sources:
  `robot_learning/scenario/observations.py#L36-L49`,
  `robot_learning/train.py#L128-L135`,
  `robot_learning/scenario/environment.py#L136-L168`. **Discriminating
  evidence:** compare actions and hold outcomes for matched physical
  observations reached with different hold histories.
- **[Reasoned implication]** The observation contains no action or torque, so
  the policy must infer the effect of its own prior command from the next
  joint velocities and endpoint displacement. This is adequate for a
  deterministic fully observed plant only when the observed state is enough
  to predict the next state; unknown compiled inertias can still make the
  learned transition difficult to identify. **Decision relevance:** action
  smoothness and short-horizon feedback may be more reliable than open-loop
  timing. **Assumptions:** no hidden actuator state exists. **Sources:**
  `robot_learning/scenario/observations.py#L36-L49`,
  `contracts/robots/two_joint_arm.xml#L30-L33`. **Discriminating evidence:**
  repeated same-state action probes and one-step prediction error using only
  the observation.

### Behavior and failure classes

- **[Reasoned implication]** The principal failure classes are: failure to
  leave or recover from the initial singular transient; slow or torque-limited
  convergence before 500 steps; convergence to a branch with poor transient
  control; endpoint overshoot or oscillation; and hold interruption after
  apparent reach. There is no obstacle, target-contact, gravity, or payload
  failure class in the defined system. **Decision relevance:** these classes
  require different evidence and should not be pooled as one generic
  distance failure. **Assumptions:** the XML and environment are the complete
  plant and task. **Sources:** `contracts/robots/two_joint_arm.xml#L1-L33`,
  `robot_learning/scenario/environment.py#L122-L168`. **Discriminating
  evidence:** episode-level traces partitioned by first-reach step,
  minimum distance, interruption count, terminal reason, branch, radius, and
  angle.
- **[Reasoned implication]** The official horizon permits 10 seconds of
  simulated control time, while the required hold consumes 2 seconds. A
  successful policy therefore needs both a finite-time capture phase and a
  remaining stable phase; a late arrival can be physically valid yet still
  truncate before 100 samples. **Decision relevance:** convergence time is a
  separate constraint from endpoint accuracy. **Assumptions:** 500 steps and
  100 hold steps are applied as specified. **Sources:**
  `contracts/scenario.md#L9-L25`, `contracts/task_spec.py#L7-L11`.
  **Discriminating evidence:** distribution of first-reach and termination
  steps for successes and failures.

### Scientifically meaningful quantities

- **[Reasoned implication]** The quantities that expose the coupled mechanism
  are target radius and angle; joint positions, velocities, and actions;
  endpoint distance and distance margin; Jacobian conditioning; first-reach
  step; endpoint velocity at entry; maximum uninterrupted held steps; hold
  interruptions; and success stratified by geometry. Reward is a training
  signal, whereas the hold outcome and these traces describe the physical
  mechanism. **Decision relevance:** these measurements distinguish
  reachability, trajectory control, convergence, and stabilization. **Assumptions:**
  the recorded diagnostics correspond to the shared environment. **Sources:**
  `robot_learning/scenario/evaluation.py#L40-L125`,
  `robot_learning/scenario/environment.py#L134-L168`. **Discriminating
  evidence:** complete per-episode state/action traces or a measurement
  artifact containing these derived quantities.

## Unknowns

### Compiled dynamics and actuator authority

- **[Unresolved quantity]** The effective link masses, center-of-mass
  locations, joint inertias, friction defaults, and resulting coupled mass
  matrix are not stated explicitly. The exact acceleration and settling
  response under a control value are therefore unresolved before model
  introspection or a response measurement. **Decision relevance:** this can
  change the first choice between broad reaching exploration and precision
  stabilization. **Assumptions:** omitted MuJoCo defaults are consequential
  and no external parameter file overrides them. **Sources:**
  `contracts/robots/two_joint_arm.xml#L1-L33`. **Discriminating evidence:**
  compiled `MjModel` inertial fields and repeatable zero-input and
  unit-action response measurements.
- **[Unresolved quantity]** The practical torque authority at each
  configuration, especially near the straight reset and with both motors
  active, is unknown even though the control range and gear are specified.
  **Decision relevance:** insufficient authority produces late-arrival or
  unreachable-in-time failures; excessive authority produces overshoot and
  hold interruptions. **Assumptions:** actuator transmission is native MuJoCo
  motor behavior. **Sources:** `contracts/robots/two_joint_arm.xml#L30-L33`,
  `contracts/robots/two_joint_arm.xml#L12-L18`. **Discriminating evidence:**
  configuration-stratified action-to-acceleration, maximum-speed, and
  braking-distance measurements.

### Assessment sampling and task-distribution details

- **[Unresolved quantity]** The accessible environment checks tolerance after
  each 20 ms control action, while the human contract uses the word
  "continuously." It is not established from the accessible contracts alone
  whether the protected official evaluator adds any finer-grained
  within-action check. **Decision relevance:** this changes how much
  sub-control-period oscillation is scientifically relevant and how strict a
  hold-margin requirement is. **Assumptions:** the protected benchmark may
  implement semantics not visible in the research environment. **Sources:**
  `contracts/scenario.md#L9-L12`,
  `robot_learning/scenario/environment.py#L131-L159`,
  `contracts/instruments.md#L369-L385`. **Discriminating evidence:** the
  official benchmark contract or a paired test showing whether a controlled
  within-substep excursion counts as an interruption.
- **[Unresolved quantity]** The task contract establishes the official
  distribution, but pre-campaign evidence does not establish how sensitive
  success is to radius, angle, or branch. The visible baseline training
  distribution is radius 0.14 to 0.20 m, narrower than the official 0.06 to
  0.20 m range. **Decision relevance:** the first learning direction may
  need to address inner-radius generalization rather than improve average
  performance on the outer band. **Assumptions:** the visible training
  environment is the active baseline recipe and no later data augmentation
  changes it. **Sources:** `robot_learning/training/environment.py#L14-L19`,
  `contracts/scenario.md#L7-L12`. **Discriminating evidence:** held-out
  success and failure diagnostics binned by radius and angle, including the
  0.06 to 0.14 m region.

### Temporal observability and policy behavior

- **[Unresolved quantity]** It is unknown whether a feed-forward policy can
  maintain a sufficiently large invariant distance margin without explicit
  hold progress, time, or action history. The physical state is observed, but
  the task automaton state is not. **Decision relevance:** this can change
  whether the first campaign focus is policy architecture/inputs or physical
  regulation under the existing interface. **Assumptions:** the current
  11-value observation and nonrecurrent MLP are retained. **Sources:**
  `robot_learning/scenario/observations.py#L11-L49`,
  `robot_learning/train.py#L128-L135`,
  `robot_learning/scenario/environment.py#L136-L168`. **Discriminating
  evidence:** matched-state trials with different hidden hold histories and
  comparison of action variance, boundary margin, and uninterrupted hold
  length.
- **[Unresolved quantity]** It is unknown whether the learned controller
  selects one IK branch consistently, uses different branches by target
  geometry, or switches during transients. **Decision relevance:** branch
  consistency could be a useful stability mechanism, while branch switching
  could explain high-distance transients without a reachability deficit.
  **Assumptions:** both branch features are retained and branch labels are
  assigned from geometric IK rather than inferred visually. **Sources:**
  `robot_learning/scenario/observations.py#L18-L47`. **Discriminating
  evidence:** classify joint trajectories against both IK solutions and
  correlate branch choice with settling time and hold interruption.

## Decision-relevant synthesis

### Initial singularity versus reachable geometry

- **[Reasoned implication] Decision relevance:** the official targets are
  geometrically reachable, but every episode starts at a straight-arm
  Jacobian singularity; early failures can therefore be transient-control
  failures rather than workspace failures.
- **[Reasoned implication] Assumptions:** rigid planar 2R kinematics and the
  stated reset and joint limits hold.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml#L9-L20`,
  `robot_learning/scenario/environment.py#L102-L120`,
  `robot_learning/scenario/observations.py#L18-L35`.
- **[Reasoned implication] Discriminating evidence:** target-binned
  constrained-IK feasibility and initial Jacobian/endpoint response traces.

### Unknown dynamic scale and control authority

- **[Unresolved quantity] Decision relevance:** omitted compiled inertias and
  defaults may determine whether the first bottleneck is reaching within the
  horizon or braking accurately enough to hold.
- **[Unresolved quantity] Assumptions:** the XML is complete but does not
  expose all compiled dynamic quantities.
- **[Unresolved quantity] Source references:** `contracts/robots/two_joint_arm.xml#L1-L33`.
- **[Unresolved quantity] Discriminating evidence:** compiled-model
  introspection and configuration-stratified step, braking, and settling
  responses.

### Hold robustness is distinct from reach

- **[Reasoned implication] Decision relevance:** the 98% objective requires
  100 uninterrupted in-tolerance samples, so first entry or minimum distance
  cannot certify success; distance margin, residual velocity, and interruption
  rate are the decision-critical physical signals.
- **[Reasoned implication] Assumptions:** official success follows the
  stated 1 cm/2 s semantics and the shared 20 ms control timing.
- **[Reasoned implication] Source references:** `contracts/scenario.md#L9-L20`,
  `contracts/task_spec.py#L7-L11`,
  `robot_learning/scenario/environment.py#L134-L168`.
- **[Reasoned implication] Discriminating evidence:** complete hold traces
  showing entry velocity, distance margin, maximum held steps, and exits.

### Official coverage versus visible training coverage

- **[Unresolved quantity] Decision relevance:** the visible baseline trains
  only on radii 0.14-0.20 m while the official distribution includes
  0.06-0.14 m; the first campaign decision may therefore be governed by
  inner-radius generalization rather than outer-radius optimization.
- **[Unresolved quantity] Assumptions:** the visible training environment is
  used without a broader target curriculum or altered sampling.
- **[Unresolved quantity] Source references:** `robot_learning/training/environment.py#L14-L19`,
  `contracts/scenario.md#L7-L12`.
- **[Unresolved quantity] Discriminating evidence:** held-out success,
  convergence, branch, and hold-interruption statistics across radius and
  angle, with explicit coverage of 0.06-0.14 m.

### Hidden temporal task state

- **[Unresolved quantity] Decision relevance:** the policy observes physical
  state but not hold progress or time; whether robust state feedback alone
  achieves the complete hold is unknown and could determine whether the
  first direction stays within control tuning or changes the policy interface.
- **[Unresolved quantity] Assumptions:** the current 11-value observation and
  feed-forward PPO MLP remain in force.
- **[Unresolved quantity] Source references:** `robot_learning/scenario/observations.py#L11-L49`,
  `robot_learning/train.py#L128-L135`,
  `robot_learning/scenario/environment.py#L136-L168`.
- **[Unresolved quantity] Discriminating evidence:** matched physical states
  with different accumulated hold histories, comparing action responses and
  complete-hold probability.
