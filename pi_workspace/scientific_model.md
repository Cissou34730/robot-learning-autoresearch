## Established facts

### Human task and assessment

- **[Fact]** The official system is a two-joint arm whose target is sampled with radius in
  0.06--0.20 m and angle over the full circle. The end effector must be at most
  0.01 m from the target for 2.0 s without an interruption. The official control
  timing defines this as 100 consecutive control steps. **Source:** `contracts/scenario.md`;
  `contracts/task_spec.py` (`TARGET_RADIUS_RANGE`, `SUCCESS_THRESHOLD`, `HOLD_SECONDS`,
  `FRAME_SKIP`).
- **[Fact]** The final assessment uses one frozen policy, 200 episodes, at most 500
  control steps per episode, and requires at least 196 successes (98%). **Source:**
  `contracts/scenario.md`.
- **[Fact]** A success is an episode-level conjunction: the hold counter must reach
  100; merely reaching the tolerance once, accumulating reward, or terminating for
  another reason is not success. **Source:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`, `step`.

### Morphology, coordinates, and kinematic structure

- **[Fact]** The robot is a serial planar 2R chain. The shoulder and elbow are hinge
  joints about the world z axis, with relative joint coordinates
  \(q=(q_1,q_2)\), link lengths \(l_1=0.12\) m and \(l_2=0.10\) m. The upper-arm
  body is translated to z=0.02 m, and the forearm is attached at the upper-arm
  endpoint; the end-effector site is at the forearm endpoint. **Source:**
  `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py` (`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`).
- **[Fact]** Each joint has the limit \([-170^\circ,170^\circ]\). There are two
  actuated coordinates and no floating-base coordinates in the robot definition.
  **Source:** `contracts/robots/two_joint_arm.xml`, `shoulder` and `elbow` joints.
- **[Fact]** The target is a mocap body with a non-contacting sphere. Reset places its
  z coordinate at the current end-effector z, so official targets lie in the arm's
  horizontal plane. The plane geom and target geom have contact disabled; the XML
  does not define a physical grasp or target reaction. **Source:**
  `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`, `_sample_target_position`.

### Actuation and simulator timing

- **[Fact]** The MuJoCo model sets gravity to zero and the base option timestep to
  0.002 s. Each environment action is clipped to two values in \([-1,1]\), copied
  to `data.ctrl`, and held while ten MuJoCo steps execute. Thus the environment
  presents a 0.020 s control interval (50 Hz) while integrating at 500 Hz.
  **Source:** `contracts/robots/two_joint_arm.xml`, `<option>` and `<actuator>`;
  `robot_learning/scenario/environment.py`, `step`.
- **[Fact]** Each actuator is a MuJoCo motor attached directly to one joint, with
  `ctrlrange="-1 1"` and `gear="5"`. Both joints have damping 0.5 and armature
  0.01 in the XML. No gravity compensation or position servo is declared.
  **Source:** `contracts/robots/two_joint_arm.xml`.
- **[Fact]** The default policy I/O passes observations and actions through unchanged.
  The loaded policy runtime can nevertheless carry a frozen alternative I/O
  mapping; recurrent policy state is reset at the start of an episode. **Source:**
  `robot_learning/scenario/policy_io.py`;
  `contracts/policy_runtime.py`, `PolicyRuntime`; `robot_learning/scenario/environment.py`.

### Reset and initial physical state

- **[Fact]** Reset calls MuJoCo data reset, then explicitly sets both joint positions
  and velocities to zero, forwards the model, samples a target, and forwards again.
  The initial arm is therefore straight along +x, with endpoint approximately
  \((0.22,0,0.02)\) m and zero joint velocity. The XML target position is not the
  official reset target because reset overwrites it. **Source:**
  `robot_learning/scenario/environment.py`, `reset` and `_sample_target_position`;
  `contracts/robots/two_joint_arm.xml`.
- **[Fact]** The official environment samples angle and radius independently and
  uniformly in the configured ranges. The training-only baseline samples the
  narrower radius range 0.14--0.20 m, whereas evaluation uses 0.06--0.20 m.
  **Source:** `robot_learning/scenario/environment.py`, `_sample_target_position`
  and `make_evaluation_env`; `robot_learning/training/environment.py`,
  `TRAINING_TARGET_RADIUS_RANGE`.

### Observation and outcome interface

- **[Fact]** The nominal observation has 11 float32 entries:
  \(q_1,q_2,\dot q_1,\dot q_2\), the three-dimensional end-effector-minus-target
  vector, and four wrapped angular errors to the open and folded inverse-kinematic
  solutions. **Source:** `robot_learning/scenario/observations.py`,
  `OBSERVATION_SIZE` and `reach_observation`.
- **[Fact]** At each control step, distance is the Euclidean norm of the
  end-effector-to-mocap-target vector. A distance at or below 0.01 m increments
  the hold counter; any later sampled distance above it resets that counter to
  zero. Success and termination are therefore evaluated at control-step
  boundaries after the ten internal MuJoCo steps, not from reward alone.
  **Source:** `robot_learning/scenario/environment.py`, `step`.
- **[Fact]** Evaluation records target radius and angle, minimum and final distance,
  first tolerance-entry step, maximum held steps, in-tolerance steps, and hold
  interruptions, in addition to the binary episode outcome. These are diagnostic
  quantities, not alternate success definitions. **Source:**
  `robot_learning/scenario/evaluation.py`.
- **[Fact]** The baseline reward combines distance progress, exponential
  closeness, hold-progress potential, an action-squared cost, an optional
  outside-band term, and a completion bonus. These terms are training signals;
  the environment's hold counter, not reward, defines success. **Source:**
  `robot_learning/training/reward.py`; `robot_learning/scenario/environment.py`.

## Physical consequences

### Kinematics, workspace, and inverse solutions

- **[Implication]** In the horizontal plane the forward kinematics are
  \[
  x=l_1\cos q_1+l_2\cos(q_1+q_2),\quad
  y=l_1\sin q_1+l_2\sin(q_1+q_2),\quad z=0.02.
  \]
  With unconstrained joints the reachable radii are the annulus
  \(\lvert l_1-l_2\rvert\le r\le l_1+l_2\), namely 0.02--0.22 m. The official
  0.06--0.20 m radial interval is inside this annulus, so geometric reachability
  is not expected to be the dominant limitation. **Decision relevance:** this
  changes whether early work should prioritize reachability or control quality
  and generalization. **Assumptions:** the serial-body frame translations have the
  standard MuJoCo composition and no contact exclusion removes a nominal
  configuration. **Sources:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `contracts/scenario.md`. **Discriminating
  evidence:** compute the compiled model's site position over the joint limits
  and compare target-conditioned inverse solutions with observed minimum distance.
- **[Implication]** For a target \((r,\alpha)\), the two planar inverse solutions
  are
  \[
  q_2=\pm\arccos\frac{r^2-l_1^2-l_2^2}{2l_1l_2},\qquad
  q_1=\alpha-\operatorname{atan2}(l_2\sin q_2,l_1+l_2\cos q_2).
  \]
  Over the official radial range, the magnitude of the elbow solution is about
  49.5--150.5 degrees, so the elbow limit does not remove these nominal
  branches. The shoulder limit can remove one branch for some target angles,
  but the symmetric alternative remains available in the ideal planar model.
  **Decision relevance:** branch choice can determine path length, shoulder
  travel, transient torque, and hold robustness; it also prevents treating one
  desired joint configuration as the unique solution. **Assumptions:** angles
  are interpreted modulo \(2\pi\), the target is exactly in the z=0.02 plane,
  and link geometry is represented by the endpoint site rather than capsule
  clearance. **Sources:** `robot_learning/scenario/observations.py`,
  `contracts/robots/two_joint_arm.xml`, `contracts/scenario.md`.
  **Discriminating evidence:** log selected joint trajectories and compare
  branch-consistent final configurations, travel, peak action, and hold
  interruptions by target geometry.
- **[Implication]** The planar Jacobian loses rank when
  \(\sin q_2=0\), at the fully extended or fully folded singularities. Official
  targets do not require the exact outer singularity (r<=0.20 m versus 0.22 m),
  and their nominal elbow angles are bounded away from 0 and \(\pi\); however,
  velocity-to-endpoint mapping and numerical conditioning still vary with
  configuration. **Decision relevance:** this affects whether endpoint error
  control, joint-space control, or branch-aware control is credible near the
  radial edges. **Assumptions:** the two-link analytical Jacobian describes the
  compiled site and no unmodeled compliance changes it. **Sources:**
  `contracts/robots/two_joint_arm.py`; `robot_learning/scenario/observations.py`;
  XML endpoint geometry. **Discriminating evidence:** measure the local
  endpoint Jacobian or finite-difference endpoint velocity at target-conditioned
  configurations and relate its conditioning to settling error.

### Actuation and dynamic response

- **[Implication]** Under standard MuJoCo motor semantics, the command produces a
  joint torque proportional to gear times control, so the nominal direct-drive
  authority is approximately \(\tau_i\in[-5,5]\) in simulator torque units before
  the coupled dynamics and any other constraints. The command is not a desired
  angle or velocity: the motion follows the integrated rigid-body equations with
  configuration-dependent inertia, velocity coupling, damping, and armature.
  **Decision relevance:** saturation and torque-to-inertia ratio determine whether
  failures are caused by insufficient authority, poor timing, or policy
  stabilization. **Assumptions:** the installed MuJoCo motor interpretation and
  default actuator transmission are used, and no custom runtime action transform
  is present. **Sources:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; installed-version contract in
  `AGENTS.md`. **Discriminating evidence:** inspect compiled actuator force
  limits and measure joint acceleration under positive, negative, and zero
  commands at representative configurations.
- **[Implication]** Zero gravity removes the persistent gravitational torque that
  would otherwise have to be rejected during a hold. Damping 0.5 dissipates
  residual motion, while armature 0.01 adds actuator-side rotational inertia;
  neither creates a stiff position lock. A policy can therefore reach a static
  target and then use braking or small corrective torques, but residual momentum
  and discrete control updates can carry the endpoint outside the 1 cm band.
  **Decision relevance:** the first decision may need to distinguish convergence
  and braking from geometric reach failure. **Assumptions:** no active contacts
  or hidden actuator state injects force during the episode. **Sources:**
  `contracts/robots/two_joint_arm.xml`; `environment.py`, `step`.
  **Discriminating evidence:** compare approach velocity, action sign changes,
  distance overshoot, and hold interruptions around first tolerance entry.
- **[Implication]** The ten-substep action hold creates a sampled-data controller:
  the policy observes state, chooses one command, and then receives no correction
  for 20 ms while the simulator integrates. A trajectory that crosses the
  tolerance boundary between observations can still be counted in tolerance if
  its next sampled distance is inside; conversely, an endpoint excursion at any
  control boundary interrupts the hold. **Decision relevance:** this changes the
  value of faster feedback, conservative approach speed, and action smoothing.
  **Assumptions:** the environment implementation is the operative interaction
  semantics and no external callback observes the ten substeps. **Sources:**
  `environment.py`, `step`; `contracts/task_spec.py`. **Discriminating evidence:**
  compare substep trajectories with boundary distances and measure whether
  failures cluster immediately after action updates.

### Initial condition and target geometry

- **[Implication]** Every episode begins from the same straight, stationary arm,
  while the target varies in radius and angle. The controller must first leave a
  common near-singular straight configuration; targets at smaller radii require
  greater folding, and target angle changes the required shoulder travel and
  initial direction. In the ideal gravity-free, rotationally symmetric model,
  angle should mainly affect transient travel from this fixed start rather than
  the final static dynamics. **Decision relevance:** a policy trained only on
  outer radii or a narrow set of approach transients can fail official inner
  targets despite nominal reachability. **Assumptions:** the target sampling
  and reset code remain as specified and contact does not break rotational
  symmetry. **Sources:** `environment.py`, `reset` and `_sample_target_position`;
  `training/environment.py`; XML geometry. **Discriminating evidence:** stratify
  first-reach time, peak action, minimum distance, and hold success by radius and
  angle.
- **[Implication]** The official tolerance is a disk of radius 1 cm in the
  horizontal task plane, but distance is computed in 3-D. Because the target z
  is copied from the end effector at reset and joint motion is planar, vertical
  error should remain zero in this model; the effective success set is therefore
  a 2-D disk around each target. **Decision relevance:** this identifies whether
  observed failures can be attributed to planar control rather than height
  regulation. **Assumptions:** both joints remain pure z-axis hinges and no
  contact displaces bodies. **Sources:** XML joint axes and body geometry;
  `environment.py`, `_sample_target_position` and `_distance_to_target`.
  **Discriminating evidence:** inspect the z component of the relative
  observation and the full distance during episodes.

### Coupled capabilities required for success

- **[Implication]** Success is a serial requirement, not an average of reaching
  and holding: the policy must select a feasible branch, generate a controlled
  trajectory, enter the 1 cm set, reduce endpoint velocity sufficiently, and
  remain there for 100 sampled intervals. A policy can have low minimum distance
  yet fail because of slow convergence, overshoot, branch switching, or one
  hold interruption. **Decision relevance:** aggregate reward or one-time reach
  rate cannot identify the goal gap; the first useful diagnosis must separate
  reach, convergence, and stabilization. **Assumptions:** the diagnostic fields
  in evaluation reflect the same episode semantics as the outcome. **Sources:**
  `contracts/scenario.md`; `environment.py`, `step`; `evaluation.py`.
  **Discriminating evidence:** compare success with `first_reach_step`,
  `max_held_steps`, `hold_interruptions`, `final_distance_cm`, and
  `in_tolerance_steps`.
- **[Implication]** The local target error alone does not specify a unique joint
  state: two IK branches can give the same endpoint, and different joint
  velocities can give the same instantaneous endpoint error. The observation
  supplies joint position and velocity plus branch-relative errors, allowing a
  policy to infer these distinctions, but it does not force the policy to use a
  branch consistently. **Decision relevance:** branch-aware trajectory analysis
  can change the interpretation of apparently identical endpoint successes or
  failures. **Assumptions:** the nominal observation path is the one frozen into
  the evaluated runtime. **Sources:** `observations.py`; `policy_runtime.py`;
  planar XML morphology. **Discriminating evidence:** condition outcomes on
  \((q,\dot q)\) and identify whether successful trajectories remain on one
  branch.

### Learning signal versus physical objective

- **[Implication]** The shaped reward can favor reducing distance, accumulating
  hold progress, avoiding action magnitude, and receiving the completion bonus,
  but it does not make a one-time reach equivalent to a successful episode.
  With zero hold-exit forfeiture in the current reward, leaving the tolerance
  resets physical success progress even though the reward does not necessarily
  erase all prior shaped progress. **Decision relevance:** reward curves or
  training success proxies can overstate the physical capability needed for the
  official 98% episode objective. **Assumptions:** the baseline reward remains
  the learning signal and the policy is optimized against it rather than
  directly against the protected assessment. **Sources:**
  `robot_learning/training/reward.py`; `robot_learning/scenario/environment.py`;
  `contracts/scenario.md`. **Discriminating evidence:** compare cumulative
  reward components with binary success, hold interruptions, and the fraction
  of episodes reaching tolerance without completing the hold.

### Observability and control relation

- **[Implication]** With the default observation, the deterministic mechanical
  state relevant to this task is close to observable: \(q\) and \(\dot q\) are
  provided, the relative target vector is provided, and the target plane and
  fixed base make absolute target geometry recoverable. The four IK errors are
  redundant derived guidance features rather than independent sensors. **Decision
  relevance:** memory may not be needed to reconstruct the nominal Markov state,
  whereas memory or extra sensing would matter only if hidden simulator or
  runtime state affects motion. **Assumptions:** model parameters are fixed,
  there are no unreported contacts, actuator internal states, delays, or
  disturbances, and the policy receives the nominal observation unchanged.
  **Sources:** `observations.py`; `policy_io.py`; `environment.py`;
  `policy_runtime.py`. **Discriminating evidence:** test whether equal
  observations with equal actions produce equal subsequent states, and inspect
  the serialized runtime's observation/action mapping.
- **[Implication]** The controller closes the loop through the sequence
  observation -> action -> ten-step physical evolution -> new observation.
  Target position is not an action input and target motion is not an exogenous
  trajectory; it is fixed after reset. The task outcome is consequently a
  property of the coupled policy, current state, target, and simulator timing.
  **Decision relevance:** changes to observation preprocessing, action mapping,
  recurrent state, or sampling interval are changes to the closed-loop system,
  not merely learning hyperparameters. **Assumptions:** evaluation uses the
  saved runtime contract and the fixed environment construction. **Sources:**
  `environment.py`; `observations.py`; `policy_runtime.py`; `evaluation.py`.
  **Discriminating evidence:** compare the saved runtime hashes and I/O behavior
  with the source defaults, then replay identical seeds and actions.

## Unknowns

### Compiled inertial and contact properties

- **[Unknown]** The XML explicitly specifies damping and armature but does not
  specify body mass, density, inertia, friction coefficients, solver settings,
  or an integrator. MuJoCo will construct effective values from its compiled
  model and defaults, but their numerical values and any link self-contact
  effects are not established by the human-authored source alone. **Decision
  relevance:** this can change torque authority, transient duration, overshoot,
  and whether a controller designed from the visible dimensions transfers across
  configurations. **Assumptions:** compiled defaults and geometry are the only
  additional physical data. **Sources:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md` (locked MuJoCo version). **Discriminating evidence:** inspect the
  compiled `body_mass`, `body_inertia`, actuator limits, options, contact
  parameters, and contact pairs, then validate with free-decay and commanded
  step-response measurements.

### Exact closed-loop action and policy contract

- **[Unknown]** The source default maps action directly to `ctrl`, but an evaluated
  candidate carries a frozen `PolicyIO`, loader, normalizer, and possibly
  recurrent policy state. Before a candidate exists, the effective action scale,
  preprocessing, recurrence, and deterministic prediction path of that candidate
  are unknown. **Decision relevance:** apparent physical improvements or failures
  cannot be assigned to morphology or control design without knowing the actual
  runtime contract. **Assumptions:** saved runtime validation succeeds and the
  candidate is evaluated with its bound weights and statistics. **Sources:**
  `contracts/policy_runtime.py`; `robot_learning/scenario/policy_io.py`;
  `environment.py`, `make_evaluation_env`. **Discriminating evidence:** inspect
  runtime metadata and hashes, record the observation/action ranges presented to
  the model, and replay a fixed episode with logged actions.

### Effective numerical dynamics

- **[Unknown]** The source establishes the nominal 2 ms timestep and ten-step
  frame skip, but not the compiled integrator's numerical error, constraint
  solver behavior, or whether any contacts are active during a given trajectory.
  The physical interpretation of a one-centimeter boundary can therefore be
  sensitive to numerical details when the endpoint is close to that boundary.
  **Decision relevance:** this determines whether marginal hold failures are
  robust physical failures or simulator-resolution artifacts. **Assumptions:**
  the locked MuJoCo 3.12.0 runtime is used and no protected benchmark override
  changes the model. **Sources:** `contracts/robots/two_joint_arm.xml`;
  `AGENTS.md`; `environment.py`. **Discriminating evidence:** inspect compiled
  options and compare boundary outcomes under controlled repeated rollouts and
  recorded substep distances, without treating a changed simulator as official
  evidence.

### Target-conditioned difficulty and symmetry

- **[Unknown]** The mechanism by which performance varies over the official
  radius-angle distribution is not established. The equations predict branch
  alternatives and a fixed-start transient, but do not predict which branch a
  learned policy selects, how close it approaches action saturation, or whether
  failures concentrate at inner radii, particular angles, or the hold phase.
  **Decision relevance:** this can change whether the first campaign focus is
  distribution coverage, trajectory generation, or stabilization. **Assumptions:**
  the official panel samples the stated distribution and evaluation diagnostics
  are retained without selection bias. **Sources:** `contracts/scenario.md`;
  `environment.py`; `evaluation.py`; `training/environment.py`.
  **Discriminating evidence:** use target-stratified episode diagnostics and
  joint/action traces, with hold interruptions separated from first-reach misses.

### Boundary semantics for “continuous” hold

- **[Unknown]** The contract describes an uninterrupted 2-second hold, while the
  implementation checks distance only after each 20 ms control interval. It is
  not established from the contract wording alone whether any protected
  evaluator adds finer-grained checks; the visible environment does not.
  **Decision relevance:** this can change the required stabilization bandwidth
  and the interpretation of trajectories that leave the tolerance between
  checks. **Assumptions:** the visible shared environment and the protected
  official evaluator have identical interaction semantics, as the scenario
  contract intends. **Sources:** `contracts/scenario.md`;
  `contracts/task_spec.py`; `environment.py`, `step`; `AGENTS.md` on protected
  benchmark ownership. **Discriminating evidence:** verify official evaluator
  semantics when available and compare substep distance extrema with the binary
  success result; until then, do not infer continuous substep containment from
  the hold counter.

## Decision-relevant synthesis

### [Implication] Official coverage is broader than baseline training exposure

- **Decision relevance:** The official distribution includes 0.06--0.14 m targets
  that the baseline training environment does not expose; a policy can appear
  competent while lacking inner-radius folding and stabilization.
- **Assumptions:** the source training environment is used for the initial recipe
  and official evaluation uses the contract distribution.
- **Source references:** `contracts/scenario.md`; `robot_learning/training/environment.py`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** radius-stratified official-like evaluation of
  minimum distance, first reach, and hold interruptions.

### [Implication] Geometric reach is available, but branch and conditioning remain causal

- **Decision relevance:** The target annulus is inside the nominal 2R workspace,
  so systematic failures should not initially be labeled unreachable; branch
  selection, shoulder limits, path choice, and Jacobian conditioning remain
  plausible causes.
- **Assumptions:** compiled site geometry follows the XML, contact does not remove
  nominal configurations, and at least one joint-limit-valid IK branch is used.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** compiled-model IK feasibility and logged final
  \(q_1,q_2\) relative to both analytical branches, stratified by radius and angle.

### [Implication] The goal is stabilization over 100 sampled control intervals

- **Decision relevance:** One-time reach rate or low minimum distance is
  insufficient. The first campaign diagnosis must preserve the distinction
  between entering the 1 cm set, converging there, and completing an
  uninterrupted 2-second hold.
- **Assumptions:** the shared environment's post-frame-skip distance check is the
  operative official semantics.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** `first_reach_step`, `max_held_steps`,
  `hold_interruptions`, in-tolerance duration, final distance, and substep
  trajectory extrema.

### [Implication] Effective dynamics are not fully specified by visible dimensions

- **Decision relevance:** Torque limits, damping, armature, compiled inertia,
  solver behavior, and contact defaults determine whether the policy has enough
  authority and how much braking margin the hold requires; assuming a
  dimension-only model could misclassify a dynamic failure.
- **Assumptions:** unspecified MuJoCo defaults materially contribute to the
  compiled model and the evaluated runtime is the locked stack.
- **Source references:** `contracts/robots/two_joint_arm.xml`; `AGENTS.md`;
  `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** compiled model inspection plus commanded
  acceleration/free-decay measurements and action-versus-distance traces.

### [Implication] The saved runtime is part of the physical experiment

- **Decision relevance:** Observation normalization, action transformation, and
  recurrence alter the feedback law that drives the same robot; source defaults
  alone cannot explain a candidate's behavior.
- **Assumptions:** the candidate's runtime files are validated and frozen with
  its weights and any normalization statistics.
- **Source references:** `contracts/policy_runtime.py`;
  `robot_learning/scenario/policy_io.py`; `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** runtime fingerprints, actual model input/output
  ranges, recurrent reset behavior, and deterministic replay from identical
  seeds.
