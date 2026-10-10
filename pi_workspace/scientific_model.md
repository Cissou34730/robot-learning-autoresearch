## Established facts

### System boundary and morphology

- **[Repository fact]** The robot is a fixed-base, planar two-joint serial arm. The
  shoulder and elbow are hinge joints about the world z axis; the upper arm is
  0.12 m long and the forearm is 0.10 m long. The end-effector site is at the
  forearm tip. There are two actuated generalized coordinates, with no base
  translation or rotation degree of freedom. [Source:
  `contracts/robots/two_joint_arm.xml:9-23`;
  `contracts/robots/two_joint_arm.py:5-7`]

- **[Repository fact]** The arm plane is z = 0.02 m. The base is fixed at the
  world origin, and the target is a kinematic mocap sphere. The target is
  deliberately placed at the end-effector plane, so the task distance is
  effectively planar even though it is computed as a three-dimensional norm.
  The plane, base, and target visual geoms have collision disabled; the arm link
  geoms do not state collision masks explicitly. [Source:
  `contracts/robots/two_joint_arm.xml:5-7,9-27`;
  `robot_learning/scenario/environment.py:78-97`]

- **[Repository fact]** Each joint declares a range of -170 to 170 degrees.
  Each joint declares damping 0.5 and armature 0.01. [Source:
  `contracts/robots/two_joint_arm.xml:12-19`]

### Kinematics and task geometry

- **[Repository fact]** With shoulder angle \(q_1\) and relative elbow angle
  \(q_2\), the end-effector position is
  \(x=L_1\cos q_1+L_2\cos(q_1+q_2)\),
  \(y=L_1\sin q_1+L_2\sin(q_1+q_2)\), z = 0.02, where
  \(L_1=0.12\) m and \(L_2=0.10\) m. [Source:
  `contracts/robots/two_joint_arm.py:5-7`;
  `contracts/robots/two_joint_arm.xml:12-20`]

- **[Repository fact]** An official target has independently uniform radius
  \(r\in[0.06,0.20]\) m and angle `theta` in `[-pi,pi]`. The target is static
  during an episode. The implementation samples those values and sets target z
  to the current end-effector z. [Source:
  `contracts/scenario.md:7-14`;
  `contracts/task_spec.py:6`;
  `robot_learning/scenario/environment.py:83-97`]

- **[Repository fact]** The initial physical state is
  \(q=(0,0)\), \(\dot q=(0,0)\). The initial end effector is at (0.22, 0, 0.02)
  m. The target is sampled after this reset and is therefore at least 0.02 m
  away initially in the closest possible target direction. [Source:
  `robot_learning/scenario/environment.py:102-120`;
  `contracts/robots/two_joint_arm.py:5-7`]

- **[Repository fact]** Success is evaluated after each control step. A step is
  in tolerance when end-effector/target distance is at most 0.01 m. The
  in-tolerance counter increments on such a step and resets to zero on the
  first out-of-tolerance step. Success requires 100 consecutive in-tolerance
  control steps, and an episode is truncated at 500 control steps. [Source:
  `contracts/scenario.md:9-14,16-27`;
  `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/environment.py:134-168`]

### Actuation, timing, and simulator

- **[Repository fact]** The policy action is a two-vector in [-1, 1]. The
  scenario action mapping is the identity, after which the environment clips
  the action and writes it directly to `data.ctrl`. Each motor has gear 5 and
  nominal control range [-1, 1]. Thus the command is a bounded joint-motor
  command with a nominal transmission scale of 5, rather than a Cartesian
  position or velocity command. [Source:
  `robot_learning/scenario/policy_io.py:11-16`;
  `robot_learning/scenario/environment.py:122-133`;
  `contracts/robots/two_joint_arm.xml:30-33`]

- **[Repository fact]** MuJoCo integrates with a 0.002 s internal timestep.
  Ten internal steps are executed per policy action, giving a 0.020 s control
  interval and 50 control decisions per second. The two-second hold therefore
  corresponds to 100 post-integration checks. [Source:
  `contracts/robots/two_joint_arm.xml:2`;
  `contracts/task_spec.py:7-11`;
  `robot_learning/scenario/environment.py:56-57,130-133`]

- **[Repository fact]** Gravity is zero. Joint damping and armature are explicit,
  while no explicit `<inertial>` elements, geom densities, actuator dynamics,
  friction losses, or solver parameters appear in the robot XML. [Source:
  `contracts/robots/two_joint_arm.xml:2,12-19,30-33`]

- **[Repository fact]** The target is mocap-controlled and has no target actuator
  or task contact semantics. The success distance is geometric, not a force,
  grasp, or collision condition. [Source:
  `contracts/robots/two_joint_arm.xml:25-27`;
  `robot_learning/scenario/environment.py:75-81,134-168`]

### Sensing and policy interface

- **[Repository fact]** The physical observation has 11 entries: two joint
  positions, two joint velocities, the three-component end-effector-to-target
  displacement, and four wrapped angular residuals to the two inverse-kinematic
  elbow branches. The branch residuals are computed from the target x-y
  coordinates and the known link lengths. [Source:
  `robot_learning/scenario/observations.py:11-49`]

- **[Repository fact]** No actuator force, acceleration, contact force, target
  velocity, elapsed time, held-step count, prior action, or simulator solver
  state is included. The action is not transformed into a Cartesian command.
  Training may normalize observations for the learned model, but that
  normalization is a policy-runtime transform rather than an additional physical
  sensor. [Source:
  `robot_learning/scenario/observations.py:36-49`;
  `robot_learning/scenario/policy_io.py:7-16`;
  `contracts/policy_runtime.py:162-177`]

- **[Repository fact]** Joint positions plus the displacement vector are enough
  in principle to reconstruct the target position from the known forward
  kinematics. The four residuals expose both principal inverse-kinematic
  branches, but do not constitute a branch selection made by the environment.
  [Source: `robot_learning/scenario/observations.py:27-47`]

### Outcome and learning signal

- **[Repository fact]** The task outcome is the uninterrupted hold, not reward
  accumulation and not generic Gymnasium termination. The research evaluator
  records success, first reach step, minimum and final distance, maximum held
  steps, in-tolerance steps, hold interruptions, and target radius/angle.
  [Source: `robot_learning/scenario/environment.py:157-168`;
  `robot_learning/scenario/evaluation.py:51-125`]

- **[Repository fact]** The training reward combines distance progress, a
  closeness potential, hold-progress potential, a small outside-band penalty
  after a hold interruption, a hold-complete bonus, and action-squared cost.
  The configured hold-exit forfeiture is zero. These terms shape learning but
  do not alter the binary success rule. [Source:
  `robot_learning/training/reward.py:16-25,47-108`;
  `robot_learning/scenario/environment.py:145-154`]

- **[Repository fact]** The official assessment uses one frozen policy on 200
  episodes and requires at least 196 successes for the 98% objective. The
  development panel is distinct from that official panel. [Source:
  `contracts/scenario.md:23-32`;
  `robot_learning/training/research_config.py:22-30`]

## Physical consequences

### Reachability and alternative configurations

- **[Reasoned implication]** Ignoring whether the XML ranges are actively
  enforced by the compiler, the planar workspace has radial reach from
  \(|L_1-L_2|=0.02\) m to \(L_1+L_2=0.22\) m. The official annulus 0.06--0.20 m
  is therefore inside the nominal workspace. For a target \((r,\theta)\), the
  two principal solutions are
  \(q_2=\pm\arccos((r^2-L_1^2-L_2^2)/(2L_1L_2))\) and
  \(q_1=\theta-\operatorname{atan2}(L_2\sin q_2,L_1+L_2\cos q_2)\).
  Over the official radial interval both branches have a shoulder angle within
  the declared +/-170 degree range after angle wrapping, so the target
  distribution has two geometrically valid elbow configurations. [Assumptions:
  standard planar forward kinematics, the stated link lengths, and active
  angles interpreted modulo 2*pi. Sources:
  `contracts/robots/two_joint_arm.py:5-7`;
  `contracts/robots/two_joint_arm.xml:12-19`;
  `robot_learning/scenario/observations.py:18-35`. Discriminating evidence:
  compiled joint-limit flags and branch-labeled terminal configurations.]

- **[Reasoned implication]** The two branches are dynamically distinct even when
  they are equally reachable: they require different joint excursions,
  velocities, and final configurations. A policy can solve the task by
  selecting one branch consistently, switching branches, or exploiting
  trajectory-dependent behavior; branch switching near a singular or
  high-speed configuration is likely to threaten the hold. This changes whether
  early research should treat branch selection as a meaningful behavioral
  variable. [Assumptions: both branches remain within the effective limits and
  the controller can observe the residuals. Sources:
  `robot_learning/scenario/observations.py:18-47`;
  `robot_learning/scenario/environment.py:122-143`. Discriminating evidence:
  branch-wise joint trajectories, action norms, and hold success.]

### Conditioning, reaching, and convergence

- **[Reasoned implication]** The planar Jacobian has determinant
  \(L_1L_2\sin q_2\). The reset state \(q_2=0\) is fully extended and
  kinematically singular: a first-order joint change produces tangential
  motion but no first-order inward radial motion. Since every target is inside
  the 0.22 m initial reach, the controller must first bend away from this
  singular configuration before it can efficiently shape the radial error.
  Targets near the minimum radius require a more folded final elbow and can
  have different conditioning and branch costs from targets near 0.20 m.
  **Decision relevance:** this can change whether startup emphasizes escaping
  the initial singularity, geometric conditioning, or target-stratified
  exploration. [Assumptions: the stated planar kinematics and local Jacobian analysis.
  Sources: `contracts/robots/two_joint_arm.py:5-7`;
  `robot_learning/scenario/environment.py:109-118`. Discriminating evidence:
  time to leave q2=0, Jacobian conditioning along trajectories, and
  radius-stratified first-reach time.]

- **[Reasoned implication]** Reaching and holding are coupled rather than
  separable. Residual position error, joint velocity, and actuator saturation at
  the first entry into the 1 cm disk determine whether the end effector
  converges to and remains in the disk. A fast approach can reduce first-reach
  time while increasing overshoot; a low-velocity approach can improve hold
  margin while consuming the 500-step horizon. The relevant controller
  objective is therefore a stable set entry, not merely a minimum-distance
  waypoint. **Decision relevance:** this can change whether learning is shaped
  primarily by reach speed, terminal velocity, or hold robustness.
  [Assumptions: finite damping, bounded torque, and the endpoint
  success checks described by the environment. Sources:
  `contracts/robots/two_joint_arm.xml:12-19,30-33`;
  `robot_learning/scenario/environment.py:130-159`. Discriminating evidence:
  first-reach step paired with terminal velocity, minimum distance, and
  interruption count.]

- **[Reasoned implication]** The 1 cm task-space tolerance maps to a
  configuration-dependent joint-space tolerance through the Jacobian. Near a
  poorly conditioned configuration, small joint motion can cause a large
  Cartesian displacement in one direction, so stabilization authority is
  anisotropic. Distance alone cannot distinguish a quiet, robust hold from a
  high-velocity crossing that happens to be sampled inside the disk.
  **Decision relevance:** this can change whether a controller should target a
  central margin or merely the tolerance boundary. [Assumptions:
  local linearization is valid over the final motion and the target is static.
  Sources: `contracts/task_spec.py:10-11`;
  `robot_learning/scenario/environment.py:134-143`. Discriminating evidence:
  joint velocity, signed error, and distance at every hold sample.]

### Dynamics and control authority

- **[Reasoned implication]** With zero gravity and no task contact, the main
  physical restoring and dissipative effects are configuration-dependent
  articulated inertia and explicit viscous joint damping. The armature adds
  reflected inertia at each actuated joint. A bounded motor command must overcome
  these inertial and damping terms to change velocity, then must apply
  counter-torque to remove velocity and hold position. The same command has
  different end-effector effects at different configurations because the
  Jacobian maps joint velocity and torque authority into task space. [Assumptions:
  standard MuJoCo motor and joint-dynamics semantics. Sources:
  `contracts/robots/two_joint_arm.xml:2,12-19,30-33`;
  `robot_learning/scenario/environment.py:130-133`. **Decision relevance:**
  this can change action scaling, exploration limits, and whether an explicit
  braking or stabilization mechanism is needed. Discriminating evidence:
  compiled inertias and bounded-action acceleration and settling responses.]

- **[Reasoned implication]** The 20 ms zero-order-held action interval is long
  relative to the 2 ms integrator step but short relative to the two-second
  task. Stabilization is consequently a sampled-data control problem: the
  policy can only update the command at 50 Hz, while ten internal integrations
  occur between decisions. The environment tests the distance only after those
  ten integrations, so the recorded hold is uninterrupted at control-sample
  resolution, not a separately instrumented continuous-time check within each
  frame-skip block. **Decision relevance:** this can change whether policy
  design prioritizes within-step margin, lower action bandwidth, or only
  post-step distance. [Assumptions: the shared scenario environment is the
  measurement semantics for the behavior being analyzed. Sources:
  `contracts/robots/two_joint_arm.xml:2`;
  `robot_learning/scenario/environment.py:130-143`;
  `contracts/scenario.md:9-14`. Discriminating evidence: internal-step
  distance traces compared with the post-control-step hold counter.]

- **[Reasoned implication]** Action cost creates a weak preference for smaller
  commands, while the success criterion still permits any action sequence that
  completes the hold. The learned reward may therefore favor smooth or
  low-effort trajectories, but reward comparisons cannot be treated as physical
  evidence of success robustness without the distance and interruption
  diagnostics. **Decision relevance:** this can change whether reward
  modifications are considered before observation or controller changes.
  [Assumptions: the current reward remains the training signal.
  Sources: `robot_learning/training/reward.py:57-96`;
  `robot_learning/scenario/evaluation.py:111-125`. Discriminating evidence:
  paired reward-component and binary-success trajectories.]

### Observability and task-state memory

- **[Reasoned implication]** The physical plant state relevant to deterministic
  future motion—joint position, joint velocity, and static target position—is
  largely observable from the 11-value observation. However, the task automaton
  state, specifically the current consecutive in-tolerance count, is not
  observed. Two physically identical observations can have different success
  futures if one follows 99 valid samples and the other follows an interruption.
  This makes hold completion a history-dependent control problem even though
  the mechanical plant is observed sufficiently for ordinary state feedback.
  **Decision relevance:** this can change whether a feedforward policy is
  adequate or temporal memory is required for reliable completion.
  [Assumptions: no hidden actuator state beyond the XML model and the policy
  receives only the declared observation. Sources:
  `robot_learning/scenario/observations.py:36-49`;
  `robot_learning/scenario/environment.py:136-159`. Discriminating evidence:
  matched observations with different prior hold histories and their
  subsequent completion rates.]

- **[Reasoned implication]** The four branch residuals make the two principal
  geometric solutions explicit, but the observation does not say which branch
  the controller should prefer or how much hold time remains. Recurrent policy
  state, a controller-generated memory variable, or a robust stationary
  stabilization strategy could address the temporal ambiguity; choosing among
  those is a research decision, not a fact implied by the robot. [Assumptions:
  policy memory is available only through the selected learning/runtime
  mechanism. Sources: `robot_learning/scenario/observations.py:18-49`;
  `contracts/policy_runtime.py:162-177`. Discriminating evidence: interruption
  and completion rates for matched branch residuals with and without recurrent
  state.]

### Scientifically meaningful behavior quantities

- **[Reasoned implication]** The quantities most directly tied to mechanism are:
  target radius and angle; joint positions, velocities, and branch identity;
  end-effector distance and signed planar error; Jacobian determinant or
  conditioning; command magnitude and inferred motor effort; first-reach time;
  minimum distance; maximum consecutive hold; in-tolerance fraction; and hold
  interruptions. Together they distinguish reachability, convergence,
  overshoot, actuation limits, branch choice, and stabilization failure.
  **Decision relevance:** these quantities determine whether a failure is
  attributed to geometry, dynamics, sensing, or control, rather than to the
  binary success rate alone. [Assumptions: recorded trajectories preserve the
  relevant physical units. Sources: `robot_learning/scenario/evaluation.py:51-125`;
  `robot_learning/scenario/observations.py:27-49`;
  `contracts/robots/two_joint_arm.xml:12-19,30-33`. Discriminating evidence:
  synchronized state, action, target-geometry, and outcome traces.]

## Unknowns

### Effective constraints and inertial parameters

- **[Unresolved quantity]** It is not established from the XML alone whether
  the `range` attributes become active joint limits under the installed
  MuJoCo compiler settings, because `limited="true"` and an explicit compiler
  `autolimits` setting are absent. This determines whether +/-170 degrees is a
  physical constraint or only the intended kinematic range. **Decision
  relevance:** it changes whether policies can use out-of-range configurations
  and whether the two-branch workspace analysis is the actual state space.
  **Assumptions:** MuJoCo compiler defaults have not been inferred from source.
  **Sources:** `contracts/robots/two_joint_arm.xml:12-19`. **Discriminating
  evidence:** compiled model limit flags and observed qpos extrema in a
  model-level measurement would support or revise the constraint interpretation.

- **[Unresolved quantity]** The effective link masses, centers of mass,
  articulated inertia, and any default geom density are not stated explicitly.
  **Decision relevance:** these quantities set acceleration, braking distance,
  settling time, and the useful action scale, so they can change whether
  exploration should emphasize fast reaching or low-velocity stabilization.
  **Assumptions:** MuJoCo accepts compiler-derived inertial properties from the
  current geom definitions. **Sources:** `contracts/robots/two_joint_arm.xml:9-20`
  (no inertial or density declarations). **Discriminating evidence:** compiled
  body masses and inertia matrices, plus bounded-action step responses, would
  support or weaken the predicted dynamic regime.

- **[Unresolved quantity]** The effective self-collision behavior of the two
  capsule links is not fixed by explicit masks in the XML. **Decision
  relevance:** contacts could create a separate failure class for folded branch
  trajectories and alter the dynamics near small-radius targets. **Assumptions:**
  default MuJoCo geom filtering and any parent-child collision rules apply.
  **Sources:** `contracts/robots/two_joint_arm.xml:15-20`. **Discriminating
  evidence:** compiled contact-pair information and contact/force traces while
  traversing both branches would determine whether self-contact is reachable and
  consequential.

### Distribution and evaluation semantics

- **[Unresolved quantity]** The visible scenario implementation samples radius
  uniformly, whereas “uniformly from 6–20 cm over the full angular range” could
  be interpreted as uniform radius or uniform planar area; the protected
  official evaluator is authoritative for the final distribution. **Decision
  relevance:** it changes the value of radius-focused training and the
  interpretation of geometry-stratified development results. **Assumptions:**
  the protected evaluator may differ from the shared research environment.
  **Sources:** `contracts/scenario.md:7-14`;
  `contracts/task_spec.py:6`;
  `robot_learning/scenario/environment.py:83-89`;
  `robot_learning/scenario/evaluation.py:94-99`. **Discriminating evidence:**
  recorded official target-radius frequencies or an evaluator contract
  measurement would settle the distributional interpretation.

- **[Unresolved quantity]** The task contract describes a continuous
  uninterrupted two-second hold, while the visible implementation observes
  distance only once per 20 ms control interval after frame skipping.
  **Decision relevance:** it changes how much inter-sample oscillation matters
  and whether a policy must be designed for continuous-time safety or sampled
  endpoint success. **Assumptions:** the protected benchmark uses the same
  interaction semantics as the shared environment. **Sources:**
  `contracts/scenario.md:9-14`;
  `robot_learning/scenario/environment.py:130-159`. **Discriminating evidence:**
  per-internal-step distance traces or the protected evaluator's exact
  trajectory semantics would support, weaken, or revise this interpretation.

### Closed-loop behavior not fixed by definitions

- **[Unresolved quantity]** The definitions do not establish the settling-time
  distribution, overshoot, saturation frequency, branch preference, or
  geometry-dependent success rate of any learned policy. **Decision relevance:**
  those quantities determine whether first research should prioritize
  representation, action scaling, temporal memory, or stabilization. **Assumptions:**
  no pre-campaign policy or trajectory evidence is treated as scientific
  evidence. **Sources:** `robot_learning/scenario/evaluation.py:90-125`;
  `contracts/scenario.md:16-32`. **Discriminating evidence:** episode-level
  diagnostics paired with joint and action trajectories would distinguish
  reach failures from hold failures and branch-specific failures.

- **[Unresolved quantity]** The observation is physically informative but its
  practical numerical sufficiency under policy normalization, angle wrapping,
  and any recurrent runtime state is not established. **Decision relevance:**
  it changes whether the first campaign should keep the current observation,
  add temporal information, or target a branch-invariant controller. **Assumptions:**
  the saved runtime uses the exact observation/action closures supplied with
  the policy. **Sources:** `robot_learning/scenario/observations.py:14-49`;
  `contracts/policy_runtime.py:69-87,153-177`. **Discriminating evidence:**
  controlled comparisons of branch-wise tracking, hold interruptions, and
  identical physical states with different hold histories would test
  observability and memory demands.

## Decision-relevant synthesis

### Initial singularity and final stabilization

- **[Reasoned implication] Decision relevance:** The arm starts fully extended and singular, while
  success requires a low-error, low-velocity two-second set hold; reaching speed
  alone is not a sufficient first objective.
- **[Reasoned implication] Assumptions:** planar Jacobian reasoning applies and the sampled endpoint
  semantics are authoritative.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.py:5-7`;
  `robot_learning/scenario/environment.py:109-159`;
  `contracts/task_spec.py:7-11`.
- **[Reasoned implication] Discriminating evidence:** first-reach time, minimum distance, final
  velocity, maximum held steps, and interruption counts stratified by target
  radius and angle.

### Two valid inverse-kinematic branches

- **[Reasoned implication] Decision relevance:** The policy can choose distinct elbow-open and
  elbow-folded configurations; branch consistency and branch-specific dynamics
  may matter more than a single scalar distance metric.
- **[Reasoned implication] Assumptions:** declared joint ranges are active and both principal branches
  remain collision-free over the task distribution.
- **[Reasoned implication] Source references:** `robot_learning/scenario/observations.py:18-47`;
  `contracts/robots/two_joint_arm.xml:12-20`.
- **[Reasoned implication] Discriminating evidence:** branch residuals, joint trajectories, Jacobian
  conditioning, self-contact events, and hold success separated by branch.

### Actuation and inertial uncertainty

- **[Reasoned implication] Decision relevance:** Nominal commands are bounded joint motor commands,
  but compiler-derived inertia and damping determine acceleration, braking, and
  whether 50 Hz control has adequate authority for robust holding.
- **[Reasoned implication] Assumptions:** MuJoCo's compiled defaults supply the unspecified inertial
  properties without hidden actuator dynamics.
- **[Reasoned implication] Source references:** `contracts/robots/two_joint_arm.xml:2,12-19,30-33`;
  `robot_learning/scenario/environment.py:125-133`.
- **[Reasoned implication] Discriminating evidence:** compiled masses/inertias and repeatable
  bounded-action step-response measurements, including saturation and settling.

### Observation versus hold history

- **[Reasoned implication] Decision relevance:** The physical state is mostly observable, but the
  consecutive-hold counter is hidden; this can change the value of recurrent
  memory or explicit stabilization behavior.
- **[Reasoned implication] Assumptions:** the policy receives exactly the declared 11-value observation
  and no additional environment info.
- **[Reasoned implication] Source references:** `robot_learning/scenario/observations.py:11-49`;
  `robot_learning/scenario/environment.py:136-168`.
- **[Reasoned implication] Discriminating evidence:** hold interruptions and completion rates for
  otherwise matched physical states, together with comparisons of policies that
  do and do not retain temporal state.

### Official target distribution and sampled hold

- **[Reasoned implication] Decision relevance:** The first campaign decisions depend on whether radius
  is uniform or area-weighted and whether “continuous” hold is enforced only
  at 50 Hz or within the ten internal integration steps.
- **[Reasoned implication] Assumptions:** the protected official evaluator, rather than a development
  panel, defines the final distribution and interaction semantics.
- **[Reasoned implication] Source references:** `contracts/scenario.md:7-14,23-32`;
  `contracts/task_spec.py:6-11`;
  `robot_learning/scenario/environment.py:83-97,130-159`.
- **[Reasoned implication] Discriminating evidence:** official target draws and per-internal-step
  distance traces, or an authoritative protected-evaluator semantics record.
