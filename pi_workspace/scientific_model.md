# Scientific model of the two-joint reach-and-hold system

This model is a pre-campaign account of the embodied system. It uses the
human-owned contracts and scenario implementation only; it does not treat
training runs, evaluation panels, or campaign history as evidence.

## Established facts

### Robot morphology and kinematics

- **[Repository fact]** The robot is a fixed-base planar serial arm with two
  revolute degrees of freedom. The shoulder and elbow axes are both the world
  \(z\) axis, the upper-arm length is \(L_1=0.12\) m, and the forearm length
  is \(L_2=0.10\) m. The end-effector site is at the forearm tip. Source:
  `contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`, `forearm`,
  `shoulder`, `elbow`, and `end_effector`); `contracts/robots/two_joint_arm.py`
  (`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`).

- **[Repository fact]** With shoulder angle \(q_1\) and relative elbow angle
  \(q_2\), the end-effector position is
  \[
  p(q)=
  \begin{bmatrix}
  L_1\cos q_1+L_2\cos(q_1+q_2)\\
  L_1\sin q_1+L_2\sin(q_1+q_2)\\
  0.02
  \end{bmatrix}\ {\rm m}.
  \]
  The \(0.02\) m height follows from the upper-arm body offset; the joints and
  site have no out-of-plane degree of freedom. Source:
  `contracts/robots/two_joint_arm.xml`; the forward-kinematic construction in
  `robot_learning/scenario/environment.py` and
  `robot_learning/scenario/observations.py`.

- **[Repository fact]** Each joint range is \([-170^\circ,170^\circ]\).
  The radial envelope implied by the link lengths and the elbow range is
  approximately \(2.8\)--\(22\) cm before accounting for the shoulder-angle
  bound. Source: `contracts/robots/two_joint_arm.xml` (`range="-170 170"` and
  link geometry); this radial calculation is a direct consequence of the
  listed lengths and joint bounds.

### Actuation and simulated dynamics

- **[Repository fact]** The action has two components, is clipped to
  \([-1,1]\), and is passed unchanged by the current policy I/O layer. Each
  component drives a MuJoCo `motor` attached directly to its corresponding
  hinge with `gear="5"`. Sources:
  `robot_learning/scenario/environment.py` (`np.clip`, `data.ctrl`);
  `robot_learning/scenario/policy_io.py` (`physical_action`);
  `contracts/robots/two_joint_arm.xml` (`motor`, `ctrlrange`, `gear`).

- **[Reasoned implication]** Under the locked MuJoCo direct-motor semantics,
  the nominal generalized actuator torque is \(5u_i\) in the joint coordinate
  before other dynamics and constraints act. This is a simulator-semantic
  consequence of the declared gear, not a measured acceleration or guarantee
  of end-effector authority. Sources: `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md` (locked MuJoCo version).

- **[Repository fact]** MuJoCo integrates at \(0.002\) s per physics step.
  Each policy action is held while ten physics steps run, so the control
  interval is \(0.020\) s and the controller acts at 50 Hz. Source:
  `contracts/robots/two_joint_arm.xml` (`timestep="0.002"`);
  `contracts/task_spec.py` (`FRAME_SKIP=10`);
  `robot_learning/scenario/environment.py` (`for _ in range(self.frame_skip)`).

- **[Repository fact]** Gravity is explicitly zero. Each hinge declares
  damping \(0.5\) and armature \(0.01\); no explicit gravity compensation,
  position servo, actuator dynamics, or command noise is declared. The plane
  and target geoms have collision disabled. Source:
  `contracts/robots/two_joint_arm.xml` (`option`, `joint`, and geom contact
  attributes).

- **[Repository fact]** Reset sets both joint positions and velocities to
  zero, runs forward dynamics, then samples a stationary mocap target in the
  same \(z=0.02\) plane. Source:
  `robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`).

### Task geometry and outcome semantics

- **[Repository fact]** At each episode, radius is sampled uniformly from
  \(0.06\)--\(0.20\) m and angle uniformly from \([-\pi,\pi]\). The target
  therefore has a uniform radial, not uniform-area, distribution over the
  specified annulus and full angular range. Source:
  `contracts/scenario.md`; `contracts/task_spec.py`
  (`TARGET_RADIUS_RANGE`); `TwoJointArmReachEnv._sample_target_position`.

- **[Repository fact]** The task is distance regulation to a fixed point, not
  grasping or contact manipulation. Success is evaluated from the Euclidean
  three-dimensional distance between the end-effector site and target mocap
  position. The tolerance is \(0.01\) m. Source:
  `contracts/scenario.md`; `robot_learning/scenario/environment.py`
  (`_distance_to_target`, `SUCCESS_THRESHOLD`).

- **[Repository fact]** The distance must be within tolerance at 100 consecutive
  control steps, equivalent to 2 s at the current 20 ms control interval.
  Leaving tolerance resets the held-step counter to zero. The environment
  checks distance after each ten-step integration block, not after every
  internal physics step. Source:
  `contracts/task_spec.py` (`HOLD_SECONDS`, `FRAME_SKIP`);
  `robot_learning/scenario/environment.py` (`_held_steps`, `step`).

- **[Repository fact]** An episode has at most 500 control steps, or 10 s, and
  the official final assessment uses one frozen policy on 200 fixed-panel
  episodes; at least 196 must succeed. Source: `contracts/scenario.md`
  (`MAX_EPISODE_STEPS`, official final assessment).

### Sensing and policy interface

- **[Repository fact]** The observation has 11 entries: two joint positions,
  two joint velocities, the three-dimensional end-effector-minus-target
  vector, and four wrapped angle errors to the open and folded inverse-
  kinematics solutions. Source:
  `robot_learning/scenario/observations.py` (`reach_observation`,
  `OBSERVATION_SIZE=11`).

- **[Repository fact]** The open and folded inverse-kinematics angles are
  computed analytically from the target \(x,y\), link lengths, and the two
  signs of \(\arccos\). The implementation clips the cosine argument before
  \(\arccos\), and wraps each angle error to \([-\pi,\pi)\). These are
  model-derived features, not noisy physical sensors. Source:
  `robot_learning/scenario/observations.py`.

- **[Repository fact]** No target velocity, actuator torque, contact force,
  acceleration, or intermediate substep state is included in the policy
  observation. The target is stationary and the arm state is directly
  represented by \(q,\dot q\) plus relative target geometry. Source:
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.

## Physical consequences

### Reachability and inverse-kinematic branch choice

- **[Reasoned implication]** Every official radius is inside the two-link
  radial envelope, and the official annulus stays away from the exact
  straight and fully folded singular configurations. For a target radius
  \(r\), the inverse-kinematic elbow angle satisfies
  \[
  \cos q_2=(r^2-L_1^2-L_2^2)/(2L_1L_2).
  \]
  Across 6--20 cm, the open-branch magnitude is approximately
  \(150^\circ\)--\(49^\circ\), so the end-effector has local two-dimensional
  Cartesian authority on the reachable branch. This makes failure more
  plausibly a trajectory, timing, sensing, or stabilization problem than a
  fundamental inability to reach an official target.
- **Decision relevance:** This can change whether initial work emphasizes
  reachability/IK coverage or closed-loop settling, and whether branch-aware
  diagnostics are needed.
- **Assumptions:** The analytic planar geometry matches MuJoCo site kinematics,
  joint limits are enforced as declared, and no unmodeled self-collision
  removes a branch.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Compute the two candidate joint configurations
  and limit margins for sampled targets, then compare measured end-effector
  error and success by target radius, angle, and selected IK branch. A failed
  branch with adequate limit margin weakens a pure reachability explanation;
  failures concentrated at limits or folded poses strengthen it.

### Reach, convergence, and uninterrupted holding are coupled

- **[Reasoned implication]** Entering the 1 cm ball is only an intermediate
  state. The policy must first move from \(q=0,\dot q=0\), reduce Cartesian
  error, remove joint velocity, and then maintain a bounded orbit inside the
  tolerance for 2 s. Overshoot or residual oscillation can repeatedly reset
  the hold even when the minimum distance is small. A controller optimized only
  for first entry can therefore have a materially different success rate from
  one optimized for complete episodes.
- **Decision relevance:** This determines whether candidate selection should
  prioritize binary success and uninterrupted hold diagnostics rather than
  minimum distance or first-reach time alone.
- **Assumptions:** The success counter's sampled semantics are the authoritative
  task definition, and policy actions can be changed at each 20 ms boundary.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py` (`_held_steps`, `terminated`);
  `robot_learning/scenario/evaluation.py` (hold diagnostics).
- **Discriminating evidence:** Record first-entry step, minimum and final
  distance, consecutive held steps, interruptions, joint velocity, and
  action magnitude. A high first-entry rate with low 100-step completion
  supports a stabilization/convergence bottleneck; low first-entry rate
  supports reaching or trajectory-generation failure.

### Zero gravity changes the stabilization problem

- **[Reasoned implication]** There is no gravitational torque to cancel at a
  stationary target. At an exact static configuration, zero command is
  compatible with equilibrium, while damping dissipates motion and motor
  commands can shape the transient. The principal dynamic challenge is thus
  inertial stopping and correction of model/state error, not maintaining a
  posture against gravity. Coupled link inertia still makes a shoulder command
  affect the distal point and can produce overshoot.
- **Decision relevance:** This can change the value of posture-holding
  strategies, action regularization, and tests that separate transient
  control from static torque demand.
- **Assumptions:** No unobserved default force, friction, or contact load is
  materially present; the target remains fixed; effective actuator torque
  follows the declared direct-motor model.
- **Source references:** `contracts/robots/two_joint_arm.xml` (`gravity="0 0
  0"`, damping, armature, motors); `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Measure free decay from nonzero joint velocity
  and acceleration under bounded commands at several configurations. Decay
  consistent with damping and configuration-dependent inertia supports this
  mechanism; persistent bias or unexplained load indicates omitted defaults,
  contacts, or implementation effects.

### Sampled control creates a hold-margin requirement

- **[Reasoned implication]** The policy can react only every 20 ms, while the
  physical state evolves through ten unobserved integrator steps. The official
  counter certifies the distance only at block boundaries. A trajectory can
  leave and re-enter the tolerance between observations without resetting the
  counter, while a boundary crossing resets the entire accumulated hold.
  Consequently, successful behavior requires a margin inside the 1 cm ball
  large enough to absorb intersample motion, not merely a boundary-grazing
  equilibrium.
- **Decision relevance:** This can change whether the first campaign measures
  substep safety margins and whether a policy should target the center of the
  tolerance region.
- **Assumptions:** MuJoCo state evolves continuously enough between integration
  samples for intersample excursions to matter; the official environment
  semantics remain unchanged.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Log distance at all ten substeps and compare it
  with the evaluated boundary distance. If successful episodes frequently
  exceed 1 cm only between checks, the task metric is less physically
  conservative than continuous holding; if not, boundary diagnostics remain
  sufficient.

### The observation is close to a Markov state, but the policy must use it
as a structured state

- **[Reasoned implication]** Because \(q,\dot q\), the relative target vector,
  and the fixed model are available, the target position can in principle be
  reconstructed from forward kinematics and the relative vector. The target
  has no hidden motion, and direct motor actuation has no declared internal
  state. Thus the observation is sufficient in principle for deterministic
  state feedback, although the four IK residuals intentionally expose two
  alternative geometric solutions and do not themselves select one.
- **Decision relevance:** This can change whether early work investigates
  recurrent memory or instead focuses on normalization, feature use, and
  branch-conditioned feedback.
- **Assumptions:** The learned policy can represent the required nonlinear
  mapping, numerical observations are exact enough, and no relevant hidden
  actuator or contact state exists.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence:** Hold \(q,\dot q\) fixed while varying target
  geometry and test whether the observation uniquely predicts the next-state
  response under the same action. Compare feed-forward and recurrent policies
  only if the same observation still leaves a measured history dependence.

### The official distribution is broader than the baseline training range

- **[Reasoned implication]** The official task samples 6--20 cm, while the
  current training environment samples 14--20 cm. A baseline policy can
  appear competent on its exposure while lacking coverage of the shorter-radius
  folded configurations, whose IK geometry and transient behavior differ.
  This is a distribution-coverage issue, not evidence that the inner targets
  are unreachable.
- **Decision relevance:** This can change the initial choice between improving
  training coverage and changing the controller or network.
- **Assumptions:** The current training environment is the recipe used for
  the candidate under consideration and evaluation remains the official
  distribution.
- **Source references:** `robot_learning/training/environment.py`
  (`TRAINING_TARGET_RADIUS_RANGE`); `contracts/task_spec.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Stratify development outcomes by target radius
  and angle, with the same diagnostics used for the official semantics. A
  sharp degradation below 14 cm supports a coverage explanation; uniform
  degradation points toward control, dynamics, or implementation limits.

### Physically meaningful trajectory quantities

- **[Reasoned implication]** The most informative physical variables are
  target radius and angle; \(q,\dot q\); end-effector error and speed; the
  Jacobian and its conditioning; joint-limit margin; action and estimated
  torque; first-entry time; minimum, final, and intersample distance; longest
  uninterrupted in-tolerance run; and the number and timing of hold exits.
  These quantities separate geometric feasibility, trajectory generation,
  convergence, and stabilization rather than collapsing them into reward.
- **Decision relevance:** They determine whether a candidate's failure is
  actionable through task coverage, control shaping, observation changes, or
  dynamic modeling.
- **Assumptions:** The relevant quantities can be logged without changing the
  official policy/environment semantics, and estimated torque is interpreted
  with the simulator's actual inertial parameters.
- **Source references:** `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence:** Jointly analyze these quantities per episode and
  across radius, angle, and IK branch. A metric that changes with a failure
  class while aggregate success does not is evidence that the class is
  scientifically useful; a metric uncorrelated with completion should not
  drive a physical interpretation.

## Unknowns

### Effective mass, inertia, and default dynamics

- **[Unresolved quantity]** The XML declares link shapes and sizes but does
  not explicitly declare body mass, density, diagonal inertia, joint
  friction, or solver/contact parameters. MuJoCo may fill some quantities from
  defaults and geom-derived inertial calculations, but their effective
  generalized inertia and configuration dependence are not established by the
  human-owned files alone.
- **Decision relevance:** These quantities could change the expected value of
  model-based control, action scaling, damping changes, or training recipes
  that assume a particular acceleration response.
- **Assumptions:** The omitted defaults materially affect the 1 cm/20 ms
  control problem; if they are negligible, this unknown can be deprioritized.
- **Source references:** `contracts/robots/two_joint_arm.xml` (absence of
  explicit mass/inertia/default blocks); `AGENTS.md` (locked MuJoCo version).
- **Discriminating evidence:** Inspect the instantiated model's body and joint
  inertial quantities and measure \(q̈\) under known commands at multiple
  configurations. Agreement with the declared damping/armature model narrows
  the uncertainty; configuration-dependent responses not explained by it
  require revising the dynamic model.

### Actual actuator and joint-limit authority

- **[Unresolved quantity]** The command range and gear are known, but the
  realized acceleration, saturation near limits, and any impulse or constraint
  behavior at the \(\pm170^\circ\) ranges are not quantified. It is also not
  established from the contract whether link self-collision can materially
  engage in folded configurations.
- **Decision relevance:** This could change the choice of action parameterization,
  safety margins, branch selection, and whether limit-aware control is needed.
- **Assumptions:** Official trajectories approach limits or folded poses closely
  enough that constraints or self-contact affect success.
- **Source references:** `contracts/robots/two_joint_arm.xml` (`range`,
  geom contact defaults, motors); `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Apply bounded commands near each joint limit
  and along both IK branches while logging joint position, velocity, action,
  and site error. Distinct acceleration clipping, impulses, or contact forces
  would support a constraint/self-collision mechanism; smooth responses with
  margin would weaken it.

### Continuous physical hold versus sampled benchmark hold

- **[Unresolved quantity]** The benchmark's exact sampled semantics are known,
  but the maximum distance and velocity between control-boundary checks during
  successful holds are unknown. Therefore it is unresolved how much physical
  robustness a policy's benchmark success represents.
- **Decision relevance:** This could change whether campaign diagnostics should
  optimize benchmark success alone or also require an intersample safety margin.
- **Assumptions:** The research question values physical interpretation of the
  simulated hold in addition to the immutable benchmark outcome.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`;
  `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence:** Compare boundary-sampled distance with
  ten-substep distance for every hold interval. A large discrepancy revises the
  interpretation of “complete uninterrupted hold” as a simulator-level
  sampled criterion; a small discrepancy supports treating it as a robust
  continuous hold proxy.

### Policy-relevant observability and numerical conditioning

- **[Unresolved quantity]** The observation is physically sufficient in
  principle, but it is unknown whether the current learned policy can use
  raw angles, velocities, relative Cartesian error, and wrapped IK residuals
  with adequate numerical conditioning. The training path normalizes
  observations, while the scenario observation function itself does not.
- **Decision relevance:** This could change whether early work modifies feature
  scaling, policy architecture, or recurrence rather than the physical
  controller.
- **Assumptions:** Learning representation error, not physical unobservability,
  is a limiting factor for the candidate.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/train.py`;
  `robot_learning/training/normalization.py`;
  `contracts/policy_runtime.py`.
- **Discriminating evidence:** Examine feature ranges and policy action
  sensitivity over matched target states, then compare failures under
  controlled feature scaling while preserving the physical environment.
  Improved branch- and radius-uniform control without new physical inputs
  supports a conditioning explanation; persistent state-dependent failures
  suggest dynamics or geometry instead.

### Failure-class prevalence under the official distribution

- **[Unresolved quantity]** Before campaign evidence exists, the relative
  frequencies of reach failure, overshoot, slow convergence, boundary
  interruption, limit interaction, and branch-dependent failure are unknown.
  The source code provides diagnostic fields but no measured prevalence.
- **Decision relevance:** This determines which causal bottleneck is worth
  addressing first and prevents selecting a training change from aggregate
  success alone.
- **Assumptions:** The available per-episode diagnostics are faithful and
  sufficiently fine to distinguish the classes.
- **Source references:** `robot_learning/scenario/evaluation.py`
  (`episode_diagnostics`); `contracts/scenario.md`.
- **Discriminating evidence:** Evaluate a fixed candidate on non-overlapping
  development panels and inspect failure classes by radius, angle, branch,
  first-reach step, and hold interruption. The class with reproducible
  concentration and a physically coherent signature should update the model;
  mixed or unstable classes keep the cause unresolved.

## Decision-relevant synthesis

### Dynamic authority is not fully specified

- **Decision relevance:** Unknown effective inertia, defaults, and constraint
  response could change whether the first campaign decision should target
  control design, action scaling, or learning coverage.
- **Assumptions:** Omitted MuJoCo inertial/default quantities materially affect
  acceleration and the 1 cm hold; if not, this is a lower-priority uncertainty.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Instantiate/introspect the model and measure
  multi-configuration acceleration and free decay under known bounded commands.

### Hold completion is a stabilization problem, not just reach

- **Decision relevance:** The policy must achieve 100 uninterrupted checked
  steps, so first-entry or minimum-distance performance is insufficient for
  candidate selection.
- **Assumptions:** Boundary checks and counter reset are the authoritative
  benchmark semantics; residual velocity and intersample motion can cause
  exits.
- **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Compare first reach, longest hold, hold exits,
  velocity, action, final distance, and substep distance per episode.

### Official coverage includes a geometry regime absent from baseline training

- **Decision relevance:** A baseline trained on 14--20 cm may not cover the
  6--14 cm folded-arm regime required for the official 98% objective; this is
  an immediate alternative to changing the controller.
- **Assumptions:** The current training range remains the candidate's exposure,
  and radius/angle are the dominant task covariates.
- **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`; `contracts/scenario.md`.
- **Discriminating evidence:** Stratified development measurements by radius,
  angle, and IK branch, with enough episodes to distinguish a systematic
  inner-radius deficit from general instability.

### Branch and limit margins should be treated as causal geometry

- **Decision relevance:** Multiple inverse-kinematic solutions allow different
  joint-limit margins, Jacobian conditioning, and transient behavior; selecting
  or exposing a branch can change robustness without changing target success
  geometry.
- **Assumptions:** Both analytic branches are dynamically available and are not
  removed by self-collision or hidden constraints.
- **Source references:** `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`.
- **Discriminating evidence:** Reconstruct branch solutions, log branch
  selection and joint-limit/Jacobian margins, and compare hold completion by
  branch across the official radius-angle domain.

### The observation likely contains the needed state, but representation may
be the bottleneck

- **Decision relevance:** Since target-relative geometry and \(q,\dot q\) are
  present, adding memory or new sensors should not be the default first
  explanation; feature conditioning and policy use are more directly
  implicated.
- **Assumptions:** No hidden actuator/contact state materially affects the
  next step and the fixed-target system is deterministic as specified.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.
- **Discriminating evidence:** Test whether matched observations predict the
  same next-state response and inspect action sensitivity to each feature.
  History dependence supports recurrence or an unmodeled state; poor
  feature-conditioned action consistency supports representation/normalization
  work.
