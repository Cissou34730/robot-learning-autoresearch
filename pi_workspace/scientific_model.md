# Scientific model of the two-joint arm reach-and-hold task

## System boundary and task

The robot is a planar, two-degree-of-freedom revolute arm. The official target
has polar radius uniformly distributed from 0.06 m to 0.20 m and angle uniformly
distributed over the full circle. It is placed in the arm's horizontal plane.
Success is not merely reaching: after entering the 0.01 m distance tolerance,
the end effector must remain in tolerance for 2 seconds, represented by 100
consecutive control steps. An episode has at most 500 control steps (10 seconds
at the current control rate), and the campaign target is at least 196 successes
in the fixed 200-episode official assessment.

## Established facts

- The shoulder and elbow are serial hinges about the vertical axis. The upper
  arm and forearm lengths are 0.12 m and 0.10 m, so with joint angles
  \(q=(q_1,q_2)\), the end-effector position relative to the base is
  \[
  x=L_1\cos q_1+L_2\cos(q_1+q_2),\qquad
  y=L_1\sin q_1+L_2\sin(q_1+q_2).
  \]
  The elbow angle is relative to the upper arm.
- Both joints are limited to -170° through +170°. Reset sets both joint
  positions and velocities to zero. The arm therefore starts fully extended at
  approximately \((0.22,0,0.02)\) m, while the target is sampled after this
  state is established.
- Gravity is disabled. The links have no configured contacts with the plane or
  one another, and the target is a non-colliding mocap body. The task therefore
  contains no contact transition, obstacle avoidance, or external disturbance.
- MuJoCo advances at 0.002 s per physics step. Each policy action is clipped to
  [-1,1] and held for 10 physics steps, giving a 0.020 s, 50 Hz zero-order-held
  control loop. Each action directly sets one motor control input.
- Each motor has gear 5, giving nominal joint torque command in the range
  [-5,5] in the simulator's torque units. Each joint has damping 0.5 and
  armature 0.01. With the current MuJoCo defaults, the loaded upper-arm and
  forearm masses are approximately 0.099 kg and 0.052 kg; their planar body
  inertias about their local centers are approximately \(1.08\times10^{-5}\)
  and \(3.67\times10^{-6}\) kg m². The effective inertia at a joint varies with
  configuration because the links are coupled.
- The observation has 11 values: the two joint positions, two joint velocities,
  the three-dimensional end-effector-to-target displacement, and wrapped
  position errors to the elbow-open and elbow-folded inverse-kinematic
  solutions. The target is stationary, and no target velocity, action history,
  hold timer, or explicit episode time is observed.
- The current training constructor samples only radii 0.14--0.20 m, whereas
  the official distribution includes 0.06--0.20 m. Evaluation uses the official
  radius range and the same physical task mechanics.

## Physical consequences

The unconstrained two-link workspace is the annulus between
\(\lvert L_1-L_2\rvert=0.02\) m and \(L_1+L_2=0.22\) m. The official annulus
lies inside it. Inverse kinematics gives two nominal configurations for most
targets:
\[
 q_2=\mathord{\pm}\arccos\left(
 \frac{r^2-L_1^2-L_2^2}{2L_1L_2}\right),
\]
with the corresponding shoulder angle chosen to point the two-link sum at the
target. At the smallest official radius the elbow magnitude is about 150.3°,
still below the joint limit. Checking both branches over the official radial
and angular domain finds at least one branch within both joint limits for every
sampled target. Thus there is no nominal reachability failure in the task
geometry, although the policy must select and regulate one of multiple
configurations.

The reset configuration is the outer workspace boundary, so the first motion
must generally retract, rotate, or both. The arm has no gravitational load to
hold against, but damping is not a positional restoring force: at a displaced
zero-velocity state it cannot return the end effector to the target. The policy
must generate positional correction, then remove enough momentum that the
end-effector error remains below 1 cm. At exactly the desired configuration
with zero velocity, zero command is physically sufficient; near it, small
torque errors or residual velocity can repeatedly cross the tolerance boundary.

The Jacobian maps joint motion into radial and tangential end-effector motion.
It becomes singular at fully extended or fully folded configurations, so
similar Cartesian corrections can require very different joint motions and
torques. Official targets approach, but do not reach, the fully extended
0.22 m boundary; the initial state is exactly at that boundary. Near singular
geometries, branch choice, action saturation, and the 20 ms action hold can
therefore affect stopping distance and settling time even when a static
inverse-kinematic solution exists.

The physical state is Markovian in \((q,\dot q,\text{target})\), with a fixed
target during an episode and deterministic simulator dynamics. The observation
contains enough geometry to reconstruct the target relationship: joint
positions determine the end-effector location from the known morphology, and
the displacement supplies the target offset. The two derived branch errors
make the alternative solutions explicit. However, the policy must infer
stability and future boundary crossing from instantaneous position and
velocity; it receives no direct measurement of hold progress or of motion
between observations.

Operationally, the environment evaluates distance after each 10-substep
control interval. A single sampled distance outside tolerance resets the held
counter to zero, so any interruption destroys the current uninterrupted hold.
The physical requirement is a two-second stable Cartesian neighborhood, while
the observable success test is its 50 Hz boundary-sampled implementation.
Reaching, braking, convergence, and holding are consequently one coupled
problem: a fast reach with residual kinetic energy can be worse than a slower
approach, and a low-error trajectory is still a failure if it intermittently
exits the tolerance.

## Unknowns

- The effective configuration-dependent inertia matrix, closed-loop settling
  time, overshoot, and maximum safely correctable velocity are not summarized
  by the XML constants. Their values under learned actions, especially near the
  outer-workspace singularity, are unresolved before campaign evidence.
- It is unknown how much of the 1 cm tolerance is consumed by 20 ms action
  quantization, simulator integration, and policy-induced oscillation during the
  2-second hold. The environment does not expose continuous substep exits.
- The two inverse-kinematic branches are both geometrically usable, but their
  relative dynamic difficulty, basin of attraction from the zero reset, and
  sensitivity to joint-limit wrapping are unknown.
- The observation is physically informative but does not directly encode target
  polar coordinates, absolute end-effector coordinates, elapsed time, or hold
  state. Whether a feed-forward policy can robustly infer the required
  stabilizing regime from these derived quantities is an empirical question.
- Before evidence exists, the distribution of failures across target radius,
  angle, approach direction, first-entry speed, and hold interruption count is
  unknown. Reward or training metrics cannot be treated as evidence of the
  complete success criterion until they are tied to uninterrupted episode
  outcomes.

## Scientifically meaningful quantities

For the complete behavior, the primary physical measurements are target radius
and angle; joint positions, velocities, and commanded torques; end-effector
position error and its radial/tangential components; speed and acceleration;
time to first enter tolerance; first-entry velocity; time continuously held;
number and duration of tolerance interruptions; minimum and final distance; and
torque saturation or action changes. These quantities distinguish geometric
reachability, approach control, braking, convergence, and genuine sustained
stability rather than collapsing them into a single reward value.
