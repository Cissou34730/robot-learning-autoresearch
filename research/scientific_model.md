# Preliminary scientific model: two-joint arm reach-and-hold

This is the pre-campaign model of the embodied learning system. It distinguishes
what the repository specifies from consequences derived from those specifications
and from quantities that require campaign evidence. The causal objective is not
merely to reach a target: the policy must regulate the end effector inside the
official tolerance continuously long enough for the hold counter to complete.

## Causal system view

At reset, the system samples a target and places the arm in the same known
zero-position, zero-velocity state. The policy receives joint position and
velocity, the end-effector-to-target displacement, and errors to two analytic
inverse-kinematics configurations. It emits two bounded motor commands. Each
command is held while MuJoCo advances the plant, producing a new end-effector
position. The distance to the target determines whether the consecutive-hold
counter increments or resets; that counter produces the binary episode outcome.

The main causal chain is therefore:

`target geometry -> desired joint configuration -> policy action -> arm dynamics
-> endpoint distance over time -> uninterrupted hold -> episode success`.

Learning can affect both the time to enter the tolerance and the closed-loop
stability after entry. The latter is essential because a brief successful reach
followed by one excursion is still a failed episode.

## Established facts

These are directly specified by `research/scenario.md` or by the human-authored
robot and benchmark implementation.

- The plant is a planar, two-hinge arm with a 0.12 m upper arm and a 0.10 m
  forearm. Both shoulder and elbow rotate about the world z axis and have
  nominal joint ranges of -170 to 170 degrees.
- Gravity is zero. The MuJoCo integration timestep is 0.002 s. The official
  control frame skip is 10, so one policy action governs 0.020 s of simulated
  time and the control rate is 50 Hz.
- The two motor actions are continuous, clipped to [-1, 1], and applied through
  actuators with control range [-1, 1] and gear 5. The joints have damping 0.5
  and armature 0.01 in the XML model.
- At reset, both joint positions and velocities are zero. A target is sampled
  with angle uniform over the full circle and radius uniform from 0.06 m to
  0.20 m. Its z coordinate is set to the end-effector z coordinate, so the
  target and arm motion share a plane.
- The official success tolerance is a three-dimensional Euclidean distance of at
  most 0.01 m. The policy must satisfy that condition for 2.0 uninterrupted
  seconds, represented by 100 consecutive control steps. Any step outside the
  tolerance resets the consecutive counter.
- An episode is limited to 500 control steps, or 10 simulated seconds. The
  official assessment uses one frozen policy on 200 fixed-seed episodes
  (seeds 1000 through 1199). At least 196 successes are required for the
  operational 98% objective.
- The official endpoint is the hold outcome, not a shaped reward or ordinary
  Gymnasium termination. The protected benchmark records success only when the
  consecutive-hold condition terminates the episode; truncation at the horizon
  is not success.
- The standard observation has 11 values: two joint positions, two joint
  velocities, three endpoint-target displacement coordinates, and four wrapped
  joint errors to the open and folded inverse-kinematics solutions. The action
  and observation interfaces are therefore state-informed rather than
  image-based.
- The current research training environment samples only radii 0.14-0.20 m,
  while research evaluation and the official benchmark sample 0.06-0.20 m.
  The research reward currently combines distance progress, closeness,
  incremental hold progress, a completion bonus, an action cost, and a small
  penalty after leaving the tolerance band. These are research choices, not
  changes to the official success definition.
- The benchmark contains no contact task: the plane, target, and arm geometry
  have non-colliding contact settings, and the target is a mocap body. The
  task is free-space positioning and regulation in a deterministic simulator
  as implemented; no sensor noise, actuator noise, external disturbance, or
  target motion is specified.

## Physical consequences

These are reasoned implications of the established implementation, not campaign
measurements.

- In the arm plane, the nominal forward kinematics are
  `x = 0.12 cos(q1) + 0.10 cos(q1 + q2)` and
  `y = 0.12 sin(q1) + 0.10 sin(q1 + q2)`. The ideal radial reach interval is
  0.02-0.22 m. The official 0.06-0.20 m band lies inside that interval, so
  every sampled radius is geometrically reachable in the ideal kinematic model.
- For the official radial band, the principal elbow inverse-kinematics angle
  lies approximately between 49.5 and 150.1 degrees. The corresponding
  shoulder branch can be selected within the stated joint limits for every
  target angle. Thus the benchmark is not intended to contain an unreachable
  target; failures should arise from policy, transient dynamics, regulation, or
  the finite episode horizon rather than target impossibility.
- The target is sampled uniformly in radius rather than uniformly in planar
  area. Equal-width radial bands therefore receive equal sampling probability,
  and the inner part of the annulus has greater target density per unit area.
  A policy's aggregate success rate can consequently hide radial variation.
- The official band is separated from the exact radial singularities at the
  arm's minimum and maximum reach. For the two analytic elbow branches, the
  target geometry still changes the required configuration and the local
  dynamics, but the task is not dominated by an exact fully extended or fully
  folded endpoint.
- A 0.01 m tolerance is a small positional tube relative to the 0.22 m arm
  reach. Since the hold is sampled at 50 Hz, a controller must keep its
  closed-loop endpoint error below that boundary across 100 inter-action
  intervals, not merely stop near the target at one instant.
- The action is zero-order-held for 20 ms while the plant integrates at 2 ms.
  This makes the learned policy a sampled-data controller. Motor saturation,
  joint damping, armature, and delayed observation-to-action updates can create
  overshoot or residual motion even in the absence of disturbances.
- Because gravity and contacts are absent and the target is stationary, the
  principal regulation problem is rotationally symmetric in target angle at
  the plant level. Angle-dependent performance would therefore indicate
  effects such as representation, joint-limit proximity, branch selection,
  numerical policy behavior, or learning rather than a gravity load.
- The fixed zero-state reset removes variation in initial arm state but leaves
  target geometry randomized. A policy has up to 500 actions to reach and then
  complete the hold; if it first enters the tolerance too late, there may be
  insufficient remaining time for 100 consecutive in-tolerance samples.
- The current narrower training-radius range creates a direct coverage gap for
  the 0.06-0.14 m portion of the official distribution. Whether that gap harms
  success is unresolved; it is not evidence that the policy fails there.
- The shaped reward supplies learning signal before success, but its scalar
  optimization target is not identical to the binary official objective. In
  particular, distance progress or partial hold progress can be rewarded even
  when an episode ultimately fails, so reward improvement alone cannot establish
  the human goal.

## Unknowns

These quantities are not established before campaign evidence exists and should
be treated as explicit objects of inquiry.

- The probability of complete episode success under the official distribution,
  including whether the 98% threshold can be reached, is unknown. No learned
  policy result is assumed by this model.
- The relative contribution of acquisition failures, overshoot, steady-state
  error, tolerance-boundary crossings, and late-horizon failures is unknown.
  The important distinction is whether the dominant limitation is reaching the
  tube or maintaining a 100-step invariant set once inside it.
- The effective closed-loop settling time, residual oscillation, and sensitivity
  to target radius and angle are unknown. XML damping and actuator parameters
  define the simulated plant, but they do not predict the behavior of a
  particular learned controller without rollouts.
- The reachable set under the actual saturated, discretely controlled dynamics
  and the time required to reach each part of the target band are unknown,
  despite nominal kinematic reachability.
- It is unknown whether the 11-value observation gives the learned policy a
  sufficiently well-conditioned representation across the full target band,
  especially when choosing between the two inverse-kinematics branches.
- The effects of the current reward terms, training-radius restriction, policy
  architecture, optimization algorithm, seed, and training duration on final
  hold reliability are unknown. None should be inferred from their presence in
  the repository.
- The official 200-episode panel is the defined verdict for this campaign, but
  the policy's performance on unseen draws outside that fixed panel and the
  statistical uncertainty around its underlying distributional success rate are
  unknown.
- No evidence yet identifies the failure distribution by radius, angle, first
  reach time, longest uninterrupted hold, or final distance. Those measurements
  are needed to discriminate geometric coverage problems from control-stability
  problems and to direct later interventions toward the 98% episode objective.
