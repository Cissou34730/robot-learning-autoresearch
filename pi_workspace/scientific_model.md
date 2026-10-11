## Established facts

### Embodied morphology and kinematics

- **[Repository fact]** The robot is a planar serial arm with two revolute degrees of freedom. The shoulder and elbow hinge axes are both the world z axis; the elbow angle is relative to the upper arm, while the shoulder angle is relative to the base. The link lengths are \(L_1=0.12\) m and \(L_2=0.10\) m. The end-effector site is at the distal end of the forearm, in the z=0.02 m plane. **Source:** `contracts/robots/two_joint_arm.xml:9-23`; `contracts/robots/two_joint_arm.py:3-7`.

- **[Repository fact]** With joint coordinates \(q=(q_1,q_2)\), the endpoint position relative to the base is
  \(x=L_1\cos q_1+L_2\cos(q_1+q_2)\),
  \(y=L_1\sin q_1+L_2\sin(q_1+q_2)\),
  \(z=0.02\) m. Each joint has an authored range of -170 to 170 degrees. **Source:** `contracts/robots/two_joint_arm.xml:12-20`.

- **[Repository fact]** Ignoring joint limits, the geometric workspace is the annulus \(0.02\leq r\leq0.22\) m. The planar Jacobian has determinant \(L_1L_2\sin q_2\), so the fully extended and fully folded configurations are kinematic singularities. The reset state \(q=(0,0)\) is fully extended and therefore singular. **Source:** the link geometry in `contracts/robots/two_joint_arm.xml:12-20`; the forward-kinematic consequence follows directly from those definitions.

- **[Repository fact]** For a target \((x_t,y_t)\) in the annulus, the two nominal inverse-kinematic branches are
  \(q_2=\mathord{+/-}\arccos((r^2-L_1^2-L_2^2)/(2L_1L_2))\), with
  \(q_1=\operatorname{atan2}(y_t,x_t)-\operatorname{atan2}(L_2\sin q_2,L_1+L_2\cos q_2)\). The observation code explicitly constructs both the positive-elbow and negative-elbow solutions. **Source:** `robot_learning/scenario/observations.py:18-35`.

### Simulator and actuation

- **[Repository fact]** MuJoCo is configured with zero gravity and an integration timestep of 0.002 s. Policy actions are two float values in [-1,1], are clipped to that interval, copied directly into the two motor controls, and are held constant for 10 MuJoCo steps. The resulting policy control interval is 0.020 s (50 Hz). **Source:** `contracts/robots/two_joint_arm.xml:1-3,30-33`; `contracts/task_spec.py:6-11`; `robot_learning/scenario/environment.py:56,122-133`; `robot_learning/scenario/policy_io.py:11-16`.

- **[Repository fact]** Each hinge motor has gear 5 and control range [-1,1], so the actuator command supplies a bounded nominal joint torque of approximately +/-5 in MuJoCo torque units, subject to the model's transmission and dynamics. Each joint has damping 0.5 and armature 0.01. **Source:** `contracts/robots/two_joint_arm.xml:13-18,30-33`.

- **[Repository fact]** The XML does not add actuator state, tendons, gravity, or task contact. The plane, base, and target are non-colliding; the target is a mocap body and the distance calculation is between the end-effector site and mocap position. Thus the task is free-space positioning rather than grasping or contact manipulation. **Source:** `contracts/robots/two_joint_arm.xml:4-11,25-27`; `robot_learning/scenario/environment.py:75-80`.

- **[Repository fact]** The physical state is advanced only after a command is applied; no action interpolation is implemented between policy updates. Joint positions and velocities are reset to zero, MuJoCo forward dynamics is evaluated, and then the target is sampled. **Source:** `robot_learning/scenario/environment.py:102-120,122-134`.

### Task geometry and outcome

- **[Repository fact]** Official targets have radius uniformly sampled from 0.06 to 0.20 m and angle uniformly sampled over [-pi, pi]. The target is placed in the arm's z=0.02 m plane. Success requires the Euclidean end-effector-target distance to be at most 0.01 m for 2.0 uninterrupted seconds. At 0.020 s per policy step this is 100 consecutive in-tolerance control steps; an episode is truncated after 500 steps. **Source:** `contracts/scenario.md:7-22`; `contracts/task_spec.py:6-11`; `robot_learning/scenario/environment.py:83-97,134-159`.

- **[Repository fact]** Since target and endpoint share z, the tolerance is a 1 cm planar disk. The target radial interval is inside the nominal annulus, and even its 1 cm radial tolerance margin remains between 0.02 and 0.22 m. The full angular range therefore asks for all azimuths, not only a preferred workspace sector. **Source:** `contracts/scenario.md:7-14`; `contracts/robots/two_joint_arm.py:5-7`; `robot_learning/scenario/environment.py:90-97`.

- **[Repository fact]** Any excursion outside the tolerance resets the current held-step count to zero. Termination occurs only when the count reaches 100; partial progress does not count as success. **Source:** `robot_learning/scenario/environment.py:136-159`.

- **[Repository fact]** The baseline training environment samples only radii 0.14 to 0.20 m, whereas evaluation uses the official 0.06 to 0.20 m range. The reward combines distance progress, closeness, hold progress, a completion bonus, and a small action cost. **Source:** `robot_learning/training/environment.py:14-19`; `robot_learning/training/reward.py:16-25,47-107`.

### Sensing and control interface

- **[Repository fact]** The policy observation has 11 values in this order: two joint positions, two joint velocities, the three-dimensional endpoint-to-target error, and four wrapped angular errors to the two inverse-kinematic branches. It contains no observation noise or explicit delay. **Source:** `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/policy_io.py:11-16`.

- **[Repository fact]** The target's absolute x-y position is not sent as a separate field, but it is reconstructible from the known forward kinematics, the observed joint positions, and the observed endpoint-to-target vector. The target radius, target angle, distance norm, held-step count, episode step count, and previous action are not explicit observation fields. **Source:** `robot_learning/scenario/observations.py:27-49`; `robot_learning/scenario/environment.py:136-168`.

- **[Repository fact]** Evaluation records success, first in-tolerance step, minimum and final distance, maximum held steps, in-tolerance steps, and hold interruptions, but these diagnostics do not alter the task outcome. The official objective is at least 196 successes in a fixed 200-episode panel. **Source:** `contracts/scenario.md:23-31`; `robot_learning/scenario/evaluation.py:40-125`.

## Physical consequences

### Reaching and stabilization are one coupled control problem

- **[Reasoned implication]** A controller must first move through a transient reach and then regulate endpoint error tightly enough that every one of the next 100 sampled states remains inside the 1 cm disk. A low minimum distance or a first entry into the disk is not sufficient; residual velocity, damping, action quantization at 50 Hz, and target-relative geometry determine whether entry becomes a complete hold.
  - **Decision relevance:** This can change whether early research should prioritize fast reaching, low-velocity convergence, or explicit hold robustness, and which diagnostics should rank candidates.
  - **Assumptions:** The simulator semantics are exactly those in `TwoJointArmReachEnv`; no unmodeled termination or contact effect intervenes.
  - **Source references:** `contracts/scenario.md:12-22`; `robot_learning/scenario/environment.py:134-168`; `robot_learning/scenario/evaluation.py:90-105`.
  - **Discriminating evidence:** Per-episode first-entry step, minimum distance, maximum held steps, interruption count, and the distance trace distinguish reach failure from convergence or stabilization failure.

### Workspace geometry makes branch choice and the initial singularity consequential

- **[Reasoned implication]** Each non-boundary target has an elbow-open and elbow-folded solution. The official radii avoid the radial workspace boundaries, so both nominal branches exist and have different joint postures, velocities, and torque demands. The arm nevertheless starts at \(q_2=0\), where the Jacobian loses rank; initial motion cannot independently generate arbitrary Cartesian velocity until the controller leaves that configuration. A branch that is easy to reach is not necessarily the branch that is easiest to hold.
  - **Decision relevance:** This can change whether policy inputs should expose branch structure, whether candidate behavior should be compared by branch, and whether initial singular escape is treated as a distinct failure class.
  - **Assumptions:** The planar kinematics above remain valid under the authored joint limits and the controller can move away from the reset singularity.
  - **Source references:** `contracts/robots/two_joint_arm.xml:12-20`; `robot_learning/scenario/observations.py:18-47`; `robot_learning/scenario/environment.py:102-114`.
  - **Discriminating evidence:** Log the sign and magnitude of elbow angle, the four IK errors, endpoint Jacobian determinant, and target angle/radius alongside success and hold interruptions.

### Torque authority and damping govern transient and steady-state behavior

- **[Reasoned implication]** The command is a bounded torque-like input, not a desired position or velocity. The effective motion results from the configuration-dependent inertia, 0.5 joint damping, 0.01 armature, and the +/-5 nominal motor limit. Near the 0.20 m outer radius, small endpoint errors can require coordinated shoulder and elbow torque; near the reset singularity, joint motion may initially produce poor Cartesian correction. Saturation or excessive speed can turn a reachable target into a failed hold even when static geometry permits it.
  - **Decision relevance:** This can change action scaling, exploration magnitude, policy regularization, and the value of velocity-aware stabilization.
  - **Assumptions:** Motor gear maps control to joint generalized force as specified by MuJoCo, and no hidden actuator dynamics are present.
  - **Source references:** `contracts/robots/two_joint_arm.xml:1-3,13-18,30-33`; `robot_learning/scenario/environment.py:125-133`.
  - **Discriminating evidence:** Record commanded controls, joint velocities, endpoint speed, inferred acceleration, and whether controls clip; compare these quantities by target radius and IK branch.

### Hidden hold progress creates a task-level state beyond physical state

- **[Reasoned implication]** The mechanical state is represented by joint position and velocity plus the fixed target, but the success automaton also depends on whether the previous control state was in tolerance and on the accumulated consecutive hold count. The policy cannot directly know whether it is at step 1 or step 99 of a valid hold. It can still maintain the endpoint using the observed physical error and velocity, but it cannot directly condition behavior on remaining hold time.
  - **Decision relevance:** This can change the case for memory, a time/hold feature, or a policy that deliberately reduces motion after entry; it also prevents interpreting high one-step reach rates as high episode success.
  - **Assumptions:** The policy receives exactly the 11 listed values and no wrapper adds hidden task telemetry.
  - **Source references:** `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/environment.py:70-73,136-168`.
  - **Discriminating evidence:** Compare physical state and control traces at first entry, after 50 held steps, and after interruptions; measure the conditional probability of completing the hold after entry.

### Training distribution and reward shape can bias physical behavior

- **[Reasoned implication]** The baseline recipe omits the official inner-radius band 0.06-0.14 m. A policy can therefore learn successful outer-workspace behavior while remaining untested on nearer targets, where the elbow geometry and branch basins differ. The dense progress and hold terms provide learning signals, but they are not the official criterion and can reward approach or partial hold without complete success.
  - **Decision relevance:** This can change whether candidate selection should be stratified by radius and whether the initial training distribution is considered scientifically adequate for the official goal.
  - **Assumptions:** The baseline training environment and reward are used without a separate curriculum or task randomization.
  - **Source references:** `robot_learning/training/environment.py:14-19`; `robot_learning/training/reward.py:47-107`; `contracts/scenario.md:7-22`.
  - **Discriminating evidence:** Evaluate identical candidates by radius bins and report first reach, hold completion, and interruption statistics rather than pooled success alone.

### Scientifically meaningful behavior quantities

- **[Reasoned implication]** The most informative physical trajectory quantities are target radius and angle; joint positions, velocities, and proximity to joint limits; elbow branch and Jacobian determinant; endpoint error vector and norm; commanded torque and clipping; endpoint speed and settling time; first in-tolerance step; uninterrupted hold length; interruption count; and final success. Together they separate geometric reachability, transient control, convergence, and stabilization rather than collapsing them into reward.
  - **Decision relevance:** These quantities determine whether a candidate change addresses the failure mechanism relevant to the 98% objective.
  - **Assumptions:** The corresponding state and action traces can be recorded without changing the policy or simulator semantics.
  - **Source references:** `robot_learning/scenario/evaluation.py:45-105`; `robot_learning/scenario/environment.py:125-168`; kinematic quantities follow from `contracts/robots/two_joint_arm.xml:12-20`.
  - **Discriminating evidence:** A trajectory-level evaluation artifact containing these quantities, stratified by target geometry and branch, supports or weakens each failure-class attribution.

## Unknowns

### Runtime-resolved mass matrix and numerical dynamics

- **[Unresolved quantity]** The XML specifies link geometry, damping, armature, gravity, and timestep, but does not explicitly specify body mass, density, inertia, integrator, solver settings, or other numerical defaults. MuJoCo therefore resolves part of the mass matrix and numerical dynamics from defaults and inferred geom properties. The exact configuration-dependent acceleration and settling time are not established by source inspection alone.
  - **Decision relevance:** This can change judgments about torque sufficiency, policy transfer across branches, and whether a failure is physical or numerical.
  - **Assumptions:** The native MuJoCo 3.12.0 runtime and its defaults are the authoritative simulator, as stated by the repository environment contract.
  - **Source references:** `contracts/robots/two_joint_arm.xml:1-33`; `AGENTS.md` environment section.
  - **Discriminating evidence:** A simulator characterization that reports compiled body masses/inertias, actuator generalized forces, and short open-loop responses at representative configurations would resolve the quantities.

### Effective control authority at difficult configurations

- **[Unresolved quantity]** The nominal +/-5 motor torque does not establish whether the arm can reach and then settle every official target within 500 policy steps, because the required joint torques depend on configuration, inertia, damping, and the chosen IK branch. The margin near the outer radius and around the initial singularity is unknown.
  - **Decision relevance:** This can change whether research should pursue policy improvements, torque/action conditioning, or a different branch preference.
  - **Assumptions:** The official target distribution and reset state are used, and the actuator remains unsaturated except where logged.
  - **Source references:** `contracts/scenario.md:7-22`; `contracts/robots/two_joint_arm.xml:12-18,30-33`; `robot_learning/scenario/environment.py:102-159`.
  - **Discriminating evidence:** For fixed target panels, compare success and hold traces with control saturation, joint speed, endpoint speed, and branch labels; saturation correlated with failures supports an authority limitation.

### Branch basins and singular escape

- **[Unresolved quantity]** It is not established which IK branch a learned controller selects for each target, whether it switches branches during an episode, or whether the reset singularity causes a measurable subset of angle-dependent failures. The two branches are kinematically available, but dynamic cost and learned basin selection are not defined by the contracts.
  - **Decision relevance:** This can change whether branch-aware diagnostics or branch-conditioned learning is needed before judging aggregate performance.
  - **Assumptions:** Both branch solutions remain within the active joint limits for the sampled targets; exact limit behavior is not assumed from the analytical formula alone.
  - **Source references:** `contracts/robots/two_joint_arm.xml:12-18`; `robot_learning/scenario/observations.py:18-47`; `robot_learning/scenario/environment.py:109-114`.
  - **Discriminating evidence:** Record elbow sign, IK residuals, Jacobian determinant, target angle, and first-entry/hold outcome for every episode.

### Stability margin during the complete hold

- **[Unresolved quantity]** The definitions specify the 1 cm boundary and 100-sample duration but do not establish the closed-loop error distribution, residual oscillation amplitude, or sensitivity to target location at first entry. A policy may reach quickly yet have too little stability margin for uninterrupted success.
  - **Decision relevance:** This can change candidate ranking and whether optimization should value lower endpoint speed and error variance over faster first reach.
  - **Assumptions:** Distance is evaluated only at the post-action control samples, exactly as in the environment.
  - **Source references:** `robot_learning/scenario/environment.py:131-159`; `contracts/task_spec.py:8-11`.
  - **Discriminating evidence:** Measure endpoint distance and speed for all 100 hold samples, including the minimum distance to the tolerance boundary and the number/timing of near-boundary samples.

### Observability of task progress to a learned controller

- **[Unresolved quantity]** The physical target is recoverable in principle from joint positions and endpoint error, but the policy's effective access depends on its preprocessing and learned representation. The hold counter, episode time, target sampling coordinates, and action history are unavailable in the raw observation; it is unknown whether a feed-forward policy can robustly infer all useful phase information from the current physical state.
  - **Decision relevance:** This can change whether memory or explicit phase information is worth considering, and whether failures are attributed to sensing rather than actuation.
  - **Assumptions:** Observation normalization may alter numerical conditioning but not information content; no external recurrent state is supplied.
  - **Source references:** `robot_learning/scenario/observations.py:27-49`; `robot_learning/training/train.py:110-116` for observation normalization.
  - **Discriminating evidence:** Compare policies with identical physical trajectories at different hold counts, and test whether adding memory changes hold completion without changing reach behavior.

## Decision-relevant synthesis

### Official coverage is broader than the baseline training geometry

- **[Reasoned implication] Decision relevance:** The baseline trains on 0.14-0.20 m while the official objective includes 0.06-0.20 m; pooled performance can conceal a systematic near-target deficit.
- **Assumptions:** The baseline environment is the starting recipe and official evaluation uses the contract distribution.
- **Source references:** `robot_learning/training/environment.py:14-19`; `contracts/scenario.md:7-22`.
- **Discriminating evidence:** Radius-stratified success, first reach, and hold-interruption measurements.

### Success is dominated by a 2-second stability requirement

- **[Reasoned implication] Decision relevance:** First reach is only an intermediate event; the decisive capability is maintaining a 1 cm endpoint error for 100 consecutive 20 ms samples.
- **Assumptions:** The post-action distance and reset-on-excursion semantics remain authoritative.
- **Source references:** `contracts/task_spec.py:8-11`; `robot_learning/scenario/environment.py:134-159`.
- **Discriminating evidence:** Full hold distance traces, maximum held steps, and interruption timing.

### Torque and inertial margins are not established

- **[Unresolved quantity] Decision relevance:** A failure near the outer workspace or during stabilization could require a policy change or could be an actuator/dynamics limit; the source does not distinguish these.
- **Assumptions:** MuJoCo's runtime-resolved mass and numerical defaults are used without further overrides.
- **Source references:** `contracts/robots/two_joint_arm.xml:1-33`; `AGENTS.md` environment section.
- **Discriminating evidence:** Compiled inertial/actuator characterization paired with control clipping, joint speed, and endpoint error traces.

### Multiple IK branches and the reset singularity may partition behavior

- **[Reasoned implication] Decision relevance:** Aggregate success may depend on which elbow branch the policy discovers and on its ability to leave the fully extended reset state; branch-specific failure can be hidden by pooled metrics.
- **Assumptions:** The analytical branches are dynamically available under the joint limits.
- **Source references:** `robot_learning/scenario/observations.py:18-47`; `contracts/robots/two_joint_arm.xml:12-20`; `robot_learning/scenario/environment.py:109-114`.
- **Discriminating evidence:** Branch labels, Jacobian determinant, target angle/radius, and outcome per episode.

### The observation exposes geometry but not hold phase

- **[Unresolved quantity] Decision relevance:** The policy can reconstruct target-relative geometry and velocity, but not remaining hold time; whether this limits 98% success is an empirical control/representation question.
- **Assumptions:** The raw 11-value observation is the complete policy input.
- **Source references:** `robot_learning/scenario/observations.py:11-49`; `robot_learning/scenario/environment.py:136-168`.
- **Discriminating evidence:** Conditional completion probability after first entry and comparison of feed-forward versus stateful policies using identical task panels.
