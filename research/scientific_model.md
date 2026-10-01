# Scientific model of the two-joint reach-and-hold system

The system is a planar two-link arm whose two revolute joints rotate about the
vertical axis. It is not a gravity-loaded manipulation problem: the target is a
fixed point in the arm's plane, there are no contact interactions, and the
policy directly commands bounded motor inputs. The scientific difficulty is
therefore the coupled transition from a dynamically moving arm to a sufficiently
quiet configuration, followed by maintaining that configuration for the complete
sampled hold interval across target geometry.

## Established facts

These are facts specified by `research/scenario.md` or by the human-authored
robot and benchmark implementation.

- The upper arm is 0.12 m and the forearm is 0.10 m. The shoulder and elbow are
  hinge joints about the z axis, with independent ranges of -170 to 170 degrees.
  At zero joint angles the links point along +x. The end-effector site is at the
  forearm tip, and the arm operates at z = 0.02 m.
- The XML sets zero gravity, a MuJoCo integration timestep of 0.002 s, joint
  damping of 0.5, and joint armature of 0.01 for both joints. Each joint has a
  motor with control range [-1, 1] and gear 5. The policy action is passed
  through unchanged and clipped to this range by the environment.
- The official controller acts every 10 physics steps. Thus one policy step is
  0.020 s (50 Hz), and the two-second hold is 100 consecutive control steps.
  Episodes last at most 500 control steps. Success is evaluated from the
  end-effector site's Euclidean distance to the target, which must be at most
  0.01 m at every one of those 100 post-step checks.
- At reset, both joint positions and velocities are zero. The target is then
  sampled with angle uniform over the full circle and radius uniform from 0.06
  m to 0.20 m, and is placed at the end-effector's z coordinate. The target is
  fixed during the episode. The target and arm geoms do not create a physical
  contact task; the target is a mocap body and the distance test is the task
  interaction.
- The policy observes 11 values: the two joint positions, two joint velocities,
  the three-dimensional end-effector-to-target vector, and four wrapped angular
  residuals to the two inverse-kinematic configurations (open and folded).
  There is no hidden actuator state in the specified motor model and no
  observation noise or delay in the implementation.

## Physical consequences

### Kinematics and reachable geometry

Writing the shoulder angle as \(q_1\) and the relative elbow angle as \(q_2\),
the end-effector position in the arm plane is

\[
 p(q) =
 \begin{bmatrix}
 0.12\cos q_1 + 0.10\cos(q_1+q_2)\\
 0.12\sin q_1 + 0.10\sin(q_1+q_2)
 \end{bmatrix}.
\]

The unconstrained position workspace is the annulus from 0.02 m to 0.22 m.
The elbow limits make the innermost exact radius about 0.0276 m, while the
official target range stays well inside the outer limit and outside this
inner restriction. For a target radius \(r\), the two nominal elbow solutions
are

\[
 q_2 = \mathord{+/-}\arccos
 \left(\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)}\right).
\]

Across the official radius range, the magnitude of this angle is approximately
49 to 151 degrees, so both elbow branches satisfy the elbow limit. The
corresponding shoulder angle is the target bearing minus (or plus) the
triangle's internal offset. The shoulder limit removes one branch in some
angular sectors near the +/-170 degree boundary, but the two branches together
cover the official target circle: each official target has at least one
position-level solution. Consequently, failure is not explained by an
unreachable official target, although it can still be caused by selecting a
poor branch or by dynamic inability to settle there.

The planar Jacobian has determinant
\(0.12(0.10)\sin q_2\). It is singular at a fully extended or fully folded
configuration. The reset state \(q_1=q_2=0\) is the outer-workspace singularity:
the initial instantaneous motion has only one first-order Cartesian direction.
To move tangentially toward a target away from +x, the arm must first create
elbow separation, so the initial transient is not equivalent to a
well-conditioned Cartesian tracking problem. Near the outer target radii,
targets also require relatively small elbow angles and remain comparatively
close to this singular geometry.

### Actuation and dynamics

The action is a pair of bounded generalized motor commands, not a desired
joint position or velocity. A MuJoCo motor with gear 5 therefore supplies a
gear-scaled joint force (nominally up to 5 in the model's force units) while
the arm's motion emerges from inertia, damping, and the ten internal
integration steps for which the command is held. The damping opposes velocity
and the armature increases the effective joint inertia. With gravity disabled,
there is no gravitational preference for any configuration; a stationary hold
requires only the control needed to counter residual motion and numerical or
model forces, rather than static gravity torque.

The XML does not define explicit actuator dynamics, joint friction, contacts, or
external disturbances. The disabled plane and non-contacting target mean that
collision avoidance and force regulation are not capabilities required by this
task. The important control problem is consequently acceleration and
deceleration under bounded torque, with the action held open-loop between
policy decisions. A policy can reach the tolerance briefly while still
carrying enough velocity to leave it. The hold requirement couples reaching to
velocity regulation, branch choice, and local stabilization rather than merely
requiring a small final position error.

The reset state is always the same physical arm state; only the target changes.
The initial end effector is at (0.22, 0, 0.02), so the initial error is the
vector from this point to the sampled target. The initial distance depends on
both target radius and bearing, and the initial configuration is dynamically
special because of the extended-arm singularity. A successful policy must
therefore solve a family of transients from one common state, not arbitrary
state-space recovery.

### Observation, control, and outcome

The observation contains the full joint position and velocity state relevant to
the two-joint, memoryless motor dynamics. It also contains the Cartesian error.
Because the current end-effector position is known from the joint positions,
that error identifies the target position in the arm plane; the target is not
hidden merely because its absolute coordinates are not a separate observation
field. The four IK residuals make both nominal branches explicit and expose
which branch is nearer, but they do not themselves command a branch.

The resulting closed loop is: observation of \(q,\dot q\), target error, and
branch residuals; bounded torque action; ten physics updates; sampled distance;
and either continuation, hold-streak reset, or success. Leaving the 1 cm ball
resets the uninterrupted streak to zero. The official verdict is based on
streak length, not on average distance, reward, or a final pose. In the
implementation, continuity is checked at the 50 Hz control boundaries; an
excursion entirely between two checks is not separately visible to the
success counter, while any detected boundary violation breaks the hold.

The physically meaningful quantities over a complete behavior are target
radius and bearing; both joint trajectories and velocities; end-effector
position error decomposed into radial and tangential components; distance to
each IK branch; the Jacobian conditioning or determinant; applied torque and
its changes; time to first enter tolerance; velocity and motion at entry; the
longest consecutive in-tolerance streak; hold interruptions; and the distance
margin \(0.01 - \|p-p_{\mathrm{target}}\|\) throughout the hold. If the compiled
inertial parameters are known, actuator work, kinetic energy, and damping
dissipation additionally distinguish efficient stabilization from merely
successful stabilization.

## Unknowns

These quantities are not established by the pre-campaign source and should not
be treated as known physical evidence.

- The XML leaves body masses, geom densities, and explicit inertial tensors
  unspecified. The exact compiled link masses, centers of mass, joint
  inertias, and hence acceleration and stopping authority depend on MuJoCo's
  compilation defaults. Exact motor torque in the compiled model, including
  the effect of the gear convention, should likewise be treated as a quantity
  to establish rather than inferred from the control range alone.
- The resulting transient time constants, peak velocities, overshoot, and
  attainable closed-loop bandwidth are unknown before observing trajectories.
  Damping and armature constrain them qualitatively but do not determine them
  without the compiled inertial values and the discrete integration behavior.
- It is not known before evidence whether a single policy will consistently
  select and stabilize both IK branches, whether it will learn a branch
  preference that remains feasible near shoulder limits, or whether the
  singular reset geometry produces a distinct failure class for targets by
  bearing and radius.
- The observation is physically sufficient for a deterministic Markov policy
  under the stated model, but its practical sufficiency for learning is
  unresolved: the policy must infer appropriate torque timing and braking from
  sampled velocities and a target-relative representation while actions persist
  for 20 ms.
- No pre-campaign claim is justified about success probability, robustness of
  the 1 cm margin, or whether failures will be dominated by reachability,
  branch selection, transient overshoot, or hold drift. Those are empirical
  properties of the learned closed loop, not consequences that can be asserted
  from the task definition alone.
