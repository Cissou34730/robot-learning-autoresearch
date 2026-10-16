# Scientific model: two-joint arm reach-and-hold

## Established facts

### Scope and statement convention

- **Repository fact - scope.** This is the pre-campaign physical model. It
  uses repository definitions only and does not use training, evaluation, or
  campaign evidence.
- **Repository fact - statement convention.** Statements are marked as
  **repository facts**, **reasoned implications**, or **unresolved
  quantities**. "Unresolved" means not established by the readable
  human-owned definitions, not that the quantity cannot be measured.

### Source reference key

- **Repository fact - [R1].** `contracts/robots/two_joint_arm.xml` is the
  MuJoCo model definition: world options, bodies, geoms, site, joint limits,
  and actuators.
- **Repository fact - [R2].** `contracts/robots/two_joint_arm.py` defines
  `UPPER_ARM_LENGTH = 0.12`, `FOREARM_LENGTH = 0.10`, and
  `MAX_REACH = 0.22`, all in meters.
- **Repository fact - [R3].** `contracts/scenario.md` defines the official
  target distribution, uninterrupted hold criterion, 500-step episode limit,
  200-episode final panel, and 98 percent objective.
- **Repository fact - [R4].** `contracts/task_spec.py` provides the visible
  task constants: target radii `(0.06, 0.20)`, `FRAME_SKIP = 10`,
  `SUCCESS_THRESHOLD = 0.01`, `HOLD_SECONDS = 2.0`, and
  `MAX_EPISODE_STEPS = 500`.
- **Repository fact - [R5].** `robot_learning/scenario/environment.py` owns
  the visible reset, target sampling, action clipping, MuJoCo stepping, hold
  counter, and shared environment mechanics.
- **Repository fact - [R6].** `robot_learning/scenario/observations.py`
  constructs the 11-element observation, including joint state, target
  relative position, and errors to two planar inverse-kinematic branches.
- **Repository fact - [R7].** `robot_learning/scenario/policy_io.py` maps
  physical actions identically and uses `reach_observation`; the runtime
  contract is in `contracts/policy_runtime.py`.
- **Repository fact - [R8].** `robot_learning/scenario/evaluation.py`
  records episode outcomes and geometry/hold diagnostics and uses deterministic
  policy prediction for its research panels.
- **Repository fact - [R9].** `robot_learning/training/reward.py` defines a
  replaceable learning signal; it does not change the MuJoCo mechanics or
  official success definition.
- **Repository fact - [R10].** `robot_learning/training/environment.py`
  gives the visible baseline training environment a target-radius range of
  `(0.14, 0.20)`, distinct from the official `(0.06, 0.20)` range.

### Morphology and coordinates

- **Repository fact - morphology.** The model has a fixed base and two
  serial child bodies, `upper_arm` and `forearm`. The shoulder and elbow are
  the only joints; both are hinge joints about the world/body z axis. There
  are therefore two generalized coordinates, which can be written
  `q = (q_s, q_e)`, with no translational or out-of-plane degree of freedom.
  [R1: `worldbody/base/upper_arm/joint` and
  `worldbody/base/upper_arm/forearm/joint`]
- **Repository fact - geometry.** The shoulder-to-elbow link length is
  0.12 m, the elbow-to-site length is 0.10 m, and the end-effector site is
  at the forearm tip. The arm plane is horizontal at z = 0.02 m because the
  `upper_arm` body is translated by 0.02 m above the base origin.
  [R1; R2]
- **Repository fact - joint constraints.** Each hinge has a range of -170 to
  170 degrees. The two angles are bounded independently in the model; the
  source does not define a wider angle wrap or a separate posture constraint.
  [R1: `range="-170 170"`]
- **Repository fact - visible geometry and collision flags.** The base
  cylinder, plane, and target sphere explicitly have `contype="0"` and
  `conaffinity="0"`. The upper-arm and forearm capsules do not explicitly set
  those flags. The target sphere has visual radius 0.012 m, but the visible
  success calculation uses the target mocap center rather than sphere-surface
  contact. [R1; R5: `_distance_to_target`]

### Simulator, actuation, and timing

- **Repository fact - simulator options.** The XML sets gravity to
  `(0, 0, 0)` and the MuJoCo integration timestep to 0.002 s. No
  gravity torque acts on the links in this model. [R1: `<option>`]
- **Repository fact - joint-level dynamic parameters.** Each hinge has
  damping 0.5 and armature 0.01. The XML does not specify a positional
  spring, velocity limit, actuator dynamics, or explicit actuator force
  range. [R1: shoulder and elbow `<joint>` elements]
- **Repository fact - motor interface.** There is one `motor` actuator per
  hinge, each with `ctrlrange="-1 1"` and scalar `gear="5"`. The Gymnasium
  action has two elements in [-1, 1], is clipped to that range, is passed
  unchanged by `physical_action`, and is written to `data.ctrl`.
  [R1; R5: `step`; R7: `physical_action`]
- **Repository fact - zero-order hold.** One policy action is applied, then
  `mujoco.mj_step` is called ten times before the next observation. The
  visible control interval is therefore 0.02 s, or 50 control updates per
  second, and 100 control steps represent 2 s. A 500-step episode spans at
  most 10 s of control time. [R4; R5: `frame_skip` and `step`]
- **Repository fact - no visible sensor/noise model.** The readable
  scenario code does not add sensor noise, actuator noise, external force,
  gravity, or target motion. The target is a mocap body and is not acted on
  by the arm in the visible model. [R1; R5; R6]

### Initial state and target geometry

- **Repository fact - reset state.** The visible environment resets MuJoCo
  data, sets both joint positions and velocities to zero, forwards the model,
  and then samples a new target. The model-file target position `(0.15, 0, 0)`
  is consequently not the episode target after this reset path.
  [R1; R5: `reset` and `_sample_target_position`]
- **Repository fact - target sampling in the visible environment.** The
  target angle is sampled uniformly from [-pi, pi], and its radius is sampled
  uniformly from 0.06 to 0.20 m. Its z coordinate is set to the current
  end-effector z coordinate, so the target and site are coplanar after reset.
  [R3; R5: `_sample_target_position`]
- **Repository fact - official success.** The end-effector must be within
  0.01 m of the target and remain continuously within that tolerance for 2 s.
  Under the current official timing this is 100 consecutive control steps.
  A single interruption resets the visible held-step counter. The episode
  also truncates at 500 control steps. [R3; R4; R5: `step`]
- **Repository fact - official assessment.** The final assessment uses one
  frozen policy on 200 episodes from the official distribution; at least 196
  successes are required for the 98 percent objective. The final panel is
  distinct from development panels. [R3]

### State delivered to the controller

- **Repository fact - observation contents.** The visible observation has
  11 float32 elements in this order: two `qpos` values, two `qvel` values,
  a three-dimensional end-effector-minus-target vector, and four wrapped
  angular errors. The four errors are the shoulder/elbow errors to the
  positive-elbow and negative-elbow inverse-kinematic solutions.
  [R6: `reach_observation`, `OBSERVATION_SIZE`]
- **Repository fact - derived target features.** The two inverse-kinematic
  solutions are computed from the target x/y coordinates and the fixed link
  lengths. The elbow cosine is clipped before `arccos`, and angle errors are
  wrapped to [-pi, pi]. These features are derived quantities, not additional
  physical sensors. [R6]
- **Repository fact - observation timing.** The observation returned by
  `step` is constructed after the ten MuJoCo substeps. The observation does
  not contain the action, elapsed episode step, current held-step count,
  previous distance, target radius/angle as named fields, torque, acceleration,
  contact force, or solver state. [R5; R6]
- **Repository fact - evaluation action selection.** The visible research
  evaluator calls the runtime with `deterministic=True`; a saved runtime may
  apply observation normalization or policy recurrence, but the physical
  action mapping remains the identity before environment clipping.
  [R7: `PolicyRuntime`; R8]

## Physical consequences

### Kinematic workspace and inverse-kinematic alternatives

- **Reasoned implication - forward kinematics.** With
  `l1 = 0.12 m`, `l2 = 0.10 m`, and `h = 0.02 m`, the site position implied
  by the body tree is
  `p(q) = (l1*cos(q_s) + l2*cos(q_s+q_e),
  l1*sin(q_s) + l2*sin(q_s+q_e), h)`. The planar Jacobian has determinant
  `det(J_xy) = l1*l2*sin(q_e)`. Thus the elbow angle determines both radial
  reach and local Cartesian conditioning.
  - **Decision relevance:** This determines whether a failure should first be
    attributed to geometric reachability, branch selection, or control
    dynamics, and whether geometry-stratified analysis is needed.
  - **Assumptions:** The XML body translations are interpreted by the
    standard serial-body transform, the site is the controlled point, and no
    contact or hidden constraint changes the nominal kinematics.
  - **Sources:** [R1: body tree, joint axes, site]; [R2: link constants];
    [R6: the same planar IK equations].
  - **Discriminating evidence:** Forward-kinematic reconstruction from
    recorded `qpos` and a target-to-site residual would support the model.
    A systematic residual, branch-specific offset, or nonzero out-of-plane
    motion would weaken it and point to a compiled-model or evaluator
    semantic difference.

- **Reasoned implication - reachable radial interval.** Ignoring the shoulder
  orientation limit, `r^2 = l1^2 + l2^2 + 2*l1*l2*cos(q_e)` gives an ideal
  annulus from 0.02 m to 0.22 m. The elbow limit of 170 degrees raises the
  minimum nominal radius to about 0.0277 m, while the maximum remains 0.22 m.
  Official target radii 0.06-0.20 m are inside this interval.
  - **Decision relevance:** The official radial range is not expected to
    contain an intrinsically unreachable target under nominal kinematics, so
    early campaign decisions can distinguish capability limits from
    reachability limits rather than treating all failures as equivalent.
  - **Assumptions:** The stated link lengths are the effective site lengths;
    joint limits are the only kinematic bounds; and default collision
    handling does not remove a target from the nominal workspace.
  - **Sources:** [R1; R2; R3; R4].
  - **Discriminating evidence:** An analytic IK residual and measured
    end-effector position for targets spanning radius and angle would support
    this implication. Nonzero residuals at interior targets would weaken it
    and make joint limits, contacts, or evaluator differences consequential.

- **Reasoned implication - two valid point-postures, with limit filtering.**
  For every official radius, the law of cosines gives an open branch
  `q_e = +acos(c)` and a folded branch `q_e = -acos(c)`. At 0.06 m the
  elbow magnitude is about 150.6 degrees; at 0.20 m it is about 49.5
  degrees. The shoulder angle is correspondingly chosen from the target
  bearing and the forearm offset. At least one branch remains within the
  +/-170-degree shoulder limit for every official bearing, although both
  branches need not remain valid near angular boundaries.
  - **Decision relevance:** Branch choice can change travel distance, joint
    limit margin, Jacobian conditioning, dynamics, and possible capsule
    self-contact. It can therefore change policy architecture, diagnostic
    grouping, and the interpretation of a candidate comparison.
  - **Assumptions:** The target is a point-center objective with no required
    end-effector orientation, and the visible IK equations match the
    official geometry.
  - **Sources:** [R1: joint ranges and lengths]; [R3: target geometry];
    [R6: `elbow_open`, `elbow_folded`, and `shoulder_for_elbow`].
  - **Discriminating evidence:** The sign of `q_e`, the two IK error pairs,
    final joint-limit margins, and target-conditioned success would show
    whether successful behavior uses one or both branches. A branch with
    persistent failure despite small analytic IK residual would implicate
    dynamics or contact rather than point reachability.

### Initial-state geometry and required motion

- **Reasoned implication - fixed singular start.** At reset,
  `q_s=q_e=0` and the end effector is nominally `(0.22, 0, 0.02)`.
  This is the fully extended configuration, where `det(J_xy)=0`; first-order
  Cartesian motion has only one direction. The target, however, is sampled
  over all bearings and radii, so the initial target error varies from a
  near target at positive x to targets requiring a large reorientation.
  - **Decision relevance:** The first control transient can dominate
    time-to-entry and overshoot. A policy that reaches after leaving the
    singular configuration is solving a different control problem from one
    that only regulates near a target.
  - **Assumptions:** The visible reset is the official reset, and the
    nominal forward kinematics apply at q = 0.
  - **Sources:** [R1: link placement]; [R5: `reset`]; [R3-R4: target
    range and angle].
  - **Discriminating evidence:** Initial `q`, `qdot`, distance, target
    bearing, and the first several control actions would support this
    explanation. If initial states vary or are not extended, the fixed-start
    mechanism must be revised.

- **Reasoned implication - target radius changes both geometry and control
  conditioning.** The official range avoids the exact outer and limited-inner
  radial boundaries, but targets near the inner boundary require a more folded
  elbow and have a smaller `|sin(q_e)|` than targets near the outer boundary.
  Conditioning varies non-monotonically across the full range because
  `|sin(q_e)|` is largest near a right-angle elbow. The target bearing also
  changes the required shoulder motion and joint-limit margin. A uniform
  radius sampler is not uniform area density: per unit planar area it places
  relatively more probability near the inner radii.
  - **Decision relevance:** Aggregate success can hide a radial or angular
    capability gap. The first campaign comparisons can change if failures
    cluster by radius, bearing, branch, or joint-limit margin.
  - **Assumptions:** The visible radius and angle sampler is the official
    sampler; target episodes are independent; and no hidden initial-state
    randomization is added.
  - **Sources:** [R3; R5: `_sample_target_position`; R10: baseline training
    range].
  - **Discriminating evidence:** A target histogram and outcome/trajectory
    stratification by radius, bearing, and analytic IK branch would support
    or weaken this distributional explanation. Agreement between the
    protected evaluator's target statistics and the visible sampler would
    resolve the official-sampler assumption.

### Torque actuation, damping, and dynamic authority

- **Reasoned implication - direct joint torque with configuration-dependent
  Cartesian effect.** Under the MuJoCo motor transmission convention, the
  scalar control `u_i` produces nominal generalized motor force proportional
  to `gear*u_i`; with gear 5 and clipped `u_i` in [-1, 1], the nominal
  hinge torque range is about +/-5 in model torque units. A schematic
  equation is
  `M(q)*qdd + C(q,qdot)*qdot + 0.5*qdot + constraints =
  tau_motor`, with armature 0.01 included in the effective generalized
  inertia and gravity absent. The mapping from joint torque to end-effector
  acceleration depends on `q` through both `M` and `J`.
  - **Decision relevance:** Action scaling, action repeat, model-based
    assumptions, and the expected benefit of torque regularization depend on
    stopping authority and Cartesian authority, not just on the action-space
    bounds.
  - **Assumptions:** The motor shortcut has its standard MuJoCo
    transmission semantics, no hidden actuator dynamics or force limit is
    injected, and compiled masses are finite and positive.
  - **Sources:** [R1: motor, gear, damping, armature, gravity, timestep];
    [R5: clipping and `data.ctrl` assignment]; [R7].
  - **Discriminating evidence:** Measured `qdd` under controlled positive and
    negative actions at several configurations, along with actual actuator
    force and saturation traces, would support the authority model. A
    configuration-independent acceleration or an effective torque below the
    nominal range would revise it.

- **Reasoned implication - damping removes velocity but not position error.**
  The 0.5 hinge damping dissipates motion, but the model has no declared
  positional servo or spring. With zero gravity, zero velocity, and zero
  motor torque, an arbitrary non-contact posture can remain an equilibrium;
  damping alone does not restore a displaced end effector to the target.
  A hold therefore requires state-dependent feedback, not merely waiting for
  passive settling.
  - **Decision relevance:** A policy can enter the tolerance band and still
    fail the episode if it does not supply a restoring action. This separates
    reach skill from stabilization skill and changes which diagnostics are
    useful for candidate selection.
  - **Assumptions:** No hidden default stiffness or contact force acts at the
    final posture, and the motor control is torque-like rather than a hidden
    position controller.
  - **Sources:** [R1: joint and actuator definitions]; [R5: hold logic].
  - **Discriminating evidence:** A zero-action perturbation/settling trace
    would support the absence of a positional attractor if velocity decays
    while position remains displaced. Return toward the target without motor
    torque would weaken this implication and identify an omitted force or
    contact mechanism.

- **Reasoned implication - the 20 ms action hold creates sampled-data
  trajectory control.** The policy cannot correct during the ten physics
  substeps; each action is piecewise constant for 20 ms. A high-speed
  approach can cross the tolerance boundary between controller updates or
  enter the band with enough kinetic energy to leave it at the next sampled
  check. The same action can have different effects as configuration and
  velocity change within the interval.
  - **Decision relevance:** Reach time, entry velocity, braking distance,
    action saturation, and control frequency are more informative than
    minimum distance alone when deciding whether a candidate has a
    convergence or stabilization deficit.
  - **Assumptions:** The visible frame skip and post-substep observation are
    the official interaction semantics, and the policy has no asynchronous
    control path.
  - **Sources:** [R4; R5: `frame_skip`, `step`; R8: episode loop].
  - **Discriminating evidence:** Physics-substep distance/velocity traces
    and control-step traces would distinguish true continuous excursions
    from endpoint-only apparent holds. Repeated boundary crossing within a
    20 ms interval would weaken an endpoint-only explanation of success.

### Coupled reach, convergence, and uninterrupted stabilization

- **Reasoned implication - success is a sequential conjunction.** A successful
  episode must (1) select a reachable posture and generate a trajectory
  toward the target, (2) reduce position and velocity enough to enter the
  1 cm ball, and (3) maintain the coupled joint state inside the ball for
  100 consecutive control observations. The later requirements are not
  implied by a small minimum distance.
  - **Decision relevance:** A single success percentage cannot identify the
    limiting capability. The first campaign decisions can differ for
    reach failures, late overshoot, repeated interruptions, and stable
    convergence.
  - **Assumptions:** Success uses the complete uninterrupted hold exactly as
    stated in the task contract, and no unobserved terminal grace period
    exists.
  - **Sources:** [R3: success criterion]; [R4-R5: tolerance, hold counter,
    termination]; [R8: `first_reach_step`, `max_held_steps`,
    `hold_interruptions`].
  - **Discriminating evidence:** Joint and Cartesian traces labeled with
    first entry, first exit, longest held run, entry velocity, and final
    distance would separate the three stages. If all failures have long
    stable runs but no termination, the hold interpretation or counter
    semantics would need revision.

- **Reasoned implication - the tolerance ball induces a posture-dependent
  joint tube.** Near a nonsingular solution, a small joint perturbation
  produces `delta p ~= J*delta q`; the allowable joint error for a 1 cm
  Cartesian tolerance depends on the singular values of `J` and on the
  selected branch. Near a singularity, some joint changes produce little
  first-order Cartesian displacement while other directions lose authority.
  The target has no orientation requirement: site position is evaluated
  directly, while site velocity matters indirectly because it determines
  whether that position remains within tolerance.
  - **Decision relevance:** Stable holds should be analyzed in both Cartesian
    error and joint velocity/branch coordinates. A policy may look jointwise
    noisy yet remain in tolerance, or look jointwise quiet while a sensitive
    Cartesian direction causes interruption.
  - **Assumptions:** The target is a point-center position objective and
    `J` from the nominal link geometry describes local motion.
  - **Sources:** [R1-R3]; [R6: site error and IK features].
  - **Discriminating evidence:** Singular values/condition numbers evaluated
    along successful and failed traces, paired with Cartesian error and
    hold interruptions, would support or weaken this local-tube explanation.

- **Reasoned implication - branch choice and dynamic coupling are inseparable.**
  The arm has two actuators for two joint coordinates, but the shoulder and
  elbow motions are dynamically coupled through the serial inertia and
  kinematically coupled at the site. A branch with a shorter or better
  conditioned route may still have different inertia, damping work, joint
  limits, or possible self-contact. The controller cannot choose a Cartesian
  acceleration independently of joint configuration.
  - **Decision relevance:** A branch-conditioned policy or a single policy
    covering both branches are scientifically distinct capabilities. The
    choice affects generalization over bearing and radius and the meaning of
    a training comparison.
  - **Assumptions:** Both motor channels remain available throughout the
    workspace and the simulator does not impose an unmodeled branch
    preference.
  - **Sources:** [R1: serial morphology and two motors]; [R6: branch errors];
    [R8: geometry diagnostics].
  - **Discriminating evidence:** Compare branch occupancy, action/velocity
    traces, joint-limit margins, and interruption rates at matched target
    geometries. Equal branch-conditioned outcomes would weaken the need to
    explain performance through branch selection; systematic differences
    would support it.

### Observation, control, and task-state observability

- **Reasoned implication - the physical target is reconstructable but not
  explicitly named.** The observation gives `q`, from which the site position
  is determined by the known geometry, and gives `p_site - p_target`.
  Therefore a controller with the model structure can reconstruct the target
  position and its radius/bearing algebraically, even though those fields are
  not direct observation entries. The four IK errors provide a second,
  branch-oriented representation of the same target relation.
  - **Decision relevance:** Apparent target-estimation failure should not be
    assumed from the absence of a target-coordinate field. The relevant
    question is whether the learned policy can exploit the available
    representation and whether branch features improve conditioning.
  - **Assumptions:** The policy receives the exact 11-element observation,
    knows or can learn the fixed link geometry, and the observation functions
    are the ones frozen into a saved runtime.
  - **Sources:** [R2; R6; R7: policy I/O persistence].
  - **Discriminating evidence:** Reconstruct target coordinates from
    observation alone and compare them with `mocap_pos`; systematic
    reconstruction error would revise the observability claim.

- **Reasoned implication - the instantaneous mechanical state is mostly
  observed, but the task automaton is not.** `q`, `qdot`, and target-relative
  position are sufficient in principle for the visible deterministic
  mechanical transition given a new action. However, the observation omits
  `held_steps`, elapsed time, previous distance, and whether a prior
  in-tolerance run was interrupted. Two episodes can have identical physical
  observations but different remaining hold durations and different success
  prospects.
  - **Decision relevance:** A feed-forward policy cannot infer exact hold
    progress from one observation. A controller that simply maintains a
    robust state can avoid needing the counter, whereas a policy relying on
    phase or time requires internal memory or a conservative invariant.
  - **Assumptions:** The success counter is not exposed through an auxiliary
    channel and candidate policies are not guaranteed to be recurrent.
  - **Sources:** [R5: `_held_steps`, `_step_count` and `step`]; [R6:
    observation construction]; [R7: optional runtime state handling].
  - **Discriminating evidence:** Present the same physical observation after
    different hold histories and inspect identical-policy actions. Different
    outcomes under identical state-action pairs would expose task-state
    dependence; successful invariant holds would weaken the practical
    importance of explicit hold observability.

- **Reasoned implication - unavailable forces and solver state limit causal
  attribution.** The policy does not observe torque, acceleration, contact
  force, compiled inertia, or numerical constraint state. An observed
  end-effector error can therefore be caused by action saturation, inertial
  coupling, damping, branch geometry, a limit constraint, contact, or the
  action-hold timing without being distinguishable from the observation
  alone.
  - **Decision relevance:** If failure mechanisms are not instrumented,
    changing the policy or reward can improve an aggregate score without
    identifying why. Mechanism claims require simulator-side traces in
    addition to policy observations.
  - **Assumptions:** No hidden observation wrapper exposes those quantities
    and the visible runtime is the complete controller interface.
  - **Sources:** [R5-R7]; [R8: currently recorded diagnostics].
  - **Discriminating evidence:** A trace containing `q`, `qdot`, action,
    torque, constraint/contact indicators, and substep error would separate
    the candidate causes. Agreement of these traces across alternatives
    would weaken a mechanism-specific attribution.

### Failure classes and meaningful physical quantities

- **Reasoned implication - qualitatively distinct failure classes exist.**
  The coupled system permits at least: target/branch or joint-limit failure;
  slow or misdirected reach; high-speed entry and overshoot; oscillatory or
  drifting hold; actuator saturation or insufficient braking; interruption
  at the control-sampling boundary; and numerical/contact behavior near
  constrained postures. These classes can produce the same binary failure.
  - **Decision relevance:** The first useful scientific comparison depends on
    which class is limiting. A candidate with a better minimum distance but
    worse uninterrupted hold is not equivalent to a candidate with slower
    but stable convergence.
  - **Assumptions:** The target range and model admit the stated nominal
    branches, and the hidden evaluator does not collapse all classes into a
    different success rule.
  - **Sources:** [R1-R8].
  - **Discriminating evidence:** For each episode, the meaningful minimum
    set is target radius/bearing, chosen branch, joint-limit margin,
    `q`/`qdot`, action and saturation, Cartesian distance, first-entry
    step and velocity, longest held run, interruption count, and
    substep-versus-control-step excursions. Their joint distributions would
    support or revise the class assignment.

- **Reasoned implication - complete-behavior quantities should be tied to
  mechanisms, not only reward.** The physically meaningful trajectory
  quantities are target geometry; `q`, `qdot`, and `qdd`; end-effector
  position and distance; Jacobian rank/conditioning; nominal torque and
  action saturation; joint-limit and contact margins; entry speed and
  stopping distance; hold-run length and interruptions; and time to success
  or truncation. The visible evaluator already records target radius/angle,
  minimum and final distance, first reach step, maximum held steps,
  in-tolerance steps, and hold interruptions.
  - **Decision relevance:** These quantities can distinguish reach,
    convergence, stabilization, and observability explanations even when
    reward coefficients or learning recipes change.
  - **Assumptions:** The recorded diagnostic fields refer to the visible
    shared mechanics and are not silently replaced by a different evaluator
    definition.
  - **Sources:** [R8: `episode_diagnostics`]; [R9: reward is not the task
    outcome]; [R1-R6].
  - **Discriminating evidence:** Agreement between these traces and the
    binary success label, with failures partitioned by the proposed class,
    would support the measurement model. A diagnostic that cannot predict
    or explain interruptions would weaken its claimed causal value.

## Unknowns

### Compiled mass, inertia, integration, and solver behavior

- **Unresolved quantity - effective link mass and inertia.** The XML gives
  capsule geometry but does not state body masses, geom densities, inertial
  tensors, compiler settings, or the resulting configuration-dependent
  `M(q)`. The armature term is explicit, but it is not the whole robot
  inertia.
  - **Decision relevance:** This can change whether +/-5 nominal torque
    provides rapid reach, whether braking is possible in 20 ms increments,
    and whether a model-based or purely feedback interpretation is credible.
  - **Assumptions:** The visible model is compiled without a separate
    runtime mass override and the XML is the complete human-owned dynamics
    definition.
  - **Sources:** [R1: explicit geometry/armature but no mass/inertia
    attributes]; [R5: `MjModel.from_xml_path`].
  - **Discriminating evidence:** The compiled `MjModel` mass/inertia fields
    or controlled action-to-acceleration measurements would resolve this.
    A measured response inconsistent with the nominal torque equation would
    weaken the current authority estimate.

- **Unresolved quantity - numerical integrator and constraint defaults.**
  The timestep is explicit, but the XML does not explicitly state the
  integrator, solver, tolerances, joint-limit softness, contact parameters,
  or constraint stabilization. These defaults can matter near the +/-170
  degree limits and during any capsule contact.
  - **Decision relevance:** Numerical stiffness, limit bounce, and substep
    accuracy can look like policy oscillation or actuator failure and can
    alter the reliability of a 1 cm, 2 s criterion.
  - **Assumptions:** The protected evaluator uses the same compiled MuJoCo
    option defaults as the visible environment.
  - **Sources:** [R1: only gravity and timestep are explicit in `<option>`];
    [R5: repeated `mj_step`].
  - **Discriminating evidence:** A compiled-option inspection plus
    timestep/substep convergence and limit-contact traces would support or
    revise this explanation.

### Contact and physical interaction semantics

- **Unresolved quantity - upper-arm/forearm capsule contact.** The plane,
  base, and target are non-colliding by explicit flags, but the link geoms
  do not explicitly disable collision. The readable XML therefore does not
  establish whether folded postures generate self-contact under the
  simulator's default filtering.
  - **Decision relevance:** Contact can eliminate or destabilize one IK
    branch, add unobserved forces, and make branch-conditioned failures
    look like poor policy control.
  - **Assumptions:** MuJoCo default geom filtering is not treated as an
    intended scientific task definition unless confirmed in the compiled
    model.
  - **Sources:** [R1: geom `contype`/`conaffinity` attributes]; [R5:
    model loading and stepping].
  - **Discriminating evidence:** Contact counts, contact forces, active
    constraints, and folded-branch traces would resolve whether contact is
    present and consequential. A contact-free compiled rollout would weaken
    this unknown.

- **Unresolved quantity - protected evaluator's intermediate-time
  semantics.** The task contract says "continuously" and equates 2 s with
  100 control steps. The visible environment updates the hold counter once
  after each ten-substep action and does not test the distance between those
  update points. The readable source does not expose whether the protected
  final assessment adds a finer-grained continuous check.
  - **Decision relevance:** This can change the meaning of a successful
    endpoint-only hold, the safety margin needed around the 1 cm boundary,
    and which trajectory diagnostics are scientifically valid.
  - **Assumptions:** The contract remains the official authority while the
    visible environment is only the accessible implementation reference.
  - **Sources:** [R3: continuous hold language]; [R4-R5: 100-step counter
    and post-substep distance test]; [R8].
  - **Discriminating evidence:** The exact protected task-reference
    semantics or a physics-substep trace from the official evaluator would
    support one interpretation. A policy that succeeds at control-step
    samples but exits between them would weaken the endpoint-only
    interpretation.

### Effective control authority and timing

- **Unresolved quantity - acceleration, braking, and settling margins.**
  The action and gear bounds establish nominal torque, but the readable
  definitions do not establish the resulting `qdd`, stopping distance, or
  settling time at each target geometry. These depend on compiled inertia,
  velocity, configuration, damping, and any active constraints.
  - **Decision relevance:** This can change whether failures are primarily
    due to insufficient control authority, poor policy timing, or inadequate
    target-state regulation, and therefore can change the first diagnostic
    priority.
  - **Assumptions:** The motor is not internally filtered and action
    clipping is the only intentional saturation.
  - **Sources:** [R1; R5; R7].
  - **Discriminating evidence:** Matched configuration/action response
    traces with torque saturation, `qdot`, `qdd`, and distance-to-target
    would discriminate authority from policy-error explanations.

- **Unresolved quantity - official reset and sampler identity.** The visible
  shared environment starts at zero joint state and samples radius and angle
  as described, while the task contract defines the official distribution
  but does not reproduce the protected evaluator implementation. The exact
  protected reset path and whether it uses radial-uniform rather than
  area-uniform sampling are not independently established here.
  - **Decision relevance:** A mismatch would change exposure weighting,
    initial transient statistics, and the interpretation of development
    performance relative to the 98 percent objective.
  - **Assumptions:** The protected evaluator is permitted to be separate
    from the visible research environment while preserving the contract's
    stated task boundary.
  - **Sources:** [R3]; [R5: `reset` and `_sample_target_position`]; [R10:
    training-only range].
  - **Discriminating evidence:** The protected task-reference target
    histogram and initial-state trace would support or revise the visible
    reset/sampler model. A mismatch would be an evaluator-distribution
    issue, not evidence that the kinematic derivation is wrong.

### Observability and policy-runtime uncertainty

- **Unresolved quantity - practical use of internal memory.** The observation
  omits hold progress and elapsed time, but `PolicyRuntime` has a recurrent
  state interface and resets it at episode boundaries. The readable physical
  model therefore does not establish whether a candidate policy uses memory,
  how normalization changes numerical conditioning, or whether it acts as a
  memoryless controller in practice.
  - **Decision relevance:** This can change whether a hold failure is treated
    as a sensing/phase problem or as a feedback-stability problem, and can
    affect comparisons between policy classes.
  - **Assumptions:** The saved runtime preserves the policy I/O and any
    normalizer exactly, as required by [R7], and no extra observation channel
    is added.
  - **Sources:** [R6: observation omissions]; [R7: `PolicyRuntime.reset`,
    `episode_start`, and normalization].
  - **Discriminating evidence:** Inspecting saved runtime metadata together
    with actions under identical mechanical observations and different hold
    histories would resolve the practical role of memory.

- **Unresolved quantity - sensor and actuator fidelity beyond source code.**
  The visible functions expose exact floating-point simulator state and
  direct control, but they do not establish numerical precision effects,
  latency outside the ten substeps, or any protected-evaluator noise and
  perturbation model.
  - **Decision relevance:** Noise or delay would make a narrow 1 cm hold a
    robustness problem rather than only a deterministic stabilization
    problem, changing the expected value of margins and feedback speed.
  - **Assumptions:** The official task may add only what is consistent with
    its human-owned contracts; the readable source is not a complete
    declaration of hidden assessment instrumentation.
  - **Sources:** [R1; R5-R8].
  - **Discriminating evidence:** Repeated identical-seed rollouts and
    action/observation timestamp traces would support determinism and no
    extra delay. Seed-dependent state deviations under identical policy
    inputs would weaken that assumption.

### Official outcome and evidence limits

- **Unresolved quantity - exact fixed final panel identity and hidden
  implementation details.** The contract fixes the panel size, success
  threshold, and required count, but the readable contract does not expose
  the final panel seeds or every protected evaluator implementation detail.
  - **Decision relevance:** This affects final uncertainty and
    generalization assessment, though it does not change the nominal
    kinematic requirement or the 196/200 threshold.
  - **Assumptions:** The protected assessment follows [R3] and does not
    change the official task boundary.
  - **Sources:** [R3: official final assessment]; [R8: visible research
    evaluation is explicitly not the official benchmark].
  - **Discriminating evidence:** The authoritative official result and its
    recorded panel metadata resolve this quantity. Development-panel
    success alone cannot resolve it.

## Decision-relevant synthesis

### **Reasoned implication - nominal geometry is feasible, but branch and conditioning are consequential**

- **Decision relevance:** The official target annulus is nominally reachable at every bearing, but there are two IK branches, a fixed-start singularity, varying Jacobian conditioning, and joint-limit margins. Early campaign interpretation should therefore separate geometric feasibility from branch-conditioned control failure.
- **Assumptions:** The XML body tree and link lengths are the official kinematics; the target is a point-position objective; hidden contact does not remove the nominal branches.
- **Source references:** [R1-R6].
- **Discriminating evidence:** Analytic FK/IK residuals, branch sign, Jacobian singular values, joint-limit margins, and success/hold outcomes stratified by target radius and bearing.

### **Unresolved quantity - effective inertia, solver defaults, and contact**

- **Decision relevance:** The nominal +/-5 motor-torque range and 20 ms action hold do not establish reach speed, braking authority, or branch stability. Unresolved compiled dynamics or capsule contact could change whether the first campaign gap is policy control, numerical behavior, or physical branch feasibility.
- **Assumptions:** The XML is complete except for simulator defaults, and the protected evaluator uses the same compiled model semantics as the visible loader.
- **Source references:** [R1: explicit and omitted dynamic/contact attributes]; [R5: `MjModel.from_xml_path` and `mj_step`].
- **Discriminating evidence:** Compiled mass/inertia/options, contact and constraint traces, and matched action-to-acceleration/braking measurements.

### **Reasoned implication - reach is not hold**

- **Decision relevance:** A minimum-distance success proxy is insufficient. The task requires low enough entry velocity and a feedback policy that keeps the site inside a 1 cm ball for 100 consecutive control updates; damping alone does not restore position. The first decision can change depending on whether failures are slow reach, overshoot, drift, or interruption.
- **Assumptions:** The continuous-hold contract and visible counter semantics are authoritative for campaign interpretation, and no hidden positional servo exists.
- **Source references:** [R1: damping/no spring]; [R3-R5: success, timing, and hold logic]; [R8: hold diagnostics].
- **Discriminating evidence:** Time-to-first-entry, entry `qdot`, substep distance, longest held run, interruption count, final distance, and action saturation over complete episodes.

### **Reasoned implication - the observation exposes mechanics but not hold phase**

- **Decision relevance:** The controller can reconstruct target geometry from `q` and site error and receives velocity, but it does not receive elapsed time or held-step progress. Stable state feedback can solve this omission; a phase-dependent strategy may require recurrent memory. This distinction can change how a hold failure is attributed.
- **Assumptions:** The 11-element observation and saved policy runtime are preserved exactly, with no hidden task-state input.
- **Source references:** [R6: observation layout and derived IK features]; [R7: runtime reset/state handling]; [R5: hidden hold counter].
- **Discriminating evidence:** Algebraic target reconstruction and matched-observation action tests across different hold histories; recurrent-state metadata where available.

### **Unresolved quantity - visible versus protected interaction semantics**

- **Decision relevance:** The visible environment checks distance after each ten-substep action, while the contract uses "continuously" and the protected evaluator is not readable. If intermediate excursions count, endpoint-only stability can overstate capability; if they do not, substep excursions remain a simulator diagnostic rather than an official failure.
- **Assumptions:** The protected evaluator may add semantics not reproduced in the visible research environment but must preserve the task contract.
- **Source references:** [R3: official criterion]; [R5: post-action hold update]; [R8: visible research evaluation].
- **Discriminating evidence:** Protected task-reference semantics or official physics-substep traces, compared with endpoint and intermediate distance histories.
