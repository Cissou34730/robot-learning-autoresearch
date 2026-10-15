## Established facts

### Robot morphology and coordinates

- **[Repository fact]** The robot is a fixed-base, planar serial arm with two
  revolute degrees of freedom: a shoulder hinge and an elbow hinge, both about
  the world/local \(z\) axis. The upper arm is 0.12 m and the forearm is
  0.10 m; the end-effector site is at the forearm tip. The arm plane is
  \(z=0.02\) m. **Source:** `contracts/robots/two_joint_arm.xml`,
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`).
- **[Repository fact]** Each joint declares a range of -170 to 170 degrees.
  The base and all visual geoms are fixed or non-contacting for this task:
  the plane, base, links, and target have `contype="0"` and
  `conaffinity="0"` where applicable. **Source:**
  `contracts/robots/two_joint_arm.xml`.
- **[Reasoned implication]** With joint coordinates \(q=(q_1,q_2)\), the
  end-effector position is
  \[
  p(q)=(0.12\cos q_1+0.10\cos(q_1+q_2),
        0.12\sin q_1+0.10\sin(q_1+q_2),0.02).
  \]
  Thus the robot has two configuration variables for two target-plane
  coordinates, no out-of-plane authority, and no grasp or contact mode.
- **[Reasoned implication]** The unconstrained planar workspace is the annulus
  between radii \(|0.12-0.10|=0.02\) m and \(0.22\) m. The joint limits carve
  that annulus by removing configurations, rather than changing the link
  lengths. The official radial interval, 0.06--0.20 m, lies inside the
  unconstrained annulus.
- **[Reasoned implication]** The differential map is
  \(J(q)=\partial(x,y)/\partial(q_1,q_2)\), with determinant
  \(0.12\cdot0.10\sin q_2\). Near a straight or fully folded posture,
  Cartesian motion becomes poorly conditioned and joint motion can create
  little or highly directional end-effector motion. The official radial
  bounds imply the inverse-kinematic elbow angle is approximately
  49.5--150.8 degrees in magnitude, so the sampled targets avoid the exact
  \(q_2=0\) and \(q_2=\pm\pi\) singular postures, although conditioning still
  varies with radius.

### Actuation and simulator timing

- **[Repository fact]** The two actuators are MuJoCo `motor` actuators
  attached directly to the shoulder and elbow. Their control range is
  \([-1,1]\), and each has gear 5. The environment clips the policy output
  to that same interval before writing it to `data.ctrl`. **Source:**
  `contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`
  (`step`).
- **[Reasoned implication]** The action is a bounded generalized motor command,
  not a desired joint position, velocity, or Cartesian point. Under the
  standard direct joint transmission, the commanded actuator contribution is
  approximately \(\tau_i=5u_i\) in the corresponding joint coordinate, with
  the sign set by the actuator transmission. The policy therefore has direct
  feedback control authority over both coordinates but no independent
  feed-forward access to acceleration or force beyond this bounded command.
- **[Repository fact]** MuJoCo integrates at 0.002 s per physics step. The
  environment holds one action constant for 10 physics steps, so the policy
  control period is 0.020 s (50 Hz). The required hold is 2.0 s, implemented
  as 100 consecutive control steps; the episode horizon is 500 control steps
  (10 s at the current timing). **Source:**
  `contracts/robots/two_joint_arm.xml`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** Gravity is explicitly zero. Joint damping is 0.5 and
  joint armature is 0.01 for both joints. **Source:**
  `contracts/robots/two_joint_arm.xml`.
- **[Reasoned implication]** Between policy updates the arm evolves under
  held motor commands for 20 ms. Damping dissipates velocity, while armature
  adds reflected rotational inertia; both affect how far a command carries the
  arm after the policy changes action. The 50 Hz loop is therefore a sampled
  feedback controller around a faster continuous-time approximation, and
  the hold requirement tests closed-loop stabilization rather than only
  reaching.
- **[Repository fact]** The XML does not explicitly specify link masses,
  inertias, friction, actuator force limits, integrator, solver settings, or
  contact parameters. **Source:**
  `contracts/robots/two_joint_arm.xml`.
- **[Reasoned implication]** Because contacts and gravity are absent, the
  important dynamic competition is motor authority versus compiled link
  inertia, armature, and damping, plus numerical integration. There is no
  environmental load that must be rejected. At a perfectly stationary
  configuration, zero gravity and zero command make a zero-velocity
  equilibrium plausible; maintaining a nonzero-error boundary condition
  still requires feedback because motion and prior command can carry the site
  outside the tolerance.

### Reset state, target geometry, and outcome

- **[Repository fact]** Reset calls `mj_resetData`, then sets both joint
  positions and velocities to zero, forwards the model, and samples a target
  with angle uniformly from \([-\pi,\pi]\) and radius uniformly from
  \([0.06,0.20]\) m. The target \(z\) is set to the current end-effector
  \(z\), so it is in the arm plane. **Source:**
  `robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`);
  `contracts/task_spec.py`.
- **[Reasoned implication]** The initial end effector is
  \((0.22,0,0.02)\) m. Episode variation is therefore target geometry, not
  randomized physical state: every episode starts from the same rest
  configuration and must acquire a new target-relative trajectory.
- **[Repository fact]** The implementation samples radius and angle
  independently uniformly; this is uniform in radius, not uniform by area.
  The target is fixed during an episode because only reset samples it.
  **Source:** `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`.
- **[Repository fact]** Success is true only when the end-effector distance
  to the target is at most 0.01 m at 100 consecutive control observations.
  Any observation outside the tolerance resets the held counter to zero.
  Reaching the count terminates the episode; otherwise 500 control steps
  truncate it. The official assessment uses one frozen policy over 200
  episodes and requires at least 196 successes. **Source:**
  `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`.
- **[Reasoned implication]** The task is a point-to-point reach followed by
  uninterrupted positional stabilization. Since there is no contact or
  object dynamics, “hold” means keeping the site inside a 1 cm Cartesian
  disk, not exerting a force on an external object.
- **[Repository fact]** The scenario reward includes distance progress,
  closeness, hold-progress, an action cost, an outside-band penalty after a
  hold interruption, and a completion bonus, but the task outcome is the
  success/hold rule above. **Source:** `robot_learning/training/reward.py`;
  `robot_learning/scenario/environment.py`.

### Observation and control-loop information

- **[Repository fact]** The default observation has 11 float32 values:
  two joint positions, two joint velocities, the three-dimensional
  end-effector-minus-target vector, and four wrapped joint errors to the
  open-elbow and folded-elbow inverse-kinematic solutions. The policy action
  mapping is the identity; optional runtime normalization acts on the
  observation, not on the physical command. **Source:**
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.
- **[Reasoned implication]** Joint position and velocity are directly
  observable in the default interface. The relative target vector makes
  Cartesian distance and direction observable; together with the known fixed
  base and current forward kinematics it also permits reconstruction of the
  target position. The target is therefore not hidden in the default task,
  even though its absolute coordinates are not a separate observation field.
- **[Repository fact]** The four inverse-kinematic errors are derived using
  link lengths, `arccos` with clipping, a shoulder-angle formula, and
  wrap-to-\(\pi\). They do not expose a branch label, actuator force,
  acceleration, contact force, simulator time, held-step counter, or previous
  action. **Source:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
- **[Reasoned implication]** The policy can infer distance, target bearing,
  local motion, and proximity to either nominal IK branch, but it must infer
  hold progress and episode phase from history or recurrent state. It cannot
  directly compensate from measured torque or acceleration. A policy can
  choose either branch and can switch configurations, but branch switching
  creates a transient trajectory that must remain controlled.
- **[Repository fact]** Each action is predicted from the current observation,
  passed through the saved policy runtime, clipped, held for 10 MuJoCo steps,
  and then followed by a new observation and distance-based hold update.
  **Source:** `contracts/policy_runtime.py`;
  `robot_learning/scenario/environment.py`.

## Physical consequences

### Reachability, branch choice, and trajectory control

- **[Reasoned implication]** For a target \((r,\theta)\), the two nominal IK
  branches satisfy
  \[
  q_2=\pm\arccos\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)}
  \]
  and
  \(q_1=\theta-\operatorname{atan2}(0.10\sin q_2,
  0.12+0.10\cos q_2)\). Thus the same target generally has elbow-open and
  elbow-folded solutions. The declared joint limits can remove one branch
  for some angular sectors, but the official radial interval keeps
  \(|q_2|\leq150.8^\circ\); selecting the branch whose shoulder offset moves
  inward from the \(\pm180^\circ\) boundary leaves at least one admissible
  branch for the official set, subject to the simulator's limit enforcement.
- **Decision relevance:** This can change whether startup treats branch
  selection as a planning variable, a source of multimodal policy behavior,
  or a negligible issue.
- **Assumptions:** The planar forward-kinematic equations, the declared
  ranges, and standard hinge-range semantics apply; no unmodeled collision or
  target constraint removes a solution.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Compute both IK branches for a dense grid of
  official radii and angles, reject configurations outside the compiled joint
  ranges, and compare the surviving branch with the target reached by
  forward simulation.

- **[Reasoned implication]** Reaching is not equivalent to commanding the IK
  angle once. The action is torque-like and sampled at 50 Hz, so the policy
  must generate a time trajectory that manages velocity and overshoot while
  approaching a branch. Near a Jacobian-conditioned posture, a small joint
  error can produce a tolerance-sized Cartesian error in one direction and
  little error in another.
- **Decision relevance:** This can change the initial preference between
  direct Cartesian/IK-shaped control and purely model-free exploration.
- **Assumptions:** The relevant behavior is dominated by the stated 2R
  kinematics and sampled motor dynamics, rather than hidden noise or contact.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Record joint trajectories, end-effector
  distance, velocity, action saturation, and Jacobian conditioning during
  approach on targets spanning radius and angle.

### Stabilization and complete hold

- **[Reasoned implication]** A successful controller must converge into the
  1 cm disk and keep the Cartesian error there for 2 s. A controller that
  reaches quickly but rings across the boundary fails exactly like one that
  never reaches. Damping helps dissipate motion, while excessive command near
  the target can create repeated boundary crossings; the hold is consequently
  a test of low-amplitude feedback, not just target acquisition.
- **Decision relevance:** This can change whether the first performance
  diagnosis focuses on reach time or on local regulation and whether success
  should be decomposed into approach and hold behavior.
- **Assumptions:** The 0.002 s integration and 0.020 s control period are the
  authoritative timing, and the distance test is evaluated only after each
  held action interval.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`; `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence:** Compare first-entry time, maximum uninterrupted
  held steps, interruption count, final distance, and distance/velocity
  traces; distinguish a first-entry failure from a boundary-crossing failure.

- **[Reasoned implication]** The tolerance is a Cartesian disk, so allowable
  joint error is configuration-dependent through \(J(q)\). A controller can
  remain within the disk while moving along a locally insensitive joint
  direction, but it cannot rely on a single joint tolerance across all
  targets. The two nominal branches also provide distinct local stabilizing
  equilibria.
- **Decision relevance:** This can change whether branch-conditioned errors,
  target-radius conditioning, or Cartesian error feedback is important for
  reaching the 98% requirement rather than merely improving average reward.
- **Assumptions:** The target is stationary and the arm remains in the
  non-contacting planar model.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Bin hold success and interruption rates by
  target radius, angle, selected IK branch, and local singular-value ratio of
  the planar Jacobian.

### Observability, recurrence, and outcome

- **[Reasoned implication]** The observation is close to full task state for
  this deterministic simulator: it contains \(q,\dot q\), the Cartesian
  target error, and branch-relative geometric features. The missing hold
  counter and time index matter only for history-dependent decisions such as
  recognizing a recent interruption or allocating the remaining horizon.
  A memoryless controller can still regulate the current physical state, but
  a recurrent controller may represent episode phase and prior boundary
  crossings.
- **Decision relevance:** This can change whether policy memory, explicit
  phase features, or state-only control should be considered a first-order
  capability.
- **Assumptions:** The runtime preserves the observation/action functions and
  any recurrent state as specified; there is no hidden evaluator observation
  change.
- **Source references:** `robot_learning/scenario/observations.py`;
  `contracts/policy_runtime.py`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Compare policies with and without recurrence
  under matched seeds, and inspect whether failures follow identical current
  observations but different preceding hold histories.

- **[Reasoned implication]** The outcome is a thresholded temporal event, so
  mean distance, reward, or minimum distance alone cannot certify success.
  One excursion after 99 valid control intervals destroys the entire episode,
  and the official target is an episode-level 196/200 count.
- **Decision relevance:** This can change model selection: the relevant
  criterion is uninterrupted episode success and its failure modes, not a
  smooth proxy or a short successful prefix.
- **Assumptions:** The official distribution and protected evaluator use the
  contract's exact hold and panel semantics.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Preserve per-episode success, maximum held
  run, interruptions, and termination/truncation status on panels with the
  official radius-angle distribution.

### Dynamic authority and simulator uncertainty

- **[Reasoned implication]** Larger actions can accelerate correction but also
  consume the bounded torque authority and inject kinetic energy that must be
  dissipated before the hold. The physically meaningful tradeoff is therefore
  convergence rate versus overshoot and residual velocity, with damping and
  inertia setting the response time scale.
- **Decision relevance:** This can change the value of action scaling, torque
  regularization, curriculum over radius, and diagnostics of saturation.
- **Assumptions:** The direct motor transmission and compiled inertial
  parameters are the dominant dynamic terms.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `robot_learning/training/reward.py`.
- **Discriminating evidence:** Apply controlled small and saturated commands
  from known configurations; identify acceleration, velocity decay, settling
  time, and actual actuator saturation from the compiled MuJoCo state.

- **[Reasoned implication]** The absence of gravity and contact makes the
  task scientifically cleaner but less representative of a loaded or
  interacting robot. A policy can exploit this free-space equilibrium and
  cannot be assumed to transfer to external loads, friction, sensing noise,
  or latency not present here.
- **Decision relevance:** This can change the scope of any claim: the
  campaign can target the official simulator objective, but robustness or
  physical-robot transfer would require separate evidence.
- **Assumptions:** The official benchmark does not inject additional
  perturbations beyond the visible source-defined environment.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `contracts/scenario.md`.
- **Discriminating evidence:** Inspect compiled model options and run
  controlled perturbation/noise/load sensitivity tests; do not infer
  real-robot robustness from official success alone.

### Scientifically meaningful quantities

- **[Reasoned implication]** Across a complete episode, the most informative
  physical quantities are target radius and angle; \(q,\dot q\); end-effector
  position and Cartesian error; Jacobian conditioning; command magnitude and
  saturation; first-entry time; uninterrupted held-run length; interruption
  count; final distance; and termination versus truncation. These quantities
  separate geometric reachability, trajectory control, convergence, and
  stabilization.
- **Decision relevance:** This can change whether a low score is attributed
  to workspace/branch geometry, dynamic authority, timing, or hold control.
- **Assumptions:** The measurements are sampled at sufficient resolution to
  identify excursions between policy observations, or the limitation is
  explicitly retained.
- **Source references:** `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Use episode diagnostics together with
  per-control-step traces; current evaluation already records target geometry,
  minimum/final distance, first reach, maximum held steps, in-tolerance steps,
  and interruptions, but not all joint/dynamic quantities.

## Unknowns

### Compiled inertial and numerical parameters

- **[Unresolved quantity]** The XML leaves masses, inertias, density-derived
  body properties, integrator choice, solver settings, and numerical
  tolerances to MuJoCo defaults or compilation. Their exact compiled values
  and their effect on settling time are not established by the repository
  text alone.
- **Decision relevance:** These values could change whether the current 50 Hz
  controller has sufficient authority and whether a policy's apparent
  stability is robust to numerical response details.
- **Assumptions:** The effective compiled model, not only the XML literals,
  determines the dynamics encountered by training and assessment.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md` (locked MuJoCo version); `pyproject.toml`.
- **Discriminating evidence:** Inspect the compiled `MjModel` fields and run
  zero-command decay and controlled-step identification at representative
  configurations. Revise the dynamic model if those measurements disagree
  with the inferred time scale.

### Effective actuator limits and joint-limit behavior

- **[Unresolved quantity]** The source fixes `ctrlrange` and gear but does not
  explicitly state force limits, transmission sign conventions beyond the
  joint attachment, or the numerical behavior when a joint approaches its
  range. It is not yet established how often a learned policy saturates or
  encounters a limit in official episodes.
- **Decision relevance:** This could change whether failures are caused by
  insufficient actuation, poor trajectory choice, or boundary interactions,
  and could change the usefulness of action penalties.
- **Assumptions:** MuJoCo's installed motor and hinge semantics implement the
  intended direct transmission and declared range.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md`.
- **Discriminating evidence:** Read compiled actuator and joint-limit fields,
  apply positive and negative commands from known states, and log control,
  generalized force, \(q\), and \(q\)-limit proximity.

### Actual policy state and runtime preprocessing

- **[Unresolved quantity]** The physical interface is defined, but no campaign
  policy evidence yet establishes whether a candidate uses recurrence,
  observation normalization, or a branch-consistent control strategy, nor
  whether its saved runtime exactly preserves those choices in assessment.
- **Decision relevance:** This could change whether an observed failure is a
  physical capability gap or a policy/runtime mismatch, and whether
  recurrence or normalization is a plausible first research direction.
- **Assumptions:** The saved runtime is validated and its frozen observation
  and action callables are the ones used in evaluation.
- **Source references:** `contracts/policy_runtime.py`;
  `robot_learning/scenario/policy_io.py`;
  `robot_learning/training/normalization.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Inspect the saved runtime metadata and
  candidate architecture, then compare raw observations, normalized inputs,
  recurrent state resets, and physical actions on identical seeded episodes.

### Distributional difficulty and branch occupancy

- **[Unresolved quantity]** The target law is defined, but before campaign
  evidence it is unknown which radii, angles, IK branches, and initial
  trajectories dominate failures. It is also unknown whether both branches
  are used or whether one branch is dynamically easier under the compiled
  model.
- **Decision relevance:** This could change whether the first development
  measurement should stratify by geometry, diagnose branch selection, or
  evaluate aggregate success only.
- **Assumptions:** Target samples are independent and follow the source-defined
  uniform-radius/uniform-angle law; no hidden task randomization is active.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`;
  `robot_learning/training/environment.py`.
- **Discriminating evidence:** Record target geometry, selected branch
  proximity, trajectory and success for a sufficiently broad seeded panel;
  compare failure rates across radius-angle bins without treating a bin
  difference as a causal explanation by itself.

### Between-observation behavior and numerical excursions

- **[Unresolved quantity]** Success is checked after each 20 ms held-action
  interval, not continuously within the ten internal physics steps. The
  repository does not establish whether a trajectory can leave and re-enter
  the tolerance between checks, nor whether this matters for candidate
  policies.
- **Decision relevance:** This could change interpretation of “continuous”
  hold and the need for higher-rate diagnostics or a stricter measurement
  of physical excursions.
- **Assumptions:** The contract's authoritative control-step semantics are
  the intended official definition, even if substep traces reveal additional
  motion.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Capture end-effector distance at every MuJoCo
  substep for hold attempts and compare it with the environment's
  control-step counter; revise only the interpretation, not the official
  success rule, if hidden substep excursions occur.

### Noise, latency, and physical transfer

- **[Unresolved quantity]** No source-defined sensor noise, action latency,
  model randomization, gravity, load, or contact disturbance is present in
  the visible implementation, but the relevance of such effects to the
  human's broader robotics intent is unknown. Official success cannot
  establish robustness outside this simulator.
- **Decision relevance:** This could change whether the campaign optimizes
  only the fixed benchmark or also values robustness-oriented diagnostics;
  it must not silently redefine the official objective.
- **Assumptions:** The protected benchmark follows the human-owned contract
  and does not add undocumented physical perturbations.
- **Source references:** `contracts/scenario.md`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md`.
- **Discriminating evidence:** Verify protected-task semantics and, separately,
  measure sensitivity to controlled observation/action perturbations or
  parameter changes. Such evidence would support a transfer claim, not
  alter official scoring.

## Decision-relevant synthesis

### [Reasoned implication] Hold stability is the immediate physical bottleneck

- **Decision relevance:** The objective is 196 uninterrupted 2 s holds, so
  fast reach without low-amplitude stabilization is not sufficient.
- **Assumptions:** The 50 Hz control period, 100-step hold, 1 cm threshold,
  and reset-on-excursion semantics are authoritative.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Per-episode first-entry time, maximum held
  run, interruption count, final distance, and substep distance/velocity
  traces, separated into approach and hold failures.

### [Reasoned implication] Geometry likely supports branch-conditioned solutions

- **Decision relevance:** The 2R arm has two nominal IK branches and the
  observation exposes errors to both; branch choice may be a major source
  of trajectory and stability variation.
- **Assumptions:** Standard planar kinematics and compiled joint limits apply;
  the official radial interval remains within at least one admissible branch
  for every target.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Grid-check admissible IK solutions, then
  stratify observed success and hold interruptions by branch proximity,
  radius, angle, and Jacobian conditioning.

### [Unresolved quantity] Dynamic authority is specified only partially

- **Decision relevance:** Gear 5, damping 0.5, armature 0.01, and 20 ms
  action holding define a plausible response scale, but omitted compiled
  inertias and solver defaults could alter overshoot and settling enough to
  change the first control strategy.
- **Assumptions:** The installed MuJoCo compilation is the operative physical
  model and no hidden loads are added.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md`.
- **Discriminating evidence:** Compiled-model inspection plus controlled
  command-response measurements of acceleration, saturation, decay, and
  settling across representative configurations.

### [Reasoned implication] The observation is physically rich but not temporally complete

- **Decision relevance:** \(q,\dot q\), target-relative error, and IK
  features make geometric feedback available, while held-step count,
  previous action, and episode time are absent. The first policy decision
  should therefore distinguish a current-state regulation deficit from a
  memory/phase deficit.
- **Assumptions:** The frozen runtime uses the documented 11-value observation
  and resets policy state at episode boundaries.
- **Source references:** `robot_learning/scenario/observations.py`;
  `contracts/policy_runtime.py`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Matched seeded comparisons of memoryless and
  recurrent policies, with identical current-state observations checked
  against different preceding hold histories.

### [Reasoned implication] Official performance must be interpreted as an episode distribution

- **Decision relevance:** The uniform-radius, full-angle target law and
  196/200 panel make aggregate reward or a favorable development subset
  insufficient evidence for the human goal.
- **Assumptions:** Development panels remain distinct from the fixed official
  panel and the protected evaluator uses the contract exactly.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Seeded, non-overlapping panels with per-geometry
  diagnostics and final frozen-policy assessment; retain the physical failure
  class rather than reporting success percentage alone.
