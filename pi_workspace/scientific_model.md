## Established facts

### Task, distribution, and assessment

- **Repository fact.** The official task samples one fixed target per episode: its
  radius is uniform on 0.06--0.20 m and its polar angle is uniform on
  [-pi, pi]. The target is not moved during an episode. The official target is
  therefore uniform in radius and angle, not uniform in Cartesian area.
  **Source references:** `contracts/scenario.md` (Official task);
  `contracts/task_spec.py` (`TARGET_RADIUS_RANGE`);
  `robot_learning/scenario/environment.py` (`_sample_target_position`).

- **Repository fact.** Success is based on the Euclidean distance between the
  end-effector site and the target position being at most 0.01 m for 2.0 s.
  With the current 0.002 s MuJoCo timestep and `FRAME_SKIP=10`, the environment
  requires 100 consecutive outer control steps. An episode is truncated after
  500 outer steps, so the available interaction time is 10.0 s.
  **Source references:** `contracts/scenario.md` (Success criterion);
  `contracts/task_spec.py` (`SUCCESS_THRESHOLD`, `HOLD_SECONDS`, `FRAME_SKIP`,
  `MAX_EPISODE_STEPS`);
  `robot_learning/scenario/environment.py` (`hold_steps_required`, `step`).

- **Repository fact.** The protected final assessment freezes one policy and
  evaluates 200 episodes; at least 196 successes are required for the official
  98% objective. A development panel is not combined with that result.
  **Source references:** `contracts/scenario.md` (Official final assessment).

### Morphology, coordinates, and kinematics

- **Repository fact.** The robot has a fixed base and exactly two actuated
  revolute degrees of freedom: a shoulder hinge and an elbow hinge, both about
  the world z axis. The shoulder and elbow ranges are each -170 to +170
  degrees. There is no translational joint, wrist joint, or vertical degree of
  freedom.
  **Source references:** `contracts/robots/two_joint_arm.xml` (the `base`,
  `shoulder`, and `elbow` bodies and joints).

- **Repository fact.** The upper-arm link length is 0.12 m and the forearm link
  length is 0.10 m. The arm plane is at z=0.02 m: the upper-arm body is
  translated to that height and the target sampler copies the end-effector z
  coordinate. The base cylinder, link capsules, end-effector site, and target
  sphere are visual/geometric model elements; success uses site and mocap
  positions, not the rendered sizes of the site or sphere.
  **Source references:** `contracts/robots/two_joint_arm.xml` (body positions,
  `fromto` lengths, site, and target geom);
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`, `MAX_REACH`);
  `robot_learning/scenario/environment.py` (`target_z`,
  `_distance_to_target`).

- **Reasoned implication.** With shoulder angle q_s and relative elbow angle
  q_e, the end-effector position is
  `p_E(q) = (0.12*cos(q_s) + 0.10*cos(q_s+q_e),`
  `0.12*sin(q_s) + 0.10*sin(q_s+q_e), 0.02)`. Ignoring joint limits, the
  exact planar workspace is the annulus from
  `|0.12-0.10|=0.02 m` to `0.12+0.10=0.22 m` at z=0.02 m; there is no
  reachable z displacement. **Source references:** the link dimensions and
  body frames in `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py` (`MAX_REACH`).

- **Repository fact.** The target body is mocap-controlled and the task writes
  its position directly. The plane, base geom, and target geom have
  `contype="0"` and `conaffinity="0"`, so those objects do not provide
  physical contact feedback or an external support force to the arm.
  **Source references:** `contracts/robots/two_joint_arm.xml` (plane, base,
  and target geoms; `mocap="true"`);
  `robot_learning/scenario/environment.py` (`data.mocap_pos`).

### Actuation and simulator timing

- **Repository fact.** Each environment action has two components in [-1, 1].
  The current physical action mapping is the identity. The environment clips
  the mapped action, writes it to the two MuJoCo actuator controls, and holds
  that control constant for ten `mj_step` calls. Each motor has `gear="5"` and
  `ctrlrange="-1 1"`, so the nominal joint command is a direct motor torque
  proportional to `5*u` in the model's torque units, with no position-servo
  target supplied by the scenario.
  **Source references:** `contracts/robots/two_joint_arm.xml` (actuators);
  `robot_learning/scenario/policy_io.py` (`physical_action`);
  `robot_learning/scenario/environment.py` (`step`).

- **Repository fact.** The XML sets gravity to zero and the physics timestep to
  0.002 s. Both joints specify viscous damping 0.5 and armature 0.01. No
  actuator state, actuator time constant, gravity load, or explicit external
  disturbance is declared.
  **Source references:** `contracts/robots/two_joint_arm.xml` (`option`,
  `shoulder`, `elbow`).

- **Repository fact.** The XML contains no explicit `<inertial>` elements and
  does not set a geom density, friction, solver, or integrator option. The
  loaded `MjModel` therefore supplies the numerical inertial and other omitted
  simulator parameters through MuJoCo's compilation/default behavior.
  **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`MjModel.from_xml_path`);
  `AGENTS.md` (locked MuJoCo version).

### Reset and closed-loop interaction

- **Repository fact.** On reset, the environment resets MuJoCo data, explicitly
  sets both joint positions and both joint velocities to zero, forwards the
  model, samples the target, and forwards again. The initial arm is therefore
  straight along positive x with `q=(0,0)`, `qdot=(0,0)`, and
  `p_E=(0.22,0,0.02)`. The initial target distance ranges from 0.02 m to
  0.42 m over the official distribution, so the initial state is outside the
  0.01 m success disk even at the closest official target.
  **Source references:** `robot_learning/scenario/environment.py` (`reset`,
  `_sample_target_position`);
  `contracts/robots/two_joint_arm.xml` (body frames);
  `contracts/task_spec.py` (`SUCCESS_THRESHOLD`).

- **Repository fact.** At outer step k, the policy receives an observation,
  emits an action, the action is integrated for ten 2 ms substeps, and only
  then is distance and hold state updated. The next observation is generated
  from the post-integration state. The environment returns reward and
  `info`, including distance and held-step count, but those fields are not
  concatenated into the policy observation.
  **Source references:** `robot_learning/scenario/environment.py` (`step`,
  `_observation`).

### Sensing, derived information, and learning interface

- **Repository fact.** The physical observation has 11 float32 values:
  two joint positions, two joint velocities, the three-dimensional vector
  `p_E-p_target`, and four wrapped joint-angle residuals to the two
  analytic inverse-kinematic branches. There is no declared measurement noise,
  sensor delay, dropout, or quantization.
  **Source references:** `robot_learning/scenario/observations.py`
  (`OBSERVATION_SIZE`, `reach_observation`);
  `robot_learning/scenario/environment.py` (`_observation`).

- **Repository fact.** The four residuals are computed from the target x/y
  position and the fixed link lengths. The open branch uses
  `q_e=+acos(c)` and the folded branch uses `q_e=-acos(c)`, where
  `c=(r^2-L1^2-L2^2)/(2*L1*L2)`; the corresponding shoulder angle is computed
  with `atan2` and every residual is wrapped to [-pi, pi]. The implementation
  clips `c` before `acos`, although every official target radius lies inside
  the unconstrained planar workspace.
  **Source references:** `robot_learning/scenario/observations.py`
  (`shoulder_for_elbow`, `wrap_to_pi`, `reach_observation`).

- **Repository fact.** The current trainer uses a feed-forward Stable-Baselines3
  `MlpPolicy` and normalizes observations with saved `VecNormalize` statistics.
  Normalization is a policy-input transformation, not a change to the physical
  sensor values. The runtime can also carry recurrent state in its general
  interface and resets that state at episode boundaries, but the current
  baseline policy is feed-forward.
  **Source references:** `robot_learning/train.py` (`PPO("MlpPolicy")`,
  `VecNormalize`);
  `robot_learning/training/normalization.py`;
  `contracts/policy_runtime.py` (`PolicyRuntime.reset`, `predict`).

- **Repository fact.** The current training environment samples radius
  0.14--0.20 m, whereas `make_evaluation_env` uses the official 0.06--0.20 m
  range. The reward contains distance progress, closeness, hold progress,
  action cost, and hold-completion terms, but reward is not the official
  success criterion.
  **Source references:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/training/reward.py`.

## Physical consequences

### Reachability, workspace, and alternative configurations

- **Reasoned implication.** For a target at polar coordinates (r, theta), the
  unconstrained inverse-kinematic candidates are
  `q_e=+/- beta`, `beta=acos((r^2-L1^2-L2^2)/(2*L1*L2))`, and
  `q_s=theta-atan2(L2*sin(q_e), L1+L2*cos(q_e))` modulo 2*pi. Over the official
  radius interval, beta is approximately 49.5--150.2 degrees. Directly
  checking the equivalent shoulder-angle representatives against the
  +/-170-degree limits shows that at least one branch is limit-compatible for
  every official target; some radius/angle regions can lose one branch, so
  two algebraic solutions must not be treated as two always-feasible choices.
  **Decision relevance:** The first controller can be designed around branch
  selection or branch-agnostic Cartesian feedback; it need not solve an
  unreachable-target problem under the official distribution. A branch choice
  can still change path length, joint-limit margin, torque demand, and hold
  robustness.
  **Assumptions:** The XML joint ranges are enforced by the compiled MuJoCo
  model, angles are interpreted modulo 2*pi for equivalent geometry, and the
  target remains in the stated z plane.
  **Source references:** `contracts/robots/two_joint_arm.xml` (joint ranges);
  `contracts/robots/two_joint_arm.py` (link lengths);
  `robot_learning/scenario/observations.py` (the two branch construction).
  **Discriminating evidence:** For sampled r/theta pairs, compute both
  candidate configurations, their joint-limit margins, end-effector residuals,
  and the branch actually approached by a policy. A failure concentrated where
  one branch is excluded supports a limit/branch explanation; a failure with a
  feasible high-margin branch weakens it.

- **Reasoned implication.** The target is a point-position task in a planar
  1 cm disk, not an orientation, contact, or force task. The site radius
  (0.008 m) and target sphere radius (0.012 m) do not enlarge the success
  region because the code compares the two position vectors directly.
  **Decision relevance:** A controller should spend authority on position
  convergence and low residual velocity rather than end-effector orientation
  or force regulation. Contact-based exploration cannot supply a missing
  success signal.
  **Assumptions:** The shared scenario environment is the semantics used by
  official assessment and no hidden evaluator adds an orientation or contact
  condition.
  **Source references:** `contracts/scenario.md` (success definition);
  `contracts/robots/two_joint_arm.xml` (site and target geoms);
  `robot_learning/scenario/environment.py` (`_distance_to_target`).
  **Discriminating evidence:** Compare position distance with orientation,
  contact, and force traces; only distance and the 100-step hold should
  predict the recorded task outcome. A systematic outcome dependence on
  orientation or contact would identify an evaluator/implementation
  discrepancy rather than a robot capability.

### Initial singularity and trajectory geometry

- **Reasoned implication.** The planar Jacobian has determinant
  `L1*L2*sin(q_e)`. At reset, q_e=0, so the arm is at the fully extended
  kinematic singularity. More specifically, at q=(0,0) the instantaneous
  end-effector x velocity from either joint rate is zero; shortening the
  0.22 m reach toward every official target requires first creating an elbow
  bend and is locally a second-order position change in that bend. The policy
  therefore begins from a state with poor radial manipulability even though
  the target itself is reachable.
  **Decision relevance:** Initial action design, exploration, and any
  curriculum should account for a departure maneuver rather than treating the
  initial Cartesian error as uniformly controllable. Early overshoot or slow
  motion can be a singular-start effect, not evidence that the target is
  geometrically difficult in its final configuration.
  **Assumptions:** The two-link kinematic equation is the effective site
  geometry, there are no hidden offsets, and the first action is applied from
  the explicitly reset state.
  **Source references:** `contracts/robots/two_joint_arm.xml` (joint and body
  frames); `robot_learning/scenario/environment.py` (`reset`, `mj_forward`);
  `contracts/robots/two_joint_arm.py` (link lengths).
  **Discriminating evidence:** Record q, qdot, end-effector velocity, Jacobian
  determinant, and distance during the first control steps. A transient loss
  of radial authority that disappears after |q_e| grows supports the
  singular-start mechanism; comparable difficulty away from q_e=0 weakens it.

- **Reasoned implication.** Position tolerance is not a fixed tolerance in
  either joint. For a small joint error delta-q near a target,
  `delta-p_E` is approximately `J(q)*delta-q`; the same 1 cm disk can permit
  different joint errors and velocity-induced exit rates on different
  configurations. Manipulability and joint-limit margin therefore couple
  target geometry to both convergence and stabilization.
  **Decision relevance:** Geometry-stratified controller gains, target
  exposure, and diagnostics should use Cartesian error together with q_e,
  `|det(J)|`, qdot, and joint-limit margins; aggregate distance alone can
  hide a configuration-sensitive failure.
  **Assumptions:** The task remains planar and local linearization is used only
  for interpretation near a configuration, not as an exact global model.
  **Source references:** the link geometry in
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py` (q and end-effector error);
  `robot_learning/scenario/environment.py` (distance criterion).
  **Discriminating evidence:** Bin complete episodes by target radius, target
  angle, q_e, manipulability, and joint-limit margin, then compare first
  reach, minimum distance, and hold interruptions. A geometry-aligned pattern
  supports this mechanism; a pattern aligned only with action magnitude or
  random seed points elsewhere.

### Direct torque control and dynamic authority

- **Reasoned implication.** Between outer observations the arm is a
  zero-order-held torque-controlled dynamical system. In the absence of
  contact, its generalized dynamics can be represented schematically as
  `M(q)qddot + h(q,qdot) + 0.5*qdot = 5*u`, with armature 0.01 added to the
  effective joint inertia and gravity absent. Here h contains velocity-dependent
  multibody terms and any active constraint forces. This is not a position
  command: action magnitude affects acceleration, and stopping requires
  deliberately removing or reversing torque while damping dissipates energy.
  **Decision relevance:** A policy or reward that only points toward the
  target can reach it with excessive kinetic energy and fail the hold. Action
  scaling, braking behavior, and controller bandwidth are first-order
  choices, not implementation details.
  **Assumptions:** `gear=5` maps each scalar motor control to the stated
  generalized torque without an additional actuator dynamic, and omitted
  model parameters take their normal MuJoCo meanings.
  **Source references:** `contracts/robots/two_joint_arm.xml` (actuators,
  damping, armature, gravity, timestep);
  `robot_learning/scenario/environment.py` (constant control over ten
  substeps).
  **Discriminating evidence:** At several q configurations, measure q,
  qdot, qddot, applied control, and end-effector response to a bounded
  constant action and to its reversal. Agreement with the torque/damping
  structure supports direct-actuation control; delayed or rate-limited
  response would expose omitted actuator or solver behavior.

- **Reasoned implication.** Once an exact limit-compatible inverse-kinematic
  pose is reached with zero velocity, zero action is a static equilibrium in
  the declared gravity-free, non-contact model. Holding is therefore mainly a
  transient-energy and feedback problem, not a steady torque-to-counterweight
  problem. Conversely, entering the tolerance disk with nonzero qdot can carry
  the site outside the disk before damping removes the motion.
  **Decision relevance:** The controller should be judged on approach velocity
  and settling, not merely on whether it first crosses the threshold. A
  terminal policy may benefit from a quiet equilibrium, while unnecessary
  corrective torque can create oscillations around the disk.
  **Assumptions:** No unmodeled contact, numerical drift, target motion, or
  actuator state adds a persistent load at rest.
  **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`_distance_to_target`,
  hold update).
  **Discriminating evidence:** From an exact IK pose with qdot=0 and zero
  action, trace q and distance for the full hold duration. Drift supports an
  omitted load, contact, or numerical-effect explanation; no drift with
  high-velocity exits supports the transient-stabilization explanation.

### Reach, convergence, and the complete hold

- **Reasoned implication.** Official success is a conjunction of four coupled
  capabilities: (1) select or reach a feasible configuration, (2) traverse
  from the singular reset state without hitting limits or losing control, (3)
  converge to the 1 cm Cartesian disk with sufficiently low residual motion,
  and (4) stabilize there for 100 sampled control intervals. A first entry is
  not success; any outside sample resets the held-step counter to zero.
  **Decision relevance:** Candidate selection and diagnosis must separate
  reach failures (`min_distance` or no first entry) from hold failures
  (`max_held_steps` below 100 or interruptions). Improving approach speed
  without improving the complete hold does not advance the official objective.
  **Assumptions:** The scenario `step` implementation is shared by training
  and official evaluation, and the target remains fixed after reset.
  **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py` (`_held_steps`,
  `_outside_after_hold`, `terminated`);
  `robot_learning/scenario/evaluation.py` (episode diagnostics).
  **Discriminating evidence:** For every episode, retain target r/theta,
  first-reach step, min/final distance, held-step maximum, in-tolerance
  samples, and interruption count. A high first-reach rate with low success
  identifies stabilization/convergence as the limiting capability; failures
  before first reach identify trajectory or reachability causes.

- **Reasoned implication.** The environment checks distance only after each
  ten-substep integration block. Thus "uninterrupted" is operationally a
  sequence of 100 consecutive post-block samples; a trajectory that leaves
  and re-enters the disk between two checks would not reset `_held_steps`.
  The physical substep path remains relevant to dynamics but is not itself
  part of the observed success test.
  **Decision relevance:** A policy can be evaluated either for the official
  sampled criterion or for a stricter physical safety margin; those are
  different claims. Controller bandwidth and a margin below 1 cm should not
  be judged from the outer-step success bit alone.
  **Assumptions:** No protected evaluator replaces this shared interaction
  semantics with a finer hold test.
  **Source references:** `contracts/scenario.md` (duration and control-step
  statement); `contracts/task_spec.py` (`FRAME_SKIP`);
  `robot_learning/scenario/environment.py` (`for _ in range(self.frame_skip)`,
  subsequent distance test).
  **Discriminating evidence:** Log distance at all 2 ms substeps as well as
  at outer steps. Between-sample threshold crossings with successful outer
  holds support the sampling distinction; none observed makes it practically
  inactive without changing the contract.

### Observation, action, and outcome coupling

- **Reasoned implication.** For this fixed model, qpos, qvel, and
  `p_E-p_target` are sufficient to reconstruct the target x/y position because
  p_E is determined by qpos and known geometry. The physical state relevant to
  future motion is therefore close to fully observable: there is no declared
  sensor noise, moving target, or actuator state. The task state is not fully
  observable, however, because the held-step count, outer step count, previous
  distance, and between-sample path are excluded from the observation.
  **Decision relevance:** A memoryless policy can in principle stabilize the
  physical state, but it cannot know how much of the 2 s hold has already
  elapsed from one instantaneous observation alone. A recurrent or otherwise
  history-aware controller is relevant if timed behavior is needed; it is not
  required merely to infer target position.
  **Assumptions:** The current feed-forward baseline is the controller under
  consideration and no external hidden state affects the dynamics.
  **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py` (`_observation`, hold variables);
  `robot_learning/train.py` (`MlpPolicy`);
  `contracts/policy_runtime.py` (runtime state reset).
  **Discriminating evidence:** Compare a memoryless policy's hold
  interruptions with a history-aware policy while keeping physical actions and
  target exposure comparable. If interruptions depend on elapsed hold time
  rather than q/qdot/error, missing task-time information is implicated.

- **Reasoned implication.** The two IK residual pairs expose useful geometric
  goals, but wrapped residuals alias angles modulo 2*pi and do not carry a
  separate feasibility flag for a branch near a joint limit. The direct qpos
  values and the explicit joint ranges are needed to interpret those
  residuals. The target angle also has a representation seam at +/-pi even
  though the physical target direction is continuous there.
  **Decision relevance:** A policy should not treat a small wrapped residual
  as sufficient evidence that the corresponding branch can be followed
  without limit checking. Branch-aware inputs or explicit joint-limit margin
  features may change robustness, especially in angular sectors where one
  branch is excluded.
  **Assumptions:** The policy uses the observation exactly as emitted and does
  not receive `info` or target diagnostics.
  **Source references:** `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml` (joint ranges);
  `robot_learning/scenario/environment.py` (`info` versus observation).
  **Discriminating evidence:** Inspect residuals, qpos, candidate IK qpos, and
  limit margins on targets near the angular seam and near branch exclusion
  sectors. A residual/limit mismatch preceding failures supports this
  observability explanation.

### Failure classes and scientifically meaningful quantities

- **Reasoned implication.** The principal physically distinct failure classes
  are: geometric/limit failure (no feasible branch or a limit encounter),
  singular-start failure (poor radial authority near q_e=0), dynamic failure
  (insufficient torque or excessive damping/inertia response), trajectory
  failure (overshoot or poor braking), convergence failure (never entering
  the 1 cm disk), and stabilization/hold failure (leaving it before 100
  sampled steps). The quantities that distinguish these classes are q, qdot,
  target r/theta, end-effector error and distance, Jacobian/manipulability,
  joint-limit margin, applied u and inferred torque, end-effector speed,
  kinetic energy, first-reach time, maximum consecutive hold, and interruption
  count. These quantities describe the complete behavior; reward total alone
  does not.
  **Decision relevance:** Instrumentation should preserve these physical
  traces before changing a controller, so a measured improvement can be
  attributed to reaching, trajectory shaping, convergence, or stabilization
  rather than to a changed mixture of target geometries.
  **Assumptions:** The observation and simulator state can be recorded without
  changing the official policy/runtime, and the compiled model exposes enough
  information to calculate inertia, Jacobian, and torque.
  **Source references:** `robot_learning/scenario/evaluation.py`
  (`episode_diagnostics`);
  `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/training/reward.py`.
  **Discriminating evidence:** A geometry- and qdot-stratified trace is
  informative if the proposed class predicts the failure field and if
  interventions that change that quantity change the corresponding class
  without merely changing target exposure. Aggregate success without these
  traces cannot discriminate the mechanisms.

- **Reasoned implication.** The current baseline learns on only the outer
  0.14--0.20 m radial band but is assessed on the full 0.06--0.20 m band.
  This is a controlled distribution mismatch in radius, not a change in
  robot physics. Inner targets require larger elbow folds and may have
  different manipulability and branch feasibility, so a baseline success
  estimate can overstate official performance even when all targets are
  exactly reachable.
  **Decision relevance:** The first campaign decision must distinguish a
  learning-exposure problem from a mechanical/control problem; official-range
  evaluation or geometry-stratified evidence is needed before attributing
  failures to actuation.
  **Assumptions:** The current training constructor remains the baseline
  constructor and research changes do not silently alter official evaluation.
  **Source references:** `robot_learning/training/environment.py`
  (`TRAINING_TARGET_RADIUS_RANGE`);
  `robot_learning/scenario/environment.py` (`make_evaluation_env`);
  `contracts/scenario.md`.
  **Discriminating evidence:** Compare success and hold diagnostics in radial
  bins including 0.06--0.14 m versus 0.14--0.20 m while keeping angular
  coverage and policy weights fixed. A sharp inner-band deficit supports
  exposure mismatch; geometry-independent deficits point more toward control
  or dynamics.

## Unknowns

### Effective inertial and actuator response

- **Unresolved quantity.** The source contract does not state the compiled
  moving-link masses, center-of-mass locations, full inertia tensors, or the
  resulting configuration-dependent mass matrix. It also does not provide an
  observed torque-to-acceleration envelope. The action-to-motion authority
  and fastest safe braking time are therefore not numerically established by
  link lengths, gear, damping, and armature alone.
  **Decision relevance:** This can change action scaling, exploration duration,
  braking/settling design, target curriculum, and whether a 20 ms control
  period is adequate for 1 cm stabilization.
  **Assumptions:** MuJoCo's omitted defaults compile consistently with the
  locked runtime and no hidden actuator behavior is introduced by the loaded
  policy runtime.
  **Source references:** `contracts/robots/two_joint_arm.xml` (absence of
  explicit inertial/actuator dynamics and presence of gear/damping/armature);
  `robot_learning/scenario/environment.py` (`MjModel` construction);
  `AGENTS.md` (MuJoCo version).
  **Discriminating evidence:** Inspect compiled body mass/inertia, dof
  armature/damping, actuator moment transmission, and configuration-dependent
  `M(q)`, then compare them with measured step and reversal responses. A
  response envelope that cannot be predicted from those quantities requires
  revising the actuation model.

### Omitted simulator and contact details

- **Unresolved quantity.** XML leaves the MuJoCo integrator, solver settings,
  geom density, friction, contact parameters, and explicit self-collision
  exclusions at defaults. The plane, base, and target cannot contact the arm,
  but the behavior of potential link-link overlap and the numerical response
  near joint limits is not established from the human-authored file alone.
  **Decision relevance:** If folded trajectories produce self-contact or
  constraint impulses, branch selection, action smoothness, and hold
  diagnostics can be dominated by simulator constraints rather than the
  intended two-link free-space dynamics.
  **Assumptions:** The official runtime is the locked MuJoCo installation and
  default contact generation is not replaced elsewhere.
  **Source references:** `contracts/robots/two_joint_arm.xml` (geom contact
  flags, joint ranges, omitted options);
  `AGENTS.md` (locked scientific stack).
  **Discriminating evidence:** Inspect compiled options and contact-pair
  behavior, and record `ncon`, contact forces, constraint forces, and q/qdot
  during both IK branches and near joint limits. Persistent nonzero contacts
  revise the free-space dynamic model; none under official trajectories
  weakens this concern.

### Closed-loop transient envelope

- **Unresolved quantity.** It is not known before measurement how many outer
  steps typical targets require to leave the singularity, reach the tolerance
  disk, brake, and remain inside it. The source defines timing and thresholds
  but does not establish settling time, overshoot, maximum end-effector speed
  at entry, or target-geometry-dependent success probability.
  **Decision relevance:** These quantities determine whether the first useful
  direction should emphasize direct policy learning, low-level action shaping,
  explicit feedback structure, or target-distribution coverage.
  **Assumptions:** The same physical model and action semantics are used during
  measurement and official assessment.
  **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.
  **Discriminating evidence:** A panel with per-step q/qdot, distance,
  end-effector speed, Jacobian determinant, torque, first-reach step, and
  hold interruptions, stratified by r/theta, directly estimates this envelope.
  A short first reach with repeated interruptions supports a stabilization
  bottleneck; long pre-entry duration supports trajectory or control-authority
  limitation.

### Physical path between hold checks

- **Unresolved quantity.** The code's hold counter is known to sample distance
  only after each 20 ms action block, but the actual 2 ms distance trajectory
  under learned policies is unknown. It is consequently unresolved whether
  any successful policy relies on threshold crossings between checks or stays
  inside the disk with a physical margin.
  **Decision relevance:** This can change whether a candidate is scientifically
  interpreted as a robust hold controller or only as a policy that exploits
  sampled semantics, and whether a stricter safety diagnostic is needed before
  selecting a candidate.
  **Assumptions:** The official score remains the implemented sampled score;
  the stricter trace is diagnostic rather than a replacement criterion.
  **Source references:** `robot_learning/scenario/environment.py` (`mj_step`
  loop and post-loop distance test);
  `contracts/scenario.md` (uninterrupted hold requirement).
  **Discriminating evidence:** Reconstruct distance at every physics substep
  for episodes that pass and fail. A successful episode with any substep
  distance above 0.01 m supports a sampled-path distinction; a margin below
  the threshold across all substeps weakens it.

### Observability needed for timed holding

- **Unresolved quantity.** The physical state is nearly state-observable from
  q, qdot, and target-relative position, but it is unknown whether the
  current policy method needs the omitted hold counter or elapsed episode time
  to achieve 100 consecutive checks. The default MlpPolicy has no memory, while
  the general runtime permits stateful policies.
  **Decision relevance:** This can change the choice between a memoryless
  feedback policy, a recurrent policy, or a controller augmented with
  history-derived features; it should not be confused with a need for better
  target sensing.
  **Assumptions:** Candidate runtimes preserve the observation contract and
  policy state is reset exactly once per episode.
  **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/train.py` (`MlpPolicy`);
  `contracts/policy_runtime.py`;
  `robot_learning/scenario/environment.py` (held-step state excluded from
  observation).
  **Discriminating evidence:** Match target panels and compare policies with
  and without history while inspecting interruption time within the hold.
  Improvement only when elapsed history is available supports a task-state
  observability limitation; unchanged physical stabilization supports a
  memoryless solution.

## Decision-relevant synthesis

### Official targets are reachable, but the reset is singular

- **Reasoned implication.** **Decision relevance:** The first campaign direction
  should distinguish the singular departure and trajectory problem from
  endpoint reachability; at least one exact IK branch is available throughout
  the official target annulus, but reset starts at q_e=0 with zero radial
  manipulability. **Assumptions:** The stated two-link geometry and joint
  limits are the compiled model and targets remain at z=0.02 m. **Source
  references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`. **Discriminating evidence:**
  Geometry-stratified q/Jacobian/first-reach traces showing difficulty only
  during the initial bend support this model; failures with a feasible
  high-margin endpoint do not support an unreachable-target explanation.

### Torque authority and settling are not numerically known

- **Unresolved quantity.** **Decision relevance:** The missing compiled
  inertias and measured step response can change action scaling, braking
  strategy, and whether a 20 ms action period can meet the 1 cm hold. **Assumptions:**
  MuJoCo defaults and the nominal `5*u` motor mapping are the only dynamic
  mechanisms. **Source references:**
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`;
  `AGENTS.md`. **Discriminating evidence:** Compiled mass/inertia and
  actuator inspection followed by bounded step/reversal traces will establish
  or revise the usable torque and settling envelope.

### The official hold is sampled, while robustness is a separate physical claim

- **Reasoned implication.** **Decision relevance:** Candidate selection must
  preserve the distinction between 100 successful post-block distance checks
  and a hold that remains within 1 cm at every 2 ms substep; this can change
  the interpretation of apparent stabilization improvements. **Assumptions:**
  The shared environment defines official interaction semantics and no hidden
  finer-grained evaluator is substituted. **Source references:**
  `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`. **Discriminating evidence:**
  Substep distance traces for passing episodes, especially those near the
  threshold, discriminate sampled success from physically marginful holding.

### The observation exposes target geometry but not hold progress

- **Unresolved quantity.** **Decision relevance:** The first architecture
  decision may depend on whether a memoryless policy can stabilize the
  physical state without elapsed-hold information; recurrent state is a
  control choice, not a remedy for missing target position. **Assumptions:**
  The 11-value observation and current feed-forward baseline remain as
  specified, with runtime reset at episode boundaries. **Source references:**
  `robot_learning/scenario/observations.py`;
  `robot_learning/train.py`;
  `contracts/policy_runtime.py`;
  `robot_learning/scenario/environment.py`. **Discriminating evidence:**
  Matched comparisons of memoryless and history-aware policies, using
  interruption timing rather than aggregate reward alone, test whether the
  omitted task state is consequential.

### Training exposure does not match the official radial distribution

- **Repository fact.** **Decision relevance:** A baseline trained on
  0.14--0.20 m is not evidence of competence on the official 0.06--0.20 m
  range; early evaluation should identify inner-radius performance before
  attributing the goal gap to dynamics or policy capacity. **Assumptions:**
  The baseline uses `make_training_env` and official evaluation uses
  `make_evaluation_env` without changing the frozen task boundary. **Source
  references:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`. **Discriminating evidence:** Radial-bin success,
  first-reach, and hold-interruption measurements on a common panel show
  whether the gap is concentrated below 0.14 m or persists across the full
  annulus.
