# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. It uses repository definitions and no
campaign evidence. "Repository fact" means that the statement is specified by
the cited source. "Reasoned implication" means that it follows from those facts
under the stated assumptions. "Unresolved quantity" means that the repository
does not establish the value or behavior without running or inspecting the
compiled simulator.

## Established facts

### Task and assessment

- **Repository fact.** The official task samples a target at a radius from 0.06
  m to 0.20 m and over the full angular range around the robot base. The end
  effector must be within 0.01 m of the target for 2 s without an interruption.
  The official objective is at least 196 successes in a fixed 200-episode panel,
  with at most 500 control steps per episode. [Source:
  `contracts/scenario.md:7-32`.]
- **Repository fact.** The protected task constants are
  `TARGET_RADIUS_RANGE=(0.06,0.20)`, `SUCCESS_THRESHOLD=0.01`,
  `HOLD_SECONDS=2.0`, `FRAME_SKIP=10`, and `MAX_EPISODE_STEPS=500`.
  [Source: `contracts/task_spec.py:1-11`.]
- **Repository fact.** The scenario implementation samples angle and radius
  independently and uniformly, sets the target in the arm plane, and measures
  distance as the three-dimensional Euclidean distance between the end-effector
  site and the target mocap position. [Source:
  `robot_learning/scenario/environment.py:75-97`.]

### Morphology and coordinates

- **Repository fact.** The robot is a serial planar chain with a fixed base, a
  0.12 m upper arm, and a 0.10 m forearm. Shoulder and elbow are hinge joints
  about the world z axis, so the generalized coordinates are two angles
  `q=(q_shoulder,q_elbow)`. The end-effector site is at the distal end of the
  forearm. [Source: `contracts/robots/two_joint_arm.xml:9-23`;
  `contracts/robots/two_joint_arm.py:5-7`.]
- **Repository fact.** The arm is elevated by 0.02 m in z. The target is a
  mocap body whose z coordinate is set to the current end-effector z coordinate
  on reset. The target sphere is non-colliding. [Source:
  `contracts/robots/two_joint_arm.xml:12-27`;
  `robot_learning/scenario/environment.py:90-97`.]
- **Repository fact.** Each joint is declared with a range of -170 to +170
  degrees, damping 0.5, and armature 0.01. The XML does not specify joint
  friction, stiffness, mass, body inertia, or a separate end-effector body.
  [Source: `contracts/robots/two_joint_arm.xml:13-19`.]
- **Repository fact.** The plane is visual only for contact purposes
  (`contype=0`, `conaffinity=0`), and gravity is explicitly zero. [Source:
  `contracts/robots/two_joint_arm.xml:1-7`.]

### Kinematics and workspace definitions

- **Repository fact.** With the shoulder angle measured from +x and the elbow
  angle relative to the upper arm, the XML places the second joint at the end
  of the first link and the site at the end of the second link. [Source:
  `contracts/robots/two_joint_arm.xml:12-23`.]
- **Repository fact.** The observation code uses the standard two-link inverse
  kinematics expression
  `cos(q_elbow)=(x^2+y^2-L1^2-L2^2)/(2 L1 L2)` and constructs both positive
  and negative elbow solutions. [Source:
  `robot_learning/scenario/observations.py:14-35`.]

### Actuation and simulator loop

- **Repository fact.** There are two MuJoCo motor actuators, one per joint.
  Their control ranges are -1 to +1 and their transmission gear is 5. The
  environment clips the policy action to the same range, copies it to
  `data.ctrl`, and executes ten `mujoco.mj_step` calls before producing the next
  observation. [Source: `contracts/robots/two_joint_arm.xml:30-33`;
  `robot_learning/scenario/environment.py:122-133`.]
- **Repository fact.** The MuJoCo integration timestep is 0.002 s. Therefore
  one policy action is held for 0.020 s, giving 50 control decisions per
  simulated second. The required hold is 100 such control steps, and the
  episode limit is 500 such steps. [Source:
  `contracts/robots/two_joint_arm.xml:1-2`;
  `robot_learning/scenario/environment.py:55-57`;
  `contracts/task_spec.py:6-11`.]
- **Repository fact.** Reset clears MuJoCo data, sets both joint positions and
  velocities to zero, runs forward dynamics, samples the target, and runs
  forward dynamics again. [Source:
  `robot_learning/scenario/environment.py:102-120`.]

### Sensing and policy interface

- **Repository fact.** The 11-element observation contains two joint positions,
  two joint velocities, the three-dimensional end-effector-to-target vector,
  and four wrapped angle errors to the two analytic inverse-kinematic branches.
  [Source: `robot_learning/scenario/observations.py:11-49`.]
- **Repository fact.** The default action mapping is the identity. There is no
  observation noise, action filtering, actuator state, or sensor delay declared
  in the policy I/O or observation implementation. [Source:
  `robot_learning/scenario/policy_io.py:7-16`;
  `robot_learning/scenario/observations.py:27-49`.]
- **Repository fact.** The observation space is unbounded in the generic
  environment, while the action space is a two-dimensional float box in
  [-1,1]. [Source: `robot_learning/scenario/environment.py:59-68`.]

### Outcome and reward mechanics

- **Repository fact.** After each control interval, distance at that interval's
  endpoint is compared with the 0.01 m threshold. An in-tolerance endpoint
  increments the hold counter; an out-of-tolerance endpoint resets it to zero.
  Success terminates at 100 consecutive in-tolerance endpoints. [Source:
  `robot_learning/scenario/environment.py:134-168`.]
- **Repository fact.** The default training environment samples only radii
  0.14-0.20 m, while the evaluation environment uses the official 0.06-0.20 m
  range. [Source: `robot_learning/training/environment.py:10-19`;
  `robot_learning/scenario/environment.py:171-178`.]
- **Repository fact.** The reward combines distance progress, closeness,
  hold-progress, a small action cost, an outside-band penalty after an
  interrupted hold, and a hold-completion bonus. The RL algorithm receives only
  the scalar total. [Source: `robot_learning/training/reward.py:16-25`,
  `47-107`; `robot_learning/scenario/environment.py:145-168`.]

## Physical consequences

### Reachability and redundant inverse kinematics

- **Reasoned implication.** Ignoring joint limits, the planar endpoint radius is
  `r(q_elbow)=sqrt(L1^2+L2^2+2 L1 L2 cos(q_elbow))`, so the geometric workspace
  is the annulus from `|0.12-0.10|=0.02 m` to `0.22 m`. The official radial
  interval is strictly inside this annulus. For every official target there are
  generally two elbow configurations, represented by the positive and negative
  inverse-kinematic branches.
  - **Decision relevance:** Reach failure should not initially be attributed to
    lack of geometric reach; first decisions can instead distinguish branch
    selection, trajectory control, and hold stabilization.
  - **Assumptions:** The planar formulas apply; the target remains at z=0.02 m;
    no self-contact or limit solver behavior removes both branches.
  - **Source references:** `contracts/robots/two_joint_arm.xml:12-23`;
    `contracts/scenario.md:9-14`; `robot_learning/scenario/observations.py:18-35`.
  - **Discriminating evidence:** Analytically check both solutions against
    joint ranges for sampled targets, then record target radius/angle, selected
    branch, minimum distance, and first-reach success by target geometry.

- **Reasoned implication.** Over the official interval, the open-elbow angle
  ranges approximately from 49 degrees at 0.20 m to 150 degrees at 0.06 m.
  At each target angle at least one branch can keep the shoulder within
  +/-170 degrees; the branch that is valid near one angular boundary can be
  different from the branch valid near the opposite boundary. Thus the
  full angular distribution is reachable in ideal kinematics, but the
  joint-limit margin is not uniform.
  - **Decision relevance:** A policy that learns only one configuration family
    may fail disproportionately at angular wrap regions or at the inner-radius
    targets, changing whether early work should emphasize branch coverage or
    generic stabilization.
  - **Assumptions:** Joint ranges are active as intended by MuJoCo, the
    analytic angle convention matches the simulator convention, and collision
    does not intervene.
  - **Source references:** `contracts/robots/two_joint_arm.xml:13-18`;
    `robot_learning/scenario/observations.py:18-35`;
    `contracts/scenario.md:9-14`.
  - **Discriminating evidence:** Compute limit margin for both solutions over a
    radius-angle grid and stratify completed episodes by target angle, radius,
    and branch-consistent final posture.

### Initial state and approach geometry

- **Reasoned implication.** Reset starts from the fully extended +x posture
  (`q=0`, `qdot=0`) with the end effector at approximately (0.22, 0, 0.02) m.
  The initial target is random, so the initial Cartesian error and the required
  direction of motion vary even though the robot state is fixed.
  - **Decision relevance:** Early trajectory behavior is a reach-from-one-
    posture problem, not a distribution of arbitrary initial configurations.
    This can change whether early development measurements should focus on
    approach time, direction, and overshoot rather than only final success.
  - **Assumptions:** The site coordinate follows the two declared link lengths
    exactly and the reset forward pass does not alter the zero configuration.
  - **Source references:** `robot_learning/scenario/environment.py:102-120`;
    `contracts/robots/two_joint_arm.xml:12-23`.
  - **Discriminating evidence:** Log initial and terminal joint state, target
    radius/angle, Cartesian error, and time to first enter tolerance for each
    episode.

### Actuation, damping, and coupled motion

- **Reasoned implication.** A bounded action changes joint generalized force
  through a direct motor transmission with nominal magnitude proportional to
  `5 * action`. The zero-gravity model removes gravitational torque, but
  velocity-dependent damping, armature inertia, and configuration-dependent
  two-link inertia remain. A joint command therefore affects endpoint motion
  through coupled shoulder-elbow dynamics rather than through independent
  Cartesian axes.
  - **Decision relevance:** The policy must solve both inverse kinematics and
    velocity/torque shaping. Large commands can shorten approach time but
    increase overshoot and make the 1 cm hold harder; this determines whether
    the first behavioral diagnosis should measure control authority and
    settling rather than optimize reward alone.
  - **Assumptions:** MuJoCo motor transmission uses the declared gear directly
    as the joint-force scale, units are SI-consistent, and no unlisted actuator
    dynamics are inserted by the runtime.
  - **Source references:** `contracts/robots/two_joint_arm.xml:1-2,13-19,30-33`;
    `robot_learning/scenario/environment.py:125-133`.
  - **Discriminating evidence:** Inspect the compiled actuator and DOF fields,
    then apply bounded diagnostic commands and measure joint acceleration,
    velocity decay, endpoint response, and action-to-torque scaling.

- **Reasoned implication.** The 0.5 damping and 0.01 armature provide passive
  velocity resistance and added rotational inertia, but the missing body mass
  and inertia declarations mean that approach speed and settling time cannot be
  inferred from link lengths and gear alone. The same target error can require
  different actions at different configurations because the manipulator inertia
  and Jacobian change with elbow angle.
  - **Decision relevance:** If the available torque is high relative to compiled
    inertia, a fast bang-bang-like approach may be viable; if not, the policy
    needs longer anticipation. This can change horizon, reward emphasis, and
    whether system characterization precedes policy selection.
  - **Assumptions:** The unlisted inertial values are not fixed by another
    repository contract and the policy has no privileged access to them.
  - **Source references:** `contracts/robots/two_joint_arm.xml:13-19`;
    `robot_learning/scenario/environment.py:52-57`.
  - **Discriminating evidence:** Read `MjModel` mass, inertia, armature,
    damping, actuator gear and force fields, and compare predicted versus
    observed response from the reset posture and representative IK postures.

### Discrete reaching and uninterrupted holding

- **Reasoned implication.** The nominal hold is 2 s, but the implementation
  evaluates tolerance only once after each 20 ms block. The operational success
  condition is therefore 100 consecutive endpoint samples, not a mathematical
  guarantee that the trajectory stayed inside the 1 cm ball at every 2 ms
  MuJoCo substep. A brief substep excursion can be invisible if both sampled
  endpoints remain in tolerance.
  - **Decision relevance:** A policy can succeed by maintaining sampled
    endpoints while still having high-frequency physical excursions. This
    changes how hold failures are diagnosed and whether substep-level telemetry
    is needed before interpreting a 98% result as robust stabilization.
  - **Assumptions:** The environment implementation is the relevant interaction
    semantics and no protected evaluator adds a finer-grained check.
  - **Source references:** `contracts/scenario.md:9-14`;
    `contracts/robots/two_joint_arm.xml:1-2`;
    `robot_learning/scenario/environment.py:131-159`.
  - **Discriminating evidence:** Recompute distance at every internal MuJoCo
    step alongside the official endpoint counter and compare endpoint success
    with continuous-substep success.

- **Reasoned implication.** Reaching the tolerance ball is only a transient
  prerequisite. Success requires low enough endpoint position error and
  velocity, or sufficiently coordinated ongoing actuation, to avoid leaving
  the ball for the full 100-step counter. The final 2 s can dominate episode
  success even when the first arrival is accurate.
  - **Decision relevance:** Aggregate reward or minimum distance alone can
    select policies that reach quickly but fail the human objective. First
    campaign decisions should preserve separate reach and hold diagnostics.
  - **Assumptions:** The official success criterion, rather than a shaped
    reward surrogate, is the objective.
  - **Source references:** `contracts/scenario.md:16-20`;
    `robot_learning/scenario/environment.py:134-168`;
    `robot_learning/scenario/evaluation.py:51-106`.
  - **Discriminating evidence:** Measure first-reach step, maximum held steps,
    hold interruptions, final distance, velocity at entry, and success by
    target geometry.

### Observation, control, and observability

- **Reasoned implication.** For the fixed planar target, `q`, `qdot`, and the
  end-effector error make the relevant instantaneous physical state observable
  to the policy; target position can be reconstructed as end-effector position
  minus the observed error. The four IK errors provide a direct representation
  of both candidate terminal configurations. The hold counter and previous
  action are not observed, so the exact task phase is not explicitly sensed.
  - **Decision relevance:** A memoryless policy can in principle choose
    state-feedback actions from physical state, but it cannot know the elapsed
    hold count or distinguish identical current states reached after different
    histories. This can change the value of recurrent state or auxiliary
    diagnostics for hold control.
  - **Assumptions:** The target is stationary, the kinematic model used by the
    policy matches the simulator, and action history is not needed to infer
    unobserved actuator state.
  - **Source references:** `robot_learning/scenario/observations.py:27-49`;
    `robot_learning/scenario/environment.py:134-168`;
    `robot_learning/scenario/policy_io.py:11-16`.
  - **Discriminating evidence:** Compare otherwise identical observations
    reached before and during a hold, and test whether hold interruptions or
    success differ after conditioning on the observable state.

- **Reasoned implication.** The idealized observation has direct, noiseless
  simulator state and no occlusion or calibration uncertainty. A policy can
  exploit exact velocities, target error, and deterministic dynamics; this is
  a simulation-control problem rather than a perception problem.
  - **Decision relevance:** Initial policy design need not solve visual
    localization or sensor filtering. Conversely, performance should not be
    interpreted as evidence of robustness to real sensing uncertainty.
  - **Assumptions:** No hidden noise, delay, or observation transformation is
    introduced by the protected assessment.
  - **Source references:** `robot_learning/scenario/observations.py:27-49`;
    `robot_learning/scenario/policy_io.py:7-16`;
    `contracts/scenario.md:34-38`.
  - **Discriminating evidence:** Compare the serialized policy I/O and
    evaluation observations with the declared 11 fields and inspect whether
    any runtime normalization changes their semantics.

### Distinct behavior and failure classes

- **Reasoned implication.** The coupled system admits qualitatively different
  failures: an unreachable or limit-infeasible posture, a slow or misdirected
  approach, overshoot caused by insufficient damping or excessive command,
  a near-target oscillation, a hold interruption, and an episode timeout.
  These cannot be collapsed into one distance statistic because the success
  predicate is sequential.
  - **Decision relevance:** The first campaign decision should be based on which
    failure class dominates under the official geometry, not on a generic
    assumption that all failures are exploration failures.
  - **Assumptions:** The listed physical state and episode diagnostics are
    available without changing the official outcome.
  - **Source references:** `robot_learning/scenario/environment.py:134-168`;
    `robot_learning/scenario/evaluation.py:51-106`;
    `contracts/scenario.md:16-32`.
  - **Discriminating evidence:** Partition episodes by first-reach step,
    minimum and final distance, maximum held steps, interruption count,
    target radius, target angle, joint-limit margin, and action magnitude.

- **Reasoned implication.** There are many admissible trajectories to the same
  terminal point: the two IK branches, different time profiles, and different
  intermediate joint paths. With no obstacles specified in the task geometry,
  the principal physical tradeoff is between path duration, endpoint momentum,
  limit margin, and hold stability.
  - **Decision relevance:** A policy can be successful without reproducing one
    canonical trajectory. Evaluation should judge the complete hold and retain
    trajectory quantities only to identify mechanisms and failure classes.
  - **Assumptions:** Arm self-contact does not eliminate a candidate path and
    the target is not a dynamic object.
  - **Source references:** `contracts/robots/two_joint_arm.xml:15-27`;
    `robot_learning/scenario/observations.py:18-35`;
    `contracts/scenario.md:16-20`.
  - **Discriminating evidence:** Record branch occupancy, joint-space path,
    endpoint path length, peak velocity, peak action, and final joint-limit
    margin for successful and failed episodes.

### Mechanistically meaningful trajectory quantities

- **Reasoned implication.** Across the complete behavior, the physically
  meaningful state and outcome variables are target radius and angle, joint
  position and velocity, commanded action and resulting generalized force,
  end-effector position error (including radial and tangential components),
  inverse-kinematic branch, joint-limit margin, time to first entry, settling
  behavior, uninterrupted hold duration, and substep excursions.
  - **Decision relevance:** These variables connect morphology and actuation to
    the official binary outcome and distinguish reach, convergence, and
    stabilization mechanisms.
  - **Assumptions:** The quantities can be logged diagnostically without
    changing the policy input or official termination semantics.
  - **Source references:** `contracts/robots/two_joint_arm.xml:12-33`;
    `robot_learning/scenario/environment.py:75-168`;
    `robot_learning/scenario/evaluation.py:51-106`.
  - **Discriminating evidence:** Per-episode and per-control-step traces
    aligned to target geometry and the hold counter, with force, distance,
    velocity, timing, and limit quantities in explicit units.

## Unknowns

### Compiled inertial and numerical dynamics

- **Unresolved quantity.** Exact body masses, composite inertias, center-of-mass
  locations, compiled DOF armature and damping, and the numerical integrator
  and constraint parameters are not written explicitly in the XML. MuJoCo
  defaults and geom-derived inertias may determine them, but their effective
  values are not established by this document.
  - **Decision relevance:** These values determine acceleration, settling,
    overshoot, and how much of the 20 ms action interval is needed for
    stabilization; they could change whether policy learning alone is adequate
    or characterization is needed.
  - **Assumptions:** Default compiler and solver behavior is material and
    cannot be treated as a negligible implementation detail.
  - **Source references:** `contracts/robots/two_joint_arm.xml:1-33`;
    `AGENTS.md` runtime versions; `robot_learning/scenario/environment.py:52-57`.
  - **Discriminating evidence:** Inspect the native MuJoCo 3.12 `MjModel`
    fields and validate them against free response and bounded-action probes.

### Effective actuator and limit behavior

- **Unresolved quantity.** The XML declares motor gear and control range, but
  the effective generalized force at each configuration, saturation semantics,
  joint-limit activation, and limit-contact solver response are not numerically
  characterized here. The arm geoms also do not explicitly state contact
  filtering, so any arm self-contact behavior is not established.
  - **Decision relevance:** Unexpected torque saturation, limit impulses, or
    self-contact could create failures that look like poor exploration and
    could change the admissible terminal branch.
  - **Assumptions:** The declared ranges and default MuJoCo contact semantics
    are actually active in the compiled model.
  - **Source references:** `contracts/robots/two_joint_arm.xml:13-19,30-33`;
    `robot_learning/scenario/environment.py:125-133`.
  - **Discriminating evidence:** Read actuator, joint-limit, and contact
    model fields; sweep commands near limits; log constraint forces, qpos,
    qvel, and endpoint distance.

### Runtime distribution realization

- **Unresolved quantity.** The task contract specifies the official radial and
  angular distribution, while the accessible training constructor defaults to
  the outer radial band 0.14-0.20 m. It is not yet established which training
  configuration a campaign will use or how performance will vary over the
  omitted inner band.
  - **Decision relevance:** This can change the first learning decision because
    success on the training distribution does not establish coverage of
    official 0.06-0.14 m targets, which require more folded configurations.
  - **Assumptions:** The baseline training constructor is used unless the PI
    changes it, and the protected assessment uses the official contract.
  - **Source references:** `contracts/scenario.md:7-14`;
    `robot_learning/training/environment.py:14-19`;
    `robot_learning/scenario/environment.py:171-178`.
  - **Discriminating evidence:** Record the effective training range and
    report success, reach time, and hold interruptions in radius bins spanning
    0.06-0.20 m.

### Policy capability under the exact hold semantics

- **Unresolved quantity.** No learned policy behavior or campaign evidence
  exists. It is unknown whether a policy can reach all target geometries,
  choose a stable IK branch, and maintain the endpoint inside the sampled
  tolerance ball for 100 consecutive control steps within 500 steps.
  - **Decision relevance:** This is the direct gap between the physical
    capability map and the 98% objective; its failure mode determines whether
    the next scientific focus is coverage, dynamics, stabilization, or policy
    representation.
  - **Assumptions:** The policy is evaluated deterministically under the exact
    official interaction semantics and no training metric substitutes for
    episode success.
  - **Source references:** `contracts/scenario.md:16-32`;
    `robot_learning/scenario/evaluation.py:34-106`.
  - **Discriminating evidence:** Use completed episode diagnostics including
    first reach, maximum hold, interruption count, timeout, target radius,
    target angle, and final distance.

### Unobserved hold phase and substep excursions

- **Unresolved quantity.** It is unknown how often the policy leaves the 1 cm
  ball between endpoint checks, and whether the absent hold counter or action
  history materially limits a memoryless policy. The official counter records
  only sampled endpoints.
  - **Decision relevance:** If endpoint success hides substep excursions, the
    physical interpretation of a 98% policy is weaker; if history matters,
    policy-state design can change the achievable hold rate.
  - **Assumptions:** The control interval and observation definition remain
    fixed, and substep telemetry is treated as diagnostic rather than as a
    replacement official score.
  - **Source references:** `robot_learning/scenario/environment.py:99-120,
    131-168`; `robot_learning/scenario/observations.py:27-49`.
  - **Discriminating evidence:** Compare internal-substep distance traces with
    the official hold counter and condition failures on current observation,
    previous action, and time since first entry.

### Scientific quantities not yet measured

- **Unresolved quantity.** The complete behavior has no measured distributions
  yet for time to first entry, settling time, peak and RMS joint velocity,
  action/torque effort, endpoint radial and tangential error, limit margin,
  branch occupancy, hold interruption timing, or minimum substep distance.
  - **Decision relevance:** These quantities distinguish a reach problem from a
    stabilization problem and identify whether aggregate success is improving
    for the right physical reason.
  - **Assumptions:** Diagnostics can be collected without changing policy
    inputs or official termination.
  - **Source references:** `robot_learning/scenario/evaluation.py:51-125`;
    `robot_learning/scenario/environment.py:134-168`.
  - **Discriminating evidence:** Preserve per-episode and, where needed,
    per-control-step traces with explicit units: meters or centimeters,
    radians, radians/second, action units, and control steps.

## Decision-relevant synthesis

### Hold stabilization is the task bottleneck to distinguish

- **Reasoned implication. Decision relevance:** Reaching a target is not
  sufficient; the 98% goal is
  most sensitive to whether endpoint error and velocity remain controlled for
  100 consecutive 20 ms samples.
- **Assumptions:** The official endpoint-based hold semantics are authoritative.
- **Source references:** `contracts/scenario.md:9-20`;
  `robot_learning/scenario/environment.py:134-159`.
- **Discriminating evidence:** First-reach step, maximum held steps,
  interruption count, final distance, velocity at entry, and substep distance
  traces separated for successful and failed episodes.

### Official coverage includes an inner radial band absent from default training

- **Reasoned implication. Decision relevance:** The default training range
  0.14-0.20 m does not cover
  official 0.06-0.14 m targets, where more folded configurations and different
  dynamics may be required.
- **Assumptions:** The default training constructor is used and the official
  distribution remains 0.06-0.20 m.
- **Source references:** `contracts/scenario.md:7-14`;
  `robot_learning/training/environment.py:14-19`.
- **Discriminating evidence:** Effective training configuration plus
  radius-binned official performance, IK branch/limit margin, and hold failure
  rates.

### Geometry supplies redundant solutions, but dynamics and limits select behavior

- **Reasoned implication. Decision relevance:** The target annulus is
  analytically reachable, so
  early failures should be tested against branch selection, joint-limit
  margin, and trajectory dynamics before being labeled unreachable.
- **Assumptions:** The planar two-link model and declared joint ranges are
  enforced without unexpected self-contact.
- **Source references:** `contracts/robots/two_joint_arm.xml:12-23`;
  `robot_learning/scenario/observations.py:18-35`;
  `contracts/scenario.md:9-14`.
- **Discriminating evidence:** A radius-angle IK feasibility grid and episode
  stratification by terminal branch, target geometry, limit margin, and
  approach path.

### Exact compiled dynamics remain a high-impact physical unknown

- **Unresolved quantity. Decision relevance:** Missing mass/inertia and
  solver-level values control
  whether the 5-gear motor authority can produce fast, non-oscillatory
  convergence; this can change the first characterization or policy decision.
- **Assumptions:** MuJoCo defaults and geom-derived inertias materially affect
  the resulting motion and are not safely inferred from XML dimensions.
- **Source references:** `contracts/robots/two_joint_arm.xml:1-33`;
  `robot_learning/scenario/environment.py:52-57`.
- **Discriminating evidence:** Compiled `MjModel` parameters and controlled
  action-response measurements at the reset posture and representative
  elbow configurations.

### Observation is kinematically rich but omits explicit task phase

- **Reasoned implication. Decision relevance:** The policy receives joint state,
  target error, and
  both IK references, but not hold count or previous action. Whether this
  limits stable control is a representation question, not a sensing-of-target
  question.
- **Assumptions:** The target is stationary and no hidden actuator state is
  introduced.
- **Source references:** `robot_learning/scenario/observations.py:11-49`;
  `robot_learning/scenario/policy_io.py:11-16`;
  `robot_learning/scenario/environment.py:134-168`.
- **Discriminating evidence:** Conditional state-history analysis of hold exits
  and success, including whether identical current observations have different
  outcomes by preceding action or hold history.
