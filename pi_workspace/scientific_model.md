## Established facts

### Scope, notation, and source authority

- **[Repository fact]** This model treats the human-authored task contract, the
  robot MJCF, the immutable task constants, and the scenario-owned reset,
  observation, and stepping code as the pre-campaign definition of the
  embodied system. It uses no campaign outcome as evidence. Source references:
  `contracts/scenario.md` (official task and assessment), `contracts/task_spec.py`
  (task constants), `contracts/robots/two_joint_arm.xml` (MuJoCo model),
  `contracts/robots/two_joint_arm.py` (length constants), and
  `robot_learning/scenario/environment.py` (available scenario mechanics).
- **[Repository fact]** The symbols below use SI lengths in meters, time in
  seconds, joint angles in radians in the Python kinematics, and degrees where
  the MJCF joint ranges are written. The shoulder and elbow coordinates are
  denoted by `q_s` and `q_e`.

### Official task and assessment

- **[Repository fact]** An episode samples a target at a radius from 0.06 m to
  0.20 m and over the full angular range. The end-effector position must be no
  more than 0.01 m from the target for an uninterrupted 2.0 s hold. The
  scenario contract identifies this as 100 consecutive control steps under the
  current timing. Source: `contracts/scenario.md` (Official task and Success
  criterion), `contracts/task_spec.py`
  (`TARGET_RADIUS_RANGE`, `SUCCESS_THRESHOLD`, `HOLD_SECONDS`, `FRAME_SKIP`).
- **[Repository fact]** The official final assessment uses one frozen policy on
  200 fixed episodes, each with at most 500 control steps, and requires at least
  196 successes (98%). Development panels are separate from that assessment.
  Source: `contracts/scenario.md` (Official final assessment).
- **[Repository fact]** The available scenario sampler draws the angle and the
  radius independently with `uniform(-pi, pi)` and `uniform(0.06, 0.20)`,
  respectively, and places the target at the end-effector's planar height.
  Source: `robot_learning/scenario/environment.py`,
  `TwoJointArmReachEnv._sample_target_position`.

### Morphology and kinematic state

- **[Repository fact]** The robot is fixed-base and has exactly two actuated
  hinge joints. Both joint axes are the world/body z axis, so the moving
  kinematic chain is planar. The base has no free joint; the target is a
  mocap body and is not a robot degree of freedom. Source:
  `contracts/robots/two_joint_arm.xml`, bodies `base`, `upper_arm`, `forearm`,
  and `target`.
- **[Repository fact]** The upper-arm centerline length is 0.12 m and the
  forearm centerline length is 0.10 m. The end-effector site is at the distal
  forearm endpoint. The upper-arm and forearm capsule radii are 0.015 m and
  0.012 m; the site has size 0.008 m. Source:
  `contracts/robots/two_joint_arm.xml`, `geom` and `site` elements, and
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`).
- **[Repository fact]** The shoulder and elbow ranges are each -170 to +170
  degrees. The upper-arm body is offset 0.02 m above the world origin, and the
  target is reset into that same plane. Source:
  `contracts/robots/two_joint_arm.xml` and
  `robot_learning/scenario/environment.py`, `_sample_target_position`.
- **[Repository fact]** The XML target sphere has radius 0.012 m but has
  `contype="0"` and `conaffinity="0"`. The plane is also non-colliding. The
  task distance is computed between the end-effector site position and the
  mocap target position, not between their rendered surfaces. Source:
  `contracts/robots/two_joint_arm.xml` and
  `robot_learning/scenario/environment.py`, `_distance_to_target`.

### Simulator, actuation, and timing

- **[Repository fact]** MuJoCo is configured with zero gravity and a 0.002 s
  simulation timestep. Both joints have 0.5 joint damping and 0.01 armature.
  The moving geoms do not specify explicit masses, inertias, or densities in
  the XML. Source: `contracts/robots/two_joint_arm.xml`, `option`, `joint`,
  and `geom` elements.
- **[Repository fact]** Each actuator is a MuJoCo `motor` attached directly to
  one joint, with `ctrlrange="-1 1"` and `gear="5"`. The environment action
  space has two values in [-1, 1], applies the policy action identity mapping,
  clips it to that range, writes it to `data.ctrl`, and then advances ten
  MuJoCo steps. Source: `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/policy_io.py` (`physical_action`), and
  `robot_learning/scenario/environment.py`, `TwoJointArmReachEnv.step`.
- **[Repository fact]** The resulting control interval is
  `10 * 0.002 = 0.020` s, or 50 policy actions per second. The available
  environment computes `round(2.0 / 0.020) = 100` required held control
  steps and permits at most 500 control steps, or 10 s. Source:
  `robot_learning/scenario/environment.py`, constructor and `step`, and
  `contracts/task_spec.py`.

### Reset, interaction, and success state

- **[Repository fact]** On reset, the available environment resets MuJoCo data,
  explicitly sets both joint positions and velocities to zero, forwards the
  model, samples a new static target, and forwards again. Thus the arm starts
  straight along +x at `q_s = q_e = 0`, at rest; the XML target position is
  overwritten by the sampled target. Source:
  `robot_learning/scenario/environment.py`, `TwoJointArmReachEnv.reset`.
- **[Repository fact]** At each available environment step, the action remains
  in `data.ctrl` for all ten internal steps. The distance is evaluated after
  those steps. A sample at or below 0.01 m increments `held_steps`; one sample
  above it resets the counter to zero. The available environment terminates
  when the counter reaches 100 and truncates at 500 steps. Source:
  `robot_learning/scenario/environment.py`, `TwoJointArmReachEnv.step`.
- **[Repository fact]** The reward implementation contains progress, closeness,
  action-cost, and hold-shaping terms, but the task outcome is the hold
  predicate, not the reward total. Source:
  `robot_learning/scenario/environment.py`, `step`, and
  `robot_learning/training/reward.py`, `reach_reward`.
- **[Repository fact]** The available scenario environment is not by itself the
  protected final evaluator: its own module states that benchmark constants are
  defaults and that the human-defined task is enforced by the protected
  benchmark. This distinction matters wherever endpoint sampling or defaults
  are discussed below. Source:
  `robot_learning/scenario/environment.py` module documentation and
  `contracts/scenario.md` (Immutable task boundary).

### Sensing and policy interface

- **[Repository fact]** The raw observation has 11 values: two joint positions,
  two joint velocities, the 3-D vector from target to end effector, and four
  wrapped angular errors to the two nominal inverse-kinematic branches
  (shoulder/elbow for the open and folded solutions). Source:
  `robot_learning/scenario/observations.py`, `OBSERVATION_SIZE` and
  `reach_observation`.
- **[Repository fact]** The observation is deterministic and has no explicitly
  modelled sensor noise. It does not include the action, actuator force,
  acceleration, contact force, target velocity, target radius or angle as
  separate fields, hold count, previous distance, or episode time. Source:
  `robot_learning/scenario/observations.py` and
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** The policy action mapping is currently the identity.
  Runtime prediction is deterministic, and a candidate may carry an optional
  observation normalizer and recurrent prediction state bound to its saved
  runtime. Sources: `robot_learning/scenario/policy_io.py`,
  `contracts/policy_runtime.py` (`PolicyRuntime.predict`, `reset`), and
  `robot_learning/train.py`.

### Training versus official exposure

- **[Repository fact]** The current training environment constructor samples
  target radii only from 0.14 m to 0.20 m, whereas the official task range is
  0.06 m to 0.20 m. This is a changeable training choice, not a change to the
  official task boundary. Source: `robot_learning/training/environment.py`,
  `TRAINING_TARGET_RADIUS_RANGE`, and `contracts/task_spec.py`.

## Physical consequences

### Planar 2R workspace and inverse kinematics

- **[Reasoned implication]** With `l_1 = 0.12` m and `l_2 = 0.10` m, the
  ideal point-site kinematics are
  `p_E = (l_1 cos(q_s) + l_2 cos(q_s+q_e),
  l_1 sin(q_s) + l_2 sin(q_s+q_e), 0.02)`. The unconstrained radial
  workspace is the annulus from `|l_1-l_2| = 0.02` m to
  `l_1+l_2 = 0.22` m. For a target radius `r` in the official interval,
  `cos(q_e) = (r^2-l_1^2-l_2^2)/(2 l_1 l_2)` gives two branches
  `q_e = +/- acos(cos(q_e))`, with the shoulder angle supplied by the
  corresponding `atan2` expression in `reach_observation`.
- **[Reasoned implication] Decision relevance:** The official annulus is inside
  the nominal radial workspace, and the two inverse-kinematic branches give at
  least one shoulder configuration within the declared joint limits for every
  official angle. The first research choice therefore need not solve a
  geometric impossibility; it can instead decide how to select, track, or
  learn an admissible branch and how to handle the different paths to it.
- **[Reasoned implication] Assumptions:** This conclusion uses point-site
  kinematics, the stated joint-angle convention, and the absence of an
  obstructing self-contact or other constraint. It does not infer that every
  dynamically commanded path is feasible or that both branches are equally
  easy to stabilize.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml`,
  `contracts/robots/two_joint_arm.py`, and
  `robot_learning/scenario/observations.py`, `shoulder_for_elbow`.
- **[Reasoned implication] Discriminating evidence:** A state trace containing
  `q_s`, `q_e`, target `(r, theta)`, joint-limit margins, and the sign of the
  elbow branch would show whether successful episodes use both branches and
  whether failures cluster near one branch or a workspace boundary.

### Initial singularity and geometry-dependent reach

- **[Reasoned implication]** The reset state is fully extended at
  `p_E = (0.22, 0, 0.02)`. The planar Jacobian is
  `J = [[-l_1 sin(q_s)-l_2 sin(q_s+q_e), -l_2 sin(q_s+q_e)],
  [l_1 cos(q_s)+l_2 cos(q_s+q_e), l_2 cos(q_s+q_e)]]`, with
  `det(J) = l_1 l_2 sin(q_e)`. At reset `q_e=0`, so `J` has rank one:
  first-order end-effector motion is tangential, while radial motion requires
  first bending the chain. The initial target distance ranges from 0.02 m
  to 0.42 m over the official distribution.
- **[Reasoned implication] Decision relevance:** The same action authority can
  produce different first-reach times by target angle and radius. A policy or
  controller that assumes a nonsingular Cartesian inverse at reset can spend
  time or torque escaping the singular configuration, leaving less of the
  10 s horizon for the required hold.
- **[Reasoned implication] Assumptions:** The implication assumes the reset is
  always the stated zero configuration and that no unmodelled gravity or
  initial velocity changes the escape. It concerns the point-site Jacobian,
  not a claim that the target is unreachable.
- **[Reasoned implication] Source references:** `robot_learning/scenario/environment.py`,
  `TwoJointArmReachEnv.reset` and `_sample_target_position`;
  `contracts/robots/two_joint_arm.xml`; and the link lengths in
  `contracts/robots/two_joint_arm.py`.
- **[Reasoned implication] Discriminating evidence:** First-reach time,
  minimum singular value of `J`, initial joint acceleration, and target
  angle/radius stratification would distinguish singularity-limited reach from
  ordinary torque or policy errors.

### Direct torque, sampled control, and dynamic authority

- **[Reasoned implication]** In the ideal MuJoCo motor mapping, a clipped
  command `u_i` produces a joint generalized torque approximately
  `tau_i = 5 u_i`, subject to joint-limit and simulator constraint forces.
  The command is zero-order held for 0.020 s, so the policy does not directly
  control the 0.002 s integration steps. The articulated dynamics have the
  form `M(q) qdd + C(q,qdot) qdot + D qdot + tau_limits = 5 u`,
  with no gravity term; `D` includes the declared 0.5 damping and `M` includes
  the armature and geometry-derived link inertias.
- **[Reasoned implication] Decision relevance:** Reach time, overshoot, and
  hold stability depend on the ratio of available torque to the actual
  configuration-dependent inertia, not on the action range alone. This can
  change whether the first campaign should favor a reactive policy, a
  trajectory/setpoint structure, action regularization, or explicit
  dynamics-aware diagnostics.
- **[Reasoned implication] Assumptions:** The torque expression assumes the
  standard direct MuJoCo `motor` semantics for the locked simulator version
  and no hidden actuator activation state. The numerical response remains
  conditional on derived masses, inertias, solver settings, and active
  constraints not specified in the XML.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml`,
  `contracts/task_spec.py`, and `robot_learning/scenario/environment.py`,
  `TwoJointArmReachEnv.__init__` and `step`.
- **[Reasoned implication] Discriminating evidence:** The loaded model's
  generalized actuator torque, articulated inertia, joint velocities, and
  response to known saturated and unsaturated commands would separate
  torque-limited behavior from inertia-, damping-, or solver-limited behavior.

### Reach, convergence, and uninterrupted stabilization are different mechanisms

- **[Reasoned implication]** A first entry into the 0.01 m ball does not
  establish success. The controller must reduce endpoint velocity and keep the
  site inside the ball for 100 consecutive control observations; a single
  out-of-band observation resets the available hold counter. With a static
  target and no gravity, an admissible exact inverse-kinematic configuration
  at rest is an equilibrium in the ideal model, and damping can dissipate
  motion without a gravity-compensation torque.
- **[Reasoned implication] Decision relevance:** A policy that reaches quickly
  but oscillates across the boundary is a different failure class from one
  that cannot reach. The first useful behavioral distinction is therefore
  convergence and stabilization after first reach, not only minimum distance
  or eventual proximity. The hold requirement also makes a branch switch or
  late correction potentially fatal even when the endpoint remains geometrically
  reachable.
- **[Reasoned implication] Assumptions:** This separation assumes the protected
  evaluator honors the contract's uninterrupted-hold meaning and that target
  motion, contact, and disturbances are absent as defined. The available
  scenario implementation samples the hold predicate only at control-step
  endpoints, which may not detect an excursion between endpoints.
- **[Reasoned implication] Source references:** `contracts/scenario.md`,
  `contracts/task_spec.py`, and `robot_learning/scenario/environment.py`,
  `TwoJointArmReachEnv.step`.
- **[Reasoned implication] Discriminating evidence:** The distance and
  endpoint-velocity trace at every control boundary, the longest uninterrupted
  in-tolerance run, the count and timing of interruptions, and any
  internal-step distance trace would separate reach, overshoot, slow settling,
  and evaluator-sampling effects.

### The task is endpoint regulation, not grasping or force closure

- **[Reasoned implication]** Because the target is a non-colliding mocap sphere
  and success uses only the 3-D distance between the target center and the
  end-effector site, the physical task imposes no target contact, grasp force,
  end-effector orientation, or load-bearing requirement. The target and arm
  share a fixed plane, so the 3-D distance reduces to planar position error
  under the stated model.
- **[Reasoned implication] Decision relevance:** Any admissible path and either
  inverse-kinematic endpoint can satisfy the task if the site remains in the
  tolerance ball. A force sensor, collision strategy, or orientation controller
  is not justified by the task definition; position error, velocity, and
  stabilization are the central mechanisms.
- **[Reasoned implication] Assumptions:** This conclusion applies to the
  protected task contract, not to visual appearance of the target sphere or
  to any future task alteration. It also assumes no active self-contact changes
  the reachable set.
- **[Reasoned implication] Source references:** `contracts/scenario.md`,
  `contracts/robots/two_joint_arm.xml`, and
  `robot_learning/scenario/environment.py`, `_distance_to_target` and
  `_sample_target_position`.
- **[Reasoned implication] Discriminating evidence:** Successful traces with
  different final joint branches but the same site distance, together with
  zero target-contact forces, would support endpoint-only success; any
  evaluator dependence on orientation or contact would contradict this model
  and require revising the task interpretation.

### Observation exposes physical geometry but not task progress

- **[Reasoned implication]** Given known link lengths, joint positions determine
  `p_E`, and the observed end-effector-minus-target vector then determines the
  target position. Thus radius, angle, distance, Jacobian, and both nominal IK
  errors are derivable from the raw observation even though some are not
  separate fields. The four IK errors provide an explicit representation of
  the two branch hypotheses.
- **[Reasoned implication]** The raw physical state relevant to deterministic
  two-joint mechanics is close to observable through `q`, `qdot`, and target
  error. However, `held_steps`, the previous in-tolerance history, and episode
  time are absent. Two visits with the same physical observation can have
  different success consequences because one may be at held step 0 and the
  other at held step 99.
- **[Reasoned implication] Decision relevance:** A memoryless policy can still
  succeed by making the physical equilibrium robust, but it cannot condition
  on hidden hold progress or elapsed horizon. A recurrent state, an explicit
  stabilization behavior, or a training signal that produces persistent
  equilibria can therefore change the route to 98% success. Candidate-specific
  normalization changes numerical conditioning without adding physical
  information.
- **[Reasoned implication] Assumptions:** The near-Markov statement assumes no
  active hidden actuator, contact, or sensor state beyond the fields in the
  observation. It does not assume that the policy runtime actually uses
  recurrence or that normalization is present.
- **[Reasoned implication] Source references:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`, and
  `contracts/policy_runtime.py`, `PolicyRuntime.predict` and `reset`.
- **[Reasoned implication] Discriminating evidence:** Reconstructing target
  geometry from observation, comparing identical physical states with
  different hold histories, and inspecting the saved runtime's normalizer and
  recurrent-state behavior would distinguish physical partial observability
  from task-automaton partial observability.

### Branch choice changes the trajectory even when the endpoint is the same

- **[Reasoned implication]** For non-singular targets, the open and folded
  solutions have opposite elbow signs and generally different shoulder angles,
  Jacobians, joint-limit margins, and torque-to-endpoint mappings. They are
  discrete alternatives rather than continuous redundancy. A controller that
  moves between them while preserving the same target generally must leave the
  target neighborhood, so a branch change during a hold can interrupt success.
- **[Reasoned implication] Decision relevance:** Branch selection can alter
  reach time, saturation, self-clearance, and hold robustness without changing
  the final distance. A method that is good on one branch is not established
  as geometry-robust until branch use and branch-conditioned success are known.
- **[Reasoned implication] Assumptions:** The alternatives are based on the
  two-link point kinematics and official targets away from the radial
  singular boundaries. Self-contact or joint-limit constraints could remove a
  nominal branch.
- **[Reasoned implication] Source references:** `robot_learning/scenario/observations.py`,
  `shoulder_for_elbow`, `contracts/robots/two_joint_arm.xml`, and
  `robot_learning/scenario/environment.py`.
- **[Reasoned implication] Discriminating evidence:** Classifying each
  trajectory by elbow sign and nearest IK branch, then comparing first reach,
  saturation, joint-limit margin, and uninterrupted hold length, would show
  whether branch selection is causal for the observed behavior or merely
  correlated with target geometry.

### The default training exposure does not cover the full official radial range

- **[Reasoned implication]** If the current training constructor is used
  unchanged, radii from 0.06 m to 0.14 m are absent during training even
  though they are part of the official distribution. The available sampler's
  independent uniform radius also weights Cartesian area non-uniformly: an
  equal radial interval contains more probability near the base than an equal
  area annulus.
- **[Reasoned implication] Decision relevance:** A high aggregate development
  score under the current training exposure could coexist with systematic
  official failures on inner targets. The first campaign comparison must
  distinguish capability across the official radius range from a score on the
  narrower training range.
- **[Reasoned implication] Assumptions:** This consequence concerns use of
  `make_training_env` and the available sampler; the protected evaluator's
  exact distribution semantics remain a separate contract question below.
- **[Reasoned implication] Source references:** `robot_learning/training/environment.py`,
  `TRAINING_TARGET_RADIUS_RANGE`, `robot_learning/scenario/environment.py`,
  `_sample_target_position`, and `contracts/scenario.md`.
- **[Reasoned implication] Discriminating evidence:** Radius-stratified
  first-reach, minimum-distance, hold-interruption, and success measurements
  over the complete official interval would reveal whether the omitted inner
  region is a material generalization boundary.

### Scientifically meaningful quantities span the whole behavior

- **[Reasoned implication]** The minimum sufficient physical record for mechanism
  analysis includes target radius and angle; `q`, `qdot`, and joint-limit
  margins; end-effector position, velocity, and distance; Jacobian singular
  values; action and implied torque with saturation; acceleration; and the
  timing of first reach, in-tolerance runs, interruptions, final error, and
  termination. These quantities separate geometry, actuation, convergence,
  and stabilization rather than collapsing them into one reward or success
  number.
- **[Reasoned implication] Decision relevance:** The quantities identify
  qualitatively different failures: unreachable or limit-limited, initially
  singular, torque/inertia-limited, overshooting, branch-switching,
  boundary-chattering, and horizon-limited. That classification can change
  which scientific direction is credible without treating a proxy as official
  success.
- **[Reasoned implication] Assumptions:** Some quantities are policy-visible
  (`q`, `qdot`, target error) while others require simulator instrumentation
  (`qacc`, actuator torque, contact and constraint forces, internal-step
  distance). Derived acceleration and power are meaningful only with a stated
  differentiation or simulator-output convention.
- **[Reasoned implication] Source references:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`, `robot_learning/scenario/evaluation.py`,
  and `contracts/scenario.md`.
- **[Reasoned implication] Discriminating evidence:** A trajectory artifact
  containing these signals, aligned to the 0.020 s control boundaries and
  labelled by target geometry and IK branch, would support a mechanism claim;
  an aggregate success rate alone would not distinguish the listed classes.

## Unknowns

### Derived moving-body inertias and numerical dynamic authority

- **[Unresolved quantity]** The XML gives link geometry, damping, and armature
  but no moving-body mass, center of mass, inertia tensor, density, or explicit
  actuator-force limit. MuJoCo therefore supplies derived inertial and default
  quantities. The numerical `M(q)`, acceleration under a saturated command,
  damping time scale, and settling time are not established by the repository
  text alone.
- **[Unresolved quantity] Decision relevance:** This can change whether failures
  should be interpreted as insufficient control authority, excessive
  overshoot, or a policy problem, and can change the value of action
  regularization, model-based control, or horizon allocation.
- **[Unresolved quantity] Assumptions:** The uncertainty matters if the default
  inertial and solver values materially affect behavior at the 0.020 s control
  interval. If the arm is strongly over-actuated relative to its inertia, it
  may be practically irrelevant.
- **[Unresolved quantity] Source references:** `contracts/robots/two_joint_arm.xml`,
  `pyproject.toml` and `AGENTS.md` for the locked MuJoCo version, and
  `robot_learning/scenario/environment.py`.
- **[Unresolved quantity] Discriminating evidence:** A loaded-model report of
  body masses, joint-space inertia, actuator generalized force, and measured
  saturated step responses would support, weaken, or revise the authority and
  time-scale assumptions.

### Joint-limit softness, self-contact, and solver defaults

- **[Unresolved quantity]** Joint ranges are declared, but limit softness,
  constraint impedance, solver tolerances, integrator choice, and contact
  filtering are not explicitly specified in the XML. The target and plane are
  explicitly non-colliding, while the XML does not explicitly state the
  effective self-contact behavior of the moving geoms under MuJoCo defaults.
- **[Unresolved quantity] Decision relevance:** If constraints or self-contact
  become active near a folded branch, they can turn a nominally reachable
  solution into a qualitatively different contact- or limit-limited behavior.
  This would change whether branch-aware control and joint-limit margins are
  central to the first method choice.
- **[Unresolved quantity] Assumptions:** The uncertainty is consequential only
  if official trajectories approach a joint limit or link intersection; it is
  likely secondary for trajectories that remain well inside the range.
- **[Unresolved quantity] Source references:** `contracts/robots/two_joint_arm.xml`,
  especially `range`, geom collision attributes, and the absence of explicit
  solver/contact defaults; `AGENTS.md` for the locked simulator version.
- **[Unresolved quantity] Discriminating evidence:** Model introspection of
  active contacts and limit constraints, plus trajectories of constraint
  forces and joint-limit margins on both IK branches, would distinguish
  kinematic branch effects from contact or solver effects.

### Protected evaluator hold granularity

- **[Unresolved quantity]** The official contract calls for a continuous
  uninterrupted 2 s hold and equates it to 100 control steps. The available
  scenario environment increments its hold counter only after each ten-step
  control interval and does not expose an internal success check. The
  protected final evaluator's exact within-interval predicate is not present
  in the accessible sources.
- **[Unresolved quantity] Decision relevance:** The distinction changes how much
  margin a stabilizing policy needs: endpoint-only checking could admit
  between-sample excursions, while continuous checking would reject them.
  It also changes the interpretation of a policy that succeeds with high
  endpoint velocity.
- **[Unresolved quantity] Assumptions:** This matters if the policy can move
  appreciably during 0.020 s or if the protected evaluator differs from the
  available scenario mechanics. If motion is slow and deeply inside the
  tolerance ball, both semantics produce the same result.
- **[Unresolved quantity] Source references:** `contracts/scenario.md`,
  `contracts/task_spec.py`, `robot_learning/scenario/environment.py`,
  `TwoJointArmReachEnv.step`, and the module documentation distinguishing the
  available environment from the protected benchmark.
- **[Unresolved quantity] Discriminating evidence:** Comparing internal
  0.002 s distance traces with the official or task-reference outcome for
  episodes near the tolerance boundary would support one sampling semantics
  and identify whether endpoint-only success is a real possibility.

### Protected distribution measure and available sampler identity

- **[Unresolved quantity]** The official prose specifies a target uniformly
  from 6-20 cm over the full angular range, while the available sampler
  explicitly draws radius and angle independently and uniformly. The
  accessible contract text does not state whether "uniformly" is intended as
  uniform radius, uniform Cartesian area in the annulus, or exactly the
  available sampler for the protected panel.
- **[Unresolved quantity] Decision relevance:** The weighting of inner versus
  outer targets changes the success rate required from each geometry class and
  can change the first training-distribution or evaluation-stratification
  decision.
- **[Unresolved quantity] Assumptions:** This uncertainty is material only if
  the protected evaluator is not bound to the available sampler's explicit
  independent draws. The radial interval and angular coverage are fixed in
  either interpretation.
- **[Unresolved quantity] Source references:** `contracts/scenario.md`,
  `contracts/task_spec.py`, and
  `robot_learning/scenario/environment.py`, `_sample_target_position`.
- **[Unresolved quantity] Discriminating evidence:** The protected panel's
  declared sampling rule or its recorded target-radius distribution would
  resolve the measure; a radius-stratified development artifact can show the
  performance consequence even before that identity is resolved.

### Candidate-specific observation scaling and memory

- **[Unresolved quantity]** The physical observation layout is fixed, but a
  saved policy may carry a normalizer, and the runtime interface permits
  recurrent state. Before a candidate exists, the scale seen by the policy,
  whether it has memory, and whether that memory tracks hold history are
  unresolved.
- **[Unresolved quantity] Decision relevance:** Scaling and memory can change
  optimization conditioning and the ability to represent a hold-aware
  behavior, while leaving the simulator physics unchanged. Confusing this
  policy-interface uncertainty with missing physical sensing would misdirect
  diagnosis.
- **[Unresolved quantity] Assumptions:** The issue matters for candidate
  comparison when runtime artifacts differ in normalization or recurrence. It
  does not change what the simulator makes physically observable.
- **[Unresolved quantity] Source references:** `robot_learning/scenario/observations.py`,
  `robot_learning/train.py`, and `contracts/policy_runtime.py`,
  `PolicyRuntime.predict` and `reset`.
- **[Unresolved quantity] Discriminating evidence:** The saved runtime payload,
  normalizer statistics, policy class, and action/observation trace at reset
  would establish whether a candidate has numerical scaling or memory that
  can account for a hold-performance difference.

## Decision-relevant synthesis

### Dynamic authority is known structurally but not numerically

- **[Reasoned implication] Decision relevance:** The first campaign decision may
  depend on whether the 5-unit action range, 20 ms hold, damping, and armature
  provide ample authority or produce saturation and overshoot. Do not infer
  this from action bounds alone.
- **[Reasoned implication] Assumptions:** The consequence depends on
  MuJoCo-derived link inertias, limit/solver defaults, and direct-motor
  semantics being materially relevant at the official horizon.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`, and
  `AGENTS.md`/`pyproject.toml` for the locked MuJoCo stack.
- **[Reasoned implication] Discriminating evidence:** Loaded-model inertias and
  actuator forces, together with saturated response and settling traces,
  discriminate authority-limited behavior from policy or geometry failure.

### The reset singularity and two IK branches define the reach problem

- **[Reasoned implication] Decision relevance:** A first method must account for
  escape from the fully extended rank-one Jacobian and for branch-conditioned
  trajectories; endpoint reachability alone does not establish easy control.
- **[Reasoned implication] Assumptions:** The reset remains `q=(0,0)`, the
  point-site 2R model is valid, and no active self-contact removes a branch.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml`,
  `contracts/robots/two_joint_arm.py`, `robot_learning/scenario/environment.py`,
  and `robot_learning/scenario/observations.py`.
- **[Reasoned implication] Discriminating evidence:** Jacobian conditioning,
  branch labels, joint-limit margins, and first-reach time stratified by
  target radius and angle show whether geometry or actuation dominates.

### Official success is a robust hold, not a reach event

- **[Reasoned implication] Decision relevance:** The first useful performance
  diagnosis must separate first entry, convergence, boundary crossings, and
  the complete 100-step uninterrupted run. A high minimum-distance score or a
  single target hit is not evidence of the human goal.
- **[Reasoned implication] Assumptions:** The protected evaluator follows the
  contract's continuous-hold meaning; the available endpoint-only behavior is
  treated as an implementation detail pending resolution.
- **[Reasoned implication] Source references:** `contracts/scenario.md`,
  `contracts/task_spec.py`, and
  `robot_learning/scenario/environment.py`, `step`.
- **[Reasoned implication] Discriminating evidence:** Full distance, endpoint
  velocity, hold-run, interruption, and internal-step traces distinguish
  stable equilibrium from sampled or oscillatory success.

### The policy sees the physical goal but not the hold automaton

- **[Reasoned implication] Decision relevance:** The observation features are
  sufficient to represent target geometry and both IK branches, but hold
  history and horizon are absent. The first policy decision therefore must
  preserve a stable physical behavior or provide appropriate memory; adding
  force or orientation sensing is not justified by the task contract.
- **[Reasoned implication] Assumptions:** The simulator has no hidden actuator,
  contact, or sensor state that materially changes the Markov state, and any
  candidate normalization or recurrence is candidate-specific.
- **[Reasoned implication] Source references:** `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/environment.py`, and
  `contracts/policy_runtime.py`.
- **[Reasoned implication] Discriminating evidence:** Observation
  reconstruction and saved-runtime inspection, paired with traces around hold
  interruptions, distinguish missing physical information from missing task
  history.

### Official coverage includes a training-exposure gap

- **[Reasoned implication] Decision relevance:** If the current training
  constructor is retained, the policy must generalize from 0.14-0.20 m
  training radii to the official 0.06-0.20 m interval. The first comparison
  should not use the narrower training score as a substitute for official
  distribution capability.
- **[Reasoned implication] Assumptions:** The current `make_training_env`
  remains the training exposure and the protected distribution follows the
  official scenario contract.
- **[Reasoned implication] Source references:** `robot_learning/training/environment.py`,
  `robot_learning/scenario/environment.py`, `contracts/task_spec.py`, and
  `contracts/scenario.md`.
- **[Reasoned implication] Discriminating evidence:** Radius-stratified
  success and mechanism diagnostics over the full official range show whether
  inner-target behavior is the first material generalization gap.
