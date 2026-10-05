# Scientific model of the two-joint arm reach-and-hold task

## System interpretation

This is a planar, torque-actuated two-link manipulator reaching a stationary
point target. The relevant state is the arm configuration and velocity together
with the fixed target location. There is no gravity, moving target, obstacle, or
task-object contact to provide a physical disturbance or force cue. Success is
therefore a feedback-control problem: move from the reset configuration into a
small Cartesian tolerance region, remove residual motion, and remain there for
the entire required dwell.

## Established facts

### Morphology, geometry, and kinematics

- The arm has two revolute degrees of freedom, shoulder and elbow, both rotating
  about the world \(z\)-axis. The upper arm is 12 cm and the forearm is 10 cm.
  Their centerline motion is confined to the horizontal plane at \(z=2\) cm.
- The end effector is at the forearm tip. Link capsule radii are 1.5 cm and
  1.2 cm; the end-effector site marker has radius 0.8 cm. The base is a
  non-actuated 4 cm-radius, 4 cm-high cylinder.
- Each joint range is \([-170,170]\) degrees. Ignoring the small effect of these
  limits and link thickness, the two-link centerline workspace is the annulus
  from \(|12-10|=2\) cm to \(12+10=22\) cm.
- The official target radius is sampled uniformly between 6 and 20 cm and its
  angle uniformly over the full circle. The target is placed at the arm-plane
  height. The target and plane are non-colliding visual/mocap geometry; success
  uses the distance between the end-effector site and target center, not either
  rendered radius.
- For every official target radius, the two usual inverse-kinematic branches
  (positive and negative elbow angle) are available and fit the stated joint
  limits. They are represented in the observation by four current-to-branch
  joint-angle errors.

### Actuation, simulation, and timing

- The action has two components, is clipped to \([-1,1]\), and is passed through
  unchanged to the two MuJoCo motors. Each motor has gear 5, so the command
  supplies a signed joint torque proportional to \(5\,\mathrm{ctrl}\), subject
  to the simulator’s actuator and joint constraints.
- The simulator timestep is 2 ms. An action is held constant for 10 simulator
  steps, giving a 20 ms control interval and a 50 Hz policy-control rate.
- Each joint has explicit damping 0.5 and armature 0.01. Gravity is zero. Link
  mass and inertia are not authored explicitly in the XML; the compiled MuJoCo
  model derives inertial properties from the geoms and simulator defaults.
- At reset, joint positions and velocities are zero. The arm is straight along
  positive \(x\), so the end effector starts at \((22,0,2)\) cm. The target is
  then sampled and fixed for the episode. The initial Cartesian error is
  consequently between approximately 2 and 28 cm, depending on target radius
  and angle.
- The official tolerance is 1 cm. The hold lasts 2 seconds, which is 100
  consecutive control intervals. An episode has at most 500 control intervals
  (10 seconds). The environment updates the hold counter from the
  end-of-interval distance; an out-of-tolerance check resets the counter.

### Sensing and policy interface

- The observation has 11 float components: two joint positions, two joint
  velocities, the three-dimensional end-effector-to-target displacement, and
  four wrapped joint-angle errors to the two analytic inverse-kinematic
  branches.
- There is no sensor noise, latency, contact sensing, force sensing, or target
  motion. The target is not given as absolute coordinates, but the current
  joint state and target-relative end-effector displacement contain enough
  information to reconstruct its position for this deterministic model.
- The observation exposes the physical state needed for feedback, but not
  acceleration, actuator torque after simulation, contact impulses, or action
  history. The action is a command, not a desired joint position or velocity.

## Physical consequences

The reset posture is the fully extended configuration. At zero joint angles the
planar end-effector Jacobian has rank one: first-order motion is tangential,
while radial motion toward or away from the straight-arm endpoint requires
changing the elbow configuration. Thus the controller must generally break the
initial straight posture before it can efficiently correct radial error. This
creates a distinct early-trajectory problem from the later stabilization
problem.

All official targets are kinematically reachable, but reachability does not
imply a short or dynamically easy path. The controller must coordinate shoulder
and elbow motion to select an inverse-kinematic branch, move through a
collision-free or otherwise dynamically admissible trajectory, decelerate
before entering the 1 cm disk, and avoid crossing its boundary for 100
successive observations. A branch change near the target is physically
expensive because the two configurations generally require different joint
velocities and can produce a large Cartesian excursion; consistent branch
selection is therefore a plausible mechanism of reliable behavior.

The target is stationary and gravity is absent, so a configuration at rest does
not need to counter a static external load. Holding still nevertheless
requires closed-loop damping of residual joint velocity and correction of
errors caused by finite action intervals, inertia, and actuator saturation.
The 20 ms zero-order-held action makes this a sampled-data stabilization task:
motion between checks can be invisible to the success counter, while a single
failed check after partial progress destroys the accumulated hold.

The 1 cm criterion is a Cartesian disk in the arm plane, not independent
per-joint tolerances. Near a stretched or otherwise ill-conditioned posture,
small joint changes can produce different Cartesian sensitivities than in a
folded posture. Consequently, identical joint-level errors need not have
identical task significance. The complete behavior couples gross reaching,
velocity management, local Cartesian convergence, and robustness of the final
equilibrium; optimizing only minimum distance or first entry would not establish
episode success.

The training constructor currently samples only radii 14--20 cm, whereas the
official distribution includes 6--14 cm. This changes the physical variety
encountered during learning but not the official evaluation mechanics or
success definition. The reward supplies progress, closeness, hold-progress,
completion, and small action terms; these are learning signals, not additional
task requirements and cannot substitute for the uninterrupted hold.

## Scientifically meaningful measurements

For each target, the most informative measurements are target radius and angle;
joint position, velocity, acceleration, and inferred motor torque trajectories;
end-effector Cartesian error decomposed into radial and tangential components;
first tolerance-entry time; overshoot and peak speed; minimum and final distance;
the longest uninterrupted in-tolerance run; number and timing of hold
interruptions; and action magnitude during approach versus hold. These
quantities separate kinematic branch choice and initial escape from the
straight-arm singularity, trajectory/convergence quality, and final
sampled-data stability.

## Unknowns

- The exact compiled masses, joint-space inertia matrix, actuator transmission
  details, integrator/solver behavior, and resulting acceleration/torque
  limits are not specified numerically by the human-authored XML. They
  determine approach time, overshoot, and how much authority remains near
  saturation.
- The XML gives link geoms their default collision settings but does not state
  explicit self-collision exclusions. Whether folded link capsules generate
  contacts in the compiled model, and whether those contacts matter for
  successful branches, must be established from the instantiated simulator
  rather than assumed from the kinematic diagram.
- The source specifies hold checks at control boundaries, not a continuous
  geometric trace between the 2 ms simulator updates. The relationship between
  unobserved within-interval excursions and the intended physical meaning of
  “continuously” is therefore an operational semantic to keep distinct from
  the idealized continuous-time requirement.
- Before campaign evidence, it is unknown which inverse-kinematic branch is
  dynamically easiest across target angle and radius, how often policies switch
  branches, whether the initial singular configuration dominates long reaches,
  and whether failures arise primarily during approach, convergence, or hold.
- The scientifically decisive reliability quantities are not known: settling
  time distribution, boundary-crossing margin, velocity at first entry, torque
  margin during hold, sensitivity to target geometry, and the rate of rare
  one-step hold interruptions. A high mean proximity or short first reach would
  not determine these quantities or establish the required 98% episode success.
