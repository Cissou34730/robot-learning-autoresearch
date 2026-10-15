## Established facts

### System boundary and authoritative objective

- **Repository fact.** The system is a fixed two-joint arm in a MuJoCo simulator. The
  human objective is a learned policy with at least 98% episode success under the
  official target distribution; success is not a high reward or a near miss, but
  completion of one uninterrupted hold. [Source: `contracts/scenario.md#Official task`,
  `#Success criterion`, `#Immutable task boundary`]
- **Repository fact.** The official assessment uses one frozen policy on 200 fixed-panel
  episodes, with at most 500 control steps per episode; at least 196 successes are
  required. Development panels are not pooled with that result. [Source:
  `contracts/scenario.md#Official final assessment`]
- **Repository fact.** The physical model is the XML loaded by
  `TwoJointArmReachEnv`; policy and reward code can change during research, but the
  official robot, physics, interaction semantics, target distribution, and success
  definition are human-owned contracts. [Sources:
  `contracts/robots/two_joint_arm.xml#L1-L32`,
  `contracts/scenario.md#Immutable task boundary`,
  `robot_learning/scenario/environment.py#L33-L58`]

### Morphology, coordinates, and kinematics

- **Repository fact.** The base is fixed at the world origin. The shoulder and elbow
  are revolute joints about the world/body \(z\)-axis, so the moving mechanism has two
  generalized coordinates: shoulder angle \(q_1\) and elbow angle \(q_2\). The upper
  link is 0.12 m and the forearm is 0.10 m; the end-effector site is at the forearm
  tip. [Source: `contracts/robots/two_joint_arm.xml#L9-L22`;
  `contracts/robots/two_joint_arm.py#L3-L8`]
- **Repository fact.** Both joint ranges are declared as \([-170^\circ,170^\circ]\).
  The link visuals are capsules with radii 0.015 m and 0.012 m, while the task
  endpoint is the site position, not a surface-contact point. [Source:
  `contracts/robots/two_joint_arm.xml#L13-L20`]
- **Repository fact.** The target is a non-colliding, mocap sphere and is placed at the
  same \(z\) coordinate as the endpoint. The plane, base, and target geometry have
  collision disabled where explicitly specified; the endpoint task is evaluated by
  Euclidean site-to-mocap distance. [Sources:
  `contracts/robots/two_joint_arm.xml#L5-L10`,
  `contracts/robots/two_joint_arm.xml#L24-L27`,
  `robot_learning/scenario/environment.py#L76-L81`,
  `robot_learning/scenario/environment.py#L91-L99`]

### Actuation, simulator, and interaction timing

- **Repository fact.** Each joint has a MuJoCo motor with control range \([-1,1]\) and
  gear 5. The environment clips the policy output to the same \([-1,1]\) box, writes
  it to `data.ctrl`, and advances the simulator for 10 physics steps before producing
  the next observation. [Sources: `contracts/robots/two_joint_arm.xml#L30-L32`,
  `robot_learning/scenario/environment.py#L117-L133`,
  `contracts/task_spec.py#L8`]
- **Repository fact.** The physics timestep is 0.002 s, so one policy control interval
  is 0.020 s (50 Hz), with the action held constant over its 10 substeps. The
  episode limit is 500 control intervals, or 10 s of simulated control time. [Sources:
  `contracts/robots/two_joint_arm.xml#L2`,
  `contracts/task_spec.py#L7-L8`,
  `robot_learning/scenario/environment.py#L50-L53`]
- **Repository fact.** Gravity is set to zero. Each joint declares damping 0.5 and
  armature 0.01. No actuator dynamics, springs, external disturbance, payload, or
  contact controller is declared in the human-owned XML. [Source:
  `contracts/robots/two_joint_arm.xml#L2`, `#L13-L19`]
- **Repository fact.** Reset sets both joint positions and velocities to zero,
  forwards the model, samples one target, and forwards again. The initial arm is
  therefore straight at \(q=(0,0)\), with the endpoint at approximately
  \((0.22,0,0.02)\) m before any action. [Source:
  `robot_learning/scenario/environment.py#L101-L115`,
  `contracts/robots/two_joint_arm.xml#L13-L22`]

### Target distribution and success mechanics

- **Repository fact.** Official targets have radius 0.06--0.20 m and full angular
  coverage. The current scenario implementation samples angle uniformly on
  \([-\pi,\pi]\), radius uniformly on \([0.06,0.20]\), and sets target \(z\) to the
  current endpoint \(z\). Thus its radial-coordinate distribution is not a
  uniform-area disk distribution. [Sources: `contracts/scenario.md#Official task`,
  `contracts/task_spec.py#L6`, `robot_learning/scenario/environment.py#L84-L99`]
- **Repository fact.** The tolerance is 0.01 m. At each control boundary, a distance
  at or below that threshold increments the held-step counter; any outside sample
  resets it to zero. The required duration is 2 s, implemented as
  `round(2.0 / 0.020) = 100` consecutive control steps. [Sources:
  `contracts/task_spec.py#L8-L12`,
  `robot_learning/scenario/environment.py#L54-L55`,
  `robot_learning/scenario/environment.py#L137-L161`]
- **Repository fact.** Success terminates immediately when the 100-step run is
  complete; otherwise the episode truncates at 500 control steps. The evaluator
  records success separately from Gymnasium termination and records target geometry,
  minimum/final distance, first reach, maximum held steps, time in tolerance, and
  interruptions. [Sources: `robot_learning/scenario/environment.py#L158-L169`,
  `robot_learning/scenario/evaluation.py#L47-L106`]

### Observation and command interface

- **Repository fact.** The default policy observation has 11 float32 values:
  \(q_1,q_2\), the two joint velocities, the three-dimensional endpoint-minus-target
  vector, and four wrapped angular errors to the open and folded inverse-kinematic
  solutions. [Sources: `robot_learning/scenario/observations.py#L10-L49`,
  `robot_learning/scenario/policy_io.py#L10-L16`]
- **Repository fact.** The inverse-kinematic features calculate
  \[
  \cos q_2=(r^2-l_1^2-l_2^2)/(2l_1l_2)
  \]
  and use \(q_2=\pm\arccos(\operatorname{clip}(\cos q_2,-1,1))\), with the
  corresponding shoulder angle. The observation therefore exposes both nominal
  elbow branches as desired-angle residuals, while the endpoint error directly
  exposes the task-space error. [Source: `robot_learning/scenario/observations.py#L14-L47`]
- **Repository fact.** The default action mapping is identity before environment
  clipping. The observation is recomputed after the ten MuJoCo substeps, and neither
  the held-step counter nor the reward is part of the default physical observation.
  [Sources: `robot_learning/scenario/policy_io.py#L10-L16`,
  `robot_learning/scenario/environment.py#L117-L169`]

## Physical consequences

### Two-link reaching is a coupled inverse-kinematic and trajectory problem

- **Reasoned implication.** In the task plane \(z=0.02\) m, the endpoint position is
  \[
  p(q)=\begin{bmatrix}
  0.12\cos q_1+0.10\cos(q_1+q_2)\\
  0.12\sin q_1+0.10\sin(q_1+q_2)\\
  0.02
  \end{bmatrix}.
  \]
  With unrestricted angles its radial workspace is the annulus 0.02--0.22 m, so the
  official 0.06--0.20 m radial band is inside the geometric annulus; the declared
  joint limits determine the available angular margin and configuration branch.
  Reaching still requires driving a selected configuration through a transient and
  arriving with sufficiently small velocity that the endpoint remains in the 1 cm
  ball. The task therefore couples reachability, trajectory shaping, convergence,
  and stabilization; a low minimum distance alone is insufficient.
- **Decision relevance.** Early campaign choices can differ between a reach-limited
  policy, a policy that reaches but oscillates, and a policy that stabilizes but
  cannot do so within 10 s. The first comparison should preserve these distinctions
  rather than use reward or minimum distance as a surrogate for episode success.
- **Assumptions.** This follows from point-distance success, the 100-step
  uninterrupted hold, bounded motor commands, and no external target motion or
  disturbance.
- **Source references.** `contracts/scenario.md#Official task`;
  `contracts/task_spec.py#L7-L12`; `robot_learning/scenario/environment.py#L117-L169`;
  `robot_learning/scenario/evaluation.py#L76-L106`.
- **Discriminating evidence.** Across complete episodes, the relevant separation is
  first-entry time, minimum distance, endpoint velocity at first entry, the full
  distance trace during the 100-step run, interruption count, and whether the
  failure is truncation or an interrupted hold. These quantities support or weaken
  reach, convergence, and stabilization explanations without assigning cause from
  success rate alone.

### The two inverse-kinematic branches create distinct valid behaviors

- **Reasoned implication.** For a target radius \(r\), the nominal solutions are
  \(q_2=\pm\beta\), where
  \(\beta=\arccos((r^2-l_1^2-l_2^2)/(2l_1l_2))\), with
  \(q_1=\theta-\operatorname{atan2}(l_2\sin q_2,l_1+l_2\cos q_2)\), modulo
  \(2\pi\). The target specifies no end-effector orientation, so open-elbow and
  folded-elbow solutions are physically equivalent task solutions when within limits.
- **Decision relevance.** A policy representation or controller that commits to one
  branch may be robust for some angles and near a joint limit for others. Branch
  selection, branch switching, and approach trajectory can change learning difficulty
  and hold reliability.
- **Assumptions.** The planar formula applies because the target and endpoint share
  \(z\), the base is fixed, and there are no task obstacles or orientation
  requirements. The stated target band is inside the unrestricted annulus, but
  limit margin still varies with \(r,\theta\).
- **Source references.** `contracts/robots/two_joint_arm.xml#L9-L22`;
  `robot_learning/scenario/observations.py#L14-L47`;
  `robot_learning/scenario/environment.py#L91-L99`.
- **Discriminating evidence.** Log the selected branch from the four IK residuals,
  joint-limit margin, endpoint error, and hold interruptions by target angle and
  radius. A consistent advantage of one branch, or failures concentrated at small
  limit margin, supports this mechanism; uniform failures with ample margin weaken
  it.

### Bounded motor torque, damping, and armature shape the transient

- **Reasoned implication.** With MuJoCo motor gear 5 and clipped command
  \(u_i\in[-1,1]\), each actuator supplies a bounded generalized motor contribution
  whose nominal gear-scaled magnitude is 5 in the joint coordinates. Damping removes
  velocity-dependent energy, while armature adds rotor inertia. The resulting
  acceleration and overshoot depend on configuration-dependent link inertia and
  coupling, not on the action value alone.
- **Decision relevance.** If the arm cannot rotate and bend rapidly enough, a policy
  may fail through late arrival or horizon truncation; if it can but is aggressively
  driven, it may enter the tolerance ball with enough velocity to leave it. The useful
  learning/control direction differs in those cases.
- **Assumptions.** This uses standard MuJoCo motor and joint semantics for the loaded
  XML; the exact generalized force and limit reactions still depend on the compiled
  model and engine defaults.
- **Source references.** `contracts/robots/two_joint_arm.xml#L2`,
  `#L13-L19`, `#L30-L32`; `robot_learning/scenario/environment.py#L117-L133`.
- **Discriminating evidence.** From controlled rollouts, compare action, joint
  velocity, endpoint velocity, acceleration, distance overshoot, and settling time,
  especially at different configurations. A torque-saturated trajectory with
  monotone late arrival supports authority limitation; repeated crossings with
  unsaturated action support damping/feedback or timing limitation instead.

### Zero gravity simplifies holding but does not remove control difficulty

- **Reasoned implication.** At a stationary exact IK configuration, zero gravity and
  the absence of declared load mean no static gravitational torque must be balanced.
  A stationary hold can therefore be maintained with little or no motor command in
  the ideal model. The controller still must dissipate arrival velocity and correct
  errors; damping alone does not prevent momentum-driven boundary crossings during
  the approach.
- **Decision relevance.** A controller that relies on gravity compensation is not
  physically justified here, while a controller that reaches gently may have a large
  holding advantage. This changes whether early work should prioritize pose
  acquisition, velocity-aware braking, or static setpoint regulation.
- **Assumptions.** No unmodeled contact, payload, actuator bias, numerical drift, or
  external disturbance is present.
- **Source references.** `contracts/robots/two_joint_arm.xml#L2`,
  `#L13-L19`; `robot_learning/scenario/environment.py#L117-L145`.
- **Discriminating evidence.** During successful and failed holds, inspect joint
  velocities, action magnitude, and distance after entry. Near-zero velocity and
  low command during stable holds support the consequence; persistent correction
  demand or drift would indicate an unrepresented or generated dynamic effect.

### Control-boundary sampling makes the operational hold discrete

- **Reasoned implication.** The environment evaluates distance once after each
  20 ms action interval, not after every internal 2 ms physics step. Therefore the
  implementation's “continuous” hold means 100 consecutive in-tolerance control
  samples; a transient excursion between samples is not directly visible to the
  success counter. This is a simulator interaction consequence, not evidence that
  the continuous physical trajectory stayed inside the ball.
- **Decision relevance.** Policies with high-frequency endpoint oscillation can appear
  successful under the current semantics while being physically less stable between
  observations. Any decision about stabilization, action frequency, or diagnostic
  interpretation must respect this aliasing.
- **Assumptions.** The current environment implementation and official timing remain
  the assessment semantics, and no hidden evaluator samples the substeps for
  success.
- **Source references.** `contracts/scenario.md#Official task`;
  `contracts/task_spec.py#L8-L12`; `robot_learning/scenario/environment.py#L117-L169`.
- **Discriminating evidence.** Record distance at all ten physics substeps in a
  diagnostic rollout and compare it with the control-boundary trace. Boundary
  success with substep exits supports aliasing; agreement weakens its practical
  importance without changing the contract.

### The initial state imposes a common, long-horizon transient

- **Reasoned implication.** Every episode starts from the same straight, stationary
  configuration, while target angle and radius vary. The initial endpoint is near the
  outer reach boundary, so targets nearer the base require elbow flexion and targets
  at other angles require coordinated shoulder/elbow rotation. The policy must infer
  the target-specific maneuver from observations rather than from initial-state
  variation.
- **Decision relevance.** A short-horizon or purely reactive policy may appear
  adequate for nearby outer targets but fail on inward or opposite-angle targets.
  Stratifying behavior by initial target geometry can change whether the first gap is
  generalization, actuation, or stabilization.
- **Assumptions.** Reset is applied exactly as implemented and targets are not
  resampled during an episode.
- **Source references.** `robot_learning/scenario/environment.py#L84-L115`;
  `contracts/robots/two_joint_arm.xml#L13-L22`; `contracts/scenario.md#Official task`.
- **Discriminating evidence.** Compare first-reach time, peak joint velocity, action
  saturation, and hold interruptions by target radius and angle. A systematic
  dependence from the common reset supports this transient explanation.

### The observation is nearly a task-state description, with specific omissions

- **Reasoned implication.** Because the base and target plane are fixed, \(q\) plus
  the endpoint-target vector is sufficient to reconstruct the target position in
  the world plane; \(q\) and \(q\)-velocity expose the arm's generalized state.
  The two IK residual pairs expose branch-relative geometry. The default physical
  state is therefore substantially observable for this deterministic, no-disturbance
  plant, but acceleration, actuator force, substep trajectory, hold counter, prior
  action, and elapsed time are unavailable.
- **Decision relevance.** A feed-forward policy has access to the information needed
  for nominal target reaching, so poor performance need not be attributed first to
  missing target position. Conversely, a policy may need memory or velocity-based
  inference for hold phase, action history, or timing even though the mechanical
  state is mostly observed.
- **Assumptions.** The loaded model has no hidden actuator state and the target is
  fixed; the runtime does not replace the default observation functions.
- **Source references.** `robot_learning/scenario/observations.py#L10-L49`;
  `robot_learning/scenario/policy_io.py#L10-L16`;
  `contracts/policy_runtime.py#L104-L128`.
- **Discriminating evidence.** Compare policies with and without recurrent state while
  holding the physical observation and action interface fixed; inspect whether
  failures correlate with unobserved phase/timing or with visible state variables.
  Directly logging substep forces and hold counters distinguishes observability
  limits from control-law limitations.

### The task distribution has a current training-exposure asymmetry

- **Repository fact.** The current baseline training environment samples radius
  0.14--0.20 m, while the evaluation environment uses the official 0.06--0.20 m
  range. [Sources: `robot_learning/training/environment.py#L15-L20`,
  `robot_learning/scenario/environment.py#L171-L177`,
  `contracts/task_spec.py#L6`]
- **Reasoned implication.** A baseline can learn behavior for outer targets without
  having experienced the inward half of the official radial band. Since inward
  targets require a more folded configuration and may alter branch/limit margins,
  an evaluation gap could be exposure or geometry generalization rather than a
  failure of the actuator model.
- **Decision relevance.** The first campaign comparison may need to distinguish
  improvement in physical control from improvement in coverage of target geometry.
  Aggregate success can conceal a radial failure mode.
- **Assumptions.** The candidate was trained with the current baseline environment
  and no additional target randomization; evaluation remains official.
- **Source references.** `robot_learning/training/environment.py#L1-L20`;
  `robot_learning/scenario/environment.py#L171-L177`;
  `robot_learning/scenario/evaluation.py#L76-L106`.
- **Discriminating evidence.** Bin evaluation outcomes and diagnostics by target
  radius and angle, and compare training exposure with the same bins. Improvement
  confined to the 0.06--0.14 m region supports an exposure explanation; failures
  across all bins weaken it.

### Physically meaningful behavior variables span the whole episode

- **Reasoned implication.** A scientifically useful trajectory description should
  include target \((r,\theta)\), \(q,\dot q\), endpoint position/error and velocity,
  branch and joint-limit margin, action/nominal torque, saturation, first entry,
  minimum distance, settling behavior, in-tolerance duration, interruptions, and
  terminal outcome. These quantities separate geometry, transient authority,
  convergence, and hold stability.
- **Decision relevance.** They prevent the 98% binary objective from obscuring
  whether a policy is close to reliable or failing through one specific physical
  mechanism, while retaining episode success as the only official criterion.
- **Assumptions.** The quantities can be recorded without changing the frozen policy
  or task semantics; diagnostic logging is not itself an intervention.
- **Source references.** `robot_learning/scenario/evaluation.py#L47-L106`;
  `robot_learning/scenario/environment.py#L137-L169`;
  `contracts/scenario.md#Success criterion`.
- **Discriminating evidence.** A complete per-step trajectory at control and, where
  needed, physics resolution can support or weaken each mechanism. Existing
  evaluator fields cover several but not all of these quantities; absent fields
  remain unknown rather than inferred from reward.

## Unknowns

### Generated mass, inertia, and exact actuator authority

- **Unresolved quantity.** The XML supplies geometry, damping, armature, gear, and
  timestep but no explicit body mass, inertia, density, actuator force curve, or
  compiled generalized-force trace. MuJoCo may generate inertial properties from
  geom defaults, but their exact values are not established by the human-authored
  text alone.
- **Decision relevance.** This determines whether observed late arrival, overshoot,
  or saturation is an unavoidable physical limitation or a controllable policy
  deficiency, and therefore can change whether the first campaign direction is
  controller shaping, action scaling, or target-coverage work.
- **Assumptions.** The simulator uses its installed MuJoCo version and XML defaults
  exactly; no runtime model mutation changes those properties.
- **Source references.** `contracts/robots/two_joint_arm.xml#L1-L32`;
  `AGENTS.md#Environment` (locked MuJoCo version).
- **Discriminating evidence.** Inspect the loaded model's mass matrix, body inertias,
  actuator moment arms, generalized actuator forces, and action saturation during
  controlled rollouts. Agreement between model-derived predictions and measured
  accelerations supports the dynamic explanation; mismatch revises it.

### Joint-limit enforcement and limit-margin behavior

- **Unresolved quantity.** The XML declares joint ranges, but the source contract
  does not state the exact compiler `limited` behavior, stop stiffness, damping,
  or whether a trajectory touching a range is reflected, clamped, or penalized by
  the loaded engine.
- **Decision relevance.** Near-limit behavior can make one IK branch dynamically
  preferable and can create a distinct failure class that looks like poor policy
  learning. It may change the choice of branch-aware control and the interpretation
  of angle-dependent failures.
- **Assumptions.** The joint ranges are active constraints in the compiled model and
  are not merely metadata.
- **Source references.** `contracts/robots/two_joint_arm.xml#L13-L19`;
  `robot_learning/scenario/observations.py#L30-L37`.
- **Discriminating evidence.** Measure \(q\), \(\dot q\), constraint/limit forces,
  and endpoint behavior while approaching each range from both sides. A reproducible
  force or velocity discontinuity identifies active stop mechanics; smooth passage
  would revise the constraint interpretation.

### Inter-substep trajectory and numerical hold margin

- **Unresolved quantity.** The source exposes only post-frame observations and
  success checks. It does not establish the maximum endpoint excursion, velocity, or
  distance-to-boundary during the ten internal physics steps of a control interval.
- **Decision relevance.** This decides whether successful 100-sample holds are also
  physically quiet at the simulator timestep, and whether increasing feedback rate
  or reducing action changes would target a real failure mechanism.
- **Assumptions.** Internal MuJoCo integration is deterministic for fixed state and
  action, and diagnostic substep sampling does not alter integration.
- **Source references.** `contracts/robots/two_joint_arm.xml#L2`;
  `contracts/task_spec.py#L8`; `robot_learning/scenario/environment.py#L128-L145`.
- **Discriminating evidence.** For each in-tolerance control interval, record all
  substep distances and compare the minimum distance margin to the 0.01 m boundary.
  Hidden exits or large margins respectively support or weaken the aliasing concern.

### Exact reachability margin under the two joint limits

- **Unresolved quantity.** The unrestricted annulus and the two algebraic IK branches
  establish candidate configurations, but the complete minimum joint-limit margin
  over every \((r,\theta)\) in the official distribution has not been enumerated.
  The observation code clips the inverse-cosine argument, so it would also produce
  a nominal feature for an out-of-workspace target rather than proving reachability.
- **Decision relevance.** If a small subset of official targets is close to or beyond
  the constrained workspace, the goal may be dominated by geometry and branch
  selection rather than learning. If all targets have healthy margin, failures should
  be sought in dynamics, control, or exposure.
- **Assumptions.** The endpoint is the site point and no obstacle or link-clearance
  requirement is added to the point task.
- **Source references.** `contracts/robots/two_joint_arm.py#L3-L8`;
  `contracts/robots/two_joint_arm.xml#L13-L22`;
  `robot_learning/scenario/observations.py#L27-L37`;
  `contracts/task_spec.py#L6`.
- **Discriminating evidence.** Enumerate both IK branches over the full target band,
  reject configurations outside the declared ranges, and report the minimum margin
  by radius and angle. A nonempty infeasible set supports a geometric failure class;
  a positive uniform margin weakens it.

### Default physical-model fidelity versus the intended robot

- **Unresolved quantity.** The repository defines the benchmark robot as the loaded
  XML, but it does not independently establish that generated geom masses,
  collision defaults, numerical tolerances, and actuator semantics match any
  physical hardware or an external intended robot. This is a simulator model, not
  evidence about a real arm.
- **Decision relevance.** It determines whether conclusions should be framed strictly
  as benchmark-policy results or generalized to hardware, and whether sim-specific
  timing/actuation behavior should guide campaign choices.
- **Assumptions.** The campaign goal is the simulated official task, so external
  hardware fidelity is not required for official success.
- **Source references.** `contracts/scenario.md#Immutable task boundary`;
  `contracts/robots/two_joint_arm.xml#L1-L32`; `AGENTS.md#Environment`.
- **Discriminating evidence.** Compare the compiled model against an explicit
  parameter inventory and, if hardware relevance is claimed, system-identification
  data for step responses, damping, inertia, and torque. Agreement supports transfer;
  disagreement limits the claim to simulation.

### Whether runtime policy I/O remains the default observation

- **Unresolved quantity.** Saved policies can carry frozen policy I/O and a loader;
  the runtime validates those artifacts rather than substituting current scientific
  code. The source therefore establishes the default observation, but not that every
  future candidate uses it without inspecting its frozen runtime.
- **Decision relevance.** A mismatch in observation layout or normalization can mimic
  a physical failure and invalidate comparisons of policies as if they had the same
  sensor suite.
- **Assumptions.** Candidate artifacts are loaded through the required runtime and
  their saved policy I/O is valid.
- **Source references.** `contracts/policy_runtime.py#L35-L75`,
  `#L104-L128`; `robot_learning/scenario/policy_io.py#L1-L16`;
  `robot_learning/scenario/environment.py#L47-L58`.
- **Discriminating evidence.** For every candidate, verify the runtime fingerprint,
  observation/action spaces, normalization, and actual 11-value observation mapping.
  Matching interfaces support physical comparison; any divergence requires separate
  interpretation.

## Decision-relevant synthesis

### Hold reliability is the primary physical bottleneck to preserve

- **Reasoned implication.** Reaching the tolerance ball is only an intermediate
  event; a policy must remain within 1 cm for 100 consecutive 20 ms control samples.
- **Decision relevance.** First campaign decisions should distinguish reach failures
  from post-entry exits, because the useful direction differs between trajectory
  acquisition and velocity/stability control.
- **Assumptions.** The official discrete control-boundary semantics are authoritative.
- **Source references.** `contracts/scenario.md#Official task`;
  `contracts/task_spec.py#L8-L12`; `robot_learning/scenario/environment.py#L137-L169`.
- **Discriminating evidence.** Per-episode first entry, distance trace, held-step
  maximum, interruptions, final distance, and terminal reason; substep traces are
  needed to test hidden excursions.

### Dynamic authority and generated inertia are the highest-impact physical unknown

- **Unresolved quantity.** Exact mass matrix, inertia, actuator generalized force,
  and joint-limit reaction are not specified explicitly by the XML.
- **Decision relevance.** These quantities decide whether late arrival and
  overshoot are actuator/dynamics limits or policy-control defects, changing the
  first scientific direction.
- **Assumptions.** Compiled MuJoCo defaults are the actual benchmark dynamics.
- **Source references.** `contracts/robots/two_joint_arm.xml#L1-L32`;
  `AGENTS.md#Environment`.
- **Discriminating evidence.** Loaded-model parameter inspection plus controlled
  action-to-acceleration and action-to-velocity measurements, stratified by
  configuration and saturation.

### Branch choice and constrained workspace should be checked before blaming learning

- **Reasoned implication.** The target has two nominal planar IK branches and the
  official band is inside the unrestricted two-link annulus, but joint-limit margin
  varies with target geometry.
- **Decision relevance.** A radius/angle-specific failure pattern can require
  branch-aware reasoning or exposure coverage, whereas healthy margins redirect
  attention to transient control and stabilization.
- **Assumptions.** The site point, not link clearance or orientation, defines the task.
- **Source references.** `contracts/robots/two_joint_arm.xml#L13-L22`;
  `robot_learning/scenario/observations.py#L14-L47`;
  `contracts/task_spec.py#L6`.
- **Discriminating evidence.** Full-band IK enumeration with joint-limit margins,
  then episode diagnostics binned by target radius, angle, branch, and limit margin.

### The baseline's radial exposure does not cover the full official band

- **Repository fact.** The current training constructor uses 0.14--0.20 m while
  official evaluation uses 0.06--0.20 m.
- **Decision relevance.** Early evaluation must not interpret a radial performance
  gap as evidence of inadequate actuator authority until inward-target exposure and
  geometry-conditioned behavior are separated.
- **Assumptions.** The candidate follows the current training constructor and the
  official evaluator uses the contract distribution.
- **Source references.** `robot_learning/training/environment.py#L15-L20`;
  `robot_learning/scenario/environment.py#L171-L177`;
  `contracts/scenario.md#Official task`.
- **Discriminating evidence.** Compare success and mechanism diagnostics in the
  0.06--0.14 m and 0.14--0.20 m bands, with angle stratification; use the result to
  revise the exposure-versus-control explanation, not to select an intervention here.

### The observation is sufficient for nominal geometry but not all hold context

- **Repository fact.** The default observation contains joint position/velocity,
  endpoint error, and both IK branch residuals, but not held steps, elapsed time,
  prior action, actuator force, or internal substep state.
- **Decision relevance.** A visible-state policy should be capable of target geometry
  reasoning; a hold-specific failure may instead reflect velocity, timing, or
  unobserved phase information. Candidate comparisons must verify frozen policy I/O.
- **Assumptions.** No candidate-specific runtime changes the observation contract.
- **Source references.** `robot_learning/scenario/observations.py#L10-L49`;
  `contracts/policy_runtime.py#L35-L75`.
- **Discriminating evidence.** Verify each candidate's frozen runtime and compare
  failure timing with \(q,\dot q\), action/saturation, branch residuals, and hold
  interruptions; inspect substeps when these visible signals cannot explain exits.
