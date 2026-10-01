# Scientific model of the two-joint reach-and-hold system

This is a pre-campaign model of the physical task, based on the scenario
definition and the human-authored MuJoCo robot and benchmark implementation.
Repository facts are separated from their physical implications and from
quantities that require measurement or compiled-model inspection.

## Established facts

- The robot has two revolute joints, shoulder and elbow, both rotating about
  the world z axis.  The upper-arm and forearm kinematic lengths are 0.12 m and
  0.10 m.  The end-effector site is at the distal end of the forearm, so the
  moving mechanism has two planar degrees of freedom and a fixed z coordinate.
- With joint angles \(q_1,q_2\), the end-effector position in the arm plane is
  \[
  x=0.12\cos q_1+0.10\cos(q_1+q_2),\qquad
  y=0.12\sin q_1+0.10\sin(q_1+q_2).
  \]
  The joints are limited to \([-170^\circ,170^\circ]\).  The arm is initially
  at \(q=(0,0)\) with zero joint velocity, pointing along positive x.
- The unconstrained planar workspace is the annulus from
  \(|0.12-0.10|=0.02\) m to \(0.12+0.10=0.22\) m.  Official targets have
  radius 0.06--0.20 m and angle over the full circle.  The implementation
  samples radius and angle independently and uniformly, then places the target
  at the end-effector's initial z height.  Success is based on the
  three-dimensional site-to-target distance, which is therefore a planar
  distance for these targets.
- Each joint is driven by a MuJoCo motor with control range [-1, 1] and gear
  5.  The policy action is passed through as the physical two-command vector
  and clipped to this range.  A command is held while MuJoCo performs ten
  integration steps.  The simulation timestep is 0.002 s, giving a 0.020 s
  control interval.
- The model has zero gravity.  Each joint explicitly has damping 0.5 and
  armature 0.01.  No task interaction depends on contact: the target is a
  mocap body and success uses distance to its position, not collision with its
  sphere.
- At every control interval the benchmark measures distance after the ten
  simulation steps.  A distance at or below 0.01 m increments the hold streak;
  any measured distance above it resets the streak.  The required streak is
  100 consecutive control intervals, nominally 2 s.  An episode can run for at
  most 500 intervals.  The official assessment uses 200 fixed episodes and
  requires at least 196 successes.
- The observation contains the two joint positions, two joint velocities, the
  three-dimensional end-effector-to-target vector, and four wrapped joint-angle
  errors: the errors to both inverse-kinematic elbow branches.  It has 11
  components.  The observation does not explicitly contain the hold counter,
  episode time, or previous action.

## Physical consequences

- The target annulus is kinematically reachable in the ideal planar geometry,
  but it is not dynamically uniform.  Targets near 0.06 m require a folded
  configuration (the elbow angle is near \(180^\circ\) in magnitude), whereas
  targets near 0.20 m require a more extended configuration.  The two
  inverse-kinematic solutions generally correspond to opposite signs of
  \(q_2\), with a corresponding different shoulder angle.  Joint limits can
  remove a branch near the angular wrap, so a reliable controller must select
  and maintain a feasible branch rather than assume one global posture.
- The reset posture is fully extended and is a kinematic singularity for
  instantaneous Cartesian motion: the shoulder and elbow columns of the
  planar Jacobian are collinear at \(q=(0,0)\).  The arm can still leave this
  posture because joint torques create angular acceleration, but lateral
  target motion initially requires bending the elbow before the end-effector
  can acquire general planar velocity.  Thus target direction, not only
  target distance, affects the initial maneuver.
- The motor command produces joint torque through the gear transmission; with
  the stated bounds its nominal magnitude is 5 in the model's torque units.
  The mechanism is therefore a second-order plant: actions change velocity and
  only subsequently change position.  Damping dissipates motion, while
  armature contributes to the effective rotational inertia.  Because gravity is
  absent, an exactly reached pose with zero velocity is a static equilibrium
  without gravity compensation; the main hold problem is removing and
  regulating residual motion generated during the reach.
- Holding one action for 20 ms makes the controller sample-and-hold rather than
  continuously modulate torque.  A fast or aggressive reach can cross the
  1 cm boundary between control updates, and braking decisions made too late
  can produce repeated entry and exit from the tolerance.  The required
  behavior is consequently a coupled reach, deceleration, convergence, and
  disturbance-free stabilization problem, not merely inverse kinematics.
- The benchmark's “uninterrupted” criterion is implemented as 100 consecutive
  post-control-step checks.  Excursions that occur and recover entirely within
  one ten-substep interval are not separately counted, while an excursion
  visible at any interval boundary destroys the streak.  A policy must
  therefore keep a margin inside the tolerance and suppress velocity, rather
  than optimize only its sampled final position.
- Joint position and velocity plus the current Cartesian error expose the
  instantaneous mechanical state needed for deterministic control.  Although
  the target position is not provided as a separate absolute field, it can be
  reconstructed from the known forward kinematics and the observed
  end-effector-to-target vector.  The four branch errors additionally expose
  the two principal posture goals.  The unobserved hold streak is task memory:
  a feed-forward policy cannot know how long the current in-tolerance run has
  lasted except through its state history or a recurrent mechanism.
- The same Cartesian error can be approached through different joint postures,
  and the two branches have different velocities, actuator demands, and
  distance to the joint limits.  Switching branches during a reach requires
  substantial joint motion and can create avoidable transients; a successful
  policy should generally converge to one feasible branch and stabilize there.
  The wrapped angular representation also introduces a coordinate discontinuity
  at the \(-\pi/\pi\) boundary, so equivalent target directions near that
  boundary can have numerically different error coordinates.

## Unknowns

- The XML does not specify body mass, density, or full inertia tensors
  explicitly.  The compiled MuJoCo model supplies the effective inertias from
  its geometry and defaults, but the resulting joint accelerations, natural
  time scales, damping ratios, and actuator saturation behavior have not been
  measured here.  These quantities determine whether the nominal torque
  authority is sufficient for fast arrival and low-velocity capture across the
  target annulus.
- Before data exist, the reachable geometry does not establish reliable
  closed-loop performance.  It is unknown how arrival time, overshoot,
  settling time, peak joint speed, peak command, and hold margin vary with
  target radius, angle, and chosen inverse-kinematic branch.
- It is unknown whether the policy will consistently choose the branch with
  the best dynamic margin, whether it will switch branches, or whether
  near-folded and near-angular-limit postures create distinct failure classes.
  The reset singularity may also produce direction-dependent early transients
  that are not predicted by target radius alone.
- The observation is physically rich but does not reveal the hold counter or
  sub-control-step boundary crossings.  It is unresolved whether a policy can
  infer sufficient phase and stability information from joint velocity and
  error alone, especially when the same instantaneous state is reached after
  different hold histories.
- The scientifically meaningful quantities for resolving these uncertainties
  are the complete time series of target radius and angle, joint positions and
  velocities, Cartesian radial and tangential error, distance at every
  control boundary, actuator commands, branch residuals, and substep
  excursions.  From them, arrival time, peak speed and torque, settling time,
  tolerance margin, longest uninterrupted streak, and failure attribution can
  be determined.  No claim about the policy's success rate, or about meeting
  the 98% objective, is justified before those measurements exist.
