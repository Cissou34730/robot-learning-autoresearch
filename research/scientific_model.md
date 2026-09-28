# Campaign-start scientific model: two-joint arm reach and hold

## Evidence boundary and objective

This model is constructed only from `research/scenario.md` and the
human-authored robot, simulator, scenario, and benchmark implementation. No
campaign policy, measurement, checkpoint, training result, or prior PI decision
is evidence here. The scientific objective is a learned policy that succeeds in
at least 196 of the 200 episodes of the official fixed panel, where success
means one uninterrupted 100-control-step hold inside the 1 cm distance
tolerance.

The object of study is one embodied-control chain:

`target geometry -> configuration selection -> powered motion -> tolerance entry
-> transient settling -> feedback stabilization -> uninterrupted hold`.

Approach, reaching, settling, and completion are not independent subtasks. A
policy can reach the target and still fail the episode if its residual velocity,
actuator saturation, configuration branch, or feedback timing causes one
out-of-tolerance sample during the hold.

## Established facts

The human-authored system defines a deterministic two-joint planar arm, a
stationary target distribution, an 11-value policy observation, bounded motor
commands, and an uninterrupted 100-control-step success condition.

### Robot and simulator

- The robot is a planar two-revolute-joint arm in the x-y plane. The shoulder
  and elbow hinge axes are both the world z axis.
- The upper arm length is 0.12 m and the forearm length is 0.10 m. The
  end-effector site is at the forearm endpoint, so the nominal maximum
  kinematic reach is 0.22 m.
- Both joints have a nominal range of -170 to +170 degrees, damping 0.5, and
  armature 0.01. There are no joint or link contacts relevant to the task:
  the visible plane and target sphere have collision disabled.
- MuJoCo uses zero gravity and a physics timestep of 0.002 s. The model has two
  motors, one per joint, with control range [-1, 1] and gear 5.
- The reset state is q = [0, 0] with zero joint velocity. The target is a
  non-actuated mocap body in the arm plane at the current end-effector height.
  Physics is otherwise deterministic for a fixed target and action sequence.

### Target, interaction, and success contract

- The official target radius is sampled uniformly between 0.06 and 0.20 m and
  its angle uniformly over [-pi, pi]. The implementation samples radius and
  angle independently, then constructs the Cartesian target.
- An environment action is a two-element float vector in [-1, 1]. The action is
  held constant for 10 MuJoCo steps, giving a 0.020 s control interval and a
  50 Hz policy-to-plant interaction.
- A control step is inside the task tolerance when the three-dimensional
  end-effector-to-target distance is at most 0.01 m. Because the target is
  placed at the end-effector height, this is effectively a planar 1 cm ball.
- The hold counter increments only on consecutive in-tolerance control
  observations and resets to zero on any outside observation. The required
  duration is 2.0 s, implemented as 100 consecutive control steps. An episode
  truncates at 500 control steps, or 10 s, if it has not terminated by
  completing the hold.
- The protected final benchmark evaluates one frozen policy on 200 seeded
  episodes. Each episode contributes one binary outcome; the official target is
  at least 196 successes (98%). The task-reference panel is a separate
  development panel and cannot establish the official result.

### Observation and policy interface

- The policy observation has 11 float32 values: two joint positions, two joint
  velocities, the three-dimensional vector from target to end effector, and
  four wrapped angular residuals to the two analytic inverse-kinematics
  configurations (open and folded elbow branches).
- The observation includes no target velocity because the target is stationary.
  Given joint positions and the relative target vector, the target position is
  reconstructible from the forward kinematics, so the task state needed for
  control is observable rather than hidden behind a camera.
- The policy action is currently mapped directly to the physical motor command.
  Evaluation uses the policy's saved observation/action runtime and, when
  present, the saved observation-normalization statistics; it does not silently
  substitute current source code for a saved policy runtime.

### Current learning and reward surface

- The current training constructor samples only target radii 0.14--0.20 m,
  whereas the protected official distribution includes 0.06--0.20 m. This is
  a replaceable training choice, not a relaxation of the official contract.
- The current trainer uses a feed-forward PPO MLP and observation
  normalization. This is a current method, not a physical or benchmark
  invariant.
- The current reward combines distance progress, an exponential closeness
  potential, incremental hold progress, a small action cost, a one-time
  outside-band penalty after a hold streak is broken, and a completion bonus.
  The benchmark ignores reward and judges only the uninterrupted hold event.

## Physical consequences

The system is a coupled torque-controlled reaching and stabilization problem:
target geometry determines feasible configurations, actuation determines
approach and settling, and the 1 cm boundary makes any transient excursion
during the 2-second hold an episode failure.

### Configuration geometry

For joint angles q1 (shoulder) and q2 (elbow), the planar endpoint is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2).
```

The unconstrained reachable radial annulus is 0.02--0.22 m. The official
0.06--0.20 m interval lies inside that annulus, but joint limits still make
configuration feasibility and margin an angle-dependent question. In the
interior, a target generally has two inverse-kinematics elbow branches. A
policy must either select a branch consistently or learn a transition-safe
representation; branch ambiguity is a control choice, not target uncertainty.
Near the radial extremes, the branches approach geometrically sensitive
postures: small Cartesian errors can require materially different joint
corrections, and the useful margin to a joint limit can shrink.

The reset posture is extended along positive x. Its initial distance to a
random target is therefore strongly dependent on target angle and radius.
Targets opposite the reset direction require a large initial reorientation,
while outer targets near the reset direction require little translation. This
creates an approach-duration and momentum distribution even though every
episode starts from the same joint state.

### Actuation and settling

The action controls motor effort rather than directly setting joint position.
The gear converts the normalized command into motor torque, while armature and
damping shape acceleration and decay. Holding a command for 20 ms creates a
sample-and-hold controller: a policy can only correct once per control
interval, and the plant evolves for ten physics integrations between
corrections. Saturation, residual velocity, and the phase lag induced by this
interval are therefore central to tolerance entry.

There is no gravity or contact disturbance to reject. The main disturbances
experienced by the closed loop are self-generated: action discretization,
inertia, damping, overshoot, and errors in the learned mapping from observed
state to torque. A successful policy should approach with enough speed to fit
within 500 control steps, then deliberately reduce kinetic energy before or
while entering the tolerance ball. The final controller must stabilize a
small Cartesian region, not merely stop near a nominal inverse-kinematics
solution.

### Observation sufficiency and useful decomposition

The observation is richer than a bare Cartesian error. Joint positions and
velocities expose the mechanical state; the relative target vector exposes the
task error; and the two inverse-kinematics residual pairs provide explicit
branch-directed features. Since the target is static and the simulator has no
unobserved external disturbance, this should be sufficient for a stationary
feedback policy in principle. It does not guarantee that a finite MLP,
normalizer, or PPO update will use the information with adequate precision.

For diagnosis, the episode should be decomposed into:

1. approach: time and action needed to reduce the initial error;
2. first tolerance entry: whether the endpoint crosses the 1 cm boundary;
3. settling: minimum distance, velocity, saturation, and boundary crossings
   around the first entry;
4. sustained completion: longest consecutive in-tolerance streak, interruptions,
   and the distance margin during the 100-step hold.

The binary episode outcome remains authoritative. These phases explain failure
mechanisms; they must not be pooled into a substitute success score.

### Learning-objective alignment

The current shaped reward supplies denser approach and closeness gradients than
the sparse terminal event, but its potential-style hold term pays incremental
progress toward the hold and does not forfeit the previously accumulated hold
capital when the streak exits. It can therefore make tolerance entry look
successful during training even when the benchmark still fails on continuity.
The small action cost may also oppose the corrective effort needed near the
boundary. Reward changes should be judged by the official hold outcome and by
phase-resolved evidence, not by episode return.

The current training-radius gap is consequential: a policy optimized only on
0.14--0.20 m does not receive direct experience of the 0.06--0.14 m part of
the official distribution. Inner targets require different elbow geometry and
often different settling behavior. Any claim about the official objective must
therefore test both radial coverage and full angular coverage rather than
extrapolate from the current training range.

### Statistical meaning of the official panel

The fixed 200-episode panel is the authoritative decision instrument and has a
discrete pass threshold of 196 successes. It is also a finite sample from the
specified target distribution, so a panel pass is strong evidence about the
frozen policy on that panel, not a noiseless proof of its population success
probability. Independent, non-overlapping development panels and stratified
failure diagnostics are needed to distinguish genuine robustness from
favorable finite-panel placement while keeping the official verdict untouched.

## Unknowns

| Unknown | Why it can change the route to 98% | Discriminating evidence |
| --- | --- | --- |
| The closed-loop settling margin at 1 cm under the 50 Hz action interface | A policy may reach the target but cross the boundary during deceleration or during the hold. | Record joint velocities, torque saturation, distance margin, first-entry step, and longest hold streak across radius-angle strata. |
| Whether both analytic IK branches remain comfortably within joint limits over the full official domain | A branch that is valid at one radius or angle may be fragile near a limit, forcing a consistent branch-selection strategy. | Compute and measure branch joint-limit margins over the official domain, then compare failures by selected branch and target geometry. |
| The minimum approach time and control authority needed for inner versus outer targets | The 500-step horizon permits settling only if approach and damping are jointly managed. | Use phase timing and action histories, stratified by radius and initial angular displacement. |
| Whether the current observation normalization preserves centimeter-scale error and velocity distinctions | Clipping or poorly estimated running statistics could erase the precision needed for boundary stabilization. | Inspect saved normalization ranges and compare normalized feature resolution with raw distance and velocity near the tolerance boundary. |
| Whether the current reward induces continuous completion rather than repeated near-success | The reward is not identical to the binary uninterrupted-hold objective and only weakly penalizes a broken streak. | Compare reward components and return with success, interruption count, longest streak, and boundary margin; alter shaping only when the causal mismatch is demonstrated. |
| How much PPO and the current MLP architecture contribute to variance or representation failure | The physical task is observable in principle, but optimization may fail to learn branch selection and low-velocity stabilization. | Repeat controlled seeds and compare learning curves using official-distribution coverage while holding mechanics and evaluation fixed. |
| The worst-case target geometry within the full-angle, 6--20 cm distribution | Aggregate success can conceal a narrow angular or radial failure set that prevents 196/200 successes. | Report success and hold diagnostics by radius bins, angle bins, initial error, and inferred IK branch. |
| The relationship between development-panel success and population success | A fixed 200-episode result can be sensitive to finite-panel composition even when the benchmark contract is satisfied. | Use independent, non-overlapping seeded panels for development and reserve the protected panel for the official decision. |
| Whether numerical edge cases near exactly 1 cm alter practical robustness | The contract uses an inclusive distance comparison, so a policy with negligible margin may be brittle to tiny state or action changes. | Report signed distance margin and require a positive robustness margin in development, while retaining the inclusive official predicate. |

## Scientific direction

The first causal priority is to cover the official target distribution and make
the hold constraint measurable as a control-stability problem. Development
evidence should preserve per-episode outcomes and phase diagnostics, with
special attention to inner-radius targets, large initial angular displacement,
first-entry overshoot, and hold interruptions. Training changes should be
selected for their effect on uninterrupted episode success and its failure
strata, not for return alone. The protected final benchmark, run only through
its official lifecycle, is the sole source of the terminal 98% decision.
