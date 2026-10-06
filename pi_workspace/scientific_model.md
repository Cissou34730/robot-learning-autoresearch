# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model of the system. It separates facts
implemented by the contracts and scenario code from consequences derived from
those facts, and from quantities that are not yet established by campaign
evidence. The relevant question is not merely whether the hand can reach a
point: success requires a policy to select and enter a feasible configuration,
remove motion, and keep the end effector inside a 1 cm ball for the full
2-second interval under the sampled control loop.

## System model

The robot is a planar, two-revolute-link arm. The shoulder and elbow axes are
parallel to world z, while the arm lies at z = 0.02 m. With joint coordinates
q = (q1, q2), link lengths L1 = 0.12 m and L2 = 0.10 m, its end-effector
position in the arm plane is

    p(q) = (L1 cos(q1) + L2 cos(q1 + q2),
            L1 sin(q1) + L2 sin(q1 + q2), 0.02).

The initial state is q = (0, 0), qdot = (0, 0): the arm is fully extended along
positive x and the hand starts at (0.22, 0, 0.02). The target is then sampled
in the same plane, so there is no out-of-plane reach problem. The initial
distance can therefore range from nearly 0.02 m to 0.42 m over the visible
6-20 cm distribution, depending on target radius and angle.

The XML gives each joint a -170 to +170 degree range, 0.5 damping and 0.01
armature. Gravity is zero. Each action component is clipped to [-1, 1] and
applied directly as a MuJoCo motor control for ten simulator steps. With the
0.002 s simulator timestep, the policy acts every 0.020 s. The motor gear is
5, so absent another actuator limit the commanded generalized torque is
approximately 5 times the action on the corresponding joint. There is no
target contact: the target is a non-colliding mocap sphere and the plane is
non-colliding. The arm link geoms do not declare explicit collision masks, so
possible self-collision is a model detail rather than an assumed contact
mechanism. The interaction is consequently point-distance regulation, not
grasping or force control against the target.

The official contract requires a target radius from 0.06 to 0.20 m at any
angle, entry into a 0.01 m tolerance, and 100 consecutive control steps in
tolerance. The visible environment computes `round(2.0 / 0.020) = 100`,
increments the hold counter only after each ten-substep action, resets it to
zero on an out-of-tolerance boundary sample, and terminates on 100. An episode
otherwise ends at 500 control steps. Thus the authoritative observable
continuity is 100 successive 20 ms samples; an excursion that leaves and
re-enters during the ten internal MuJoCo steps is not separately represented
by this success counter.

The policy observes 11 values: q, qdot, the 3-D target-to-end-effector
displacement, and four signed angular residuals to the two inverse-kinematic
branches (open and folded elbow). The displacement's z component is zero for
the sampled task. The target's absolute position is omitted, but q and the
relative displacement are sufficient to reconstruct the target position under
the fixed planar geometry. The four IK residuals are therefore useful branch
coordinates rather than independent physical sensors. The hold counter,
episode step count, and action history are not observed.

The visible training distribution is radius 0.14-0.20 m with full angular
coverage, whereas the human task includes 0.06-0.20 m. The shared reward
provides distance progress, a closeness potential, linear hold-progress
reward, a completion bonus, and a small action cost. Exiting a hold has zero
hold-capital forfeiture in the current implementation and receives only the
configured outside-band term. These are learning-signal facts, not changes to
the physical success definition.

## Established facts

* **Morphology and coordinates.** There are two hinge degrees of freedom,
  shoulder then elbow, with 0.12 m and 0.10 m links. The end-effector site is
  at the end of the forearm. Both joints rotate about z, so the reachable
  motion is planar at fixed z. Joint ranges are +/-170 degrees.
  Sources: [S2], [S3].

* **Actuation and timing.** There are two direct motor actuators, one per
  joint, with control range [-1, 1] and gear 5. The simulator timestep is
  2 ms; the environment holds one action for 10 simulator steps, exposing a
  20 ms control interval. Source: [S2]; [S5] lines 52-58 and 122-133.

* **Dynamics named by the model.** Gravity is disabled. Each joint has
  viscous damping 0.5 and armature 0.01. No explicit body masses, friction
  parameters, controller gains, or actuator force limits are authored in the
  XML; MuJoCo resolves geom-derived inertial quantities when loading the
  model. Sources: [S2] lines 1-3 and 12-19, 30-33.

* **Reset and target geometry.** Reset sets both positions and velocities to
  zero, forwards the model, samples an angle uniformly over [-pi, pi] and a
  radius uniformly over the configured interval, and sets target z to the
  current hand z. Source: [S5] lines 83-120.

* **Task outcome.** The official target distribution is 6-20 cm at all angles;
  tolerance is 1 cm; the hold is 2 s or 100 control steps; the official panel
  allows at most 500 control steps and requires at least 196 of 200 successes
  for 98%. Sources: [S1] lines 7-32; [S4] lines 6-11.

* **Observation/action interface.** Observation construction includes q, qdot,
  hand-target displacement, and open/folded IK residuals. The current policy
  action mapping is identity before environment clipping. Sources: [S6] lines
  14-49; [S7] lines 7-16; [S5] lines 60-65 and 122-129.

* **Success state machine.** A distance at or below 0.01 m increments the
  counter; a distance above it resets the counter. Success is termination on
  the counter reaching 100, not merely reaching the tolerance once. Sources:
  [S5] lines 134-168; [S9] lines 45-76.

## Physical consequences

* **The official annulus is geometrically reachable.** Ignoring joint limits,
  the radial workspace is 0.02-0.22 m. With the +/-170 degree elbow limits,
  the smallest radial distance at the limit is about 0.0276 m, so the
  official inner radius 0.06 m remains outside the folded-limit boundary and
  the outer radius 0.20 m remains below maximum extension. This conclusion
  depends on the XML lengths and planar joint convention being the complete
  kinematic model. A static IK sweep over all target angles and radii that
  finds a valid branch would support it; branch failures near joint limits
  would revise it. Sources: [S1], [S2], [S3].

* **There are two mechanically distinct nominal solutions.** For target
  radius r and angle phi,

      cos(q2) = (r^2 - L1^2 - L2^2) / (2 L1 L2)

  gives q2 = +/- arccos(...), and

      q1 = phi - atan2(L2 sin(q2), L1 + L2 cos(q2)).

  These are the open/elbow-up and folded/elbow-down branches represented in
  the observation. The joint limits can make one branch less usable at some
  angular sectors even when the target itself is reachable. This can create
  qualitatively different policies: consistent branch selection, switching
  between branches, or approaches that reach the point but arrive with large
  residual velocity. Sources: [S2] lines 12-20; [S6] lines 18-35.

* **Reaching and holding are coupled through momentum.** A point is accepted
  only at a control boundary, so a fast approach can cross the 1 cm ball
  between samples or enter with enough angular velocity to leave on the next
  sample. Damping removes motion but does not itself enforce a position; the
  controller must use torque to regulate both configuration and velocity.
  The relevant closed-loop capability is therefore trajectory shaping followed
  by local stabilization, not a one-time inverse-kinematic command. Sources:
  [S2] lines 1-3 and 12-19; [S5] lines 130-159.

* **Control authority is configuration-dependent.** The motor torque is bounded
  in command space, while end-effector displacement is related to joint motion
  by the Jacobian. Link coupling and the configuration-dependent joint-space
  inertia change how the same two torques affect hand position and velocity.
  Near a kinematic singularity, a desired Cartesian correction can require
  disproportionately coordinated joint motion. The official radial interval
  avoids exact q2 = 0 maximum extension and exact q2 = pi folding, but does not
  make transient approaches or joint-limit effects uniform. Sources: [S2];
  [S5] lines 125-133.

* **The initial condition makes angular coverage a real control problem.** All
  episodes start in the same fully extended pose, while target angle varies
  over the full circle. Some episodes begin close to the hand and others
  require a long reversal around the base. A policy can therefore fail through
  direction/branch choice, overshoot, or time spent settling even when its
  final IK solution is valid. Sources: [S5] lines 102-120; [S1] lines 7-14.

* **The observed state is nearly sufficient for physical feedback but not for
  administrative state.** Given the fixed model, q and qdot determine the
  mechanical state and the relative target vector determines the target
  location. The omitted hold counter does not affect mechanics, so a
  memoryless stabilizer could in principle maintain the hold. It does mean
  that the policy cannot condition on how much uninterrupted duration remains
  or on whether a previous hold was broken. This matters if time-aware
  behavior or recovery scheduling is useful. Sources: [S5] lines 116-120 and
  134-164; [S6] lines 27-49.

* **Training coverage and official coverage differ physically.** Current
  training samples exclude radii 0.06-0.14 m, although the official task does
  not. The inner region uses more folded configurations and can present
  different torque coupling and branch-limit geometry. Any apparent
  generalization decision therefore depends on whether those configurations
  are learned from structure or merely extrapolated. Sources: [S1] lines
  7-14; [S8] lines 10-19.

* **The complete trajectory has measurable physical signatures.** The
  meaningful quantities are target radius/angle, q and qdot, end-effector
  error, branch and joint-limit margin, action/torque, acceleration or
  overshoot, first entry time, minimum and final distance, uninterrupted held
  steps, and interruption count. Together they distinguish geometric
  reachability, approach shaping, convergence, and sustained regulation;
  episode success alone cannot. The research evaluator already records a
  subset of these quantities, while qdot, action, and substep traces remain
  useful diagnostic extensions. Sources: [S5] lines 134-167; [S6] lines 27-49;
  [S9] lines 90-125.

## Unknowns

* **Effective inertia and torque response.** The XML specifies armature and
  geom shapes but not an explicit mass/density contract. The loaded MuJoCo
  model supplies the actual mass matrix, bias terms, and limit behavior.
  Unknown configuration-dependent quantities include acceleration per unit
  action, actuator saturation beyond the control clip, and the extent to which
  damping dominates near rest. This could change whether early behavior should
  be interpreted as underpowered, overdamped, or simply poorly coordinated.
  Evidence that would discriminate: a controlled action-response measurement
  reporting q, qdot, acceleration, and torque-equivalent response at several
  configurations. Sources: [S2] lines 12-19 and 30-33; [S5] lines 125-133.

* **Branch preference and branch-switching cost.** Both IK branches are
  represented, but no fact yet establishes which is dynamically easier across
  the official annulus, whether one branch approaches joint limits, or whether
  switching causes hold interruptions. This could change how a first policy is
  judged: failures may be branch selection rather than generic reachability.
  Evidence: branch-conditioned trajectories with joint-limit margin, Jacobian
  conditioning, peak speed, and hold interruptions by target angle and radius.
  Sources: [S6] lines 18-47; [S5] lines 160-167.

* **Boundary-sampled versus continuous physical hold.** The environment checks
  distance after each ten-substep action, not at each 2 ms simulator state.
  It is unknown whether policies exploit substep excursions or whether the
  20 ms sampling is sufficiently fine that this distinction is immaterial.
  This could change the interpretation of a 98% result and the design of
  diagnostics. Evidence: substep-resolved distance and velocity traces
  synchronized with the 100 boundary samples. Source: [S5] lines 130-159.

* **Settling-time distribution under the official geometry.** The code exposes
  first reach, minimum distance, final distance, and hold interruptions in
  research evaluation, but no campaign evidence exists for their distributions.
  It is unknown whether the 500-step horizon is restrictive, whether failures
  cluster at small radii or particular angles, and whether most failures occur
  before or during the hold. Evidence: evaluation panels stratified by radius
  and angle with those diagnostics and q/qdot/action traces. Source: [S9]
  lines 40-125.

* **Learning-signal alignment.** The current reward supplies hold progress and
  a completion bonus, but assigns zero hold-capital forfeiture on exit and only
  a small outside-band penalty. It is unknown whether this makes repeated
  fragile entries more attractive during learning than low-velocity
  stabilization. This could change the interpretation of a training plateau,
  but reward arithmetic alone does not establish a physical cause. Evidence:
  compare reach, hold duration, exit/re-entry count, and action magnitude while
  keeping the task mechanics fixed. Source: [S10] lines 40-107.

## Decision-relevant synthesis

1. **Feasibility is likely, but branch and limit geometry must remain explicit.**
   The official annulus lies inside the two-link workspace and has two nominal
   IK branches, subject to +/-170 degree limits. This supports treating early
   performance as a coupled branch-selection and control problem rather than
   assuming all failures are unreachable targets. Assumption: the XML
   kinematics and visible target plane match the protected assessment.
   References: [S1], [S2], [S3], [S6]. Discriminating evidence: an exhaustive
   constrained IK sweep and branch-conditioned trajectory metrics.

2. **The first physical distinction is reach versus stabilization.** A policy
   must enter a 1 cm ball at a control boundary and then suppress enough
   velocity to survive 100 further boundary checks. The same torque and
   damping properties govern both phases, so final-position success alone
   cannot identify the limiting mechanism. Assumption: the visible
   20 ms/100-step semantics are the relevant task interface.
   References: [S1], [S2], [S4], [S5], [S9]. Discriminating evidence: first-reach
   time, entry velocity, minimum distance, held-step trajectory, and
   interruption counts.

3. **Official coverage includes a mechanically different inner region than
   current training.** The visible recipe trains only on 14-20 cm while the
   goal includes 6-20 cm; small-radius targets require more folded
   configurations and may expose different coupling and limits. This can
   change the initial campaign decision between interpreting failures as
   optimization failure and as distribution/geometry coverage failure.
   Assumption: the protected official distribution follows the contract rather
   than the training-only range.
   References: [S1], [S8]. Discriminating evidence: success and stabilization
   metrics stratified by radius, especially 6-14 cm versus 14-20 cm.

4. **The most consequential dynamics are not fully specified by named XML
   constants.** Gravity is absent and damping/armature are known, but effective
   inertial response and any transient substep excursions remain unresolved.
   This can change whether a weak or unstable-looking policy reflects torque
   authority, configuration-dependent inertia, or a policy timing artifact.
   Assumption: MuJoCo's resolved model is the authoritative simulator.
   References: [S2], [S5]. Discriminating evidence: controlled system-response
   measurements and substep-resolved hold traces.

5. **A high episode rate must be interpreted as complete uninterrupted holds,
   not just successful reaches.** The protected objective is 196/200 episodes,
   and the success state machine resets on any out-of-tolerance sampled step.
   The current reward and observation do not directly reveal hold progress, so
   learning evidence should separate entry, convergence, and sustained
   regulation. Assumption: diagnostics remain explanatory and the official
   success bit remains authoritative.
   References: [S1], [S5], [S6], [S9], [S10]. Discriminating evidence: the
   complete per-episode hold trajectory, interruptions, action magnitude, and
   target-geometry stratification.

## Source references

* **[S1]** `contracts/scenario.md`, lines 7-37.
* **[S2]** `contracts/robots/two_joint_arm.xml`, lines 1-33.
* **[S3]** `contracts/robots/two_joint_arm.py`, lines 1-8.
* **[S4]** `contracts/task_spec.py`, lines 6-11.
* **[S5]** `robot_learning/scenario/environment.py`, lines 33-178.
* **[S6]** `robot_learning/scenario/observations.py`, lines 11-49.
* **[S7]** `robot_learning/scenario/policy_io.py`, lines 7-16.
* **[S8]** `robot_learning/training/environment.py`, lines 10-19.
* **[S9]** `robot_learning/scenario/evaluation.py`, lines 26-125.
* **[S10]** `robot_learning/training/reward.py`, lines 16-107.
