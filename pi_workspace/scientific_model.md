## Established facts

### System boundary, coordinates, and morphology

- **[Repository fact]** The simulated plant is the MuJoCo model loaded from
  `contracts/robots/two_joint_arm.xml` by
  `robot_learning/scenario/environment.py::TwoJointArmReachEnv`. The base is
  fixed at the world origin. The upper-arm body is offset to
  `(0, 0, 0.02)`, so the arm moves in the horizontal `x-y` plane at
  `z = 0.02`.
  **Source references:** `contracts/robots/two_joint_arm.xml` worldbody and
  body hierarchy; `robot_learning/scenario/environment.py::__init__`.

- **[Repository fact]** There are two generalized coordinates: a shoulder
  hinge `q_1` and a relative elbow hinge `q_2`, both rotating about the
  world/local `z` axis. Each joint declares the range `[-170, 170]` degrees.
  The upper-arm and forearm lengths are `l_1 = 0.12 m` and `l_2 = 0.10 m`.
  The end-effector task point is the site at the distal end of the forearm;
  its visual site size is not part of the task distance.
  **Source references:** `contracts/robots/two_joint_arm.xml` shoulder, elbow,
  capsule, and `end_effector` definitions; `contracts/robots/two_joint_arm.py`
  `UPPER_ARM_LENGTH` and `FOREARM_LENGTH`.

- **[Reasoned implication]** With the usual serial-planar joint convention,
  the task point is
  `p(q) = (l_1 cos(q_1) + l_2 cos(q_1+q_2),
  l_1 sin(q_1) + l_2 sin(q_1+q_2), 0.02)`. Its velocity is
  `v = J(q) qdot`, where the planar Jacobian has columns
  `(-l_1 sin(q_1)-l_2 sin(q_1+q_2),
  l_1 cos(q_1)+l_2 cos(q_1+q_2))` and
  `(-l_2 sin(q_1+q_2), l_2 cos(q_1+q_2))`.
  **Source references:** body/joint/site transforms in
  `contracts/robots/two_joint_arm.xml`; the same geometry is used explicitly
  by `robot_learning/scenario/observations.py::reach_observation`.

- **[Reasoned implication]** Ignoring joint limits, the radial workspace is
  the annulus `[|l_1-l_2|, l_1+l_2] = [0.02, 0.22] m`. The declared target
  centers, `[0.06, 0.20] m`, are strictly inside this annulus. The declared
  joint limits also leave both inverse-kinematic branches admissible over
  that radial interval: `|q_2|` is approximately `49.5` to `150` degrees,
  and the worst shoulder magnitude for the opposite-direction target is
  below `170` degrees. Thus the center of every official target is
  kinematically reachable in two configurations, subject to the compiled
  model's limit/contact behavior.
  **Source references:** `contracts/task_spec.py::TARGET_RADIUS_RANGE`;
  `contracts/robots/two_joint_arm.py`; `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py::reach_observation`.

- **[Reasoned implication]** For target polar coordinates `(r, phi)`, the
  observation code uses
  `cos(q_2) = (r^2-l_1^2-l_2^2)/(2 l_1 l_2)` and
  `q_1 = phi - atan2(l_2 sin(q_2), l_1+l_2 cos(q_2))`. It evaluates both
  `q_2 = +acos(cos(q_2))` and `q_2 = -acos(cos(q_2))`, called here the
  open and folded branches. The two branches are distinct throughout the
  official radius range rather than a singular duplicate.
  **Source references:** `robot_learning/scenario/observations.py` local
  functions `shoulder_for_elbow`, `elbow_open`, `elbow_folded`.

### Physics, actuation, and timing

- **[Repository fact]** MuJoCo gravity is explicitly zero and the physics
  timestep is `0.002 s`. Each hinge has explicit viscous damping `0.5` and
  armature `0.01`; each motor has gear `5` and a declared control range
  `[-1, 1]`. The world plane and target geom have
  `contype="0"` and `conaffinity="0"`, so they are not contact participants.
  **Source references:** `contracts/robots/two_joint_arm.xml` `<option>`,
  joint attributes, actuator definitions, plane, and target geom.

- **[Reasoned implication]** A policy action is a two-component command in
  `[-1,1]^2`. `physical_action` is the identity, and the environment clips
  the result before writing it to `data.ctrl`. Under MuJoCo's direct
  single-joint motor transmission, the commanded generalized motor torque is
  `tau_i = 5 u_i` in the model's torque units, with `|tau_i| <= 5` from the
  environment clip. No action-rate limit or command smoothing is defined.
  **Source references:** `robot_learning/scenario/policy_io.py::physical_action`;
  `robot_learning/scenario/environment.py::step`; actuator entries in
  `contracts/robots/two_joint_arm.xml`.

- **[Repository fact]** The command is held constant for `FRAME_SKIP = 10`
  MuJoCo steps. Therefore the control period is `10 * 0.002 = 0.020 s`
  (50 control updates per second). The maximum episode length is 500
  control steps, nominally 10 seconds, and the required hold is
  `round(2.0 / 0.020) = 100` control steps.
  **Source references:** `contracts/task_spec.py`; 
  `robot_learning/scenario/environment.py::__init__` and `step`.

- **[Reasoned implication]** Between policy updates the plant evolves under a
  zero-order-held torque command at the finer MuJoCo timestep. A schematic
  generalized equation is
  `M(q) qddot + h(q,qdot) + 0.5 qdot + tau_constraints =
  diag(5,5) u`, with the `0.01` armatures included in the effective
  generalized inertia. `h` contains velocity-dependent multibody coupling
  and any compiled non-gravitational terms. With zero gravity and no active
  constraints, zero command at zero velocity is a static equilibrium at any
  interior configuration; damping removes velocity but does not create a
  position servo.
  **Source references:** explicit XML physics and actuator parameters;
  `robot_learning/scenario/environment.py::step` call to `mujoco.mj_step`.
  The equation is a model consequence, not a claim that all compiled
  coefficients are numerically known here.

- **[Repository fact]** Reset calls `mj_resetData`, then sets both joint
  positions and velocities to zero, calls `mj_forward`, samples the target,
  and calls `mj_forward` again. The initial arm is therefore straight along
  positive `x`, with end-effector position `(0.22, 0, 0.02)`. The target is
  static mocap data, not a dynamically falling or moving body.
  **Source references:** `robot_learning/scenario/environment.py::reset` and
  `_sample_target_position`; `contracts/robots/two_joint_arm.xml`.

### Target distribution and task geometry

- **[Repository fact]** Each official target angle is sampled uniformly from
  `[-pi, pi]`, and its radius is sampled independently and uniformly from
  `0.06` to `0.20 m`. The target `z` coordinate is set to the current
  end-effector `z`, so the success distance is effectively planar even though
  it is computed as a 3-D Euclidean norm.
  **Source references:** `contracts/scenario.md`; 
  `robot_learning/scenario/environment.py::_sample_target_position`;
  `contracts/task_spec.py::TARGET_RADIUS_RANGE`.

- **[Reasoned implication]** Uniform radius and uniform angle do not produce a
  uniform spatial density over the annulus: the official task gives equal
  probability to equal radial intervals, while equal-area annular bands have
  different probabilities. Radius-stratified outcomes therefore describe the
  task distribution directly rather than merely correcting for a sampling
  artifact.
  **Source references:** target sampler in
  `robot_learning/scenario/environment.py::_sample_target_position`;
  `contracts/scenario.md`.

- **[Repository fact]** The target is a point-center task with tolerance
  `0.01 m`: the environment computes
  `d = ||p_end - p_target||` and considers a control-step sample in
  tolerance when `d <= 0.01`. The visible target sphere has radius
  `0.012 m`, but target and plane visuals do not define the success radius or
  a physical collision.
  **Source references:** `contracts/task_spec.py::SUCCESS_THRESHOLD`;
  `robot_learning/scenario/environment.py::_distance_to_target` and `step`;
  target geom in `contracts/robots/two_joint_arm.xml`.

- **[Reasoned implication]** At reset the initial distance obeys
  `d_0^2 = 0.22^2 + r^2 - 2(0.22)r cos(phi)`. Across the official
  distribution it is at least `0.02 m` and can reach `0.42 m`; it is
  therefore always outside the `0.01 m` tolerance initially. The controller
  must produce a nontrivial reach before any hold can begin.
  **Source references:** reset state and target sampler in
  `robot_learning/scenario/environment.py`; lengths in
  `contracts/robots/two_joint_arm.py`; tolerance in
  `contracts/task_spec.py`.

### Sensing, policy input, and interaction semantics

- **[Repository fact]** The default observation has 11 float32 entries:
  two `qpos` values, two `qvel` values, the three-vector
  `end_effector - target`, and four wrapped joint-angle errors to the open
  and folded inverse-kinematic configurations. There is no sensor noise,
  camera image, force/torque reading, contact reading, or explicit target
  velocity in this representation.
  **Source references:** `robot_learning/scenario/observations.py::reach_observation`
  and `OBSERVATION_SIZE`; `robot_learning/scenario/policy_io.py::make_policy_io`.

- **[Reasoned implication]** For this static-target, no-actuator-state model,
  the physical state relevant to future motion is effectively observable:
  `q` and `qdot` are supplied, and the target can be reconstructed from the
  known kinematics and `p_end - p_target`. The `z` error is identically zero
  after reset. The four IK errors do not reveal an additional hidden
  variable; they expose both available posture references and permit branch
  selection.
  **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py::reset` and `step`.

- **[Repository fact]** A saved runtime may normalize and clip observations
  before prediction, and its recurrence state is reset at every episode.
  The runtime then returns an action which is passed through the physical
  identity mapping and environment clip. This input transform is policy
  artifact state, not a new physical sensor.
  **Source references:** `contracts/policy_runtime.py::PolicyRuntime`,
  `robot_learning/scenario/policy_io.py`, and
  `robot_learning/scenario/environment.py::step`.

- **[Repository fact]** One interaction cycle is: observe the current state,
  predict an action, write the clipped command, integrate ten physics steps,
  compute the distance once, update the hold counter, and return the next
  observation. If the sampled distance is outside tolerance, the hold counter
  is reset to zero. Termination occurs at 100 consecutive in-tolerance
  control-step samples; truncation occurs at 500 steps.
  **Source references:** `robot_learning/scenario/environment.py::step`;
  `contracts/task_spec.py`; `contracts/scenario.md`.

- **[Repository fact]** The official assessment freezes one policy and tests
  200 episodes from the official distribution. The campaign objective is at
  least 196 successes, or 98 percent; development panels are distinct from
  that assessment.
  **Source references:** `contracts/scenario.md::Official final assessment`
  and `Success criterion`.

## Physical consequences

### Reachability is broad, but posture is a real control choice

- **[Reasoned implication]** Both open and folded postures can solve every
  official target center, so failure need not be caused by lack of geometric
  reach. The policy must nevertheless choose a branch and traverse to it
  without violating joint limits or losing the target during convergence.
  **Decision relevance:** A first explanation of failure should distinguish
  branch/trajectory selection from workspace infeasibility; this can change
  whether the campaign treats the problem as posture selection or as pure
  torque regulation.
  **Assumptions:** The planar transform above matches MuJoCo's compiled body
  frames; link self-contact and joint stops do not invalidate the calculated
  centers.
  **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`; `contracts/task_spec.py`.
  **Discriminating evidence:** Per-episode final `q`, branch-relative angle
  errors, joint-limit proximity, target radius/angle, and whether the
  end-effector enters tolerance are sufficient to separate unreachable,
  wrong-branch, and failed-convergence cases.

### Radius changes conditioning without making reach impossible

- **[Reasoned implication]** The planar Jacobian determinant is
  `det(J) = l_1 l_2 sin(q_2)`. The official outer radius maps to
  approximately `|q_2| = 49.5` degrees, while the inner radius maps to
  approximately `|q_2| = 150` degrees. The inner end of the range is
  therefore closer to the folded singularity at `q_2 = 180` degrees and
  has a smaller determinant magnitude (about `0.0060 m^2` versus
  `0.0091 m^2` at the outer end). The outer end is closer to the extended
  singularity at `q_2 = 0`; full velocity anisotropy depends on the two
  singular values and is not ranked by radius from these facts alone.
  **Decision relevance:** Radius-dependent reach time, overshoot, and hold
  interruption can change the first useful research direction even when
  aggregate success looks similar.
  **Assumptions:** The policy uses the declared site position as the task
  point and dynamics do not introduce a larger constraint effect near the
  folded posture.
  **Source references:** lengths in `contracts/robots/two_joint_arm.py`;
  inverse-kinematic calculation in `robot_learning/scenario/observations.py`;
  target range in `contracts/task_spec.py`.
  **Discriminating evidence:** Stratify first-reach step, minimum distance,
  peak joint speed, peak command, and hold interruptions by radius and by
  selected IK branch; compare those quantities with the analytic `J(q)`.

### Reaching and holding are coupled dynamical problems

- **[Reasoned implication]** Reaching requires moving a two-link inertia through
  a target-dependent configuration; holding requires suppressing residual
  velocity and dynamic coupling inside a 1 cm ball for 2 seconds. A command
  that reduces instantaneous Cartesian error can still create velocity that
  exits the tolerance on a later 20 ms sample. Because there is no gravity
  load, a settled interior pose does not require a constant gravity
  compensation torque, but active corrections are still needed for velocity,
  coupling, and numerical or constraint effects.
  **Decision relevance:** A low minimum distance is not evidence of task
  competence; the first campaign split must preserve reach and stabilization
  as separate physical failure classes.
  **Assumptions:** The direct motor mapping and explicit damping are the
  dominant control paths, and no unmodeled external load exists.
  **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py::step`;
  `contracts/scenario.md`.
  **Discriminating evidence:** Time series of distance, Cartesian velocity,
  joint velocity, action, first in-tolerance step, maximum held steps, and
  every hold interruption distinguish arrival from stable convergence.

### Torque authority is filtered by unknown inertia and fixed control bandwidth

- **[Reasoned implication]** The action can change torque discontinuously at
  50 Hz, while the plant integrates at 500 Hz. The same bounded command can
  produce different accelerations and overshoot at different configurations
  because `M(q)` and velocity coupling vary. The explicit damping makes
  velocity decay possible, but the settling time is set by damping relative
  to effective inertia, not by the action bound alone.
  **Decision relevance:** Whether early work should emphasize policy behavior,
  controller shaping, or physical characterization depends on whether errors
  are authority-limited, timing-limited, or caused by overshoot.
  **Assumptions:** MuJoCo's compiled motor transmission is the direct
  `5 u` mapping and there are no active contact constraints during the
  trajectory.
  **Source references:** actuator and joint attributes in
  `contracts/robots/two_joint_arm.xml`; `FRAME_SKIP` and `mj_step` loop in
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** Command-to-acceleration response at several
  configurations, peak acceleration/velocity, torque saturation fraction,
  and decay after command removal identify effective authority and damping.

### The baseline exposure does not cover the official inner band

- **[Repository fact]** The current training environment samples radii from
  `[0.14, 0.20] m`, whereas evaluation samples `[0.06, 0.20] m`.
  Training-only target construction is isolated in
  `robot_learning/training/environment.py`; the official environment uses
  `contracts/task_spec.py::TARGET_RADIUS_RANGE`.
  **Decision relevance:** A baseline policy can be competent on the exposed
  outer band while failing on 6--14 cm targets, so an aggregate development
  score cannot by itself identify physical generalization across the official
  workspace.
  **Assumptions:** The current training environment is the relevant baseline
  recipe and no saved policy has received other inner-band exposure.
  **Source references:** `robot_learning/training/environment.py::TRAINING_TARGET_RADIUS_RANGE`;
  `robot_learning/scenario/environment.py::make_evaluation_env`;
  `contracts/task_spec.py`.
  **Discriminating evidence:** Radius-binned evaluation outcomes and the
  dynamic diagnostics above, using identical episode seeds when comparing
  policies, show whether the gap is exposure-related or a general
  stabilization limitation.

### The observable state is nearly Markov, but branch symmetry remains

- **[Reasoned implication]** The default vector contains enough information to
  reconstruct current configuration, velocity, relative target, and both
  static IK references, so image-based localization or memory is not required
  by the stated physical task. The symmetry is not hidden state: it is a
  choice between two valid configurations. A policy can switch branches, but
  doing so adds motion and can pass through configurations with different
  Jacobian conditioning.
  **Decision relevance:** If this observability claim holds for the evaluated
  runtime, early explanations should prioritize closed-loop torque behavior
  over partial-observation inference.
  **Assumptions:** The saved runtime uses the current `reach_observation`
  closure, the target stays static, and no active actuator state is omitted
  from the model.
  **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`.
  **Discriminating evidence:** Reconstruct target coordinates from logged
  observations and compare them with simulator target data; inspect the
  runtime's frozen observation callable and any normalization statistics.

### The measured objective is an uninterrupted hold, not a terminal pose

- **[Reasoned implication]** An episode that reaches the tolerance and leaves it
  before 100 consecutive samples is a failure under the environment counter,
  even if it later returns. The complete behavior therefore includes
  acquisition, convergence, and a low-velocity tolerance margin for the full
  hold. The shaped reward includes progress, closeness, action cost, and hold
  progress, but reward components do not alter the physical success predicate.
  **Decision relevance:** Candidate ranking based only on minimum distance or
  final pose would select the wrong behavior; hold continuity and interruption
  structure are necessary scientific quantities.
  **Assumptions:** The shared environment implements the protected interaction
  semantics used for official measurement.
  **Source references:** `robot_learning/scenario/environment.py::step`;
  `robot_learning/training/reward.py::reach_reward`;
  `contracts/scenario.md`.
  **Discriminating evidence:** Complete per-control-step distance and held-step
  traces, including the first exit after entry and maximum uninterrupted
  hold, directly test this implication.

## Unknowns

### Compiled mass, inertia, and numerical integration

- **[Unresolved quantity]** The XML gives capsule geometry, but it does not
  state body masses, inertial tensors, geom density, compiler inertia policy,
  integrator choice, or solver parameters. The loaded `MjModel` resolves
  these values, but their numerical values are not present in the
  human-readable robot contract. Consequently the exact `M(q)`, damping
  ratios, natural response time, and acceleration under `|tau_i| <= 5` are
  unresolved here.
  **Decision relevance:** These quantities determine whether observed
  overshoot or slow settling is an intrinsic plant limit, a controllable
  policy behavior, or a numerical-time-step effect.
  **Assumptions:** The XML and installed MuJoCo version are the complete
  simulator definition; no external load or hidden controller is added.
  **Source references:** `contracts/robots/two_joint_arm.xml` has no explicit
  inertial or solver blocks; `AGENTS.md` fixes native MuJoCo `3.12.0`;
  `robot_learning/scenario/environment.py` constructs `MjModel` directly.
  **Discriminating evidence:** The compiled model's mass, inertia, actuator,
  timestep, integrator, and solver fields together with measured
  command-to-motion response would support or revise the dynamic equation
  used above.

### Contact, self-collision, and joint-stop behavior

- **[Unresolved quantity]** Plane and target contact are explicitly disabled,
  but the arm and base geoms retain their XML defaults, and no explicit
  self-collision exclusions or joint-stop softness parameters are shown.
  Whether folded link geometry generates contacts, and the exact forces when
  a joint approaches `+/-170` degrees, therefore remains unresolved from the
  source text alone.
  **Decision relevance:** Contact or stop forces could create a qualitatively
  different failure class near folded solutions and could invalidate a
  torque-only explanation of hold exits.
  **Assumptions:** Default MuJoCo geom filtering and joint-limit compilation
  are active as loaded, rather than being replaced by a benchmark wrapper.
  **Source references:** geom and joint declarations in
  `contracts/robots/two_joint_arm.xml`; model construction in
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** Compiled contact-pair/constraint data, contact
  force and joint-limit force traces, and the minimum distance between link
  geoms during folded trajectories would resolve this quantity.

### Control-step sampling versus continuous physical containment

- **[Unresolved quantity]** The human contract says the end effector must
  remain continuously within the 1 cm tolerance for 2 seconds, while the
  visible environment calls `_distance_to_target()` only after the ten-step
  integration loop and updates `_held_steps` at control-step boundaries.
  The source therefore establishes a 100-sample operational counter but does
  not, by itself, establish whether a protected evaluator also checks the
  intermediate 2 ms states.
  **Decision relevance:** A policy can pass endpoint sampling while making
  short excursions between observations, or fail a stricter continuous test;
  this can change the meaning of every hold diagnostic and the first
  campaign diagnosis.
  **Assumptions:** The protected benchmark may share the visible
  `TwoJointArmReachEnv` semantics, but its implementation is not part of the
  accessible source.
  **Source references:** `contracts/scenario.md::Success criterion`;
  `robot_learning/scenario/environment.py::step`; `FRAME_SKIP` in
  `contracts/task_spec.py`.
  **Discriminating evidence:** A boundary-case trajectory sampled at every
  MuJoCo substep, compared with the recorded success result under the
  official evaluator, would distinguish endpoint and continuous semantics.

### Candidate-specific input transformation and effective policy state

- **[Unresolved quantity]** The physical observation definition is fixed, but
  a saved policy may carry observation-normalization statistics and a
  candidate-specific recurrent or feed-forward runtime. Before a candidate is
  selected, the actual normalized ranges, clipping frequency, and action
  sensitivity are unknown. These are not new plant sensors, but they affect
  what information reaches the controller.
  **Decision relevance:** Saturated normalization or a mismatched runtime can
  mimic poor physical observability or poor torque control and change whether
  a result is attributed to the policy or the plant.
  **Assumptions:** Runtime validation accepts only the frozen observation and
  weight pairing described by `contracts/policy_runtime.py`.
  **Source references:** `contracts/policy_runtime.py::save_runtime`,
  `validate_runtime_files`, and `PolicyRuntime.predict`;
  `robot_learning/training/normalization.py`.
  **Discriminating evidence:** The saved runtime's observation callable,
  normalization statistics, pre/post-normalization observation trace, and
  action trace would show whether the controller receives the intended
  state without clipping or stale recurrence.

### Which physical failure dominates official success

- **[Unresolved quantity]** No pre-campaign evidence establishes the
  distribution of reach failures, hold interruptions, branch choices,
  radius/angle sensitivity, or success probability for any learned policy.
  The contract supplies the required 98 percent outcome but not its mechanism.
  **Decision relevance:** The first campaign decision can change depending on
  whether the dominant gap is acquisition, convergence, long-hold stability,
  or a narrow geometric subset; aggregate success alone cannot identify that
  cause.
  **Assumptions:** Per-episode diagnostics remain available without changing
  the official success definition, and development panels are interpreted as
  evidence about mechanisms rather than as the official result.
  **Source references:** `contracts/scenario.md`; 
  `robot_learning/scenario/evaluation.py::evaluate_research_model`;
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** A frozen-policy panel with episode-level
  target radius/angle, minimum and final distance, first-reach step, maximum
  held steps, interruptions, and success provides the required separation;
  the official panel remains the only 200-episode goal assessment.

### Quantities that are physically meaningful but not yet measured

- **[Unresolved quantity]** The scientifically meaningful trajectory variables
  are joint state `(q, qdot)`, task state `(p, e, d)`, Jacobian and
  manipulability, command and realized torque, acceleration, dynamic
  coupling, time to first entry, tolerance margin during the hold, action
  variation/effort, selected IK branch, joint-limit/contact proximity, and
  the uninterrupted held-step sequence. None should be treated as an
  observed campaign fact before measurement.
  **Decision relevance:** These quantities provide the mechanism-level
  distinctions needed to connect a success count to a physical explanation
  without changing the task boundary.
  **Assumptions:** State and target traces can be recorded at the control
  rate, and substep traces can be obtained when the continuous-hold question
  matters.
  **Source references:** kinematics in
  `robot_learning/scenario/observations.py`; interaction and diagnostics in
  `robot_learning/scenario/environment.py` and
  `robot_learning/scenario/evaluation.py`; success contract in
  `contracts/scenario.md`.
  **Discriminating evidence:** Joint/task trajectories and their derived
  Jacobian, torque, velocity, margin, and interruption statistics would
  support or weaken each proposed mechanism; absent such traces, only the
  binary episode outcome is established.

## Decision-relevant synthesis

### Official inner-band coverage and radius-dependent conditioning

- **Decision relevance:** The current training definition omits 6--14 cm
  targets, which exercise the folded side of the Jacobian range and a
  different dynamic/kinematic conditioning regime. This is the most direct
  pre-campaign reason that a policy can appear competent while missing part
  of the official distribution; the relative severity of inner versus outer
  conditioning is not assumed.
- **Assumptions:** The current training range is the baseline exposure and
  branch/conditioning effects dominate any radius dependence.
- **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`; `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Radius- and branch-stratified success, first
  reach, peak speed/command, minimum distance, and hold interruptions.

### Two-second stabilization under 50 Hz action updates

- **Decision relevance:** The target is not solved by entry alone. Residual
  velocity, torque discontinuities, damping, and configuration-dependent
  inertia can determine whether 100 consecutive samples are retained.
- **Assumptions:** Direct `5 u` motor authority, 20 ms zero-order hold, and
  explicit damping describe the evaluated control loop.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Full distance/velocity/action traces through
  the hold, including every interruption and the tolerance margin at each
  control sample.

### Compiled dynamics and contact defaults

- **Decision relevance:** Unknown mass/inertia, integration, self-contact, or
  joint-stop behavior can change the physical explanation of slow motion,
  overshoot, and folded-posture failures before any learning conclusion is
  justified.
- **Assumptions:** Human-readable XML omissions are not silently filled by a
  campaign-specific wrapper.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md` MuJoCo version
  contract.
- **Discriminating evidence:** Loaded-model dynamic/constraint fields and
  command-response measurements, including contact and limit forces.

### Control-step success semantics

- **Decision relevance:** The written task promises continuous containment,
  but the visible counter tests one distance after each ten-substep action.
  This distinction can change whether a passing hold is physically
  continuous and how official failures are interpreted.
- **Assumptions:** The protected final evaluator may or may not match the
  visible environment's endpoint sampling; that fact is not established here.
- **Source references:** `contracts/scenario.md::Success criterion`;
  `robot_learning/scenario/environment.py::step`; `contracts/task_spec.py`.
- **Discriminating evidence:** Substep distance traces paired with the
  official evaluator's success bit for trajectories that cross the tolerance
  between control boundaries.
