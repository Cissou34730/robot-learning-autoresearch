## Established facts

### Robot morphology and kinematic state

- **Repository fact.** The robot is a planar serial two-link arm with a revolute shoulder and a revolute elbow. Both hinge axes are the world `z` axis, so the two generalized coordinates are joint angles `q1` and `q2`, with `q2` measured relative to the upper arm. The upper-arm and forearm lengths are 0.12 m and 0.10 m. The shoulder and elbow joint ranges are each -170 to 170 degrees. [Source: `contracts/robots/two_joint_arm.xml:12-19`; `contracts/robots/two_joint_arm.py:5-7`]

- **Repository fact.** The end-effector site is at the distal forearm endpoint. Its fixed height is 0.02 m above the world origin, because the upper-arm body is translated to `z=0.02` and the remaining bodies and site have zero relative `z` translation. The target is a mocap body whose position is set in that same plane. [Source: `contracts/robots/two_joint_arm.xml:12-20,25-27`; `robot_learning/scenario/environment.py:90-97`]

- **Repository fact.** The planar forward kinematics are therefore
  `x = 0.12 cos(q1) + 0.10 cos(q1+q2)` and
  `y = 0.12 sin(q1) + 0.10 sin(q1+q2)`, with `z=0.02`. The nominal radial workspace before joint limits is the annulus from `|0.12-0.10|=0.02 m` to `0.22 m`. [Source: link geometry in `contracts/robots/two_joint_arm.xml:15-20`]

- **Repository fact.** The arm, target, and plane geoms have contact disabled (`contype=0`, `conaffinity=0`). The target is a visual mocap body rather than a physical object that can push or constrain the arm. [Source: `contracts/robots/two_joint_arm.xml:6,10-11,25-27`]

### Actuation, simulator, and timing

- **Repository fact.** The policy emits two continuous values in `[-1,1]`. The scenario passes them unchanged through `physical_action`, clips them to that range, writes them to `data.ctrl`, and holds them while MuJoCo advances ten physics steps. [Source: `robot_learning/scenario/policy_io.py:11-16`; `robot_learning/scenario/environment.py:122-133`]

- **Repository fact.** Each actuator is a MuJoCo motor on one joint, with `ctrlrange=-1 1` and scalar `gear=5`. With the standard motor transmission and no separate force limit in the XML, the commanded generalized actuator force is proportional to `5*ctrl`, subject to MuJoCo's compiled actuator semantics. [Source: `contracts/robots/two_joint_arm.xml:30-32`]

- **Repository fact.** The physics timestep is 0.002 s, gravity is zero, and each policy action spans ten physics steps. The control interval is therefore 0.020 s (50 Hz). The shoulder and elbow have damping 0.5 and armature 0.01. [Source: `contracts/robots/two_joint_arm.xml:1-3,13-18`; `contracts/task_spec.py:8`; `robot_learning/scenario/environment.py:56-57`]

- **Repository fact.** Reset sets both joint positions and velocities to zero, runs forward dynamics, samples the target, and does not add sensor noise, action delay, or target motion in the accessible scenario implementation. [Source: `robot_learning/scenario/environment.py:102-120`]

### Task geometry and success semantics

- **Repository fact.** Official targets span radii 0.06–0.20 m and the full angular range about the base. The accessible sampler draws angle uniformly from `[-pi,pi]` and radius uniformly from the configured interval, then sets target `z` to the end-effector height. [Source: `contracts/scenario.md:7-14`; `contracts/task_spec.py:6`; `robot_learning/scenario/environment.py:83-97`]

- **Repository fact.** Success is based on the Euclidean end-effector-to-target distance being at most 0.01 m for 2.0 s. At 0.020 s per control step this is 100 consecutive in-tolerance control steps. One observed step outside the tolerance resets the held-step count; an episode truncates at 500 control steps if it has not terminated. [Source: `contracts/scenario.md:9-20`; `contracts/task_spec.py:7-11`; `robot_learning/scenario/environment.py:134-168`]

- **Repository fact.** The official assessment uses 200 frozen-policy episodes and requires at least 196 successes for 98%. Development research evaluation is separate and records per-episode radius, angle, minimum and final distance, first reach step, maximum held steps, in-tolerance steps, and hold interruptions. [Source: `contracts/scenario.md:24-32`; `robot_learning/scenario/evaluation.py:90-125`]

### Sensing, reward, and learning interface

- **Repository fact.** The 11-element observation contains the two joint positions, two joint velocities, the three-dimensional end-effector-minus-target vector, and four wrapped angular errors to analytically computed open and folded inverse-kinematic solutions. [Source: `robot_learning/scenario/observations.py:11-49`]

- **Repository fact.** The observation exposes no explicit force, acceleration, actuator state, contact state, or target velocity. The target is fixed, and the relative position is measured without noise in the accessible implementation. [Source: `robot_learning/scenario/observations.py:36-49`; `robot_learning/scenario/environment.py:83-97`]

- **Repository fact.** The current training distribution is radii 0.14–0.20 m, narrower than the official 0.06–0.20 m distribution. The current reward combines distance progress, exponential closeness, hold progress, a small action cost, an outside-band penalty after a hold interruption, and a completion bonus. These are research implementation choices, not the immutable success definition. [Source: `robot_learning/training/environment.py:14-19`; `robot_learning/training/reward.py:16-25,47-108`; `robot_learning/scenario/environment.py:7-11`]

## Physical consequences

### Reachability and inverse-kinematic alternatives

- **Reasoned implication.** For a target radius `r`, inverse kinematics requires
  `cos(q2)=(r^2-0.12^2-0.10^2)/(2*0.12*0.10)`. Across 0.06–0.20 m this gives two elbow branches with approximately `|q2|` from 49.5 to 150.1 degrees, inside the ±170-degree elbow limit. The corresponding shoulder branches differ in sign about the target bearing; because their geometric offset remains more than 10 degrees over this radius range, at least one and, away from numerical boundary details, both branches can satisfy the ±170-degree shoulder limit for every target bearing. The official target annulus is therefore kinematically reachable, with branch choice rather than reachability being the main geometric alternative.

  - **Decision relevance:** A controller can solve the same target through elbow-open or elbow-folded postures. A failure should not automatically be interpreted as insufficient workspace; branch selection, branch switching, or poor conditioning may be causal.
  - **Assumptions:** The site position follows the two-link equations, joint angles use the XML relative-joint convention, and MuJoCo limit handling does not materially remove the analytic branches.
  - **Source references:** `contracts/robots/two_joint_arm.xml:12-20`; `contracts/robots/two_joint_arm.py:5-7`; `robot_learning/scenario/observations.py:18-35`.
  - **Discriminating evidence:** Per-episode final `qpos`, branch-specific IK residuals, and target bearing/radius stratification would show whether failures cluster on one branch or on particular workspace regions.

### Initial configuration and trajectory difficulty

- **Reasoned implication.** Reset starts at `q1=q2=0`, so the end effector is fully extended at `(0.22, 0, 0.02)`, while every official target has radius at most 0.20 m. The initial arm is outside the success ball and at a kinematic singularity: the first-order Jacobian has no radial motion at full extension. Moving inward therefore requires coordinated bending and then rotation, not merely a small radial correction.

  - **Decision relevance:** Early-episode behavior can be dominated by escaping the extended singular posture. Reach time, initial action direction, and overshoot are distinct from steady-state holding ability.
  - **Assumptions:** The reset is exactly the accessible implementation's zero state and the target is sampled after that state is established.
  - **Source references:** `robot_learning/scenario/environment.py:102-120`; `contracts/robots/two_joint_arm.xml:15-20`; `contracts/scenario.md:9-14`.
  - **Discriminating evidence:** Joint and end-effector trajectories during the first control steps, especially radial versus tangential velocity and elbow-bending onset, would distinguish singularity escape from weak actuation or poor target encoding.

### Dynamics, authority, and control rate

- **Reasoned implication.** The policy is not commanding a kinematic pose or a velocity; it commands bounded joint motor effort that is held for 20 ms. Damping dissipates joint motion, while armature adds effective rotational inertia. With gravity and contact absent, the behavior is principally an inertial, damped, two-joint system. The usable acceleration, settling time, and amount of overshoot depend on the compiled link inertias relative to the nominal motor torque and damping.

  - **Decision relevance:** The relative scale of motor authority and inertia determines whether direct policy control can make a fast, stable approach, whether action saturation is common, and whether a smoother or more explicitly stabilizing policy is needed.
  - **Assumptions:** MuJoCo applies the motor transmission as specified and no unlisted actuator dynamics or force saturation dominates.
  - **Source references:** `contracts/robots/two_joint_arm.xml:1-3,13-18,30-32`; `robot_learning/scenario/environment.py:125-133`.
  - **Discriminating evidence:** A bounded-action open-loop or local perturbation trace recording `qpos`, `qvel`, action, and end-effector acceleration would identify effective torque-to-acceleration response, damping, saturation, and settling time.

### Convergence and uninterrupted stabilization

- **Reasoned implication.** The task is not satisfied by reaching the tolerance once. A single sampled excursion resets the hold to zero, so the controller must reduce both position error and residual velocity before or while entering the 1 cm ball. Once exactly at a stationary target with zero velocity, zero gravity and zero contact force make zero motor effort a physical equilibrium; practical holding difficulty comes from approach momentum, numerical integration, imperfect settling, or a controller that continues injecting effort.

  - **Decision relevance:** Separating first-reach failures from hold interruptions changes whether the limiting behavior is trajectory generation or stabilization. Maximal reach distance alone is not a sufficient progress measure.
  - **Assumptions:** The accessible success loop is representative of official control-step semantics and the target remains fixed throughout the episode.
  - **Source references:** `contracts/scenario.md:9-20`; `robot_learning/scenario/environment.py:134-159`; `contracts/robots/two_joint_arm.xml:1-3`.
  - **Discriminating evidence:** The evaluation diagnostics already expose first reach, maximum held steps, in-tolerance steps, and interruptions; adding velocity and action traces at entry and interruption would identify momentum-driven exits versus persistent control oscillation.

### Observation-to-action relation and observability

- **Reasoned implication.** In the deterministic, noiseless model, the observation is close to a full task-relevant state: `qpos` and `qvel` give joint state, and the relative end-effector vector plus forward kinematics makes the target position reconstructible. The four IK errors explicitly reveal both candidate goal postures. Thus target bearing is not fundamentally hidden, although there is no single preferred branch and no direct measurement of unmodeled dynamic quantities.

  - **Decision relevance:** If behavior is poor despite correct geometric errors, the likely frontier is dynamic calibration, action timing, or stabilization rather than target localization. Branch-aware diagnostics are more informative than treating the observation as a generic feature vector.
  - **Assumptions:** The policy runtime uses the saved observation function, the model geometry is exact, and no hidden observation normalization or recurrent state changes the physical information content.
  - **Source references:** `robot_learning/scenario/observations.py:14-49`; `robot_learning/scenario/policy_io.py:11-16`; `contracts/policy_runtime.py:153-177`.
  - **Discriminating evidence:** Reconstruct the target from observed joint state and relative error, compare it with `mocap_pos`, and correlate prediction/action errors with `qvel`, branch residuals, and distance rather than with target coordinates alone.

### Failure classes and scientifically meaningful quantities

- **Reasoned implication.** The coupled behavior has at least four physically distinct failure classes: unreachable or limit-constrained posture (unlikely for the official annulus), slow or misdirected singularity escape, first entry followed by an in-tolerance exit, and timeout before entry or completion. The most informative quantities over the complete behavior are target radius and bearing, joint angles and velocities, action saturation, end-effector position and velocity, distance-to-target, first-reach time, uninterrupted hold length, and hold interruption count.

  - **Decision relevance:** These quantities distinguish geometric coverage, trajectory control, convergence, and stabilization, preventing a scalar success rate from hiding the mechanism limiting the 98% objective.
  - **Assumptions:** The target distribution and success predicate are fixed as stated, and the recorded diagnostics are aligned to the same control-step clock as the task.
  - **Source references:** `contracts/scenario.md:7-32`; `robot_learning/scenario/evaluation.py:40-125`; `robot_learning/scenario/environment.py:134-168`.
  - **Discriminating evidence:** Jointly stratified episode diagnostics by radius, bearing, branch residual, first-reach step, maximum hold, and action magnitude would identify which physical class contributes the remaining failures.

## Unknowns

### Compiled mass and inertia

- **Unresolved quantity.** The XML gives capsule and cylinder geometry but no explicit body mass, inertial tensor, or geom density. MuJoCo consequently derives compiled inertial properties using simulator defaults and the attached geoms; the resulting link and composite inertias are not established by the source text alone.

  - **Decision relevance:** This can change the effective acceleration, action saturation, approach overshoot, and whether a policy trained under the current dynamics has enough authority at all target geometries.
  - **Assumptions:** No external model-generation step replaces the XML-derived inertial compilation.
  - **Source references:** `contracts/robots/two_joint_arm.xml:9-20`; `robot_learning/scenario/environment.py:52-57`.
  - **Discriminating evidence:** A Runner-authorized model characterization or a recorded MuJoCo model dump of body masses, inertia matrices, actuator transmissions, and local linear responses would resolve it; measured acceleration under known commands would support or weaken the compiled-value interpretation.

### Solver, integrator, and joint-limit behavior

- **Unresolved quantity.** The XML fixes timestep and gravity but does not explicitly state integrator, solver tolerances, constraint parameters, or limit-contact behavior. These simulator defaults can affect numerical damping, behavior near ±170 degrees, and whether a control-step distance check misses a transient inside a ten-substep block.

  - **Decision relevance:** If failures concentrate near joint limits or occur as short hold interruptions, the cause may be numerical/constraint behavior rather than policy representation.
  - **Assumptions:** The protected evaluator uses the same compiled model and control-step sampling semantics as the accessible environment.
  - **Source references:** `contracts/robots/two_joint_arm.xml:1-3,13-18`; `robot_learning/scenario/environment.py:130-159`; `contracts/scenario.md:9-14`.
  - **Discriminating evidence:** Exact compiled option/solver inspection plus substep distance and limit-force traces would show whether the arm leaves the tolerance between policy observations or receives material limit impulses.

### Effective actuator force and hidden runtime transformations

- **Unresolved quantity.** The XML establishes the motor gear and control range, but the compiled actuator force under every state, including any simulator-level force limits or transmission details, is not recorded in the accessible source. Saved policy normalization affects observation values presented to the policy, and the exact runtime artifact may contain a frozen I/O closure.

  - **Decision relevance:** An apparent policy change may actually be a change in action scaling, normalization, or saturation. This affects comparisons of control authority and transfer across candidates.
  - **Assumptions:** The runtime artifact is valid and corresponds to the evaluated policy weights and normalization statistics.
  - **Source references:** `contracts/robots/two_joint_arm.xml:30-32`; `robot_learning/scenario/policy_io.py:11-16`; `contracts/policy_runtime.py:61-111,153-181`.
  - **Discriminating evidence:** Runtime fingerprint inspection together with commanded-versus-applied control and actuator-force traces would separate policy output, clipping, transmission, and physical force.

### Protected official evaluation details

- **Unresolved quantity.** The public scenario contract fixes the official radius range, full angle range, 200-episode panel, 500-step limit, and 100-step hold requirement, but the protected evaluator's exact target sampling implementation and whether it tests only post-control-step states or also internal MuJoCo substeps are not accessible here.

  - **Decision relevance:** A policy that is robust at 50 Hz can still differ from one that exploits unobserved within-block excursions; the distinction matters when interpreting development diagnostics and claiming readiness for the 98% threshold.
  - **Assumptions:** The public contract is the complete behavioral definition except for implementation details intentionally protected by the benchmark.
  - **Source references:** `contracts/scenario.md:7-32`; `contracts/instruments.md:405-421`; accessible comparison implementation `robot_learning/scenario/environment.py:130-159`.
  - **Discriminating evidence:** A task-reference or official assessment result, supplemented where available by its recorded evaluator semantics, would support or revise the control-step interpretation; development results alone cannot establish the protected panel's exact behavior.

### Generalization from training to the official inner workspace

- **Unresolved quantity.** The current training environment samples only 0.14–0.20 m, whereas the official task includes 0.06–0.14 m. The physical model predicts those inner targets are reachable, but it does not establish that the learned policy will select valid branches, escape the initial posture, or stabilize there.

  - **Decision relevance:** This is a direct distributional risk to the 98% objective and may matter more than optimizing already-covered outer-radius behavior.
  - **Assumptions:** The current training range remains the effective range and the official evaluator uses the stated full range.
  - **Source references:** `robot_learning/training/environment.py:14-19`; `contracts/scenario.md:7-14`; `contracts/robots/two_joint_arm.py:5-7`.
  - **Discriminating evidence:** Radius-stratified development evaluation, especially below 14 cm, with branch and hold diagnostics would show whether the gap is geometric, dynamic, or learned-distribution generalization.

## Decision-relevant synthesis

### Inner-workspace coverage is the first distributional risk

- **Decision relevance:** Official targets include 6–14 cm radii absent from the current 14–20 cm training range; this can dominate the gap to 98%.
- **Assumptions:** The current training environment is the effective learned distribution and the official range is as specified.
- **Source references:** `contracts/scenario.md:7-20`; `robot_learning/training/environment.py:14-19`.
- **Discriminating evidence:** Radius-stratified success, first-reach time, branch residual, and hold interruption diagnostics below and above 14 cm.

### The fully extended reset creates a singularity-escape problem

- **Decision relevance:** The arm begins at maximum reach with no first-order radial motion, so early trajectory failure can be distinct from endpoint or hold failure.
- **Assumptions:** Reset state is zero joint position and velocity, with the end effector at 0.22 m.
- **Source references:** `robot_learning/scenario/environment.py:102-120`; `contracts/robots/two_joint_arm.xml:15-20`.
- **Discriminating evidence:** Initial qpos/qvel, radial and tangential end-effector velocity, action saturation, and time to first meaningful elbow bend.

### Holding is a separate control requirement from reaching

- **Decision relevance:** One out-of-tolerance control sample resets all hold progress; policies that reach quickly can still fail the complete uninterrupted task.
- **Assumptions:** The official hold is evaluated at the stated 100-control-step resolution and the target remains fixed.
- **Source references:** `contracts/scenario.md:9-20`; `robot_learning/scenario/environment.py:134-159`.
- **Discriminating evidence:** Maximum held steps, interruption counts, end-effector velocity at first entry, and action magnitude during the hold.

### Dynamic authority is not established by geometry alone

- **Decision relevance:** The 5:1 motor transmission, damping, armature, and unspecified compiled inertias determine whether bounded actions can converge without overshoot.
- **Assumptions:** MuJoCo compiled defaults supply the omitted inertial and solver quantities without an unmodeled external force limit.
- **Source references:** `contracts/robots/two_joint_arm.xml:1-3,13-18,30-32`.
- **Discriminating evidence:** Known-action system characterization with applied force, acceleration, settling time, and saturation across representative postures.

### Branch choice is a real alternative, not an observation deficiency

- **Decision relevance:** The official annulus admits open and folded inverse-kinematic solutions, so branch-aware behavior may improve reliability without changing the task geometry.
- **Assumptions:** The analytic two-link model and joint limits describe the compiled kinematics over the full target range.
- **Source references:** `robot_learning/scenario/observations.py:18-47`; `contracts/robots/two_joint_arm.xml:12-20`.
- **Discriminating evidence:** Final joint configurations and the four branch-specific angular residuals, stratified by target geometry and outcome.
