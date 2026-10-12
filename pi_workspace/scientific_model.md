# Scientific model of the two-joint reach-and-hold system

This model is constructed before campaign evidence. Statements are tagged as
`[Repository fact]`, `[Reasoned implication]`, or `[Unresolved quantity]`.
Source references point to the human-owned contracts or the implementation
that defines the quantity. No behavioral performance claim is made here.

## Established facts

### Task, assessment, and immutable boundary

- [Repository fact] The policy controls a two-joint arm. A target is sampled
  with radius uniformly in 0.06--0.20 m and angle uniformly over
  `[-pi, pi]`; the target is stationary for the episode. Source:
  `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py::_sample_target_position`.
- [Repository fact] Success requires the end-effector distance to be at most
  0.01 m for 100 consecutive control steps. The control period is
  `0.002 * 10 = 0.020` s, so the required run is 2 s. An episode is truncated
  after 500 control steps, and the official panel contains 200 episodes; at
  least 196 must succeed for the 98% objective. Source:
  `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`.
- [Repository fact] The official assessment is a fixed panel distinct from
  development panels. The human-authored robot, physics, interaction
  semantics, distribution, and success definition are immutable. Source:
  `contracts/scenario.md`.
- [Repository fact] The baseline training environment samples only radii
  0.14--0.20 m, while evaluation uses 0.06--0.20 m. This is a training
  exposure choice, not a change to the official task. Source:
  `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py::make_evaluation_env`.

### Morphology and kinematics

- [Repository fact] The robot is a fixed-base planar serial chain with two
  hinge joints: `q = [q_shoulder, q_elbow]`. Both axes are the world/local
  z-axis. The upper arm length is 0.12 m and the forearm length is 0.10 m.
  Both joint ranges are declared as -170 to 170 degrees. Source:
  `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`.
- [Repository fact] The upper-arm body is located at z = 0.02 m, the forearm
  is attached at x = 0.12 m in the upper-arm frame, and the end-effector site
  is 0.10 m farther along the forearm. Thus the end-effector remains in the
  z = 0.02 m plane. Source: `contracts/robots/two_joint_arm.xml`.
- [Repository fact] With the usual relative hinge coordinates, the
  end-effector position is
  `p(q) = [0.12 cos(q1) + 0.10 cos(q1+q2),
  0.12 sin(q1) + 0.10 sin(q1+q2), 0.02]`. Source:
  `contracts/robots/two_joint_arm.xml`; the forward-kinematic structure is
  also encoded by `contracts/robots/two_joint_arm.py` and
  `robot_learning/scenario/observations.py`.
- [Repository fact] There are no translational base degrees of freedom and no
  wrist or gripper degrees of freedom. The task's target is a mocap sphere,
  not a graspable body. The plane and target have collision disabled, so
  success is a point-distance condition rather than contact, grasp, or force
  closure. Source: `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py::_distance_to_target`.
- [Repository fact] The target z coordinate is set to the current
  end-effector z coordinate. The 3-D distance used for success therefore
  reduces to planar xy distance for the reset state and unchanged model
  geometry. Source:
  `robot_learning/scenario/environment.py::_sample_target_position`;
  `robot_learning/scenario/environment.py::_distance_to_target`.

### Reachable workspace and configuration structure

- [Repository fact] Ignoring joint limits, the radial workspace of a
  two-link chain is the annulus from `|0.12-0.10| = 0.02` m to
  `0.12+0.10 = 0.22` m. The official radial interval 0.06--0.20 m is
  strictly inside that unconstrained annulus. Source:
  `contracts/robots/two_joint_arm.py`; forward kinematics above.
- [Repository fact] For target radius `r`, inverse kinematics obeys
  `cos(q2) = (r^2 - 0.12^2 - 0.10^2)/(2*0.12*0.10)`. The two signs of
  `q2` give the elbow-open and elbow-folded branches. The observation code
  explicitly computes both branches and reports four wrapped joint errors.
  Source: `robot_learning/scenario/observations.py`.
- [Reasoned implication] At the official radial endpoints, the nominal elbow
  branches are about +/-150 degrees at r = 0.06 m and +/-49.5 degrees at
  r = 0.20 m, both inside the declared elbow range. The branch shoulder
  offsets are sufficient for at least one branch to satisfy the +/-170 degree
  shoulder limit over the full target-angle range. Thus the official target
  annulus is expected to be kinematically reachable, although the exact
  limit-enforced set remains a runtime quantity. Source:
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`; deduction from the equations
  above.
- [Repository fact] The planar Jacobian is the derivative of `p_xy(q)` and
  has determinant `0.12*0.10*sin(q2)`. Source: the forward-kinematic
  definition above.
- [Reasoned implication] The chain loses first-order Cartesian conditioning
  as `q2` approaches 0 or pi. Official targets avoid the outer singularity
  at r = 0.22 m, but the inner part of the official range is closer to the
  folded singularity and can require larger joint motion for a small Cartesian
  correction. Source: the Jacobian determinant; task and link dimensions.

### Actuation and control timing

- [Repository fact] The action is a two-element vector in [-1, 1]. The
  policy-to-physical action map is currently the identity, and the
  environment clips the action before assigning it to `data.ctrl`. Source:
  `robot_learning/scenario/policy_io.py`;
  `robot_learning/scenario/environment.py::step`.
- [Repository fact] Each actuator is a MuJoCo `motor` attached directly to one
  hinge, with `ctrlrange="-1 1"` and `gear="5"`. Under MuJoCo motor semantics,
  the actuator command is converted to generalized joint force through the
  gear ratio. Source: `contracts/robots/two_joint_arm.xml`; the locked
  native MuJoCo dependency is recorded in `AGENTS.md`.
- [Repository fact] The commanded control is held constant while ten MuJoCo
  steps execute. The simulation timestep is 0.002 s, giving a 500 Hz
  internal integration rate and a 50 Hz policy/control interface. There is no
  explicit action-rate limiter or action filter in the scenario code. Source:
  `contracts/robots/two_joint_arm.xml`;
  `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py::step`.
- [Repository fact] Gravity is explicitly zero. Each joint declares damping
  0.5 and armature 0.01. Source: `contracts/robots/two_joint_arm.xml`.
- [Reasoned implication] In the absence of gravity and contact, a stationary
  configuration does not require a gravity-compensation torque. Damping
  dissipates velocity but does not create a position-restoring force, so the
  controller must actively correct position error; zero command can preserve
  a perfectly stationary state but does not generally stop a moving state.
  Source: gravity, damping, and actuator declarations in
  `contracts/robots/two_joint_arm.xml`; rigid-body dynamics.

### Reset state and task geometry

- [Repository fact] On reset, `qpos` and `qvel` are set to zero, MuJoCo
  forward dynamics are evaluated, and then a target with the official
  distribution is placed in the robot plane. Source:
  `robot_learning/scenario/environment.py::reset`.
- [Repository fact] The initial end-effector position is therefore
  approximately (0.22, 0, 0.02) m. The initial target distance depends on
  radius and angle and can range from near 0.02 m to about 0.42 m before
  considering the exact sampled angle. Source:
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py::reset`; forward kinematics.
- [Reasoned implication] The initial state is not a single fixed reaching
  problem: target direction, initial distance, and the choice of IK branch
  vary per episode. The policy must infer a target-relative correction from
  the first observation rather than rely on a fixed trajectory. Source:
  target sampling and reset implementation above.

### Sensing, policy interface, and task transition

- [Repository fact] The observation has 11 elements: two joint positions,
  two joint velocities, the three-dimensional end-effector-minus-target
  vector, and four wrapped joint-error values to the two IK branches. Source:
  `robot_learning/scenario/observations.py`.
- [Repository fact] These quantities are computed directly from MuJoCo state
  and target mocap position. No sensor noise, quantization, or measurement
  latency is introduced by the scenario observation code. Source:
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`.
- [Reasoned implication] Given the known link lengths, joint positions and
  the relative end-effector-target vector, the planar target position is
  reconstructible from the observation even though target radius and angle
  are not separate fields. The four IK errors additionally expose the
  instantaneous relation to both nominal branches. Source:
  `robot_learning/scenario/observations.py`; forward kinematics.
- [Repository fact] The policy observes the reset/current state, produces an
  action, and then receives a new observation after ten internal simulation
  steps. An optional saved normalizer and recurrent policy state are applied
  by the policy runtime; recurrent state is reset at episode start. Source:
  `contracts/policy_runtime.py`; `robot_learning/scenario/environment.py`.
- [Repository fact] The environment evaluates distance only after the ten
  internal steps. A distance within tolerance increments the held counter; a
  sampled distance outside tolerance resets it to zero. Success terminates
  at 100 such consecutive control observations. Source:
  `robot_learning/scenario/environment.py::step`.

## Physical consequences

### The objective is a coupled reach, convergence, and stabilization problem

- [Reasoned implication] **Decision relevance:** A policy must first reduce
  Cartesian error, then enter a 1 cm ball with sufficiently low residual
  motion to avoid resetting the 100-step run. A fast first arrival with
  oscillation is not equivalent to success; the first campaign direction
  should therefore distinguish reach time from hold continuity.
- [Reasoned implication] **Assumptions:** The implication assumes the
  distance and held-counter code are authoritative and that actions affect
  velocity through the declared second-order dynamics rather than an
  unmodeled position servo.
- [Reasoned implication] **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py::step`;
  `contracts/robots/two_joint_arm.xml`.
- [Reasoned implication] **Discriminating evidence:** Per-episode first
  in-tolerance step, minimum and final distance, maximum held run, number and
  timing of interruptions, joint velocity, and action/torque traces separate
  reach-limited from stabilization-limited behavior.

### Kinematic branch choice changes the trajectory and local dynamics

- [Reasoned implication] **Decision relevance:** Elbow-open and elbow-folded
  solutions can reach the same target but induce different joint paths,
  joint-limit margins, Jacobians, velocities, and inertial coupling. A
  branch-aware controller or observation interpretation may therefore matter
  more than a single Cartesian error heuristic.
- [Reasoned implication] **Assumptions:** This depends on both branches being
  dynamically accessible under the joint-limit solver and on the policy
  having enough action authority to move between configurations without
  leaving the episode horizon.
- [Reasoned implication] **Source references:** `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml`; the Jacobian and inverse-kinematic
  equations in this model.
- [Reasoned implication] **Discriminating evidence:** Record the realized
  elbow sign, distance to each joint limit, branch residuals, Jacobian
  determinant/condition measure, and success stratified by target radius and
  angle. A consistent branch with fewer interruptions would support branch
  conditioning as a useful mechanism; mixed branches with equal outcomes
  would weaken that priority.

### Control authority and damping determine whether settling is easy or hard

- [Reasoned implication] **Decision relevance:** The nominal actuator command
  is bounded and held for 20 ms, while damping and armature alter acceleration
  and stopping distance. If saturated commands cannot brake quickly enough,
  the relevant intervention is control timing/trajectory shaping; if authority
  is abundant, the limiting issue is more likely policy adaptation or
  observation use.
- [Reasoned implication] **Assumptions:** This relies on the compiled mass
  and inertia being compatible with the declared dimensions and on the motor
  `gear=5` being the dominant command scaling. No quantitative authority
  claim follows from the XML alone because masses and inertias are not
  explicitly authored there.
- [Reasoned implication] **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py::step`; the MuJoCo motor
  declaration and rigid-body equation `M(q)qdd+C(q,qdot)+Dqdot=B*tau`.
- [Reasoned implication] **Discriminating evidence:** Compiled `MjModel`
  masses/inertias, commanded versus realized generalized forces, acceleration
  after a bounded pulse, stopping distance, and action saturation fraction
  would distinguish authority-limited from policy-limited failures.

### The task has no gravity or contact-based stabilization

- [Reasoned implication] **Decision relevance:** Holding is purely geometric
  and dynamical tracking. There is no support surface, target reaction force,
  or gravity load that can passively stabilize the end effector. Methods
  relying on contact, grasping, or gravity compensation are not physically
  relevant to this task.
- [Reasoned implication] **Assumptions:** This assumes the disabled plane and
  target collision masks remain the effective interaction semantics and that
  no unmodeled external force is introduced.
- [Reasoned implication] **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py::_distance_to_target`.
- [Reasoned implication] **Discriminating evidence:** Contact counts/forces
  and gravity-enabled counterfactuals would be relevant only to test a
  disputed model interpretation; under the authored model, successful
  stabilization should instead coincide with low joint velocity and bounded
  control corrections.

### The 1 cm tolerance is a tight Cartesian tube relative to arm length

- [Reasoned implication] **Decision relevance:** A 1 cm radial tolerance is
  about 4.5% of the 22 cm maximum reach and 8.3--16.7% of the individual
  link lengths. Small joint errors can therefore cause a hold failure,
  especially where the Jacobian maps joint motion strongly into Cartesian
  motion. Settling margin, not just binary entry, is a consequential
  quantity.
- [Reasoned implication] **Assumptions:** This uses the exact Euclidean
  distance threshold and the planar target placement; it does not assume
  that success is checked continuously between control boundaries.
- [Reasoned implication] **Source references:** `contracts/task_spec.py`;
  `contracts/scenario.md`; `robot_learning/scenario/environment.py`;
  forward kinematics and Jacobian above.
- [Reasoned implication] **Discriminating evidence:** The distribution of
  distance-to-threshold margin during successful holds, Cartesian velocity,
  and joint-limit/Jacobian conditioning at the target would show whether
  the tolerance or the transient dynamics is the active bottleneck.

### Control-boundary sampling creates a distinction between physical and scored continuity

- [Reasoned implication] **Decision relevance:** The contract describes an
  uninterrupted 2 s hold, but the implementation updates the hold counter
  once per 20 ms after ten internal steps. A trajectory could leave the
  tolerance between sampled control boundaries and still be scored as held.
  Controller design and diagnostics must not silently equate the scored
  criterion with continuous-time occupancy.
- [Reasoned implication] **Assumptions:** This follows directly if no hidden
  evaluator samples the intermediate MuJoCo states differently from the
  visible scenario implementation.
- [Reasoned implication] **Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py::step`.
- [Reasoned implication] **Discriminating evidence:** Compare endpoint
  distance checks with distance at all ten internal states for every hold.
  Agreement supports treating the sampled criterion as a good proxy; detected
  excursions would revise the physical interpretation and the diagnostic
  definition of stabilization.

### The baseline training distribution leaves part of the official geometry unseen

- [Reasoned implication] **Decision relevance:** Training only on 14--20 cm
  radii does not expose a baseline policy to the more folded, potentially
  differently conditioned 6--14 cm region. A development result on the
  baseline distribution cannot by itself support uniform 98% performance
  over the official annulus.
- [Reasoned implication] **Assumptions:** This assumes the training
  environment remains the baseline used for the candidate and that the
  official evaluator uses the contract distribution without adaptation.
- [Reasoned implication] **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`; `contracts/scenario.md`.
- [Reasoned implication] **Discriminating evidence:** Evaluate matched target
  radius bins and angle bins, with reach and hold diagnostics. A sharp
  degradation below 14 cm supports coverage/conditioning as a first
  decision factor; uniform performance weakens that explanation.

### Scientifically meaningful quantities span the whole behavior

- [Reasoned implication] The minimum useful physical record is target radius
  and angle; initial distance; `q`, `qdot`, and joint-limit margins; Cartesian
  error and its velocity; first in-tolerance step; maximum consecutive hold;
  interruptions; final distance; branch residuals; Jacobian conditioning;
  command/torque magnitude and saturation; and, where available, compiled
  mass/inertia and contact/constraint forces. These quantities connect reset,
  reach trajectory, convergence, stabilization, and scored outcome.
- [Reasoned implication] **Decision relevance:** They allow a failure to be
  classified as unreachable/branch-limited, slow-to-reach,
  under-actuated/overshooting, observation-limited, or hold-interrupted
  instead of treating every failure as an undifferentiated reward outcome.
- [Reasoned implication] **Assumptions:** The quantities are useful only if
  measured with the same control timing and policy runtime as the candidate
  whose behavior is being interpreted.
- [Reasoned implication] **Source references:** `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`; `contracts/scenario.md`.
- [Reasoned implication] **Discriminating evidence:** A complete trajectory
  plus episode outcome is required; aggregate success alone cannot identify
  the mechanism.

## Unknowns

### Compiled mass, inertia, and effective torque authority

- [Unresolved quantity] The XML supplies geometry, damping, armature, and
  motor gear, but no explicit body inertial elements or geom density. The
  compiled `M(q)`, link masses, and exact generalized force response are not
  established by the human-authored text alone. Source:
  `contracts/robots/two_joint_arm.xml`.
- **Decision relevance:** This can change whether to prioritize model-based
  control, action scaling, braking/trajectory shaping, or policy learning.
- **Assumptions:** The relevance depends on transient acceleration and
  stopping being limiting rather than purely target-conditioned policy
  selection.
- **Discriminating evidence:** Inspect the compiled MuJoCo inertial arrays
  and measure a controlled pulse/free-response trajectory, comparing command,
  qvel, qacc, and stopping distance. A large torque margin weakens an
  authority hypothesis; saturation with slow braking supports it.

### Integrator, solver defaults, and exact limit enforcement

- [Unresolved quantity] The XML sets gravity and timestep but does not
  explicitly state the integrator, solver tolerances, joint-limit solver
  parameters, or whether range enforcement uses library defaults. Source:
  `contracts/robots/two_joint_arm.xml`; `AGENTS.md` records the MuJoCo version
  but not these compiled options.
- **Decision relevance:** These settings can affect endpoint states, limit
  behavior, numerical damping, and reproducibility near a 1 cm boundary.
- **Assumptions:** The issue matters most for high-speed motion, branch
  transitions, or trajectories near +/-170 degrees.
- **Discriminating evidence:** Record `MjModel` option and joint-limit
  settings and compare repeated trajectories plus near-limit probes. Stable
  results far from limits would reduce this uncertainty for the first
  campaign decisions.

### Continuous-time occupancy during each control interval

- [Unresolved quantity] The visible environment scores only the state after
  each ten-step frame skip. It does not establish whether the protected
  official evaluator additionally checks intermediate states, despite the
  contract's word "continuously." Source:
  `contracts/scenario.md`;
  `robot_learning/scenario/environment.py::step`;
  `contracts/instruments.md` says the protected evaluator is separate.
- **Decision relevance:** This can change whether to optimize endpoint
  distance alone or to enforce a margin throughout all internal steps.
- **Assumptions:** The uncertainty exists only because the protected
  evaluator implementation is not part of the accessible definitions.
- **Discriminating evidence:** Compare visible and official outcomes where
  intermediate excursions are present, or obtain an authoritative evaluator
  trace. Until then, internal-step occupancy should be retained as a
  diagnostic rather than assumed irrelevant.

### Exact reachable set under MuJoCo joint constraints

- [Unresolved quantity] Analytical kinematics predicts that the official
  target annulus is reachable on at least one IK branch, but the exact
  reachable set under the compiled joint-range and limit solver, including
  edge behavior, is not measured. Source:
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`.
- **Decision relevance:** If any angle/radius sector is practically
  unreachable or expensive, target-stratified policy design and failure
  interpretation change.
- **Assumptions:** This matters if solver enforcement or actuator limits
  materially reduce the analytical set.
- **Discriminating evidence:** Enumerate targets over the official annulus,
  solve both branches with explicit limit checks, and execute low-speed
  tracking tests. A missing sector would revise the claim that the task is
  uniformly reachable; no missing sector would support treating failures as
  control/dynamics failures.

### Observation sufficiency versus runtime preprocessing

- [Unresolved quantity] The raw scenario observation is effectively
  noise-free and contains state-derived target-relative information, but a
  learned artifact may apply saved normalization and may carry recurrent
  policy state. The candidate-specific preprocessing and recurrence behavior
  are not properties of the physical robot. Source:
  `robot_learning/scenario/observations.py`;
  `contracts/policy_runtime.py`;
  `robot_learning/training/normalization.py`.
- **Decision relevance:** Apparent sensing or memory failures may instead be
  normalization mismatch, recurrent-state handling, or action-runtime
  mismatch; this changes whether to alter observations or learning.
- **Assumptions:** The issue is consequential only for candidates whose
  runtime artifact includes normalization or recurrence.
- **Discriminating evidence:** Verify the saved runtime, normalization
  statistics, recurrent reset behavior, and raw versus normalized action
  inputs. Reproducing the same action from the same raw observation weakens
  an observability explanation.

### Effective policy latency and action persistence

- [Unresolved quantity] The environment specifies a zero-order hold over
  ten internal steps, but candidate inference cost, recurrent update timing,
  and any library-level action handling are not characterized as physical
  latency. Source:
  `robot_learning/scenario/environment.py::step`;
  `contracts/policy_runtime.py`.
- **Decision relevance:** Latency can explain overshoot and determine whether
  higher-rate control, prediction, or conservative approach trajectories are
  worth considering.
- **Assumptions:** This matters only when the policy's computational/runtime
  delay is comparable to the 20 ms control interval or the hold tolerance.
- **Discriminating evidence:** Timestamp observation, prediction, command
  assignment, and state transitions, and compare constant-command intervals.
  A measured delay much below 20 ms would weaken latency as a first-order
  cause.

### Transfer from shaped reward to the binary official objective

- [Unresolved quantity] The current reward includes distance progress,
  closeness, hold progress, an action cost, and a completion bonus, but the
  reward is research code and is not the official success criterion. Source:
  `robot_learning/training/reward.py`;
  `contracts/scenario.md`.
- **Decision relevance:** A high reward can coexist with repeated hold
  interruptions, so the first learning decision may need to change reward
  shaping, exposure, or evaluation rather than optimize reward magnitude.
- **Assumptions:** This is relevant when training selection or updates use
  reward proxies without hold diagnostics.
- **Discriminating evidence:** Compare reward components against success,
  maximum held run, interruptions, and final distance on the same episodes.
  Weak reward-success alignment supports changing the learning signal; strong
  alignment weakens that need.

## Decision-relevant synthesis

### Hold continuity is likely to be the first physical bottleneck

- **Decision relevance:** The 98% goal is a complete uninterrupted hold, so
  reach-only success or high shaped reward is insufficient. First decisions
  should distinguish entry from stable occupancy and braking.
- **Assumptions:** The visible environment semantics represent the official
  task, and the policy acts at 50 Hz with 20 ms zero-order holds.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py::step`;
  `contracts/task_spec.py`.
- **Discriminating evidence:** First-reach step, distance margin throughout
  each 2 s run, internal-step excursions, qvel, action saturation, and hold
  interruptions.

### Compiled dynamics are not quantitatively specified

- **Decision relevance:** The XML establishes damping, armature, timestep,
  zero gravity, and motor gearing, but not explicit mass/inertia or all solver
  defaults. The choice between dynamics characterization, model-based
  stabilization, and direct learning therefore depends on this uncertainty.
- **Assumptions:** Dynamics materially affect acceleration and stopping at the
  1 cm tolerance.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md`; `robot_learning/scenario/environment.py::step`.
- **Discriminating evidence:** Compiled inertial parameters and a bounded
  pulse/free-response trace showing qacc, qvel, torque, and stopping distance.

### Both IK branches are available, but conditioning and limits vary

- **Decision relevance:** The target is a position-only task with multiple
  kinematic configurations; branch choice can alter joint limits, Jacobian
  conditioning, path length, and hold stability. Branch-aware diagnostics
  should precede conclusions that a policy lacks reachability.
- **Assumptions:** At least one branch remains accessible under compiled
  limits for every official target, as analytical geometry indicates.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.py`.
- **Discriminating evidence:** Branch realized, branch residuals, Jacobian
  conditioning, joint-limit margin, and success/hold interruption by target
  radius and angle.

### Official coverage includes a region absent from baseline training

- **Decision relevance:** Baseline exposure begins at 14 cm while the
  official distribution begins at 6 cm. Performance near the more folded
  region cannot be inferred from outer-radius training behavior, even though
  all official targets are analytically within the arm's reach.
- **Assumptions:** Candidate training uses
  `TRAINING_TARGET_RADIUS_RANGE` and official evaluation preserves the
  contract distribution.
- **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`; `contracts/scenario.md`.
- **Discriminating evidence:** Matched evaluation bins over radius and angle,
  with separate reach and hold outcomes. A lower-radius failure cluster would
  support coverage/conditioning as the immediate decision frontier.

### The observation is rich, but it does not expose every dynamic quantity

- **Decision relevance:** The policy receives exact q, qvel, relative
  Cartesian error, and branch errors, but not mass/inertia, applied torque,
  acceleration, constraint forces, or intermediate states. If hidden dynamic
  quantities are needed for braking, history or a different observation may
  matter; if not, changing sensing would be unnecessary.
- **Assumptions:** The raw observation definition is the one used by the
  candidate runtime, with its saved preprocessing correctly restored.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`.
- **Discriminating evidence:** Compare actions and outcomes under identical
  observable states, and correlate failures with unobserved acceleration,
  torque saturation, and internal-step excursions. This separates
  observability limits from insufficient control authority or training.

