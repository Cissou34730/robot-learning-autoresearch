## Established facts

### Source references and status

- **[Repository fact]** This is the pre-campaign physical model. It contains no
  campaign evidence and selects no training intervention. The lifecycle requires
  this model to distinguish facts, consequences, and unknowns before campaign
  work begins. **Source:** `contracts/program.md:35-47`;
  `contracts/instruments.md:387-400`.
- **[Repository fact]** The official task is a two-joint-arm reach-and-hold:
  a target is sampled with radius 0.06--0.20 m over the full angular range, and
  the end effector must remain within 0.01 m for 2.0 s. The official assessment
  uses 200 episodes and requires at least 196 successes. **Source:**
  `contracts/scenario.md:7-31`; `contracts/task_spec.py:6-11`.

### Morphology, coordinates, and kinematics

- **[Repository fact]** The robot is fixed at the world origin and moves in the
  horizontal plane at `z = 0.02 m`. It has a shoulder hinge and an elbow hinge,
  both about the world/body `z` axis. The upper arm and forearm lengths are
  `L1 = 0.12 m` and `L2 = 0.10 m`; the end-effector site is at the forearm tip.
  **Source:** `contracts/robots/two_joint_arm.xml:9-23`;
  `contracts/robots/two_joint_arm.py:3-7`.
- **[Repository fact]** With `q = (q1, q2)`, where `q1` is the shoulder angle
  from world `+x` and `q2` is elbow angle relative to the upper arm, the
  end-effector position is
  `p(q) = (L1 cos(q1) + L2 cos(q1+q2),
  L1 sin(q1) + L2 sin(q1+q2), 0.02)`. **Source:**
  `contracts/robots/two_joint_arm.xml:12-23`.
- **[Repository fact]** Each joint range is `[-170, 170]` degrees. The
  configuration has two position degrees of freedom and two corresponding
  generalized velocities. **Source:** `contracts/robots/two_joint_arm.xml:13-18`.
- **[Reasoned implication]** The unconstrained planar workspace is the annulus
  `|L1-L2| <= r <= L1+L2`, or `0.02 <= r <= 0.22 m`, with all polar angles.
  The official radial interval lies inside this annulus, so target position is
  geometrically reachable before joint-limit and trajectory considerations.
  **Decision relevance:** this separates a position-space impossibility from a
  control failure. **Assumptions:** the XML site and link offsets are the
  effective lengths and the target shares `z = 0.02 m`. **Source:**
  `contracts/robots/two_joint_arm.xml:12-26`; `contracts/task_spec.py:6-6`.
  **Discriminating evidence:** analytic and compiled-model IK over the complete
  official radius-angle domain.
- **[Reasoned implication]** For a target with polar angle `phi` and radius
  `r`, the two analytic branches are
  `q2 = +/- acos((r^2-L1^2-L2^2)/(2L1L2))`, with `q1` chosen to align the
  two-link sum with `phi`. The elbow-up and elbow-down branches are therefore
  alternative terminal postures, not merely alternative labels. **Decision
  relevance:** branch choice can change path length, joint-limit margin,
  Jacobian conditioning, and inertial transients. **Assumptions:** the target
  is in the annulus and the analytic geometry matches the compiled model.
  **Source:** `robot_learning/scenario/observations.py:18-35`.
  **Discriminating evidence:** branch-wise IK feasibility, trajectory,
  Jacobian, and success measurements.
- **[Reasoned implication]** At least one nominal IK branch is within the stated
  joint ranges for every official target: over `r = 0.06--0.20 m`, the required
  elbow magnitude is approximately `49.5--150 degrees`, and a branch can be
  selected so the shoulder magnitude remains below approximately `158 degrees`
  for the extreme target angles. Thus the official distribution does not have
  an obvious static joint-limit impossibility, although a particular motion
  path can still encounter a limit. **Decision relevance:** persistent failures
  should not be attributed to unreachable terminal poses without checking
  path and limit behavior. **Assumptions:** the angle convention and native
  hinge ranges are as stated, and the analytic branch is not altered by
  hidden constraints. **Sources:** `contracts/robots/two_joint_arm.xml:13-18`;
  `robot_learning/scenario/observations.py:18-35`; `contracts/scenario.md:9-14`.
  **Discriminating evidence:** exhaustive constrained IK with limit margins and
  compiled-model forward-kinematics residuals.
- **[Reasoned implication]** The planar Jacobian is
  `J = [[-L1 sin(q1)-L2 sin(q1+q2), -L2 sin(q1+q2)],
  [L1 cos(q1)+L2 cos(q1+q2), L2 cos(q1+q2)]]`, with
  `det(J) = L1 L2 sin(q2)`. The reset pose `q=(0,0)` is straight and rank
  deficient at `p=(0.22,0,0.02)`; official terminal radii avoid the two
  workspace-boundary singularities. **Decision relevance:** the initial motion
  must leave a singular configuration, while terminal control is locally
  two-dimensional but posture-conditioned. **Assumptions:** the analytic
  Jacobian describes the site position and local linearization is adequate.
  **Sources:** `contracts/robots/two_joint_arm.xml:12-23`;
  `robot_learning/scenario/environment.py:109-114`;
  `contracts/task_spec.py:6-6`. **Discriminating evidence:** Jacobian singular
  values, initial steering trajectories, and target-conditioned settling.

### Actuation, dynamics, and timing

- **[Repository fact]** The policy produces a two-element action in `[-1,1]`.
  The environment clips it, maps it identically to `data.ctrl`, and holds it
  for 10 MuJoCo steps. The simulator timestep is `0.002 s`, so the policy
  control interval is `0.020 s` (`50 Hz`). **Source:**
  `robot_learning/scenario/environment.py:56-68,122-133`;
  `robot_learning/scenario/policy_io.py:11-16`;
  `contracts/robots/two_joint_arm.xml:1-2`.
- **[Repository fact]** Each actuator is a native MuJoCo motor on one hinge with
  `gear=5` and control range `[-1,1]`; under native motor transmission this
  makes the commanded generalized torque proportional to control, with nominal
  magnitude 5 in the model's torque units. There is no XML position or
  velocity servo. **Source:** `contracts/robots/two_joint_arm.xml:30-33`.
- **[Repository fact]** Joint damping is `0.5` and armature is `0.01` for both
  joints. Gravity is zero. The floor and target geom are non-colliding; the
  success definition contains no grasp, force, or object-contact requirement.
  **Source:** `contracts/robots/two_joint_arm.xml:2,6,13-18,25-27`;
  `contracts/scenario.md:16-21`.
- **[Reasoned implication]** In the active free-space task, the qualitative
  generalized dynamics are
  `M(q) qdd + C(q,qdot) qdot + D qdot + tau_limit/contact = tau_motor`,
  with zero gravity and explicit damping/armature contributions. The shoulder
  and elbow are dynamically coupled because the forearm moves with the
  shoulder and `M(q)` varies with posture. **Decision relevance:** fast
  shoulder and elbow actions cannot be interpreted as independent scalar
  position commands. **Assumptions:** standard native MuJoCo articulated-body
  dynamics apply and no unmeasured contact impulse dominates. **Sources:**
  `contracts/robots/two_joint_arm.xml:2,13-19,30-33`. **Discriminating
  evidence:** cross-joint acceleration response, actuator saturation, and
  free-decay traces.
- **[Reasoned implication]** With no gravity, a stationary in-tolerance pose
  needs no gravity-compensation torque; damping also vanishes at zero velocity.
  Holding is therefore primarily about eliminating residual velocity and
  avoiding action-induced drift inside a 1 cm Cartesian region. **Decision
  relevance:** terminal braking and small corrective actions matter more than
  static load balancing. **Assumptions:** no contact, numerical drift, or
  hidden actuator state materially changes the ideal model. **Sources:**
  `contracts/robots/two_joint_arm.xml:2,13-18,30-33`;
  `robot_learning/scenario/environment.py:134-143`. **Discriminating evidence:**
  zero-action settling and action/velocity traces during successful holds.
- **[Reasoned implication]** The plant is sampled-data with zero-order-held
  actions: the controller observes a post-step state, commits one action for
  20 ms, then receives the next observation and checks the target distance.
  The policy must account for motion accumulated during that interval rather
  than correct continuously. **Decision relevance:** the useful feedback
  bandwidth and braking timing are part of the task, not only properties of
  the learned function. **Assumptions:** protected evaluation preserves the
  visible control cadence. **Source:** `robot_learning/scenario/environment.py:122-168`;
  `contracts/task_spec.py:8-8`. **Discriminating evidence:** timestamped
  action, substep state, and distance traces.

### Initial state and task geometry

- **[Repository fact]** Reset sets `qpos=(0,0)`, `qvel=(0,0)`, forwards the
  model, then samples a stationary target with angle uniform on `[-pi,pi]` and
  radius uniform on `[0.06,0.20] m`; target `z` equals the end-effector `z`.
  **Source:** `robot_learning/scenario/environment.py:83-97,102-120`;
  `contracts/scenario.md:9-14`.
- **[Reasoned implication]** The reset end effector is at the outer workspace
  boundary while every official target has radius at most 0.20 m, so the
  initial point is outside the 1 cm success ball. The initial radial and
  angular error depend strongly on target angle: targets near `+x` require
  little initial displacement, whereas targets near the opposite side require
  a large reorientation and traversal. **Decision relevance:** target angle is
  a physical difficulty variable and can alter reach time even at fixed radius.
  **Assumptions:** the reset and target sampling code is authoritative for
  development behavior. **Sources:** `contracts/robots/two_joint_arm.xml:12-20`;
  `robot_learning/scenario/environment.py:83-120`. **Discriminating evidence:**
  initial distance, path length, first-entry time, and success by angle.
- **[Reasoned implication]** The target is sampled uniformly in radius, not
  uniformly in planar area, so equal radial intervals receive equal sampling
  probability. This makes radius-conditioned performance directly relevant to
  the official objective. **Decision relevance:** average performance can hide
  a systematic inner- or outer-radius failure region. **Assumptions:** the
  contract's distribution is implemented by the visible sampler and not
  transformed by the protected evaluator. **Source:**
  `robot_learning/scenario/environment.py:83-97`; `contracts/task_spec.py:6-6`.
  **Discriminating evidence:** target-radius histograms and protected-panel
  sampling records.
- **[Repository fact]** Distance is the Euclidean distance from the end-effector
  site to the target mocap position. An episode holds only when this distance
  is at most `0.01 m` for 100 consecutive control samples; an excursion resets
  the hold count. The episode horizon is 500 control steps (10 s). **Source:**
  `robot_learning/scenario/environment.py:75-81,134-168`;
  `contracts/task_spec.py:7-11`.
- **[Reasoned implication]** The 1 cm Cartesian ball corresponds locally to a
  tangential angular tolerance of about `0.01/r`: roughly 9.6 degrees at
  6 cm and 2.9 degrees at 20 cm. Outer targets therefore demand tighter
  angular regulation even though they require less elbow bending than inner
  targets. **Decision relevance:** radius can affect stabilization independently
  of reach distance. **Assumptions:** small-error tangential linearization and
  the stated point-distance criterion. **Sources:** `contracts/task_spec.py:6-11`;
  `robot_learning/scenario/environment.py:78-81`. **Discriminating evidence:**
  distance, Jacobian conditioning, velocity, and interruption statistics by
  radius.
- **[Repository fact]** The baseline training environment samples radii
  `0.14--0.20 m`, narrower than the official `0.06--0.20 m` interval. **Source:**
  `robot_learning/training/environment.py:14-19`;
  `contracts/task_spec.py:6-6`.

### Sensing and the control-to-outcome relation

- **[Repository fact]** The observation has 11 float32 values: two joint
  positions, two joint velocities, the 3-D end-effector-minus-target vector,
  and four wrapped residuals to the open and folded analytic IK solutions.
  **Source:** `robot_learning/scenario/observations.py:11-49`.
- **[Reasoned implication]** In the noiseless simulator, the task-relevant
  instantaneous physical state is effectively observable. Joint position and
  the known kinematics determine end-effector position; adding the observed
  position error reconstructs target position; joint velocity is explicit.
  No camera pose, measurement noise, or target motion is introduced in this
  path. **Decision relevance:** memory is not required merely to recover the
  current target or velocity, though it may help sequence actions. **Assumptions:**
  the model geometry and observation function are exact and unchanged at
  export. **Sources:** `robot_learning/scenario/observations.py:27-49`;
  `robot_learning/scenario/environment.py:83-100`;
  `robot_learning/scenario/policy_io.py:7-16`. **Discriminating evidence:**
  reconstruct target position from observations and compare it with mocap
  position.
- **[Reasoned implication]** The IK residuals expose candidate terminal
  postures but do not expose actuator torque, acceleration, contact force,
  joint-limit activation, or hold progress. The observation supports geometric
  regulation while leaving dynamic margin and episode-history state implicit.
  **Decision relevance:** a hold failure cannot be assigned to sensing versus
  dynamics from the observation alone. **Assumptions:** no additional runtime
  diagnostics are supplied to the policy. **Source:**
  `robot_learning/scenario/observations.py:37-49`. **Discriminating evidence:**
  synchronized observations with velocity, control, limit, contact, and hold
  traces.
- **[Reasoned implication]** Success is a coupled sequence: select a feasible
  posture, traverse it within torque and joint constraints, enter while
  sufficiently slow, and remain in the Cartesian ball for 100 samples.
  Minimum distance or first entry alone cannot establish success. **Decision
  relevance:** reach, convergence, and stabilization must be diagnosed as
  separate phases of one episode. **Assumptions:** the official criterion is
  the contract criterion and not a reward surrogate. **Sources:**
  `contracts/scenario.md:16-21`; `robot_learning/scenario/environment.py:134-168`;
  `robot_learning/scenario/evaluation.py:51-105`. **Discriminating evidence:**
  first-entry velocity, hold interruptions, maximum held steps, final distance,
  and episode success.

### Quantities that describe the complete behavior

- **[Reasoned implication]** The physically meaningful record spans target radius
  and angle; `q`, `qdot`, and preferably `qdd`; action and transmitted torque;
  end-effector position and error; IK branch and Jacobian singular values;
  joint-limit and actuator-saturation margins; first-entry time; time in
  tolerance; maximum uninterrupted hold; interruptions; final distance; and
  episode success. These quantities connect morphology, dynamics, sensing,
  control, and outcome. **Decision relevance:** their decomposition can
  distinguish geometric, reach-speed, overshoot, and stabilization failures.
  **Assumptions:** values are sampled with known timing and units. **Sources:**
  `robot_learning/scenario/evaluation.py:51-125`;
  `robot_learning/scenario/environment.py:122-168`. **Discriminating evidence:**
  synchronized trajectory diagnostics rather than reward alone.

## Physical consequences

### Behavior classes

- **[Reasoned implication]** Failures should fall into distinct physical classes:
  path or limit constrained; reachable but too slow for the 500-step horizon;
  first entry with residual velocity and subsequent exit; and stable holds.
  These classes arise from different portions of the same coupled dynamics.
  **Decision relevance:** episode success alone cannot identify the limiting
  mechanism. **Assumptions:** target-conditioned trajectories and hold
  interruptions are recorded. **Sources:** `contracts/robots/two_joint_arm.xml:13-18,30-33`;
  `robot_learning/scenario/environment.py:134-168`;
  `robot_learning/scenario/evaluation.py:90-105`. **Discriminating evidence:**
  constrained IK, first-entry timing/velocity, actuator margins, and complete
  distance traces.

### Branch, angle, and posture effects

- **[Reasoned implication]** The two IK branches permit a policy to trade elbow
  posture against path length, limit margin, and transient inertia. With zero
  gravity and circular target sampling, rotating a target should mainly rotate
  the required shoulder motion, but the reset pose, finite shoulder range, and
  branch choice break exact behavioral equivalence. **Decision relevance:**
  radius-angle and branch-conditioned performance can reveal structural failure
  regions rather than stochastic failures. **Assumptions:** both candidate
  branches are feasible for the target and there are no orientation/contact
  requirements. **Sources:** `contracts/robots/two_joint_arm.xml:2,13-18`;
  `robot_learning/scenario/environment.py:83-97`;
  `robot_learning/scenario/observations.py:29-47`. **Discriminating evidence:**
  branch feasibility, path length, Jacobian condition, and success heatmaps.
- **[Reasoned implication]** Joint-space error is not uniformly Cartesian error:
  `J(q)` maps perturbations with posture-dependent gain and conditioning.
  Consequently, a policy can appear settled in joint coordinates while the
  end effector exits the 1 cm ball, especially where the Cartesian tolerance
  has a small angular margin. **Decision relevance:** Cartesian error and
  Jacobian metrics are required to interpret apparent joint stability.
  **Assumptions:** local Jacobian linearization is valid during hold.
  **Sources:** `contracts/robots/two_joint_arm.xml:12-23`;
  `robot_learning/scenario/environment.py:78-81`. **Discriminating evidence:**
  Jacobian-conditioned joint perturbations and hold interruptions.

### Reach, braking, and stabilization

- **[Reasoned implication]** Holding is likely to be velocity-management limited
  after the target is approached: a fast entry can carry the site across the
  small ball during the next 20 ms action interval, while zero-action motion
  should decay through damping in the ideal free-space model. **Decision
  relevance:** first-entry velocity and braking behavior are more informative
  than minimum distance for explaining hold failure. **Assumptions:** damping
  and inertia dominate unmodeled effects and the sampled evaluator is
  authoritative. **Sources:** `contracts/robots/two_joint_arm.xml:2,13-18`;
  `robot_learning/scenario/environment.py:122-168`. **Discriminating evidence:**
  state/action traces around first entry and every hold interruption.
- **[Reasoned implication]** The official objective is a tail requirement:
  four or more failures in the fixed 200-episode panel misses 98%. A policy
  that improves average distance while retaining a concentrated
  radius-angle failure region may not improve the official result. **Decision
  relevance:** robustness across the distribution matters more than aggregate
  reward or mean error. **Assumptions:** the fixed panel and success count in
  the scenario contract are authoritative. **Source:**
  `contracts/scenario.md:24-31`. **Discriminating evidence:** the protected
  assessment, interpreted alongside non-official stratified diagnostics.

### Training distribution consequence

- **[Reasoned implication]** The baseline recipe does not expose the policy to
  the official inner-radius interval `0.06--0.14 m`; performance there cannot
  be inferred from outer-radius training alone. The mismatch may affect both
  branch geometry and stabilization tolerance. **Decision relevance:** a
  measured gap could be distribution generalization rather than actuator
  authority. **Assumptions:** the baseline training environment remains the
  active recipe and evaluation uses the official distribution. **Sources:**
  `robot_learning/training/environment.py:12-19`;
  `contracts/task_spec.py:6-6`. **Discriminating evidence:** equal-seed,
  radius-stratified evaluation with first-entry and hold diagnostics.

## Unknowns

### Compiled inertia and control authority

- **[Unresolved quantity]** The XML does not explicitly state body masses,
  inertial tensors, geom density, compiled aggregate `M(q)`, actuator
  acceleration authority, or saturation behavior under coupled motion. These
  values are supplied by native MuJoCo compilation and are not established by
  the text of the robot contract. **Decision relevance:** they determine travel
  time, braking distance, overshoot, and whether the 20 ms control interval is
  dynamically adequate. **Assumptions:** native MuJoCo 3.12.0 compilation is
  the complete simulator definition. **Sources:**
  `contracts/robots/two_joint_arm.xml:9-20,30-33`;
  `AGENTS.md` runtime requirements. **Discriminating evidence:** compiled
  `body_mass`, `body_inertia`, actuator transmission/force fields, and
  repeatable single-joint and coupled torque-response/free-decay measurements.

### Exact closed-loop bandwidth

- **[Unresolved quantity]** The action bounds and timestep do not establish the
  learned controller's effective bandwidth, settling time, overshoot, or
  first-entry velocity for each target geometry. **Decision relevance:** the
  campaign may be reach-limited, convergence-limited, or hold-limited, which
  would change the interpretation of otherwise similar failures.
  **Assumptions:** policy behavior is the principal feedback mechanism and the
  policy runtime preserves the declared action mapping. **Sources:**
  `robot_learning/scenario/environment.py:122-168`;
  `robot_learning/scenario/policy_io.py:11-16`;
  `robot_learning/scenario/evaluation.py:90-105`. **Discriminating evidence:**
  first-entry step and velocity, final distance, maximum held steps,
  interruptions, action magnitude, and saturation by target geometry.

### Official hold sampling semantics

- **[Unresolved quantity]** The visible environment checks distance after each
  group of 10 physics steps, whereas the contract describes a complete
  uninterrupted 2-second hold. It is not established from accessible sources
  whether the protected evaluator also rejects excursions between those
  checks. **Decision relevance:** a policy can pass sampled occupancy while
  violating continuous physical containment, changing how development
  diagnostics should be interpreted. **Assumptions:** the visible scenario and
  protected evaluator may differ only at this semantic boundary. **Sources:**
  `contracts/scenario.md:9-14`; `contracts/task_spec.py:8-11`;
  `robot_learning/scenario/environment.py:130-168`. **Discriminating evidence:**
  compare substep distance maxima with protected outcomes for the same frozen
  policy.

### Contact and limit impulses

- **[Unresolved quantity]** The floor and target are explicitly non-colliding,
  but the arm geoms do not declare individual contact masks in the XML. The
  practical occurrence and magnitude of self-collision or joint-limit
  constraint impulses are therefore not established. **Decision relevance:**
  contact impulses would invalidate a purely free-space explanation and could
  create otherwise unexplained velocity changes. **Assumptions:** native
  MuJoCo default collision filtering and hinge-limit semantics apply.
  **Sources:** `contracts/robots/two_joint_arm.xml:6,9-27`;
  `robot_learning/scenario/environment.py:52-57`. **Discriminating evidence:**
  contact pairs, constraint forces, limit activation, and velocity jumps across
  the full target distribution.

### Source of eventual failures

- **[Unresolved quantity]** Before campaign evidence, the relative contribution
  of radius, angle, branch, initial error, residual velocity, actuator
  saturation, and hold semantics to the eventual failure rate is unknown.
  **Decision relevance:** these alternatives imply different causal bottlenecks
  despite the same episode-level failure label. **Assumptions:** a fixed policy
  can be compared on seed-controlled panels with synchronized diagnostics.
  **Sources:** `robot_learning/scenario/environment.py:83-168`;
  `robot_learning/scenario/evaluation.py:90-125`. **Discriminating evidence:**
  paired, seed-controlled trajectories stratified by each listed quantity.

### Distribution and runtime fidelity

- **[Unresolved quantity]** The effect of the baseline radial-distribution
  mismatch on official success is unknown, as is the practical numerical
  observability margin after policy normalization and serialization. Exact
  arithmetic makes the physical observation sufficient, but runtime scaling
  could create a separate failure mechanism. **Decision relevance:** this
  distinguishes generalization or serialization faults from morphology and
  control limitations. **Assumptions:** the exported runtime uses the same
  observation and identity action functions as training. **Sources:**
  `robot_learning/training/environment.py:12-19`;
  `robot_learning/scenario/observations.py:27-49`;
  `robot_learning/scenario/policy_io.py:7-16`. **Discriminating evidence:**
  reconstruct target positions from exported observations, verify action
  identity and normalization, and compare radius-stratified success on equal
  seeds.

### Post-entry behavior

- **[Unresolved quantity]** The behavior between first entry and completed hold
  is not known: it may settle monotonically, oscillate within the ball, or
  repeatedly exit and re-enter. **Decision relevance:** these cases require
  different explanations even when minimum distance is identical, and only
  uninterrupted hold determines success. **Assumptions:** the visible hold
  counter is the relevant episode state and per-step diagnostics are retained.
  **Sources:** `robot_learning/scenario/environment.py:134-168`;
  `robot_learning/scenario/evaluation.py:67-105`. **Discriminating evidence:**
  complete distance, velocity, action, held-step, and interruption traces.
