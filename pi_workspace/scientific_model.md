## Established facts

### System boundary and success definition

- **[Repository fact]** The system is a fixed-base, two-joint arm in a MuJoCo
  model. The official task samples a target at a radius of 6--20 cm from the
  base over the full angular range. Success requires the end-effector position
  to be within 1 cm of the target continuously for 2 seconds; the official
  timing defines this as 100 consecutive control steps. The official objective
  is at least 196 successes in a fixed 200-episode assessment. **Source:**
  `contracts/scenario.md:9-23`.
- **[Repository fact]** The official robot, physics, target distribution,
  interaction semantics, and success definition are immutable benchmark
  contracts. The PI-owned research environment is not itself the authority for
  the final assessment. **Source:** `contracts/scenario.md:20-23`;
  `contracts/instruments.md`, “Saved controller execution”.

### Morphology, coordinates, and kinematic state

- **[Repository fact]** The base is fixed at the world origin. The shoulder
  and elbow are hinge joints about the world/body \(z\)-axis, so the moving
  mechanism has two scalar configuration coordinates: shoulder angle
  \(q_s\) and elbow angle \(q_e\). The elbow angle is relative to the upper
  arm, and the forearm orientation is \(q_s+q_e\). **Source:**
  `contracts/robots/two_joint_arm.xml:9-23`.
- **[Repository fact]** The upper arm length is 0.12 m and the forearm length
  is 0.10 m. Their capsule radii are 0.015 m and 0.012 m. The end-effector
  site is at the distal forearm endpoint and has a visual site size of
  0.008 m. The shoulder and elbow ranges are each \([-170^\circ,170^\circ]\).
  **Source:** `contracts/robots/two_joint_arm.xml:12-20`;
  `contracts/robots/two_joint_arm.py:5-8`.
- **[Repository fact]** The joint origins and the end-effector lie in the
  horizontal plane \(z=0.02\) m: the upper-arm body is offset upward by
  0.02 m and all subsequent link and site offsets have zero local \(z\)
  component. Thus, for the nominal joint coordinates,
  \[
  p_E(q)=\begin{bmatrix}
  0.12\cos q_s+0.10\cos(q_s+q_e)\\
  0.12\sin q_s+0.10\sin(q_s+q_e)\\
  0.02
  \end{bmatrix}.
  \]
  **Source:** `contracts/robots/two_joint_arm.xml:9-20`.
- **[Repository fact]** The plane, base, arm, and target are not a manipulation
  scene: the plane and arm geoms have `contype="0"` and
  `conaffinity="0"`, and the target is a mocap body rather than a dynamic
  object. The target sphere and end-effector site therefore provide visual
  geometry and a reference point, not a grasp or contact interaction in the
  visible model. **Source:** `contracts/robots/two_joint_arm.xml:5-26`;
  `robot_learning/scenario/environment.py:75-97`.

### Actuation, simulation, and control timing

- **[Repository fact]** Each joint is driven by a MuJoCo motor actuator with
  control range \([-1,1]\) and gear 5. The current policy action adapter is
  the identity, and the environment clips the resulting two-vector to
  \([-1,1]^2\) before assigning it to `data.ctrl`. **Source:**
  `contracts/robots/two_joint_arm.xml:30-32`;
  `robot_learning/scenario/policy_io.py:8-16`;
  `robot_learning/scenario/environment.py:123-132`.
- **[Repository fact]** With the hinge motor transmission, the command is a
  direct generalized joint-torque command with nominal magnitude
  \(5|a_i|\) in MuJoCo torque units per joint; no position target or velocity
  target is specified. No actuator activation state or actuator time constant
  is authored in the XML. **Source:** `contracts/robots/two_joint_arm.xml:30-32`;
  MuJoCo motor semantics used by the pinned `mujoco==3.12.0` stack
  (`AGENTS.md`, “Environment”).
- **[Repository fact]** The physics timestep is 0.002 s. One policy action is
  held while 10 `mj_step` calls execute, so the visible control interval is
  0.020 s (50 Hz). The hold requirement is therefore 100 such intervals, and
  the visible episode limit is 500 control intervals (10 s). **Source:**
  `contracts/robots/two_joint_arm.xml:2`;
  `contracts/task_spec.py:6-11`;
  `robot_learning/scenario/environment.py:52-57,123-159`.
- **[Repository fact]** Gravity is explicitly zero. Each joint declares
  viscous damping 0.5 and armature 0.01. Link mass and inertia are not
  explicitly authored as body inertials or geom densities in the XML; the
  compiled model consequently supplies those quantities through MuJoCo
  defaults and geometry compilation. **Source:**
  `contracts/robots/two_joint_arm.xml:2,12-19`.

### Reset, target geometry, and termination

- **[Repository fact]** Reset calls `mj_resetData`, then sets both joint
  positions and velocities to zero and runs forward kinematics. It samples an
  angle uniformly from \([-\pi,\pi]\) and a radius uniformly from
  \([0.06,0.20]\) m, and places the mocap target at that \(x,y\) location and
  at the current end-effector \(z\). **Source:**
  `robot_learning/scenario/environment.py:83-114`;
  `contracts/task_spec.py:6`.
- **[Repository fact]** At reset the end effector is at
  \(p_E=(0.22,0,0.02)\) m, with \(q_s=q_e=\dot q_s=\dot q_e=0\). The target
  is stationary after sampling. **Source:** `contracts/robots/two_joint_arm.xml:9-20`;
  `robot_learning/scenario/environment.py:102-114`.
- **[Repository fact]** The visible success test computes the Euclidean
  three-dimensional distance between the end-effector site and target mocap
  position after each control interval. Being inside the tolerance increments
  a consecutive counter; one outside sample resets that counter. Termination
  occurs at 100 held intervals, while truncation occurs at 500 total
  intervals. **Source:** `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/environment.py:75-81,134-169`.
- **[Repository fact]** The research evaluator records one binary outcome and
  diagnostics including target radius and angle, minimum and final distance,
  first reach step, maximum held steps, in-tolerance steps, and hold
  interruptions. **Source:** `robot_learning/scenario/evaluation.py:48-96`.

### Observation and policy interface

- **[Repository fact]** The default 11-dimensional observation is ordered as
  two joint positions, two joint velocities, the three-dimensional
  end-effector-minus-target displacement, and four wrapped joint errors to the
  two inverse-kinematic branches (open/elbow-up and folded/elbow-down).
  **Source:** `robot_learning/scenario/observations.py:7-49`.
- **[Repository fact]** The branch targets are computed from the known link
  lengths using
  \[
  \cos q_e =
  \frac{x_t^2+y_t^2-l_1^2-l_2^2}{2l_1l_2},
  \]
  followed by \(q_e=\pm\arccos(\cdot)\) and the corresponding shoulder
  angle. The implementation clips the cosine argument before `arccos`.
  **Source:** `robot_learning/scenario/observations.py:12-35`.
- **[Repository fact]** The visible observation reads simulator state directly:
  there is no sensor noise, filtering, quantization, force sensing, or
  acceleration channel in this representation. The target's orientation and
  velocity are not observed. **Source:** `robot_learning/scenario/observations.py:27-49`;
  `contracts/robots/two_joint_arm.xml:25-26`.
- **[Repository fact]** A saved runtime can freeze observation, action, and
  reset callables, together with optional normalization, beside policy
  weights. The current default callables are the observation above and the
  identity action map. **Source:** `contracts/policy_runtime.py:18-36,86-135`;
  `robot_learning/scenario/policy_io.py:8-16`;
  `contracts/instruments.md`, “Saved controller execution”.

### Learning signal and exposure

- **[Repository fact]** The shared research environment uses distance progress,
  exponential closeness, hold-progress, a possible outside-band penalty,
  action cost, and a hold-complete bonus as reward components. The binary
  success condition, not reward total, defines task success. **Source:**
  `robot_learning/training/reward.py:12-109`;
  `robot_learning/scenario/environment.py:145-169`;
  `contracts/scenario.md:11-15`.
- **[Repository fact]** The current training-only environment samples radii
  from 0.14--0.20 m, whereas the evaluation environment uses the official
  0.06--0.20 m interval. Both use the shared planar mechanics and full angular
  sampling in the visible code. **Source:**
  `robot_learning/training/environment.py:8-18`;
  `robot_learning/scenario/environment.py:33-57`;
  `contracts/task_spec.py:6`.

## Physical consequences

### The official target annulus is kinematically reachable but has two branches

- **[Reasoned implication]** For link lengths \(l_1=0.12\) m and \(l_2=0.10\) m,
  the unconstrained radial envelope is \([|l_1-l_2|,l_1+l_2]=[0.02,0.22]\) m.
  With the declared elbow range, the smallest radial value on the permitted
  elbow boundary is about 0.0277 m. For an official target radius \(r\), the
  inverse solutions satisfy
  \(q_e=\pm\arccos((r^2-l_1^2-l_2^2)/(2l_1l_2))\): the magnitude is about
  \(150.07^\circ\) at 6 cm and \(49.46^\circ\) at 20 cm. Both are inside the
  elbow range. The associated shoulder offset is about \(22.33^\circ\) to
  \(56.25^\circ\), so at least one of the two branches supplies a shoulder
  angle inside \(\pm170^\circ\) for every target angle. Static reachability is
  therefore not the primary reason an official target should fail.
  **Decision relevance:** This can change whether initial research treats the
  problem as inverse-kinematic reachability or as trajectory and stabilization
  control; it also makes branch-conditioned diagnostics meaningful.
  **Assumptions:** The XML link frames and relative elbow convention are
  interpreted as written, the target remains in the stated plane, and the
  compiled joint limits do not remove configurations inside their declared
  ranges.
  **Source references:** `contracts/robots/two_joint_arm.xml:12-20`;
  `contracts/robots/two_joint_arm.py:5-8`;
  `contracts/scenario.md:9-12`;
  `robot_learning/scenario/observations.py:27-35`.
  **Discriminating evidence:** For a radius-angle grid, compute FK residuals
  for both inverse branches and record whether either joint-limit-respecting
  solution exists; compare that map with measured minimum distance and first
  reach step.

### Branch choice is a real configuration choice, not an orientation requirement

- **[Reasoned implication]** The task constrains only end-effector position, so
  elbow-up and elbow-down configurations are both valid physical solutions.
  The planar position Jacobian has determinant
  \(\det J=l_1l_2\sin q_e\); the official inverse solutions are away from both
  \(q_e=0\) and \(q_e=\pi\), so each target solution is locally full-rank even
  though the initial configuration is not. A continuous change from positive to
  negative \(q_e\) within the joint range must cross \(q_e=0\), where the
  endpoint radius is 22 cm. Since official targets have radius at most 20 cm,
  that crossing is at least 2 cm from a same-angle target and cannot occur
  inside the 1 cm hold ball. A policy that has entered a hold branch is thus
  physically unable to switch branches without interrupting the hold.
  **Decision relevance:** This can change whether a controller is evaluated as
  branch-selecting, branch-switching, or branch-robust, and whether hold
  failures are interpreted as local stabilization failures rather than missing
  an alternative solution.
  **Assumptions:** Joint motion is continuous, the end-effector is the site
  used by the success test, and the 1 cm criterion is applied to the target
  center rather than to the target sphere surface.
  **Source references:** `contracts/robots/two_joint_arm.xml:13-20`;
  `contracts/scenario.md:11-12`;
  `robot_learning/scenario/environment.py:75-81`;
  `robot_learning/scenario/observations.py:29-46`.
  **Discriminating evidence:** Log the sign and magnitude of \(q_e\), branch
  residuals, and hold interruptions throughout each episode; a successful
  uninterrupted hold should retain one elbow sign unless the evaluator permits
  a noncontinuous or differently defined state transition.

### The reset is a singular, fully extended launch state

- **[Reasoned implication]** At reset \(q_e=0\), so both Jacobian columns are
  tangent-aligned and the instantaneous position Jacobian has rank one.
  Radial motion from the 22 cm extension cannot be produced to first order by
  an infinitesimal joint velocity at that exact state; the controller must first
  bend the elbow. This makes initial motion geometry-dependent, especially for
  targets near the initial outward ray, and couples time-to-reach to the choice
  of elbow sign.
  **Decision relevance:** It can change the priority assigned to initial
  maneuvering, target-angle conditioning, and time remaining for the 2-second
  hold; a policy that reaches reliably from non-singular states would not
  establish success from the contractual reset.
  **Assumptions:** The reset state is applied before every official episode and
  no hidden reset perturbation or warm start is introduced.
  **Source references:** `robot_learning/scenario/environment.py:102-114`;
  `contracts/robots/two_joint_arm.xml:12-20`;
  `contracts/scenario.md:9-15`.
  **Discriminating evidence:** Measure the initial Jacobian rank, the sign and
  rate of early \(q_e\), end-effector radial velocity, and first-reach step
  stratified by target angle and radius.

### Direct torque control makes convergence and stabilization dynamic problems

- **[Reasoned implication]** The action is not a Cartesian displacement or joint
  setpoint. It applies a bounded generalized torque while the simulator
  advances for 20 ms. The joint dynamics therefore include inertial coupling,
  velocity-dependent terms, explicit viscous damping, and actuator saturation;
  a useful local form is
  \(M(q)\ddot q+C(q,\dot q)\dot q+0.5\dot q+\tau_{\rm limits}
  =5a\), with zero gravity and with \(M\) including the declared armature and
  compiled link inertias. A nonzero constant torque is not a static pose
  command in this gravity-free system: absent a balancing policy it produces
  motion, while holding requires reducing joint velocity and regulating the
  resulting Cartesian error.
  **Decision relevance:** This can change whether the first controller should
  emphasize velocity feedback, torque shaping, model-based prediction, or
  purely positional branch errors. It also determines whether action saturation
  and overshoot, rather than inverse-kinematic error, dominate failures.
  **Assumptions:** MuJoCo motor gear semantics apply directly, the current
  identity action adapter is used, and no unmodeled external force acts on the
  arm.
  **Source references:** `contracts/robots/two_joint_arm.xml:2,13-18,30-32`;
  `robot_learning/scenario/policy_io.py:8-16`;
  `robot_learning/scenario/environment.py:123-132`.
  **Discriminating evidence:** Record applied actions, inferred joint torques,
  joint velocities and accelerations, actuator saturation, and distance
  overshoot after entry into tolerance; compare these with a known-action
  step-response or impulse-response characterization.

### Reaching and holding are coupled, not separable stages

- **[Reasoned implication]** A first entry into the 1 cm ball is insufficient:
  entering with nonzero Cartesian velocity can be followed by an exit, which
  resets the hold counter. With a 20 ms control period, the latest possible
  first in-tolerance sample for a 100-sample uninterrupted hold is step 401
  of a 500-step episode. The controller must therefore converge early enough
  to leave a two-second low-error, low-velocity margin; a policy can have a
  good minimum distance and still fail the task.
  **Decision relevance:** This can change which diagnostics and training
  objectives are considered primary: first reach and minimum distance alone
  are not sufficient proxies for the official goal.
  **Assumptions:** The official hold counter has the stated consecutive-step
  semantics and the episode is not terminated for another reason before the
  hold completes.
  **Source references:** `contracts/scenario.md:11-15`;
  `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/environment.py:134-169`;
  `robot_learning/scenario/evaluation.py:55-95`.
  **Discriminating evidence:** Compare first-reach step, end-effector velocity
  at first reach, maximum consecutive held steps, interruption count, final
  distance, and whether success occurs exactly at the horizon.

### The target-angle distribution does not imply perfectly isotropic behavior

- **[Reasoned implication]** Link geometry and zero gravity are rotationally
  symmetric about the base only in the absence of joint limits and reset
  effects. The shoulder range stops short of a full revolution, the reset is
  fixed at \(q_s=0\), and the initial end effector points along \(+x\).
  Therefore target angle is a physically meaningful difficulty variable even
  though it is sampled uniformly; different angles can demand different
  shoulder travel, branch choices, or proximity to a limit.
  **Decision relevance:** This can change whether a single aggregate success
  percentage is trusted as evidence of uniform task capability and whether
  angle-stratified behavior is needed for selecting the next research
  direction.
  **Assumptions:** The declared shoulder range is enforced in the protected
  model and the reset is the same for all target angles.
  **Source references:** `contracts/robots/two_joint_arm.xml:9-18`;
  `robot_learning/scenario/environment.py:83-114`;
  `contracts/scenario.md:9-12`.
  **Discriminating evidence:** Bin episodes by target angle and inspect
  shoulder-limit proximity, chosen branch, torque saturation, first reach, and
  uninterrupted hold success.

### The task is free-space point regulation rather than manipulation

- **[Reasoned implication]** With zero gravity, disabled arm/plane collision,
  no target dynamics, and no target orientation requirement, success does not
  require force control, grasp closure, obstacle avoidance, or contact
  planning. The essential coupled capability is to move a two-DoF joint state
  from the extended reset through a feasible trajectory and regulate the
  two-dimensional endpoint inside a small tolerance.
  **Decision relevance:** This can change the value assigned to contact
  sensing, collision-aware planning, and force-control machinery relative to
  kinematic conditioning and velocity stabilization.
  **Assumptions:** The protected evaluator preserves the human-owned XML
  interaction semantics and does not add hidden obstacles or disturbances.
  **Source references:** `contracts/robots/two_joint_arm.xml:2,5-7,9-26`;
  `contracts/scenario.md:20-23`.
  **Discriminating evidence:** Inspect contact counts and forces, target
  motion, and external generalized forces during representative episodes; any
  nonzero interaction would revise this free-space model.

### The observation is close to a task-specific Markov state, but not a force state

- **[Reasoned implication]** Under a fixed deterministic MuJoCo model, joint
  positions, joint velocities, and target-relative displacement are sufficient
  to reconstruct the instantaneous endpoint error and predict the next state
  given an action and the model. The four branch errors expose both local
  inverse-kinematic alternatives. The observation does not reveal mass matrix,
  actuator torque, contact force, acceleration, or prior action, so it is not a
  direct dynamic-identification or force-feedback observation.
  **Decision relevance:** This can change the comparison between feed-forward,
  recurrent, model-based, and system-identification approaches. It also
  constrains claims that a policy has learned force or contact behavior.
  **Assumptions:** The model has no hidden actuator state, disturbance, or
  observation transformation not captured by the saved runtime.
  **Source references:** `robot_learning/scenario/observations.py:27-49`;
  `robot_learning/scenario/policy_io.py:8-16`;
  `contracts/policy_runtime.py:86-135`.
  **Discriminating evidence:** Test one-step prediction from repeated
  identical \((q,\dot q,p_E-p_T,a)\) states and compare residuals; inspect the
  saved observation callable and normalization used by the evaluated policy.

### Current training exposure omits the inner official radial range

- **[Reasoned implication]** The visible baseline training distribution
  \([0.14,0.20]\) m does not expose the policy to targets from 6--14 cm,
  although official assessment includes them. Inner targets require larger
  elbow magnitudes (about \(101.54^\circ\) at 14 cm up to \(150.07^\circ\) at
  6 cm) and different local Jacobian conditioning than the outer training
  range. This is an exposure mismatch, not evidence that a policy cannot
  generalize there.
  **Decision relevance:** It can change whether early campaign comparisons
  should be interpreted as control improvement or distribution coverage, and
  whether aggregate development scores are sufficient.
  **Assumptions:** The current training environment and its target sampler are
  used for the candidate being considered, while official assessment uses the
  full contract range.
  **Source references:** `robot_learning/training/environment.py:8-18`;
  `robot_learning/scenario/environment.py:83-97`;
  `contracts/task_spec.py:6`;
  `contracts/scenario.md:9-12`.
  **Discriminating evidence:** Evaluate the same policy with radius-stratified
  panels, report branch and hold diagnostics by radius, and compare those
  results with the actual training exposure.

### Physical quantities that can discriminate the mechanisms

- **[Reasoned implication]** The scientifically meaningful trajectory is not
  only binary success. It includes target \((r,\theta)\); \(q,\dot q\);
  endpoint position, velocity, and error; Jacobian rank/conditioning; inverse
  branch residuals and elbow sign; applied command and torque saturation;
  kinetic energy \(T=\frac12\dot q^\mathsf{T}M(q)\dot q\); damping loss;
  first-reach time; minimum and final distance; consecutive hold length; and
  hold interruptions. Together these distinguish geometric infeasibility,
  initial-singularity delay, dynamic overshoot, limit/saturation behavior, and
  local stabilization failure.
  **Decision relevance:** These quantities can change causal interpretation of
  a binary success difference and identify which physical capability remains
  limiting before a new policy or reward is selected.
  **Assumptions:** The relevant state and command traces can be recorded
  without changing the saved controller or protected task semantics, and
  compiled \(M(q)\) is available when energy is required.
  **Source references:** `robot_learning/scenario/evaluation.py:48-96`;
  `robot_learning/scenario/observations.py:27-49`;
  `contracts/robots/two_joint_arm.xml:13-32`.
  **Discriminating evidence:** A trajectory-level artifact containing these
  quantities, aligned to target geometry and branch, can be checked against
  the failure-class predictions above; binary success alone cannot.

## Unknowns

### Compiled masses, inertias, integration defaults, and limit response

- **[Unresolved quantity]** The XML does not state body masses, body inertial
  tensors, geom density, integrator choice, or joint-limit solver parameters.
  MuJoCo will compile a definite model under the pinned version, but the
  numeric \(M(q)\), natural time scales, effective damping ratio, and behavior
  at a range boundary are not established by the human-authored numbers in
  this repository.
  **Decision relevance:** These values could change action scaling, model-based
  predictions, expected settling time, saturation risk, and whether a
  controller that is stable in one local configuration remains stable across
  the target annulus.
  **Assumptions:** The omitted MuJoCo defaults materially contribute relative
  to the explicit armature and damping, and no separate compiled-model
  artifact is already authoritative.
  **Source references:** `contracts/robots/two_joint_arm.xml:1-33`;
  `AGENTS.md`, “Environment”.
  **Discriminating evidence:** Inspect the loaded `MjModel` mass and inertia
  arrays and integration/limit options, then compare measured torque-to-
  acceleration and free-decay responses across representative configurations.

### Effective protected control and hold sampling semantics

- **[Unresolved quantity]** The visible research environment holds one command
  over ten 2 ms steps and checks distance once per control interval. The
  contracts establish the official 50 Hz/100-step duration, but the protected
  evaluator implementation and whether it checks only control boundaries or
  also internal physics substeps are not visible in the scientific sources.
  The saved-runtime contract does establish that the protected environment
  calls the saved action adapter and then validates and clips its result; what
  remains unknown here is the protected substep hold check and the
  candidate-specific adapter behavior.
  **Decision relevance:** A policy can pass boundary samples while crossing
  outside the tolerance between them; the distinction could change the
  interpretation of hold stability, required action frequency, and the value
  of substep trajectory diagnostics.
  **Assumptions:** The protected implementation may differ from the visible
  research environment despite sharing the human contract and timing.
  **Source references:** `contracts/scenario.md:11-15`;
  `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/environment.py:123-169`;
  `contracts/instruments.md`, “Saved controller execution”.
  **Discriminating evidence:** Compare official/task-reference outcomes with
  substep-resolved endpoint traces for trajectories that approach the
  tolerance boundary, and verify the exact saved runtime callable and
  evaluator command path.

### Candidate-specific observation and action transformations

- **[Unresolved quantity]** The default source path is identity action plus the
  11-value observation, but a saved runtime may contain frozen policy I/O
  callables and an observation normalizer. Before inspecting a particular
  candidate, it is unresolved whether its effective policy input and physical
  command are exactly the visible defaults.
  **Decision relevance:** This could change reproducibility between research
  evaluation and protected assessment and could make an apparent learning or
  control improvement a runtime-interface change instead.
  **Assumptions:** Candidate artifacts are allowed to use the runtime
  persistence mechanism and the protected evaluator executes that saved
  runtime as specified.
  **Source references:** `contracts/policy_runtime.py:18-36,86-135`;
  `robot_learning/scenario/policy_io.py:8-16`;
  `contracts/instruments.md`, “Saved controller execution”.
  **Discriminating evidence:** Verify runtime and weights fingerprints, inspect
  the serialized I/O and normalization metadata, and record the post-adapter
  command actually applied to `data.ctrl`.

### Geometry-conditioned capability and branch occupancy

- **[Unresolved quantity]** No pre-campaign evidence establishes how success,
  first reach, hold interruptions, or selected elbow branch vary with target
  radius and angle. The kinematic model shows that solutions exist; it does
  not establish that a learned policy can find and stabilize them from the
  singular reset.
  **Decision relevance:** This is the main uncertainty in deciding whether the
  first campaign gap is coverage, trajectory generation, torque regulation, or
  hold stabilization. A high aggregate score could conceal a systematic
  failure region.
  **Assumptions:** The policy is evaluated from the contractual reset on the
  official target distribution and enough episode diagnostics are retained to
  condition outcomes.
  **Source references:** `contracts/scenario.md:9-15`;
  `robot_learning/scenario/environment.py:102-169`;
  `robot_learning/scenario/evaluation.py:55-96`.
  **Discriminating evidence:** Use matched radius-angle panels and inspect
  success, first-reach step, minimum/final distance, elbow sign, saturation,
  and uninterrupted hold length for every episode.

### Actual dynamic margin during the two-second hold

- **[Unresolved quantity]** The explicit tolerance is 1 cm, but the available
  contracts do not establish the distribution of endpoint velocity, residual
  oscillation, torque margin, or distance-to-boundary margin when a policy
  first enters and then holds. The presence of damping does not by itself
  establish a settling time or a stable closed-loop response.
  **Decision relevance:** This could change whether the dominant gap is
  convergence before the horizon, low-velocity capture, or robustness to
  residual oscillation; those gaps imply different scientific comparisons.
  **Assumptions:** The learned policy is deterministic at assessment and the
  simulator state/command trace can be observed without changing it.
  **Source references:** `contracts/robots/two_joint_arm.xml:13-18`;
  `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/environment.py:134-169`.
  **Discriminating evidence:** Measure endpoint velocity and distance margin
  throughout the 100 held steps, not only at first entry and termination; a
  stable margin that persists across radii and angles would weaken the
  residual-oscillation explanation.

### Protected target measure and panel realization beyond the contract

- **[Unresolved quantity]** The visible sampler draws radius and angle
  independently and uniformly, while the human contract states the official
  distribution in words and fixes a protected 200-episode panel. The precise
  protected sampler implementation, panel realization, and any distinction
  between uniform radial distance and uniform area are not exposed here; the
  contract, not the visible research sampler, remains authoritative.
  **Decision relevance:** This could change how representative a development
  panel is and how radius-conditioned evidence is mapped to the official
  98% objective.
  **Assumptions:** The protected benchmark is not byte-for-byte identical to
  the visible environment sampler, and development results are not pooled with
  the official panel.
  **Source references:** `contracts/scenario.md:9-18`;
  `robot_learning/scenario/environment.py:83-97`;
  `contracts/task_spec.py:6`.
  **Discriminating evidence:** Inspect the protected task-reference/official
  sampling metadata or compare a sufficiently documented target sample against
  both candidate measures; do not infer it from aggregate success.

## Decision-relevant synthesis

### Feasibility is not the expected first bottleneck

- **[Reasoned implication]** The official annulus has valid inverse solutions on
  at least one elbow branch for every target angle, but reset begins at a
  rank-deficient 22 cm extension. **Decision relevance:** The first campaign
  decision can change between solving reachability and diagnosing
  singularity-exit, branch selection, and trajectory timing. **Assumptions:**
  The declared kinematics and limits are the protected ones and no hidden
  disturbance makes a statically reachable target dynamically unreachable.
  **Source references:** `contracts/robots/two_joint_arm.xml:9-20`;
  `contracts/scenario.md:9-12`;
  `robot_learning/scenario/environment.py:102-114`.
  **Discriminating evidence:** Radius-angle inverse-kinematic feasibility,
  initial Jacobian rank, early elbow motion, and first-reach distributions.

### Compiled dynamics can change the control problem materially

- **[Unresolved quantity]** Link mass/inertia and MuJoCo integration/limit
  defaults are not explicitly authored, while commands are bounded direct
  torques with explicit damping and armature. **Decision relevance:** This can
  change whether the initial direction is torque-limited, whether trajectories
  overshoot, and which control or model-identification assumptions are
  credible. **Assumptions:** Omitted compiler defaults are large enough to
  matter over the 20 ms action interval and are shared by assessment.
  **Source references:** `contracts/robots/two_joint_arm.xml:2,13-19,30-32`;
  `AGENTS.md`, “Environment”.
  **Discriminating evidence:** Compiled \(M(q)\), option/limit inspection, and
  known-action acceleration/free-decay measurements.

### The success bottleneck may be stabilization rather than first contact

- **[Reasoned implication]** A single 1 cm entry does not count; 100
  uninterrupted control samples are required, and entry with residual velocity
  can reset the counter. **Decision relevance:** First campaign comparisons
  should be capable of distinguishing reach, convergence, and hold failure;
  minimum distance or reward alone cannot establish progress toward 98%
  episode success. **Assumptions:** The protected evaluator uses the stated
  consecutive-step semantics and the 10-second horizon. **Source references:**
  `contracts/scenario.md:11-15`; `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/evaluation.py:55-96`.
  **Discriminating evidence:** First-reach time, endpoint velocity, distance
  margin, hold interruptions, maximum held steps, and success stratified by
  radius and angle.

### The saved runtime is part of the physical experiment

- **[Unresolved quantity]** The visible default exposes near-complete joint
  kinematic state and maps actions directly, but candidate runtimes can freeze
  different I/O and normalization behavior. **Decision relevance:** A policy
  result can otherwise be misread as a morphology or controller result when
  the effective observation/action interface changed between training and
  assessment. **Assumptions:** Protected evaluation follows the saved-runtime
  contract and candidate artifacts may contain non-default callables.
  **Source references:** `robot_learning/scenario/observations.py:27-49`;
  `robot_learning/scenario/policy_io.py:8-16`;
  `contracts/policy_runtime.py:86-135`;
  `contracts/instruments.md`, “Saved controller execution”.
  **Discriminating evidence:** Runtime fingerprint and callable inspection,
  normalization metadata, and the actual post-adapter `data.ctrl` trace.

### Official coverage includes a radial region absent from the visible baseline

- **[Repository fact]** The current training recipe samples 14--20 cm but the
  official task includes 6--20 cm. **Decision relevance:** Early evidence can
  change interpretation depending on whether failure is concentrated in the
  unseen inner annulus; aggregate success should not be treated as a uniform
  capability claim without that discriminator. **Assumptions:** The candidate
  uses the current training environment and official assessment uses the
  immutable full range. **Source references:**
  `robot_learning/training/environment.py:8-18`;
  `contracts/task_spec.py:6`;
  `contracts/scenario.md:9-18`.
  **Discriminating evidence:** Radius-stratified matched evaluation with
  branch, first-reach, saturation, and hold diagnostics, keeping development
  panels distinct from the official 200-episode result.
