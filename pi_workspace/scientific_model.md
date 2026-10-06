# Scientific model of the two-joint arm reach-and-hold task

This model separates implementation facts from physical implications and
quantities that cannot be determined without policy behavior. It is based on
the human-authored task and robot definitions; no campaign evidence exists yet.

## Established facts

### Task, timing, and outcome

The official task samples a stationary target at radius 0.06--0.20 m from the
base over the full angular range. The end effector must stay continuously
within 0.01 m for 2 s. The official evaluator allows at most 500 control
steps, and success is a binary episode outcome; a partial approach or an
interrupted hold is failure. These requirements are authoritative rather than
reward definitions ([contracts/scenario.md:9-31],
[contracts/task_spec.py:6-11]).

The simulator integrates at 0.002 s per MuJoCo step. The environment applies
one action for 10 such steps, so one policy control step is 0.020 s and the
required hold is 100 consecutive control steps. The episode can therefore
last 10 s before truncation if it never completes
([contracts/robots/two_joint_arm.xml:1-3],
[robot_learning/scenario/environment.py:55-58,122-168]).

### Morphology and kinematics

The robot is a planar serial arm with two revolute degrees of freedom. The
shoulder and elbow axes are both the world z axis. The upper arm length is
0.12 m and the forearm length is 0.10 m. With joint coordinates
`q = (q1, q2)`, the end-effector position is

    p(q) = (0.12 cos(q1) + 0.10 cos(q1+q2),
            0.12 sin(q1) + 0.10 sin(q1+q2),
            0.02).

Both joints are limited to -170 to +170 degrees. The arm is initialized at
`q=(0,0)`, so it is fully extended along +x and the end effector starts at
`(0.22, 0, 0.02)` with zero velocity
([contracts/robots/two_joint_arm.xml:9-20],
[robot_learning/scenario/environment.py:102-120]).

Ignoring the joint limits, the planar reachable radii are 0.02--0.22 m.
The 170-degree limits reduce the inner radius slightly to about 0.019 m, so
the official 0.06--0.20 m target band is geometrically reachable. The target
is put at the end-effector z height, so the 3-D distance test is equivalent to
the planar distance for this model
([robot_learning/scenario/environment.py:83-97]).

### Actuation and dynamics

The two actions are direct normalized motor commands in `[-1,1]`. The policy
I/O leaves them unchanged and the environment clips them before applying them.
Each MuJoCo motor has gear 5, giving nominal joint torque in the range
`[-5,+5]` N m, with no action smoothing or actuator state
([robot_learning/scenario/policy_io.py:11-16],
[robot_learning/scenario/environment.py:122-133],
[contracts/robots/two_joint_arm.xml:30-33]).

Gravity is zero. Each joint has damping 0.5 and armature 0.01; the model
therefore has viscous velocity resistance but no gravitational restoring
torque. The current native MuJoCo compilation reports upper-arm and forearm
masses of approximately 0.09896 kg and 0.05248 kg, respectively, with
configuration-dependent coupled inertia. The XML does not explicitly specify
these densities or a separate controller, so the compiled values and the
MuJoCo integrator remain part of the simulator definition rather than
independently identified physical parameters
([contracts/robots/two_joint_arm.xml:1-3,12-20],
compiled `MjModel` from that XML under the locked MuJoCo runtime).

The plane and target geometry are non-colliding (`contype=0`), and the target
is a mocap body rather than a body the arm can push. The task is consequently
free-space control: outcome depends on end-effector distance, not contact,
grasping, or force regulation
([contracts/robots/two_joint_arm.xml:4-7,25-28]).

### Observation and control loop

The policy receives 11 values: two joint positions, two joint velocities, the
three-dimensional end-effector-to-target error, and four wrapped angular
errors to the analytic elbow-open and elbow-folded inverse-kinematic
solutions. The target is stationary and noiseless. Since the observation
contains the current configuration and Cartesian error, the target planar
position is reconstructable from the observation and the forward kinematics;
there is no target-position ambiguity in the nominal simulator. There is no
observation noise, delay, acceleration measurement, or action history in the
scenario code
([robot_learning/scenario/observations.py:11-49]).

The observation is taken before the action. The action is then held while the
physics advances for 20 ms, after which distance and hold state are evaluated.
An in-tolerance step increments the hold counter; one out-of-tolerance step
resets it to zero. Termination occurs only at 100 uninterrupted in-tolerance
steps ([robot_learning/scenario/environment.py:122-168]).

## Physical consequences

### 1. Reaching is a branch-constrained inverse-kinematics problem

For a target radius `r`, the elbow solutions satisfy

    cos(q2) = (r^2 - 0.12^2 - 0.10^2) / (2*0.12*0.10).

The positive and negative solutions are elbow-open and elbow-folded
configurations. Their shoulder angles differ correspondingly. Both branches
are available for central angular sectors, while the shoulder limits remove
one branch near some directions; at least one branch remains available across
the official band. At small radii the elbow is close to the folded limit
(about 150 degrees at 6 cm), while at large radii it approaches extension.

**Decision relevance:** A first policy decision can change depending on whether
the learned controller should represent one continuous branch or safely handle
branch changes. A policy that reaches one branch but crosses the shoulder
limit, or switches branches while moving, can fail despite a reachable target.

**Assumptions and sources:** This follows from the two-link geometry, the
declared joint limits, and the two branch errors supplied to the policy
([contracts/robots/two_joint_arm.py:5-7],
[contracts/robots/two_joint_arm.xml:12-20],
[robot_learning/scenario/observations.py:18-47]). It assumes the compiled
joint limits have their ordinary MuJoCo meaning.

**Discriminating evidence:** For each target, record the selected IK branch,
joint-limit margin, final joint configuration, and whether a branch switch or
limit interaction precedes failure. Branch-balanced success with adequate
limits would weaken branch selection as the dominant concern; failures
concentrated by angular sector or radius would support it.

### 2. The reset state creates a transient singularity and a large dynamic range

The arm starts fully extended, where the planar Jacobian has rank one
(`sin(q2)=0`). End-effector motion in one Cartesian direction is therefore
not independently controllable to first order at the initial configuration.
The target can instead be anywhere from 2 cm to 42 cm from the initial
end-effector, depending on radius and angle. Targets near +x and 20 cm are
close in position but require leaving the initially singular posture; targets
near the opposite direction require a large reorientation.

**Decision relevance:** This changes whether early behavior should be judged
primarily as global reorientation, singularity escape, or fine convergence.
It also makes a single aggregate success rate insufficient for deciding which
physical difficulty limits the campaign.

**Assumptions and sources:** The implication uses the forward kinematics,
zero reset state, and uniform angular task geometry
([robot_learning/scenario/environment.py:83-120],
[contracts/scenario.md:9-12]). It assumes no unmodeled external disturbance.

**Discriminating evidence:** Stratify first-reach time and failure by target
angle, radius, initial Cartesian distance, and initial Jacobian condition.
Fast success for distant targets but slow or unstable behavior near the +x
singular direction would support this mechanism.

### 3. Reaching and holding are dynamically coupled

The motors accelerate the arm directly; they do not command a desired joint
position. With zero gravity, a configuration at zero velocity needs no torque
to remain there, but a moving arm must be decelerated before entering the
1-cm ball. Damping removes some velocity, while the controller must generally
use opposing torque to prevent overshoot. The same high control authority that
shortens transit can make the final two seconds difficult if entry velocity is
large. Because the tolerance is evaluated only every 20 ms, an excursion
between evaluations is not measured by the task, whereas an excursion at one
evaluation destroys the entire accumulated hold.

**Decision relevance:** The first campaign comparison may need to distinguish
transit efficiency from low-velocity stabilization. Optimizing approach
distance or reward without measuring hold continuity can select a policy that
reaches often but rarely completes episodes.

**Assumptions and sources:** This follows from direct motor actuation, damping,
zero gravity, frame skipping, and the reset-on-exit hold state
([contracts/robots/two_joint_arm.xml:1-3,13-18,30-33],
[robot_learning/scenario/environment.py:131-159]).

**Discriminating evidence:** Measure end-effector velocity and acceleration at
first tolerance entry, distance margin throughout the hold, action magnitude,
and the timing of each interruption. A large interruption rate with high entry
velocity supports a braking/convergence mechanism; interruptions at low
velocity point instead to observation, discretization, or branch/limit
effects.

### 4. The official distribution is broader than the visible training
distribution

The task contract includes radii from 6 to 20 cm, but the current training
environment samples only 14 to 20 cm. The evaluation environment uses the
official 6 to 20 cm range. Thus a policy can appear competent on the current
training band while encountering qualitatively more folded configurations and
different leverage at 6--14 cm during evaluation
([robot_learning/training/environment.py:14-19],
[robot_learning/scenario/environment.py:171-178],
[contracts/scenario.md:9-12]).

**Decision relevance:** Early campaign evidence must separate learning failure
from extrapolation failure. The radius distribution is a direct candidate for
changing the interpretation of any apparent high training performance; this
is a consequence to test, not a prescribed intervention.

**Assumptions and sources:** This assumes the visible training constructor is
the one used by the baseline and that the protected evaluator retains the
contract range.

**Discriminating evidence:** Report success, first reach, minimum distance,
and hold interruptions in radial bins, especially 6--14 cm versus 14--20 cm.
A flat profile weakens distribution mismatch as a first-order issue; a sharp
inner-radius drop supports it.

### 5. The nominal observation is Markov-complete but not behaviorally
diagnostic by itself

The policy has enough noiseless state information to infer target position and
current velocity under the known simulator, so partial observability is not
the leading nominal constraint. However, the observation does not expose
torque, acceleration, Jacobian conditioning, branch identity as a discrete
label, or distance-to-joint-limit directly. These are recoverable or
computable diagnostic quantities, but a policy must infer their relevance from
the continuous features.

**Decision relevance:** If failures are concentrated at equivalent Cartesian
errors but different velocities or configurations, the limiting issue is
control-state sensitivity rather than target localization. This changes which
measurements can justify a learning-method decision.

**Assumptions and sources:** The claim follows from the exact observation
construction and identity policy-action mapping
([robot_learning/scenario/observations.py:27-49],
[robot_learning/scenario/policy_io.py:11-16]).

**Discriminating evidence:** Compare outcomes at matched distance and target
error while varying velocity, IK branch, and joint-limit margin. Consistent
outcomes across those conditions weaken this explanation; configuration- or
velocity-conditioned outcomes support it.

### 6. The meaningful outcome decomposition is transit, convergence, and
continuity

The code already records first tolerance entry, minimum and final distance,
maximum held steps, total in-tolerance steps, and interruptions. These are
physically interpretable alongside target radius/angle. The decisive quantity
is not total in-tolerance time: any interruption resets the contiguous hold,
and only 100 consecutive steps terminate successfully. The shaped reward adds
progress, closeness, hold-progress, and a completion bonus, but it is not the
official success criterion ([robot_learning/scenario/evaluation.py:51-106],
[robot_learning/training/reward.py:47-107]).

**Decision relevance:** These measurements can identify whether the first
campaign decision concerns global reachability, settling, or sustained
stability without substituting a proxy for the human goal.

**Assumptions and sources:** This assumes the scenario-owned diagnostics
faithfully reflect the protected success semantics.

**Discriminating evidence:** A successful policy should show both high
episode success and a low tail of hold interruptions, not merely low minimum
distance or high average in-tolerance steps. The official 200-episode panel
must remain the final binary assessment ([contracts/scenario.md:24-31]).

## Unknowns

1. **Policy-dependent settling margin.** The simulator parameters are fixed,
   but it is unknown how much distance and velocity margin a learned policy
   has on entry to the tolerance region. This can change whether early work
   should prioritize transit or stabilization. It assumes the dominant
   failures are policy-induced rather than numerical. Sources are the actuator
   and timing definitions ([contracts/robots/two_joint_arm.xml:1-3,13-18,30-33],
   [robot_learning/scenario/environment.py:131-168]). First-entry velocity,
   peak overshoot, and hold-interruption timing discriminate the alternatives.

2. **Failure distribution over geometry.** Before evidence, it is unknown
   whether failures cluster at small radii, near the initial +x direction,
   near full angular extremes, or uniformly. This can change whether the
   training/evaluation distribution or kinematic branch coverage is the first
   decision. Sources are the target sampler and IK equations
   ([robot_learning/scenario/environment.py:83-97],
   [robot_learning/scenario/observations.py:18-35]). A radius-angle heat map
   of success and first-reach time supports or weakens each mechanism.

3. **Branch and limit behavior during motion.** Static IK establishes available
   solutions, not whether the learned trajectory stays on one branch or
   approaches a joint limit with damaging velocity. This can change the
   interpretation of apparently intermittent failures. It assumes the
   relevant trajectory remains within the declared limits. Sources are
   [contracts/robots/two_joint_arm.xml:12-20] and
   [robot_learning/scenario/observations.py:18-47]. Joint trajectories, branch
   residuals, limit margins, and action sign changes are the discriminating
   observations.

4. **Sensitivity to the 20-ms observation/action granularity.** The code
   evaluates only the post-frame-skip state, but the effect of sampling on
   narrow 1-cm-margin holds is unknown before a policy is observed. This can
   change whether failures are treated as ordinary control error or
   timing-sensitive boundary crossings. Sources are
   [contracts/robots/two_joint_arm.xml:1-3] and
   [robot_learning/scenario/environment.py:55-58,131-168]. Comparing sampled
   distance margins and within-step simulated trajectories would support,
   weaken, or revise this interpretation.

5. **Transfer from shaped learning signal to binary success.** The reward
   encourages progress and hold-counter growth, but the complete uninterrupted
   hold is the only official outcome. It is unknown whether optimization will
   reliably discover the low-velocity behavior needed for 100 consecutive
   steps. This can change the first learning-method decision. Sources are
   [robot_learning/training/reward.py:47-107] and
   [contracts/scenario.md:18-31]. Reward components, episode success, and
   interruption counts provide the discriminating comparison.

## Decision-relevant synthesis

1. **Hold continuity is the governing physical bottleneck, not proximity.**
   The policy must brake a directly actuated, gravity-free arm and maintain a
   1-cm distance for 100 consecutive 20-ms evaluations. This matters because a
   reach-heavy metric can select the wrong behavior. It assumes the simulator
   semantics are the official semantics; the source is
   [contracts/scenario.md:18-31] and
   [robot_learning/scenario/environment.py:131-168]. First-entry velocity,
   distance margin, and interruption timing are the decisive evidence.

2. **The reset posture makes the early transient geometrically special.**
   Full extension is a Jacobian singularity, while targets span 6--20 cm and
   all angles. This matters because failures may be caused by singularity
   escape or global reorientation rather than final targeting. It assumes the
   reset is unchanged; sources are
   [contracts/robots/two_joint_arm.xml:12-20] and
   [robot_learning/scenario/environment.py:102-120]. Angle/radius-stratified
   first-reach and conditioning measurements discriminate it.

3. **Kinematic branch availability and the inner-radius gap are coupled
   campaign risks.** Two-link IK offers open/folded alternatives, but shoulder
   limits remove branches in angular sectors, and the visible training range
   omits 6--14 cm. This matters because high apparent performance can conceal
   branch or distribution failures. The assumptions and sources are
   [robot_learning/scenario/observations.py:18-47],
   [contracts/robots/two_joint_arm.xml:13-18], and
   [robot_learning/training/environment.py:14-19]. Evidence must include
   branch/limit diagnostics and radial success bins.

4. **Nominal sensing is sufficient, so physical failure should be localized
   before treating it as an observability problem.** The observation includes
   configuration, velocity, Cartesian error, and both analytic IK branches,
   with no noise or delay. This matters because matched-state comparisons can
   distinguish representation limits from convergence dynamics. It assumes the
   policy runtime preserves the scenario observation/action functions
   ([robot_learning/scenario/observations.py:27-49],
   [robot_learning/scenario/policy_io.py:11-16]). Matched error, velocity,
   branch, and joint-limit measurements are the required evidence.
