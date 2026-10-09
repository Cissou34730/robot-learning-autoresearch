## Established facts

### Embodiment, coordinates, and kinematics

- **[Repository fact]** The robot is a two-joint planar serial arm. The shoulder and elbow are revolute joints about the world/body \(z\) axis; the upper arm is 0.12 m and the forearm is 0.10 m. The end-effector site is at the forearm tip, and the arm plane is \(z=0.02\) m. Sources: `contracts/robots/two_joint_arm.xml:9-20`; `contracts/robots/two_joint_arm.py:3-7`.
- **[Repository fact]** With shoulder angle \(q_1\) and relative elbow angle \(q_2\), the end-effector position is
  \[
  x=0.12\cos q_1+0.10\cos(q_1+q_2),\quad
  y=0.12\sin q_1+0.10\sin(q_1+q_2),\quad z=0.02.
  \]
  The XML declares \(-170^\circ\le q_1,q_2\le170^\circ\). Source: `contracts/robots/two_joint_arm.xml:12-20`.
- **[Reasoned implication]** Ignoring joint limits, the radial workspace is the annulus from \(|0.12-0.10|=0.02\) m to \(0.12+0.10=0.22\) m, with two inverse-kinematic branches for interior radii. The official target radii, 0.06–0.20 m, lie inside this nominal annulus; joint limits and branch availability still determine the exact feasible set at each angle. Sources: `contracts/robots/two_joint_arm.xml:12-20`; `contracts/task_spec.py:6`.

### Physics, actuation, and timing

- **[Repository fact]** MuJoCo uses zero gravity and a 0.002 s integration timestep. Each policy action is clipped to \([-1,1]^2\), assigned to the two controls, and followed by 10 MuJoCo steps. Therefore the policy acts every 0.020 s (50 Hz), while the physics integrates at 500 Hz. Sources: `contracts/robots/two_joint_arm.xml:1-3,30-33`; `robot_learning/scenario/environment.py:52-68,122-133`; `contracts/task_spec.py:8`.
- **[Repository fact]** Each actuator is a MuJoCo motor on one joint with gear 5 and control range \([-1,1]\). The action mapping is otherwise the identity; there is no separate command filter or actuator state in the scenario code. Sources: `contracts/robots/two_joint_arm.xml:30-33`; `robot_learning/scenario/policy_io.py:11-16`; `robot_learning/scenario/environment.py:125-132`.
- **[Repository fact]** Both joints declare damping 0.5 and armature 0.01. The XML does not explicitly specify body masses, inertias, actuator time constants, friction, or gravity compensation. Sources: `contracts/robots/two_joint_arm.xml:13-19`.
- **[Repository fact]** The base, plane, and target geoms have collision disabled. The target is a kinematic mocap body, not a dynamically moved object. Sources: `contracts/robots/two_joint_arm.xml:5-11,25-27`.

### Initial state and task geometry

- **[Repository fact]** Reset sets both joint positions and velocities to zero, forwards the model, then samples a target radius uniformly from 0.06–0.20 m and an angle uniformly from \(-\pi\) to \(\pi\). The target is placed at the end-effector’s \(z\) coordinate. Source: `robot_learning/scenario/environment.py:83-120`; `contracts/task_spec.py:6`.
- **[Reasoned implication]** The initial end effector is at \((0.22,0,0.02)\), the straight configuration, while the target can be anywhere on the stated annulus. The initial radial error can therefore be large and the initial direction can require either a substantial shoulder rotation or a branch-changing maneuver. This is a fixed-state reach problem, not a tracking problem with a moving target.
- **[Repository fact]** At each 0.020 s control boundary, success-band membership is tested using three-dimensional Euclidean distance. Membership requires distance \(\le0.01\) m; one outside sample resets the held counter to zero. Termination occurs after 100 consecutive in-band control steps, equivalent to 2 s, and truncation occurs after 500 control steps, equivalent to 10 s. Sources: `contracts/scenario.md:7-14,24-32`; `contracts/task_spec.py:7-11`; `robot_learning/scenario/environment.py:134-168`.
- **[Reasoned implication]** Because the target and end effector share \(z\), the official tolerance is effectively a 1 cm planar disk, but the operational hold is sampled at 50 Hz rather than checked after every 0.002 s integrator step. Source: `robot_learning/scenario/environment.py:130-159`.

### Sensing and policy interface

- **[Repository fact]** The observation has 11 values: two joint positions, two joint velocities, the three-dimensional end-effector-to-target vector, and four wrapped angular errors to the two analytic inverse-kinematic branches. The branch angles are computed from link lengths and target \(x,y\). Sources: `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/policy_io.py:7-16`.
- **[Reasoned implication]** The policy receives full noiseless generalized position and velocity for this model plus target-relative geometry. Absolute target coordinates are not a separate channel, but in this deterministic planar model they can be reconstructed from the measured end-effector position implied by \(q\) and the relative vector. There is no sensor noise, delay, force sensing, contact sensing, or explicit hold-counter observation.
- **[Repository fact]** Evaluation uses the saved policy runtime, deterministic prediction, and the same scenario observation/action functions; the normalizer, when present, is part of the saved runtime. Sources: `contracts/policy_runtime.py:153-177`; `robot_learning/scenario/evaluation.py:37-60`.

### Outcome semantics

- **[Repository fact]** The official distribution is uniform in radius and angle, and the official assessment uses 200 episodes with at most 500 control steps; at least 196 complete holds are required for 98%. Sources: `contracts/scenario.md:7-32`.
- **[Repository fact]** Research diagnostics distinguish first in-band step, minimum distance, final distance, maximum held run, in-band steps, and hold interruptions, but only the success Boolean defines the official outcome. Source: `robot_learning/scenario/evaluation.py:51-126`.

## Physical consequences

### Reachability and inverse-kinematic branch choice

- **[Reasoned implication]** **Decision relevance:** The first policy design must solve both target direction and radius over a two-branch inverse-kinematic family; a policy that memorizes one elbow posture can fail where that branch approaches a joint limit or demands a large transient. **Assumptions:** The declared joint ranges are active constraints and the analytic geometry is the runtime geometry. **Sources:** `contracts/robots/two_joint_arm.xml:12-20`; `robot_learning/scenario/observations.py:18-47`; `contracts/scenario.md:7-15`. **Discriminating evidence:** Per-target branch feasibility, terminal joint angles, branch selected, and distance-to-joint-limit measured across the full radius-angle domain.
- **[Reasoned implication]** **Decision relevance:** Targets near the outer radial edge have reduced radial margin to the 0.22 m kinematic maximum and can require coordinated motion of both joints; targets near the inner edge require a folded posture. These regions may need separate attention even though they are nominally reachable. **Assumptions:** No unmodeled collision or actuator limitation removes the analytic solutions. **Sources:** `contracts/robots/two_joint_arm.xml:12-20`; `contracts/task_spec.py:6`. **Discriminating evidence:** Workspace sweeps using the compiled model, achieved minimum distance by radius and angle, and the Jacobian singular values along successful and failed trajectories.

### Reaching is a torque- and timing-limited transient

- **[Reasoned implication]** **Decision relevance:** Action scale, exploration, and control smoothness can change whether the arm reaches in the 10 s horizon without overshoot. The 50 Hz action hold means each command persists for 20 ms and can produce a materially different velocity before the next correction. **Assumptions:** Motor force follows the native MuJoCo motor model without hidden filtering, and the effective torque authority is sufficient but finite. **Sources:** `contracts/robots/two_joint_arm.xml:1-3,30-33`; `robot_learning/scenario/environment.py:125-133`; `contracts/task_spec.py:7-8`. **Discriminating evidence:** Step responses from fixed joint states, action-to-acceleration gain, peak velocity, settling time, saturation fraction, and success versus first-reach time.
- **[Reasoned implication]** **Decision relevance:** Damping can make low-amplitude corrections converge, but inertia and armature can make abrupt reversals slow or oscillatory; reaching and stabilization cannot be optimized independently. **Assumptions:** The compiled masses and inertias are stable across episodes and the declared damping acts as joint viscous damping. **Sources:** `contracts/robots/two_joint_arm.xml:13-19`. **Discriminating evidence:** Free-response decay, commanded reversals at several postures, and residual error/velocity during the hold.

### Complete hold is a stabilization problem

- **[Reasoned implication]** **Decision relevance:** A fast first arrival is insufficient. The policy must maintain a closed-loop equilibrium inside a 1 cm disk for 2 s, with enough margin to absorb discretization and residual velocity. Selection should therefore value maximum uninterrupted held run and exit rate, not reward or minimum distance alone. **Assumptions:** The target is stationary and the success counter semantics remain authoritative. **Sources:** `contracts/scenario.md:7-20`; `robot_learning/scenario/environment.py:134-168`; `robot_learning/scenario/evaluation.py:67-75`. **Discriminating evidence:** Hold-duration distributions, velocity and action variance during holds, number and timing of exits, and success conditioned on first reaching the band.
- **[Reasoned implication]** **Decision relevance:** Since velocity is observed, the controller can brake before entering the band and correct errors after entry; since force and hold state are not observed, it must infer stability from position/velocity history and its own actions. **Assumptions:** The observation is noiseless and the saved runtime preserves the same observation semantics. **Sources:** `robot_learning/scenario/observations.py:36-49`; `contracts/policy_runtime.py:153-177`. **Discriminating evidence:** Compare entry speed, post-entry error variance, and hold success for trajectories with similar first-reach distance.

### Failure classes and meaningful measurements

- **[Reasoned implication]** **Decision relevance:** Failures separate into (a) geometric/limit failure, (b) slow or torque-limited arrival, (c) overshoot or oscillation, and (d) hold interruption after arrival. These classes imply different research choices, so episode success should be decomposed by target radius, angle, first-reach step, minimum distance, maximum held run, action saturation, and joint-limit proximity. **Assumptions:** The diagnostics are recorded without changing task semantics. **Sources:** `robot_learning/scenario/evaluation.py:90-126`; `robot_learning/scenario/environment.py:157-168`. **Discriminating evidence:** Stratified episode traces and joint/action telemetry for each failure class.
- **[Reasoned implication]** **Decision relevance:** The mechanically meaningful state is \((q,\dot q)\); the task-relative state is end-effector error \(e\); the control quantities are action, resulting generalized torque, velocity, and energy; the outcome quantities are first entry and uninterrupted dwell. These are sufficient to distinguish kinematic error from dynamic control error, whereas scalar reward is not. **Assumptions:** Native MuJoCo state and actuator quantities are available to a measurement module without altering the policy interface. **Sources:** `robot_learning/scenario/observations.py:36-49`; `contracts/robots/two_joint_arm.xml:30-33`; `robot_learning/training/reward.py:47-107`. **Discriminating evidence:** Time-aligned traces of \(q,\dot q,e,u\), actuator saturation, and hold state.

## Unknowns

### Compiled inertial and actuator parameters

- **[Unresolved quantity]** The source XML does not state the effective masses, full inertia tensors, center-of-mass locations, actuator gain details beyond gear, or whether any native actuator/limit defaults add dynamics. These quantities determine acceleration, coupling, braking distance, and the true torque margin. **Decision relevance:** They could change whether to prioritize fast reaching, smooth actions, or explicit stabilization. **Assumptions:** The XML alone is an adequate physical specification; this assumption is not yet verified for the compiled MuJoCo model. **Sources:** `contracts/robots/two_joint_arm.xml:12-33`. **Discriminating evidence:** A compiled-model dump of masses/inertias, actuator transmission/gain/force limits, and controlled step-response measurements.

### Joint-limit and contact behavior

- **[Unresolved quantity]** The joint ranges are declared, but the source does not expose the compiled limit activation and reaction behavior. Arm link geoms have default contact attributes while the plane, base, and target explicitly disable contact, so any self-contact behavior near the elbow is not established from the contract alone. **Decision relevance:** Active limits or unexpected contacts could create sharp failure regions and alter branch selection. **Assumptions:** Declared ranges are the only relevant constraints and adjacent-link contacts never occur. **Sources:** `contracts/robots/two_joint_arm.xml:5-20`. **Discriminating evidence:** Compiled joint-limit flags and contact exclusions, plus workspace sweeps recording constraint forces and contacts.

### Effective hold continuity

- **[Unresolved quantity]** The task calls the hold continuous, but the implementation evaluates membership only after each 10-substep control interval. It is unknown whether a trajectory can leave and re-enter the tolerance disk between checks without being counted as interrupted. **Decision relevance:** If this occurs, action timing and high-frequency oscillations may exploit or be penalized by the operational semantics, changing the value of smoothing and hold-specific control. **Assumptions:** The control-boundary check is the complete authoritative implementation of continuity. **Sources:** `contracts/scenario.md:7-14`; `robot_learning/scenario/environment.py:130-159`. **Discriminating evidence:** Record distance at every MuJoCo substep for trajectories that pass the 50 Hz hold test and search for within-interval exits.

### Feasible-branch margin over the official distribution

- **[Unresolved quantity]** Analytic inverse kinematics supplies two candidate branches, but the exact subset that respects compiled joint limits with useful dynamic margin at every target angle and radius is not recorded. **Decision relevance:** A narrow branch margin would favor branch-aware or posture-conditioned control; broad margins would favor a single smooth policy. **Assumptions:** The analytic branch equations match MuJoCo site kinematics and no collision constraint removes solutions. **Sources:** `robot_learning/scenario/observations.py:18-47`; `contracts/robots/two_joint_arm.xml:12-20`. **Discriminating evidence:** Dense target-grid solving with limit margins, Jacobian conditioning, and achieved trajectories on both branches.

### Policy-normalization and learned-action realization

- **[Unresolved quantity]** The current configuration enables observation normalization for PPO training, but the magnitude distribution of normalized observations and the resulting learned action distribution are not physical properties fixed by the robot contract. **Decision relevance:** Saturation, action cost, and generalization across target geometry may be learning bottlenecks rather than mechanical limits. **Assumptions:** The saved runtime includes matching normalization statistics and deterministic inference. **Sources:** `robot_learning/train.py:103-116,158-183`; `contracts/policy_runtime.py:69-79,153-177`; `robot_learning/training/current_params.json:1-23`. **Discriminating evidence:** Runtime action histograms, saturation by target geometry, and paired traces with and without normalization only where the runtime contract permits comparison.

## Decision-relevant synthesis

### Hold stability is the primary physical bottleneck

- **[Reasoned implication] Decision relevance:** The 2 s uninterrupted hold makes stabilization, not merely reachability, decisive for the 98% objective.
- **[Reasoned implication] Assumptions:** The stationary-target and 100-consecutive-control-step semantics are authoritative.
- **[Repository references]** `contracts/scenario.md:7-20`; `robot_learning/scenario/environment.py:134-168`.
- **[Discriminating evidence]** Hold-duration and interruption distributions, entry velocity, post-entry error variance, and success conditioned on first reaching tolerance.

### The task is nominally reachable but has branch and workspace structure

- **[Reasoned implication] Decision relevance:** The first campaign decision may depend on whether one or both elbow branches remain dynamically useful across radius and angle; outer and inner radial regions should not be assumed equally easy.
- **[Reasoned implication] Assumptions:** The analytic two-link geometry and declared joint ranges describe the compiled robot without hidden contact exclusions or limit changes.
- **[Repository references]** `contracts/robots/two_joint_arm.xml:12-20`; `contracts/task_spec.py:6`; `robot_learning/scenario/observations.py:18-47`.
- **[Discriminating evidence]** Target-grid branch feasibility, joint-limit/Jacobian margins, and success stratified by radius and angle.

### Dynamics are specified only partially

- **[Unresolved quantity] Decision relevance:** Effective inertia, actuator gain/limits, and native constraint behavior could determine whether failures require faster control, smoother braking, or a different policy representation.
- **[Unresolved quantity] Assumptions:** No compiled-model inspection or system-identification evidence is yet available beyond the XML declarations.
- **[Repository references]** `contracts/robots/two_joint_arm.xml:1-3,12-33`.
- **[Discriminating evidence]** Compiled inertial/actuator parameters and measured action-to-acceleration, reversal, settling, and saturation responses.

### Observation is rich for state feedback but omits direct physical diagnostics

- **[Reasoned implication] Decision relevance:** The policy can condition on position, velocity, target error, and both IK branches, but it cannot directly observe torque, contact, or the hold counter; diagnosis must therefore use external traces and not infer mechanism from reward alone.
- **[Reasoned implication] Assumptions:** The observation remains noiseless and the saved runtime preserves the scenario functions.
- **[Repository references]** `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/policy_io.py:11-16`; `contracts/policy_runtime.py:153-177`.
- **[Discriminating evidence]** Time-aligned observation/action/state traces with actuator saturation, constraint forces, and per-substep distance.
