## Established facts

### Robot morphology and coordinates

- **[Repository fact]** The robot is a serial, planar two-link arm. The shoulder
  is a revolute joint about the world \(z\) axis at \((0,0,0.02)\); the upper
  arm has length \(L_1=0.12\) m and the forearm has length \(L_2=0.10\) m.
  The end-effector site is at the distal forearm endpoint. Both joint axes are
  parallel to \(z\), so the joint configuration is
  \(q=(q_s,q_e)\), where the elbow angle is relative to the upper arm.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`,
  `forearm`, `shoulder`, `elbow`, `end_effector`);
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`).

- **[Repository fact]** The two joints declare ranges of \([-170^\circ,170^\circ]\),
  have damping \(0.5\), and have armature \(0.01\). The XML does not add a
  wrist, gripper, translational joint, obstacle, or movable object. The visible
  plane is at \(z=0\), while the arm and target are placed at \(z=0.02\);
  the task is therefore planar in \(x,y\).
  **Source:** `contracts/robots/two_joint_arm.xml`.

- **[Repository fact]** The site forward kinematics are
  \[
  p_e(q)=
  (L_1\cos q_s+L_2\cos(q_s+q_e),\;
   L_1\sin q_s+L_2\sin(q_s+q_e),\;0.02).
  \]
  **Reasoned implication:** The ideal radial workspace is the annulus
  \(|L_1-L_2|\leq r\leq L_1+L_2\), namely \(0.02\leq r\leq0.22\) m, before
  joint-limit effects. **Sources:** the same XML geometry and the length
  constants in `contracts/robots/two_joint_arm.py`.

### Actuation, simulator, and timing

- **[Repository fact]** Each joint has a MuJoCo `motor` actuator with
  `ctrlrange="-1 1"` and `gear="5"`. The policy action has two components,
  is clipped to \([-1,1]\), is passed through the default physical-action
  mapping unchanged, and is written directly to `data.ctrl`. There is no
  position controller or action-rate limiter in the scenario layer.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`actuator`);
  `robot_learning/scenario/policy_io.py` (`physical_action`);
  `robot_learning/scenario/environment.py` (`step`).

- **[Repository fact]** The simulator integrates with a physics timestep of
  \(0.002\) s. Each policy action is held for `FRAME_SKIP=10` physics steps,
  giving a \(0.020\) s control interval and a 50 Hz policy loop. The maximum
  episode length is 500 control steps, or 10 s of nominal simulated time.
  The required hold is \(2.0/0.020=100\) qualifying control steps.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`option timestep`);
  `contracts/task_spec.py` (`FRAME_SKIP`, `MAX_EPISODE_STEPS`,
  `HOLD_SECONDS`); `robot_learning/scenario/environment.py`
  (`hold_steps_required`).

- **[Repository fact]** Gravity is explicitly zero. Joint damping and armature
  are explicitly present, while body masses, inertial tensors, actuator force
  ranges, integrator choice, solver settings, and most global MuJoCo defaults
  are not written in the XML. **[Repository fact]** The locked runtime is
  native MuJoCo 3.12.0. **Source:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md` (locked runtime APIs).

- **[Reasoned implication]** Away from active constraints, the joint-space
  dynamics have the form
  \[
  M(q)\ddot q+C(q,\dot q)\dot q+D\dot q
  =\tau_{\mathrm{motor}}+\tau_{\mathrm{constraint}},
  \]
  with no gravity term, \(D\) including the declared joint damping, and the
  armature contributing to \(M(q)\). For the two-dimensional planar task, the
  end-effector velocity is \(v_e=J(q)\dot q\), with
  \(\det J=L_1L_2\sin q_e\). The exact \(M,C,J\)-conditioned response is
  therefore configuration dependent even though the actuator interface is
  fixed.
  **Sources:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; MuJoCo joint/body definitions.

- **[Repository fact]** On reset, MuJoCo state is reset and then all joint
  positions and velocities are set to zero before forward kinematics. The
  initial arm is consequently straight along \(+x\), with the end effector at
  \((0.22,0,0.02)\). The target is sampled after this state is established.
  **Source:** `robot_learning/scenario/environment.py` (`reset`,
  `_sample_target_position`).

### Task geometry and success semantics

- **[Repository fact]** Each official target has an angle uniform on
  \([-\pi,\pi)\) and a radius uniform on \([0.06,0.20]\) m. The target is
  placed at the arm's \(z\) coordinate. The target sphere and plane are
  non-contacting visual geometry; success is not a contact event.
  **Sources:** `contracts/scenario.md`; `contracts/task_spec.py`
  (`TARGET_RADIUS_RANGE`); `contracts/robots/two_joint_arm.xml`; 
  `robot_learning/scenario/environment.py` (`_sample_target_position`).

- **[Repository fact]** Success is defined by end-effector center distance
  \(d=\|p_e-p_t\|\leq0.01\) m at every one of 100 consecutive control-step
  checks. Any checked distance outside the tolerance resets the held-step count.
  An episode terminates on the 100th qualifying check and truncates at 500
  control steps. The official assessment uses 200 fixed episodes and requires
  at least 196 successes. **Sources:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`
  (`step`); `contracts/program.md` (human goal).

- **[Repository fact]** The task reference and the training default differ:
  official evaluation samples radii from \(0.06\) to \(0.20\) m, whereas
  `make_training_env` defaults to \(0.14\) to \(0.20\) m. Training distribution
  is therefore not, by itself, evidence of official-distribution performance.
  **Sources:** `contracts/task_spec.py`; `robot_learning/training/environment.py`.

### Sensing and control interface

- **[Repository fact]** The default observation has 11 float32 values:
  two joint positions, two joint velocities, the three-dimensional vector from
  target to end effector, and four wrapped joint-error values for the
  positive-elbow and negative-elbow analytic inverse-kinematic solutions.
  **Source:** `robot_learning/scenario/observations.py`
  (`reach_observation`, `OBSERVATION_SIZE`).

- **[Repository fact]** The observation uses exact simulator `qpos` and `qvel`,
  the simulator end-effector site position, and target mocap position. It does
  not expose action, torque, acceleration, contact force, actuator state,
  simulator constraint state, elapsed time, or the internal held-step counter.
  **Sources:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.

- **[Repository fact]** The observation's IK values are derived from
  \[
  \cos q_e =
  \frac{x_t^2+y_t^2-L_1^2-L_2^2}{2L_1L_2},
  \]
  followed by \(q_e=\pm\arccos(\cdot)\) and the corresponding shoulder
  angle. The implementation clips the cosine before `arccos` and wraps angle
  errors to \([-\pi,\pi)\). **Source:**
  `robot_learning/scenario/observations.py`.

### Physical quantities with scientific meaning

- **[Repository fact]** The task implementation already records target radius
  and angle, minimum and final distance, first in-tolerance step, maximum
  consecutive hold, in-tolerance steps, hold interruptions, total steps, and
  success. **Source:** `robot_learning/scenario/evaluation.py`.

- **[Reasoned implication]** For mechanism understanding, the corresponding
  state and input traces are joint angles \(q\), velocities \(\dot q\),
  end-effector position and velocity, target-relative error, commanded
  control and inferred generalized torque, distance-to-target, distance rate,
  tolerance-boundary margin, saturation frequency, branch choice, and the
  fraction and longest run of qualifying hold samples. These quantities
  separate reach, convergence, and stabilization rather than treating the
  scalar episode outcome as a mechanism.
  **Sources:** forward kinematics above; `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.

## Physical consequences

### Reachability is geometrically available but not automatically achieved

- **[Reasoned implication]** The official annulus \([0.06,0.20]\) m lies
  strictly inside the ideal arm annulus \([0.02,0.22]\) m. For a target radius
  in this interval, the required elbow magnitude is approximately
  \(49.5^\circ\) to \(150.6^\circ\), within the declared elbow range. The two
  elbow signs provide two discrete inverse-kinematic configurations; their
  shoulder offsets are approximately \(22.3^\circ\) to \(55.9^\circ\), so an
  angularly valid branch is expected throughout the full target-angle range.
  This makes geometric reachability unlikely to be the dominant limitation,
  while leaving approach path and dynamics consequential.

- **Decision relevance:** This can change whether early work treats failures as
  target-coverage/IK failures or as trajectory, timing, and stabilization
  failures; it also determines whether branch-aware diagnostics are useful.
- **Assumptions:** The analytic planar geometry matches the MuJoCo site,
  declared joint ranges are active as MuJoCo joint limits, and no unmodeled
  collision or solver constraint removes the analytic configurations.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Compute both IK solutions and forward-kinematic
  residuals for sampled targets, then compare them with actual constrained
  simulator states and target-angle/radius-conditioned failures. A large
  residual or concentration at joint limits would weaken the geometric claim;
  low residuals with late hold failures would support it.

### The action is torque-like trajectory control, not a setpoint command

- **[Reasoned implication]** The actuator converts bounded control to bounded
  generalized motor effort through gear 5, while joint damping resists motion
  and armature adds generalized inertia. The coupled two-joint inertia means
  a command at one joint can alter the motion required at the other. Since each
  command is held for 20 ms, the policy must produce both the approach
  trajectory and the final corrective behavior. A policy that reaches the
  tolerance with substantial velocity can leave it before the next qualifying
  sample.

- **Decision relevance:** This can change the first choice between improving
  policy learning and characterizing low-level closed-loop behavior; it makes
  velocity, torque saturation, and boundary margin more decision-relevant than
  position error alone.
- **Assumptions:** MuJoCo motor semantics map the gear-scaled control to joint
  effort as expected, and the omitted mass/inertia defaults do not invalidate
  the qualitative damped, effort-driven picture.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`step`);
  `robot_learning/scenario/policy_io.py`.
- **Discriminating evidence:** Apply controlled constant actions and measure
  \(q,\dot q\), acceleration, and effort response over physics and control
  steps. Saturation, overshoot, settling time, and cross-joint response
  distinguish authority-limited motion from policy trajectory error.

### Success couples reaching, convergence, and stabilization

- **[Reasoned implication]** Reaching means entering a 1 cm ball; convergence
  means entering it before the 500-step horizon; stabilization means preserving
  that condition for 100 consecutive checks. These are physically coupled:
  velocity at entry, damping, action discretization, joint-limit proximity,
  and target radius all affect whether a reached state remains inside the
  tolerance. The strict uninterrupted counter makes a single checked
  excursion a complete hold failure rather than a small score reduction.

- **Decision relevance:** Aggregate success alone cannot identify whether the
  campaign needs faster reaching, lower residual velocity, or more robust
  holding. The first model comparison should therefore preserve timing and
  interruption diagnostics.
- **Assumptions:** The policy observes enough state to regulate velocity and
  the simulator is deterministic conditional on target and policy state.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py` (`held_steps`, `terminated`);
  `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Partition episodes by first-reach step,
  minimum distance, velocity at first reach, maximum held run, interruptions,
  and target geometry. Early reach with short holds supports a stabilization
  bottleneck; no qualifying samples supports reach or control-authority
  limitation.

### The operationally continuous hold is sampled at the control boundary

- **[Reasoned implication]** The environment checks distance only after ten
  MuJoCo steps, at 50 Hz. It does not inspect the trajectory between those
  checks. Thus “continuous” is enforced as 100 consecutive sampled
  observations under the current interaction semantics; an intra-interval
  excursion that returns before the next check is not counted as an
  interruption. This is an evaluation property, not evidence that the
  physical trajectory stayed within 1 cm at every 2 ms state.

- **Decision relevance:** This can change whether a policy is judged robust
  enough for the official task and whether diagnostics must include
  physics-step distance rather than only control-step distance.
- **Assumptions:** The official evaluator uses the same scenario step
  semantics and does not add a hidden intra-step check.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py` (`FRAME_SKIP`);
  `robot_learning/scenario/environment.py` (`for _ in range(self.frame_skip)`,
  followed by one distance check).
- **Discriminating evidence:** Record distance at every MuJoCo physics step
  for successful and near-successful episodes. Substantial unobserved
  tolerance crossings would weaken the assumption that sampled hold is a
  sufficient proxy for continuous physical hold.

### The observation makes target geometry and branch structure largely explicit

- **[Reasoned implication]** Because joint positions determine the end-effector
  position and the observation supplies end-effector-minus-target, the target
  position in the arm frame is reconstructable. The two IK error pairs expose
  both discrete elbow branches. The policy therefore need not infer target
  location from reward or visual motion. However, it does not receive the
  held-step counter, previous action, or simulator's unobserved dynamics, so
  exact hold progress is history-dependent from the policy's perspective.

- **Decision relevance:** Early learning effort is more likely to be limited by
  temporal control and policy memory/implicit state estimation than by target
  localization. Branch-conditioned behavior can also reveal whether the policy
  uses both feasible solutions or collapses onto one.
- **Assumptions:** The saved policy runtime preserves the default observation
  callable and does not apply an additional observation transform; a recurrent
  policy, if used, can retain useful recent history.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.
- **Discriminating evidence:** Verify the exported runtime's observation
  fingerprint and inspect policy behavior across both IK branches, including
  velocity and action changes near the tolerance boundary. Performance
  differences after matched physical states would indicate policy-state
  limitations rather than missing target information.

### Training reward shapes behavior but does not define physical success

- **[Repository fact]** The baseline reward combines progress in distance,
  exponential closeness, incremental hold progress, a small action-square cost,
  an outside-band penalty after a hold exit, and a completion bonus.
  **Reasoned implication:** The reward can favor smooth closeness and completed
  holds, but its scalar value is not a physical state variable and cannot
  certify the 98% objective. A policy can optimize reward while still failing
  the all-or-nothing hold criterion.

- **Decision relevance:** This can change whether a training modification is
  evaluated by reward trends or by task-conditioned hold diagnostics; official
  progress must remain episode success.
- **Assumptions:** The candidate was trained with this baseline reward and no
  incompatible wrapper changes.
- **Source references:** `robot_learning/training/reward.py`;
  `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Compare reward components with success,
  first-reach timing, longest hold, and interruptions on the same episodes.
  Divergence between reward ranking and hold success weakens reward as a
  decision proxy.

## Unknowns

### Effective mass, inertia, and numerical integration

- **[Unresolved quantity]** The XML specifies link geometry, damping, armature,
  timestep, and zero gravity but does not specify body mass/inertia, density,
  integrator, solver, constraint tolerances, or related global defaults.
  MuJoCo 3.12.0 will resolve these at model construction, but their numerical
  values and effective closed-loop consequences have not been established
  here from a runtime measurement.

- **Decision relevance:** These quantities can change acceleration, settling
  time, overshoot, controllability near the 1 cm boundary, and which policy
  time scales are plausible.
- **Assumptions:** The omission is consequential only if inherited defaults
  materially affect the response relative to the explicit 5-gear effort,
  damping, and armature.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md` (MuJoCo version); `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Inspect `MjModel` mass/inertia and `opt`
  fields, then compare measured free and forced responses with the dynamics
  predicted from those fields. A match narrows the uncertainty; mismatch
  indicates solver or hidden-default effects requiring separate treatment.

### Active joint-limit and actuator-boundary behavior

- **[Unresolved quantity]** Joint ranges and control ranges are declared, but
  the pre-campaign model has not measured how close successful trajectories
  approach the joint limits, whether constraint forces become active, or how
  the motor effort behaves at the control boundary. The XML also does not
  explicitly state every limit/force option whose default semantics may matter.

- **Decision relevance:** Limit encounters can produce a distinct failure class:
  a geometrically valid target may be unreachable by the chosen branch or may
  become difficult to stabilize because corrective motion is one-sided.
- **Assumptions:** The analytic IK margin is not sufficient if MuJoCo
  constraints, finite tolerance, or transient momentum dominate near a limit.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Log joint-limit margins, actions, velocities,
  and constraint/actuator quantities on successful and failed episodes,
  conditioned on target angle and radius. Clustering at \(\pm170^\circ\) or at
  action \(\pm1\) would support this failure explanation.

### Continuous-time robustness between official checks

- **[Unresolved quantity]** The official outcome is known to be checked at
  control boundaries, but the amount of distance excursion during the ten
  internal physics steps is unknown for any future policy. The model therefore
  cannot infer physical continuous-hold robustness from a successful episode
  alone.

- **Decision relevance:** This can change confidence in a policy that barely
  passes sampled hold and can alter the scientific interpretation of late
  hold failures versus hidden oscillation.
- **Assumptions:** Physics-step telemetry is available without changing the
  policy or official evaluator, and sampled success is the campaign's
  authoritative metric.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Measure the maximum physics-step distance and
  number of substep tolerance crossings during each sampled hold. Agreement
  between substep and control-step results supports the sampled proxy; a gap
  identifies an unobserved robustness distinction.

### Policy-specific state and action transformations

- **[Unresolved quantity]** The default scenario mapping is identity, but
  policy artifacts can carry a frozen `PolicyIO`, normalization, loader, and
  optional reset behavior. Before a candidate exists, it is unknown whether
  an eventual runtime will preserve only the default physical mapping or add
  a learned-policy-side transformation.

- **Decision relevance:** A transformed observation or action changes the
  effective controller and invalidates direct comparisons that attribute a
  behavior solely to policy weights or algorithm choice.
- **Assumptions:** Runtime persistence is honored and the saved callable is
  the one used for evaluation; the official evaluator rejects mismatched
  runtime files rather than silently substituting current code.
- **Source references:** `contracts/policy_runtime.py`;
  `robot_learning/scenario/policy_io.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Verify runtime and weight fingerprints, inspect
  the resolved observation/action spaces and callables, and replay identical
  physical states through the runtime. A mismatch between resolved and
  default mappings revises attribution of control behavior.

### Distribution-conditioned difficulty

- **[Unresolved quantity]** The geometry of the official distribution is fixed,
  but its effect on success is unknown before campaign evidence. In
  particular, radius is uniform rather than area-uniform, and the initial
  state is always the straight-arm state while target angle is uniform.

- **Decision relevance:** The first campaign decision can change if failures
  concentrate at small radii, near the joint-limit angular margins, or at
  large initial displacement; aggregate success can conceal that structure.
- **Assumptions:** Target sampling is independent uniform sampling as
  implemented, and the policy sees the stated target-relative observation.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`);
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Stratify complete episode outcomes and
  reach/hold diagnostics by target radius and angle, using the same official
  sampling rule. A flat conditional profile weakens geometry-conditioned
  explanations; a structured profile supports them.

## Decision-relevant synthesis

### Reachability versus control limitation

- **Decision relevance:** This distinction determines whether the first
  campaign direction should focus on target coverage/IK or on dynamic
  convergence and hold stabilization.
- **Assumptions:** The analytic FK/IK geometry matches the constrained MuJoCo
  model and the declared joint ranges are active.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Compare both IK branches and their FK residuals
  with target-conditioned episode diagnostics, joint-limit margins, and
  first-reach/hold outcomes.

### Effective dynamics and control authority

- **Decision relevance:** Mass/inertia defaults, damping, solver behavior, and
  effort saturation can determine whether a policy can settle inside a 1 cm
  ball at 50 Hz; they may change the priority of controller characterization
  versus learning changes.
- **Assumptions:** Omitted MuJoCo defaults are materially relevant and the
  gear-scaled motor is the effective physical input.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/policy_io.py`.
- **Discriminating evidence:** Inspect resolved model dynamics and measure
  impulse/constant-action acceleration, settling, saturation, and
  cross-joint response.

### Hold robustness and sampled semantics

- **Decision relevance:** Passing the task requires 100 consecutive checks,
  so the likely goal gap may be stabilization rather than reaching; sampled
  success does not by itself establish no 2 ms-scale excursions.
- **Assumptions:** The official 50 Hz step semantics remain authoritative and
  substep telemetry is used only as scientific diagnosis.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Measure velocity and tolerance margin at entry,
  every control check, every physics substep during holds, longest held run,
  and interruption cause.

### Observation sufficiency and runtime identity

- **Decision relevance:** Target position and both IK branches are exposed,
  but hold progress and action history are not; an eventual runtime transform
  can also alter the effective controller. This changes how policy behavior
  should be attributed and whether temporal state is a plausible bottleneck.
- **Assumptions:** The candidate's persisted `PolicyIO` and normalization are
  exactly those used by evaluation.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.
- **Discriminating evidence:** Verify the frozen runtime, replay identical
  observations, and compare branch-conditioned action/velocity trajectories
  and hold interruptions. This separates missing information from inadequate
  use of information already supplied.

### Official-distribution geometry

- **Decision relevance:** The baseline training radii omit \(0.06\) to
  \(0.14\) m, while the official distribution includes them; early aggregate
  performance may therefore reflect exposure mismatch rather than a general
  control limitation.
- **Assumptions:** The training environment remains the stated baseline and
  official assessment uses the fixed distribution in the task contract.
- **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Compare radius- and angle-stratified first-reach,
  hold, and success statistics under the official distribution, keeping the
  official outcome separate from development panels.
