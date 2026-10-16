# Scientific model: two-joint arm reach-and-hold

This is a pre-campaign model. It uses the human-authored contracts and the
current scenario implementation, not training or evaluation evidence. The
labels below distinguish what the repository says from what follows
mathematically and from quantities that still require evidence. Source
references are repository-relative and line-addressed for later verification.
The model identifies consequences and discriminating evidence; it does not
select an intervention.

## Established facts

### Task boundary and assessment

- [Repository fact] The learned policy controls a fixed two-joint arm. An
  official target is sampled with radius uniformly in [0.06, 0.20] m and angle
  uniformly over the full circle. Success requires the end-effector point to
  be at most 0.01 m from the target for 2.0 s without an interruption.
  `contracts/scenario.md:L7-L14`; `contracts/task_spec.py:L6-L11`
- [Repository fact] The current control timing is 0.002 s per MuJoCo
  integration step and ten integration steps per policy action, so the
  implementation requires 100 control steps for the configured 2.0 s hold.
  `contracts/robots/two_joint_arm.xml:L1-L2`;
  `contracts/task_spec.py:L7-L11`;
  `robot_learning/scenario/environment.py:L52-L57`
- [Repository fact] The official assessment uses one frozen policy on 200
  episodes, at most 500 control steps per episode, and counts success only
  under the complete hold criterion. At least 196 successes are required for
  98 percent. The development panel is separate from this result.
  `contracts/scenario.md:L16-L32`

### Morphology, coordinates, and geometry

- [Repository fact] The base is fixed at the world origin. The shoulder and
  elbow are the only generalized coordinates; both are hinge joints about the
  world/local z axis, so the arm moves in the xy plane. The link lengths are
  L1 = 0.12 m and L2 = 0.10 m, and the end-effector site is at the forearm
  tip. `contracts/robots/two_joint_arm.xml:L9-L23`;
  `contracts/robots/two_joint_arm.py:L3-L7`
- [Repository fact] The arm plane is at z = 0.02 m because the upper-arm body
  is offset by 0.02 m. The upper-arm and forearm capsules have radii 0.015 m
  and 0.012 m; the end-effector site has size 0.008 m. The site position,
  rather than the capsule surface, is used for the task distance.
  `contracts/robots/two_joint_arm.xml:L12-L20`;
  `robot_learning/scenario/environment.py:L75-L81`
- [Repository fact] Each joint has a declared range of -170 to 170 degrees,
  damping 0.5, and armature 0.01. Gravity is zero. The XML does not declare a
  floating base, joint stiffness, friction loss, or a task-side obstacle.
  `contracts/robots/two_joint_arm.xml:L2-L18`
- [Repository fact] The target is a mocap body with a visual sphere of size
  0.012 m. Its geom, the base geom, and the plane geom have contact disabled.
  The target is repositioned on reset into the arm plane, so the initial XML
  target position is not the episode target.
  `contracts/robots/two_joint_arm.xml:L6-L11`;
  `contracts/robots/two_joint_arm.xml:L25-L26`;
  `robot_learning/scenario/environment.py:L83-L97`

### Reset, actuation, and control timing

- [Repository fact] Reset calls MuJoCo data reset, then explicitly sets both
  joint positions and velocities to zero, runs forward dynamics, samples one
  fixed target, and runs forward dynamics again. The controller therefore
  starts from q = (0, 0), qdot = (0, 0), with no randomized physical
  initial state. `robot_learning/scenario/environment.py:L102-L120`
- [Repository fact] The action is a two-element vector in [-1, 1]. The current
  physical-action mapping is identity; the environment converts to float64,
  clips to that range, writes the result to the two motor controls, and holds
  it while calling `mj_step` ten times. A new observation is made only after
  those ten steps. `robot_learning/scenario/policy_io.py:L7-L16`;
  `robot_learning/scenario/environment.py:L59-L68`;
  `robot_learning/scenario/environment.py:L122-L134`
- [Repository fact] The two XML actuators are direct `motor` actuators attached
  to the shoulder and elbow, each with `ctrlrange="-1 1"` and `gear="5"`.
  No position or velocity target is passed to the simulator by the scenario.
  `contracts/robots/two_joint_arm.xml:L30-L32`
- [Repository fact] The environment uses the scalar distance between the site
  and mocap target. If the post-action distance is at most 0.01 m, the hold
  counter increments; otherwise it is reset to zero. Termination occurs at
  100 held control steps and truncation occurs at 500 total control steps.
  `robot_learning/scenario/environment.py:L134-L168`

### Policy observation and learning signal

- [Repository fact] The physical observation is an 11-element float32 vector:
  two qpos values, two qvel values, the three-dimensional
  end-effector-minus-target vector, and four wrapped angular errors to the
  positive-elbow and negative-elbow inverse-kinematic solutions.
  `robot_learning/scenario/observations.py:L11-L16`;
  `robot_learning/scenario/observations.py:L27-L49`
- [Repository fact] The inverse-kinematic features use the target's x and y
  coordinates and the contract lengths. The cosine argument is clipped before
  `arccos`, and every angular error is wrapped to [-pi, pi). No sensor noise,
  observation delay, camera image, contact signal, torque signal, hold
  counter, or episode-step counter is added by this representation.
  `robot_learning/scenario/observations.py:L14-L35`;
  `robot_learning/scenario/environment.py:L60-L64`
- [Repository fact] The current training construction samples only radii
  [0.14, 0.20] m, while the shared evaluation construction uses the official
  [0.06, 0.20] m range. This is a learning-recipe choice, not a change to the
  official task boundary. `robot_learning/training/environment.py:L1-L19`;
  `robot_learning/scenario/environment.py:L171-L178`
- [Repository fact] The baseline reward combines distance progress, an
  exponential closeness potential, hold-progress potential, an action-square
  cost, a small outside-band penalty, and a completion bonus. Its configured
  hold-exit forfeiture fraction is zero. The scalar total is the learning
  signal; reward components are reported in `info` but are not the policy
  input. `robot_learning/training/reward.py:L16-L25`;
  `robot_learning/training/reward.py:L57-L106`;
  `robot_learning/scenario/environment.py:L145-L168`
- [Repository fact] A saved runtime can apply saved observation normalization
  and can maintain recurrent policy state, but it resets recurrence at the
  episode boundary. The physical action mapping and observation callable are
  saved with the policy runtime rather than silently replaced by current
  source code. `contracts/policy_runtime.py:L153-L177`;
  `contracts/policy_runtime.py:L90-L111`

## Physical consequences

### Planar forward kinematics, workspace, and inverse-kinematic branches

- [Reasoned implication] With q_s as shoulder angle and q_e as relative elbow
  angle, the site position is
  `p(q) = (L1 cos(q_s) + L2 cos(q_s + q_e),`
  `L1 sin(q_s) + L2 sin(q_s + q_e), 0.02)`. Its radial distance satisfies
  `r^2 = L1^2 + L2^2 + 2 L1 L2 cos(q_e)`. These equations follow from the
  two serial z-axis hinges and the two link offsets.
- [Reasoned implication] Ignoring the shoulder angular cut, the joint range
  gives a radial interval of approximately 0.0277 to 0.220 m:
  the lower value is
  `sqrt(L1^2 + L2^2 - 2 L1 L2 cos(10 degrees))`, and the upper value is
  L1 + L2. The shoulder limit makes the full workspace an angularly clipped
  annulus rather than a perfect annulus.
- [Reasoned implication] Every official target radius is above the
  range-limited inner radius and below 0.220 m. For a target angle phi, the
  two mathematical solutions are q_e = +/- theta, where
  `theta = arccos(cos(q_e))`, with
  `q_s = phi - atan2(L2 sin(q_e), L1 + L2 cos(q_e))`. Over the official
  radii, the positive branch offset has magnitude about 22 to 56 degrees.
  Choosing the branch whose shoulder angle points inward from the relevant
  angular boundary keeps q_s within about +/-158 degrees even at
  phi = +/-180 degrees. Thus official target points are kinematically
  reachable in at least one valid branch, although both branches are not
  valid near the angular boundary.
- [Reasoned implication] The planar position Jacobian has determinant
  `det(J) = L1 L2 sin(q_e)`. It is singular at the fully extended and fully
  folded configurations. Away from those configurations, the two IK branches
  are alternative postures for the same point; selecting one is a physical
  trajectory choice, not a different task target.

**Decision relevance -- [Reasoned implication]:** This can change whether early work treats failures as
unreachability, branch selection, joint-limit avoidance, or control failure.
It also determines whether a Cartesian controller can use one inverse branch
without handling the angular edge cases.

**Assumptions -- [Reasoned implication]:** The deduction assumes the XML hinge ranges are enforced as
stated, the target and site share z = 0.02 m, and no contact or actuator
limit prevents a kinematically valid posture. Kinematic reachability does not
establish that a posture is reached within 500 control steps.

**Source references -- [Repository fact]:** `contracts/robots/two_joint_arm.xml:L12-L20`;
`contracts/robots/two_joint_arm.py:L5-L7`;
`robot_learning/scenario/environment.py:L83-L97`;
`robot_learning/scenario/observations.py:L18-L35`.

**Discriminating evidence -- [Unresolved quantity]:** For each target, calculate both IK residuals,
record the selected q_e branch and joint-limit distance, and compare them
with the observed minimum distance and first-entry step. A nonzero residual
despite a valid branch would weaken a pure reachability explanation; branch-
dependent success or failures near |phi| = 180 degrees would support the
limit/branch explanation.

### Singular reset and the reach trajectory

- [Reasoned implication] Reset places the site at (0.22, 0, 0.02), fully
  extended along +x. Because official target radii are at most 0.20 m, the
  closest possible initial target is 0.02 m away; every episode begins
  outside the 0.01 m success ball.
- [Reasoned implication] At q_e = 0, the position Jacobian has rank one:
  instantaneous joint velocity produces tangential motion at first order,
  while inward radial motion requires leaving the singular posture and is
  represented at higher order. The controller therefore has to create a bend
  before it can efficiently converge radially toward the target.
- [Reasoned implication] With gravity disabled and no passive position
  stiffness declared, the zero-action, zero-velocity state is an equilibrium,
  but it does not attract the arm to the target. Initial acceleration and
  subsequent convergence must come from motor torque and damping.

**Decision relevance -- [Reasoned implication]:** This can change the priority given to launch behavior,
initial exploration, and reach-time failures. A policy that appears to have
poor radial progress may be limited by the exact reset singularity rather than
by target geometry.

**Assumptions -- [Reasoned implication]:** The conclusion uses ideal forward kinematics and assumes the
first action is applied exactly as the environment specifies. It does not
assume a particular mass, actuator gain, or learned policy.

**Source references -- [Repository fact]:** `robot_learning/scenario/environment.py:L102-L120`;
`contracts/robots/two_joint_arm.xml:L2-L18`;
`contracts/robots/two_joint_arm.py:L5-L7`.

**Discriminating evidence -- [Unresolved quantity]:** Measure the first several q, qdot, controls, and
end-effector radial/tangential velocities after reset. A transient dominated by
motor saturation or a clear bend-before-radial-motion pattern supports this
mechanism; immediate radial motion without leaving q_e approximately zero
would require revising the idealized interpretation.

### Direct torque control, timing, damping, and stabilization

- [Reasoned implication] The policy is a sampled-data torque controller: one
  action is held for 20 ms while ten 2 ms physics steps advance the arm. Under
  standard MuJoCo motor semantics, the gear value maps a unit control to a
  five-fold actuator transmission at each joint; the exact effective torque
  still depends on simulator defaults and any compiled actuator parameters.
- [Reasoned implication] The controller has no explicit position servo in the
  task layer. It must shape acceleration, velocity, and final error through
  direct joint commands. The 0.5 joint damping dissipates velocity, while the
  0.01 armature increases reflected generalized inertia; neither term creates a
  target-centered restoring torque.
- [Reasoned implication] A 20 ms action interval creates a nonzero delay between
  the state that generated an action and the next policy observation. Near a
  1 cm boundary, residual velocity over that interval can be large enough to
  leave the tolerance even when the current position is acceptable.
- [Reasoned implication] Since gravity is zero, a perfectly settled posture
  can remain at rest with zero motor command, but that equilibrium is not
  robust to residual velocity or perturbation. Reliable success therefore
  requires convergence to a low-velocity neighborhood and stabilization, not
  merely one close position sample.

**Decision relevance -- [Reasoned implication]:** These facts can change the choice between a reach-first
and a stabilization-first diagnosis, the interpretation of action saturation,
and the importance assigned to control frequency, velocity information, and
terminal margins.

**Assumptions -- [Reasoned implication]:** The nominal gear interpretation follows MuJoCo's `motor`
  actuator semantics; the XML does not explicitly enumerate compiled gains,
  masses, or force limits. The conclusions about settling assume no external
  disturbance.

**Source references -- [Repository fact]:** `contracts/robots/two_joint_arm.xml:L2-L2`;
`contracts/robots/two_joint_arm.xml:L13-L18`;
`contracts/robots/two_joint_arm.xml:L30-L32`;
`robot_learning/scenario/environment.py:L122-L134`;
`AGENTS.md:L12-L18`.

**Discriminating evidence -- [Unresolved quantity]:** Extract the compiled actuator and body
  parameters, then compare commanded controls with actual generalized forces,
  qdot decay, and distance over substeps. A measured response inconsistent
  with a five-fold direct-motor mapping would revise the torque model; slow
  settling at low command would support damping/inertia rather than geometric
  unreachability.

### Complete hold versus entry into tolerance

- [Reasoned implication] Episode success is a conjunction of first reaching
  the 1 cm ball and preserving membership for 100 consecutive controller
  observations. A policy can have a small minimum distance and still fail
  because it overshoots, oscillates, or exits after a long partial hold.
- [Reasoned implication] The implementation evaluates distance only after the
  ten internal MuJoCo steps. The contractual word "continuously" therefore
  has a sampled operational realization: an excursion between control
  boundaries can go uncounted if both boundary samples remain inside.
- [Reasoned implication] The hold counter is reset by one outside sample with
  no hysteresis. The control objective is consequently a robust interior
  trajectory, not merely a trajectory that touches the tolerance boundary.
  The existing evaluator's `first_reach_step`, `max_held_steps`, and
  `hold_interruptions` distinguish the main reach and hold failure classes.

**Decision relevance -- [Reasoned implication]:** This can change whether development is judged by
minimum distance or by uninterrupted hold, and whether a candidate that reaches
quickly but oscillates is scientifically preferable to a slower, low-velocity
candidate.

**Assumptions -- [Reasoned implication]:** The official benchmark uses the current environment's
post-frame-skip check as its interaction semantics. If "continuous" is meant
as a requirement on every 2 ms state, the current checker is an approximation
whose adequacy must be resolved.

**Source references -- [Repository fact]:** `contracts/scenario.md:L9-L18`;
`contracts/task_spec.py:L7-L11`;
`robot_learning/scenario/environment.py:L131-L168`;
`robot_learning/scenario/evaluation.py:L53-L105`.

**Discriminating evidence -- [Unresolved quantity]:** Compare boundary-sampled distance with the
minimum distance over all ten internal steps, and record qdot at each sampled
hold step. Boundary success with an inter-sample excursion would weaken the
claim that the implementation enforces physical continuity; repeated
interruptions with high terminal velocity would support a stabilization failure.

### Observability, inverse-kinematic ambiguity, and hidden task state

- [Reasoned implication] Under the current noiseless representation, the
  physical state relevant to point dynamics is effectively observable:
  qpos and known link lengths determine the site position, and the observed
  site-minus-target vector then determines the target position in the base
  frame. The target's radius and angle are derived rather than directly
  supplied.
- [Reasoned implication] The four IK errors expose both elbow signs, so the
  geometric branch ambiguity is represented. They do not declare which branch
  respects the joint limits, and wrapping makes errors near the +/-pi cut
  equivalent but numerically discontinuous.
- [Reasoned implication] The task state is not fully observable from the
  physical observation: `_held_steps`, `_step_count`, and the previous
  distance are absent. Two episodes can have the same q, qdot, and target
  observation while differing in whether the next in-tolerance sample is
  step 1 or step 99 of the hold. A recurrent policy can carry history, but
  the environment does not expose the counter explicitly.
- [Reasoned implication] The observation is state-rich but not force-rich. It
  cannot directly distinguish a low-distance state with low kinetic energy
  from one with high kinetic energy moving through the target; qdot provides
  a proxy, while actuator force, contact force, and model inertia remain
  unavailable to the policy.

**Decision relevance -- [Reasoned implication]:** This can change whether a feed-forward policy is
considered sufficient, whether recurrence or explicit velocity-aware
stabilization is needed, and how branch and hold failures are separated.

**Assumptions -- [Reasoned implication]:** The policy knows or can learn the fixed link lengths and
observation ordering. The target remains fixed during an episode, as the
current reset and step code imply.

**Source references -- [Repository fact]:** `robot_learning/scenario/observations.py:L27-L49`;
`robot_learning/scenario/environment.py:L70-L80`;
`robot_learning/scenario/environment.py:L134-L168`;
`contracts/policy_runtime.py:L162-L177`.

**Discriminating evidence -- [Unresolved quantity]:** Reconstruct target coordinates from q and the
  observed relative vector and check the reconstruction against logged target
  coordinates. Then compare policies with and without memory while stratifying
  identical physical states by hold age; any difference attributable to hold
  age supports hidden task-state effects rather than missing geometric sensing.

### Distribution shift and the training signal

- [Reasoned implication] The baseline training recipe omits official inner
  targets from 0.06 to 0.14 m. Those targets require more folded postures and
  may expose different branch, self-contact, damping, or time-to-converge
  behavior than the trained outer band. A strong outer-band result therefore
  does not establish uniform official performance.
- [Reasoned implication] The reward is not the success criterion. Because
  hold-exit forfeiture is configured to zero and the outside penalty is small,
  a reward-maximizing policy may receive substantial learning signal from
  entering and re-entering the tolerance even when its episodes fail the
  uninterrupted criterion. This is a possible incentive mismatch, not a
  demonstrated learned behavior.
- [Reasoned implication] The meaningful decomposition of behavior is
  target geometry -> first-entry time -> terminal distance and velocity ->
  uninterrupted held steps -> success. Aggregate reward or minimum distance
  alone cannot identify where a candidate loses the official objective.

**Decision relevance -- [Reasoned implication]:** This can change how much confidence to place in
baseline training metrics and whether a development candidate is judged as
generalizing to inner radii, stabilizing after entry, or merely optimizing a
proxy.

**Assumptions -- [Reasoned implication]:** The current baseline trainer is used without changing its
training distribution or reward, and the saved runtime preserves the stated
observation/action contract.

**Source references -- [Repository fact]:** `robot_learning/training/environment.py:L14-L19`;
`robot_learning/training/reward.py:L16-L25`;
`robot_learning/training/reward.py:L65-L96`;
`robot_learning/scenario/evaluation.py:L44-L105`.

**Discriminating evidence -- [Unresolved quantity]:** Stratify episode success, first-entry step,
minimum/final distance, maximum held steps, and interruptions by radius and
angle. Compare reward components with those outcomes. Inner-radius failures
with valid IK residuals support distribution or dynamic generalization
limits; low reward despite uninterrupted success would weaken a reward-alignment
explanation.

### Behaviorally meaningful quantities and failure classes

- [Reasoned implication] The minimum sufficient physical trace for mechanism
  attribution includes target radius and angle; q, qdot, action and effective
  torque; site-target distance; Jacobian determinant or manipulability;
  distance to joint limits; first entry; consecutive hold age; interruption
  count; and truncation time. These quantities cover geometry, kinematics,
  dynamics, control authority, observability, and outcome.
- [Reasoned implication] The main qualitative failures are: no valid or no
  timely convergence; valid reach with excessive terminal velocity; repeated
  tolerance exits; branch or joint-limit constraint; actuator saturation or
  insufficient dynamic authority; and an episode that truncates before the
  100-step hold completes. The same binary failure can arise from different
  mechanisms.
- [Repository fact] The current research evaluator already records target
  radius/angle, minimum and final distance, first reach, maximum held steps,
  in-tolerance steps, interruptions, total steps, and success. It does not
  record q, qdot, controls, torque, Jacobian, or internal 2 ms excursions.
  `robot_learning/scenario/evaluation.py:L44-L105`

**Decision relevance -- [Reasoned implication]:** These quantities can change whether the first
campaign decision is about policy selection, mechanism investigation, or
learning-recipe development; the binary score alone cannot make that
distinction.

**Assumptions -- [Reasoned implication]:** A diagnostic is useful only if it is recorded under the same
target distribution and runtime semantics as the candidate outcome it is used
to explain.

**Source references -- [Repository fact]:** `robot_learning/scenario/evaluation.py:L44-L105`;
`robot_learning/scenario/environment.py:L134-L168`;
`contracts/scenario.md:L22-L32`.

**Discriminating evidence -- [Unresolved quantity]:** A trajectory-level record that aligns each
quantity with the same episode and target can separate reach, stabilization,
and truncation causes. If only aggregate success is available, those
mechanisms remain observationally confounded.

## Unknowns

### Compiled mass, inertia, actuator gain, and force authority

- [Unresolved quantity] The XML specifies link geometry, damping, armature,
  control range, and gear, but it does not state body masses, inertial tensors,
  density, actuator gain parameters, or explicit actuator force ranges.
  MuJoCo will fill omitted values according to its compiled defaults, but the
  resulting numerical `M(q)` and effective torque are not established by the
  repository text alone.
- **Decision relevance — [Unresolved quantity]** This could change whether
  slow reach, overshoot, or saturation is attributed to policy behavior,
  damping, insufficient torque, or a simulator-scale assumption.
- **Assumptions — [Unresolved quantity]** The question matters if dynamic
  authority or settling time is close to the 20 ms control interval or 500-step
  horizon; it matters less if all postures have large authority margins.
- **Source references — [Repository fact]** `contracts/robots/two_joint_arm.xml:L12-L19`;
  `contracts/robots/two_joint_arm.xml:L30-L32`;
  `AGENTS.md:L12-L18`.
- **Discriminating evidence — [Unresolved quantity]** Inspect the instantiated
  MuJoCo model's body mass/inertia, actuator gain/gear/force fields, and joint
  limits, then compare those values with open-loop q acceleration, velocity
  decay, and control saturation. This evidence would support or revise the
  direct-torque dynamic model without relying on reward behavior.

### Contact, joint-limit, and folded-branch mechanics

- [Unresolved quantity] Plane, base, and target contacts are explicitly
  disabled, but the link capsule geoms leave contact types at simulator
  defaults. The presence, exclusion, and solver response of upper-arm/
  forearm self-contact and joint-limit contact in folded configurations are
  not specified in the human-authored XML.
- **Decision relevance — [Unresolved quantity]** If folded inner-target
  solutions invoke contacts or limit impulses, branch choice and inner-radius
  failures may be constrained by contact mechanics rather than by the
  two-link equations.
- **Assumptions — [Unresolved quantity]** This is consequential only for
  trajectories that bring link capsules or joints near their limits; it is
  not needed to explain an outer-band failure far from contact.
- **Source references — [Repository fact]** `contracts/robots/two_joint_arm.xml:L6-L20`;
  `contracts/robots/two_joint_arm.xml:L25-L26`;
  `robot_learning/scenario/observations.py:L29-L35`.
- **Discriminating evidence — [Unresolved quantity]** For both IK branches,
  record contact count, contact identities, contact forces/impulses, and
  joint-limit distance while sweeping target radius and angle. Nonzero
  branch-specific contacts or limit impulses would support this explanation;
  zero contacts with persistent failure would weaken it.

### Physical continuity between controller observations

- [Unresolved quantity] The code's success test is known at the 20 ms
  boundary, but no recorded evidence currently establishes the minimum
  site-target distance during each intervening 2 ms step. It is therefore
  unresolved whether sampled success is a good physical approximation to
  uninterrupted continuous hold for learned trajectories.
- **Decision relevance — [Unresolved quantity]** The answer could change how
  much terminal margin and velocity robustness are required before treating a
  candidate as scientifically credible.
- **Assumptions — [Unresolved quantity]** This matters if trajectories can
  cross the 1 cm boundary between observations; it is immaterial for
  trajectories with a wide distance margin at every internal step.
- **Source references — [Repository fact]**
  `robot_learning/scenario/environment.py:L125-L143`;
  `robot_learning/scenario/environment.py:L157-L168`;
  `contracts/scenario.md:L9-L14`.
- **Discriminating evidence — [Unresolved quantity]** Preserve all internal
  site-target distances and qdot values for held intervals and compare their
  minima with the boundary samples. Any hidden exit would revise the
  interpretation of a successful hold even though the protected checker
  reports success.

### Dynamic feasibility and branch preference across the official panel

- [Unresolved quantity] Kinematic reachability is derived, but the number of
  control steps needed to reach and settle each radius/angle, the branch a
  policy actually selects, and the probability of completing 100 held steps
  before truncation are not known before a candidate is run.
- **Decision relevance — [Unresolved quantity]** This could change whether
  early work should be evaluated as a general reach problem, a branch-aware
  trajectory problem, or a hold-stabilization problem.
- **Assumptions — [Unresolved quantity]** The distinction depends on the
  compiled dynamics and policy, not on geometry alone; the fixed reset makes
  initial launch cost common to every episode but not equally difficult for
  every target.
- **Source references — [Repository fact]**
  `robot_learning/scenario/environment.py:L109-L119`;
  `robot_learning/scenario/environment.py:L157-L163`;
  `robot_learning/scenario/evaluation.py:L90-L105`.
- **Discriminating evidence — [Unresolved quantity]** Use paired target
  geometry and trajectory records to report success and first-entry/hold
  distributions by radius, angle, branch, Jacobian determinant, and joint
  limit. A geometry-independent hold failure would shift attention away from
  branch feasibility; geometry-localized failures would support it.

### Reward-to-behavior alignment

- [Unresolved quantity] The formulas establish what reward is delivered, but
  not whether the learned policy values uninterrupted stabilization more than
  repeated partial entries. The effect depends on discounting, rollout
  sampling, policy capacity, normalization, and the learned action sequence.
- **Decision relevance — [Unresolved quantity]** This could change whether a
  low development success rate calls for a reward/learning change or for
  physical-control diagnosis.
- **Assumptions — [Unresolved quantity]** The question is relevant only when
  the current reward and training construction are retained; replacing either
  changes the causal claim.
- **Source references — [Repository fact]**
  `robot_learning/training/reward.py:L16-L25`;
  `robot_learning/training/reward.py:L65-L106`;
  `robot_learning/train.py:L96-L130`;
  `robot_learning/training/normalization.py:L7-L45`.
- **Discriminating evidence — [Unresolved quantity]** Compare per-step reward
  components and action magnitude with hold interruptions, terminal velocity,
  and success on the same episodes. Frequent partial holds with positive
  hold-progress reward would support an incentive mismatch; stable failures
  despite favorable reward components would weaken that explanation.

### Candidate-specific observation processing and memory

- [Unresolved quantity] The physical observation definition is fixed for the
  current runtime, but a particular saved candidate may normalize it using
  saved statistics and may or may not use recurrent state. The candidate's
  learned mapping from the 11 values to controls is not known before training.
- **Decision relevance — [Unresolved quantity]** This could change whether a
  failure is attributed to missing information, poor use of available
  velocity/branch information, normalization, or inadequate memory for hidden
  hold age.
- **Assumptions — [Unresolved quantity]** The saved runtime is the one actually
  evaluated; substituting current observation code for its frozen runtime
  would invalidate the comparison.
- **Source references — [Repository fact]**
  `contracts/policy_runtime.py:L90-L111`;
  `contracts/policy_runtime.py:L153-L177`;
  `robot_learning/scenario/policy_io.py:L7-L16`;
  `robot_learning/training/normalization.py:L30-L45`.
- **Discriminating evidence — [Unresolved quantity]** Record the candidate's
  runtime metadata, normalization statistics, recurrent reset behavior, and
  observation/action traces. An identical physical trace under different
  preprocessing would support a runtime explanation; different actions from
  identical observations would indicate memory or hidden-state dependence.

## Decision-relevant synthesis

### Reset singularity and unknown dynamic scale

- **Decision relevance — [Reasoned implication]** Early candidate behavior can
  be limited by launching from q = (0, 0) at a rank-deficient, fully extended
  posture rather than by inability to reach official targets. The first
  campaign distinction is therefore reach-time/control authority versus
  kinematic unreachability.
- **Assumptions — [Reasoned implication]** The reset and planar kinematics are
  unchanged; compiled mass, inertia, and actuator parameters determine whether
  the launch is merely awkward or materially horizon-limited.
- **Source references — [Repository fact]**
  `robot_learning/scenario/environment.py:L102-L120`;
  `contracts/robots/two_joint_arm.xml:L2-L18`;
  `contracts/robots/two_joint_arm.py:L5-L7`.
- **Discriminating evidence — [Unresolved quantity]** The first-step q/qdot,
  action saturation, radial/tangential velocity, compiled body inertia, and
  effective motor torque discriminate dynamic authority from geometric failure.

### Strict hold and sampled continuity

- **Decision relevance — [Reasoned implication]** A candidate with a good
  minimum distance is not necessarily useful: one exit resets all hold
  progress, and success requires 100 consecutive post-action samples. The
  first decision can change depending on whether failures are entry failures,
  high-velocity stabilization failures, or hidden inter-sample exits.
- **Assumptions — [Reasoned implication]** The official interaction semantics
  are the current 20 ms checker; if physical continuity is interpreted at the
  2 ms level, the boundary test is only a proxy.
- **Source references — [Repository fact]**
  `contracts/scenario.md:L9-L20`;
  `robot_learning/scenario/environment.py:L131-L168`;
  `robot_learning/scenario/evaluation.py:L90-L105`.
- **Discriminating evidence — [Unresolved quantity]** Internal-step distance
  minima, qdot during hold, hold age, and interruption timing distinguish
  robust stabilization from boundary-only success and from simple failure to
  converge.

### Official inner-radius coverage

- **Decision relevance — [Reasoned implication]** The current baseline exposes
  training to 0.14-0.20 m but official assessment includes 0.06-0.14 m.
  Outer-band learning performance cannot by itself justify a 98 percent
  claim under the official distribution.
- **Assumptions — [Reasoned implication]** The baseline training constructor
  remains the exposure used for the first candidate and no unrecorded
  curriculum supplies inner targets.
- **Source references — [Repository fact]**
  `robot_learning/training/environment.py:L14-L19`;
  `contracts/task_spec.py:L6-L11`;
  `robot_learning/scenario/environment.py:L171-L178`.
- **Discriminating evidence — [Unresolved quantity]** Radius- and
  angle-stratified success, first-entry time, branch, minimum distance, and
  interruption distributions show whether inner targets are a distinct
  generalization failure or share the same mechanism as outer targets.

### Observation sufficiency versus hidden hold state

- **Decision relevance — [Reasoned implication]** The 11-vector contains
  enough noiseless geometry to reconstruct the fixed target and includes both
  IK branches, but it omits hold age and episode time. This can change the
  initial judgment about whether a failure reflects missing sensing or a
  controller's use of available state.
- **Assumptions — [Reasoned implication]** Target motion, observation ordering,
  and saved runtime semantics remain fixed; recurrent state, if present, is
  reset only at episode boundaries.
- **Source references — [Repository fact]**
  `robot_learning/scenario/observations.py:L27-L49`;
  `robot_learning/scenario/environment.py:L70-L80`;
  `contracts/policy_runtime.py:L162-L177`.
- **Discriminating evidence — [Unresolved quantity]** Target reconstruction,
  action traces at matched observations, and outcomes grouped by hold age
  distinguish an information deficit from a memory/control-policy deficit.

### Reward alignment with the human outcome

- **Decision relevance — [Reasoned implication]** The baseline reward may
  provide progress for partial entries without making every interruption
  costly, while the human objective counts only complete holds. This can
  change whether the first learning decision concerns proxy alignment or
  physical stabilization.
- **Assumptions — [Reasoned implication]** The stated baseline reward,
  normalization, and training distribution are the actual recipe producing
  the candidate; the reward does not alter official evaluation semantics.
- **Source references — [Repository fact]**
  `robot_learning/training/reward.py:L16-L25`;
  `robot_learning/training/reward.py:L65-L106`;
  `contracts/scenario.md:L16-L20`.
- **Discriminating evidence — [Unresolved quantity]** Same-episode reward
  components, action effort, hold interruptions, terminal velocity, and
  official-style success reveal whether reward is aligned with complete
  uninterrupted behavior or only with approach and re-entry.
