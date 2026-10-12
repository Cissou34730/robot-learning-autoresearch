## Established facts

### System boundary and objective

- **[Repository fact]** The embodied system is a MuJoCo model of a fixed-base,
  planar, two-joint arm. The official task samples a stationary target with
  radius uniformly between 0.06 m and 0.20 m and angle uniformly over
  \([-\pi,\pi]\). Success requires the end effector to remain at distance at
  most 0.01 m from that target for 2.0 s without an interruption. The official
  assessment uses 200 episodes, at most 500 control steps per episode, and
  requires at least 196 successes. **Sources:** `contracts/scenario.md`
  (Official task, Success criterion, Official final assessment);
  `contracts/task_spec.py` (`TARGET_RADIUS_RANGE`, `SUCCESS_THRESHOLD`,
  `HOLD_SECONDS`, `MAX_EPISODE_STEPS`).

- **[Repository fact]** The human-defined task, robot, physics, interaction
  semantics, and success definition are immutable task boundaries. The
  implementation in `robot_learning/scenario/environment.py` supplies shared
  mechanics, but its constructor can expose research-time alternatives; the
  protected official assessment is the authority for the official result.
  **Sources:** `contracts/scenario.md` (Immutable task boundary);
  `robot_learning/scenario/environment.py` (`TwoJointArmReachEnv`,
  `make_evaluation_env`).

### Morphology, coordinates, and kinematics

- **[Repository fact]** The base is fixed to the world because the root body has
  no free joint. The upper arm has length 0.12 m and the forearm has length
  0.10 m. The shoulder and elbow are hinge joints about the world \(z\)-axis,
  so the moving mechanism has two generalized coordinates
  \(q=(q_s,q_e)\) and moves in the \(x\)-\(y\) plane at \(z=0.02\) m. The
  end-effector site is at the forearm tip; no end-effector orientation is
  specified as a task objective.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`,
  `forearm`, `shoulder`, `elbow`, `end_effector`);
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`,
  `FOREARM_LENGTH`).

- **[Repository fact]** Both hinge ranges are \([-170^\circ,170^\circ]\).
  The geometric forward kinematics are
  \(x=L_1\cos q_s+L_2\cos(q_s+q_e)\),
  \(y=L_1\sin q_s+L_2\sin(q_s+q_e)\), with \(L_1=0.12\) m and
  \(L_2=0.10\) m. The unconstrained radial workspace is therefore the
  annulus \(0.02\leq r\leq0.22\) m.
  **Sources:** `contracts/robots/two_joint_arm.xml` (body offsets and joint
  structure); `robot_learning/scenario/observations.py`
  (`shoulder_for_elbow` and link-length use); `contracts/robots/two_joint_arm.py`
  (`MAX_REACH`).

- **[Repository fact]** For an official target radius \(r\), the observation
  code computes the two inverse-kinematic elbow branches from
  \[
  \cos q_e=(r^2-L_1^2-L_2^2)/(2L_1L_2),
  \]
  using \(q_e=+\arccos(\cdot)\) and \(q_e=-\arccos(\cdot)\), then computes the
  corresponding shoulder angles. It exposes errors to both branches.
  **Source:** `robot_learning/scenario/observations.py`
  (`shoulder_for_elbow`, `elbow_open`, `elbow_folded`,
  `shoulder_open`, `shoulder_folded`).

### Actuation, simulation, and timing

- **[Repository fact]** Each joint is driven by a MuJoCo `motor` actuator with
  control range \([-1,1]\) and gear 5. The action space has two float32
  components in that range, and `physical_action` passes the policy output
  through without a scenario-specific transformation. The environment clips
  the resulting command to the action-space bounds before assigning it to
  `data.ctrl`.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`actuator` block);
  `robot_learning/scenario/policy_io.py` (`physical_action`,
  `make_policy_io`); `robot_learning/scenario/environment.py` (`step`).

- **[Repository fact]** The MuJoCo integration timestep is 0.002 s and each
  policy action is held for 10 physics steps. The policy therefore receives
  one post-integration observation every 0.020 s, or 50 control updates per
  second. The official 2.0 s hold is implemented as 100 consecutive
  in-tolerance control observations. **Sources:**
  `contracts/robots/two_joint_arm.xml` (`timestep`);
  `contracts/task_spec.py` (`FRAME_SKIP`, `HOLD_SECONDS`);
  `robot_learning/scenario/environment.py` (`control_dt`,
  `hold_steps_required`, `frame_skip`).

- **[Repository fact]** The XML sets gravity to zero. Each hinge specifies
  damping 0.5 and armature 0.01. No actuator transmission dynamics, motor
  time constant, sensor noise, external disturbance, obstacle, or contact
  behavior is specified in the robot XML. The visual plane has contacts
  disabled, and the target sphere also has contacts disabled.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`option`, `joint`,
  plane `contype`/`conaffinity`, target `contype`/`conaffinity`).

- **[Repository fact]** The XML does not explicitly specify body masses,
  inertias, solver settings, or an integrator. MuJoCo still constructs a
  numerical model when the XML is loaded, but those resulting quantities are
  not values stated by the human-owned source.
  **Source:** `contracts/robots/two_joint_arm.xml` (absence of explicit
  mass/inertia and solver/integrator attributes);
  `robot_learning/scenario/environment.py` (`MjModel.from_xml_path`).

### Initial state, target construction, and episode semantics

- **[Repository fact]** Reset calls `mj_resetData`, sets every joint position
  and velocity to zero, forwards the model, samples a target angle and radius,
  and places the target at that radius and angle with the current end-effector
  \(z\)-coordinate. Thus the initial arm is straight with
  \(q=(0,0)\), \(\dot q=(0,0)\), the end effector is at approximately
  \((0.22,0,0.02)\) m, and the target lies in the same plane.
  **Sources:** `robot_learning/scenario/environment.py` (`reset`,
  `_sample_target_position`); `contracts/robots/two_joint_arm.xml`
  (body positions and link geometry).

- **[Repository fact]** The target is a mocap body: its position is set by the
  environment and it is not a simulated arm payload or moving obstacle. The
  distance used for success is the three-dimensional Euclidean distance
  between the end-effector site and target mocap position.
  **Sources:** `contracts/robots/two_joint_arm.xml` (`target mocap="true"`);
  `robot_learning/scenario/environment.py` (`_distance_to_target`,
  `_sample_target_position`).

- **[Repository fact]** On each control step, one distance sample determines
  whether the hold counter increments or resets. Leaving the tolerance after
  any positive hold count sets an interruption flag and resets the counter to
  zero. An episode terminates on 100 held steps and truncates at 500 control
  steps if it has not terminated.
  **Source:** `robot_learning/scenario/environment.py` (`step`,
  `_held_steps`, `_outside_after_hold`, `terminated`, `truncated`).

### Sensing and policy interface

- **[Repository fact]** The default observation is an 11-element float32 vector:
  two joint positions, two joint velocities, the three-dimensional
  end-effector-minus-target vector, and four wrapped angular errors to the
  open and folded inverse-kinematic configurations. The observation is read
  directly from the current MuJoCo state after the ten physics substeps.
  **Sources:** `robot_learning/scenario/observations.py`
  (`OBSERVATION_SIZE`, `reach_observation`);
  `robot_learning/scenario/environment.py` (`_observation`, `step`);
  `robot_learning/scenario/policy_io.py` (`make_policy_io`).

- **[Repository fact]** The observation contains the generalized position and
  velocity state and a relative target vector, but not an explicit clock,
  held-step counter, previous action, actuator torque, acceleration, contact
  force, mass matrix, or external disturbance. Target radius and bearing are
  derivable from the relative vector plus current forward kinematics; the
  branch errors are derived quantities rather than additional physical
  sensors. No observation noise or sensor latency is added by the default
  observation function.
  **Sources:** `robot_learning/scenario/observations.py` (entire
  `reach_observation`); `robot_learning/scenario/environment.py`
  (`_observation`, `step`).

### Training signal and exposure

- **[Repository fact]** The current training environment samples radii only
  from 0.14 m to 0.20 m, whereas official evaluation samples 0.06 m to
  0.20 m. The current reward gives progress and closeness terms, hold-progress
  and completion bonuses, an action-cost penalty, and a small outside-band
  penalty; reward attribution does not alter the binary success rule.
  **Sources:** `robot_learning/training/environment.py`
  (`TRAINING_TARGET_RADIUS_RANGE`); `contracts/task_spec.py`
  (`TARGET_RADIUS_RANGE`); `robot_learning/training/reward.py`
  (`reach_reward`); `robot_learning/scenario/environment.py` (`step`).

- **[Repository fact]** Evaluation records minimum distance, final distance,
  first in-tolerance step, maximum held steps, in-tolerance steps, and hold
  interruptions in addition to the binary episode outcome. These are
  available diagnostics, not pre-existing campaign evidence.
  **Source:** `robot_learning/scenario/evaluation.py`
  (`episode_diagnostics`).

## Physical consequences

### Reachability is kinematically adequate but branch-dependent

- **[Reasoned implication]** Every official radius lies strictly inside the
  unconstrained annulus: the required elbow magnitude ranges approximately
  from \(49.5^\circ\) at \(r=0.20\) m to \(150.1^\circ\) at \(r=0.06\) m.
  The two elbow signs provide two distinct postures for the same planar point.
  The shoulder range is therefore not merely a representation detail: a policy
  can choose a branch with a different shoulder margin and different
  velocity/torque geometry. The task is not expected to fail because of
  geometric reach alone, but it can fail through joint limits, poor approach
  posture, or dynamics.
- **Decision relevance:** This changes whether early work should treat failures
  as workspace impossibility or as branch selection and control problems; it
  also affects whether a policy should be encouraged to use one branch or both.
- **Assumptions:** The stated link lengths and planar forward kinematics are
  the effective kinematics; no hidden collision or end-effector orientation
  constraint is introduced; MuJoCo joint limits are enforced as specified.
- **Source references:** `contracts/robots/two_joint_arm.xml`; 
  `contracts/robots/two_joint_arm.py`; `robot_learning/scenario/observations.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** For a grid of official radii and angles, solve
  both analytic branches and report joint-limit margin and forward-kinematic
  residual; compare each branch's successful approach and hold diagnostics.

### The reset state is a maximum-extension singular posture

- **[Reasoned implication]** At \(q_e=0\), the two Jacobian columns are
  collinear and the planar position Jacobian has rank one. Tangential motion
  is immediately available, but moving radially inward from the 0.22 m
  maximum extension requires first bending the elbow and is locally
  second-order in the elbow displacement. This makes the first part of an
  episode qualitatively different from later regulation and can create
  overshoot or slow convergence even though the target is reachable.
- **Decision relevance:** A startup decision may need to distinguish
  initialization/escape behavior from target regulation; aggregate success
  alone cannot reveal whether the bottleneck is singularity escape.
- **Assumptions:** The Jacobian is evaluated for the site position in the
  planar coordinates, the initial joint state is exactly zero, and no hidden
  initial perturbation is present.
- **Source references:** `robot_learning/scenario/environment.py` (`reset`);
  `contracts/robots/two_joint_arm.xml` (joint axes and link geometry);
  `robot_learning/scenario/observations.py` (forward-kinematic structure).
- **Discriminating evidence:** Measure initial reach time, elbow departure,
  Jacobian singular values or condition number, peak speed, and minimum
  distance separately for targets near and far from the initial end-effector
  position.

### Bounded motors and damping create a reach–stabilize tradeoff

- **[Reasoned implication]** A command at either action limit requests a motor
  drive proportional to gear 5, while joint damping dissipates velocity and
  armature contributes to effective rotational inertia. The same torque margin
  used to reduce distance quickly can produce residual velocity at the
  tolerance boundary; damping then helps suppress motion but also slows
  corrections. With zero gravity, the dominant forces are motor drive,
  damping, inertial effects, and any numerical constraint forces, not
  gravitational sag.
- **Decision relevance:** A policy that reaches quickly may still be inferior
  if it cannot remove velocity before the 100-sample hold; this determines
  whether the first development comparison should prioritize time-to-reach,
  settling, effort, or hold continuity.
- **Assumptions:** MuJoCo's standard motor transmission maps control through
  the declared gear, no unspecified force limit clips it first, and the
  effective mass/inertia is physically consistent with the compiled model.
- **Source references:** `contracts/robots/two_joint_arm.xml` (`motor`,
  `gear`, `damping`, `armature`, gravity); `robot_learning/scenario/environment.py`
  (`data.ctrl`, ten `mj_step` calls).
- **Discriminating evidence:** Record `ctrl`, joint velocity, end-effector
  velocity, distance, and distance change at every control step; compare
  saturated versus unsaturated actions and estimate step responses around
  representative postures.

### Holding is sampled boundary regulation, not merely point reaching

- **[Reasoned implication]** The 0.01 m tolerance is sampled every 20 ms and
  has no hysteresis. A single sampled excursion outside the band resets the
  entire hold, so a trajectory can be geometrically close on average and
  still fail. The policy must converge with sufficiently low position error
  and velocity, then maintain a stable feedback equilibrium for 2 s. The
  finite 50 Hz action rate couples allowable residual motion to local
  Jacobian conditioning and actuator authority.
- **Decision relevance:** The principal goal is an uninterrupted-hold rate, so
  first campaign decisions should separate arrival from post-arrival
  stabilization and use interruption counts rather than reward or minimum
  distance as the main diagnostic.
- **Assumptions:** The environment's sampled distance is the authoritative
  task measurement; no hidden continuous-time collision or between-sample
  criterion is applied; the target remains fixed.
- **Source references:** `contracts/scenario.md` (continuous hold wording);
  `robot_learning/scenario/environment.py` (`success_threshold`,
  `hold_steps_required`, counter update); `contracts/task_spec.py`
  (`FRAME_SKIP`, `HOLD_SECONDS`).
- **Discriminating evidence:** For each episode, compare first-reach step,
  in-tolerance steps, maximum consecutive held steps, interruption count,
  final distance, and end-effector velocity during the hold.

### The observation is close to a full deterministic task state, but not a
hold-state measurement

- **[Reasoned implication]** Joint positions and velocities plus the relative
  target vector are sufficient in this deterministic, planar model to
  reconstruct current point geometry and target bearing/radius. The four IK
  errors make both discrete posture alternatives explicit. Thus target
  localization is not intrinsically hidden. However, the observation does not
  expose the hold counter, whether the preceding sample was outside, torque,
  or acceleration. A memoryless policy cannot condition directly on elapsed
  hold progress; a recurrent policy can infer history only through its own
  internal state.
- **Decision relevance:** If failures cluster after apparently successful
  arrival, the issue may be regulation under missing force/hold-state
  information rather than target localization; this changes whether to inspect
  policy memory, control shaping, or physical-model mismatch.
- **Assumptions:** The default `PolicyIO` is used, the environment is
  deterministic apart from target sampling, and current state values are
  available without measurement noise or delay.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`
  (`PolicyRuntime.predict` and recurrent state handling).
- **Discriminating evidence:** Compare policies or controllers with and
  without recurrence while holding the physical action interface fixed; test
  whether hold interruptions are predicted by observed \(q,\dot q\), distance,
  and action history without access to the hidden counter.

### Official coverage includes a current training-distribution gap

- **[Reasoned implication]** The baseline training range excludes all targets
  with radii 0.06–0.14 m, even though those targets are official and require
  larger elbow folds. A policy can therefore appear competent on its training
  exposure while failing on an official geometric regime that is reachable but
  dynamically different. Uniform radius sampling also makes this a distribution
  difference, not merely a rare corner case.
- **Decision relevance:** The first campaign decision must treat performance on
  inner radii as a separate capability question; otherwise a high development
  score on the current range can be mistaken for evidence about the official
  objective.
- **Assumptions:** The current training environment is the recipe used for
  candidate generation and the official evaluator uses the contract range;
  policy capacity and optimization do not automatically extrapolate across
  elbow configurations.
- **Source references:** `robot_learning/training/environment.py`
  (`TRAINING_TARGET_RADIUS_RANGE`); `contracts/task_spec.py`;
  `contracts/scenario.md`.
- **Discriminating evidence:** Stratify matched-seed evaluation by target
  radius and angle, with explicit success and hold diagnostics for
  0.06–0.14 m versus 0.14–0.20 m.

### Failure classes are physically separable

- **[Reasoned implication]** A failed episode can arise from at least five
  distinct mechanisms: failure to leave the initial singular posture, a
  branch/joint-limit or geometric approach problem, insufficient torque or
  timing for convergence, overshoot/oscillation at the tolerance boundary, or
  an otherwise successful arrival followed by hold interruption. These classes
  have different signatures in reach time, minimum distance, joint posture,
  velocity, action saturation, and held-step trajectory.
- **Decision relevance:** The appropriate next research direction depends on
  which class dominates; binary success alone cannot justify a mechanism claim.
- **Assumptions:** The recorded diagnostics are computed from the same
  authoritative distance and hold logic used for success, and no unmodeled
  disturbance is present.
- **Source references:** `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py` (`episode_diagnostics`);
  `contracts/scenario.md`.
- **Discriminating evidence:** Inspect complete per-episode diagnostic
  trajectories together with action and joint-state traces, stratified by
  target radius, bearing, IK branch, and initial-distance regime.

### Physical quantities that explain the complete behavior

- **[Reasoned implication]** The scientifically meaningful trajectory is not
  just reward or success. It includes target \((r,\theta)\), \(q,\dot q\),
  end-effector position and velocity, position error, Jacobian singular values
  and branch posture, commanded and transmitted torque, action saturation,
  kinetic/actuation effort, first-reach time, settling time, time in
  tolerance, consecutive hold length, interruptions, and final error. These
  quantities connect morphology to actuation, observation to motion, and
  motion to the official outcome.
- **Decision relevance:** This set supports causal separation of reach,
  convergence, and stabilization decisions and identifies what a development
  measurement must preserve before a candidate can be compared scientifically.
- **Assumptions:** The corresponding MuJoCo state and control values can be
  recorded without changing the physical task semantics.
- **Source references:** `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`; `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** A fixed-seed trace at every 20 ms, plus
  branch- and radius-stratified aggregate summaries, would support or weaken
  each proposed failure mechanism without changing the official success rule.

## Unknowns

### Compiled inertial and numerical dynamics

- **[Unresolved quantity]** The source does not state the resulting body
  masses, center-of-mass locations, joint-space inertia matrix, MuJoCo
  integrator, solver tolerances, or constraint iterations. Those values can
  materially change acceleration, overshoot, and settling despite the visible
  geometry and damping being fixed.
- **Decision relevance:** This could change whether a control problem is
  torque-limited, inertia-limited, or numerically damped, and therefore whether
  model-based reasoning, action shaping, or ordinary policy optimization is the
  credible first route.
- **Assumptions:** MuJoCo compiler defaults are accepted by the loaded model
  and are not intentionally replaced elsewhere; the XML is the complete
  physical definition.
- **Source references:** `contracts/robots/two_joint_arm.xml` (omitted
  inertial and solver attributes); `robot_learning/scenario/environment.py`
  (`MjModel.from_xml_path`).
- **Discriminating evidence:** Inspect the compiled `MjModel` inertial and
  option fields, then compare measured free response and motor step response
  against the implied equations of motion.

### Effective motor authority under the compiled model

- **[Unresolved quantity]** The gear declaration and control bounds establish
  the actuator interface, but the practically available end-effector
  acceleration and torque margin over the workspace are not known. They vary
  with posture, joint-space inertia, damping, and the ten-substep hold.
- **Decision relevance:** If authority is low in the inner-radius or
  near-singular regimes, increasing policy complexity may not address the
  physical bottleneck; if authority is ample, stabilization and policy
  representation become more plausible bottlenecks.
- **Assumptions:** There are no hidden actuator limits or external forces
  beyond the loaded MuJoCo model.
- **Source references:** `contracts/robots/two_joint_arm.xml` (`motor`,
  `ctrlrange`, `gear`); `robot_learning/scenario/environment.py` (`data.ctrl`,
  `mj_step`).
- **Discriminating evidence:** Apply bounded, repeatable commands at several
  postures and identify angular acceleration, velocity decay, saturation time,
  and end-effector displacement; repeat for both IK branches.

### Boundary robustness and numerical margin

- **[Unresolved quantity]** It is unknown how much of the observed policy
  behavior lies near the 1 cm boundary and how much velocity or numerical
  state variation is tolerated before one 20 ms sample exits the band. The
  contract defines the threshold but not a safety margin.
- **Decision relevance:** This determines whether first improvements should seek
  lower steady-state error, lower velocity, a different posture, or merely
  better arrival timing.
- **Assumptions:** Between-sample motion is not separately assessed, and the
  sampled distance is the only success discriminator.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`distance <= success_threshold`).
- **Discriminating evidence:** Measure distance and end-effector velocity at
  every control sample during successful and interrupted holds; report the
  minimum distance margin to the threshold and the distribution of
  interruption timing.

### Policy information use and effective temporal memory

- **[Unresolved quantity]** The default observation omits hold progress and
  the current policy artifact is not specified by the physical contracts as
  memoryless or recurrent. The runtime supports recurrent state, but it is
  unknown whether a candidate uses it and whether its reset is correct at
  episode boundaries.
- **Decision relevance:** This can change whether a hold failure is an
  information/credit-assignment problem or a physical regulation problem, and
  whether a change in policy memory is scientifically relevant.
- **Assumptions:** Runtime serialization binds the candidate to its actual
  observation and policy functions, as required by `PolicyRuntime`.
- **Source references:** `contracts/policy_runtime.py` (`PolicyIO`,
  `PolicyRuntime.reset`, `predict`); `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`.
- **Discriminating evidence:** Inspect the candidate's bound runtime metadata
  and compare reset-correct recurrent and memoryless traces on identical
  episode seeds, focusing on post-arrival interruptions.

### Robustness beyond the nominal deterministic simulator

- **[Unresolved quantity]** No campaign evidence establishes sensitivity to
  parameter variation, action delay, observation noise, disturbances, or
  target-placement error. Their absence from the current model is an
  established nominal condition, not evidence of robustness.
- **Decision relevance:** This matters only if the campaign decision concerns
  robustness beyond the official nominal simulator; it should not be allowed
  to redefine the official success criterion.
- **Assumptions:** The official assessment uses the fixed nominal contracts and
  does not introduce hidden perturbations.
- **Source references:** `contracts/scenario.md` (immutable physics and task
  boundary); `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Controlled perturbation or parameter-sweep
  measurements, explicitly labeled as non-official, would establish sensitivity
  and identify which uncertainty matters for transfer or scientific claims.

## Decision-relevant synthesis

### Compiled dynamics and control authority

- **[Reasoned implication / unresolved quantity] Decision relevance:** The
  first route depends on whether acceleration and settling are constrained by
  hidden compiled inertia/numerical settings or are readily controllable.
- **Assumptions:** XML omissions are resolved by MuJoCo defaults and the loaded
  model is the operative physics.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Inspect compiled inertial/options fields and run
  bounded motor step responses before attributing failures to policy learning.

### Initial singularity and IK branch choice

- **[Reasoned implication] Decision relevance:** The reset at full extension and
  the two open/folded solutions can make early escape and approach posture
  dominate official performance even though all official targets are
  geometrically inside the workspace.
- **Assumptions:** The analytic planar kinematics and joint limits in the XML
  govern the effective task, with no hidden orientation or collision objective.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Radius/angle-stratified traces with Jacobian
  conditioning, chosen branch, first-reach time, and joint-limit margin.

### Reach versus uninterrupted stabilization

- **[Reasoned implication] Decision relevance:** The 2 s hold is 100 sampled
  updates at 50 Hz, so a high minimum-distance or first-reach score is not
  evidence of official success. Stabilization and boundary margin must be
  treated as a separate capability.
- **Assumptions:** One out-of-band sampled distance resets the hold and the
  target remains stationary.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Consecutive held steps, interruption timing,
  distance margin, and end-effector velocity throughout the complete hold.

### Official inner-radius coverage

- **[Reasoned implication] Decision relevance:** The current recipe trains on
  0.14–0.20 m but official episodes include 0.06–0.14 m, where the elbow must
  fold more. A development result without radius-stratified official-range
  evidence cannot establish readiness for the 98% objective.
- **Assumptions:** The current training environment remains the candidate's
  exposure and official evaluation retains the contract distribution.
- **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`; `contracts/scenario.md`.
- **Discriminating evidence:** Matched-seed success and full hold diagnostics
  separately reported for inner and outer radius bands and both angular
  directions.

### Observation sufficiency versus hidden hold state

- **[Reasoned implication / unresolved quantity] Decision relevance:** Geometry
  and current generalized state are observable enough to localize the target,
  but hold progress, torque, and acceleration are not directly observed.
  Whether temporal memory is needed for reliable stabilization is therefore a
  live decision boundary.
- **Assumptions:** The default 11-value observation and serialized runtime are
  used without extra sensors or state features.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py`.
- **Discriminating evidence:** Identical-seed comparisons of memoryless and
  recurrent policies, with action/state traces and post-arrival interruption
  rates, while preserving the official task and success semantics.
