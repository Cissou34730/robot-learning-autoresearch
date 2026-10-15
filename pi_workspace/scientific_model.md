## Established facts

### System boundary and morphology

- **Repository fact.** The modeled plant is a serial planar arm with two hinge
  joints: `shoulder` and `elbow`, both rotating about the world z axis. The
  shoulder is attached to the base and the elbow is at the end of the
  upper-arm body. The endpoint is the `end_effector` site on the forearm.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `contracts/robots/two_joint_arm.py`.
- **Repository fact.** The upper-arm and forearm lengths used by the model and
  by the observation code are respectively `0.12 m` and `0.10 m`; their
  nominal maximum radial reach is therefore `0.22 m`. The arm plane is at
  `z=0.02 m`, because the upper-arm body is offset by `0.02 m` and the target
  is placed at the current endpoint z coordinate.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `contracts/robots/two_joint_arm.py`,
  `robot_learning/scenario/environment.py`.
- **Repository fact.** The two joint coordinates have limits of `-170` to
  `170` degrees. The XML provides capsule visual geometries, a base cylinder,
  an endpoint site, and no task obstacle or grasp/contact requirement.
  **Source refs:** `contracts/robots/two_joint_arm.xml`.
- **Reasoned implication.** With joint coordinates `q=(q1,q2)`, the endpoint
  position in its plane is
  `x = 0.12 cos(q1) + 0.10 cos(q1+q2)` and
  `y = 0.12 sin(q1) + 0.10 sin(q1+q2)`. Thus the two physical degrees of
  freedom directly control planar endpoint position, while endpoint
  orientation is not independently actuated. **Source refs:**
  `contracts/robots/two_joint_arm.xml`, `robot_learning/scenario/observations.py`.
  **Decision relevance:** endpoint-position control is the natural physical
  abstraction, while orientation control is not an available task degree of
  freedom. **Assumptions:** the site remains fixed at the declared forearm
  endpoint. **Discriminating evidence:** compare the endpoint Jacobian
  computed from q with finite differences of the simulated site position.
- **Reasoned implication.** Ignoring the small shoulder-limit edge regions, the
  joint-limited radial workspace is approximately an annulus from
  `sqrt(l1^2+l2^2+2*l1*l2*cos(170 deg)) = 0.0277 m` to `0.22 m`.
  Every official radius from `0.06 m` through `0.20 m` lies inside this
  radial range. The two inverse-kinematic elbow branches for an official
  target have `q2=+acos(c)` and `q2=-acos(c)`, where
  `c=(r^2-l1^2-l2^2)/(2*l1*l2)`; for the official radial interval these are
  approximately `+-150 deg` at `r=0.06 m` through `+-49 deg` at `r=0.20 m`,
  so both are within the elbow limit. At least one corresponding shoulder
  representation can be wrapped into the shoulder limit for each target
  angle. **Source refs:** `contracts/scenario.md`,
  `contracts/task_spec.py`, `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/observations.py`.
  **Decision relevance:** a reachability baseline can be analytic rather than
  learned, and failures can be attributed to execution when feasibility holds.
  **Assumptions:** the declared lengths and joint limits are the compiled
  kinematic values. **Discriminating evidence:** evaluate both IK solutions
  against the actual compiled joint limits for targets at radial and angular
  boundaries.
- **Reasoned implication.** The planar Jacobian loses rank when
  `sin(q2)=0`, namely at fully stretched or fully folded configurations.
  Official targets do not require the exact stretched endpoint (`r=0.22 m`)
  or the exact folded endpoint (`r=0.02 m`), but the inner-radius solutions
  are closer to the folded singular geometry than the outer-radius solutions.
  Cartesian motion can therefore require different joint velocities and
  torques for targets with similar endpoint error.
  **Source refs:** `contracts/scenario.md`,
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/observations.py`.
  **Decision relevance:** inner-radius behavior may need separate conditioning
  diagnostics even when endpoint distance is matched. **Assumptions:** the
  declared two-link planar Jacobian describes the compiled site kinematics.
  **Discriminating evidence:** report the smallest singular value of the
  Jacobian alongside qdot and endpoint velocity by target radius.

### Actuation, simulation, and timing

- **Repository fact.** Each hinge is driven by a MuJoCo `motor` actuator with
  control range `[-1,1]` and gear `5`. The environment clips the policy
  command to the same action range before writing it to `data.ctrl`.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/policy_io.py`.
- **Reasoned implication.** Under MuJoCo direct hinge-motor semantics, the
  action is a bounded signed joint torque command with nominal magnitude
  `5` in actuator torque units, not a joint-position or endpoint-position
  setpoint. A policy must consequently generate the motion and braking
  trajectory itself; there is no repository-defined low-level servo that
  converges to a commanded angle. This implication assumes the standard
  MuJoCo motor transmission and gain semantics for the locked runtime.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/policy_io.py`, `AGENTS.md`.
  **Decision relevance:** a controller or policy must learn braking and
  regulation rather than only select target joint angles. **Assumptions:**
  the locked MuJoCo motor has unit gain with the declared gear and no hidden
  position controller. **Discriminating evidence:** a unit action pulse and
  measured generalized force from the compiled model.
- **Repository fact.** The MuJoCo integration uses zero gravity and a
  `0.002 s` simulator timestep. Each policy action is held while ten
  `mj_step` calls run, giving a `0.020 s` control interval. The official
  two-second hold is therefore `100` control steps, and an episode is
  truncated after at most `500` control steps (`10 s`).
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `contracts/task_spec.py`, `robot_learning/scenario/environment.py`.
- **Repository fact.** Both joints have explicit viscous damping `0.5` and
  armature `0.01`; gravity is explicitly zero. No explicit link mass or
  inertia is written in the XML, and no task contact force is used in the
  success calculation.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
- **Reasoned implication.** During each 20 ms zero-order-held interval, the
  commanded torque, joint damping, mass matrix, and velocity determine the
  acceleration and endpoint movement. Damping opposes velocity and armature
  increases effective generalized inertia, so a command that reaches a target
  can still carry the endpoint outside the tolerance unless the policy
  anticipates braking. Zero gravity removes sag and gravity compensation, but
  does not remove inertial coupling between shoulder and elbow.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
  **Decision relevance:** reach-only behavior should not be interpreted as
  adequate without measuring braking and hold stability. **Assumptions:** the
  compiled mass matrix is positive definite and the damping/armature values
  are applied as declared. **Discriminating evidence:** compare predicted
  versus observed qdot and endpoint distance after a fixed action sequence.

### Initial state and target geometry

- **Repository fact.** Reset zeroes all joint positions and velocities, runs
  forward dynamics, samples an angle uniformly over `[-pi,pi]` and a radius
  uniformly over `[0.06,0.20] m`, and places the target at that radius and
  angle in the arm plane. The initial joint configuration is therefore
  `q=(0,0)`, with the endpoint at approximately `(0.22,0,0.02)`.
  **Source refs:** `contracts/scenario.md`, `contracts/task_spec.py`,
  `robot_learning/scenario/environment.py`.
- **Reasoned implication.** The initial endpoint is fully extended along +x,
  while the target may lie anywhere on the official annulus. The initial
  planar distance can range approximately from `0.02 m` (near `r=0.20`,
  angle zero) to `0.28 m` (near `r=0.06`, angle pi). The starting condition
  therefore combines easy near-forward cases with long, high-direction-change
  reaches. **Source refs:** `contracts/scenario.md`,
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
  **Decision relevance:** development diagnostics should include initial
  distance and direction, not just aggregate success. **Assumptions:** the
  reset state and target sampling order are unchanged. **Discriminating
  evidence:** verify the empirical initial-distance distribution from seeded
  resets.
- **Reasoned implication.** Uniform radius is not uniform area density:
  equal radial intervals receive equal probability, so probability per unit
  planar area is higher near the base. The official distribution consequently
  gives direct weight to short-radius, more-folded solutions rather than
  weighting all annular area equally. **Source refs:** `contracts/scenario.md`,
  `contracts/task_spec.py`, `robot_learning/scenario/environment.py`.
  **Decision relevance:** a uniform-area development panel would not represent
  the official weighting and could mis-rank geometry-specific behavior.
  **Assumptions:** “uniformly from 6-20 cm” is implemented by the separate
  uniform radius and angle draws. **Discriminating evidence:** histogram
  sampled radius and planar area density from seeded resets.

### Task mechanics and outcome

- **Repository fact.** Success is defined by endpoint distance no greater than
  `0.01 m` for `2 s` without interruption. The environment increments the
  held counter only after a control interval whose endpoint is within the
  band; any outside sample resets the counter. Termination occurs at
  `100` held control steps, and the official final panel contains `200`
  episodes with success required in at least `196`.
  **Source refs:** `contracts/scenario.md`, `contracts/task_spec.py`,
  `robot_learning/scenario/environment.py`.
- **Repository fact.** Distance is the 3-D Euclidean distance between the
  endpoint site and the target mocap position. The target is a mocap body,
  and the target and plane have collision disabled; the endpoint is not
  required to contact, grasp, or orient relative to the target.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
- **Reasoned implication.** Because the target and endpoint share z, the
  official success condition is effectively a 2-D positional condition with a
  1 cm radial tolerance. There is no obstacle-avoidance or force-control
  tradeoff: the physically relevant terminal behavior is endpoint convergence
  followed by low-variation stabilization. **Source refs:**
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
  **Decision relevance:** effort can focus on positional regulation rather than
  force or orientation control. **Assumptions:** target and endpoint z remain
  identical and collision flags remain disabled. **Discriminating evidence:**
  inspect z error and contact counts during representative episodes.
- **Reasoned implication.** The implementation observes the distance only at
  the 20 ms control boundaries, although MuJoCo integrates ten 2 ms steps
  between observations. Thus the code enforces uninterrupted membership at
  sampled control boundaries; it does not expose or independently test an
  intra-interval excursion. This is the operational meaning that a policy is
  actually measured against, while the contract describes the requirement as
  continuous. **Source refs:** `contracts/scenario.md`,
  `robot_learning/scenario/environment.py`.
  **Decision relevance:** sampled-pass trajectories may need a separate
  within-step safety margin before being treated as physically robust.
  **Assumptions:** no hidden evaluator samples the intermediate MuJoCo states.
  **Discriminating evidence:** compare 2 ms distances with the existing
  20 ms hold counter on successful and borderline episodes.

### Observation, action, and outcome relation

- **Repository fact.** The physical observation has 11 values: two joint
  positions, two joint velocities, the three-component endpoint-minus-target
  vector, and four wrapped joint errors to the open-elbow and folded-elbow
  inverse-kinematic solutions. It is returned as `float32`; the physical
  action mapping is currently identity. **Source refs:**
  `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/policy_io.py`.
- **Reasoned implication.** Given the link lengths and joint coordinates, the
  endpoint position is known; combining it with the endpoint-minus-target
  vector reconstructs the target position, radius, and angle (up to ordinary
  floating-point precision). The observation therefore provides target
  localization and robot velocity information without a separate target
  sensor. **Source refs:** `robot_learning/scenario/observations.py`,
  `contracts/robots/two_joint_arm.py`.
  **Decision relevance:** target encoding is unlikely to be the first
  localization bottleneck; motion and stabilization can be isolated first.
  **Assumptions:** endpoint kinematics use the same lengths as the observation
  helper and numerical precision is adequate. **Discriminating evidence:**
  reconstruct target xy from observations and compare it with `mocap_pos`.
- **Repository fact.** The observation does not include held-step count,
  episode step count, previous action, actuator force, acceleration, mass
  properties, contact state, or a direct success flag. The evaluator keeps
  held-step state internally and returns it in `info`, not in the policy
  observation. **Source refs:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/evaluation.py`.
- **Reasoned implication.** The robot state needed for instantaneous kinematics
  and dynamics is largely observed, but the task automaton is not: two
  identical physical states can have different success prospects depending on
  how many consecutive in-band samples have already occurred. A memoryless
  policy can still stabilize the endpoint, but a recurrent policy or
  observation-side history could represent hold progress explicitly. This is
  an observability consequence, not evidence that recurrence is necessary.
  **Source refs:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`,
  `contracts/policy_runtime.py`.
  **Decision relevance:** memory or a hold-progress feature becomes relevant
  only if identical instantaneous states show history-dependent outcomes.
  **Assumptions:** no hidden policy state encodes the counter. **Discriminating
  evidence:** replay matched physical observations with different held-step
  histories and compare continuation success.
- **Repository fact.** Training wraps observations with `VecNormalize` and the
  exported runtime preserves the normalizer and policy I/O alongside the
  weights; evaluation uses the preserved runtime rather than substituting
  current observation code. **Source refs:** `robot_learning/train.py`,
  `robot_learning/training/checkpoint.py`,
  `contracts/policy_runtime.py`.

### Reward and measurable behavior

- **Repository fact.** The scalar training reward combines distance progress,
  exponential closeness, linear hold-progress potential, an action-square
  cost, a small outside-band penalty after a hold interruption, and a
  completion bonus. Exiting the band resets held steps; the configured
  hold-exit forfeiture is zero. These terms are not the official success
  definition. **Source refs:** `robot_learning/training/reward.py`,
  `robot_learning/scenario/environment.py`,
  `contracts/scenario.md`.
- **Reasoned implication.** The reward encourages approach and eventual hold
  completion but can value transient progress differently from binary episode
  success. Scientific assessment must therefore separate learning signal from
  task outcome and retain trajectory quantities such as first reach, minimum
  distance, maximum held streak, interruptions, and final distance.
  **Source refs:** `robot_learning/training/reward.py`,
  `robot_learning/scenario/evaluation.py`.
  **Decision relevance:** reward changes should not be accepted as task
  improvements without hold-complete episode outcomes. **Assumptions:** the
  scalar reward is the signal seen by the learning algorithm and `info` is not
  used by it. **Discriminating evidence:** paired policy evaluations with
  identical official seeds and the same trajectory diagnostics.

## Physical consequences

### Reachability and inverse-kinematic choice

- **Reasoned implication.** Official targets are geometrically reachable in
  both elbow-open and elbow-folded branches under the stated joint ranges.
  A failure to enter the tolerance is therefore not expected to be caused by
  an unreachable official target; it is more plausibly a branch-selection,
  trajectory, timing, actuation, or stabilization failure. This conclusion
  assumes the compiled model preserves the declared link lengths and joint
  limits. **Decision relevance:** it changes whether early work should target
  kinematic coverage or controller execution. **Assumptions:** XML geometry
  and joint coordinates are authoritative and no hidden obstacle exists.
  **Source refs:** `contracts/scenario.md`,
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/observations.py`.
  **Discriminating evidence:** compare target-wise success and first-reach
  rates with analytic IK feasibility and record which branch the trajectory
  approaches; a failure on a feasible target weakens a geometric-impossibility
  explanation.
- **Reasoned implication.** The two branches are physically distinct joint
  trajectories even when they end at the same endpoint. They can have
  different distance from joint limits, Jacobian conditioning, required
  velocity, and transient torque demand. The four branch-error features make
  branch choice available to a policy but do not force one branch.
  **Decision relevance:** branch-conditioned diagnostics can distinguish a
  representation or exploration problem from an actuator/stability problem.
  **Assumptions:** qpos and the target-relative vector are accurate enough for
  the branch formulas to be useful. **Source refs:**
  `robot_learning/scenario/observations.py`,
  `contracts/robots/two_joint_arm.xml`.
  **Discriminating evidence:** compare successful and failed episodes by
  signed elbow configuration, minimum distance to each branch, and branch
  switching near the target.

### Reaching, convergence, and stabilization are coupled

- **Reasoned implication.** Reaching and holding are not separable binary
  subproblems. A fast reach changes qvel and therefore the braking distance;
  braking changes endpoint error; a small endpoint band converts residual
  oscillation into repeated hold resets. The same torque authority and
  unknown mass matrix govern all three phases. **Decision relevance:** a
  policy that maximizes first entry may underperform one that arrives with
  low velocity and a controllable posture. **Assumptions:** direct motor
  commands are the only control input and there is no hidden position servo.
  **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/evaluation.py`.
  **Discriminating evidence:** jointly inspect first-reach step, endpoint
  velocity at first reach, minimum distance, maximum held streak, and
  interruption count; high first-reach rates with short streaks support a
  stabilization bottleneck.
- **Reasoned implication.** At a fixed 1 cm tolerance, allowable endpoint
  motion is small relative to the 20 ms action interval. The policy must
  regulate a moving, coupled two-joint state rather than merely choose an IK
  pose. **Decision relevance:** this determines whether a reach-only baseline
  is scientifically informative or structurally insufficient. **Assumptions:**
  the tolerance is applied to the endpoint site exactly as implemented.
  **Source refs:** `contracts/scenario.md`, `contracts/task_spec.py`,
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** measure endpoint velocity and distance
  oscillation during the hold window, not only terminal success.

### Control authority and dynamic uncertainty

- **Reasoned implication.** With bounded motor command, control authority is
  finite and configuration-dependent: the same joint torque produces different
  Cartesian effects through the Jacobian, while shoulder and elbow torques
  interact through the mass matrix. Zero gravity simplifies the equilibrium
  problem, but does not guarantee fast or monotonic convergence.
  **Decision relevance:** it changes whether action scaling, braking, or
  dynamics-aware control should be considered before altering task geometry.
  **Assumptions:** standard MuJoCo actuator semantics and the compiled
  geometry-derived inertias apply. **Source refs:**
  `contracts/robots/two_joint_arm.xml`, `AGENTS.md`.
  **Discriminating evidence:** apply controlled action pulses at several
  postures and identify qdot, qacc, and endpoint response; compare response
  to the nominal `gear=5` prediction.
- **Reasoned implication.** The omitted explicit inertial parameters are a
  model-structure risk rather than a claim that the simulator is stochastic.
  If MuJoCo's inferred inertias make the arm highly responsive, overshoot and
  hold regulation dominate; if they make it sluggish, action authority and
  horizon dominate. **Decision relevance:** the first controller or learning
  recipe can differ materially between these regimes. **Assumptions:** no
  unrecorded runtime XML/default changes. **Source refs:**
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`, `AGENTS.md`.
  **Discriminating evidence:** inspect the compiled `MjModel` inertial and
  actuator fields through an authorized simulator measurement, then validate
  predicted versus observed short-horizon state transitions.

### Observable state and task-memory constraints

- **Reasoned implication.** Target location is effectively observable, and
  qpos/qvel make the instantaneous plant state close to fully observed, but
  hold progress is hidden. The environment is thus Markov for the simulator
  state plus its success counter, not necessarily Markov for the policy's
  11-value input. **Decision relevance:** this can change the priority of
  feed-forward IK, recurrent memory, or explicit history features.
  **Assumptions:** policy I/O remains the current 11-value mapping and no
  hidden actuator state is introduced. **Source refs:**
  `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/policy_io.py`.
  **Discriminating evidence:** test whether policies with identical current
  observations but different hold histories receive different continuation
  outcomes; compare a stateless controller with one supplied hold-history
  information.
- **Reasoned implication.** Since action history is absent and actions are
  directly applied, any needed anticipation must be inferred from qvel and
  current geometry rather than from an actuator command memory. **Decision
  relevance:** systematic action lag or oscillation would point toward
  dynamics/observation limitations rather than target localization.
  **Assumptions:** the current `physical_action` identity mapping is retained.
  **Source refs:** `robot_learning/scenario/policy_io.py`,
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** compare current action, qvel, endpoint velocity,
  and subsequent distance over consecutive control intervals.

### Behavior and failure classes

- **Reasoned implication.** The coupled system supports at least five
  scientifically distinct outcome classes: (1) no useful approach, (2)
  approach to the wrong or poorly conditioned IK branch, (3) entry into the
  band followed by overshoot, (4) repeated intermittent in-band excursions,
  and (5) low-velocity stabilization for the full hold. A sixth class is
  timeout after partial progress. **Decision relevance:** pooled success alone
  cannot identify which mechanism a change affected. **Assumptions:** the
  evaluator diagnostics are retained as factual trajectory summaries.
  **Source refs:** `robot_learning/scenario/evaluation.py`,
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** use `first_reach_step`, `max_held_steps`,
  `hold_interruptions`, `min_distance_cm`, `final_distance_cm`, and target
  radius/angle jointly.
- **Reasoned implication.** No official target is expected to be blocked by an
  obstacle or contact interaction, so collision avoidance and force regulation
  are not explanatory failure classes for this task. A failure attributed to
  “contact” would require evidence of an unrecognized simulator interaction
  or a source-definition change. **Decision relevance:** it prevents spending
  early campaign effort on an absent physical mechanism. **Assumptions:**
  collision settings and task XML are the executed definitions. **Source refs:**
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** inspect geom contact flags and contact counts
  during a representative trajectory if contact is suspected.

### Scientifically meaningful physical quantities

- **Reasoned implication.** The most informative trajectory quantities are:
  target radius and angle; q and qdot; endpoint-target distance and its
  derivative; endpoint Cartesian velocity; action/torque; Jacobian
  conditioning; first entry time; continuous sampled hold streak; hold
  interruptions; minimum and final distance; and whether termination was
  success or timeout. Together they separate geometry, reach dynamics,
  convergence, and stabilization. **Decision relevance:** these quantities
  define what a first diagnostic measurement must preserve even if reward or
  policy architecture changes. **Assumptions:** quantities not currently
  emitted can be computed from the same simulator state without changing the
  official task. **Source refs:** `robot_learning/scenario/evaluation.py`,
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/observations.py`.
  **Discriminating evidence:** a trajectory artifact containing these signals
  at every control step, with simulator state available at the 2 ms
  integration resolution when testing the continuity question.

## Unknowns

### Compiled inertial and actuator quantities

- **Unresolved quantity.** The repository does not state the compiled masses,
  centers of mass, inertia tensors, actuator force limits after compilation,
  or the exact mass-matrix condition across the workspace.
  **Decision relevance:** these values can change the choice between direct
  policy learning, model-based control, action scaling, and stabilization-first
  diagnostics. **Assumptions:** the XML's omitted inertial fields are filled by
  MuJoCo defaults consistently in the locked runtime. **Source refs:**
  `contracts/robots/two_joint_arm.xml`, `AGENTS.md`.
  **Discriminating evidence:** an authorized measurement that records
  `MjModel` inertial, actuator, and mass-matrix quantities and validates them
  against short action-pulse responses.

### Intra-interval hold continuity

- **Unresolved quantity.** The success counter is evaluated once per 20 ms
  control interval, but the contract's word “continuously” could be read as
  requiring the endpoint to stay within 1 cm at every 2 ms simulator step.
  The current evaluator does not record the ten intermediate distances.
  **Decision relevance:** if meaningful within-interval exits occur, a policy
  can pass the implemented sampled criterion while violating physical
  continuity, changing both diagnostic interpretation and the appropriate
  stabilization margin. **Assumptions:** the official implementation remains
  the authority for measured success while the contract remains the scientific
  intent. **Source refs:** `contracts/scenario.md`,
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** compare every 2 ms endpoint distance with the
  existing 20 ms samples during successful and near-successful holds.

### Effective dynamic response and settling envelope

- **Unresolved quantity.** No source definition establishes the maximum
  endpoint speed, stopping distance, settling time, or steady-state
  oscillation under bounded actions at each target geometry.
  **Decision relevance:** these determine whether 500 steps is generous, whether
  a two-second hold is dynamically difficult, and whether failures are mostly
  timing-limited or representation-limited. **Assumptions:** the model is
  deterministic for a fixed seed and action sequence, with no unmodeled
  disturbances. **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `contracts/task_spec.py`, `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** controlled rollouts over radii, angles, and
  both IK branches reporting qdot, endpoint velocity, distance, and recovery
  after a bounded torque pulse.

### Distributional difficulty by geometry

- **Unresolved quantity.** The definitions specify the target distribution but
  do not establish how success probability varies with radius, angle,
  branch, or proximity to joint limits. **Decision relevance:** a first
  campaign may prioritize uniform geometric coverage, hard-case oversampling
  for development, or stabilization independent of target geometry.
  **Assumptions:** development diagnostics are not substituted for the
  official 200-episode assessment and do not change its distribution.
  **Source refs:** `contracts/scenario.md`, `contracts/task_spec.py`,
  `robot_learning/training/environment.py`,
  `robot_learning/scenario/evaluation.py`.
  **Discriminating evidence:** stratified development panels reporting
  success and failure class by target radius, angle, and realized IK branch;
  official assessment remains the final distributional evidence.

### Observation sufficiency for robust hold

- **Unresolved quantity.** It is not established whether the current
  qpos/qvel, target-relative vector, and branch errors are sufficient for a
  policy to infer the braking and hold phase at the required reliability, or
  whether omitted hold progress and action history materially limit control.
  **Decision relevance:** this can change the first intervention from learning
  recipe changes to observation or policy-memory changes. **Assumptions:** the
  physical task and protected evaluation semantics are unchanged. **Source
  refs:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`,
  `contracts/policy_runtime.py`.
  **Discriminating evidence:** paired evaluations of stateless versus
  history-aware policies, with matched training budget and diagnostics of
  entry velocity and interruption count.

### Sim-to-contract semantic scope

- **Unresolved quantity.** The source comments describe the current environment
  as shared training/evaluation mechanics, while training intentionally uses
  a narrower radius range `(0.14,0.20)` than the official `(0.06,0.20)`.
  The physical consequence of that curriculum gap for learned generalization
  is not established. **Decision relevance:** it can change whether the first
  campaign keeps the baseline training distribution or expands it toward the
  official inner radii. **Assumptions:** the evaluation runtime and official
  contract remain fixed, and only training construction is changed.
  **Source refs:** `robot_learning/training/environment.py`,
  `robot_learning/scenario/environment.py`, `contracts/scenario.md`,
  `contracts/task_spec.py`.
  **Discriminating evidence:** matched-seed evaluations stratified by radius,
  plus training-domain coverage and failure classes, without pooling those
  measurements into the official result.

## Decision-relevant synthesis

### Official targets are feasible, so execution is the first physical bottleneck

- **Decision relevance:** The declared annular target set is inside the
  joint-limited workspace and has two analytic IK branches; early decisions
  should distinguish motion execution from geometric impossibility rather
  than assume the task requires unreachable poses.
- **Assumptions:** the XML lengths, limits, and MuJoCo compilation are the
  executed definitions, and at least one wrapped shoulder branch is valid
  across the full angular range.
- **Source refs:** `contracts/scenario.md`,
  `contracts/robots/two_joint_arm.xml`,
  `contracts/task_spec.py`, `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** analytic feasibility joined to target-stratified
  first-reach and success diagnostics, including realized elbow branch.

### Hold reliability is a stabilization problem coupled to reaching

- **Decision relevance:** A policy can enter the 1 cm band yet fail the actual
  objective through residual velocity, overshoot, or intermittent exits; the
  first campaign decisions should therefore treat first reach and complete
  hold as separate physical mechanisms without treating them as independent.
- **Assumptions:** bounded direct motor control, 20 ms action holding, and the
  current 100-consecutive-step success counter remain fixed.
- **Source refs:** `contracts/scenario.md`,
  `contracts/task_spec.py`, `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** first-reach step, endpoint velocity at entry,
  max held streak, interruption count, final distance, and 2 ms within-step
  distances for near-successes.

### Inertial parameters are the highest-impact physical unknown

- **Decision relevance:** The XML fixes damping, armature, timestep, and
  nominal motor gearing but omits explicit link inertias. The resulting
  acceleration and stopping envelope could change whether action authority,
  braking, or policy representation is the limiting factor.
- **Assumptions:** MuJoCo's locked runtime fills omitted inertial quantities
  from defaults and geometry exactly as executed; direct motor semantics apply.
- **Source refs:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`, `AGENTS.md`.
- **Discriminating evidence:** compiled `MjModel` inertial/actuator inspection
  plus controlled torque-pulse system identification across representative
  postures.

### The current observation is geometrically rich but omits task memory

- **Decision relevance:** Target position, qpos, and qvel are available or
  reconstructable, while held-step count, action history, and acceleration are
  absent. Whether this limits 98% reliability determines whether early work
  should focus on the learning recipe or on memory/observation design.
- **Assumptions:** the current `reach_observation` and identity action mapping
  are the policy contract, and no hidden actuator state is added.
- **Source refs:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/policy_io.py`,
  `robot_learning/scenario/environment.py`,
  `contracts/policy_runtime.py`.
- **Discriminating evidence:** matched stateless/history-aware comparisons with
  identical target panels, reporting hold interruptions and entry velocities,
  not only pooled success.

### Training does not cover the full official radial range

- **Decision relevance:** Baseline training samples radii `0.14-0.20 m`,
  whereas official evaluation includes `0.06-0.20 m`; inner-radius,
  near-folded configurations may be an immediate generalization gap.
- **Assumptions:** the training environment remains the baseline source and
  official evaluation remains the fixed distribution; development panels stay
  distinct from the official panel.
- **Source refs:** `robot_learning/training/environment.py`,
  `contracts/scenario.md`, `contracts/task_spec.py`,
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** radius-stratified development results and
  branch/conditioning diagnostics on the inner `0.06-0.14 m` interval, followed
  by the fixed 200-episode official assessment for the final claim.
