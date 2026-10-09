# Scientific model: two-joint arm reach-and-hold

## Established facts

### Task, simulator, and episode semantics

- **[Repository fact]** The official task samples a target at a radius from 0.06 m
  to 0.20 m from the base, over the full angular range. Success requires the
  end effector to be within 0.01 m of that target for 2.0 s without an
  interruption. The official control timing defines this as 100 consecutive
  control steps; an episode has at most 500 control steps. **Sources:**
  `contracts/scenario.md`; `contracts/task_spec.py`.
- **[Repository fact]** The official assessment uses 200 fixed-panel episodes and
  requires at least 196 successes, or 98%. This is an episode-level criterion:
  a partial hold is a failure, not partial credit toward success. **Source:**
  `contracts/scenario.md`.
- **[Repository fact]** The native MuJoCo model advances at 0.002 s per
  integration step. The shared environment applies one action for 10 such
  steps, so one policy decision spans 0.020 s and the controller rate is 50 Hz.
  The 100-step hold is therefore 2.0 s, and the 500-step episode limit is 10 s.
  **Sources:** `contracts/robots/two_joint_arm.xml`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** At reset, both joint positions and velocities are set to
  zero, MuJoCo is forwarded, and then a target is sampled. The target angle is
  uniform on `[-pi, pi]` and its radius is uniform on `[0.06, 0.20]` m in the
  shared environment. **Source:** `robot_learning/scenario/environment.py`.

### Morphology and kinematics

- **[Repository fact]** The robot is a serial two-link planar arm. The shoulder
  and elbow are hinge joints about the world z axis, with link lengths
  `l1 = 0.12 m` and `l2 = 0.10 m`. The end-effector site is at the distal end
  of the forearm. The arm plane is `z = 0.02 m`. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`.
- **[Repository fact]** With joint coordinates `q = (q1, q2)`, where `q2` is
  relative elbow angle, the end-effector position is
  `p(q) = (l1*cos(q1) + l2*cos(q1+q2),
  l1*sin(q1) + l2*sin(q1+q2), 0.02)`. **Source:** the body hierarchy and
  joint axes in `contracts/robots/two_joint_arm.xml`.
- **[Repository fact]** Each hinge has a configured range of -170 to +170
  degrees. The unconstrained two-link workspace is the annulus from
  `|l1-l2| = 0.02 m` to `l1+l2 = 0.22 m`; joint limits remove configurations
  near some angular and radial boundaries. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`.
- **[Repository fact]** The planar Jacobian is
  `J(q) = [[-l1*sin(q1)-l2*sin(q1+q2), -l2*sin(q1+q2)],
  [l1*cos(q1)+l2*cos(q1+q2), l2*cos(q1+q2)]]`, with determinant
  `l1*l2*sin(q2)`. **Source:** the kinematic structure in
  `contracts/robots/two_joint_arm.xml`.
- **[Repository fact]** The target is placed at the end-effector z coordinate,
  so the three-dimensional distance used for success has no z component in the
  defined environment. The plane, base, and target geoms explicitly disable
  collision; the link geoms do not set collision masks in the XML. Thus there is
  no defined external obstacle interaction, while possible link self-contact
  depends on MuJoCo's defaults and is not established by the source text alone.
  **Source:** `robot_learning/scenario/environment.py`;
  `contracts/robots/two_joint_arm.xml`.

### Actuation and dynamics

- **[Repository fact]** Each joint is driven by a MuJoCo motor with control
  range `[-1, 1]` and gear `5`. The policy action is passed through unchanged
  after environment clipping, and the resulting control is held constant for
  the 10 integration steps of a control interval. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/policy_io.py`;
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** The joints have damping `0.5` and armature `0.01`.
  Gravity is zero. No actuator activation state, actuator filter, explicit
  torque limit beyond the motor control range, or action delay is defined in the
  model. **Source:** `contracts/robots/two_joint_arm.xml`.
- **[Repository fact]** The action changes generalized joint forcing; MuJoCo
  then integrates the coupled joint dynamics over 10 substeps before the next
  observation. In schematic form,
  `M(q)*qdd = tau(action) - h(q,qdot) - damping*qdot - limit_forces`,
  with `tau` determined by the motor gear and `h` containing the
  configuration-dependent inertial terms. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** The XML does not explicitly provide body masses,
  inertial tensors, friction coefficients, or actuator dynamics. MuJoCo
  therefore supplies the compiled inertial quantities from its model defaults
  and geometry processing. The source-level numeric values of those compiled
  quantities are not stated here. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md` (native MuJoCo runtime contract).

### Sensing and policy interface

- **[Repository fact]** The policy receives 11 values in this order: two joint
  positions, two joint velocities, the three-vector from end effector to
  target, and four joint-space errors to the two inverse-kinematic branches
  (open elbow and folded elbow). **Source:**
  `robot_learning/scenario/observations.py`.
- **[Repository fact]** Joint position and velocity, end-effector position,
  target position, and the two branch solutions are exact simulator-derived
  quantities in the shared environment; no observation noise or quantization is
  added there. The target position is not copied directly into the vector, but
  it is reconstructible from the known end-effector position and the observed
  relative vector. **Sources:**
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** The observation does not contain the held-step counter,
  previous action, previous distance, episode time, target radius/angle as
  separate fields, compiled dynamic parameters, actuator forces, or contact
  forces. The hold counter is maintained internally by the environment and is
  reset whenever a post-action distance is outside the tolerance. **Sources:**
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
- **[Repository fact]** The success distance is the Euclidean end-effector to
  target distance after each control interval. A distance at or below 0.01 m
  increments the consecutive hold count; one distance above it resets that
  count to zero. **Source:** `robot_learning/scenario/environment.py`.

## Physical consequences

### Reachability and inverse-kinematic alternatives

- **[Reasoned implication]** Every official target radius lies inside the
  unconstrained annulus, and at least one inverse-kinematic branch is physically
  available across the official range. The elbow magnitudes vary from about
  150.2 degrees at 0.06 m to 49.5 degrees at 0.20 m; the corresponding
  shoulder solutions fit within the stated +/-170 degree limits for a valid
  branch. The alternate branch can be removed by the shoulder limit near
  angular wrap boundaries. Thus failure need not be caused by geometric
  impossibility, but can be caused by selecting or transitioning through an
  inconvenient branch. **Decision relevance:** Initial policy representations
  and diagnostics should distinguish branch selection from pure reachability.
  **Assumptions:** The planar position equation is the operative kinematics and
  the configured ranges are enforced symmetrically. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`;
  `robot_learning/scenario/observations.py`.
  **Discriminating evidence:** Per-target final joint configuration and the
  sign/magnitude of `q2`, compared with both analytic IK solutions, would show
  whether failures are branch-selection or tracking failures.

### Trajectory control and singularity conditioning

- **[Reasoned implication]** Reaching is not equivalent to solving IK. A
  controller must move from the zero state, apply torque through a coupled
  Jacobian, avoid overshoot at 50 Hz, and settle inside a 1 cm disk. The
  Jacobian becomes ill-conditioned as `sin(q2)` approaches zero, so motion
  close to full extension or full folding can require larger joint motion or
  more precise timing for a given Cartesian correction. **Decision relevance:**
  First performance analysis should separate first entry into tolerance from
  sustained hold and should stratify by radius and target angle. **Assumptions:**
  The local Jacobian governs the relevant correction and no contact force
  changes the motion. **Sources:** the Jacobian derived from
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** Time histories of distance, joint position,
  joint velocity, and branch error by target radius would reveal whether errors
  concentrate near poorly conditioned configurations.

### Stabilization is the decisive coupled capability

- **[Reasoned implication]** The 2 s hold is a local stabilization problem after
  the reaching problem. With direct motor commands, nonzero velocity at first
  entry can carry the end effector outside the tolerance on a later 20 ms
  interval. A successful policy therefore needs both convergence and a
  low-motion equilibrium or corrective feedback, not merely a single accurate
  waypoint crossing. **Decision relevance:** A high rate of first entries with
  low success indicates that hold control, not global reachability, is the
  limiting capability. **Assumptions:** The compiled inertial and damping
  properties permit a controllable local equilibrium within the torque range.
  **Sources:** `contracts/scenario.md`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** `first_reach_step`, `max_held_steps`,
  `hold_interruptions`, final distance, and joint velocity over complete
  episodes distinguish convergence from hold loss.

### The reset state makes target geometry a trajectory variable

- **[Reasoned implication]** The arm always starts at `q = (0, 0)` and
  `qdot = (0, 0)`, with the links extended toward positive x. Targets at
  different angles therefore begin with different required rotations and
  transient distances even when their radii match. The task is not only a
  stationary mapping from target position to IK; it is a finite-horizon
  trajectory from one common initial state. **Decision relevance:** Early
  comparisons should stratify by target angle as well as radius, because
  direction-dependent acquisition or braking can dominate aggregate success.
  **Assumptions:** Reset is performed exactly as in the shared environment and
  target sampling is independent of the reset state. **Sources:**
  `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`.
  **Discriminating evidence:** Compare first-reach time, peak joint speed, and
  hold interruptions across angular bins at matched radii.

### Action authority and timing

- **[Reasoned implication]** The policy can change both joint commands every
  20 ms, but cannot react within the 10 MuJoCo substeps. The gear and control
  range provide bounded direct joint forcing; damping opposes velocity and
  armature adds apparent joint inertia. This creates a tradeoff between fast
  acquisition and low residual velocity at entry to the hold. **Decision
  relevance:** Control-rate assumptions determine whether a method needs
  anticipatory braking or can rely on reactive correction. **Assumptions:** The
  motor gear maps normalized control to the usual MuJoCo generalized actuator
  force and the compiled mass matrix is finite and positive definite. **Sources:**
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/policy_io.py`.
  **Discriminating evidence:** A bounded action sweep from several reset
  states, recording joint acceleration, velocity, and distance response over
  substeps, would measure usable control authority and braking time.

### Observation is physically rich but task-progress incomplete

- **[Reasoned implication]** The policy has enough instantaneous information to
  reconstruct the target relative to the arm and to compare its state with both
  IK branches. The physical state relevant to deterministic motion is therefore
  largely observable. However, the hold-progress state is not observed, so a
  memoryless policy cannot know how many successful intervals have already
  accumulated; it must instead maintain the physical condition indefinitely or
  use temporal information available through its policy architecture. **Decision
  relevance:** Evaluation must not interpret a stable final pose as evidence of
  a completed hold, and learning methods should be judged on uninterrupted
  trajectories rather than proximity alone. **Assumptions:** The visible
  observation implementation is the one used by the measured policy and no
  recurrent state is supplied outside the listed values. **Sources:**
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** Compare policies with equal minimum distance but
  different `max_held_steps` and interruption counts; this directly tests the
  hidden-progress consequence.

### Training distribution is narrower than the official physical task

- **[Reasoned implication]** The baseline training environment samples radii
  from 0.14 m to 0.20 m, while official evaluation samples 0.06 m to 0.20 m.
  A policy can therefore learn adequate outer-workspace behavior while
  remaining untested during training on the more folded inner targets. This is
  a distribution-coverage issue, not evidence that inner targets are
  unreachable. **Decision relevance:** The first campaign comparison must treat
  inner-radius performance as a separate generalization question. **Assumptions:**
  The baseline construction remains the active training recipe and official
  evaluation uses the contract distribution. **Sources:**
  `robot_learning/training/environment.py`;
  `contracts/scenario.md`;
  `contracts/task_spec.py`.
  **Discriminating evidence:** Equal-seed evaluation binned by target radius,
  especially below 0.14 m, would show whether the official gap is localized to
  coverage rather than control or geometry.

### Complete-trajectory quantities are more informative than a scalar score

- **[Reasoned implication]** Target radius and angle, end-effector distance,
  joint position and velocity, first entry time, minimum and final distance,
  maximum consecutive hold, and interruption count jointly identify whether an
  episode failed by unreachable geometry, slow acquisition, overshoot, or
  unstable holding. A scalar reward or success percentage cannot distinguish
  those mechanisms. **Decision relevance:** These quantities determine whether
  the next scientific comparison concerns workspace coverage, trajectory
  shaping, or stabilization. **Assumptions:** The telemetry is recorded at each
  control step and the distance threshold is the official success test.
  **Sources:** `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`.
  **Discriminating evidence:** Episode-level trajectories and geometry-binned
  summaries containing all listed quantities.

## Unknowns

### Compiled inertial and force-response quantities

- **[Unresolved quantity]** The effective link masses, inertia tensors,
  center-of-mass locations, and resulting mass matrix are not explicitly
  specified in the XML. Consequently, the numerical acceleration, peak
  velocity, braking distance, and time-to-target under a given action are not
  derivable from the source text alone. **Decision relevance:** These values
  can change whether fast reaching, conservative damping, or explicit
  trajectory shaping is physically viable. **Assumptions:** MuJoCo default
  geometry density and inertial compilation are active exactly as in the
  installed runtime. **Sources:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md`.
  **Discriminating evidence:** Inspect the compiled MuJoCo `body_mass`,
  `body_inertia`, and joint mass matrix, then compare them with measured
  acceleration and settling responses under known controls.

### Joint-limit behavior at the edge of the configured range

- **[Unresolved quantity]** The XML declares joint ranges but does not state in
  the file how limit activation and near-limit constraint forces are exposed
  during policy control. The consequence of driving against a limit, including
  any rebound or loss of authority, is therefore not established by the model
  text alone. **Decision relevance:** A branch or trajectory that approaches
  +/-170 degrees may require limit-aware control and can alter the ranking of
  alternative IK solutions. **Assumptions:** MuJoCo's native interpretation of
  the hinge range is the official interpretation and no hidden wrapper changes
  it. **Source:** `contracts/robots/two_joint_arm.xml`.
  **Discriminating evidence:** Compiled joint-limit flags and a controlled
  approach/reversal experiment recording q, qdot, actuator force, and constraint
  force would resolve the behavior.

### Link self-contact under MuJoCo defaults

- **[Unresolved quantity]** The upper-arm and forearm capsules do not specify
  collision masks, unlike the plane, base, and target. Whether MuJoCo excludes
  their parent-child contact or permits any capsule self-contact at particular
  joint configurations is therefore not established by the XML alone.
  **Decision relevance:** Unexpected self-contact could create a distinct
  failure class and invalidate a purely free-space dynamics explanation near
  folded configurations. **Assumptions:** Native MuJoCo collision filtering
  and the compiled geometry are authoritative. **Source:**
  `contracts/robots/two_joint_arm.xml`.
  **Discriminating evidence:** Inspect compiled contact exclusions and record
  contact pairs and constraint forces during representative folded and
  extended trajectories.

### Realized actuator authority relative to the task horizon

- **[Unresolved quantity]** The motor gear and control range establish the
  command scale, but the source definitions do not establish the maximum
  Cartesian speed, settling time, or worst-case 10 s success margin for all
  official targets. **Decision relevance:** If the slowest target trajectories
  consume most of the 500-step horizon, the first research direction must
  prioritize time-efficient acquisition rather than only steady-state accuracy.
  **Assumptions:** Compiled inertia, damping, and limit forces are the dominant
  contributors and there are no unmodeled contacts. **Sources:**
  `contracts/scenario.md`;
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** Episode diagnostics of first-reach step and
  timeout rate, stratified by target geometry, together with controlled action
  response measurements.

### Observation and task-state sufficiency for the actual policy runtime

- **[Unresolved quantity]** The scenario observation function exposes physical
  state and geometric errors, but the model does not establish whether the
  selected learned policy is memoryless or recurrent, nor whether any saved
  runtime normalization changes numerical conditioning. **Decision relevance:**
  This can change whether hidden hold progress is harmless because the policy
  maintains a stable pose, or harmful because it requires temporal state.
  **Assumptions:** The serialized policy runtime is authoritative for the
  candidate being studied. **Sources:**
  `robot_learning/scenario/observations.py`;
  `contracts/policy_runtime.py`;
  `robot_learning/training/current_params.json`.
  **Discriminating evidence:** Inspect the candidate runtime contract and compare
  repeated hold trajectories with and without recurrent state, while preserving
  the same target panel.

### Distribution semantics and edge-case coverage in official measurement

- **[Unresolved quantity]** The shared implementation explicitly samples radius
  uniformly, while the prose contract specifies uniform targets by radial
  interval and angle without separately stating whether “uniform” means
  uniform radius or uniform planar area. The implementation is the available
  concrete definition, but this semantic distinction would change the
  frequency of inner targets if the protected evaluator differed. **Decision
  relevance:** It changes which geometry dominates the 98% aggregate and how
  development panels should be interpreted. **Assumptions:** The protected
  benchmark follows the human contract rather than a different sampling
  measure. **Sources:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`.
  **Discriminating evidence:** The official evaluator's recorded target-radius
  distribution or a protected task-reference panel would settle the measure;
  until then, radius-uniform sampling is the implementation-grounded model.

## Decision-relevant synthesis

### Effective dynamics are the main physical uncertainty

- **[Reasoned implication / unresolved quantity] Decision relevance:** The
  missing explicit masses and inertias can change acceleration, braking, and
  hold stability, so they are likely to change whether the first policy should
  emphasize speed or conservative convergence.
- **Assumptions:** MuJoCo's compiled defaults, damping, armature, and motor gear
  are the operative dynamics and there are no contacts.
- **Sources:** `contracts/robots/two_joint_arm.xml`; `AGENTS.md`.
- **Discriminating evidence:** Compiled inertial values and controlled torque
  response, followed by first-reach and hold diagnostics.

### Official coverage includes an inner-radius regime absent from baseline training

- **[Repository fact / reasoned implication] Decision relevance:** Baseline
  training covers 0.14-0.20 m, but the official goal includes 0.06-0.20 m;
  aggregate development success can conceal a systematic inner-workspace gap.
- **Assumptions:** The baseline training environment is used and the official
  distribution follows `contracts/scenario.md`.
- **Sources:** `robot_learning/training/environment.py`;
  `contracts/scenario.md`;
  `contracts/task_spec.py`.
- **Discriminating evidence:** Radius-binned, same-panel measurements of
  first reach, minimum distance, hold interruptions, and timeout rate.

### Success is a sustained-control property, not a reach-only property

- **[Reasoned implication] Decision relevance:** The complete uninterrupted
  100-step hold can fail after a successful first entry; the first campaign
  judgment must therefore use hold-specific evidence rather than proximity or
  reward alone.
- **Assumptions:** The environment's post-step tolerance test and counter reset
  define official success.
- **Sources:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** `first_reach_step`, `max_held_steps`,
  `hold_interruptions`, and final success for each episode.

### Multiple IK branches create a real policy choice

- **[Reasoned implication] Decision relevance:** Where both elbow
  configurations satisfy the joint limits, their joint paths, conditioning, and
  proximity to limits differ; near angular boundaries only one branch may be
  admissible. A policy can therefore fail through poor branch choice even when
  the target is reachable.
- **Assumptions:** The analytic two-link kinematics and stated joint ranges
  govern the official robot.
- **Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Compare the executed joint trajectory against
  both branch references and stratify failures by elbow sign and target radius.
