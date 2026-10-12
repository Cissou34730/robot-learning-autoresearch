## Established facts

### Source register and system boundary

- **[Repository fact]** The official system is a two-joint arm reach-and-hold task. The
  robot, physics, interaction semantics, target distribution, and success definition
  are immutable human-owned definitions; no campaign result is used in this model.
  **Sources:** `contracts/scenario.md` (Official task, Immutable task boundary);
  `contracts/robots/two_joint_arm.xml`; `contracts/task_spec.py`.

- **[Repository fact]** The model below uses `[RF]` for repository fact,
  `[RI]` for reasoned implication, and `[UQ]` for unresolved quantity. Source
  references identify the implementation or contract that must be rechecked if a
  definition changes.

### Morphology, coordinates, and kinematics

- **[Repository fact]** The fixed base has no joint. The upper arm and forearm are
  serial bodies with one hinge each: `shoulder` and `elbow`, both rotating about
  the world/body z axis. Their lengths are 0.12 m and 0.10 m, respectively. The
  end-effector site is at the distal end of the forearm. Both links lie in the
  horizontal z = 0.02 m plane; the visible plane geom is not a support or contact
  surface because its contact types are disabled. **Sources:**
  `contracts/robots/two_joint_arm.xml` (`worldbody`, `upper_arm`, `forearm`,
  `end_effector`).

- **[Repository fact]** The generalized configuration is
  \(q=(q_s,q_e)\), where the elbow angle is relative to the upper arm. With
  \(L_1=0.12\) m and \(L_2=0.10\) m, the end-effector forward kinematics are
  \(x=L_1\cos q_s+L_2\cos(q_s+q_e)\),
  \(y=L_1\sin q_s+L_2\sin(q_s+q_e)\), and \(z=0.02\) m. The arm therefore has
  two planar degrees of freedom and a two-dimensional planar task pose; it has
  no commanded orientation degree of freedom. **Sources:**
  `contracts/robots/two_joint_arm.xml`; `contracts/robots/two_joint_arm.py`.

- **[Repository fact]** Each hinge declares a joint range of -170 to +170 degrees.
  The nominal action has two components in [-1, 1], one for each motor. **Sources:**
  `contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`
  (`action_space`, action clipping).

- **[Repository fact]** The nominal geometric reach without joint limits is the
  annulus from \(|L_1-L_2|=0.02\) m to \(L_1+L_2=0.22\) m. Targets are placed in
  the same z plane at radii 0.06--0.20 m and all azimuths. The radius and azimuth
  are sampled independently and uniformly in the visible scenario implementation,
  so this is not a distribution uniform in planar area. **Sources:**
  `contracts/task_spec.py` (`TARGET_RADIUS_RANGE`);
  `robot_learning/scenario/environment.py` (`_sample_target_position`).

### Actuation, simulator, and timing

- **[Repository fact]** MuJoCo is configured with zero gravity and a 0.002 s
  physics timestep. Each policy action is assigned to `data.ctrl` and held while
  ten `mj_step` calls execute, giving a 0.020 s control interval. **Sources:**
  `contracts/robots/two_joint_arm.xml` (`option`);
  `robot_learning/scenario/environment.py` (`frame_skip`, `step`).

- **[Repository fact]** Each actuator is a MuJoCo `motor` attached directly to a
  hinge with `gear="5"` and control range [-1, 1]. The environment's policy-action
  mapping is the identity before clipping. Under the standard MuJoCo motor
  transmission, a command \(u_i\) produces nominal joint torque
  \(\tau_i=5u_i\) in the actuator's transmitted coordinate, with no declared
  activation state or actuator delay. **Sources:**
  `contracts/robots/two_joint_arm.xml` (`actuator`);
  `robot_learning/scenario/policy_io.py` (`physical_action`);
  `robot_learning/scenario/environment.py` (`step`).

- **[Repository fact]** Each hinge declares viscous damping 0.5 and armature
  0.01. No gravity, contact, target force, or link-link collision force is
  declared: all listed geoms have contact disabled. The target is a mocap body,
  so it is a prescribed reference rather than a dynamically pushed object.
  **Sources:** `contracts/robots/two_joint_arm.xml`.

- **[Repository fact]** Reset sets both joint positions and velocities to zero,
  runs forward kinematics, then samples a static target in the current
  end-effector plane. Thus the initial arm is straight along +x, with its
  end-effector at approximately (0.22, 0, 0.02) m, and is initially at rest.
  **Sources:** `robot_learning/scenario/environment.py` (`reset`,
  `_sample_target_position`); `contracts/robots/two_joint_arm.xml`.

- **[Repository fact]** An episode is capped at 500 control steps (10 s at the
  declared control period). A target is successful only after the end effector
  is within 0.01 m and remains there for 2.0 s, represented by 100 consecutive
  control steps under the current timing. An exit resets the consecutive count;
  success is not credited for a partial hold. The official assessment is 200
  independent episode outcomes and requires at least 196 successes. **Sources:**
  `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`hold_steps_required`, termination);
  `contracts/robots/two_joint_arm.xml` (`timestep`).

### Sensing and control interface

- **[Repository fact]** The default observation has 11 float32 values:
  two joint positions, two joint velocities, the three-dimensional
  end-effector-minus-target vector, and four wrapped angular residuals to the
  open and folded inverse-kinematic solutions. The action is a two-vector in
  [-1, 1]. **Sources:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/policy_io.py`.

- **[Repository fact]** The observation is model-based and noiseless as written.
  It directly exposes \(q\), \(\dot q\), and the target-relative Cartesian error;
  it does not expose sensor noise, latency, contact signals, force/torque
  measurements, acceleration, actuator state, hold counter, or time remaining.
  The four IK residuals are computed from target x/y and the declared link
  lengths, not measured by an additional sensor. **Sources:**
  `robot_learning/scenario/observations.py`; `robot_learning/scenario/environment.py`.

- **[Repository fact]** The default policy I/O is a direct observation/action
  mapping. A saved policy runtime can freeze a different policy I/O callable,
  but the exact artifact is not part of the pre-campaign physical definition.
  **Sources:** `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.

- **[Repository fact]** The visible evaluation environment measures distance after
  the ten internal physics steps, increments `held_steps` only at that boundary,
  and terminates when the boundary count reaches 100. The task contract,
  however, describes an uninterrupted hold as the authoritative requirement.
  **Sources:** `contracts/scenario.md`; `robot_learning/scenario/environment.py`
  (`step`).

### Training and task-definition separation

- **[Repository fact]** The baseline training environment samples radii 0.14--0.20
  m, whereas the evaluation environment uses the official 0.06--0.20 m range.
  The training choice is research-owned and may change; it does not redefine the
  official task. **Sources:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`; `contracts/task_spec.py`.

## Physical consequences

### Reachability and inverse-kinematic alternatives

- **[RI] Decision relevance:** The official radial interval lies strictly inside
  the unconstrained two-link workspace, so geometric impossibility is not the
  expected explanation for failure. A target generally has two elbow branches:
  \(q_e=+\arccos(c)\) and \(q_e=-\arccos(c)\), with
  \(c=(r^2-L_1^2-L_2^2)/(2L_1L_2)\). The joint limits can remove one branch for
  some azimuths, but the other branch provides a distinct reachable approach.
  This can change whether early work should focus on branch-aware state/control
  representation rather than expanding workspace.
- **[RI] Assumptions:** This follows from the planar forward-kinematic equations,
  the declared lengths and target plane, and the declared limits being enforced
  by the compiled MuJoCo model. It does not assume a particular learned policy.
- **[RI] Sources:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `contracts/task_spec.py`;
  `robot_learning/scenario/observations.py`.
- **[RI] Discriminating evidence:** Enumerate both analytic IK solutions for a
  dense grid of official radius/angle pairs, reject solutions outside compiled
  joint limits, and forward-evaluate the survivors. A nonzero residual or an
  empty feasible set would revise the reachability claim; branch-dependent
  success or settling would support the alternative-solution mechanism.

### Initial singular geometry and coupled reaching

- **[RI] Decision relevance:** The reset posture is fully extended, \(q_e=0\).
  The planar Jacobian
  \(J=\partial(x,y)/\partial(q_s,q_e)\) has rank one there: an infinitesimal
  shoulder/elbow change initially gives only one independent Cartesian velocity
  direction. Moving inward from the 0.22 m initial reach therefore requires
  first bending the chain and then changing radius; a controller that treats
  Cartesian radial correction as immediately available may overshoot or spend
  control authority creating the second direction. This couples reaching speed
  to trajectory choice and may change the first control representation or
  initialization decision.
- **[RI] Assumptions:** The implication uses the stated planar kinematics and
  differentiability at the straight configuration; it concerns local
  instantaneous authority, not global reachability.
- **[RI] Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`reset`);
  `contracts/robots/two_joint_arm.py`.
- **[RI] Discriminating evidence:** Compute the smallest singular value and
  condition number of \(J(q)\) along successful and failed trajectories, and
  compare initial radial/tangential end-effector velocities under controlled
  shoulder and elbow commands. A non-rank-one compiled kinematics result would
  invalidate the stated local mechanism.

### Bounded actuation, damping, and stabilization

- **[RI] Decision relevance:** The command-to-torque path is direct and bounded,
  while damping dissipates velocity. Consequently, success requires not only
  reaching the tolerance ball but arriving with sufficiently low velocity and
  enough remaining authority to reject drift. With zero gravity, a stationary
  configuration needs no static gravity-compensation torque; however, residual
  velocity, motor commands, numerical error, or target-tracking oscillation can
  still eject the end effector from a 1 cm ball. This can change whether the
  first campaign effort prioritizes trajectory shaping, velocity-aware control,
  or a terminal settling behavior.
- **[RI] Assumptions:** The nominal \(\tau=5u\) motor semantics apply, the
  actuator has no hidden activation dynamics, and the compiled inertia is
  positive and finite. Exact acceleration and settling rates additionally
  depend on compiled mass properties.
- **[RI] Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/policy_io.py`;
  `robot_learning/scenario/environment.py`.
- **[RI] Discriminating evidence:** Apply bounded step and impulse commands from
  several configurations and record \(q,\dot q,\ddot q\), actuator force, and
  end-effector error at physics-step resolution. Matching torque ratios and a
  stable damped response support the model; saturation, delay, or strongly
  configuration-dependent responses beyond the inertial prediction identify a
  missing compiled/default term.

### Closed-loop relation from observation to outcome

- **[RI] Decision relevance:** At each 20 ms boundary, the policy receives the
  current observation, emits a two-component command, and the simulator holds
  that command while the arm evolves. In generalized coordinates the physical
  relation has the form
  \(M(q)\ddot q+C(q,\dot q)\dot q+D\dot q=\tau(u)\), with zero gravity and no
  contact term in the declared model. Forward kinematics maps \(q\) to the
  end-effector position; the distance predicate maps that position to
  in-tolerance status; the consecutive-hold state maps the status to episode
  success. This is the causal chain that must be diagnosed when a policy enters
  tolerance but does not complete the episode.
- **[RI] Assumptions:** The standard rigid-body MuJoCo equations and direct motor
  transmission apply, \(D\) includes the declared joint damping and compiled
  armature effects are included in \(M\), and the target is fixed during the
  episode.
- **[RI] Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py` (`step`, `_distance_to_target`);
  `robot_learning/scenario/policy_io.py`.
- **[RI] Discriminating evidence:** For a seeded replay, align observation,
  action, qpos/qvel, end-effector error, in-tolerance status, and hold counter
  at every control boundary, while retaining physics-step state. A mismatch in
  any link identifies whether the uncertainty is in policy I/O, dynamics,
  kinematics, or success accounting.

### Timing and the complete hold

- **[RI] Decision relevance:** The 20 ms action-hold interval makes the policy a
  sampled-data controller: one action remains active for ten physics steps.
  The tolerance is only 1 cm, so a trajectory can be inside at policy
  boundaries while leaving the ball between them. Under the visible environment,
  this is not counted as an interruption; under the authoritative wording, it
  would violate a continuous hold. This distinction can change the needed
  control bandwidth, evaluation diagnostics, and whether a candidate is safe to
  take to the official panel.
- **[RI] Assumptions:** The visible environment is representative of the
  protected evaluator's interaction semantics. The physical state evolves at
  every MuJoCo timestep even though the policy and visible hold counter update
  less often.
- **[RI] Sources:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`.
- **[RI] Discriminating evidence:** Compare the boundary-sampled hold result with
  a physics-step distance trace for the same frozen policy and seeded episodes.
  Agreement supports boundary equivalence; any intra-interval excursion beyond
  0.01 m supports a materially stricter continuous-hold interpretation. The
  protected evaluator's result is the final authority for official behavior.

### Observation, observability, and controller state

- **[RI] Decision relevance:** In the default model, \(q\), \(\dot q\), and the
  target-relative error make the physical configuration and target effectively
  observable to a controller with the declared model. The target x/y can be
  reconstructed from forward kinematics and the observed error, while the
  four residuals expose both IK branches. A memoryless policy can therefore
  address the physical state without estimating hidden target motion. Conversely,
  the hold counter, elapsed time, internal substep path, actuator force, and
  any unmodeled compiled state are unavailable; memory cannot recover a quantity
  that is never observed unless it is inferred from history. This can change the
  value of recurrent policies or explicit terminal-state features.
- **[RI] Assumptions:** The default `reach_observation` is the runtime used by
  the candidate, the target remains fixed, and the compiled model matches the
  declared link geometry. “Effectively observable” does not mean physically
  measured in hardware; it means exactly supplied by the simulator interface.
- **[RI] Sources:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`;
  `robot_learning/scenario/environment.py`.
- **[RI] Discriminating evidence:** Reconstruct target position from observed
  \(q\) and error and compare it with `mocap_pos`; test pairs of states with the
  same observation but different hidden hold counters or elapsed times. Exact
  reconstruction supports the stated observability; mismatches or policy
  dependence on unobserved timing expose an additional state variable.

### Task geometry, convergence, and failure classes

- **[RI] Decision relevance:** The physical objective decomposes into coupled
  classes, not independent subtasks: (1) reach the target with a feasible IK
  branch, (2) converge with sufficiently small Cartesian error and velocity, and
  (3) stabilize for the full uninterrupted duration. A policy can have a small
  minimum distance yet fail through late overshoot, can reach quickly yet lose
  the hold, or can hold easy outer targets while failing the inner-radius
  distribution. This decomposition can change which diagnostic quantity is
  optimized or which candidate is scientifically preferred.
- **[RI] Assumptions:** Distance to the end-effector site is the relevant task
  error, the target is stationary, and no contact interaction changes the
  dynamics. The three classes are causal interpretations, not additional
  success criteria.
- **[RI] Sources:** `contracts/scenario.md`; `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`; `contracts/robots/two_joint_arm.xml`.
- **[RI] Discriminating evidence:** For each episode record target radius/angle,
  first-tolerance step, minimum and final distance, maximum consecutive hold,
  interruptions, joint-limit proximity, \(\|\dot q\|\), Cartesian speed, and
  Jacobian conditioning. Clustering failures by these quantities distinguishes
  reach, convergence, branch/limit, and stabilization mechanisms.

### Physically meaningful quantities

- **[RI] Decision relevance:** The most informative complete-behavior quantities
  are \(q,\dot q\), action and transmitted torque, end-effector/target position
  and distance, Cartesian velocity, acceleration, Jacobian singular values,
  joint-limit margin, selected IK branch, first-entry time, overshoot,
  settling time, uninterrupted in-tolerance duration, and energy-like
  quantities such as kinetic energy and dissipated damping work. Together they
  connect command to motion and motion to the binary episode outcome; reward
  totals alone do not identify those mechanisms.
- **[RI] Assumptions:** The simulator state and model parameters can be recorded
  without altering the production interaction, and diagnostic logging does not
  change policy inputs or timing.
- **[RI] Sources:** `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`; `robot_learning/training/reward.py`;
  `contracts/robots/two_joint_arm.xml`.
- **[RI] Discriminating evidence:** Physics-step telemetry and replayed seeded
  episodes should show whether these quantities separate successful from failed
  holds and whether the separation persists across radius and azimuth. If a
  quantity does not discriminate, it should not be treated as a mechanism.

### Official-distribution coverage

- **[RI] Decision relevance:** The baseline's 0.14--0.20 m training radii omit
  the official 0.06--0.14 m inner region. A policy trained only on that baseline
  can have adequate outer-radius behavior while lacking exposure to different
  elbow configurations, Jacobian conditioning, and initial-to-target
  trajectories. Distribution coverage is therefore a plausible first decision
  variable, not evidence that the baseline will fail.
- **[RI] Assumptions:** Training exposure affects the learned policy and the
  inner region is dynamically or kinematically distinct enough to matter; the
  evaluation distribution remains the contract distribution.
- **[RI] Sources:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`; `contracts/task_spec.py`.
- **[RI] Discriminating evidence:** Stratify fixed-seed evaluation by radius and
  angle, and compare first reach, hold interruptions, and success for inner
  versus outer targets. A flat profile weakens the coverage concern; a
  reproducible inner-region deficit supports it.

## Unknowns

### Compiled mass and inertia

- **[UQ] Quantity:** The XML gives link geometry, damping, and armature but no
  explicit body mass, density, diagonal inertia, or full compiled mass matrix.
  MuJoCo may derive these through defaults and geom-based compilation. The
  exact \(M(q)\), coupling, natural time scales, and acceleration under
  \(\tau=5u\) are unresolved from the human-owned text alone.
- **[UQ] Decision relevance:** This can change action scaling, expected settling
  time, whether the 500-step horizon is generous, and whether a model-based or
  velocity-aware controller is worthwhile.
- **[UQ] Assumptions:** The candidate is sensitive to acceleration and settling
  rather than only static kinematics; default density and inertial compilation
  are not treated as scientifically obvious constants.
- **[UQ] Sources:** `contracts/robots/two_joint_arm.xml`; MuJoCo model loading in
  `robot_learning/scenario/environment.py`.
- **[UQ] Discriminating evidence:** Inspect the compiled model's body masses,
  inertias, and `M(q)` at representative configurations, then validate with
  torque-to-acceleration and free-decay measurements. A measured response
  inconsistent with those values requires revising the dynamics model.

### Limit and actuator enforcement details

- **[UQ] Quantity:** The XML writes joint ranges and actuator control ranges but
  does not spell out every compiler/default flag governing range enforcement,
  control clamping, actuator force limits, or transmission sign conventions.
  The environment clips policy actions, but the compiled actuator behavior and
  behavior at joint boundaries remain to be verified.
- **[UQ] Decision relevance:** Unexpected limit clamping or actuator saturation
  can create distinct failure classes near difficult azimuths and can change
  whether branch selection or torque margin is the correct first focus.
- **[UQ] Assumptions:** The implementation relies on MuJoCo's standard XML
  defaults and motor semantics; no external wrapper changes the model.
- **[UQ] Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`np.clip`, `data.ctrl`).
- **[UQ] Discriminating evidence:** Read the compiled joint and actuator
  limit/force fields and apply commands at interior and boundary configurations,
  recording actual generalized forces and qpos. A boundary reached without the
  expected constraint or a torque different from the nominal mapping revises
  this model.

### Integrator and numerical dynamics

- **[UQ] Quantity:** The timestep is explicit, but the XML does not explicitly
  state the integrator, solver settings, constraint tolerances, or numerical
  stability behavior. These can affect short transients and whether a
  boundary-sampled trace hides a within-frame excursion.
- **[UQ] Decision relevance:** If the task lies near the 1 cm tolerance, numerical
  damping or integration error can change controller bandwidth, reproducibility,
  and the interpretation of a complete hold.
- **[UQ] Assumptions:** Numerical effects are not negligible relative to the
  tolerance and the protected evaluator uses the same model configuration.
- **[UQ] Sources:** `contracts/robots/two_joint_arm.xml` (`option`);
  `robot_learning/scenario/environment.py` (`mj_step` loop).
- **[UQ] Discriminating evidence:** Record the compiled integrator/solver
  settings and repeat deterministic rollouts at smaller timesteps or equivalent
  integration settings without changing the policy. Stable trajectories and
  unchanged hold outcomes weaken this unknown; material changes support it.

### Continuous-hold evaluation semantics

- **[UQ] Quantity:** The contract says the end effector must remain continuously
  within tolerance, while the visible environment evaluates distance only after
  each frame skip. It is unresolved whether the protected benchmark checks
  intermediate physics states or intentionally defines continuity at control
  boundaries.
- **[UQ] Decision relevance:** This is directly capable of changing official
  success, the required stabilization margin, and the validity of development
  diagnostics.
- **[UQ] Assumptions:** The visible scenario is not itself the complete protected
  benchmark implementation; the contract's “authoritative” duration has priority
  over a convenience interpretation of the visible counter.
- **[UQ] Sources:** `contracts/scenario.md`; `robot_learning/scenario/environment.py`;
  `contracts/task_spec.py`.
- **[UQ] Discriminating evidence:** Compare physics-step traces against the
  official evaluator's episode outcomes on the same frozen policy and seeds.
  A disagreement specifically involving intra-frame exits resolves the
  ambiguity; absent access, the contract must remain the conservative
  scientific interpretation.

### Candidate-specific runtime I/O

- **[UQ] Quantity:** The baseline uses the 11-value default observation and
  identity action mapping, but `PolicyRuntime` freezes policy I/O with each
  artifact. Before a candidate exists, its normalization, observation callable,
  action callable, and any recurrence are not known.
- **[UQ] Decision relevance:** A candidate may not be comparable by weights or
  nominal action values alone if its runtime rescales inputs, transforms
  actions, or carries recurrent state. This can change which physical
  diagnostics are valid and whether a policy's apparent stabilization is
  attributable to the intended interface.
- **[UQ] Assumptions:** Runtime serialization is honored exactly during
  evaluation and the candidate may differ from the default recipe.
- **[UQ] Sources:** `contracts/policy_runtime.py`;
  `robot_learning/scenario/policy_io.py`;
  `robot_learning/scenario/environment.py` (`policy_runtime`).
- **[UQ] Discriminating evidence:** Validate the saved runtime and log the
  observation/action values immediately before `data.ctrl` for representative
  states. Agreement with the default mapping closes the unknown for that
  candidate; any transform must be included in its physical model.

## Decision-relevant synthesis

### Reachability is available, but the reset posture is locally singular

- **[RI] Decision relevance:** The official targets are inside the two-link
  workspace and have alternative elbow solutions, so first decisions should
  distinguish trajectory/branch/control failures from geometric impossibility.
  The fully extended reset has rank-one Cartesian velocity authority, making
  inward reaching a coupled bend-then-translate maneuver.
- **[RI] Assumptions:** The stated planar kinematics and joint limits are the
  compiled model; no hidden contact or base motion exists.
- **[RI] Sources:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`reset`).
- **[RI] Discriminating evidence:** Analytic IK feasibility over the official
  domain plus trajectory logs of Jacobian conditioning, branch, and joint-limit
  margin.

### Stabilization, not entry alone, determines success

- **[RI] Decision relevance:** The 1 cm tolerance and 100-step uninterrupted
  requirement make arrival velocity, overshoot, settling, and disturbance
  rejection central physical quantities. Zero gravity removes static
  gravity-compensation demand but does not remove transient or numerical
  ejection risk.
- **[RI] Assumptions:** Motor commands have the standard direct MuJoCo meaning,
  damping is active as declared, and the protected evaluator honors the
  complete-hold wording.
- **[RI] Sources:** `contracts/scenario.md`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`.
- **[RI] Discriminating evidence:** Physics-step distance, Cartesian speed,
  qvel, action/torque, and uninterrupted in-tolerance traces, compared between
  episodes that enter tolerance and episodes that succeed.

### Compiled dynamics and evaluator sampling are the highest-impact unknowns

- **[UQ] Decision relevance:** Exact mass/inertia, actuator/limit defaults, and
  integrator settings determine control authority and time scales; the
  boundary-versus-continuous hold interpretation determines what behavior is
  actually accepted. Either uncertainty can reverse an early decision about
  control bandwidth, diagnostics, or candidate readiness.
- **[UQ] Assumptions:** These quantities are not fully specified by the XML text
  and the visible environment is not assumed to reveal all protected benchmark
  semantics.
- **[UQ] Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`; `contracts/task_spec.py`.
- **[UQ] Discriminating evidence:** Inspect compiled MuJoCo fields; measure
  command-to-acceleration and free-decay responses; and compare
  physics-step hold traces with protected-evaluator outcomes. These observations
  support, weaken, or revise the model without presupposing an intervention.

### Official coverage includes an omitted inner-radius region in the baseline

- **[RI] Decision relevance:** The baseline training distribution starts at
  0.14 m while official evaluation starts at 0.06 m. Before attributing a
  development deficit to dynamics or control, performance must be understood
  across radius and angle; otherwise outer-region competence can mask an
  inner-region failure.
- **[RI] Assumptions:** The baseline recipe is the starting exposure and
  kinematics/conditioning differ enough across the official domain to affect
  learning.
- **[RI] Sources:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`; `contracts/task_spec.py`.
- **[RI] Discriminating evidence:** Radius- and angle-stratified first-reach,
  hold-interruption, and success measurements on fixed seeded panels.
