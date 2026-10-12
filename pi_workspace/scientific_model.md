## Established facts

### Human-defined task and assessment

- **[Repository fact]** The official task samples a target with radius uniformly
  distributed on 0.06--0.20 m and angle uniformly distributed on
  \([-\pi,\pi)\). The target is in the arm's horizontal plane. Success requires
  the end effector to be at most 0.01 m from the target at every one of 100
  consecutive control steps, representing an uninterrupted 2 s hold. An
  episode is otherwise a failure, even if the arm reaches the target briefly.
  **Source:** `contracts/scenario.md` (Official task, Success criterion);
  `contracts/task_spec.py` (`TARGET_RADIUS_RANGE`, `SUCCESS_THRESHOLD`,
  `HOLD_SECONDS`, `FRAME_SKIP`).
- **[Repository fact]** The official panel contains 200 episodes, each with at
  most 500 control steps, and the goal is at least 196 successes (98%).
  **Source:** `contracts/scenario.md` (Official final assessment).

### Morphology, coordinates, and kinematics

- **[Repository fact]** The robot is a fixed-base, planar, serial two-link
  arm. The shoulder and elbow are revolute joints about the world \(z\) axis.
  Link lengths are \(l_1=0.12\) m and \(l_2=0.10\) m. The arm plane is at
  \(z=0.02\) m. The base is fixed to the world; there are no translational or
  out-of-plane degrees of freedom. **Source:** `contracts/robots/two_joint_arm.xml`
  (`base`, `upper_arm`, `forearm`, `shoulder`, `elbow`, `end_effector`);
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`).
- **[Repository fact]** The generalized configuration is
  \(q=(q_1,q_2)\), with both joint ranges \([-170^\circ,170^\circ]\).
  The end-effector forward kinematics are
  \[
    p(q)=\begin{bmatrix}
      l_1\cos q_1+l_2\cos(q_1+q_2)\\
      l_1\sin q_1+l_2\sin(q_1+q_2)\\
      0.02
    \end{bmatrix}.
  \]
  **Source:** `contracts/robots/two_joint_arm.xml` (joint axes, ranges,
  body offsets, capsule `fromto`, site position).
- **[Repository fact]** The unconstrained planar radial workspace is the
  annulus \(||l_1-l_2||\le r\le l_1+l_2\), i.e. 0.02--0.22 m, before applying
  the joint limits. The target distribution occupies 0.06--0.20 m, so it is
  strictly inside the nominal radial bounds. **Source:** link lengths in
  `contracts/robots/two_joint_arm.py`; target range in
  `contracts/task_spec.py`.
- **[Repository fact]** The XML has a non-colliding visual plane and a
  non-colliding, mocap target sphere. Gravity is explicitly zero. Thus the
  official success test is a geometric end-effector-to-target distance test,
  not grasping, contact, force closure, or support against gravity.
  **Source:** `contracts/robots/two_joint_arm.xml` (`gravity`, plane and target
  `contype`/`conaffinity`); `robot_learning/scenario/environment.py`
  (`_distance_to_target`, termination logic).

### Actuation, dynamics, and timing

- **[Repository fact]** The policy emits two floating-point controls in
  \([-1,1]\). The environment clips them, writes them directly to the two
  MuJoCo motor controls, and holds the same values for 10 physics steps.
  Each motor has scalar gear 5, so the nominal generalized motor contribution
  is \(5u_i\) in the MuJoCo actuator convention. There is no position target,
  inverse-kinematics command, or explicit policy-side torque controller in the
  default mapping. **Source:** `robot_learning/scenario/environment.py`
  (`step`); `robot_learning/scenario/policy_io.py` (`physical_action`);
  `contracts/robots/two_joint_arm.xml` (`motor`, `ctrlrange`, `gear`).
- **[Repository fact]** The physics timestep is 0.002 s and the control
  interval is \(10(0.002)=0.020\) s. The required hold is therefore
  `round(2.0/0.020)=100` post-integration control observations; the episode
  horizon is 500 control intervals, or 10 s. **Source:**
  `contracts/robots/two_joint_arm.xml` (`option timestep`);
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`
  (`control_dt`, `hold_steps_required`, `frame_skip`, `max_episode_steps`).
- **[Repository fact]** Each hinge has damping 0.5 and armature 0.01.
  Gravity is zero, while link mass and inertia are not explicitly specified
  in the XML. No explicit joint friction loss, actuator dynamics, integrator,
  or solver parameters are authored there. **Source:**
  `contracts/robots/two_joint_arm.xml` (joint attributes and `<option>`).

### Initial state, target construction, and episode mechanics

- **[Repository fact]** Reset sets both joint positions and velocities to zero,
  forwards the model, then samples one fixed target radius and angle. The
  initial end effector is therefore \(p(0)=(0.22,0,0.02)\), while the target
  has \(z=0.02\) and remains a mocap position during the episode. **Source:**
  `robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`);
  link geometry in `contracts/robots/two_joint_arm.xml`.
- **[Repository fact]** At every control step, a distance within 1 cm increments
  the current consecutive hold count; one outside sample resets it to zero.
  Termination is true only when the count reaches 100. The maximum-step
  truncation is separate from task success. **Source:**
  `robot_learning/scenario/environment.py` (`step`).
- **[Repository fact]** The current training environment samples only radii
  0.14--0.20 m, whereas the official distribution also contains 0.06--0.14 m.
  This is a changeable training recipe, not an alteration of the official
  assessment. **Source:** `robot_learning/training/environment.py`
  (`TRAINING_TARGET_RADIUS_RANGE`); `contracts/scenario.md`.

### Sensing, policy interface, and measured outcome

- **[Repository fact]** The default 11-component observation contains the two
  joint positions, two joint velocities, the three-dimensional end-effector
  minus target vector, and four wrapped angular errors to the elbow-open and
  elbow-folded inverse-kinematic solutions. The observation is exact simulator
  state; no sensor noise, delay, or quantization is introduced by the shown
  observation function. **Source:** `robot_learning/scenario/observations.py`
  (`reach_observation`, `OBSERVATION_SIZE`).
- **[Repository fact]** The two inverse-kinematic branches are computed from
  \[
    \cos q_2 =
    \frac{x_t^2+y_t^2-l_1^2-l_2^2}{2l_1l_2}
  \]
  and \(q_2=\pm\arccos(\operatorname{clip}(\cos q_2,-1,1))\); the corresponding
  shoulder angles are then constructed analytically. Clipping makes the
  representation defined even for an out-of-workspace target, although such a
  target is not in the official radial range. **Source:**
  `robot_learning/scenario/observations.py`.
- **[Repository fact]** The default policy input/output mapping is identity for
  both observation and action. A saved runtime can additionally bind a
  normalizer, recurrent reset, and model-specific I/O to the saved weights;
  runtime validation rejects mismatched weights or normalization files.
  **Source:** `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py` (`PolicyRuntime`, `validate_runtime_files`).
- **[Repository fact]** Research evaluation records success, episode length,
  minimum and final distance, first in-tolerance step, maximum consecutive
  hold, in-tolerance steps, and hold interruptions. These diagnostics are
  measurements of behavior and do not redefine the official success outcome.
  **Source:** `robot_learning/scenario/evaluation.py`
  (`episode_diagnostics`, `episode_results`).

## Physical consequences

### Reachability, inverse kinematics, and path alternatives

- **[Reasoned implication]** Every official target is nominally position
  reachable by at least one two-link configuration. For a target radius
  \(r\), the two branches have
  \(q_2=\pm\arccos((r^2-l_1^2-l_2^2)/(2l_1l_2))\); over 0.06--0.20 m this
  ranges approximately from \(\pm150^\circ\) to \(\pm49^\circ\), inside the
  elbow limits. The corresponding shoulder offsets leave a valid branch
  within the shoulder limits for every target angle in the official range.
  This establishes geometric possibility, not that a bounded motor policy can
  reach and stop there in 10 s.
  - **Decision relevance:** A failure should not initially be attributed to
    impossible target geometry; decisions can distinguish motion/control
    failure from static reachability failure. The two branches also permit
    different joint-limit margins and transient dynamics.
  - **Assumptions:** The XML joint-range behavior is the intended hard
    constraint; the target stays at the stated \(z\); compiled geometry does
    not change the site kinematics.
  - **Source references:** `contracts/scenario.md`;
    `contracts/task_spec.py`; `contracts/robots/two_joint_arm.xml`;
    `robot_learning/scenario/observations.py`.
  - **Discriminating evidence:** Compute FK residuals and joint-limit margins
    for both analytical branches over a dense target panel, then compare
    target-conditioned reach and hold outcomes by selected branch or observed
    joint posture.

- **[Reasoned implication]** The Jacobian
  \[
    J(q)=\begin{bmatrix}
    -l_1\sin q_1-l_2\sin(q_1+q_2)&-l_2\sin(q_1+q_2)\\
     l_1\cos q_1+l_2\cos(q_1+q_2)& l_2\cos(q_1+q_2)
    \end{bmatrix}
  \]
  maps joint motion to planar end-effector motion. It loses rank at the
  fully extended and fully folded radial boundaries. The official interval
  excludes those exact boundaries but comes within 2 cm of the 0.22 m
  extension boundary, so branch-dependent conditioning and radial/tangential
  control authority can still matter.
  - **Decision relevance:** It can change whether the first performance
    diagnosis emphasizes target geometry, configuration selection, or generic
    policy capacity; distance-only success can hide a directionally weak
    controller.
  - **Assumptions:** The relevant local behavior is well approximated by the
    kinematic Jacobian during the hold; actuator and joint constraints do not
    dominate first.
  - **Source references:** link geometry and joint axes in
    `contracts/robots/two_joint_arm.xml`; target range in
    `contracts/task_spec.py`.
  - **Discriminating evidence:** Record \(q\), \(J\)'s singular values,
    branch identity, end-effector velocity, and distance excursions by target
    radius and angle.

### Torque-driven motion and dynamic coupling

- **[Reasoned implication]** A constant action is a constant motor command
  over 20 ms, not a constant end-effector velocity or position. The arm's
  joint acceleration therefore depends on configuration-dependent two-link
  inertia, velocity-dependent coupling, damping, armature, and the available
  motor torque. Shoulder and elbow commands are coupled at the end effector,
  so independently shaped action coordinates do not produce independent
  Cartesian coordinates.
  - **Decision relevance:** Reaching may require anticipating momentum and
    braking, while holding may require small corrective torques. A recipe
    optimized for fast approach can have poor hold success even with good
    minimum distance.
  - **Assumptions:** The standard rigid-body MuJoCo equations apply and the
    compiled link inertias are finite; no unmodeled external force acts.
  - **Source references:** motor and joint definitions in
    `contracts/robots/two_joint_arm.xml`; action integration in
    `robot_learning/scenario/environment.py`.
  - **Discriminating evidence:** Measure action, \(q,\dot q\), finite-difference
    acceleration, end-effector velocity, and distance at every control step;
    compare the same command at multiple configurations.

- **[Reasoned implication]** Damping dissipates velocity and armature adds
  acceleration resistance, while zero gravity removes a major static load.
  With no authored actuator lag, the main temporal effects are the 2 ms
  numerical integration, 20 ms zero-order action hold, rigid-body inertia,
  velocity coupling, and damping. The 1 cm band is crossed and sampled only
  once per 20 ms control interval, so a trajectory can leave and re-enter
  between observations without that intermediate excursion being directly
  represented in the task counter.
  - **Decision relevance:** This determines whether the first control problem
    is primarily anticipation/stabilization at the control rate or a slower
    reach problem, and whether the observed hold metric can be interpreted as
    continuous physical containment.
  - **Assumptions:** MuJoCo's internal substeps are the only state evolution
    between policy calls and no hidden evaluator checks intermediate samples.
  - **Source references:** `contracts/robots/two_joint_arm.xml` (`timestep`,
    damping, armature); `contracts/task_spec.py` (`FRAME_SKIP`,
    `HOLD_SECONDS`); `robot_learning/scenario/environment.py` (`step`).
  - **Discriminating evidence:** Log substep distance and velocity in a
    diagnostic measurement, compare it with the post-control-step hold count,
    and estimate settling time after a target approach.

### Initial geometry and task difficulty

- **[Reasoned implication]** The arm begins fully extended at 22 cm on the
  positive \(x\) axis with zero velocity, while the target is at most 20 cm
  from the base. Thus the target is never initially coincident with the
  end effector; the initial distance can be approximately 2 cm for a
  same-angle 20 cm target and up to 42 cm for an opposite-angle 20 cm target.
  The policy must both rotate/reconfigure and remove initial transient error.
  - **Decision relevance:** Early distance and direction errors may reflect
    the reset geometry rather than poor local stabilization; target-angle and
    radius stratification is necessary before changing the controller.
  - **Assumptions:** The site position and link lengths give the stated FK
    position and the sampled target is fixed after reset.
  - **Source references:** `robot_learning/scenario/environment.py`
    (`reset`, `_sample_target_position`); `contracts/robots/two_joint_arm.xml`;
    `contracts/task_spec.py`.
  - **Discriminating evidence:** Compare initial distance, initial bearing,
    first-reach time, and success by target angle/radius; verify the reset
    state directly.

- **[Reasoned implication]** The shorter-radius portion of the official
  distribution is physically different from the current baseline exposure:
  reaching inward requires more elbow folding and is absent from training
  samples below 14 cm. The policy can still observe the actual target and IK
  errors, but generalization across this radial regime is not established by
  the repository.
  - **Decision relevance:** This is the most direct reason a policy can appear
    strong on development behavior yet fail the official 98% objective; it
    can change whether initial evaluation must be geometry-stratified.
  - **Assumptions:** The current training environment is the recipe used for
    the candidate under consideration and the official distribution remains
    the contract.
  - **Source references:** `robot_learning/training/environment.py`;
    `contracts/scenario.md`; `contracts/task_spec.py`.
  - **Discriminating evidence:** Use matched-seed evaluation with separate
    radial bins, including 0.06--0.14 m, and inspect joint trajectories and
    hold interruptions rather than pooled success alone.

### What success physically requires

- **[Reasoned implication]** Success is a conjunction of (1) entering the
  tolerance band, (2) converging sufficiently that the sampled distance
  remains inside it, and (3) maintaining a stable bounded trajectory for
  100 control intervals. Reaching, braking, local configuration choice, and
  disturbance-free stabilization are therefore coupled: residual velocity or
  an ill-conditioned configuration can turn a successful reach into a hold
  failure.
  - **Decision relevance:** A single success percentage cannot identify whether
    the limiting capability is reach, convergence, or stabilization; the first
    campaign measurements should preserve all three distinctions.
  - **Assumptions:** No external disturbance or target motion is present, and
    the sampled distance is an adequate task state for the success definition.
  - **Source references:** `contracts/scenario.md`; `robot_learning/scenario/environment.py`;
    `robot_learning/scenario/evaluation.py`.
  - **Discriminating evidence:** Use first-reach step, maximum consecutive hold,
    interruption count, final distance, velocity at first entry, and distance
    variance during the hold.

- **[Reasoned implication]** Multiple joint solutions make the task
  underdetermined in configuration space: the same target position can be
  reached elbow-open or elbow-folded. A policy may choose either, switch
  branches during motion, or approach a joint limit. Since success imposes no
  posture or path preference, such alternatives are physically valid unless
  dynamics or joint limits make one unreliable.
  - **Decision relevance:** It can change whether a stable policy should be
    understood as a single-posture controller or a target-conditioned
    multimodal controller, and whether failures are branch-selection failures.
  - **Assumptions:** Only end-effector distance defines task success; there is
    no hidden posture cost in the official evaluator.
  - **Source references:** `robot_learning/scenario/observations.py` (both IK
    branches); `contracts/scenario.md`; `robot_learning/scenario/environment.py`.
  - **Discriminating evidence:** Classify trajectories by the sign and
    magnitude of \(q_2\), branch residuals, joint-limit margin, and hold
    reliability for each class.

### Observation-to-outcome relation

- **[Reasoned implication]** The actual joint state and target-relative vector
  make the task state sufficiently specified for deterministic model-based
  prediction of geometric error: FK reconstructs the end effector, and the
  relative vector plus FK reconstructs the target position. The observation
  does not expose mass, inertia, actuator torque, acceleration, solver
  constraint forces, or substep history. Thus it is rich for kinematics but
  incomplete for direct inverse dynamics; a memoryless policy must infer
  dynamic quantities from \(q,\dot q\) and repeated interaction, while a
  recurrent runtime can retain history.
  - **Decision relevance:** It can change whether a first method is expected to
    learn primarily a kinematic mapping or a dynamic feedback law, and whether
    failures should motivate richer observations rather than more training.
  - **Assumptions:** Observation values are exact and the model/runtime
    semantics are frozen with the saved policy.
  - **Source references:** `robot_learning/scenario/observations.py`;
    `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`.
  - **Discriminating evidence:** Compare action quality and hold success for
    policies with and without temporal memory, while logging acceleration,
    torque command, configuration, and distance.

- **[Reasoned implication]** The episode outcome is produced by the sequence
  \(o_k \rightarrow u_k \rightarrow\) 10 MuJoCo integrations
  \(\rightarrow p_{k+1}\rightarrow d_{k+1}\), with the hold counter applying
  to \(d_{k+1}\). Reward can shape this sequence through progress, closeness,
  hold-progress, action cost, and an outside-band term, but the reward is not
  the success definition. In particular, the current reward forfeits no hold
  capital when a hold is exited (`HOLD_EXIT_FORFEIT_FRACTION=0`), so reward
  preference and uninterrupted-task reliability are not identical concepts.
  - **Decision relevance:** Reward changes can improve a proxy while leaving
    the 98% episode objective unchanged; policy selection must therefore use
    complete hold outcomes and failure decomposition.
  - **Assumptions:** The current reward is used for the candidate and no
    protected evaluator adds an unlisted physical criterion.
  - **Source references:** `robot_learning/training/reward.py`;
    `robot_learning/scenario/environment.py`; `contracts/scenario.md`.
  - **Discriminating evidence:** Relate reward components and training
    diagnostics to independent episode success, maximum hold, and interruption
    counts on fixed target panels.

### Scientific quantities for the complete behavior

- **[Reasoned implication]** The physically meaningful trajectory is the time
  series of target pose, \(q,\dot q\), commanded control and nominal motor
  torque, end-effector pose/velocity, distance, Jacobian conditioning,
  joint-limit margin, energy/action magnitude, and the binary in-tolerance
  and consecutive-hold states. Their ordering separates approach, crossing,
  convergence, stabilization, and failure. Aggregates such as minimum
  distance alone do not preserve that causal distinction.
  - **Decision relevance:** These quantities identify which capability limits
    the route to 98% and prevent selecting a policy that reaches often but
    cannot stabilize.
  - **Assumptions:** Logged simulator state is sufficiently precise and can be
    aligned to each 20 ms action interval.
  - **Source references:** `robot_learning/scenario/evaluation.py`;
    `robot_learning/scenario/environment.py`; `contracts/robots/two_joint_arm.xml`.
  - **Discriminating evidence:** Preserve per-step trajectories and report
    geometry-stratified summaries for first reach, hold continuity, velocity,
    action, conditioning, and limit margin.

## Unknowns

### Effective compiled rigid-body dynamics

- **[Unresolved quantity]** The XML does not state link masses, densities,
  explicit inertial tensors, compiled actuator force limits beyond the control
  and gear declarations, or solver/integrator choices. MuJoCo will compile
  effective values from the model and its defaults, but their numerical values
  and the resulting \(M(q)\), coupling terms, and acceleration response are
  not established by reading the authored XML alone.
  - **Decision relevance:** The unknown can change whether the action range is
    ample, marginal, or saturating for fast approach and fine holding, and
    therefore whether model-free training or explicit dynamics identification
    is the credible first direction.
  - **Assumptions:** The compiled model is the authoritative simulator and
    defaults are stable across the evaluation runtime.
  - **Source references:** `contracts/robots/two_joint_arm.xml` (absence of
    explicit mass/inertia/solver fields); `robot_learning/scenario/environment.py`
    (`MjModel.from_xml_path`).
  - **Discriminating evidence:** Inspect compiled `MjModel` masses, inertias,
    actuator quantities, timestep integrator/solver fields, and apply
    controlled single-joint or small-signal perturbations at several
    configurations.

### Constraint and numerical behavior at joint limits

- **[Unresolved quantity]** The intended joint intervals are explicit, but the
  exact compiled enforcement behavior, limit reaction forces, and numerical
  effect of impacts or repeated limit contact are not specified in the
  human-authored model. The official targets are geometrically inside the
  limits, yet a high-speed trajectory can reach a limit before settling.
  - **Decision relevance:** Limit contact could explain angle-dependent
    failures and favor branch-aware or slower trajectories; without evidence,
    it is unsafe to treat a target-conditioned failure as purely learning
    failure.
  - **Assumptions:** MuJoCo joint ranges are active constraints under the
    compiled defaults and no other collision geometry contributes contact.
  - **Source references:** `contracts/robots/two_joint_arm.xml` (joint
    `range`, non-colliding geoms); `robot_learning/scenario/environment.py`.
  - **Discriminating evidence:** Log joint-limit margin and constraint force
    indicators during failed and successful episodes, especially at target
    angles near the shoulder range endpoints.

### Between-sample physical trajectory

- **[Unresolved quantity]** The official predicate is defined at 100
  consecutive control steps, and the visible environment updates its counter
  after each 10-substep, 20 ms action interval. The maximum distance excursion
  inside each 2 ms substep interval is not exposed to the policy or the
  episode diagnostics. Thus official sampled success is established, while
  physical containment between sampled observations is an unresolved
  trajectory quantity rather than an additional success criterion.
  - **Decision relevance:** A controller can satisfy the sampled predicate
    while having a smaller physical safety margin than its distance trace
    suggests. This matters for interpreting stabilization mechanisms and for
    deciding whether a safety-margin diagnostic is needed, but does not alter
    the stated official outcome.
  - **Assumptions:** The visible scenario mechanics implement the contract's
    control-step semantics; substep traces are used for diagnosis, not to
    redefine success.
  - **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
    `robot_learning/scenario/environment.py` (`for _ in range(frame_skip)`,
    then distance and hold update).
  - **Discriminating evidence:** Record distance at every physics substep and
    compare its within-interval maximum with the post-step hold outcome on
    the same episodes.

### Candidate-specific runtime semantics

- **[Unresolved quantity]** For a future saved policy, it is not known in
  advance whether its runtime contains observation normalization, recurrent
  state, or a non-identity policy I/O closure. The default source mapping is
  identity, but runtime artifacts can bind exact candidate-specific behavior.
  - **Decision relevance:** A mismatch between training-time and evaluation-time
    I/O or recurrence can look like a physical/control failure and invalidate
    comparisons between candidates.
  - **Assumptions:** Candidate artifacts are loaded through the human-owned
    runtime validator and not through legacy scientific code.
  - **Source references:** `robot_learning/scenario/policy_io.py`;
    `contracts/policy_runtime.py` (`save_runtime`, `validate_runtime_files`,
    `PolicyRuntime.predict`).
  - **Discriminating evidence:** Verify the saved runtime digest and inspect
    its bound observation/action/reset callables and normalizer before
    attributing an outcome to morphology or dynamics.

### Behavioral capability and failure mixture

- **[Unresolved quantity]** No pre-campaign fact establishes policy success,
  first-reach latency, branch preference, settling time, hold interruption
  rate, or their dependence on target radius and angle. The repository's
  evaluation schema can record these quantities, but it does not supply their
  values here.
  - **Decision relevance:** The first campaign decision depends on whether the
    gap to 98% is dominated by broad reachability, the inner-radius
    distribution, or rare hold failures; aggregate reward or a single
    development score cannot decide that.
  - **Assumptions:** A candidate and fixed-seed panel are measured with the
    exact task semantics and the diagnostics are retained without selection
    bias.
  - **Source references:** `contracts/scenario.md`;
    `robot_learning/scenario/evaluation.py` (`episode_diagnostics`);
    `robot_learning/scenario/environment.py`.
  - **Discriminating evidence:** Evaluate fixed panels with the official
    radius/angle distribution and inspect per-episode outcomes plus the
    complete trajectory quantities listed above.

### Observation sufficiency for dynamic prediction

- **[Unresolved quantity]** The observation is kinematically informative, but
  it is unknown whether \(q,\dot q\), target-relative position, and the
  four IK residuals are sufficient for the policy class and horizon to infer
  the dynamic state needed for 1 cm stabilization. The simulator state also
  contains quantities not exposed to the policy, including compiled model
  parameters and substep history.
  - **Decision relevance:** If the representation is dynamically sufficient in
    practice, added sensing is unnecessary; if not, representation or memory
    changes may be more valuable than additional optimization.
  - **Assumptions:** The policy observes only the declared 11-vector and the
    candidate's recurrent state, if any.
  - **Source references:** `robot_learning/scenario/observations.py`;
    `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`.
  - **Discriminating evidence:** Compare matched candidates with memoryless
    and recurrent inference, and test predictive residuals for next-step
    position/velocity using the same observations.

## Decision-relevant synthesis

### Official geometry differs from current training exposure

- **[Reasoned implication] Decision relevance:** The official 6--20 cm radial
  distribution includes 8 cm of inner targets absent from the current
  14--20 cm training recipe; this is the clearest pre-evidence source of a
  geometry-dependent gap to 98%.
- **Assumptions:** The baseline candidate uses
  `robot_learning/training/environment.py`, while the official contract is
  unchanged.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/training/environment.py`.
- **Discriminating evidence:** Fixed-seed official-distribution evaluation
  separated into 6--14 cm and 14--20 cm bins, with joint posture and hold
  interruption diagnostics.

### The objective is stabilization, not merely reaching

- **[Reasoned implication] Decision relevance:** A target can be reached and
  still fail because one outside-tolerance sample resets the 100-step hold;
  approach speed, braking, local conditioning, and residual velocity are
  coupled to the actual episode outcome.
- **Assumptions:** The visible consecutive-step predicate is the authoritative
  success mechanism and no external disturbance moves the target.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** First-reach step, maximum held steps,
  interruption count, final distance, and velocity/distance traces during the
  attempted hold, not only minimum distance or reward.

### Action authority and effective dynamics are not numerically closed

- **[Unresolved quantity] Decision relevance:** Controls are bounded motors
  held for 20 ms, but effective inertia, compiled mass properties, solver
  behavior, and limit reactions are not explicit. The first method choice
  depends on whether the action range gives robust braking and fine correction.
- **Assumptions:** MuJoCo compilation defaults materially determine the
  unlisted dynamic quantities and the XML is the complete physical model.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/policy_io.py`.
- **Discriminating evidence:** Inspect the compiled model and run small
  controlled perturbations while recording action, acceleration, velocity,
  distance, and constraint/limit indicators.

### The state is kinematically rich but dynamically partial

- **[Reasoned implication] Decision relevance:** Exact \(q,\dot q\), target
  error, and both IK branch errors support direct geometric feedback, while
  unobserved acceleration and model parameters may make 1 cm holding a
  history-dependent problem. This determines whether memory or a different
  representation is scientifically justified.
- **Assumptions:** Candidate runtime preserves the declared observation and
  any recurrent state is correctly reset at episode boundaries.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`.
- **Discriminating evidence:** Matched memoryless/recurrent comparisons with
  next-step prediction residuals and hold success stratified by target
  geometry and IK branch.

### Multiple valid postures make failure attribution non-unique

- **[Reasoned implication] Decision relevance:** Elbow-open and elbow-folded
  solutions both satisfy the geometric task, but can differ in conditioning,
  limit margin, transient torque demand, and stabilization. A failed episode
  cannot be assigned to target geometry alone without its joint trajectory.
- **Assumptions:** The official evaluator imposes no hidden posture or path
  preference beyond end-effector tolerance and uninterrupted duration.
- **Source references:** `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml`; `contracts/scenario.md`.
- **Discriminating evidence:** Joint-sign/branch classification, Jacobian
  singular values, limit margin, action effort, and hold continuity for every
  target-conditioned failure class.
