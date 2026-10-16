## Established facts

### Scope and scientific authority

- **[Repository fact]** The human goal is episode success, not reward: a target
  is sampled at a radius of 6--20 cm over the full angular range, the
  end-effector must be within 1 cm of it for an uninterrupted 2 seconds, and
  the campaign seeks at least 196 successes in the fixed 200-episode official
  assessment (98%). Each episode has at most 500 control steps.
  **Source:** `contracts\scenario.md:8-31`.
- **[Repository fact]** The official robot, physics, interaction semantics,
  distribution, and success definition are human-owned and immutable. This
  document is a pre-campaign model; it contains no campaign evidence and does
  not assert that any policy succeeds.
  **Source:** `contracts\scenario.md:33-35`,
  `contracts\program.md` (Campaign startup), `AGENTS.md` (ownership).
- **[Repository fact]** The scientific runtime is native MuJoCo 3.12.0 with
  Gymnasium 1.3.0 and Stable-Baselines3 2.9.0; the XML is loaded by
  `mujoco.MjModel.from_xml_path`.
  **Source:** `AGENTS.md` (Environment),
  `robot_learning\scenario\environment.py:1-27`.

### Morphology and coordinates

- **[Repository fact]** The base is fixed to the world because its body has no
  joint. It carries a shoulder hinge and a child forearm carrying an elbow
  hinge; both hinge axes are the world/body-local \(z\) axis. The upper arm is
  0.12 m, the forearm is 0.10 m, and the end-effector site is at the distal
  end of the forearm. The link capsule radii are 0.015 m and 0.012 m.
  **Source:** `contracts\robots\two_joint_arm.xml:9-21`,
  `contracts\robots\two_joint_arm.py:3-7`.
- **[Repository fact]** The arm's joint coordinates are the XML-ordered
  shoulder and elbow hinge positions. Both have declared ranges of -170 to
  170 degrees. The target is a mocap body with a 0.012 m visual sphere; it is
  not a jointed or actuated object.
  **Source:** `contracts\robots\two_joint_arm.xml:13-18,25-26`.
- **[Repository fact]** The arm is placed at \(z=0.02\) m by the upper-arm body
  offset. Resetting the two joint positions to zero therefore aligns both
  links along positive \(x\) and places the site in the arm plane. The target
  is reset into that same \(z\) plane.
  **Source:** `contracts\robots\two_joint_arm.xml:12,16,21`,
  `robot_learning\scenario\environment.py:104-115`.

### Simulator, actuation, and timing

- **[Repository fact]** Gravity is explicitly zero and the MuJoCo integration
  timestep is 0.002 s. The task environment advances ten MuJoCo steps per
  policy action, so the nominal control period is 0.020 s (50 Hz); the 2 s
  hold is computed as 100 control steps and the 500-step episode limit is
  nominally 10 s.
  **Source:** `contracts\robots\two_joint_arm.xml:2`,
  `contracts\task_spec.py:6-11`,
  `robot_learning\scenario\environment.py:53-58`.
- **[Repository fact]** Each joint has explicit viscous damping 0.5 and
  armature 0.01. Each motor accepts control in [-1, 1] and has gear 5. No
  separate actuator force range is declared. The action space is also
  [-1, 1] for both joints.
  **Source:** `contracts\robots\two_joint_arm.xml:13-18,30-32`,
  `robot_learning\scenario\environment.py:60-67`.
- **[Repository fact]** The plane, base geom, and target geom explicitly have
  collision type and affinity zero. The upper-arm and forearm capsules do not
  specify those attributes, so their effective self-collision filtering is
  inherited from MuJoCo defaults rather than stated in the robot contract.
  **Source:** `contracts\robots\two_joint_arm.xml:6,10-11,15,19,26`.
- **[Repository fact]** The environment clips the policy action, writes it to
  `data.ctrl`, and holds that control constant over all ten internal
  `mj_step` calls. There is no scenario-owned action smoothing, joint-position
  servo, or action-delay model.
  **Source:** `robot_learning\scenario\environment.py:122-134`,
  `robot_learning\scenario\policy_io.py:7-16`.

### Reset, target, and outcome mechanics

- **[Repository fact]** Reset calls `mj_resetData`, sets both joint positions
  and velocities to zero, performs forward kinematics, samples an angle
  uniformly from \([-\pi,\pi]\) and a radius uniformly from [0.06, 0.20] m,
  then places the target at that radius and at the current end-effector
  \(z\). The target remains fixed during the episode.
  **Source:** `robot_learning\scenario\environment.py:102-118,83-97`.
- **[Repository fact]** Distance is the three-dimensional Euclidean distance
  between the end-effector site position and the target mocap position. After
  every control block, distance at that sample is compared with 0.01 m:
  an in-tolerance sample increments the consecutive hold counter, while an
  outside sample resets it to zero. Success is termination at 100 consecutive
  samples; the 500-step limit is truncation.
  **Source:** `contracts\task_spec.py:6-11`,
  `robot_learning\scenario\environment.py:128-168`.
- **[Repository fact]** The target and the end-effector are not coupled by a
  contact requirement: the target is mocap and its geom is non-colliding, and
  the task measures site-to-mocap distance rather than contact force or
  surface intersection.
  **Source:** `contracts\robots\two_joint_arm.xml:21,25-26`,
  `robot_learning\scenario\environment.py:75-80,128-135`.

### Observation and policy interface

- **[Repository fact]** The raw observation has 11 components: two joint
  positions, two joint velocities, the three-vector from target to
  end-effector, and four wrapped joint errors for the positive-elbow and
  negative-elbow inverse-kinematic candidates.
  **Source:** `robot_learning\scenario\observations.py:11-46`.
- **[Repository fact]** The policy receives the scenario observation through
  `PolicyIO`; the physical action mapping is the identity before environment
  clipping. `held_steps`, target radius/angle, episode step count, reward,
  torque, acceleration, contact forces, and the model's compiled inertial
  parameters are not included in the raw observation.
  **Source:** `robot_learning\scenario\policy_io.py:7-16`,
  `robot_learning\scenario\environment.py:155-167`.
- **[Repository fact]** A saved policy runtime may normalize and clip the raw
  observation and may maintain recurrent model state. Evaluation resets that
  runtime at the beginning of each episode; this preprocessing is part of a
  learned artifact, not an additional physical sensor.
  **Source:** `contracts\policy_runtime.py:150-176`,
  `robot_learning\scenario\evaluation.py:50-52`.

### Reward and official success

- **[Repository fact]** The baseline reward combines distance progress,
  exponential closeness, hold progress, a small outside-band term, a
  completion bonus, and an action-square cost. The reward is returned to the
  learning algorithm, but the task outcome is the consecutive-hold success
  condition, not the reward total.
  **Source:** `robot_learning\training\reward.py:16-25,47-105`,
  `robot_learning\scenario\environment.py:146-168`,
  `contracts\scenario.md:14-31`.

## Physical consequences

### Planar kinematics, workspace, branches, and singularity

- **[Reasoned implication]** With \(q_1\) the shoulder angle and \(q_2\) the
  relative elbow angle, the site position is
  \[
  p(q)=\left(L_1\cos q_1+L_2\cos(q_1+q_2),\
  L_1\sin q_1+L_2\sin(q_1+q_2),\ 0.02\right),
  \]
  with \(L_1=0.12\) m and \(L_2=0.10\) m. The ideal point workspace is the
  annulus \(0.02\leq r\leq0.22\) m. The official radii 0.06--0.20 m are
  strictly inside that radial annulus, so ideal point reachability is not
  itself an obvious task impossibility.
- **[Reasoned implication]** For an interior target radius,
  \[
  \cos q_2=\frac{r^2-L_1^2-L_2^2}{2L_1L_2}
  \]
  gives two configurations \(q_2=\pm\alpha\), with
  \(\alpha\) approximately 49.5--150.1 degrees over the official radial
  range. The corresponding shoulder angles are the two elbow-up/elbow-down
  branches represented by the four IK-error features. At every official
  direction, at least one branch can keep the shoulder within its declared
  range in the ideal point model; branch selection is therefore an available
  solution, not merely a numerical detail.
- **[Reasoned implication]** The reset pose \(q_1=q_2=0\) is fully extended at
  \(r=0.22\) m. The planar Jacobian has determinant
  \(L_1L_2\sin q_2\), so it is rank-deficient at reset. Initial Cartesian
  motion is therefore directionally constrained until the controller creates
  elbow deflection; the target distribution does not remove this common
  transient.
- **[Reasoned implication]** At reset the end effector is at
  \((0.22,0,0.02)\) m, so the initial target distance is
  \[
  d_0=\sqrt{0.22^2+r^2-2(0.22)r\cos\theta}.
  \]
  Across the official distribution it ranges from 0.02 m to 0.42 m.
  Consequently every episode starts outside the 0.01 m success ball and
  requires a physical approach before holding can begin.
- **Decision relevance [Reasoned implication]** Early research decisions can
  distinguish dynamic approach and branch/limit handling from an
  unreachable-target problem. A policy can be physically successful through
  either branch, but a branch choice that drives a joint toward a limit or
  a self-contact configuration can create a qualitatively different trajectory.
- **Assumptions [Unresolved quantity]** These conclusions use the point
  kinematic chain and ignore any effective capsule self-contact, compiler
  limit behavior, or finite-time actuator constraint. Those effects can
  reduce the dynamically usable part of the ideal workspace without changing
  the geometric annulus.
- **Source references [Repository fact]** `contracts\robots\two_joint_arm.xml:12-21`,
  `contracts\robots\two_joint_arm.py:5-7`,
  `robot_learning\scenario\observations.py:20-46`,
  `robot_learning\scenario\environment.py:83-97`.
- **Discriminating evidence [Reasoned implication]** A model-forward
  reachability calculation and episode records stratified by target radius,
  angle, selected branch, joint-limit proximity, and final distance would
  support the kinematic account if residuals are small across both branches.
  Persistent failures at reachable targets, or contact/limit events confined
  to one branch, would weaken the ideal point-workspace account.

### Direct torque control and dynamic authority

- **[Reasoned implication]** Away from contact and joint limits, the motion
  can be represented as
  \[
  M(q)\ddot q+C(q,\dot q)\dot q+
  \operatorname{diag}(0.5,0.5)\dot q
  =\tau_{\mathrm{motor}},
  \]
  with gravity absent and the explicit 0.01 armatures included in the
  generalized inertia. In the standard MuJoCo motor transmission, the
  requested generalized motor force is proportional to \(5u\), where
  \(u\in[-1,1]^2\); the action is therefore a saturated torque-like command,
  not a desired joint angle or Cartesian velocity.
- **[Reasoned implication]** The 20 ms zero-order hold means the policy has
  only 50 opportunities per second to change torque, while the simulator
  integrates ten 2 ms substeps. Link inertia, inertial coupling, damping,
  Coriolis effects, and any link contact determine how much motion a saturated
  command produces. A large action can improve approach time while increasing
  residual velocity at entry to the tolerance band.
- **[Reasoned implication]** Because gravity and target contact are absent, an
  interior configuration with \(\dot q=0\), no active contact, and zero motor
  command is a static equilibrium. Successful holding is consequently a
  convergence-and-braking problem rather than force closure or balancing
  against a load; damping can remove residual motion, but it does not guarantee
  that a fast approach arrives with sufficiently small velocity.
- **Decision relevance [Reasoned implication]** Control choices should be
  judged by the coupled torque-to-acceleration and settling behavior, not by
  nominal action magnitude alone. The first useful physical distinction is
  whether failures are authority-limited approaches, overshoot caused by
  residual momentum, or unstable policy commands inside the tolerance band.
- **Assumptions [Unresolved quantity]** The equation assumes no active
  self-contact or joint-limit impulse during the segment and treats the
  MuJoCo motor defaults as the intended direct-transmission semantics.
  Effective \(M(q)\), default density, and numerical solver behavior are not
  numerically stated in the XML.
- **Source references [Repository fact]** `contracts\robots\two_joint_arm.xml:2,13-18,30-32`,
  `robot_learning\scenario\environment.py:122-134`,
  `AGENTS.md` (locked MuJoCo version).
- **Discriminating evidence [Reasoned implication]** Compiled model
  parameters plus controlled single-joint and two-joint torque trajectories
  would identify the effective acceleration, damping, coupling, and
  saturation. During policy evaluation, joint velocity at first entry,
  action saturation, and distance overshoot would support or weaken the
  authority-versus-settling explanation.

### The hold couples reaching, convergence, and stabilization

- **[Reasoned implication]** The first in-tolerance post-action sample must
  occur no later than control step 401 to leave 100 samples through step 500.
  Thus the 500-step horizon gives an approach budget of at most about 8.0 s
  before a full 2.0 s hold; entering early but with nonzero velocity is not
  equivalent to completing the task.
- **[Reasoned implication]** The 1 cm criterion is a ball around the target
  site position, not a surface-contact or force criterion. A trajectory can
  cross the ball and still fail if its sampled distance later exceeds 1 cm.
  Since the hold counter resets rather than accumulating across interruptions,
  one excursion destroys the complete-hold condition.
- **[Reasoned implication]** The environment checks distance after each
  20 ms action block. The implemented continuity requirement is therefore
  continuity at control-step observations; motion between checks is not itself
  counted by the visible scenario loop. A policy that oscillates within a
  block could be physically different from one that remains close throughout,
  even if both have the same sampled hold counter.
- **Decision relevance [Reasoned implication]** Reaching metrics alone cannot
  select a task-relevant policy. The decision frontier must separate first
  entry, settling time, uninterrupted hold length, interruption count, and
  final distance; a policy with a lower minimum distance can still be worse
  on the human objective.
- **Assumptions [Unresolved quantity]** This interpretation assumes the
  protected assessment uses the same stated 100-control-step semantics as the
  visible task contract. The protected evaluator is authoritative for any
  additional temporal sampling.
- **Source references [Repository fact]** `contracts\scenario.md:10-17,25-31`,
  `contracts\task_spec.py:7-11`,
  `robot_learning\scenario\environment.py:128-168`,
  `robot_learning\scenario\evaluation.py:62-121`.
- **Discriminating evidence [Reasoned implication]** Per-control-step
  distance and velocity traces, including the minimum distance, first reach
  step, longest held run, interruptions, and substep extrema, would distinguish
  true settling from sampled boundary crossing. Agreement between visible
  traces and official outcomes would support the timing interpretation.

### Observation, control, and observability

- **[Reasoned implication]** For the fixed target and the direct motor model,
  the raw observation contains the physical variables needed to propagate the
  next state: \(q\), \(\dot q\), and the target-relative site vector. Since
  \(q\) determines the site position, the relative vector also determines the
  target position; target radius and angle are not irretrievably hidden.
  The four IK errors are derived, redundant branch coordinates rather than
  independent sensors.
- **[Reasoned implication]** The physical state is close to Markov for the
  deterministic simulator, but the task automaton is not fully observable:
  `held_steps` and `_step_count` are not in the observation. Two episodes can
  have the same physical observation while differing in accumulated hold
  progress or remaining time. Recurrent policy state can represent history,
  whereas a memoryless policy must succeed by maintaining a state that never
  exits tolerance rather than by knowing the counter.
- **[Reasoned implication]** The raw sensing model has no declared noise,
  filtering, delay, or force/contact sensing. Any information loss from
  normalization, clipping, or recurrence is a learned-runtime property, not
  a property of the MuJoCo body state.
- **Decision relevance [Reasoned implication]** A failure should not be
  attributed to target ambiguity before checking the complete raw state:
  the target-relative vector and joint state expose the geometry. Conversely,
  a policy that relies on hidden elapsed time or hidden hold progress may
  behave differently under runtime reset or across episode lengths.
- **Assumptions [Unresolved quantity]** The Markov claim assumes the motor has
  no unobserved activation state and that no solver/contact state materially
  persists beyond \(q,\dot q\). The final candidate's normalizer, recurrent
  state, and clipping range are not known before a candidate exists.
- **Source references [Repository fact]** `robot_learning\scenario\observations.py:11-46`,
  `robot_learning\scenario\policy_io.py:7-16`,
  `contracts\policy_runtime.py:150-176`,
  `robot_learning\scenario\environment.py:136-168`.
- **Discriminating evidence [Reasoned implication]** Replaying identical raw
  states with different hold histories can test task-state aliasing; inspecting
  the saved runtime and comparing raw versus policy-input observations can
  test preprocessing loss. Prediction changes under controlled history
  changes would support the relevance of recurrence or hidden automaton state.

### Behavior classes under the official distribution

- **[Reasoned implication]** The principal failure classes are: late or
  unsuccessful approach; valid geometric approach blocked by joint-limit or
  self-contact behavior; overshoot or repeated boundary crossing during
  settling; and stable entry followed by a hold interruption. The same final
  minimum distance does not identify which class occurred.
- **[Reasoned implication]** Radius changes the required elbow angle and
  initial distance, while angle changes the shoulder branch and proximity to
  the shoulder limits. Because the official distribution covers all angles,
  a policy that works only in a preferred sector cannot support 98% episode
  success even if its aggregate development mean is high.
- **Decision relevance [Reasoned implication]** Candidate comparisons should
  preserve the episode outcome and geometry-conditioned diagnostics. The
  four-failure allowance in a 200-episode official panel makes rare
  angle/branch tails decision-relevant, not merely descriptive.
- **Assumptions [Repository fact]** This consequence assumes the visible
  evaluation diagnostics retain the target angle, target radius, minimum and
  final distance, first reach, maximum held run, and interruptions; those
  fields are explicitly recorded by the scenario evaluator.
- **Source references [Repository fact]** `contracts\scenario.md:8-31`,
  `robot_learning\scenario\environment.py:83-97`,
  `robot_learning\scenario\evaluation.py:62-121`.
- **Discriminating evidence [Reasoned implication]** Geometry-stratified
  episode outcomes and the named diagnostics would support a distribution-tail
  explanation if failures cluster by radius, angle, branch, or interruption
  type. Uniformly distributed failures would weaken a purely geometric
  explanation and increase the importance of general control robustness.

### Quantities that identify the physical mechanism

- **[Reasoned implication]** The scientifically meaningful trajectory is not
  one scalar distance. It includes target radius and angle; \(q,\dot q\) and
  joint-limit margins; end-effector position and target-relative vector;
  action and nominal motor request; Jacobian conditioning through
  \(\sin q_2\); distance and its substep extrema; first in-tolerance step;
  longest uninterrupted held run; interruption count; and final success.
  These quantities span geometry, actuation, motion, convergence, and the
  history-dependent outcome.
- **Decision relevance [Reasoned implication]** Keeping these quantities
  together permits a mechanism claim such as “late reach,” “overshoot,” or
  “limit/contact interaction” without treating a lower reward or minimum
  distance as a sufficient explanation.
- **Assumptions [Unresolved quantity]** The current evaluator records the
  target geometry and several distance/hold summaries, but not every listed
  state, action, acceleration, Jacobian, or internal-substep quantity. Their
  availability therefore depends on a separately authorized diagnostic
  measurement rather than on the existing episode artifact.
- **Source references [Repository fact]** `robot_learning\scenario\evaluation.py:62-121`,
  `robot_learning\scenario\observations.py:14-46`,
  `robot_learning\scenario\environment.py:128-168`,
  `contracts\scenario.md:8-17`.
- **Discriminating evidence [Reasoned implication]** A synchronized trace of
  those quantities would support a physical failure attribution when the
  candidate's state and action trajectory predicts the observed outcome;
  disagreement between the trace and the attribution would keep the cause
  unresolved.

### Training reward is not a physical success signal

- **[Reasoned implication]** The reward makes progress and closeness valuable,
  adds hold-progress and completion terms, and charges action magnitude. It
  can therefore favor a particular approach or braking style, but it cannot
  turn an interrupted hold into success or certify the official 98% objective.
- **Decision relevance [Reasoned implication]** Reward curves or reward totals
  cannot by themselves decide whether the learned controller has solved the
  task. They are informative about the training pressure only when paired
  with success and hold diagnostics.
- **Assumptions [Repository fact]** This follows from the explicit separation
  between `reach_reward` and the environment's `terminated`/`is_success`
  fields; research may alter the reward implementation without changing the
  human success contract.
- **Source references [Repository fact]** `robot_learning\training\reward.py:16-105`,
  `robot_learning\scenario\environment.py:146-168`,
  `contracts\scenario.md:14-17`.
- **Discriminating evidence [Reasoned implication]** A candidate whose reward
  rises while its uninterrupted success rate, hold interruptions, or
  geometry-conditioned outcome does not improve would support the distinction;
  matched improvements in both would weaken the concern that reward is being
  optimized as a proxy.

## Unknowns

### Compiled mass, inertia, contact, and numerical defaults

- **[Unresolved quantity]** The XML specifies link geometry, damping, armature,
  gravity, and timestep but does not specify body masses, inertial tensors,
  geom density, solver/integrator settings, contact friction, or explicit
  upper-arm/forearm collision filtering. The exact compiled \(M(q)\), contact
  behavior, and numerical response are therefore not available from source
  text alone.
- **Decision relevance [Reasoned implication]** These values can change
  acceleration under the nominal \(5u\) motor request, the ability to leave
  the initial singularity before step 401, the usable IK branch, and the
  settling margin. They could change whether the first campaign decision is
  primarily policy development or physical-model characterization.
- **Assumptions [Reasoned implication]** The uncertainty is resolvable from
  the locked MuJoCo compilation and does not imply run-to-run randomness; it
  is an omitted numeric/default specification, not evidence of stochastic
  physics.
- **Source references [Repository fact]** `contracts\robots\two_joint_arm.xml:2,6,9-21`,
  `contracts\robots\two_joint_arm.xml:25-32`,
  `AGENTS.md` (locked runtime versions).
- **Discriminating evidence [Reasoned implication]** A compiled-model
  inspection of body masses, inertias, dof armatures/damping, geom collision
  flags, options, and contact pairs, followed by torque-response traces, would
  resolve or narrow this unknown. A discrepancy between predicted and measured
  acceleration would require revising the nominal dynamic model.

### Finite-time reachability and stabilization envelope

- **[Unresolved quantity]** Ideal kinematics says every official target has a
  solution, but no pre-campaign source fact establishes that every target can
  be reached and held for 100 consecutive control samples within 500 saturated
  torque actions. The distribution of time-to-first-entry, residual velocity,
  and hold interruptions is unknown.
- **Decision relevance [Reasoned implication]** This unknown determines whether
  early work should target approach speed, branch/limit robustness, braking and
  damping, or a broader policy change. It also determines whether an
  apparently strong average can plausibly reach the four-failure official
  allowance.
- **Assumptions [Reasoned implication]** The distinction assumes the official
  target distribution and task semantics are held fixed; changing training
  exposure or reward can change a policy's envelope without changing the
  physical envelope.
- **Source references [Repository fact]** `contracts\scenario.md:8-31`,
  `contracts\task_spec.py:6-11`,
  `robot_learning\scenario\environment.py:122-168`.
- **Discriminating evidence [Reasoned implication]** Repeated evaluation with
  episode diagnostics, stratified by target radius and angle, would resolve
  whether failures are reach-time, minimum-distance, residual-velocity, or
  hold-interruption limited. A candidate-independent failure pattern would
  point toward physics or timing; candidate-dependent changes would point
  toward control.

### Effective learned-runtime information path

- **[Unresolved quantity]** Before training, there is no candidate-specific
  fact about policy architecture, recurrent memory, observation
  normalization, clipping, or action-prediction behavior. The runtime contract
  permits all of these to affect the policy input/output path while preserving
  the same raw physical observation.
- **Decision relevance [Reasoned implication]** A first decision about a
  memoryless versus recurrent controller, or about preprocessing, could change
  whether hidden hold history and numerical scale are treated as limitations
  or simply ignored. It also affects reproducibility of any physical
  interpretation of a saved policy.
- **Assumptions [Repository fact]** The raw scenario observation and physical
  action mapping remain fixed, while candidate runtime serialization binds
  the selected weights, normalizer, and callables to that artifact.
- **Source references [Repository fact]** `robot_learning\scenario\observations.py:11-46`,
  `robot_learning\scenario\policy_io.py:7-16`,
  `contracts\policy_runtime.py:64-81,150-176`.
- **Discriminating evidence [Reasoned implication]** Inspection of a saved
  runtime's normalization statistics and recurrence contract, plus matched
  replays of raw observations and predicted actions, would establish whether
  preprocessing or history materially changes commands. Divergence after
  runtime reset would support a temporal-policy explanation.

### Temporal meaning of “continuously” between control samples

- **[Unresolved quantity]** The visible scenario counts distance only after
  each ten-substep action block, while the human wording says continuously.
  The contract fixes 100 consecutive control steps, but the protected final
  evaluator's treatment of any within-block excursion is not exposed in the
  readable implementation.
- **Decision relevance [Reasoned implication]** If within-block motion is
  ignored, a sampled hold can conceal fast oscillation; if it is checked, the
  same controller has a stricter physical requirement. This can change the
  interpretation of a near-threshold policy and the value of substep
  stabilization diagnostics.
- **Assumptions [Repository fact]** The human contract, not a development
  implementation guess, governs the official result. The visible environment
  is evidence about shared mechanics but cannot by itself certify hidden
  evaluator internals.
- **Source references [Repository fact]** `contracts\scenario.md:10-17`,
  `robot_learning\scenario\environment.py:128-168`,
  `robot_learning\scenario\evaluation.py:62-121`.
- **Discriminating evidence [Reasoned implication]** Recording distance at all
  ten MuJoCo substeps during an otherwise successful sampled hold would show
  whether candidate behavior has hidden excursions. An explicit evaluator
  comparison, if available through the human-owned assessment, would resolve
  the semantic distinction; absent that, the claim must remain bounded to
  control-step continuity.

### Distribution-level success before campaign evidence

- **[Unresolved quantity]** No source definition of the robot or task implies
  a learned policy's episode success probability, including the probability
  of rare branch, angle, radius, and hold failures. The 98% requirement is a
  goal and threshold, not a prior physical result.
- **Decision relevance [Reasoned implication]** This unknown controls whether a
  candidate is merely promising or sufficiently robust for the official
  commitment. It cannot be replaced by kinematic reachability, reward, or a
  small unpaired development panel.
- **Assumptions [Repository fact]** The official percentage is computed from
  one frozen policy over 200 fixed-panel episodes, with success counted as an
  episode-level binary outcome.
- **Source references [Repository fact]** `contracts\scenario.md:14-31`,
  `robot_learning\scenario\evaluation.py:62-121`.
- **Discriminating evidence [Reasoned implication]** Episode-level outcomes on
  the official or task-reference semantics, accompanied by hold and geometry
  diagnostics where permitted, would support or weaken any claim of
  distributional robustness. Development evidence remains distinct from the
  protected final result.

## Decision-relevant synthesis

### 1. Ideal reachability is available, but the reset is singular

- **Decision relevance [Reasoned implication]:** The first campaign decisions
  should treat approach dynamics, branch selection, and joint-limit behavior
  as the likely discriminators rather than assuming unreachable targets.
- **Assumptions [Unresolved quantity]:** This relies on ideal point kinematics
  and on link self-contact not removing a required branch.
- **Source references [Repository fact]:** `contracts\robots\two_joint_arm.xml:12-21`,
  `contracts\robots\two_joint_arm.py:5-7`,
  `robot_learning\scenario\observations.py:29-46`.
- **Discriminating evidence [Reasoned implication]:** IK residuals and
  target-stratified failures, together with initial joint trajectories, would
  distinguish geometric impossibility from failure to leave the
  \(q_2=0\) singular start.

### 2. Direct 50 Hz torque commands must both arrive and settle

- **Decision relevance [Reasoned implication]:** Reaching and holding are one
  coupled control problem: a policy that reaches quickly with residual
  velocity can be worse than a slower policy that enters and remains within
  1 cm for all 100 samples.
- **Assumptions [Repository fact]:** Gravity and target contact are absent,
  the action is held for ten 2 ms substeps, and the visible success counter
  samples after each 20 ms block.
- **Source references [Repository fact]:** `contracts\robots\two_joint_arm.xml:2,13-18,30-32`,
  `contracts\task_spec.py:7-11`,
  `robot_learning\scenario\environment.py:122-168`.
- **Discriminating evidence [Reasoned implication]:** First-entry step,
  entry velocity, action saturation, substep distance, longest uninterrupted
  hold, and interruption count directly distinguish approach, braking, and
  stabilization limits.

### 3. Compiled dynamics are the most consequential physical unknown

- **Decision relevance [Reasoned implication]:** Unstated mass/inertia,
  self-contact, and numerical defaults can change control authority and
  settling enough to alter whether the first work should characterize the
  simulator or develop a policy against it.
- **Assumptions [Unresolved quantity]:** The XML is complete only up to
  deterministic MuJoCo defaults; the effective compiled parameters have not
  yet been inspected or measured.
- **Source references [Repository fact]:** `contracts\robots\two_joint_arm.xml:2,6,9-21`,
  `AGENTS.md` (MuJoCo 3.12.0).
- **Discriminating evidence [Reasoned implication]:** Model introspection and
  controlled torque-response measurements would resolve the nominal dynamic
  model; mismatch between those predictions and trajectories would revise
  the control-authority explanation.

### 4. Raw sensing is rich, but the task counter is hidden

- **Decision relevance [Reasoned implication]:** Target ambiguity is not the
  primary sensing limitation because joint state and target-relative position
  are exposed. The meaningful observability question is whether policy memory
  or a stable physical equilibrium is needed to survive the hidden hold and
  horizon state.
- **Assumptions [Unresolved quantity]:** The conclusion assumes no hidden
  actuator state and leaves candidate-specific normalization, clipping, and
  recurrence unresolved.
- **Source references [Repository fact]:** `robot_learning\scenario\observations.py:11-46`,
  `contracts\policy_runtime.py:150-176`,
  `robot_learning\scenario\environment.py:136-168`.
- **Discriminating evidence [Reasoned implication]:** Matched raw-state
  replays with different hold histories and inspection of the saved runtime
  would show whether policy history or preprocessing changes the action.

### 5. The official requirement is a distribution-tail requirement

- **Decision relevance [Reasoned implication]:** With all angles, radii
  6--20 cm, and only four failures allowed in 200 episodes, aggregate reward
  or average distance is insufficient for the first campaign decision.
- **Assumptions [Repository fact]:** The official panel and episode-level
  success semantics remain those fixed by the human contract, distinct from
  development panels.
- **Source references [Repository fact]:** `contracts\scenario.md:8-31`,
  `robot_learning\scenario\evaluation.py:62-121`.
- **Discriminating evidence [Reasoned implication]:** Geometry-conditioned
  outcomes and complete-hold diagnostics would reveal whether the remaining
  gap is a rare branch/angle failure, a radius-dependent time limit, or a
  general stabilization failure; the principal investigator chooses the
  response to that evidence.
