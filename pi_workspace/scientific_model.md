# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. It separates what is specified by the
human-authored implementation from consequences inferred from that
specification, and from quantities that must still be measured. References use
repository paths and line ranges so that later campaign evidence can revise
the interpretation without confusing an implementation fact with an observed
result.

## Established facts

### Task and physical layout

The robot is a planar serial arm with two revolute joints about the world
z-axis. The shoulder is at `(0, 0, 0.02)`, the upper arm is 0.12 m, and the
forearm is 0.10 m. The end-effector site is therefore at the two-link
kinematic position

`p(q) = (0.12 cos(q1) + 0.10 cos(q1+q2), 0.12 sin(q1) + 0.10 sin(q1+q2), 0.02)`.

Both joints have authored ranges of -170 to +170 degrees. The ideal
unconstrained planar workspace is the annulus from
`|0.12-0.10| = 0.02 m` to `0.12+0.10 = 0.22 m`; the official target radii,
0.06-0.20 m, lie strictly inside that annulus. Targets cover the full polar
angle and are sampled uniformly in radius, not uniformly by area
(`contracts/scenario.md:9-14`; `contracts/robots/two_joint_arm.xml:9-27`;
`contracts/robots/two_joint_arm.py:5-7`; `contracts/task_spec.py:6`).

The target is a fixed mocap body in the same z-plane as the end effector. It
does not collide with the arm. At reset, the arm is set to `q=(0,0)` and
`qdot=(0,0)`, the model is forwarded, and a target is sampled at the current
end-effector z coordinate. The initial end effector is thus at `(0.22, 0,
0.02)`, while the target is `(r cos(theta), r sin(theta), 0.02)`. The initial
distance is consequently
`sqrt(0.22^2 + r^2 - 0.44 r cos(theta))`
(`robot_learning/scenario/environment.py:102-120`; `contracts/robots/two_joint_arm.xml:12-25`).

### Actuation, timing, and simulation

The MuJoCo timestep is 0.002 s and gravity is zero. Each action has two
components in `[-1,1]`, is passed through unchanged by the policy I/O, is
written to the two motor controls, and is held for ten MuJoCo steps. The
control interval is therefore 0.020 s, or 50 Hz. Each motor has gear 5 and
control range `[-1,1]`, giving a nominal direct joint-torque scale of
`[-5,+5]` in the absence of other actuator or joint effects. There is no
position-servo target in the authored actuator model. Each joint has damping
0.5 and armature 0.01. The plane and target have collision disabled
(`contracts/robots/two_joint_arm.xml:1-7,13-20,25-33`;
`robot_learning/scenario/environment.py:52-57,122-133`;
`robot_learning/scenario/policy_io.py:11-16`).

The source does not author body masses, densities, or inertial tensors. The
compiled MuJoCo model therefore supplies the geom-derived dynamic quantities,
but their exact values are not established by the source text. The authored
zero gravity and disabled environmental collisions remove gravitational and
floor-contact loads; damping, armature, inertia, and commanded torque remain
the material motion mechanisms.

### Episode mechanics and outcome

After every control interval, success distance is the three-dimensional
Euclidean distance from the end-effector site to the mocap target. A distance
at most 0.01 m increments the hold counter by one; any distance above 0.01 m
resets it to zero. Success terminates the episode only after 100 consecutive
in-tolerance control steps, which is 2 s at the current control interval.
Episodes truncate at 500 control steps, or 10 s. The official assessment is
one frozen policy over 200 independently sampled situations and requires at
least 196 successes (`contracts/scenario.md:9-32`;
`contracts/task_spec.py:6-11`;
`robot_learning/scenario/environment.py:134-168`).

### Observation and command interface

The policy receives 11 float values: two joint positions, two joint velocities,
the two-dimensional `end_effector - target` vector, and four wrapped angular
residuals to the two inverse-kinematic branches (elbow positive and negative).
The branch residuals are computed analytically from the known link lengths and
the target x/y position. The action is not transformed into a desired joint
position or velocity (`robot_learning/scenario/observations.py:11-49`;
`robot_learning/scenario/policy_io.py:11-16`).

The observation exposes the instantaneous mechanical state relevant to the
fixed target, but not the hold counter, time since entering the tolerance
region, episode time remaining, actuator force, or a contact signal. Since
joint positions determine the end-effector position for this fixed morphology,
the target-relative vector plus joint position is sufficient in principle to
recover target x/y; target velocity is always zero. The policy nevertheless
does not receive an explicit task-phase variable or a direct target polar
representation.

## Physical consequences

### Reachability is broad, but joint limits select configurations

For a target at radius `r`, inverse kinematics has the two nominal branches

`q2 = +/- acos((r^2 - 0.12^2 - 0.10^2)/(2*0.12*0.10))`,

with the corresponding shoulder angle determined by target angle and the
forearm direction. Across the official range, the elbow magnitudes are about
150 degrees at 0.06 m and 49.5 degrees at 0.20 m, before the target-angle
offset is applied. Thus the task is not fundamentally a reachability
challenge: every official radius is inside the ideal workspace, and the two
elbow branches provide alternatives. It is a constrained configuration
selection problem because the +/-170 degree joint limits can make one branch
less viable near some target angles.

**Decision relevance:** This could change whether early campaign interpretation
treats failures as geometric impossibility, branch/limit selection, or control
execution. It also determines whether target-angle coverage must be analyzed
separately from radius coverage.

**Assumptions and sources:** This follows the two-link geometry and assumes
the compiled joint ranges are the only kinematic limits; it uses
`contracts/robots/two_joint_arm.xml:12-20` and
`robot_learning/scenario/observations.py:18-35`.

**Discriminating evidence:** Solve both branches over a dense `(r,theta)`
grid, record joint-limit margins and Jacobian conditioning, and compare those
predictions with the first-entry and failure distributions by target angle.
Missing valid configurations or angle-localized failures would weaken the
simple “all official targets are equally reachable” interpretation.

### The physical objective is stabilization, not endpoint arrival

The 1 cm ball is an endpoint constraint, while the arm is controlled in joint
torque at only 50 Hz. Reaching the ball with nonzero joint velocity can be
followed by an immediate exit on the next interval. The Jacobian maps joint
velocity into endpoint velocity, so the controller must coordinate braking and
configuration choice as well as reduce position error. A successful steady
state at an arbitrary target is physically compatible with zero torque and
zero velocity because gravity is absent; during convergence, damping and
bounded torque determine whether motion can be arrested inside the ball.

**Decision relevance:** This distinguishes a policy that reaches quickly but
oscillates from one that reliably completes the hold. It could change whether
the first campaign comparison is judged primarily by minimum distance or by
settling time, endpoint velocity, overshoot, and uninterrupted dwell.

**Assumptions and sources:** The implication assumes the direct motor model
and no unmodeled contact; it follows from
`contracts/robots/two_joint_arm.xml:1-3,13-20,30-33` and
`robot_learning/scenario/environment.py:130-159`.

**Discriminating evidence:** Record endpoint velocity, joint velocity,
distance, torque saturation, and every tolerance exit through the reach,
convergence, and hold phases. A high success rate conditioned on early
settling would support a stabilization bottleneck; repeated exits at low
velocity would instead implicate geometry, numerical tolerance, or observation
effects.

### The initial state creates a large, angle-dependent maneuver

The arm always starts fully extended along +x. Initial distance ranges from
`|0.22-r|` to `0.22+r`; for official targets this is approximately 0.02 to
0.42 m. Targets behind the initial arm therefore require substantial
reorientation before convergence, while targets near the initial ray can
already be close at the outer-radius end. The reset does not randomize joint
state or velocity, so target geometry is the main source of episode-to-episode
physical variation.

**Decision relevance:** Early performance can be dominated by maneuver duration
and braking from the common reset rather than by steady-state holding. This
could change how a training result is stratified and whether a failure is
attributed to the 10 s horizon or to the final hold.

**Assumptions and sources:** This uses the explicit reset and target sampling
order in `robot_learning/scenario/environment.py:83-120` and the geometry in
`contracts/robots/two_joint_arm.xml:12-25`.

**Discriminating evidence:** Relate first-entry time, peak joint speed,
overshoot, and success to initial distance and target angle. If failures
cluster at large initial distance while holds are reliable once reached, the
finite-horizon maneuver is the limiting capability.

### Observation is nearly state-complete for mechanics but incomplete for task phase

For a static target, qpos, qvel, and the endpoint-target vector describe the
physical state needed for deterministic mechanics. The two IK residual pairs
also expose the alternative geometric goals. However, the observation omits
`held_steps`; two episodes can present the same physical observation while
requiring different remaining dwell durations. It also omits the global step
count and action history. The hold counter is nevertheless reset by a single
out-of-tolerance sample, so the missing task phase matters for interpreting
reward and progress even if “stay still” is locally sufficient.

**Decision relevance:** This could change whether feed-forward policies are
considered adequate, whether a measured learning problem is treated as
partial observability, and how hold-progress signals are interpreted. It also
limits causal conclusions drawn from reward without phase-aligned trajectories.

**Assumptions and sources:** This assumes no hidden stochastic state beyond
the target and MuJoCo state; it follows from
`robot_learning/scenario/observations.py:14-49` and
`robot_learning/scenario/environment.py:136-154`.

**Discriminating evidence:** Compare trajectories with the same or nearly the
same physical observation but different accumulated hold durations, and test
whether action choices or failure probabilities depend on unobserved phase
after conditioning on q, qdot, and distance.

### The current training distribution does not equal the official distribution

The official radius range is 0.06-0.20 m, whereas the current training
environment samples 0.14-0.20 m. The implementation therefore currently
exposes learning to only the outer half of the official radial interval,
although evaluation uses the official range. This is a distribution shift in
a physically meaningful variable: inner targets use more folded elbow
configurations and can have different shoulder-limit margins and transient
geometry.

**Decision relevance:** Any early training result cannot identify official
98% capability without separating the covered outer range from the omitted
inner range. This could change the first campaign decision about whether a
failure is a learning-distribution problem or a control/stability problem.

**Assumptions and sources:** This assumes the current training constructor is
the active recipe; the distinction is explicit in
`robot_learning/training/environment.py:3-19`, while the evaluation range is
set by `contracts/task_spec.py:6` and
`robot_learning/scenario/environment.py:171-178`.

**Discriminating evidence:** Evaluate identical policies with diagnostics
binned by radius and branch/limit margin. A sharp performance change below
0.14 m would support distribution shift as a first-order explanation; smooth
performance with failures concentrated by angle or velocity would weaken it.

### Exact dynamic authority and numerical margins are not established

The direct torque scale, timestep, damping, armature, and frame skip are
known, but exact link mass, composite inertia, actuator response, and the
resulting acceleration limits are not authored explicitly. Consequently,
“full action” is not yet a quantitative statement about angular acceleration.
The same 20 ms action interval can produce either well-damped convergence or
overshoot depending on the compiled inertia and configuration-dependent mass
matrix.

**Decision relevance:** This could change conclusions about whether a failure
is caused by policy learning, action temporal resolution, torque saturation,
or an inherently difficult transient. It determines which physical quantities
must be measured before comparing learning methods.

**Assumptions and sources:** The uncertainty follows from the absence of
inertial declarations in `contracts/robots/two_joint_arm.xml:9-20`; known
timing and actuator parameters are in `contracts/robots/two_joint_arm.xml:1-3,30-33`,
`contracts/task_spec.py:8`, and
`robot_learning/scenario/environment.py:55-57,125-133`.

**Discriminating evidence:** Inspect the compiled model and measure short
single-joint and coordinated torque responses across configurations, recording
q, qdot, qddot, control, and saturation. Agreement with a deterministic
compiled-model prediction would reduce this unknown; configuration-dependent
deviations would revise the simple fixed-authority model.

## Unknowns

1. **Compiled inertia and torque-to-motion map.** The geom-derived masses and
   inertias, effective actuator force, and configuration-dependent acceleration
   authority are unresolved from the authored source. This matters for the
   choice between learning difficulty and physical controllability as the
   first campaign explanation. It assumes MuJoCo's compiled model is the
   operative physics. Source: `two_joint_arm.xml:9-20,30-33`. Evidence:
   compiled-model introspection and impulse/step responses.

2. **Joint-limit feasibility and conditioning over the entire official
   distribution.** Analytic branches suggest broad feasibility, but the exact
   valid branch, joint-limit margin, Jacobian condition, and distance-to-limit
   distribution have not been enumerated. This matters for deciding whether
   target angle, target radius, or branch selection is the relevant task
   coordinate. Sources: `two_joint_arm.xml:13-18`,
   `observations.py:18-35`. Evidence: dense IK/Jacobian/limit analysis linked
   to episode outcomes.

3. **Closed-loop settling margin at 50 Hz.** It is unknown how much residual
   endpoint motion remains after the first entry and how often bounded torque
   can arrest it before a tolerance exit. This matters because the official
   criterion weights the complete hold, not first reach. Sources:
   `task_spec.py:8-11`, `environment.py:134-168`. Evidence: phase-aligned
   endpoint and joint time series with tolerance crossings.

4. **Practical sufficiency of the current observation for reliable holding.**
   The physical state appears observable for a fixed target, but the hold
   counter and time horizon are hidden. It is unknown whether that omission
   materially changes action selection or only changes reward visibility.
   Sources: `observations.py:14-49`, `environment.py:136-159`. Evidence:
   matched-state comparisons and failures conditioned on physical state and
   hold age.

5. **Failure allocation under the official distribution.** Before campaign
   evidence exists, the relative rates of reach timeout, overshoot, repeated
   tolerance exits, joint-limit approach, and inner-radius distribution shift
   are unknown. This is the central measurement needed to connect physical
   capability to the 98% episode objective. Sources:
   `scenario.md:17-32`, `evaluation.py:51-125`, and
   `training/environment.py:14-19`. Evidence: per-episode target geometry,
   first reach, minimum/final distance, maximum hold, interruptions, and
   termination cause.

## Scientifically meaningful quantities across complete behavior

For each episode, the physically informative trajectory is target `(r,theta)`;
joint position, velocity, acceleration, and control/torque; endpoint position,
velocity, and distance; Jacobian and branch/limit margins; and time-indexed
phase labels for reach, convergence, and hold. Useful episode summaries are
initial distance, first-entry time, minimum distance, peak speed and control,
settling/overshoot, longest uninterrupted in-tolerance run, number of
interruptions, final distance, and whether the 500-step horizon truncated the
episode. These quantities connect action to motion and motion to the only
authoritative outcome, complete uninterrupted hold. The existing research
evaluation already records target radius/angle, minimum and final distance,
first reach, maximum held steps, in-tolerance steps, and interruptions, but
not the full mechanical trajectory (`robot_learning/scenario/evaluation.py:51-125`).

## Decision-relevant synthesis

1. **Hold reliability is the primary physical bottleneck to distinguish from
   reach.** Direct torque control at 50 Hz must bring endpoint velocity and
   residual error low enough that 100 consecutive post-step distances remain
   within 1 cm. This matters because first reach is not success. It assumes
   the authored no-gravity, no-floor-contact model is operative. Sources:
   `contracts/task_spec.py:8-11`, `two_joint_arm.xml:1-3,30-33`,
   `environment.py:134-168`. Discriminating evidence is phase-aligned distance,
   endpoint/joint velocity, torque, overshoot, and tolerance interruptions.

2. **The official task is broadly reachable but has two branch choices and
   angle-dependent joint-limit margins.** This matters because an apparent
   learning failure may be branch selection or a target-angle-specific
   kinematic constraint rather than lack of workspace. It assumes the
   two-link geometry and authored +/-170 degree limits fully describe
   feasibility. Sources: `two_joint_arm.xml:12-20`,
   `observations.py:18-47`, `scenario.md:9-14`. Discriminating evidence is a
   dense branch feasibility/Jacobian analysis and outcome stratification by
   radius, angle, and branch margin.

3. **The reset and current training range create two separable sources of
   difficulty.** All episodes begin from the same fully extended state, while
   current training omits targets below 0.14 m even though official evaluation
   includes them down to 0.06 m. This matters for deciding whether early
   failures reflect finite-horizon maneuvering, inner-radius coverage, or
   stabilization. Sources: `environment.py:83-120`,
   `training/environment.py:14-19`, `task_spec.py:6`, `scenario.md:24-32`.
   Discriminating evidence is per-radius/per-angle first-entry, timeout, and
   hold-success measurement on the official range.

4. **Dynamic authority is known only parametrically, not quantitatively.**
   Torque bounds, damping, armature, timestep, and action hold are specified,
   but compiled mass and inertia are not. This matters for judging whether the
   observed policy can physically settle within the 10 s horizon and for
   interpreting action saturation. It assumes the XML's implicit MuJoCo
   compilation is the final dynamics. Sources: `two_joint_arm.xml:1-3,9-20,30-33`.
   Discriminating evidence is compiled-model inspection plus measured
   configuration-dependent torque responses.

5. **The observation is mechanically informative but hides task phase.** This
   matters for deciding whether failures are caused by insufficient physical
   information or by the policy's inability to know hold age and remaining
   horizon. It assumes the static-target dynamics are otherwise Markov in
   q, qdot, and target-relative position. Sources:
   `observations.py:14-49`, `environment.py:136-159`. Discriminating evidence
   is matched-physical-state analysis across different hold durations and
   interruption outcomes.
