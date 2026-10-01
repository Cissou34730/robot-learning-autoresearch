# Scientific model of the robot and task

This is the pre-campaign model of the simulated two-joint arm. It separates
what is specified by the human-authored implementation from physical
consequences inferred from that specification. It contains no learned-policy or
campaign evidence.

## Established facts

The robot is a serial planar 2R arm. A fixed base supports a shoulder hinge,
followed by an upper arm of length 0.12 m and an elbow hinge, followed by a
forearm of length 0.10 m. Both hinge axes are the world z axis, so the
configuration is \(q=(q_1,q_2)\), where \(q_1\) is the shoulder angle and
\(q_2\) is the elbow angle relative to the upper arm. The arm plane is at
\(z=0.02\) m. The end-effector position is therefore

\[
p(q) = (0.12\cos q_1 + 0.10\cos(q_1+q_2),\;
         0.12\sin q_1 + 0.10\sin(q_1+q_2),\;0.02).
\]

Each joint is limited to -170 to 170 degrees. The unconstrained radial
workspace is the annulus from \(|0.12-0.10|=0.02\) m to
\(0.12+0.10=0.22\) m. The target is a non-colliding mocap sphere, not a
physical object to push or grasp.

The model has no gravity. The joints have damping 0.5 and armature inertia
0.01 in their respective joint definitions. Each joint is driven by a motor
with gear 5 and control range [-1, 1]. The policy action is passed through
unchanged to the two physical controls and is clipped to that range. Thus the
command is a bounded motor command, not a desired joint position or velocity;
under the standard motor convention its generalized actuator effort is
approximately \(5u_i\), subject to the compiled model dynamics.

MuJoCo integrates at a 0.002 s timestep. The official environment holds each
action for 10 integration steps, giving a 0.020 s control interval and a
50 Hz decision rate. The target is fixed during an episode. At reset, joint
positions and velocities are zero, the model is forwarded, and a target is
sampled with radius uniformly in [0.06, 0.20] m and angle uniformly over
\([-\pi,\pi]\). Its z coordinate is set to the end-effector plane, so the
three-dimensional distance is genuinely planar.

The official controller receives an 11-element observation:

* the two joint positions and two joint velocities;
* the three-dimensional end-effector-to-target displacement;
* four wrapped angular residuals to the two inverse-kinematic branches,
  consisting of an elbow-open and an elbow-folded solution.

The observation is recomputed after each 20 ms action interval. The target
itself is not separately exposed, but joint configuration determines the
end-effector position, so the target position is recoverable from the
relative displacement. The z displacement is structurally zero in this task.

Success uses a 0.01 m end-effector distance threshold. A post-action distance
must be within that threshold for 100 consecutive control steps, which is two
seconds at the official control rate. Any outside sample resets the hold
streak. An episode has at most 500 control steps (10 seconds), and only
completion of the full streak counts as success; truncation does not. The
official panel contains 200 independently seeded episodes, and the campaign
threshold is at least 196 successes.

## Physical consequences

The target radial interval lies inside the arm's unconstrained workspace:
0.06--0.20 m is separated from both the 0.02 m inner boundary and the 0.22 m
maximum extension. The arm therefore has radial reach for every official
target before considering joint limits. For a target with polar angle
\(\phi\) and radius \(r\), inverse kinematics satisfies

\[
\cos q_2 =
\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)}.
\]

Except at a kinematic singularity, this produces two elbow configurations,
\(q_2=+\arccos(\cdot)\) and \(q_2=-\arccos(\cdot)\), with corresponding
shoulder angles. The official radial interval gives approximately 150 degrees
of elbow magnitude at 0.06 m and 49 degrees at 0.20 m, so neither endpoint is
an exact straight-arm singularity. The two branches are physically distinct
joint configurations for the same target. Shoulder limits can make one branch
less convenient near angular wrap boundaries, so a controller must select and
stabilize a feasible branch rather than treat the target as having one unique
joint answer.

The local position Jacobian has determinant proportional to
\(0.12(0.10)\sin q_2\). It is nonzero throughout the stated radial range, but
its magnitude changes with radius. Consequently, the same Cartesian error
does not require the same joint correction everywhere: near the inner part of
the distribution, elbow motion and shoulder motion are coupled differently
than near maximum reach. The observation's explicit branch residuals expose
useful geometric alternatives, while the joint state and relative target
vector already provide the information needed to choose between them.

The physical transition is a second-order, coupled joint system of the form
\[
M(q)\ddot q + C(q,\dot q)\dot q + B\dot q \simeq \tau,
\]
with no gravity or contact force. The inertia matrix changes with elbow
configuration, and the two joints are dynamically coupled through the serial
geometry. Damping dissipates motion, but it does not make a commanded action a
position servo. A large or sustained command accelerates the arm; reversing
the command is needed to brake unwanted momentum. The zero-order-held action
and bounded effort impose a finite reach-and-settle time, while the 20 ms
sampling interval means that feedback corrects only once per control interval.

The task is therefore not only point reaching. A successful trajectory must
choose a reachable configuration, move there without exhausting the 10-second
horizon, reduce residual joint and end-effector velocity, and maintain the
end-effector inside a small disk for 100 successive checks. Because gravity,
contact, and target forces are absent, a stationary configuration requires no
support torque in the ideal model; the difficult part of the hold is removing
approach velocity and suppressing subsequent oscillation. A trajectory that
briefly enters the disk and exits it has made no progress toward the official
outcome, regardless of its closest approach.

The official implementation samples the hold condition after each group of
10 physics steps. Thus “uninterrupted” means 100 consecutive sampled
post-action distances within tolerance; excursions between those checks are
not separately recorded by the success logic. The relevant control-to-outcome
chain is

\[
\text{observation} \rightarrow \text{bounded motor command}
\rightarrow \text{10 physics steps} \rightarrow p(q)
\rightarrow \text{distance and hold streak}.
\]

This creates distinct physical failure classes: an unreachable or
joint-limit-incompatible branch choice; wrong-direction or poorly coordinated
joint motion; actuator saturation or insufficient time to travel; overshoot
caused by residual momentum; and a near-target oscillation or drift that breaks
the hold streak. The current training constructor samples only radii
0.14--0.20 m, whereas the official task includes 0.06--0.20 m. A policy
trained only on that constructor would consequently have no direct training
coverage of the inner radial portion, even though the official mechanics and
observation remain the same.

## Unknowns

The XML gives arm dimensions, damping, armature, motor gear, and timing, but
does not state link masses and inertias explicitly. Their exact compiled
values, the resulting configuration-dependent inertia coupling, and the
effective acceleration and braking margins are therefore not established by
the source dimensions alone. The practical motor authority also depends on
those compiled quantities and on the detailed MuJoCo actuator and integrator
behavior.

Before evidence exists, it is unknown how much of the 10-second horizon is
required for each radius and angle, where the worst settling cases occur, and
how much residual speed can be tolerated while remaining within the 1 cm
disk. It is also unknown whether one IK branch is dynamically superior across
the distribution, whether switching branches during an episode is ever useful,
and how close any successful trajectory must operate to the action bounds.

The observation is physically sufficient for the deterministic task model, but
the useful closed-loop observables have not yet been characterized. In
particular, the campaign has no prior measurements of target-relative radial
and tangential error, end-effector speed, joint speed, acceleration, actuator
saturation, energy or work, settling time, hold exits, or the longest
consecutive in-tolerance interval. These quantities are needed to distinguish
geometric errors from dynamic and stabilization failures without confusing a
near miss with an achieved hold.

Finally, no pre-campaign fact establishes that a learned policy can maintain
the complete hold over the full official distribution, or that training
success on the narrower current training range transfers to the inner
targets. That is an empirical question governed by the coupled kinematic,
dynamic, control, and observation mechanisms above; it cannot be inferred from
the nominal reachability calculation.
