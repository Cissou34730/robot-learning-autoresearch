# Preliminary scientific model: two-joint arm reach-and-hold

This is the campaign-start model of the embodied learning system. It is based
on `research/scenario.md`, the protected MuJoCo robot model, and the protected
task and assessment implementations. It is written before campaign evidence
exists and is therefore a physical and learning reference, not a performance
claim. Repository facts are kept separate from implications and unresolved
quantities.

## Established facts

The repository defines a deterministic two-link MuJoCo arm, a fixed target
sampling rule, a sampled action interface, and an uninterrupted-hold success
contract. The following facts are directly established by those protected
implementations.

### Human task and assessment

- The controlled plant is a planar, two-joint serial arm. The shoulder and
  elbow are hinge joints about the world z axis. The upper arm is 0.12 m and
  the forearm is 0.10 m long.
- At reset, both joint positions and velocities are set to zero. A target is
  then sampled independently with angle uniformly distributed over
  `[-pi, pi]` and radius uniformly distributed over `[0.06, 0.20]` m. Its z
  coordinate is set to the end-effector plane, so the target is stationary in
  the arm's plane for the episode.
- The official tolerance is 0.01 m Euclidean distance between the end
  effector and the target. The end effector must be inside that tolerance for
  100 consecutive control steps, which is 2.0 s at the official timing.
  Leaving the tolerance resets the consecutive-hold count. A complete
  uninterrupted hold is the episode outcome.
- An official episode has at most 500 control steps. The final assessment
  evaluates one frozen policy on 200 fixed-panel episodes, and the campaign
  objective is met at 196 or more successes (at least 98 percent). The
  development task-reference panel is separate from this final panel.

### Plant and control interface

- MuJoCo advances the model at a 0.002 s physics timestep with gravity
  disabled. Each policy action is applied for 10 physics steps, giving a
  0.020 s control interval and 50 policy decisions per second.
- Each action has two components and is clipped to `[-1, 1]`. The XML uses
  one motor on each joint with gear 5. The joints have damping 0.5 and
  armature 0.01; their declared position ranges are -170 to 170 degrees.
  The plane and arm geoms have collisions disabled, so the task contains no
  contact interaction.
- The target is a mocap body and is not itself a dynamical object. There is no
  explicit process noise, observation noise, disturbance, or target motion in
  the task implementation. Saved policies are evaluated with deterministic
  action prediction.

### Policy information and task mechanics

- The standard observation has 11 float values: two joint positions, two joint
  velocities, the three-dimensional end-effector-to-target displacement, and
  four wrapped inverse-kinematics errors. The last four values are shoulder and
  elbow errors for the open-elbow and folded-elbow solutions computed from the
  two link lengths.
- The standard action mapping is the identity, so the policy directly proposes
  the two physical motor commands. The saved policy runtime preserves the
  observation and action mapping used when that policy was produced.
- The protected benchmark declares the success mechanics independently of
  training reward. The research environment uses a reward containing distance
  progress, exponential closeness, incremental hold progress, an action
  magnitude cost, an outside-band penalty after a hold interruption, and a
  completion bonus. The current hold-exit forfeiture fraction is zero.
- The baseline training constructor samples only radii in `[0.14, 0.20]` m.
  The evaluation and official task constructors sample the full `[0.06, 0.20]`
  m range. The baseline trainer currently uses PPO with a feed-forward
  multilayer policy, but the learning method is replaceable and is not part
  of the immutable task boundary.

## Physical consequences

- The arm's unconstrained planar kinematic workspace is an annulus from
  `|0.12 - 0.10| = 0.02` m to `0.12 + 0.10 = 0.22` m. Therefore the
  official radial interval lies inside the nominal workspace, but that fact
  alone does not establish reachability with the declared joint limits,
  acceptable branch selection, or dynamic control.
- There are two inverse-kinematic elbow branches for most official targets.
  The observation exposes both branches rather than requiring the policy to
  infer them only from a Cartesian error. A successful controller must still
  select a branch that stays away from the shoulder and elbow limits and
  settle it with bounded motion; branch availability is not the same as
  stable tracking.
- The reset creates a common initial arm state but a target-dependent initial
  error. The full angular distribution therefore changes the initial
  direction of motion, while the fixed radial distribution changes both
  initial distance and the local kinematic sensitivity. Because the target is
  fixed during an episode, the control problem is point-to-point motion
  followed by regulation, not pursuit.
- A 1 cm ball is a relatively tighter angular requirement for distant targets
  than for near targets: the small-error tangential scale is about 2.9 degrees
  at 20 cm and 9.5 degrees at 6 cm. The exact joint-space tolerance also
  depends on configuration and the Jacobian, so Cartesian distance alone does
  not predict control difficulty.
- The 20 ms zero-order-held action interval makes the hold a sampled-data
  stability problem. Joint inertia, actuator saturation, damping, and the
  policy's action changes determine whether an apparently successful arrival
  overshoots, oscillates, or remains inside the tolerance. The 100-step
  criterion makes a transient reach insufficient: a policy must preserve a
  small end-effector error for a full 2 s.
- With uniform radius rather than uniform area, the target distribution gives
  equal probability to equal radial intervals and consequently more target
  probability per unit planar area near the base. The baseline training band
  covers only 6 of the official 14 cm of radial interval; the 6--14 cm
  region is absent from that baseline training distribution. This is a
  distribution-shift risk, not evidence that the inner region is harder or
  easier.
- The arm's zero-gravity planar dynamics are close to rotationally symmetric
  in the unconstrained interior, but the fixed zero-angle reset, absolute
  shoulder limits, and the two branch representations break exact
  angle-independent learning. Full-angle coverage is therefore relevant even
  though the target geometry is rotationally described.
- Training reward is only a shaping signal. Distance progress and closeness
  can be earned before a hold, and the current reward does not forfeit prior
  hold progress when the tolerance is exited. Consequently, a high training
  return or frequent brief entries into the tolerance is not causally
  equivalent to official episode success. The decisive state variable for the
  objective is the longest uninterrupted in-tolerance streak.
- The official result is a binary count on a fixed 200-episode panel. A mean
  distance, a final distance, a development-panel result, or a reward curve
  cannot substitute for that count. The useful causal failure split is
  failure to enter the tolerance versus interruption after entry, further
  stratified by target radius and angle.

## Unknowns

The following quantities are unresolved before campaign evidence. Each is
decision-relevant because it can change whether the limiting intervention
should target representation, distribution, control dynamics, reward, or
optimization.

- **Constrained workspace and branch margin:** For every official radius and
  angle, what is the nearest valid open or folded configuration to the joint
  limits, and are there thin angular sectors where the 1 cm tolerance is
  reachable only with poor margin? This can be resolved by a deterministic
  constrained-kinematics sweep before attributing such failures to learning.
- **Closed-loop transient behavior:** For each target geometry, what are the
  time to first entry, overshoot, maximum consecutive hold streak, steady
  error, and action saturation pattern? These determine whether the dominant
  gap is motion planning/arrival or regulation/hold stability.
- **Geometry of failure probability:** How does success vary across radius and
  angle, especially between the trained outer band and the untrained inner
  band? The current code provides diagnostic fields for this, but no campaign
  measurements have established the pattern.
- **Observation sufficiency for the required controller:** Does the 11-value
  observation permit a policy to distinguish all dynamically relevant states
  and maintain the correct branch near the tolerance boundary? It contains
  joint position and velocity and target-relative geometry, but no evidence
  yet shows whether the chosen representation supports the required
  precision under the available policy class.
- **Optimization and reward alignment:** Does the current shaped reward make
  sustained, low-action holding more valuable to PPO than repeated brief
  entries, and is the zero hold-exit forfeiture materially harmful? This is
  unknown independently of the mechanics because training can fail to find
  the behavior even when the plant is controllable.
- **Dynamic controllability margin:** What end-effector acceleration and
  settling margin are available under the motor limits after MuJoCo compiles
  the model's inertial properties? The XML fixes the model, but the
  policy-relevant response has not been identified over the workspace.
- **Panel-to-distribution uncertainty:** What success probability would the
  frozen policy have over the complete official distribution rather than the
  fixed 200-episode verdict panel? The final contract decides the campaign
  using 196/200 successes, but no pre-campaign evidence supports treating
  that finite panel as a precise estimate of the distribution-level rate.
- **Robustness to unmodeled variation:** The benchmark contains no explicit
  disturbances or sensor noise. It is unknown whether a policy that succeeds
  in this deterministic contract has any margin to numerical, modeling, or
  execution variation; such robustness is not tested by the official success
  definition and must not be silently inferred.
