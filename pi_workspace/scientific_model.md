## Established facts

### Human-defined task and assessment

- [Repository fact] The official task is a two-joint arm reaching a target whose
  radius from the base is sampled from 6--20 cm over the full angular range.
  Success requires the end effector to enter a 1 cm distance tolerance and
  remain continuously inside it for 2 s; the contract identifies this as 100
  consecutive control steps under the official timing. Sources:
  `contracts/scenario.md:10-13`, `contracts/task_spec.py:6-11`.
- [Repository fact] The final assessment freezes one policy, evaluates 200
  episodes, permits at most 500 control steps per episode, and requires at least
  196 successes (98%). Development measurements are not part of that panel.
  Source: `contracts/scenario.md:18-32`.

### Morphology, coordinates, and geometry

- [Repository fact] The robot is a serial planar chain with a fixed base, a
  12 cm upper arm, and a 10 cm forearm. Shoulder and elbow are hinge joints
  about the world z axis, each with a -170 to 170 degree range. The end-effector
  site is at the forearm tip. Sources:
  `contracts/robots/two_joint_arm.xml:11-21`,
  `contracts/robots/two_joint_arm.py:3-7`.
- [Repository fact] The arm plane is z=0.02 m: the upper-arm body is offset by
  0.02 m above the base, and all link and site offsets are in that body plane.
  Source: `contracts/robots/two_joint_arm.xml:10-21`.
- [Repository fact] The target is a mocap body with a non-colliding sphere
  visualization. The task code places its center at the sampled x-y point and
  at the current end-effector z coordinate. Success uses the center-to-site
  distance, not sphere contact. Sources:
  `contracts/robots/two_joint_arm.xml:24-27`,
  `robot_learning/scenario/environment.py:76-96`.
- [Repository fact] The plane and target visualization have collision disabled
  in the XML. No separate obstacle or grasp object is defined. Source:
  `contracts/robots/two_joint_arm.xml:7-8,25-26`.

### Physics, actuation, and timing

- [Repository fact] MuJoCo is configured with zero gravity and a 2 ms physics
  timestep. Each environment action is assigned to both actuators and followed
  by 10 MuJoCo steps. Sources:
  `contracts/robots/two_joint_arm.xml:2`,
  `robot_learning/scenario/environment.py:122-133`.
- [Repository fact] Each joint has explicit viscous damping 0.5 and armature
  0.01. Each actuator is a motor with control range [-1, 1] and gear 5.
  Sources: `contracts/robots/two_joint_arm.xml:13-15,18-19,30-32`.
- [Repository fact] The action space is two-dimensional with bounds [-1, 1].
  The policy-to-physical-action mapping is the identity; the environment clips
  the resulting command to those bounds before applying it. Sources:
  `robot_learning/scenario/environment.py:63-68,123-130`,
  `robot_learning/scenario/policy_io.py:7-12`.
- [Repository fact] The XML does not explicitly specify link mass, density,
  inertia, friction, contact parameters, or actuator force limits beyond the
  motor control range and gear. The installed MuJoCo compiler therefore
  determines some effective model quantities from defaults and geometry, but
  their numerical values are not human-authored in the visible robot contract.
  Source: `contracts/robots/two_joint_arm.xml`.

### Reset, sampling, sensing, and outcome computation

- [Repository fact] Reset sets both joint positions and velocities to zero,
  forwards the model, then samples the target. Consequently the initial
  configuration is the straight pose q=(0,0), with the end effector at
  (0.22, 0, 0.02) m before the target is sampled. Sources:
  `robot_learning/scenario/environment.py:102-116`,
  `contracts/robots/two_joint_arm.xml:10-21`.
- [Repository fact] The current shared environment samples angle and radius
  independently from uniform distributions, writes target
  (r cos(theta), r sin(theta), 0.02), and measures the Euclidean 3-D site-to-
  target-center distance. Sources:
  `robot_learning/scenario/environment.py:76-96`,
  `contracts/task_spec.py:6`.
- [Repository fact] The observation has 11 float32 values: two joint positions,
  two joint velocities, the three-component end-effector-to-target vector, and
  four wrapped joint errors to the open and folded analytic IK solutions.
  Sources:
  `robot_learning/scenario/observations.py:11-47`.
- [Repository fact] The observation reads simulator state directly and adds no
  sensor noise. It does not include acceleration, actuator torque, contact
  force, a hold counter, or an explicit success flag. Source:
  `robot_learning/scenario/observations.py:14-47`.
- [Repository fact] After each action interval, the environment increments the
  held-step counter if the sampled distance is at most 0.01 m; any sampled
  outside step resets it to zero. Termination is held_steps >= 100 and
  truncation is step_count >= 500. Sources:
  `robot_learning/scenario/environment.py:134-159`.
- [Repository fact] The baseline training constructor uses a 14--20 cm radius
  range, while evaluation is constructed with the official 6--20 cm range.
  Source: `robot_learning/training/environment.py:9-20`,
  `robot_learning/scenario/environment.py:163-169`.

## Physical consequences

### Kinematic structure and reachable workspace

- [Reasoned implication] Let q_s be shoulder angle and q_e be elbow angle,
  both in radians. The end-effector position is
  `p(q) = (l1 cos(q_s) + l2 cos(q_s+q_e),
  l1 sin(q_s) + l2 sin(q_s+q_e), 0.02)`, with l1=0.12 m and l2=0.10 m.
  Its planar Jacobian maps joint velocity to Cartesian velocity. The
  unconstrained workspace is the annulus from |l1-l2|=0.02 m to
  l1+l2=0.22 m; the joint limits remove portions of that annulus. Decision
  relevance: this determines whether failures can be physical infeasibility or
  controller behavior. Assumptions: hinge coordinates are MuJoCo relative
  joint angles and the link offsets are interpreted as specified. Sources:
  `contracts/robots/two_joint_arm.xml:10-21`,
  `contracts/robots/two_joint_arm.py:3-7`. Discriminating evidence: compute
  forward kinematics and the joint-limit-constrained workspace from the
  compiled model, then compare every target pose with an IK solution.

- [Reasoned implication] Every official target radius is inside the
  unconstrained annulus. Solving the two-link cosine law gives elbow branches
  q_e=+/- arccos((r^2-l1^2-l2^2)/(2 l1 l2)); across r=0.06--0.20 m these
  branches are approximately +/-150 to +/-49 degrees. At least one shoulder
  branch can remain within +/-170 degrees for every target angle in the
  official band, so official targets are kinematically reachable even though
  one branch can be excluded by the shoulder limit at some angles. Decision
  relevance: a broad failure across the panel should not be attributed to
  unreachable targets without checking the branch and limits. Assumptions:
  the target is exactly in the arm plane and the stated independent radius and
  angle sampling is the official distribution. Sources:
  `contracts/scenario.md:10-13`,
  `robot_learning/scenario/environment.py:83-96`,
  `contracts/robots/two_joint_arm.xml:13-19`. Discriminating evidence: enumerate
  both analytic IK branches against both joint ranges over the sampled target
  panel.

- [Reasoned implication] The Jacobian loses rank at a fully extended or fully
  folded elbow, so Cartesian control authority becomes directionally poor near
  the annulus boundaries. The official band stops at 0.20 m rather than 0.22 m
  and starts at 0.06 m rather than 0.02 m, reducing but not eliminating
  conditioning variation. Decision relevance: target-radius stratification can
  distinguish geometry/conditioning failures from generic learning failures.
  Assumptions: endpoint motion is the relevant controlled quantity and no
  unmodeled contact dominates it. Sources:
  `contracts/robots/two_joint_arm.xml:13-21`,
  `contracts/task_spec.py:6`. Discriminating evidence: report the minimum
  singular value or condition number of the endpoint Jacobian by target radius
  together with reach and hold outcomes.

### Alternative solutions and trajectories

- [Reasoned implication] For a generic reachable target there are two discrete
  IK configurations, an open and a folded elbow, and the observation exposes
  wrapped errors to both. The current q position and q velocity distinguish
  which branch the arm occupies; the branch choice is not redundant freedom,
  because there are only two task-space degrees of freedom and two joints.
  Decision relevance: a policy may need branch-aware convergence rather than a
  single global joint setpoint. Assumptions: the analytic lengths match the
  compiled geometry and the target is not at an IK singularity. Sources:
  `robot_learning/scenario/observations.py:17-46`,
  `contracts/robots/two_joint_arm.py:3-6`. Discriminating evidence: compare
  successful trajectories, branch occupancy, and hold interruptions after
  classifying each trajectory by the sign of q_e.

- [Reasoned implication] Endpoint success does not select a unique transient:
  different branch choices, approach velocities, braking profiles, and
  corrections can reach the same 1 cm ball. The two-second hold makes the
  terminal velocity and local closed-loop stiffness physically relevant, not
  merely the first entry into the ball. Decision relevance: optimizing early
  distance or first reach alone can select policies that fail the actual
  objective. Assumptions: the hold semantics are enforced as stated by the
  official contract. Sources:
  `contracts/scenario.md:10-20`,
  `robot_learning/scenario/evaluation.py:57-90`. Discriminating evidence:
  measure first-reach step, velocity at entry, maximum contiguous hold, and
  interruption count.

### Actuation, dynamics, and control authority

- [Reasoned implication] The policy operates at 50 Hz: one action is held by
  the simulator for 10 x 2 ms = 20 ms. Under standard MuJoCo motor
  transmission semantics, a command u_i contributes nominal generalized
  torque proportional to gear*u_i, so the command bound corresponds to a
  nominal magnitude of 5 in each joint before the rest of the dynamics acts.
  Decision relevance: the policy must brake and correct with quantized,
  bounded torque rather than continuously choose an arbitrary Cartesian
  velocity. Assumptions: the visible XML is the compiled model and standard
  motor transmission semantics apply. Sources:
  `contracts/robots/two_joint_arm.xml:2,30-32`,
  `contracts/task_spec.py:8`,
  `robot_learning/scenario/environment.py:56-57,128-133`. Discriminating
  evidence: log commands, joint accelerations, and endpoint displacement at
  each control interval, including command saturation.

- [Reasoned implication] A useful reduced equation is
  `M(q) q_ddot + C(q,q_dot) q_dot + D q_dot = tau(u)`, with gravity absent;
  the armature contributes to effective inertia and the explicit damping
  dissipates motion. The coupled mass matrix means a shoulder command changes
  both the shoulder and downstream endpoint motion, while elbow authority is
  state-dependent through the Jacobian. Decision relevance: action scaling,
  braking, and controller architecture depend on the ratio of available torque
  to effective inertia and damping. Assumptions: no meaningful external
  contact occurs and MuJoCo's inferred inertial model is stable across runs.
  Sources: `contracts/robots/two_joint_arm.xml:2,13-19,30-32`. Discriminating
  evidence: inspect compiled masses/inertias and fit local step responses or
  impulse responses at representative configurations.

- [Reasoned implication] The zero-gravity, non-grasping setup removes weight
  compensation and target reaction forces from the task. The main stabilization
  problem is therefore regulating a free endpoint against inertial motion,
  damping, and discrete control delay; a physical target cannot passively stop
  the arm. Decision relevance: a policy that reaches by relying on contact or
  gravity would not have a supported mechanism for success. Assumptions: the
  target and plane collision masks remain as authored and arm self-contact is
  absent or negligible. Sources:
  `contracts/robots/two_joint_arm.xml:2,7-8,24-26`,
  `robot_learning/scenario/environment.py:76-96`. Discriminating evidence:
  inspect contact records and compare free-space endpoint settling with and
  without commanded corrections.

### Initial state, task geometry, and complete behavior

- [Reasoned implication] The reset pose starts fully extended toward +x while
  targets span all angles. Initial target distance can therefore be much
  larger than the 1 cm tolerance and varies strongly with target angle; the
  controller must first rotate/retract the chain before fine stabilization for
  many episodes. Decision relevance: initial transient reach and terminal hold
  are distinct capabilities and should not be collapsed into one reward or
  score. Assumptions: reset is performed exactly as in the shared environment.
  Sources: `robot_learning/scenario/environment.py:102-116`,
  `contracts/scenario.md:10-13`. Discriminating evidence: stratify first-reach
  time and hold success by initial target angle and radius.

- [Reasoned implication] A successful episode requires a coupled sequence:
  choose a feasible branch, generate enough endpoint motion to converge,
  dissipate or counter residual velocity, enter the tolerance, and maintain a
  bounded endpoint error for 100 control intervals. Reaching without
  convergence fails; convergence without 2 s of uninterrupted stability fails.
  Decision relevance: the first campaign comparison must preserve complete
  episode success and separately diagnose reach versus hold failure. Assumptions:
  the official duration and uninterrupted criterion are authoritative. Sources:
  `contracts/scenario.md:10-20`,
  `robot_learning/scenario/environment.py:134-159`. Discriminating evidence:
  use complete episode outcomes plus minimum distance, first reach, maximum
  held steps, and interruption count.

- [Reasoned implication] The 500-step horizon is 10 s at the current 20 ms
  control interval, so there are about 8 s available for reaching and settling
  before the latest possible start of a 2 s hold. A later reach cannot complete
  the required hold. Decision relevance: horizon-limited failures must be
  distinguished from unstable holds. Assumptions: the official environment
  retains the visible timestep and frame skip. Sources:
  `contracts/scenario.md:24-30`,
  `contracts/task_spec.py:7-8`,
  `robot_learning/scenario/environment.py:56-57,158-159`. Discriminating
  evidence: compare first-reach step with remaining hold opportunity and
  truncation status.

### Observation, control, and task outcome

- [Reasoned implication] The policy has near-complete task kinematics in its
  observation: q and q_dot are provided, and the endpoint error is provided
  directly. Given the authored model, q and the error also determine the
  target position in the base frame. This makes target localization and
  velocity-aware feedback possible without an image or force sensor. Decision
  relevance: poor performance is more plausibly a control, optimization, or
  dynamics issue than a missing-target-information issue. Assumptions: the
  policy uses the observation without an incompatible normalization/runtime
  transformation and knows the fixed coordinate convention. Sources:
  `robot_learning/scenario/observations.py:37-47`,
  `robot_learning/scenario/policy_io.py:7-16`. Discriminating evidence:
  replay observations and reconstruct target and endpoint positions from q and
  the error, checking equality to simulator state.

- [Reasoned implication] The four IK-error channels are derived features, not
  independent sensors. They can be ambiguous near wrapped angular boundaries
  and can become artificial if the cosine-law argument is clipped for an
  unreachable target; official targets should avoid the latter by the
  reachability result above. Hold progress is also unavailable directly, so a
  memoryless policy cannot know how many consecutive in-tolerance steps have
  elapsed except through its current physical state and any temporal policy
  memory. Decision relevance: recurrence or an explicit stabilizing state may
  matter even though the task is Markov in the full simulator state. Assumptions:
  the policy is not given additional hidden environment info. Sources:
  `robot_learning/scenario/observations.py:23-46`,
  `robot_learning/scenario/environment.py:134-153`. Discriminating evidence:
  compare otherwise matched states with different hidden held-step counts and
  inspect whether policy outputs differ only when internal recurrent state
  differs.

- [Reasoned implication] The control loop maps observation -> bounded joint
  command -> 10 physics integrations -> sampled endpoint distance -> reward,
  held-step state, and next observation. Reward shapes learning but does not
  change the physical success definition; its progress, closeness, hold,
  action-cost, and completion terms are not evidence of episode success.
  Decision relevance: model selection must use complete success, not reward
  total or first-reach proxy. Assumptions: the evaluator uses the stated
  `is_success` outcome rather than reward. Sources:
  `robot_learning/scenario/environment.py:122-160`,
  `robot_learning/training/reward.py:25-91`,
  `robot_learning/scenario/evaluation.py:65-90`. Discriminating evidence:
  compare reward totals with binary success and the retained hold diagnostics.

### Scientifically meaningful behavior quantities

- [Reasoned implication] The physically meaningful trajectory quantities are
  target radius/angle, q, q_dot, q_ddot, command and saturation, endpoint
  position/velocity, endpoint error norm, Jacobian conditioning, first entry
  into tolerance, contiguous in-tolerance duration, hold interruptions,
  minimum/final distance, and truncation. They separate geometry, actuation,
  convergence, and stabilization mechanisms. Decision relevance: these
  quantities identify which capability limits complete episode success.
  Assumptions: quantities derived from simulator state are recorded with the
  same time convention. Sources:
  `robot_learning/scenario/evaluation.py:47-90`,
  `robot_learning/scenario/observations.py:37-47`. Discriminating evidence:
  retain synchronized per-control-step traces rather than only aggregate
  success percentages.

## Unknowns

### Effective inertial and actuator parameters

- [Unresolved quantity] The visible XML does not state link mass/density or
  inertia, so the effective mass matrix, natural frequencies, acceleration
  limits, and settling time are not known numerically from the human-authored
  source. Decision relevance: this can change whether high-gain setpoint
  control, smooth trajectory control, or learned feedback is physically
  viable, and it changes action-scale interpretation. Assumptions: MuJoCo
  compiler defaults materially determine these quantities and no later source
  overrides them. Sources:
  `contracts/robots/two_joint_arm.xml:2-32`. Discriminating evidence: inspect
  `MjModel` masses, inertias, damping, and actuator transmission, then measure
  local responses at open and folded configurations.

- [Unresolved quantity] The realized torque and acceleration under saturated
  commands, including any configuration-dependent coupling and numerical
  integration effects, are not established by the XML declarations alone.
  Decision relevance: it determines how early the policy must brake and
  whether 20 ms action quantization causes overshoot outside the 1 cm ball.
  Assumptions: the nominal gear interpretation is correct but effective
  motion still depends on compiled dynamics. Sources:
  `contracts/robots/two_joint_arm.xml:30-32`,
  `robot_learning/scenario/environment.py:128-133`. Discriminating evidence:
  execute controlled positive, negative, and zero commands from multiple q
  states and record q, q_dot, and endpoint motion.

### Hold-time semantic resolution

- [Unresolved quantity] The task contract says the end effector must remain
  continuously within tolerance, while the accessible shared environment
  updates the hold counter only once after each 10-substep action interval.
  It is therefore not established from these sources whether the protected
  official evaluator rejects a transient excursion inside a 20 ms interval or
  uses the same sampled interaction semantics. Decision relevance: this
  changes the required stabilization bandwidth and the interpretation of a
  nominal 100-step hold. Assumptions: the protected benchmark may implement
  semantics not visible in the shared research environment. Sources:
  `contracts/scenario.md:10-13`,
  `robot_learning/scenario/environment.py:128-159`. Discriminating evidence:
  obtain the authoritative task-reference/protected semantics or compare
  substep endpoint traces against evaluator outcomes for trajectories that
  cross the tolerance between control boundaries.

### Self-contact and contact dynamics

- [Unresolved quantity] The target and plane are explicitly non-colliding, but
  the arm geoms retain ordinary collision masks and no explicit self-contact
  exclusion is visible in the XML. Whether folded configurations generate
  contacts, and whether those contacts materially alter motion, is not known
  from source inspection alone. Decision relevance: contact can create a
  qualitatively different failure class and can make the folded IK branch
  less useful than the open branch. Assumptions: default MuJoCo collision
  filtering is active and the policy visits sufficiently folded states.
  Sources: `contracts/robots/two_joint_arm.xml:14-19,25-26`. Discriminating
  evidence: record contact counts, normal forces, and branch-conditioned
  outcomes during folded and open trajectories.

### Distribution exposure and difficulty

- [Unresolved quantity] The baseline training constructor exposes only radii
  14--20 cm, whereas official assessment includes 6--14 cm. The consequence
  for learned branch selection, conditioning, and hold reliability at inner
  radii is not known before evidence. Decision relevance: it can change the
  first campaign choice between improving the baseline recipe and changing
  target exposure. Assumptions: the baseline constructor is used for the
  initial policy and no additional curriculum or domain randomization supplies
  inner-radius experience. Sources:
  `robot_learning/training/environment.py:9-20`,
  `contracts/scenario.md:10-13`. Discriminating evidence: evaluate matched
  radius strata with first-reach, Jacobian conditioning, and complete hold
  success, while preserving the official aggregate criterion.

### State observability at the success boundary

- [Unresolved quantity] The observation omits hold count, acceleration,
  actuator effort, and contacts. It is not known whether q, q_dot, and endpoint
  error alone make the sampled hold sufficiently easy, or whether hidden
  history and recurrent memory are needed to distinguish safe settling from a
  soon-to-fail oscillation. Decision relevance: this can change whether the
  first investigation should target observation/memory or physical feedback
  dynamics. Assumptions: no policy-side memory or auxiliary signal is assumed
  unless its saved runtime contract provides it. Sources:
  `robot_learning/scenario/observations.py:37-47`,
  `contracts/policy_runtime.py:47-72`. Discriminating evidence: compare
  feed-forward and recurrent action histories on matched physical states and
  quantify hold interruptions without using reward as a substitute.

## Decision-relevant synthesis

### Reachability is likely not the limiting mechanism

- **Decision relevance:** Official targets lie inside the two-link workspace and
  have at least one joint-limit-feasible analytic IK branch; broad failure is
  therefore more likely to involve control, dynamics, exposure, or hold
  stability than geometric impossibility.
- **Assumptions:** The target remains in z=0.02 m, link lengths match the
  compiled model, and the analytic joint-limit calculation applies.
- **Source references:** `contracts/scenario.md:10-13`;
  `contracts/robots/two_joint_arm.xml:10-21`;
  `robot_learning/scenario/observations.py:17-36`.
- **Discriminating evidence:** Branch-feasibility enumeration and success
  stratified by target radius and angle, with Jacobian conditioning.

### Completion is a stabilization problem, not only a reach problem

- **Decision relevance:** The objective requires 100 consecutive control-step
  successes; first reach, low minimum distance, or reward cannot certify the
  policy. Early decisions should distinguish transient convergence from
  terminal hold failure.
- **Assumptions:** The uninterrupted 2 s criterion is authoritative and
  sampled diagnostics faithfully identify interruptions.
- **Source references:** `contracts/scenario.md:10-20`;
  `robot_learning/scenario/environment.py:134-159`;
  `robot_learning/scenario/evaluation.py:65-90`.
- **Discriminating evidence:** Complete binary episode outcomes paired with
  first-reach step, maximum held steps, interruption count, endpoint velocity,
  and final distance.

### Unknown compiled dynamics can change the control route

- **Decision relevance:** Missing authored mass and inertia values leave
  torque-to-motion authority, overshoot, and settling time unresolved. This is
  the main physical uncertainty that could change the initial choice between
  setpoint-like, trajectory-like, or feedback-oriented learning.
- **Assumptions:** MuJoCo's inferred inertial quantities and default contact
  behavior materially affect the observed closed-loop response.
- **Source references:** `contracts/robots/two_joint_arm.xml:2-32`;
  `robot_learning/scenario/environment.py:128-133`.
- **Discriminating evidence:** Compiled-model parameter inspection plus
  controlled step responses at representative open and folded configurations.

### Official exposure differs from baseline exposure

- **Decision relevance:** Training on 14--20 cm does not cover the official
  6--14 cm inner band, where elbow geometry and conditioning differ. This can
  change whether the first campaign effort should address generalization or
  stabilization in the already-seen outer band.
- **Assumptions:** The baseline training constructor describes the initial
  exposure and no other training source supplies the missing radii.
- **Source references:** `robot_learning/training/environment.py:9-20`;
  `contracts/scenario.md:10-13`.
- **Discriminating evidence:** Radius-stratified development evaluation using
  the same success definition, with matched diagnostics for reach and hold.

### Continuous-hold semantics must not be assumed from endpoint samples

- **Decision relevance:** A transient within-interval excursion would be
  invisible to the accessible held-step counter but could violate the human
  contract. Resolving this can change the required control bandwidth and the
  validity of sampled hold diagnostics.
- **Assumptions:** The protected evaluator may differ from the shared
  environment's post-frame-skip check.
- **Source references:** `contracts/scenario.md:10-13`;
  `robot_learning/scenario/environment.py:128-159`.
- **Discriminating evidence:** Authoritative task-reference semantics or a
  paired comparison of substep traces with official evaluator outcomes on
  boundary-crossing trajectories.
