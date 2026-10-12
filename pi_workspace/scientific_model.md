# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. It uses **repository fact** for a
human-owned or implementation-defined statement, **reasoned implication** for a
consequence derived from those facts, and **unresolved quantity** for something
that cannot be established without measuring the compiled simulation or a
policy's behavior. No campaign evidence is used here.

## Established facts

### Robot morphology and coordinates

- **Repository fact.** The robot is a serial planar arm with two scalar hinge
  joints: `shoulder` and `elbow`, both rotating about the world/local z axis.
  The upper arm is 0.12 m and the forearm is 0.10 m long. The joints and
  end-effector site lie at z = 0.02 m; the base is fixed at the world origin.
  Source: `contracts/robots/two_joint_arm.xml`,
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`).
- **Repository fact.** Each joint has a range of -170 to +170 degrees. The
  model has two actuated degrees of freedom and no independent wrist or
  end-effector orientation degree of freedom. Source:
  `contracts/robots/two_joint_arm.xml`.
- **Repository fact.** At reset, both joint positions and velocities are set
  to zero and MuJoCo is forwarded before target sampling. Thus the arm starts
  straight along +x, with its end effector at approximately
  `(0.22, 0, 0.02)` m. Source:
  `robot_learning/scenario/environment.py` (`reset`),
  `contracts/robots/two_joint_arm.xml`.

### Simulator, timing, and actuation

- **Repository fact.** MuJoCo uses zero gravity and a physics timestep of
  0.002 s. The environment holds each action for `FRAME_SKIP = 10` physics
  steps, so the policy control interval is 0.020 s (50 Hz); each action spans
  ten 2 ms physics steps.
  Source: `contracts/robots/two_joint_arm.xml` (`option`),
  `contracts/task_spec.py` (`FRAME_SKIP`), and
  `robot_learning/scenario/environment.py` (`step`).
- **Repository fact.** Each action has two components, is clipped to [-1, 1],
  passed unchanged by `physical_action`, written to `data.ctrl`, and applied
  through a MuJoCo motor with `gear="5"` and control range [-1, 1]. This is
  direct motor actuation, not a declared position or velocity servo. Source:
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/policy_io.py`,
  `contracts/robots/two_joint_arm.xml`.
- **Repository fact.** Both joints declare damping 0.5 and armature 0.01.
  Gravity, external task contacts, and target contacts are not used by the
  task: the plane and target geometry have disabled contact masks, and success
  is computed from point distance. Source:
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`.
- **Repository fact.** The visible task environment checks distance only after
  the ten internal physics steps. It increments the hold counter when distance
  is at most 0.01 m and resets that counter on a checked sample outside the
  band. `HOLD_SECONDS = 2.0` therefore gives 100 consecutive control steps.
  Source: `contracts/task_spec.py`,
  `robot_learning/scenario/environment.py`.

### Task geometry and assessment

- **Repository fact.** A target is sampled at a radius of 0.06--0.20 m from
  the base over the full angular range, in the arm's z plane. The visible
  sampler draws angle uniformly on [-pi, pi] and radius uniformly over that
  interval, independently. Source: `contracts/scenario.md`,
  `contracts/task_spec.py`, `robot_learning/scenario/environment.py`
  (`_sample_target_position`).
- **Repository fact.** The target is a non-contact mocap sphere, but the
  geometric success test is the 3-D Euclidean distance between its mocap
  position and the end-effector site. The tolerance is 1 cm. Source:
  `contracts/robots/two_joint_arm.xml`,
  `robot_learning/scenario/environment.py`,
  `contracts/task_spec.py`.
- **Repository fact.** An episode succeeds only after the uninterrupted hold;
  it may last at most 500 control steps. The official assessment uses one
  frozen policy on 200 episodes and requires at least 196 successes (98%).
  Source: `contracts/scenario.md`.
- **Repository fact.** The visible baseline training distribution uses radii
  0.14--0.20 m, while evaluation uses the official 0.06--0.20 m range. Source:
  `robot_learning/training/environment.py`,
  `robot_learning/scenario/environment.py`,
  `contracts/task_spec.py`.

### Observation and policy interface

- **Repository fact.** The default observation has 11 float32 values:
  two joint positions, two joint velocities, the three-dimensional
  end-effector-to-target vector, and four wrapped angular errors to the
  open-elbow and folded-elbow inverse-kinematic solutions. Source:
  `robot_learning/scenario/observations.py`.
- **Repository fact.** The observation is computed from exact simulator
  `qpos`, `qvel`, site position, mocap position, and link-length constants.
  There is no declared sensor noise, filtering, latency, torque sensing,
  acceleration sensing, contact sensing, hold-counter input, or explicit
  clock input. Source: `robot_learning/scenario/observations.py`,
  `robot_learning/scenario/policy_io.py`.
- **Repository fact.** The runtime can preserve recurrent policy state and
  resets it at episode boundaries, but the physical action mapping itself is
  identity. Source: `contracts/policy_runtime.py`,
  `robot_learning/scenario/policy_io.py`.

## Physical consequences

### Kinematics and workspace

- **Reasoned implication.** With shoulder angle \(q_1\) and elbow angle \(q_2\),
  the site position in the task plane is
  \(p(q)=(L_1\cos q_1+L_2\cos(q_1+q_2),
  L_1\sin q_1+L_2\sin(q_1+q_2),0.02)\). Without joint limits its radial
  workspace is the annulus from \(|L_1-L_2|=0.02\) m to
  \(L_1+L_2=0.22\) m. The official target radii lie outside the inner hole and
  below maximum extension, so point reachability is geometrically plausible;
  the exact range-limited subset still depends on the two joint limits.
- **Reasoned implication.** For a reachable non-singular target, inverse
  kinematics generally supplies two discrete configurations:
  \(q_2=\pm\arccos((r^2-L_1^2-L_2^2)/(2L_1L_2))\), with the corresponding
  shoulder angle. These are the elbow-open and elbow-folded branches exposed
  in the observation. A policy can therefore succeed through distinct joint
  postures and approach trajectories; endpoint distance alone does not select
  one.
- **Decision relevance.** The branch choice can change joint-limit margin,
  Jacobian conditioning, required torque, and settling behavior, so it can
  change whether the first policy should learn joint-space or endpoint-space
  regulation.
- **Assumptions.** This follows from the planar two-link geometry, a rigid
  fixed base, and the site being at the stated link endpoint; it does not
  assume a preferred elbow branch or infer exact compiled inertial values.
- **Source references.** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence.** Compute the compiled model's forward kinematics
  and range-constrained IK over the official radius-angle domain, then record
  branch feasibility, joint-limit margin, Jacobian singular values, and
  endpoint error for each solution.

### Reaching, convergence, and stabilization are one coupled control problem

- **Reasoned implication.** Reaching is not sufficient: the controller must
  first reduce endpoint error, then dissipate residual joint and endpoint
  velocity, and finally maintain the endpoint inside a 1 cm ball for 2 s.
  The same motor command that reduces position error can create overshoot;
  damping helps remove energy but also reduces acceleration authority.
- **Reasoned implication.** Because the target can be sampled near either
  0.06 m or 0.20 m and at any angle, the required joint excursion, branch
  margin, and local Jacobian mapping vary by episode. Near a kinematic
  configuration with a poorly conditioned Jacobian, small endpoint corrections
  may require larger or coordinated joint motion.
- **Decision relevance.** A high first-reach rate can coexist with poor episode
  success if velocity, oscillation, or action saturation causes hold
  interruptions. Development measurements should therefore separate first
  entry, maximum uninterrupted dwell, and final success rather than treating
  reward or minimum distance as the task outcome.
- **Assumptions.** The implication assumes no unmodeled contacts or target
  compliance contribute to stabilization; the visible task makes success a
  kinematic distance condition.
- **Source references.** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence.** For complete trajectories, compare endpoint
  error and velocity, joint velocity, action saturation, overshoot, settling
  time, and every hold interruption against the 100-step criterion, stratified
  by target radius, angle, and IK branch.

### Actuation, timing, and control authority

- **Reasoned implication.** The action is a normalized torque-like motor
  command held open-loop between policy decisions. The motor transmission
  gives a nominal generalized-force scale of 5 per unit control before the
  coupled dynamics and saturation are considered; there is no position servo
  that automatically converges to an angular setpoint.
- **Reasoned implication.** At 50 Hz the policy cannot correct continuously:
  each command commits the system to ten 2 ms integrations. A policy that
  changes sign to brake does so only at the next control boundary. The
  1 cm tolerance can therefore be crossed between checks, while the visible
  success counter observes only post-frame-skip samples.
- **Decision relevance.** If the reachable motion is fast relative to 20 ms,
  action magnitude, rate of change, and braking strategy may dominate success;
  if it is slow, the 500-step horizon may constrain long excursions. This
  determines whether early work should focus on control bandwidth, damping,
  or geometric targeting.
- **Assumptions.** The nominal force scale treats MuJoCo's motor transmission
  convention as applying the declared gear directly; effective acceleration
  additionally depends on compiled mass matrix, armature, velocity damping,
  and numerical integration.
- **Source references.** `contracts/robots/two_joint_arm.xml`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/policy_io.py`.
- **Discriminating evidence.** Apply controlled impulses and step responses at
  representative configurations; identify torque-to-acceleration gain,
  rise/settling time, saturation, action-to-motion delay, and whether
  between-check excursions are material.

### Initial state and episode geometry

- **Reasoned implication.** Every episode begins from the same straight,
  stationary arm while the target changes. The start is at maximum nominal
  extension, so the task is not a generic random-state stabilization problem:
  it is a target-conditioned maneuver followed by regulation from a common
  state.
- **Reasoned implication.** A target at radius near 0.20 m and angle near zero
  is initially close to the starting endpoint, whereas targets at other angles
  require substantial coordinated motion. The shortest path in endpoint space
  need not be the lowest-cost or fastest path in joint space.
- **Decision relevance.** Start-state specialization may make a policy look
  capable on the official distribution while leaving recovery from transient
  errors untested. It also makes target-angle and target-radius stratification
  important for locating the 2% failure budget.
- **Assumptions.** The reset sequence is executed exactly as shown and the
  target is sampled after the zero configuration is forwarded; no hidden
  reset randomization is included.
- **Source references.** `robot_learning/scenario/environment.py` (`reset`,
  `_sample_target_position`);
  `contracts/robots/two_joint_arm.xml`;
  `contracts/scenario.md`.
- **Discriminating evidence.** Record initial and target-relative states and
  group first-reach and hold outcomes by angular displacement from the
  initial endpoint and by target radius.

### Observation-to-action observability

- **Reasoned implication.** For the declared planar task, the observation
  contains enough exact information to reconstruct the relevant target
  position: the policy receives \(q\), the site-to-target vector, and known
  link lengths; forward kinematics also reconstructs the site. The four IK
  errors explicitly expose both posture alternatives. This is substantially
  more informative than a camera-only or endpoint-only sensor.
- **Reasoned implication.** The observation omits the hold counter and an
  explicit action history. A feed-forward policy cannot directly know how
  many consecutive checks it has survived; velocity and recent observations
  provide indirect motion information, while a recurrent policy can retain
  episode history. It also cannot observe the simulator's unexposed mass,
  damping torque, or actuator saturation state directly.
- **Decision relevance.** If deterministic full-state observation is sufficient,
  failures are more likely control/dynamics or policy-capacity failures than
  target localization failures. If hold progress or hidden dynamics matter,
  recurrence or auxiliary state may change the first campaign direction.
- **Assumptions.** The default `PolicyIO` is the active input contract for the
  candidate being considered and the target remains in the same plane as the
  site.
- **Source references.** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence.** Use observation reconstruction checks and
  controlled policy probes: predict target position from observations, compare
  feed-forward and recurrent behavior under identical trajectories, and test
  whether failures correlate with unobserved hold phase or dynamic state.

### Scientific quantities that define behavior

- **Reasoned implication.** The physically meaningful trajectory is described by
  \(q,\dot q,\ddot q\), motor controls and implied generalized forces, endpoint
  \(p\), endpoint velocity, target error \(e=p-p_\mathrm{target}\), distance
  \(\|e\|\), Jacobian \(J(q)\), joint-limit margin, branch identity, and
  control-step time. Task-level quantities are first entry, first-reach time,
  maximum uninterrupted hold, interruptions, settling time, peak error,
  action saturation, and success. These connect morphology, actuation,
  sensing, and the official outcome.
- **Decision relevance.** These quantities distinguish geometric infeasibility,
  insufficient authority, poor trajectory timing, and unstable regulation;
  aggregate reward alone cannot make those distinctions.
- **Assumptions.** Velocities and controls recorded from the simulator are
  treated as the relevant state and command variables, and finite differences
  used for accelerations are interpreted with the 2 ms or 20 ms timing stated
  above.
- **Source references.** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`;
  `contracts/scenario.md`.
- **Discriminating evidence.** Preserve complete episode trajectories or
  equivalent summaries containing these quantities; verify that their units
  and sampling interval are explicit before attributing failures.

## Unknowns

### Compiled mass, inertia, and numerical dynamics

- **Unresolved quantity.** The XML declares link geometry, damping, and
  armature but no explicit masses, inertial tensors, solver settings, or
  integrator choice. Effective mass and inertia may therefore come from
  MuJoCo defaults and geometry inference; their exact compiled values are not
  established by the human-owned files read here.
- **Decision relevance.** These quantities set acceleration, natural response,
  braking distance, and the action scale needed for a 20 ms correction. They
  could change whether the first campaign needs conservative regulation,
  trajectory shaping, or a different policy time scale.
- **Assumptions.** The visible XML is the exact model loaded by
  `MjModel.from_xml_path`, and no runtime code changes model defaults after
  loading.
- **Source references.** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`;
  `AGENTS.md` (locked MuJoCo version).
- **Discriminating evidence.** Inspect compiled `body_mass`, inertia, joint
  damping/armature, option/integrator settings, and mass-matrix response;
  validate them with free or controlled step responses at several postures.

### Effective motor authority and saturation

- **Unresolved quantity.** The declared range and gear establish command
  bounds and transmission scale, but not the resulting joint acceleration or
  endpoint authority under coupled inertia, damping, and configuration.
  The practical torque margin during a candidate's maneuver is unknown.
- **Decision relevance.** If controls saturate during long reaches, learning
  may need to account for time-optimal or saturated motion; if they do not,
  failures more likely arise from regulation or policy representation.
- **Assumptions.** MuJoCo motor semantics are applied without an additional
  wrapper, and no uninspected actuator defaults materially alter the declared
  motor.
- **Source references.** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/policy_io.py`.
- **Discriminating evidence.** Measure controls, joint accelerations, and
  endpoint velocity under bounded step and reversal commands at multiple
  configurations; report the fraction of steps at each control bound.

### Exact range-constrained workspace and branch conditioning

- **Unresolved quantity.** The nominal annulus and analytical IK branches are
  known, but the exact set of target angles and radii admitting both joint
  angles within [-170, 170] degrees, together with their Jacobian conditioning,
  has not been enumerated from the compiled model. The target sampler's
  intended notion of “uniform” is also contractually stated while the visible
  implementation is uniform in radius and angle rather than uniform in planar
  area.
- **Decision relevance.** A small range-limited or poorly conditioned subset
  could dominate the 2% failure budget and change whether branch-aware
  targeting is needed.
- **Assumptions.** Link lengths in the Python observation code match the XML
  site geometry and the protected official evaluator follows the declared
  task distribution.
- **Source references.** `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence.** Enumerate both IK branches over a fine
  radius-angle grid, apply the compiled joint limits, calculate Jacobian
  singular values and compare the result with sampled target frequencies.

### Between-check motion and hold integrity

- **Unresolved quantity.** The implementation defines hold continuity at
  20 ms checkpoints, but a policy's endpoint may leave and re-enter the
  tolerance during the ten internal physics steps. The frequency and
  magnitude of such unobserved excursions are unknown before trajectories
  are measured.
- **Decision relevance.** If excursions are common, a nominal 100-check hold
  does not provide the same physical margin as a continuously monitored
  2-second hold, and stabilization-oriented behavior becomes more important
  than minimum-distance behavior.
- **Assumptions.** The visible environment is the operative success
  implementation and no hidden evaluator samples the internal 2 ms states.
- **Source references.** `contracts/scenario.md`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence.** Replay successful and interrupted episodes,
  evaluate distance at every internal MuJoCo step in an analysis-only copy of
  the mechanics, and compare that result with the official control-step
  counter.

### Policy-dependent dynamic and hold margins

- **Unresolved quantity.** No campaign policy has yet established the
  distribution of settling time, overshoot, action saturation, branch use,
  hold interruptions, or failure causes across the official target domain.
  Reward coefficients describe training feedback but do not establish task
  success or a physical capability.
- **Decision relevance.** The first campaign decision could differ radically
  depending on whether the goal gap is mostly reach time, target geometry,
  stabilization, or rare branch-specific failures.
- **Assumptions.** Development diagnostics are collected without changing the
  official success definition, and candidate comparisons preserve the
  observation/runtime contract being attributed.
- **Source references.** `robot_learning/training/reward.py`;
  `robot_learning/scenario/evaluation.py`;
  `contracts/scenario.md`.
- **Discriminating evidence.** Evaluate complete deterministic panels with
  episode-level success plus trajectory diagnostics: radius, angle, minimum
  and final distance, first reach, maximum hold, interruptions, controls,
  joint/end-point velocities, and termination reason.

## Decision-relevant synthesis

### 1. The first bottleneck is likely to be regulation, not mere reachability

- **Decision relevance.** The official unit is an uninterrupted 100-control-step
  hold; a policy can reach the 1 cm ball and still fail through residual motion
  or overshoot. First decisions should distinguish reach from stabilization.
- **Assumptions.** The visible distance-based, post-frame-skip success logic is
  authoritative and the arm's nominal workspace covers the sampled targets.
- **Source references.** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`;
  `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence.** Hold duration, interruptions, endpoint/joint
  velocities, peak error, settling time, and action saturation over complete
  episodes, stratified by target geometry.

### 2. Effective dynamics and motor authority are the highest-impact physical unknowns

- **Decision relevance.** Unspecified compiled inertia and actuator response
  determine whether 20 ms actions can brake and regulate inside 1 cm; this can
  redirect work between policy learning and control/dynamics characterization.
- **Assumptions.** Geometry-derived MuJoCo defaults materially influence the
  loaded model and are not fully exposed by the XML declarations.
- **Source references.** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`;
  `AGENTS.md`.
- **Discriminating evidence.** Compiled inertial parameters plus controlled
  step/reversal responses, torque-to-acceleration gain, and saturation rates
  at representative configurations.

### 3. IK branch and target-geometry variation may concentrate the failures

- **Decision relevance.** The two elbow configurations offer alternatives with
  different joint-limit and conditioning margins; rare angle-radius regions
  can consume the 2% allowed failure budget even when aggregate development
  success is high.
- **Assumptions.** Both analytical branches correspond to the site geometry,
  targets are sampled over the full stated angular range, and branch identity
  is behaviorally available through the observation.
- **Source references.** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`;
  `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence.** Range-constrained IK and Jacobian maps, branch
  assignments in trajectories, and success/hold diagnostics by radius and
  angle.

### 4. The observation is nearly full-state for this task, but omits hold phase

- **Decision relevance.** Exact q, qdot, and target-relative geometry make
  localization an unlikely first bottleneck; the missing hold counter and
  hidden dynamic quantities could instead make recurrence or explicit
  stabilization behavior consequential.
- **Assumptions.** The default 11-value `PolicyIO` is used and observations
  remain noise-free and synchronous as implemented.
- **Source references.** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.
- **Discriminating evidence.** Reconstruct target/site state from observations
  and compare failure phase for feed-forward versus recurrent policies under
  matched target panels; check correlation with hold interruptions rather than
  only first reach.

### 5. The baseline exposure is narrower than the official radial distribution

- **Decision relevance.** Training on 0.14--0.20 m while assessment includes
  0.06--0.14 m can leave a physically distinct inner-radius regime
  underrepresented; this may change the initial judgment about whether
  failures are learning coverage or control capability.
- **Assumptions.** The visible training environment is the actual baseline
  recipe and the official evaluator uses the contract range.
- **Source references.** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`;
  `contracts/task_spec.py`;
  `contracts/scenario.md`.
- **Discriminating evidence.** Compare performance and stabilization
  diagnostics across radial bins, especially 0.06--0.14 m versus
  0.14--0.20 m, while retaining the official success definition.
