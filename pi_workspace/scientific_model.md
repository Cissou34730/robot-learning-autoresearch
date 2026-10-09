## Established facts

### Robot morphology and coordinates

- **[Repository fact]** The robot is a planar, serial two-revolute-joint arm. The shoulder and elbow axes are both the world z axis; the upper arm is 0.12 m and the forearm is 0.10 m. The end-effector site is at the forearm tip. The arm therefore has two configuration coordinates, `q = (q_shoulder, q_elbow)`, and moves in the horizontal xy plane at z = 0.02 m. [Source: `contracts/robots/two_joint_arm.xml:9-21`; `contracts/robots/two_joint_arm.py:5-7`]
- **[Repository fact]** Each hinge range is -170 to +170 degrees. The initial reset sets both joint positions and velocities to zero, so the arm starts straight along +x with the end effector at approximately `(0.22, 0, 0.02)` and zero velocity. [Source: `contracts/robots/two_joint_arm.xml:12-19`; `robot_learning/scenario/environment.py:102-120`]
- **[Repository fact]** The planar forward kinematics are therefore
  `x = 0.12 cos(q1) + 0.10 cos(q1+q2)`,
  `y = 0.12 sin(q1) + 0.10 sin(q1+q2)`,
  with constant z = 0.02. The target is a mocap body, not an actuated or dynamically falling object. [Source: `contracts/robots/two_joint_arm.xml:16-27`; `robot_learning/scenario/environment.py:75-81`]

### Actuation, simulation, and timing

- **[Repository fact]** The action is a two-element box in `[-1, 1]^2`. The policy action is passed through unchanged and then clipped by the environment. Each element drives a MuJoCo motor attached to one joint with gear 5, so the nominal transmitted joint torque is `tau_i = 5 u_i`, bounded at approximately +/-5 N m before other model effects. [Source: `robot_learning/scenario/environment.py:122-132`; `robot_learning/scenario/policy_io.py:11-17`; `contracts/robots/two_joint_arm.xml:30-33`]
- **[Repository fact]** MuJoCo integrates at a 0.002 s timestep. Ten internal steps use the same command between observations, giving a 0.020 s control period and 50 control decisions per second. [Source: `contracts/robots/two_joint_arm.xml:1-2`; `contracts/task_spec.py:8`; `robot_learning/scenario/environment.py:55-57,130-133`]
- **[Repository fact]** Gravity is disabled. Each joint has damping 0.5 and armature 0.01. No explicit body mass, inertia, actuator dynamics, friction, or integrator setting appears in the robot XML; unspecified values are supplied by MuJoCo defaults or derived from the geometry. [Source: `contracts/robots/two_joint_arm.xml:1-2,12-19`; `robot_learning/scenario/environment.py:52-57`]
- **[Repository fact]** The visible plane, base, links, and target do not define a task interaction such as grasping: the success calculation is the Euclidean distance between the end-effector site position and the target mocap position. [Source: `contracts/robots/two_joint_arm.xml:5-6,9-20,25-27`; `robot_learning/scenario/environment.py:75-81,134-168`]

### Task distribution and success state

- **[Repository fact]** Official targets have radius 0.06–0.20 m from the base and cover the full angle range. The current sampler draws radius and angle independently and uniformly, places the target at the end-effector plane height, and leaves the target fixed during an episode. [Source: `contracts/scenario.md:7-14`; `contracts/task_spec.py:6`; `robot_learning/scenario/environment.py:83-97`]
- **[Repository fact]** The tolerance is 0.01 m. At each post-control-step sample, distance at or below tolerance increments the hold counter; one sample outside resets it to zero. Completion requires 100 consecutive in-tolerance control samples, equivalent to 2.0 s at the current 0.020 s period. An episode truncates after 500 control steps, or 10 s. [Source: `contracts/scenario.md:9-14,16-27`; `contracts/task_spec.py:7-11`; `robot_learning/scenario/environment.py:134-168`]
- **[Repository fact]** The target is sampled after reset while the arm is in its straight initial state. The initial distance is thus determined by target radius and angle; it is never below 0.02 m for the official radial range because the initial reach is 0.22 m and the largest target radius is 0.20 m. [Source: `robot_learning/scenario/environment.py:102-120`; `contracts/robots/two_joint_arm.py:5-7`; `contracts/task_spec.py:6`]
- **[Repository fact]** The official assessment uses one frozen policy over 200 episodes, with success required in at least 196 episodes. [Source: `contracts/scenario.md:24-31`]

### Observation and policy interface

- **[Repository fact]** The observation has 11 float32 values: two joint positions, two joint velocities, the three-dimensional end-effector-minus-target vector, and four wrapped angular errors to the two inverse-kinematic branches (elbow open and elbow folded). [Source: `robot_learning/scenario/observations.py:11-49`]
- **[Repository fact]** The inverse-kinematic reference uses the known link lengths and the target xy position. It computes `q2 = +/- acos(c)` and the corresponding shoulder angle, clipping `c` to `[-1,1]`; both branch errors are exposed. [Source: `robot_learning/scenario/observations.py:18-35,41-47`]
- **[Repository fact]** The environment returns distance, current held steps, and success in `info`, but these values are not part of the policy observation. The policy receives neither the hold counter nor an explicit time-to-go signal. [Source: `robot_learning/scenario/environment.py:134-168`; `robot_learning/scenario/observations.py:36-49`]
- **[Repository fact]** The current training entry point constructs PPO with an `MlpPolicy`; the runtime interface nevertheless permits a policy with recurrent state and resets that state at episode start. [Source: `robot_learning/train.py:22-23,127-136`; `contracts/policy_runtime.py:153-177`]

## Physical consequences

### Reachability and kinematic structure

- **[Reasoned implication]** The unconstrained reachable radii are `[|0.12-0.10|, 0.12+0.10] = [0.02, 0.22]` m. The official `[0.06,0.20]` annulus is strictly inside that radial envelope. Using the two inverse-kinematic branches, official targets require elbow magnitudes of approximately 150 degrees at 0.06 m down to 49 degrees at 0.20 m; these are inside the +/-170 degree elbow limit. The shoulder-limit question is resolved by branch choice for this annulus under the stated planar kinematics, so the dominant difficulty is control, not geometric impossibility. [Sources: `contracts/robots/two_joint_arm.xml:12-19`; `contracts/task_spec.py:6`; `robot_learning/scenario/observations.py:18-35`]
  1. **Decision relevance:** Treat failures near the boundary as reach-and-control failures rather than assuming unreachable targets; branch-aware control and target-angle stratification are physically justified.
  2. **Assumptions:** The XML hinge ranges use the standard MuJoCo angle convention, the planar forward-kinematic equations above apply, and there are no unlisted obstacles or contact constraints.
  3. **Source references:** `contracts/robots/two_joint_arm.xml:12-20`; `contracts/robots/two_joint_arm.py:5-7`; `robot_learning/scenario/observations.py:18-35`.
  4. **Discriminating evidence:** Enumerate both inverse-kinematic solutions over the full official radius-angle domain, then forward-simulate each solution and measure residual distance and joint-limit margin.

- **[Reasoned implication]** Each reachable target generally has elbow-up and elbow-down solutions. The two branches have different joint trajectories, velocities, torques, and proximity to the shoulder limits even when they produce the same end-effector point. The four branch-error features make branch selection observable to the policy, but do not force it to remain on one branch. [Sources: `robot_learning/scenario/observations.py:18-47`; `contracts/robots/two_joint_arm.xml:12-19`]
  1. **Decision relevance:** A controller can trade off shorter motion, lower peak torque, and larger joint-limit margin against branch switching; aggregate success alone cannot identify which behavior succeeded.
  2. **Assumptions:** The policy can use the branch features and the dynamics do not introduce a hidden obstacle between branches.
  3. **Source references:** `robot_learning/scenario/observations.py:18-47`; `robot_learning/scenario/environment.py:122-143`.
  4. **Discriminating evidence:** Record branch identity, joint-limit margin, path length, peak action, and branch changes for successful and failed episodes.

- **[Reasoned implication]** The Jacobian loses authority at fully extended or folded configurations because its determinant is proportional to `0.12*0.10*sin(q2)`. Official targets avoid exact singular radii, but the straight reset is a singular configuration; the first action must create useful elbow motion before Cartesian steering becomes well-conditioned. [Sources: `contracts/robots/two_joint_arm.xml:12-19`; `robot_learning/scenario/environment.py:109-114`]
  1. **Decision relevance:** Early-episode behavior and acceleration away from the reset can dominate reach time; a policy that only reacts to Cartesian error may be weaker than one that accounts for joint configuration.
  2. **Assumptions:** Standard two-link Jacobian kinematics apply and “authority” means local mapping from joint velocity/torque to xy motion.
  3. **Source references:** `contracts/robots/two_joint_arm.xml:12-19`; `robot_learning/scenario/environment.py:109-114`.
  4. **Discriminating evidence:** Measure the smallest singular value of the Jacobian and end-effector displacement during the first control steps across target angles.

### Dynamics and control authority

- **[Reasoned implication]** With gravity absent, the primary dynamics are configuration-dependent link inertia, the 0.01 armature contribution, viscous damping torque proportional to angular velocity, and bounded motor torque. The same normalized action can therefore produce different accelerations at different configurations and can overshoot a target even though the target is static. [Sources: `contracts/robots/two_joint_arm.xml:1-2,12-19,30-33`]
  1. **Decision relevance:** Reach speed and the final 1 cm hold may require different control regimes: large motion authority for convergence, then low-velocity damping and corrections for stabilization.
  2. **Assumptions:** MuJoCo’s derived inertial model is deterministic and no unmodeled external forces act.
  3. **Source references:** `contracts/robots/two_joint_arm.xml:1-2,12-19,30-33`.
  4. **Discriminating evidence:** Apply controlled action pulses at representative configurations and estimate acceleration, damping decay, peak speed, and stopping distance.

- **[Reasoned implication]** The 20 ms zero-order-held action interval is long relative to the 1 cm tolerance: an end-effector moving at only 0.5 m/s traverses 1 cm in 20 ms. A policy can be inside the band at one observation and outside it at the next unless it converges with sufficiently small velocity and acceleration. [Sources: `contracts/task_spec.py:8-11`; `robot_learning/scenario/environment.py:130-143`]
  1. **Decision relevance:** The first campaign decision should distinguish fast arrival from low-speed settling; minimizing time-to-first-entry is not equivalent to maximizing complete-hold success.
  2. **Assumptions:** The command is held constant for all ten internal steps and the post-step distance is the relevant task sample.
  3. **Source references:** `contracts/robots/two_joint_arm.xml:1-2`; `contracts/task_spec.py:8-11`; `robot_learning/scenario/environment.py:130-143`.
  4. **Discriminating evidence:** Compare first-entry time, velocity at first entry, maximum subsequent distance, and hold interruptions.

- **[Reasoned implication]** The implemented success counter samples continuity only at control boundaries. Thus a trajectory can cross outside the tolerance between samples without resetting the counter, unless the protected evaluator applies additional within-step checks. [Sources: `contracts/scenario.md:9-14`; `robot_learning/scenario/environment.py:130-143`]
  1. **Decision relevance:** The interpretation changes how much high-frequency stabilization is necessary and how diagnostics should define a “complete uninterrupted hold.”
  2. **Assumptions:** The readable scenario environment matches the protected official interaction semantics.
  3. **Source references:** `contracts/scenario.md:9-14`; `robot_learning/scenario/environment.py:134-168`.
  4. **Discriminating evidence:** Compare sampled distances at 50 Hz with the within-step trajectory from MuJoCo, and compare the result with a task-reference or official evaluation outcome.

### Task geometry and coupled capabilities

- **[Reasoned implication]** Success is a sequential conjunction: reach the 1 cm ball, enter with manageable residual velocity, and maintain the ball for 100 samples. Reaching without convergence fails; convergence without maintaining the band fails; a stable local controller is insufficient if the policy cannot select a valid branch or reach all target angles within 500 steps. [Sources: `contracts/scenario.md:9-20`; `robot_learning/scenario/environment.py:134-168`]
  1. **Decision relevance:** Evaluation must separate first reach, settling, and hold interruption rather than optimize a single final distance or reward.
  2. **Assumptions:** The target remains fixed and no target interaction changes the mechanics.
  3. **Source references:** `contracts/scenario.md:16-27`; `robot_learning/scenario/evaluation.py:51-106`.
  4. **Discriminating evidence:** Use first-reach step, minimum distance, final distance, maximum held steps, in-tolerance steps, and hold interruptions by target radius and angle.

- **[Reasoned implication]** The initial state creates a systematic transient: the arm begins at maximum extension and the target is sampled afterward. Targets near radius 0.20 m and angle 0 are initially close but still outside tolerance; targets near the opposite direction require a large reorientation. The same policy must therefore solve easy near-collinear cases and long, dynamically different rotations. [Sources: `robot_learning/scenario/environment.py:102-120`; `contracts/task_spec.py:6`]
  1. **Decision relevance:** Performance should be conditioned on initial distance and angular displacement, not only target radius.
  2. **Assumptions:** Reset is always the stated zero state and target sampling is independent of policy history.
  3. **Source references:** `robot_learning/scenario/environment.py:102-120`; `robot_learning/scenario/evaluation.py:90-106`.
  4. **Discriminating evidence:** Bin episodes by initial distance, target angle, and selected branch; compare reach and hold failure rates.

- **[Reasoned implication]** The training default samples only radii 0.14–0.20 m, whereas official evaluation spans 0.06–0.20 m. A policy can learn the outer annulus while being under-tested on the more folded, lower-radius configurations. [Sources: `robot_learning/training/environment.py:14-19`; `contracts/task_spec.py:6`]
  1. **Decision relevance:** Generalization to the inner annulus is a direct campaign risk even if training success is high.
  2. **Assumptions:** The current training environment remains the recipe used for the candidate and official evaluation uses the full contract range.
  3. **Source references:** `robot_learning/training/environment.py:14-19`; `contracts/scenario.md:7-14`.
  4. **Discriminating evidence:** Evaluate matched panels stratified by radius, especially 0.06–0.14 m, with the same policy and seeds.

### Qualitatively different failure classes

- **[Reasoned implication]** The coupled system creates at least four distinguishable failure classes: (1) geometric or joint-limit failure, (2) slow or poorly conditioned convergence from the reset, (3) dynamic overshoot or insufficient braking at first entry, and (4) late hold interruption caused by residual motion, control discretization, or hidden task time. A single episode failure does not identify which mechanism occurred. [Sources: `contracts/robots/two_joint_arm.xml:12-19,30-33`; `robot_learning/scenario/environment.py:134-168`; `robot_learning/scenario/evaluation.py:90-106`]
  1. **Decision relevance:** The first scientific interpretation should classify failures by mechanism before changing morphology, observation, reward, or learning method.
  2. **Assumptions:** Distance, q, qdot, action, branch, and timing diagnostics can be collected without changing the policy-environment contract.
  3. **Source references:** `robot_learning/scenario/evaluation.py:90-106`; `robot_learning/scenario/observations.py:27-49`; `robot_learning/scenario/environment.py:134-168`.
  4. **Discriminating evidence:** Assign each episode its earliest failure class using reachability residual, joint-limit margin, Jacobian conditioning, first-entry velocity, peak overshoot, and hold interruption timing.

### Observability and measurable behavior

- **[Reasoned implication]** For the physical plant, joint positions, joint velocities, known link lengths, and relative target vector are sufficient to reconstruct the planar configuration and target location; the observation is therefore close to Markov for deterministic motion. It is not Markov for the full task automaton because accumulated hold duration is hidden. [Sources: `robot_learning/scenario/observations.py:27-49`; `robot_learning/scenario/environment.py:136-159`]
  1. **Decision relevance:** A memoryless controller can regulate current distance but may not explicitly know how long stability has already been maintained; recurrence or conservative stabilization may affect hold reliability.
  2. **Assumptions:** There is no observation noise, target motion, hidden contact state, or stochastic simulator state.
  3. **Source references:** `robot_learning/scenario/observations.py:27-49`; `robot_learning/scenario/environment.py:136-159`; `contracts/policy_runtime.py:163-177`.
  4. **Discriminating evidence:** Compare policies with and without temporal memory while matching actions and measure failures caused by late hold exits.

- **[Reasoned implication]** The observation exposes redundant Cartesian and inverse-kinematic information but not actual actuator torque, generalized acceleration, contact force, energy, or hold progress. It also omits explicit absolute target radius and angle, although q and the relative vector allow them to be derived. [Sources: `robot_learning/scenario/observations.py:27-49`; `robot_learning/scenario/environment.py:160-168`]
  1. **Decision relevance:** Apparent failure to stabilize may be an unobserved-dynamics problem rather than a reachability problem; diagnostic instrumentation should measure physical quantities unavailable to the policy.
  2. **Assumptions:** The policy input is exactly the exported 11-value observation and no wrapper augments it.
  3. **Source references:** `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/policy_io.py:7-17`.
  4. **Discriminating evidence:** Log q, qdot, action, transmitted torque, distance, Cartesian velocity, Jacobian conditioning, and hold counter on the same trajectories.

- **[Reasoned implication]** The scientifically meaningful behavior record spans the complete trajectory: target radius and angle; q and qdot; end-effector position and velocity; distance and radial/tangential error; branch identity and joint-limit margin; action and transmitted torque; first-entry and settling time; peak speed and overshoot; in-tolerance duration; interruptions; and terminal success. Reward is a learning signal, not a physical outcome. [Sources: `robot_learning/scenario/evaluation.py:51-106`; `robot_learning/training/reward.py:47-107`]
  1. **Decision relevance:** These quantities distinguish geometric failure, slow convergence, overshoot, branch/limit failure, and hold instability, which require different scientific explanations.
  2. **Assumptions:** The logged simulator state is synchronized with post-control-step evaluation.
  3. **Source references:** `robot_learning/scenario/evaluation.py:90-106`; `robot_learning/training/reward.py:47-107`.
  4. **Discriminating evidence:** Attribute each failed episode to the earliest violated requirement and check that the attribution predicts later success or failure.

## Unknowns

### Effective inertial and numerical model

- **[Unresolved quantity]** The effective link masses, inertia tensors, composite joint inertia, MuJoCo integrator, and any default friction or solver behavior are not specified explicitly in the readable XML. They determine acceleration, stopping distance, and the real meaning of the nominal +/-5 N m authority. [Sources: `contracts/robots/two_joint_arm.xml:1-33`; `robot_learning/scenario/environment.py:52-57`]
  1. **Decision relevance:** This can change whether the first method should emphasize direct reactive control, explicit dynamics compensation, or conservative stabilization.
  2. **Assumptions:** MuJoCo defaults are active exactly as loaded and are stable across training and evaluation processes.
  3. **Source references:** `contracts/robots/two_joint_arm.xml:1-33`; `robot_learning/scenario/environment.py:52-57`.
  4. **Discriminating evidence:** Read the loaded `MjModel` mass, inertia, damping, actuator and integrator fields; then fit local pulse-response models at extended, folded, and intermediate configurations.

### Protected distribution and semantics equivalence

- **[Unresolved quantity]** The contract states a uniform target distribution, while the readable scenario sampler is uniform in radius and angle rather than uniform with respect to planar area. The exact protected evaluator sampler and whether it checks only post-control-step distances are not available in the accessible definitions. [Sources: `contracts/scenario.md:7-14,34-38`; `robot_learning/scenario/environment.py:83-97,134-168`]
  1. **Decision relevance:** The distinction changes which radii are statistically important and whether a policy can rely on between-sample motion being unobserved.
  2. **Assumptions:** The protected assessment is authoritative and may differ from the research environment despite shared task constants.
  3. **Source references:** `contracts/scenario.md:7-14`; `contracts/task_spec.py:6`; `robot_learning/scenario/environment.py:83-97`.
  4. **Discriminating evidence:** Obtain target histograms and within-step success semantics from an allowed task-reference or official measurement, or reconcile the contract wording with the protected implementation.

### Temporal-policy sufficiency

- **[Unresolved quantity]** It is not established whether the hidden hold counter materially harms a memoryless policy under the current dynamics; the current baseline uses PPO `MlpPolicy`, while the runtime can carry recurrent state. [Sources: `robot_learning/train.py:22-23,127-136`; `contracts/policy_runtime.py:153-177`; `robot_learning/scenario/environment.py:136-159`]
  1. **Decision relevance:** This can change the priority between architecture changes and physical-control changes.
  2. **Assumptions:** Policies are compared under identical training allocation, target distribution, and exported observation semantics.
  3. **Source references:** `robot_learning/train.py:127-136`; `contracts/policy_runtime.py:163-177`.
  4. **Discriminating evidence:** Paired evaluation of matched memoryless and recurrent policies, with hold-interruption timing and near-threshold velocity as mechanism diagnostics.

### Realized branch and limit margins

- **[Unresolved quantity]** Existence of a valid inverse-kinematic solution does not establish that a learned trajectory will preserve adequate shoulder/elbow margin, avoid high-speed branch transitions, or remain stable near the inner-radius folded configurations. [Sources: `contracts/robots/two_joint_arm.xml:12-19`; `robot_learning/scenario/observations.py:18-47`]
  1. **Decision relevance:** If failures cluster at small joint-limit margins, the useful change is trajectory/branch management rather than more generic reach reward.
  2. **Assumptions:** The simulator state and both target branches can be logged without altering policy behavior.
  3. **Source references:** `robot_learning/scenario/observations.py:41-47`; `robot_learning/scenario/evaluation.py:90-106`.
  4. **Discriminating evidence:** Compute minimum joint-limit margin, branch error, Jacobian singular values, and branch-switch count for each target geometry.

## Decision-relevant synthesis

### Hold is a dynamical requirement, not just reachability

- **[Reasoned implication] Decision relevance:** The first campaign comparison should separate reaching, settling, and uninterrupted holding because the 1 cm band and 100-sample duration make residual velocity and correction timing decisive.
- **[Reasoned implication] Assumptions:** The current 20 ms action hold and post-step success counter represent official interaction semantics.
- **[Repository fact] Source references:** `contracts/scenario.md:9-20`; `contracts/task_spec.py:8-11`; `robot_learning/scenario/environment.py:130-168`.
- **[Unresolved quantity] Discriminating evidence:** First-entry velocity, settling time, maximum held steps, interruptions, and within-step distance traces, compared with task-reference or official semantics.

### The official annulus is reachable but has multiple physical solutions

- **[Reasoned implication] Decision relevance:** Branch choice, singularity escape from the straight reset, and joint-limit margin are likely to matter more than raw geometric reach; target-angle and radius-conditioned evidence should guide the first method decision.
- **[Reasoned implication] Assumptions:** Standard two-link planar kinematics and the stated +/-170 degree limits apply without hidden collision constraints.
- **[Repository fact] Source references:** `contracts/robots/two_joint_arm.xml:9-20`; `contracts/task_spec.py:6`; `robot_learning/scenario/observations.py:18-47`.
- **[Unresolved quantity] Discriminating evidence:** Enumerated branch feasibility plus trajectory logs of Jacobian conditioning, branch identity, peak torque, and limit margin.

### Dynamics are under-specified at the source level

- **[Reasoned implication] Decision relevance:** The choice between reactive learning and dynamics-aware stabilization cannot be justified from normalized actions alone; effective inertia and damping must be treated as a first-order uncertainty.
- **[Reasoned implication] Assumptions:** Unspecified MuJoCo defaults materially affect the loaded model and no separate human-owned dynamics contract supersedes the XML.
- **[Repository fact] Source references:** `contracts/robots/two_joint_arm.xml:1-2,12-19,30-33`; `robot_learning/scenario/environment.py:52-57`.
- **[Unresolved quantity] Discriminating evidence:** Loaded-model parameter extraction and controlled action-pulse identification across representative configurations.

### Training distribution does not cover the whole official geometry equally

- **[Reasoned implication] Decision relevance:** High training success is not evidence of 98% official success if the policy has not learned the inner 0.06–0.14 m annulus and all angular sectors.
- **[Reasoned implication] Assumptions:** The current training target range remains `(0.14, 0.20)` while official evaluation remains `(0.06, 0.20)`.
- **[Repository fact] Source references:** `robot_learning/training/environment.py:14-19`; `contracts/scenario.md:7-14`.
- **[Unresolved quantity] Discriminating evidence:** Matched, geometry-stratified evaluation reporting success and mechanism diagnostics by radius and angle.

### Observation is physically rich but task-time incomplete

- **[Reasoned implication] Decision relevance:** The policy can infer target geometry and current kinematic error, but cannot directly know accumulated hold time or actual torque; whether memory and extra physical feedback are necessary is an empirical decision.
- **[Reasoned implication] Assumptions:** No wrapper adds hidden state and the baseline remains memoryless unless deliberately changed.
- **[Repository fact] Source references:** `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/environment.py:160-168`; `robot_learning/train.py:127-136`.
- **[Unresolved quantity] Discriminating evidence:** Compare matched temporal-policy variants and correlate failure timing with qdot, action, torque, distance, and hidden hold progress.
