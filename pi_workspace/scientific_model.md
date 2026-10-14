# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. Every entry is labelled as a
**repository fact**, a **reasoned implication**, or an **unresolved quantity**.
Source references identify the implementation or contract that should be
rechecked if the claim becomes consequential. No campaign evidence is assumed.

## Established facts

### System boundary and task authority

- **[Repository fact]** The human-defined task is a two-joint-arm reach and
  hold: a target is sampled 6--20 cm from the base over the full angular
  range; the end effector must enter a 1 cm tolerance and remain continuously
  there for 2 seconds, which is 100 control steps at the official timing.
  Success is the complete uninterrupted hold, not merely reaching. The target
  objective is at least 196 successes in the fixed 200-episode official panel.
  **Source:** `contracts/scenario.md` (Official task, Success criterion,
  Official final assessment).

- **[Repository fact]** The visible scenario constructs a MuJoCo model from
  `contracts/robots/two_joint_arm.xml`; the scenario module explicitly says
  that its defaults are research scaffolding and that the protected benchmark
  enforces the human-defined task. **Source:**
  `robot_learning/scenario/environment.py` (`TwoJointArmReachEnv`,
  `make_evaluation_env`) and its module docstring.

### Morphology and kinematic structure

- **[Repository fact]** The base is fixed to the world. The arm has two
  revolute joints about the world z axis: `shoulder` is at the base and
  `elbow` is at the end of a 0.12 m upper arm. The forearm is 0.10 m long and
  carries the `end_effector` site at its distal end. The joint coordinates are
  therefore \(q=(q_s,q_e)\), with the elbow angle relative to the upper arm
  and forearm orientation \(q_s+q_e\). **Source:**
  `contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`, `forearm`,
  `shoulder`, `elbow`, `end_effector`).

- **[Repository fact]** Both hinge ranges are -170 to 170 degrees. The
  kinematic lengths are also exported as `UPPER_ARM_LENGTH=0.12`,
  `FOREARM_LENGTH=0.10`, and `MAX_REACH=0.22`. **Source:**
  `contracts/robots/two_joint_arm.xml`; `contracts/robots/two_joint_arm.py`.

- **[Reasoned implication]** In the arm plane, with base-plane height
  \(z_0=0.02\) m, the forward kinematics are
  \(p(q)=z_0\hat z+[L_1\cos q_s+L_2\cos(q_s+q_e),
  L_1\sin q_s+L_2\sin(q_s+q_e),0]\). With unrestricted angles the workspace is
  the annulus \(|L_1-L_2|\leq r\leq L_1+L_2\), namely 0.02--0.22 m.
  Joint limits carve this annulus near selected directions and configurations;
  the exact feasible set is the limit-constrained image of the two angle
  intervals, not the ideal annulus. **Assumptions:** the XML body offsets and
  site coordinates are interpreted in the usual serial-chain way and no
  other body motion is introduced. **Decision relevance:** boundary targets
  and limit-near solutions may require different training coverage or
  selection of an inverse-kinematic branch. **Sources:** the XML geometry and
  joint ranges; `two_joint_arm.py` constants. **Discriminating evidence:**
  enumerate forward kinematics over the bounded joint rectangle and compare
  target-radius/angle bins with the 1 cm tolerance.

- **[Reasoned implication]** The planar Jacobian has determinant proportional
  to \(L_1L_2\sin q_e\). It loses rank at the fully extended and fully folded
  configurations. At the reset pose \(q=(0,0)\), the end effector is at
  \((0.22,0,0.02)\) and is at an extension singularity: first-order motion
  is strong in one Cartesian direction while motion that changes radial reach
  is poorly conditioned. **Assumptions:** standard planar revolute
  kinematics. **Decision relevance:** early steering and braking can be harder
  than a static inverse-kinematic calculation suggests, particularly for
  targets near the initial ray or inner workspace. **Sources:** XML reset
  geometry; `environment.py` reset; the kinematic lengths. **Discriminating
  evidence:** evaluate the Jacobian singular values along trajectories and
  relate their minimum to time-to-tolerance and hold interruptions.

- **[Repository fact]** The observation code computes both geometric inverse
  kinematic branches, called `open` (\(q_e=+\arccos(\cdot)\)) and `folded`
  (\(q_e=-\arccos(\cdot)\)), and reports the wrapped angle error to each
  branch. **Source:** `robot_learning/scenario/observations.py`
  (`shoulder_for_elbow`, `elbow_open`, `elbow_folded`).

### Actuation, timing, and simulator dynamics

- **[Repository fact]** Each joint is driven by a MuJoCo motor with control
  range [-1, 1] and gear 5. The policy action is a two-vector in that range;
  the environment clips the policy-runtime output to the same bounds before
  writing `data.ctrl`. **Source:** `two_joint_arm.xml` (`<actuator>`); 
  `robot_learning/scenario/environment.py` (`step`); `policy_io.py`.

- **[Reasoned implication]** Under MuJoCo's motor transmission convention, a
  constant saturated command supplies a nominal generalized torque magnitude
  of 5 actuator units at the associated joint, with the sign set by the
  command. The actual acceleration is state dependent because the two-link
  inertia matrix couples the joints and because damping opposes velocity.
  **Assumptions:** the installed MuJoCo 3.12 motor/gear convention applies and
  no other actuator transformation is installed. **Decision relevance:**
  control authority, braking distance, and action smoothness can determine
  whether a reaching policy can enter and remain in a 1 cm band. **Sources:**
  XML motor definitions; `policy_io.py` identity action mapping;
  `AGENTS.md` (locked MuJoCo version). **Discriminating evidence:** apply
  controlled commands and record joint acceleration/velocity response and
  `data.actuator_force` or equivalent generalized effects.

- **[Repository fact]** The physics timestep is 0.002 s, every policy action is
  held for 10 MuJoCo steps, and the resulting control interval is 0.020 s.
  Damping is 0.5 on each hinge and armature is 0.01 on each hinge. Gravity is
  explicitly zero. The plane, base cylinder, and target explicitly disable
  contact; the two arm capsules do not specify contact masks, so their
  effective self-contact behavior follows MuJoCo defaults. **Source:**
  `two_joint_arm.xml`; `environment.py` (`control_dt`, `frame_skip`, `mj_step`).

- **[Reasoned implication]** The policy is a zero-order-hold controller at
  50 Hz around a 500 Hz physics simulation. There are ten integration steps
  between observations, so an action cannot react to within-interval motion.
  Damping reduces residual velocity but cannot remove the sampling delay or
  finite braking distance. With no gravity, target contact, or plane contact
  load, a stationary configuration at zero velocity needs no static torque;
  stabilization is mainly velocity and perturbation management rather than
  supporting weight. **Assumptions:** the visible timing and contact masks
  are the official physical semantics. **Decision relevance:** a controller
  that reaches with substantial velocity can fail the hold despite a small
  instantaneous distance; action frequency, braking, and low-motion
  regulation are therefore distinct from reach accuracy. **Sources:** XML;
  `environment.py`; 
  `contracts/task_spec.py`. **Discriminating evidence:** log distance,
  Cartesian velocity, action, and exit time at every control step, including
  the first 100 in-tolerance steps.

- **[Unresolved quantity]** Link masses, full inertias, solver/integrator
  defaults, and any mass properties inferred from the capsule geoms are not
  stated in the human-owned XML. Their values can materially change the
  acceleration and damping time constants even though the lengths and
  nominal actuator gear are known. **Decision relevance:** this could change
  whether the first research direction should emphasize model-free exploration,
  model-based prediction, or conservative stabilization. **Assumptions:** the
  unspecified MuJoCo defaults and inferred geom properties are active and
  unchanged in the protected benchmark. **Sources:** 
  `contracts/robots/two_joint_arm.xml`; `AGENTS.md` (MuJoCo version).
  **Discriminating evidence:** an exact model-property dump and impulse/step
  response identified at several joint configurations; agreement between
  predicted and observed \(q,\dot q\) trajectories would support the assumed
  dynamics.

### Initial state and task geometry

- **[Repository fact]** Reset sets both joint positions and velocities to zero,
  performs forward dynamics, and samples one fixed mocap target in the same
  z-plane as the end effector. The visible sampler draws angle uniformly over
  \([-\pi,\pi]\) and radius uniformly over its configured interval. The
  visible evaluation default is 0.06--0.20 m; the baseline training
  environment uses only 0.14--0.20 m. **Sources:** `environment.py`
  (`reset`, `_sample_target_position`); `contracts/task_spec.py`;
  `robot_learning/training/environment.py`.

- **[Repository fact]** The success distance is the three-dimensional Euclidean
  distance from the end-effector site to the mocap target, tested after each
  20 ms control interval. Entering the tolerance increments a consecutive
  counter; any outside sample resets it to zero. The episode terminates at
  100 held control steps or truncates at 500 steps. **Source:**
  `robot_learning/scenario/environment.py` (`_distance_to_target`, `step`);
  `contracts/task_spec.py`.

- **[Reasoned implication]** The task is a point-position regulation problem,
  not grasping or target-contact manipulation: there is no target force
  requirement, end-effector orientation requirement, or obstacle in the
  visible model. The arm capsules may still self-contact under their default
  masks, which could matter in folded configurations even though such contact
  is not part of the success predicate. The 1 cm ball becomes a 1 cm disk in
  the arm plane, while the target is stationary during an episode.
  **Assumptions:** the visible contact masks and same-plane target are retained
  officially. **Decision relevance:** a method should be judged on complete
  position regulation and not on target force or orientation behavior; folded
  self-contact must not be mistaken for a pure kinematic effect.
  **Sources:** XML; `environment.py`; `scenario.md`. **Discriminating
  evidence:** verify target position is invariant and report contact forces
  alongside distance, branch, and joint configuration; contact should not
  contribute directly to the official success predicate.

### Sensing, observation, and policy loop

- **[Repository fact]** The default observation has 11 float32 values:
  two joint positions, two joint velocities, the three-component
  end-effector-minus-target vector, and four wrapped errors to the open and
  folded inverse-kinematic configurations. The declared environment
  observation space is unbounded. **Source:** 
  `robot_learning/scenario/observations.py`; `environment.py`
  (`OBSERVATION_SIZE`, `observation_space`).

- **[Reasoned implication]** In the visible noiseless simulator this is
  effectively a Markov state for the task: joint position and velocity give
  mechanical state, while the relative target vector gives task geometry.
  Absolute target angle is omitted but is recoverable for the planar task from
  the relative vector and current joint configuration; rotational symmetry
  makes absolute world orientation unnecessary. The four branch errors provide
  redundant task-directed structure rather than an external force sensor.
  **Assumptions:** no hidden disturbance, sensor noise, observation delay, or
  unmodeled actuator state is introduced. **Decision relevance:** memory may
  be unnecessary for state reconstruction, while normalization or recurrent
  state can still affect learning and transient control. **Sources:**
  `observations.py`; `policy_io.py`; `environment.py`. **Discriminating
  evidence:** compare identical physical states with different histories and
  verify identical observations and next-state distributions.

- **[Repository fact]** The default action mapping is identity. The runtime
  may instead carry a saved policy-specific observation/action callable;
  runtime loading freezes that I/O together with model weights and optional
  observation-normalization statistics. **Source:** `policy_io.py`;
  `contracts/policy_runtime.py` (`save_runtime`, `PolicyRuntime`).

- **[Reasoned implication]** The closed loop is
  observation -> policy action -> clipping -> ten physics steps -> new
  observation and distance test. The controller sees no direct future
  velocity or acceleration; it must infer braking needs from current velocity,
  geometry, and the branch alternatives. The action cost in the visible
  reward discourages magnitude, but reward is not the success definition.
  **Decision relevance:** reward changes can improve or harm hold behavior
  without changing official mechanics, and runtime I/O must be treated as part
  of a candidate's physical controller. **Sources:** `environment.py`;
  `observations.py`; `policy_io.py`; `robot_learning/training/reward.py`.
  **Discriminating evidence:** compare policy actions and physical trajectories
  under the same initial state, and score hold success independently of reward.

### What can be measured across the complete behavior

- **[Reasoned implication]** The physically meaningful trajectory is
  \((q,\dot q,p_{\rm ee}-p_{\rm target},u)\) together with target radius and
  angle, Jacobian conditioning, and the 100-step in-tolerance run. Useful
  derived quantities are time to first tolerance entry, minimum and final
  distance, Cartesian speed at entry, maximum consecutive hold, interruption
  count, action/torque magnitude, and distance and speed during the hold.
  These quantities distinguish reach failure, overshoot, branch/limit
  difficulty, and stabilization failure; aggregate reward or success alone
  cannot make those distinctions. **Assumptions:** trajectory diagnostics are
  collected at the same control cadence and do not alter the policy.
  **Decision relevance:** these are the observables that can discriminate
  physical explanations before changing a learning recipe. **Sources:**
  `environment.py`; `evaluation.py` (`episode_diagnostics`); the kinematic
  definitions above. **Discriminating evidence:** retain stepwise traces
  aligned to target geometry and classify failures by first entry, speed, and
  interruption pattern.

## Physical consequences

### Reachability, branches, and singularity-conditioned behavior

- **[Reasoned implication]** Most targets in the 0.06--0.20 m radial band have
  two geometric inverse-kinematic configurations, but the joint limits and
  1 cm tolerance determine whether each branch is actually usable. The two
  branches can have different distance from the reset state, limit margin,
  Jacobian conditioning, and braking behavior even when they reach the same
  point. **Decision relevance:** branch selection or branch-aware policy
  structure could change early campaign choices. **Assumptions:** both
  geometric branches remain within the effective joint limits for the target
  being considered. **Sources:** XML ranges; `observations.py` branch
  construction; `environment.py` reset. **Discriminating evidence:** for each
  target, solve and forward-check both branches, then compare trajectory
  length, limit margin, singular values, and hold interruptions.

- **[Reasoned implication]** The reset at full extension is a systematic
  initial-condition difficulty, not a random dynamical perturbation. A policy
  can benefit from first creating elbow clearance and only then correcting
  radial error; directly chasing Cartesian error near a singularity can
  demand large joint motion or produce overshoot. **Decision relevance:** it
  changes whether a first controller should be evaluated as a staged reach
  followed by regulation rather than as one undifferentiated action map.
  **Assumptions:** the reset state is always exactly zero and targets are
  sampled after reset. **Sources:** `environment.py`; XML. **Discriminating
  evidence:** stratify time-to-entry and peak action by initial Jacobian
  condition and target direction.

### Reach-to-hold coupling

- **[Reasoned implication]** Reaching and holding are coupled through velocity:
  entering the distance ball with nonzero Cartesian speed consumes the
  available margin before the next 20 ms observation and can reset the entire
  100-step counter. Thus a policy can have good minimum distance and still
  fail the task; convergence rate, terminal speed, and local feedback
  stiffness are separate capabilities. **Decision relevance:** first
  decisions should not optimize minimum distance or first reach alone.
  **Assumptions:** the outside-sample reset in the visible environment is the
  official hold semantics. **Sources:** `scenario.md`; `environment.py`;
  `evaluation.py`. **Discriminating evidence:** compare success with
  minimum distance, speed at first entry, maximum held steps, and interruption
  count.

- **[Reasoned implication]** Because gravity, target contact, and plane contact
  loads are absent, a successful steady hold can use very small or zero command
  once velocity is removed. The hard part is settling inside the narrow band
  without crossing its boundary, not maintaining a static load; folded
  self-contact remains a possible exception. **Decision relevance:** a
  low-action, damping-aware regulator may be more valuable than persistent
  torque output; action magnitude should be interpreted together with speed,
  error, and contact state. **Assumptions:** no hidden disturbance or actuator
  bias. **Sources:** XML gravity and contact settings; `environment.py`.
  **Discriminating evidence:** measure command, velocity, and contact state
  during successful holds and test whether exits correlate with residual speed
  rather than insufficient steady torque or self-contact.

### Timing, authority, and dynamic uncertainty

- **[Reasoned implication]** Ten physics steps per action create a minimum
  observation-to-correction delay of one control interval. The 1 cm tolerance
  is only 5% of the 0.20 m maximum official radius and may be small relative
  to a one-interval displacement during a fast approach. **Decision
  relevance:** action-rate assumptions and conservative approach speed can
  dominate success more than raw positional reachability. **Assumptions:**
  the 0.002 s integrator step and 0.020 s action interval are unchanged.
  **Sources:** XML; `environment.py`; `task_spec.py`. **Discriminating
  evidence:** measure maximum in-band displacement per action interval and
  compare it with the remaining tolerance margin.

- **[Reasoned implication]** Unknown inertia and MuJoCo defaults affect the
  ratio of available motor torque to inertial acceleration and the time needed
  to reverse velocity. The same policy action can therefore produce
  configuration-dependent overshoot through the coupled two-link inertia,
  even with constant gear and damping. **Decision relevance:** model-free
  policy robustness versus explicit dynamics characterization is a live
  decision. **Assumptions:** the unspecified properties are not negligible.
  **Sources:** XML actuator/damping/armature fields; absence of explicit mass
  and solver fields; `AGENTS.md`. **Discriminating evidence:** fit local
  second-order responses at extended, bent, and folded configurations and
  check whether one identified model predicts held trajectories.

### Distribution and task coverage

- **[Reasoned implication]** The baseline training sampler covers only 14--20
  cm, while the official task includes 6--20 cm. A policy can therefore learn
  a competent outer-workspace reach while remaining untested on inner,
  more-folded and potentially more-conditioned configurations. Angular
  generalization is also required over the full circle. **Decision relevance:**
  this is a direct reason to treat baseline training performance as
  insufficient evidence for the official 98% objective. **Assumptions:** the
  baseline training environment and the contract distribution remain as
  referenced. **Sources:** `robot_learning/training/environment.py`;
  `contracts/scenario.md`; `contracts/task_spec.py`. **Discriminating
  evidence:** evaluate diagnostics in radius bands 6--14 and 14--20 cm and
  across angle, using the official success predicate rather than reward.

- **[Reasoned implication]** The visible sampler makes the target fixed
  within each episode, so the policy solves a static target regulation
  problem rather than tracking a moving target. It must nevertheless
  generalize over target geometry and initial identical arm state. **Decision
  relevance:** temporal memory for target motion is not implied by the task,
  while geometry-aware control is. **Assumptions:** protected evaluation uses
  the same stationary-target semantics. **Sources:** `environment.py`;
  `scenario.md`. **Discriminating evidence:** verify target constancy in
  episode traces and compare performance by radius and angle.

### Observability and alternative solutions

- **[Reasoned implication]** The default observation contains enough
  information to distinguish the arm's current branch because it contains
  \(q\), but it also presents both desired branches. A policy may choose a
  branch implicitly through transient actions; this is a genuine control
  solution difference, not an observation ambiguity at a fixed state.
  **Decision relevance:** compare complete policies by branch occupancy and
  hold quality rather than assuming one inverse-kinematic solution is
  canonical. **Assumptions:** default observation/runtime is used.
  **Sources:** `observations.py`; `policy_io.py`. **Discriminating evidence:**
  classify settled elbow sign and branch error for successful and failed
  episodes.

- **[Reasoned implication]** No force or contact observation is exposed, and
  target and plane contact are disabled; the target is kinematic. The possible
  arm self-contact is likewise not represented in the default observation. If
  self-contact or another protected disturbance changes transitions, the
  current 11-value state is not a complete observable physical state.
  **Decision relevance:** robustness or recurrent control should not be
  prioritized solely from an unsubstantiated disturbance hypothesis, but
  contact must be checked before interpreting folded failures as policy
  errors. **Assumptions:** protected physics matches the visible contract
  implementation. **Sources:** XML; `observations.py`; `scenario.md`;
  `AGENTS.md`. **Discriminating evidence:** inspect contact state in official
  evaluation traces or compare repeated-state transitions for unobserved
  force/contact effects.

## Unknowns

### Effective physical parameters and numerical semantics

- **[Unresolved quantity]** The exact masses, inertias, center-of-mass
  properties, integrator/solver settings, and effective joint-limit
  enforcement are not explicit in the accessible human-owned XML.
  **Decision relevance:** they could change the choice between a dynamics
  characterization, conservative policy training, and direct policy search.
  **Assumptions:** MuJoCo defaults and compiler inference are the operative
  semantics, and the protected benchmark does not substitute another model.
  **Sources:** `contracts/robots/two_joint_arm.xml`; `AGENTS.md`.
  **Discriminating evidence:** record the instantiated model's physical
  arrays and responses to known commands at multiple configurations; revise
  the model if measured acceleration or limit behavior disagrees.

### Official distribution and evaluator realization

- **[Unresolved quantity]** The contract states a target uniformly sampled
  from 6--20 cm over all angles, while the visible environment explicitly
  samples radius and angle independently uniformly and the baseline trainer
  narrows radius to 14--20 cm. The exact probability measure intended by
  “uniformly” (uniform radius versus uniform planar area), the protected
  sampler details, and any evaluator-specific defaults are not accessible
  here. **Decision relevance:** this could change which geometry is most
  valuable to cover first and how development scores predict the 200-episode
  official result. **Assumptions:** the wording of `scenario.md` is
  authoritative even where visible research defaults differ. **Sources:**
  `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/training/environment.py`. **Discriminating evidence:**
  obtain the protected sampler specification or target histogram and compare
  candidate success under the exact official panel distribution.

### Runtime I/O and normalization of future candidates

- **[Unresolved quantity]** A future saved policy may carry frozen observation
  and action callables and normalization statistics that differ from the
  current default identity action and 11-value observation path. The model
  describes the physical plant, but candidate behavior also depends on this
  frozen interface. **Decision relevance:** a policy comparison can confound
  learning changes with changed sensing, action scaling, or normalization.
  **Assumptions:** runtime artifacts are valid and loaded as required by
  `contracts/policy_runtime.py`. **Sources:** `policy_io.py`;
  `contracts/policy_runtime.py`; `robot_learning/training/normalization.py`.
  **Discriminating evidence:** inspect each candidate's runtime manifest,
  observation/action shapes and scaling, then replay identical physical
  states through the exported runtime.

### Disturbance, determinism, and within-step state

- **[Unresolved quantity]** The visible code supplies no noise, delay,
  perturbation, or external force, but the accessible task contract does not
  enumerate every protected evaluator implementation detail. It is therefore
  unknown whether repeated episodes with the same seed and policy are fully
  deterministic under the official path and whether any unobserved state
  affects transitions. **Decision relevance:** this determines whether
  deterministic trajectory optimization is appropriate and whether robust
  margins are necessary for 98% success. **Assumptions:** hidden benchmark
  behavior may differ only within the immutable task boundary. **Sources:**
  `scenario.md`; `environment.py`; `evaluation.py`; `AGENTS.md`.
  **Discriminating evidence:** repeated same-seed official-compatible
  rollouts, paired transition traces, and explicit benchmark metadata about
  perturbations.

### Failure-class prevalence before campaign evidence

- **[Unresolved quantity]** No campaign result yet establishes whether failure
  is dominated by unreachable/limit-near targets, slow arrival, overshoot,
  branch choice, or late hold interruption. The source model only establishes
  mechanisms that could produce each class. **Decision relevance:** the first
  measurement and learning direction should differ depending on which class
  dominates; aggregate success cannot choose among them. **Assumptions:**
  stepwise diagnostics can be collected without changing evaluation behavior.
  **Sources:** `evaluation.py` diagnostics; `environment.py` success state;
  `scenario.md`. **Discriminating evidence:** per-episode traces containing
  target geometry, first-reach step, speed/error near entry, held-step
  maximum, and interruptions.

## Decision-relevant synthesis

### Hold stabilization is a separate capability from reach

- **[Reasoned implication] Decision relevance:** The first campaign decision
  should distinguish arrival from complete 2-second regulation; optimizing
  minimum distance alone can select a policy that fails the human goal.
- **[Reasoned implication] Assumptions:** the visible 20 ms sampling and reset
  of the consecutive counter on any outside sample are authoritative.
- **[Repository fact] Source references:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/evaluation.py`.
- **[Unresolved quantity] Discriminating evidence:** compare success with
  first-reach step, speed and distance margin at entry, maximum held steps,
  and interruption count over complete episodes.

### Inner-workspace and singularity coverage may be the main generalization gap

- **[Reasoned implication] Decision relevance:** The visible baseline exposes
  training primarily to 14--20 cm, whereas the official distribution reaches
  6 cm and all angles; branch-conditioned Jacobian difficulty may therefore
  dominate early official failures.
- **[Reasoned implication] Assumptions:** the training sampler is the active
  baseline and the official target law is the contract law.
- **[Repository fact] Source references:** `contracts/scenario.md`;
  `robot_learning/training/environment.py`; `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/observations.py`.
- **[Unresolved quantity] Discriminating evidence:** radius/angle-binned
  official-compatible success and trajectory diagnostics, including branch
  sign, limit margin, and Jacobian singular values.

### Dynamic authority and model defaults can determine whether braking is feasible

- **[Reasoned implication] Decision relevance:** Torque gear and damping are
  known qualitatively, but acceleration, reversal time, and in-band
  displacement depend on unspecified inertial and numerical properties; this
  can change whether to favor model-free robustness or explicit dynamics
  characterization.
- **[Reasoned implication] Assumptions:** inferred MuJoCo mass properties and
  default solver semantics materially affect the 50 Hz closed loop.
- **[Repository fact] Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md`.
- **[Unresolved quantity] Discriminating evidence:** instantiated model
  properties plus controlled step/impulse responses at extended, bent, and
  folded states, aligned with hold-exit trajectories.

### The exact official probability measure and runtime interface must not be inferred from reward

- **[Reasoned implication] Decision relevance:** Development reward and the
  visible training distribution do not establish 98% official success; target
  measure and candidate-specific frozen I/O can alter generalization and
  comparability.
- **[Reasoned implication] Assumptions:** protected evaluation is authoritative
  and saved runtime callables are part of each candidate's deployed controller.
- **[Repository fact] Source references:** `contracts/scenario.md`;
  `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`;
  `contracts/policy_runtime.py`; `robot_learning/training/reward.py`.
- **[Unresolved quantity] Discriminating evidence:** verify the official
  target histogram and each candidate's runtime shape/scaling, then use the
  official success predicate and fixed 200-episode panel rather than reward or
  a development proxy.
