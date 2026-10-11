## Established facts

### Human-defined task and assessment

- **[Repository fact]** The controlled plant is the human-defined MuJoCo
  two-joint arm. An episode succeeds only if the end effector is within
  `0.01 m` of the target for an uninterrupted `2.0 s`; the official objective
  is at least 196 successes in a fixed 200-episode panel (98%). [Source:
  `contracts/scenario.md` — Official task, Success criterion, Official final
  assessment.]
- **[Repository fact]** Official targets have radius uniformly sampled from
  `0.06 m` to `0.20 m` and angle uniformly sampled over `[-pi, pi]`. The
  scenario implementation samples radius and angle independently and places
  the target in the end-effector's horizontal plane. [Source:
  `contracts/scenario.md` — Official task; `robot_learning/scenario/environment.py`
  — `_sample_target_position`; `contracts/task_spec.py` —
  `TARGET_RADIUS_RANGE`.]
- **[Repository fact]** The official episode horizon is at most 500 control
  steps. The fixed evaluation reports one binary outcome per episode; research
  diagnostics additionally record target geometry, minimum and final distance,
  first reach, maximum held steps, in-tolerance steps, and hold interruptions.
  [Source: `contracts/task_spec.py`; `robot_learning/scenario/evaluation.py` —
  `evaluate_research_model`.]

### Morphology, coordinates, and constraints

- **[Repository fact]** The mechanism is a planar serial 2R chain. The
  shoulder and elbow are revolute joints about the world/body `z` axis, with
  link lengths `l1 = 0.12 m` and `l2 = 0.10 m`; the end-effector site is at
  the forearm tip. [Source: `contracts/robots/two_joint_arm.xml` —
  `upper_arm`, `forearm`, `end_effector`; `contracts/robots/two_joint_arm.py`
  — `UPPER_ARM_LENGTH`, `FOREARM_LENGTH`.]
- **[Repository fact]** Both joint ranges are declared as `[-170, 170]`
  degrees. The arm plane is at `z = 0.02 m`; the target is assigned the
  current end-effector `z`, so the task is planar in the three-dimensional
  distance calculation. [Source: `contracts/robots/two_joint_arm.xml` —
  joint ranges and body positions; `robot_learning/scenario/environment.py`
  — `_sample_target_position`.]
- **[Repository fact]** The visual base is a cylinder and the links are
  capsules. The target is a mocap sphere with collisions disabled. The plane
  and base also have collisions disabled; the link capsules do not declare
  collision masks in the XML. [Source:
  `contracts/robots/two_joint_arm.xml` — `geom` declarations.]
- **[Repository fact]** There are two actuated degrees of freedom and no
  translational base, wrist, gripper, object, or contact-maintenance
  degree of freedom. [Source: `contracts/robots/two_joint_arm.xml` —
  body/joint/actuator structure.]

### Actuation, simulator, and reset

- **[Repository fact]** Each joint has a direct MuJoCo motor with
  `ctrlrange = [-1, 1]` and `gear = 5`. The environment clips the policy
  action to that range, writes it directly to `data.ctrl`, and does not add a
  position or velocity servo. [Source: `contracts/robots/two_joint_arm.xml` —
  `<motor>`; `robot_learning/scenario/environment.py` — `step`;
  `robot_learning/scenario/policy_io.py` — `physical_action`.]
- **[Repository fact]** The MuJoCo integration timestep is `0.002 s`. One
  environment action is held while ten `mj_step` calls execute, giving a
  `0.020 s` control interval. The required hold is therefore
  `round(2.0 / 0.020) = 100` consecutive control observations. [Source:
  `contracts/robots/two_joint_arm.xml` — `<option>`; `contracts/task_spec.py`
  — `FRAME_SKIP`, `HOLD_SECONDS`; `robot_learning/scenario/environment.py` —
  `hold_steps_required`, `step`.]
- **[Repository fact]** Gravity is explicitly zero. Each joint declares
  damping `0.5` and armature `0.01`; no link mass, inertia, density,
  integrator, or solver option is explicitly written in the robot XML.
  [Source: `contracts/robots/two_joint_arm.xml` — `<option>`, joint
  attributes, and absent inertial declarations.]
- **[Repository fact]** Reset calls `mj_resetData`, sets both joint positions
  and velocities to zero, forwards the model, then samples a stationary
  target. Thus the initial arm is fully extended along positive `x` at rest,
  with end effector position `(0.22, 0, 0.02)`. [Source:
  `robot_learning/scenario/environment.py` — `reset`, `_sample_target_position`;
  `contracts/robots/two_joint_arm.py` — link lengths.]

### Observation and policy interface

- **[Repository fact]** The physical observation has 11 entries: two joint
  positions, two joint velocities, the three-dimensional end-effector-minus-
  target vector, and four wrapped joint errors to the analytic open and
  folded inverse-kinematic solutions. [Source:
  `robot_learning/scenario/observations.py` — `reach_observation`,
  `OBSERVATION_SIZE`.]
- **[Repository fact]** The observation is computed from exact simulator state;
  the source specifies no sensor noise, quantization, dropout, latency, or
  target motion. A saved runtime may additionally normalize and clip the
  observation before policy prediction, but that transformation is a policy
  artifact rather than a new physical sensor. [Source:
  `robot_learning/scenario/observations.py`; `contracts/policy_runtime.py` —
  `PolicyRuntime`; `robot_learning/training/normalization.py`.]
- **[Repository fact]** The action returned by the policy is the two-component
  physical command after the runtime transformation; the current runtime
  transformation is the identity. Recurrent policy state, if a policy uses
  it, is reset at the start of each episode. [Source:
  `robot_learning/scenario/policy_io.py`; `contracts/policy_runtime.py` —
  `PolicyRuntime.reset`, `predict`.]

### Task mechanics and outcome semantics

- **[Repository fact]** Distance is the Euclidean distance from the end-
  effector site to the mocap target. At each control step, distance at or below
  `0.01 m` increments the hold counter; any distance above it resets that
  counter to zero. Success is termination at 100 held steps, not merely first
  entry into the tolerance ball. [Source:
  `robot_learning/scenario/environment.py` — `_distance_to_target`, `step`;
  `contracts/task_spec.py` — `SUCCESS_THRESHOLD`, `HOLD_SECONDS`.]
- **[Repository fact]** The current reward contains progress, closeness,
  hold-progress, optional outside-band, completion, and action-cost terms.
  Reward is research-owned shaping and does not alter the binary success
  contract. The baseline training target radii are `0.14` to `0.20 m`, a
  narrower exposure than the official `0.06` to `0.20 m` range. [Source:
  `robot_learning/training/reward.py`; `robot_learning/training/environment.py`
  — `TRAINING_TARGET_RADIUS_RANGE`; `contracts/task_spec.py`.]

## Physical consequences

### Kinematic reachability and inverse-kinematic alternatives

- **[Reasoned implication]** With shoulder angle `q1` and elbow angle `q2`,
  the end-effector position is
  `p(q) = (l1 cos(q1) + l2 cos(q1+q2),
  l1 sin(q1) + l2 sin(q1+q2), 0.02)`. The unconstrained radial workspace is
  the annulus `[|l1-l2|, l1+l2] = [0.02, 0.22] m`, which contains the whole
  official `[0.06, 0.20] m` radial interval.
  **Decision relevance:** This separates geometric impossibility from
  controller or dynamics failure; it supports treating official targets as
  reachable rather than learning around unreachable cases.
  **Assumptions:** The XML lengths and planar joint axes are the complete
  kinematic chain, and joint limits are the only kinematic limits.
  **Sources:** `contracts/robots/two_joint_arm.xml`; `contracts/robots/two_joint_arm.py`.
  **Discriminating evidence:** Compute forward kinematics for the sampled
  target and solve the bounded IK problem; a bounded solution establishes
  reachability for that target, while no bounded solution identifies a
  geometric failure.

- **[Reasoned implication]** For every official target radius, the two
  nominal branches are
  `q2 = +/- acos((r^2-l1^2-l2^2)/(2 l1 l2))`, with `|q2|` approximately
  `49.5` to `150.4` degrees over `r = 0.20` to `0.06 m`; the corresponding
  shoulder solutions are `q1 = theta - atan2(l2 sin(q2),
  l1+l2 cos(q2))`. Both branches are distinct and fit the declared
  `170`-degree joint limits over this official annulus. The branch choice is
  therefore a genuine trajectory choice, not a missing task capability.
  **Decision relevance:** A policy may need branch-invariant targeting or
  branch selection that avoids an inefficient or unstable path; success
  should not be interpreted as evidence for one unique posture.
  **Assumptions:** Ideal planar FK and the declared joint ranges; no
  self-collision removes a branch.
  **Sources:** `robot_learning/scenario/observations.py` — open/folded IK;
  `contracts/robots/two_joint_arm.xml`.
  **Discriminating evidence:** Record final joint angles by target angle and
  radius and compare them with both bounded IK solutions; branch occupancy and
  branch-specific hold failures distinguish selection effects.

### Initial state, singularity, and approach geometry

- **[Reasoned implication]** The reset pose `q = (0,0)` is the fully extended
  radial configuration and a kinematic singularity because
  `det(J) = l1*l2*sin(q2) = 0`. Tangential end-effector motion has no
  first-order elbow contribution at reset, although torque can still create
  elbow acceleration and leave the singularity.
  **Decision relevance:** Early behavior can be dominated by escape from the
  singular pose, so a slow or curved initial approach is not evidence that
  the target is unreachable.
  **Assumptions:** The planar Jacobian derived from the two link lengths
  describes the site position and the initial velocities are exactly zero.
  **Sources:** `robot_learning/scenario/environment.py` — reset;
  `contracts/robots/two_joint_arm.xml` — link hierarchy.
  **Discriminating evidence:** Compare early elbow motion, Cartesian
  tangential velocity, and distance reduction for targets at different
  angles; a rank-deficient initial Cartesian response supports this mechanism.

- **[Reasoned implication]** Initial distance is target-dependent: the arm
  starts at radius `0.22 m`, so it is approximately `0.02 m` from a target
  on the positive radial ray and up to `0.42 m` from the opposite ray.
  The target is fixed after reset, so the controller must solve a transient
  reach followed by a stationary regulation problem.
  **Decision relevance:** First-reach time and initial-distance stratification
  can distinguish exploration/trajectory limits from hold regulation limits.
  **Assumptions:** Target sampling is the implementation in
  `_sample_target_position` and the target mocap body remains fixed.
  **Sources:** `robot_learning/scenario/environment.py` — `reset`,
  `_sample_target_position`; `contracts/scenario.md`.
  **Discriminating evidence:** Plot distance and first-reach step against
  target radius and angle, not only pooled success.

### Actuation, dynamics, and control authority

- **[Reasoned implication]** Under standard MuJoCo motor semantics, a clipped
  command `u_i in [-1,1]` produces nominal joint actuation
  `tau_i = 5 u_i`, subject to the simulator's joint-limit and other
  constraint forces. The command is zero-order-held for `20 ms`; it is not a
  desired joint position.
  **Decision relevance:** The policy must learn torque timing, braking, and
  coordinated shoulder/elbow motion; changing a policy architecture cannot
  remove the plant's action-to-motion delay or saturation.
  **Assumptions:** The compiled motor transmission uses the standard
  `gear * ctrl` mapping and no additional runtime action transform is present.
  **Sources:** `contracts/robots/two_joint_arm.xml` — motors;
  `robot_learning/scenario/environment.py` — clipping and frame skip;
  `robot_learning/scenario/policy_io.py`.
  **Discriminating evidence:** Query compiled actuator gear/force fields and
  measure joint acceleration under isolated positive and negative commands.

- **[Reasoned implication]** The state evolution has the qualitative form
  `M(q) qddot + c(q,qdot) + d qdot + tau_limit =
  tau_act`, with gravity absent, `d = 0.5` damping, and `0.01` armature
  contributing to effective inertia. The absolute acceleration, settling time,
  overshoot, and braking distance depend on the compiled `M(q)` and numerical
  integration details, which are not fully declared in the XML.
  **Decision relevance:** These quantities determine whether a policy can
  enter and remain inside a 1 cm ball within 500 steps and whether a
  high-gain-looking policy is actually underdamped.
  **Assumptions:** MuJoCo's compiled model and solver are the authoritative
  dynamics; contacts are absent or negligible during the tested motion.
  **Sources:** `contracts/robots/two_joint_arm.xml`; `robot_learning/scenario/environment.py`
  — `mj_step`.
  **Discriminating evidence:** Inspect compiled mass/inertia/solver fields and
  measure free decay, step response, reversal braking, and repeatability.

### Reach, convergence, and uninterrupted stabilization

- **[Reasoned implication]** Reaching, trajectory control, and stabilization
  are coupled but distinct phases. Reaching requires enough integrated torque
  to change `q`; trajectory control must select a feasible IK branch and
  dissipate momentum; convergence requires Cartesian error below `1 cm`;
  stabilization requires keeping every subsequent sampled state inside the
  ball for 100 control intervals. A small endpoint error at one step is
  insufficient.
  **Decision relevance:** Aggregate success alone cannot identify whether the
  first campaign bottleneck is arrival, convergence, or hold regulation.
  **Assumptions:** The evaluation diagnostics faithfully expose the
  environment's hold counter and the target remains fixed.
  **Sources:** `robot_learning/scenario/environment.py` — `step`;
  `robot_learning/scenario/evaluation.py` — diagnostics;
  `contracts/scenario.md`.
  **Discriminating evidence:** Use first-reach step, maximum held steps,
  in-tolerance steps, interruption count, final distance, joint velocities,
  and action magnitude over the complete episode.

- **[Reasoned implication]** With zero gravity and no target contact force, an
  exactly stationary end effector at the target does not need a static
  gravity-compensation torque. However, residual joint velocity, numerical
  error, damping, and coordinated joint motion can carry the endpoint outside
  the tolerance ball; the 100-step hold is therefore a dynamic regulation
  requirement rather than a static pose test.
  **Decision relevance:** A policy that reaches accurately but crosses the
  boundary during settling is a hold-control failure, and action cost or
  low-motion behavior should be interpreted in that context.
  **Assumptions:** No unmodeled disturbance or contact force acts on the arm
  and the zero-gravity XML is authoritative.
  **Sources:** `contracts/robots/two_joint_arm.xml` — gravity;
  `robot_learning/scenario/environment.py` — hold update;
  `robot_learning/training/reward.py`.
  **Discriminating evidence:** Examine endpoint velocity, signed distance to
  the 1 cm boundary, and action/torque during the full hold; repeated exits
  with nonzero velocity support dynamic overshoot rather than reach failure.

### Observation, control, and outcome

- **[Reasoned implication]** Although the target's absolute coordinates are
  not a separate observation field, they are reconstructible in the ideal
  model: current `q` gives the end-effector position and the observed
  end-effector-minus-target vector gives the target position. Joint state and
  the analytic branch errors also expose the local posture relative to both
  IK alternatives. This is an exactly observed, model-informed control
  problem, not a vision or target-localization problem.
  **Decision relevance:** Failure should first be attributed to policy mapping,
  dynamics, or regulation rather than target observability, unless runtime
  normalization or recurrent state loses information.
  **Assumptions:** The policy receives the uncorrupted 11-vector or a
  lossless enough saved normalization transform and knows the fixed kinematic
  constants through its learned mapping.
  **Sources:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/policy_io.py`; `robot_learning/training/normalization.py`.
  **Discriminating evidence:** Reconstruct target coordinates from each
  observation and compare them with `data.mocap_pos`; inspect normalization
  ranges and clipped components in the executed runtime.

- **[Reasoned implication]** The closed loop is
  `observation(q,qdot,target) -> action(u) -> ten simulator substeps ->
  distance/hold update -> next observation`. The outcome depends on the whole
  transient and not just on the final observation, because an intervening
  out-of-tolerance sample resets the hold counter.
  **Decision relevance:** Training metrics or single-pose accuracy that omit
  temporal continuity are incomplete proxies for the official objective.
  **Assumptions:** The environment implementation is the evaluation semantics
  and no wrapper changes action timing or termination.
  **Sources:** `robot_learning/scenario/environment.py`; `contracts/scenario.md`.
  **Discriminating evidence:** Replay complete trajectories and verify that
  every successful episode contains a contiguous 100-step in-tolerance run.

### Failure classes and scientifically meaningful quantities

- **[Reasoned implication]** The physically distinct failure classes are:
  geometric/limit violation; insufficient or mistimed torque; poor
  branch/trajectory selection; overshoot or slow convergence; and hold
  interruption after arrival. The official geometry removes exact
  unreachable-target failure as the expected dominant class, but it does not
  remove the other four.
  **Decision relevance:** Each class implies a different research direction,
  so pooled success should not be used to infer a mechanism.
  **Assumptions:** Bounded IK remains feasible for the official target range
  and the compiled model has no unexpected obstructing contacts.
  **Sources:** `contracts/scenario.md`; `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/evaluation.py`.
  **Discriminating evidence:** Stratify outcomes by target radius/angle and
  inspect joint limits, first reach, minimum distance, velocity, and hold
  interruptions in the same episode records.

- **[Reasoned implication]** The most meaningful episode-level physical
  quantities are target radius/angle, initial and time-resolved Cartesian
  error, minimum/final error, first-reach time, continuous in-tolerance run
  lengths, interruption count, joint positions/velocities, commands/torques,
  and (when compiled dynamics are available) acceleration, kinetic energy,
  damping loss, and actuator work. These quantities cover geometry, motion,
  convergence, and stabilization across the complete behavior.
  **Decision relevance:** They provide mechanism evidence for deciding whether
  a change improves the human objective or only a reward proxy.
  **Assumptions:** The relevant state and action traces can be recorded without
  changing the policy-runtime semantics.
  **Sources:** `robot_learning/scenario/evaluation.py`;
  `robot_learning/scenario/environment.py`; `contracts/robots/two_joint_arm.xml`.
  **Discriminating evidence:** Preserve per-control-step traces for matched
  target seeds and compare complete trajectories, not only episode totals.

### Training exposure versus official task

- **[Reasoned implication]** The current baseline trains on radii
  `0.14`-`0.20 m` but is evaluated on `0.06`-`0.20 m`. The unexposed inner
  targets have different IK configurations and may have different approach
  and damping behavior, even though they are kinematically reachable.
  **Decision relevance:** A high baseline training return cannot establish
  98% official success; the first campaign interpretation must distinguish
  exposure/generalization effects from actuator or hold-control limits.
  **Assumptions:** The baseline training environment and official evaluation
  environment are the environments used for the compared policy artifacts.
  **Sources:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`; `contracts/task_spec.py`.
  **Discriminating evidence:** Evaluate matched policies by radius bands,
  especially `0.06`-`0.14 m`, with hold diagnostics and the same physical
  semantics as official evaluation.

## Unknowns

### Compiled inertial and numerical dynamics

- **[Unresolved quantity]** The source does not state the compiled link
  masses, centers of mass, full inertias, default geom density, integrator,
  solver tolerances, or iteration settings. MuJoCo will compile a definite
  model, but its numerical values cannot be inferred reliably from the XML
  text alone.
  **Decision relevance:** This can change acceleration, overshoot, settling
  time, and therefore whether the first effort should target controller
  timing, action scaling, or policy learning.
  **Assumptions:** The missing defaults are materially different across
  plausible compiled configurations; if the installed MuJoCo defaults are
  treated as fixed and known, this unknown narrows to a verification task.
  **Sources:** `contracts/robots/two_joint_arm.xml` — absent inertial and
  solver declarations; `AGENTS.md` — locked MuJoCo version.
  **Discriminating evidence:** Read `MjModel` mass/inertia and option fields
  from the exact installed MuJoCo build, then compare measured and simulated
  free-decay and torque-step responses.

### Contact and self-collision behavior

- **[Unresolved quantity]** Plane, base, and target collision participation
  is explicitly disabled, but the link capsules omit collision masks. The
  effective compiled self-collision pairs and whether they intervene in
  folded IK trajectories are not established by the contract text.
  **Decision relevance:** Unexpected contact could create a discrete failure
  class and make one nominal IK branch dynamically unavailable.
  **Assumptions:** Folded trajectories approach the capsule geometries closely
  enough for contact filtering to matter.
  **Sources:** `contracts/robots/two_joint_arm.xml` — link, base, plane, and
  target geoms.
  **Discriminating evidence:** Inspect compiled contact pairs and run
  collision/contact-count traces through both IK branches over the official
  target panel.

### Effective policy input transformation

- **[Unresolved quantity]** The physical observation definition is known, but
  each learned artifact may carry its own normalization statistics and
  optional recurrent state. It is unknown before a policy exists whether
  normalization clips informative components or whether recurrence is needed
  to exploit the fully observed state.
  **Decision relevance:** This can turn an apparently physical failure into an
  input-distribution or memory failure and can affect transfer across target
  radii.
  **Assumptions:** The candidate uses the saved runtime contract rather than
  current source code substituted at evaluation.
  **Sources:** `contracts/policy_runtime.py`;
  `robot_learning/training/normalization.py`;
  `robot_learning/scenario/observations.py`.
  **Discriminating evidence:** Inspect the candidate's saved runtime and
  normalization statistics, test observation reconstruction before and after
  normalization, and compare recurrent versus reset-state rollouts.

### Actual behavior under the official distribution

- **[Unresolved quantity]** No pre-campaign evidence establishes the policy's
  success rate, target-angle/radius dependence, first-reach time, or ability
  to sustain the 100-step hold. The model establishes mechanisms and
  constraints, not performance.
  **Decision relevance:** This is the central unknown governing whether the
  first work should diagnose failures, develop a policy, or compare candidates.
  **Assumptions:** Development panels are interpreted as evidence about the
  same task semantics but cannot replace the protected 200-episode assessment.
  **Sources:** `contracts/scenario.md`; `robot_learning/scenario/evaluation.py`;
  `contracts/instruments.md` — research evaluation semantics.
  **Discriminating evidence:** Completed evaluation panels with per-episode
  diagnostics, followed only when justified by the official fixed assessment.

## Decision-relevant synthesis

### Official targets are reachable but have two posture solutions

- **[Reasoned implication] Decision relevance:** The first campaign should
  interpret failures as control/dynamics or hold failures unless bounded IK
  actually fails; branch selection is a real alternative, not a unique-pose
  requirement.
- **[Reasoned implication] Assumptions:** The planar FK, link lengths, and
  declared joint limits are complete and self-collision does not remove a
  branch.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `robot_learning/scenario/observations.py`.
- **[Reasoned implication] Discriminating evidence:** Bounded IK feasibility
  and final-branch occupancy stratified by target radius and angle.

### The task starts at a singular, fully extended rest pose

- **[Reasoned implication] Decision relevance:** Early reach behavior must be
  separated from steady-state hold behavior; initial singular escape and
  approach timing may dominate the first diagnosis.
- **[Reasoned implication] Assumptions:** Reset exactly sets `qpos=qvel=0`
  and the target is stationary in the same plane.
- **[Reasoned implication] Source references:** `robot_learning/scenario/environment.py`
  — `reset`; `contracts/robots/two_joint_arm.xml`.
- **[Reasoned implication] Discriminating evidence:** Time-resolved Cartesian
  and joint traces, especially tangential velocity and first-reach step by
  target angle.

### Torque control and compiled inertia set the reachable behavior in time

- **[Reasoned implication] Decision relevance:** The 5:1 motor authority,
  20 ms action hold, damping, armature, and unverified compiled inertia may
  determine whether learning or control refinement can meet the 1 cm/2 s
  requirement.
- **[Reasoned implication] Assumptions:** Standard MuJoCo motor semantics
  apply and omitted compiled dynamics are not already verified.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md`.
- **[Unresolved quantity] Discriminating evidence:** Exact `MjModel` dynamics
  fields plus isolated torque-step, reversal, and free-decay measurements.

### Success is a sustained regulation event, not a reach event

- **[Reasoned implication] Decision relevance:** The decisive behavior is a
  contiguous 100-step in-tolerance run; first entry or low reward distance
  is not sufficient evidence of progress toward 98% episode success.
- **[Reasoned implication] Assumptions:** The environment's counter-reset and
  termination semantics are authoritative for development interpretation.
- **[Reasoned implication] Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.
- **[Reasoned implication] Discriminating evidence:** Complete hold traces
  containing distance, endpoint velocity, interruptions, maximum held steps,
  and final outcome for every episode.

### Baseline training does not cover the full radial task

- **[Reasoned implication] Decision relevance:** Any initial candidate must be
  judged separately on the official inner-radius band; training success on
  `0.14`-`0.20 m` cannot establish the 98% objective.
- **[Reasoned implication] Assumptions:** The current baseline exposure is
  retained for the candidate being interpreted and evaluation semantics are
  unchanged.
- **[Reasoned implication] Source references:** `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`; `contracts/task_spec.py`.
- **[Unresolved quantity] Discriminating evidence:** Radius-stratified
  evaluation diagnostics, with the `0.06`-`0.14 m` band explicitly inspected
  rather than pooled into the official percentage.
