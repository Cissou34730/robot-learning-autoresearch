## Established facts

### Scope and evidence status

**Repository fact.** This is the pre-campaign physical model of the official
two-joint-arm reach-and-hold task. It uses the human-authored scenario, robot
XML, task constants, and current scenario implementation; it does not use
training results or campaign evidence. The classification labels below mean
**Repository fact**, **Reasoned implication**, and **Unresolved quantity**.
Source references: `contracts/program.md` (campaign startup), 
`contracts/scenario.md` (official task and boundary), `AGENTS.md` (source
ownership).

### Morphology and coordinate structure

**Repository fact.** The robot has a fixed base and two revolute joints:
`shoulder` and `elbow`. Both hinge axes are the world/local z axis, both joint
ranges are `[-170, 170]` degrees, the upper-arm centerline length is `0.12 m`,
and the forearm centerline length is `0.10 m`. The end-effector site is at the
forearm tip, so its centerline distance from the shoulder is `0.22 m` when the
links are collinear. The upper-arm and forearm capsule radii are `0.015 m` and
`0.012 m`; these are geometry radii, not task tolerances. Source references:
`contracts/robots/two_joint_arm.xml` (`base`, `upper_arm`, `forearm`,
`end_effector`), `contracts/robots/two_joint_arm.py`
(`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`).

**Repository fact.** The shoulder is at z=`0.02 m` and the two link centerlines,
the end-effector site, and the reset target all lie in that horizontal plane.
The base has no joint, so there is no floating-base translation, base rotation,
or out-of-plane arm degree of freedom. Source references:
`contracts/robots/two_joint_arm.xml`, `robot_learning/scenario/environment.py`
(`_sample_target_position`).

**Repository fact.** The target is a mocap body, not a jointed or actuated
object. Its visible sphere has size `0.012 m`, but its geom has
`contype="0"` and `conaffinity="0"`. The plane and base geom also explicitly
have contact disabled. The target therefore supplies a geometric reference
point and no grasp, impact, or load-bearing interaction. Source reference:
`contracts/robots/two_joint_arm.xml`.

### Simulator, reset, and timing

**Repository fact.** The scenario constructs `mujoco.MjModel` from the robot
XML and advances `MjData` with `mujoco.mj_step`. The XML sets gravity to
`[0, 0, 0]` and the MuJoCo integration timestep to `0.002 s`. The environment
uses `FRAME_SKIP=10`, holds one command through ten simulator steps, and
therefore exposes a `0.020 s` control period, or `50 Hz`. Source references:
`contracts/robots/two_joint_arm.xml` (`option`), `contracts/task_spec.py`
(`FRAME_SKIP`), `robot_learning/scenario/environment.py` (`step`).

**Repository fact.** On reset, the environment resets the MuJoCo state, sets
both joint positions and velocities to zero, runs forward kinematics, and then
samples the target. The initial arm is consequently straight along +x, with
the end effector at approximately `(0.22, 0, 0.02) m`; the target is then
placed in the same z plane. Source references:
`robot_learning/scenario/environment.py` (`reset`, `_sample_target_position`),
`contracts/robots/two_joint_arm.xml`.

**Repository fact.** Each target radius is sampled independently and uniformly
from `0.06 m` to `0.20 m`, and its angle is sampled uniformly from
`[-pi, pi]`. This is uniform in radius and angle, not uniform in planar area.
The official episode limit is 500 control steps. Source references:
`contracts/scenario.md`, `contracts/task_spec.py`
(`TARGET_RADIUS_RANGE`, `MAX_EPISODE_STEPS`), 
`robot_learning/scenario/environment.py` (`_sample_target_position`).

### Actuation and command application

**Repository fact.** The action interface has two scalar values in `[-1, 1]`.
The current scenario policy mapping is the identity; the environment converts
the result to floating point, clips it to the action-space bounds, writes it to
`data.ctrl`, and then advances ten internal steps. Each actuator is a MuJoCo
`motor` attached to one hinge with `gear="5"` and `ctrlrange="-1 1"`. There is
no explicit actuator activation state, transmission dynamics, force range, or
action-rate limit in the XML. Source references:
`robot_learning/scenario/policy_io.py` (`physical_action`, `make_policy_io`),
`robot_learning/scenario/environment.py` (`step`), 
`contracts/robots/two_joint_arm.xml` (`actuator`), 
`contracts/instruments.md` (saved controller execution).

**Repository fact.** The joints specify damping `0.5` and armature `0.01`.
These are the only explicit joint dynamic parameters in the robot XML. No
`inertial` elements or explicit body masses, centers of mass, or inertia
tensors are declared. Source reference:
`contracts/robots/two_joint_arm.xml` (`shoulder`, `elbow`).

### Observation and evaluation semantics

**Repository fact.** The policy observation has 11 float32 entries in this
order: two joint positions, two joint velocities, the three-dimensional
end-effector-minus-target vector, and four wrapped joint errors to the
elbow-open and elbow-folded inverse-kinematics solutions. The observation is
computed from the current MuJoCo state and target after reset or after each
control step. Source references:
`robot_learning/scenario/observations.py` (`reach_observation`,
`OBSERVATION_SIZE`), `robot_learning/scenario/environment.py`
(`_observation`, `step`).

**Repository fact.** The implementation adds no observation noise, sensor
latency, quantization, force sensing, or contact sensing. The observation does
not include the action, acceleration, actuator effort, contact force, absolute
target position, episode step count, or hold counter. Source references:
`robot_learning/scenario/observations.py`,
`robot_learning/scenario/environment.py`.

**Repository fact.** After each action, the environment computes the Euclidean
distance between the end-effector site and the mocap target. A sample is
inside tolerance when that distance is at most `0.01 m`. An inside sample
increments the hold counter; any outside sample resets it to zero. Termination
occurs at 100 consecutive inside control-step samples, while truncation occurs
at 500 control steps. With a `0.020 s` control period, the required count is
`round(2.0 / 0.020) = 100`. Source references:
`contracts/scenario.md`, `contracts/task_spec.py`
(`SUCCESS_THRESHOLD`, `HOLD_SECONDS`), `robot_learning/scenario/environment.py`
(`hold_steps_required`, `step`).

**Repository fact.** The official assessment uses one frozen policy on 200
episodes, with success required on at least 196 episodes for the 98% objective.
Research evaluation diagnostics record target radius and angle, minimum and
final sampled distance, first sampled reach, maximum sampled held steps,
in-tolerance sampled steps, and hold interruptions. Source references:
`contracts/scenario.md`, `robot_learning/scenario/evaluation.py`
(`episode_diagnostics`).

**Repository fact.** The current baseline training environment samples only
`0.14 m` to `0.20 m`, whereas evaluation uses the official `0.06 m` to
`0.20 m` range. This is a training exposure choice, not a change to the
official task. Source references:
`robot_learning/training/environment.py`
(`TRAINING_TARGET_RADIUS_RANGE`), `contracts/task_spec.py`,
`robot_learning/scenario/environment.py` (`make_evaluation_env`).

## Physical consequences

### Planar forward kinematics, workspace, and branches

**Reasoned implication.** Let `q1` be shoulder angle and `q2` elbow angle,
with lengths `L1=0.12 m` and `L2=0.10 m`. The centerline end-effector
position is

```text
p(q) = [L1*cos(q1) + L2*cos(q1+q2),
        L1*sin(q1) + L2*sin(q1+q2),
        0.02].
```
With unrestricted planar angles the radial workspace is the annulus from
`|L1-L2|=0.02 m` to `L1+L2=0.22 m`. The elbow limit changes the smallest
radial value to about `0.0276 m` at `|q2|=170 deg`; the official radii
`0.06` to `0.20 m` are inside both radial bounds. For a target with radius
`r`, the two point-kinematic solutions are
`q2 = +/- acos((r^2-L1^2-L2^2)/(2*L1*L2))`, with
`q1 = theta - atan2(L2*sin(q2), L1+L2*cos(q2))`. Across the official radius
range, the nominal elbow magnitudes run from about `49.5 deg` to `150.1 deg`,
so both nominal elbow branches are within the elbow limit. The shoulder limit
can remove one branch for some directions, but the two branches have
complementary shoulder offsets; under this point-kinematic model at least one
branch remains available over the official angle range.

- **Decision relevance:** A failure to reach an official target is not
  explained by radial workspace alone. Early decisions can instead turn on
  branch selection, shoulder-limit handling, path feasibility, or dynamics.
  The close-radius portion requires much larger elbow folds than the outer
  portion, so radius-conditioned behavior can change which capability is
  limiting.
- **Assumptions:** The implication assumes centerline point kinematics, no
  active self-collision, the stated joint limits, and the target center as the
  task point. It does not establish that a dynamic trajectory can reach every
  solution within 500 control steps.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/robots/two_joint_arm.py`; `contracts/task_spec.py`;
  `robot_learning/scenario/observations.py`
  (`shoulder_for_elbow` and the two IK branches).
- **Discriminating evidence:** Target-radius/angle-conditioned endpoint
  distances and IK errors would support or weaken the kinematic explanation.
  Joint trajectories and the number of admissible branch solutions at the
  realized target would revise it if contact or joint-limit forces intervene.

### Initial singularity and maneuver geometry

**Reasoned implication.** The reset configuration is `q1=q2=0`, so the
instantaneous planar Jacobian is

```text
J = [[-L1*sin(q1)-L2*sin(q1+q2), -L2*sin(q1+q2)],
     [ L1*cos(q1)+L2*cos(q1+q2),  L2*cos(q1+q2)]]
```

and has rank one at reset: the first-order x velocity is zero for every joint
velocity, while y velocity is `0.22*q1dot + 0.10*q2dot`. Radial retraction
from the fully extended `0.22 m` posture therefore begins through elbow
bending and higher-order position change rather than an instantaneous radial
velocity. At any exact target solution in the official annulus,
`det(J)=L1*L2*sin(q2)` is nonzero because the two elbow solutions are away
from `q2=0` and `q2=pi`.

- **Decision relevance:** Startup transients can be dominated by escape from
  the initial singular posture even though the final target posture is locally
  well-conditioned. A policy that only behaves well after reaching a
  branch-specific neighborhood can still fail broadly from reset.
- **Assumptions:** This uses the centerline kinematic model and assumes the
  target remains static. It does not infer a particular acceleration or
  escape time without compiled inertia and actuator dynamics.
- **Source references:** `robot_learning/scenario/environment.py` (`reset`);
  `contracts/robots/two_joint_arm.xml`; the length definitions in
  `contracts/robots/two_joint_arm.py`.
- **Discriminating evidence:** The first several control steps of `q`, `qdot`,
  end-effector position, and branch errors would show whether failures cluster
  before the arm leaves `q2=0`. A measured Jacobian or finite-difference
  displacement from reset would support or revise the singularity mechanism.

### Direct actuation, damping, and dynamic authority

**Reasoned implication.** For the two hinge coordinates, the simulated
equations have the form
`M(q)*qdd + h(q,qdot) + B*qdot + constraint_terms = tau`, where `B` includes
the explicit `0.5` joint damping and the `0.01` armature terms augment the
joint-space inertia. Gravity contributes no term because the XML sets
gravity to zero. Under the direct MuJoCo motor transmission, a clipped
control `u` is nominally mapped by the gear to a generalized motor effort on
the order of `tau=5*u`, before the configuration-dependent dynamics and any
constraints determine acceleration. There is no gravity load to compensate:
in a contact-free interior posture with zero velocity, zero command is a
static equilibrium. Damping reduces velocity but is not a position servo, so
motion control still requires feedback through the observed state.

- **Decision relevance:** Whether a 50 Hz direct-command loop can settle in the
  tolerance band depends on the ratio of available effort to compiled inertia,
  damping, and the configuration-dependent coupling. This can change the
  relative value of fast trajectory shaping, conservative setpoints, or
  model-based control, without changing the geometric task.
- **Assumptions:** The nominal `5*u` statement assumes standard MuJoCo motor
  transmission semantics and no omitted force limit becomes active. The
  magnitude of `M(q)`, constraint forces, and actual acceleration remains
  unspecified by the XML.
- **Source references:** `contracts/robots/two_joint_arm.xml`
  (`option`, joint damping/armature, `actuator`); 
  `robot_learning/scenario/environment.py` (`step` clipping and command
  application); `AGENTS.md` (locked MuJoCo version).
- **Discriminating evidence:** Compiled mass, center-of-mass, inertia, and
  actuator fields, plus controlled torque/step or free-decay traces at
  representative postures, would establish acceleration, overshoot, and
  settling authority. A mismatch between the nominal torque and observed
  acceleration would weaken this simplified equation and identify an omitted
  limit or constraint.

### Sampled control and the hold requirement

**Reasoned implication.** The command is zero-order held for `10*0.002 s`
and the distance test is performed only after that block. Thus the official
  implementation counts 100 consecutive control-step endpoint samples, not
  an independently checked invariant at every 2 ms integration state. A
  transient excursion outside the 1 cm ball that returns before the next
  endpoint would not reset `_held_steps`; an endpoint excursion does reset it.
  The physical objective therefore couples reach, low residual velocity, and
  endpoint-to-endpoint stability, while the strictest continuous-time
  interpretation is not directly certified by the current evaluator.

- **Decision relevance:** A policy can attain the coded success criterion with
  inter-sample motion that would be unacceptable under a continuous-time
  interpretation. Conversely, a policy with small endpoint errors can still
  lose the hold at a sampled endpoint. This changes how a first campaign
  interprets hold success and which trajectory quantities are worth measuring.
- **Assumptions:** The protected evaluator uses the same frame-skip and
  endpoint test specified by the current contract. The statement concerns
  implementation semantics, not a claim that hidden benchmark code samples
  additional substeps.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`for _ in range(self.frame_skip)`,
  distance test, and `_held_steps`).
- **Discriminating evidence:** Recording end-effector distance at all ten
  internal substeps and comparing its maximum to endpoint-only hold outcomes
  would show whether inter-sample excursions are materially present. The
  protected evaluation contract and an implementation trace would resolve any
  semantic discrepancy.

### Coupled reaching, convergence, and stabilization

**Reasoned implication.** The 1 cm success region is a task-space ball
centered at the static target; in the planar reset/task plane it is a disk.
For small joint errors, `delta_p ~= J*delta_q`, so the same joint error
produces different Cartesian errors at different postures. The target is
locally invertible at its nominal IK solutions, but the route from the reset
singularity must coordinate both joints through an inertia-coupled system.
Once inside the ball, the controller must keep the endpoint inside for 2 s:
small joint velocity, action-induced oscillation, or an unfavorable coupled
joint correction can reset the entire hold. Since gravity and target load are
absent, a settled zero-velocity posture can remain static, but entering the
ball is not sufficient evidence of stabilization.

- **Decision relevance:** Episode success is a conjunction of arrival,
  convergence, and sustained stabilization, not a reach-only score. A policy
  can have a low minimum distance and still be poor at the official objective
  if it oscillates or exits late in the hold. The distinction determines
  whether first decisions emphasize approach time, final error, velocity, or
  hold robustness.
- **Assumptions:** The target remains fixed after reset, the centerline site is
  the controlled task point, and no unmodeled external load acts on the arm.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`_distance_to_target`,
  `_held_steps`); `robot_learning/scenario/observations.py`;
  `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence:** Joint velocity and distance traces through the
  complete episode, separated into first reach and hold intervals, would
  distinguish slow approach, overshoot, and late stabilization. The recorded
  `first_reach_step`, `max_held_steps`, and `hold_interruptions` already
  provide endpoint-level evidence for these classes.

### Observability and controller state

**Reasoned implication.** For the deterministic, planar, fixed-base model,
`q`, `qdot`, and the relative end-effector vector expose the mechanical state
needed for forward prediction up to the compiled dynamics and any contact
state. Because the base pose and link geometry are known, the absolute target
x-y position can be reconstructed from the observed end-effector position
computed from `q` and the observed relative vector, even though absolute target
coordinates are not directly included. The four wrapped IK errors provide a
derived representation of both elbow branches. The target is static, and the
current motor has no declared activation state, so no hidden actuator memory is
defined by the scenario.

The hold counter is different: two episodes can have the same physical
`q,qdot,target` observation but different `_held_steps` and therefore different
remaining success requirements. The counter, episode age, and prior action are
not observable in the current vector. A memoryless controller cannot know
whether an identical physical state is the first inside sample or sample 99;
it can still succeed by maintaining the state long enough, but it cannot use
explicit progress information unless its own recurrent state retains it.

- **Decision relevance:** The physical state is close to fully observed for
  motion control, while task progress is partially observed. This separates
  dynamics/kinematics failures from a possible memory or termination-awareness
  limitation and can change the interpretation of a reach-successful but
  hold-failing policy.
- **Assumptions:** The base pose and all relevant model parameters are known
  to the controller designer, target motion is absent, and no contact or
  actuator state is hidden. A saved runtime may carry recurrent policy state,
  but the observation itself does not carry hold progress.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`; `contracts/policy_runtime.py`
  (`PolicyRuntime.reset`, `predict`); `contracts/instruments.md` (saved
  runtime calls).
- **Discriminating evidence:** Matched physical states with different prior
  hold histories, together with policy recurrent state and actions, would
  establish whether the policy uses memory. Observation/action traces can
  also test whether target reconstruction and branch errors predict the
  subsequent motion.

### Distribution, reward, and behavior classes

**Reasoned implication.** The official distribution includes inner targets that
the current baseline training environment does not expose. Inner targets
require more folded configurations and may have different approach and
joint-limit geometry than the outer training interval. The dense training
reward combines distance progress, exponential closeness, hold progress,
outside-band penalty, completion bonus, and action cost, but the official
outcome is only the uninterrupted hold. Therefore reward improvement or a low
minimum distance can favor progress without guaranteeing the 100-step task
event.

The physically distinct episode classes are: never entering tolerance;
entering but exiting before 100 sampled steps; reaching only near the 500-step
limit; and completing the hold. These map respectively to reach/path,
convergence/stabilization, timing/authority, and full-task success mechanisms.

- **Decision relevance:** Early campaign decisions can change depending on
  whether failures are radius/angle coverage failures, slow approaches, or
  hold interruptions. A pooled success value alone cannot identify those
  mechanisms, especially when the target distribution is nonuniform in area.
- **Assumptions:** The current training range and reward implementation are
  representative of the candidate being considered; the official evaluator
  remains the authority for success.
- **Source references:** `robot_learning/training/environment.py`;
  `robot_learning/training/reward.py`; `contracts/scenario.md`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Stratified outcomes by target radius and angle,
  plus `first_reach_step`, `in_tolerance_steps`, `max_held_steps`, and
  `hold_interruptions`, would support or reject each failure class. Comparing
  reward components with the binary success outcome would show whether the
  dense proxy is aligned with the physical requirement.

### Quantities meaningful across the complete behavior

**Reasoned implication.** The most informative physical record is a time
history, not a terminal distance: target `(r, theta)`, `q`, `qdot`, end
effector position, distance-to-target, branch errors, action/control effort,
and the Jacobian conditioning should be interpreted from reset through the
entire hold. Aggregate quantities then have clear meanings: time to first
inside sample, minimum distance, final distance, sampled in-tolerance count,
maximum uninterrupted hold, number and timing of exits, truncation, and binary
success. Compiled acceleration, mass-matrix, contact, and actuator-force
quantities are needed to attribute a trajectory to dynamics rather than only
to policy behavior.

- **Decision relevance:** These quantities separate geometric feasibility,
  transient control authority, settling, and sustained stability; they also
  expose whether a 98% objective is limited by a narrow target subset or by
  broad stochastic-looking failures.
- **Assumptions:** Endpoint diagnostics are only endpoint diagnostics unless
  internal MuJoCo states are recorded. Actions are proxies for motor effort
  until the compiled transmission and any limits are verified.
- **Source references:** `robot_learning/scenario/evaluation.py`
  (`episode_diagnostics`); `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`; `contracts/robots/two_joint_arm.xml`.
- **Discriminating evidence:** Full-episode state/control traces and compiled
  model fields would support causal attribution. The existing evaluation
  artifact supports the aggregate reach-versus-hold partition, but cannot by
  itself establish unobserved inter-substep motion, torque, acceleration, or
  contact causality.

## Unknowns

### Compiled mass, inertia, and acceleration scale

**Unresolved quantity.** The XML does not state geom density, body masses,
centers of mass, or inertia tensors. MuJoCo will compile values for the loaded
model, but the repository text alone does not establish the resulting
`M(q)`, link inertial coupling, maximum acceleration, natural transient time,
or settling time. These quantities may materially determine whether a
5-scaled motor command is gentle or aggressive.

- **Decision relevance:** This can change the first choice between trajectory
  shaping, direct setpoint control, model-based control, or a campaign focused
  on damping and settling.
- **Assumptions:** The loaded model is the exact XML under the locked MuJoCo
  version, and no external load is present. The explicit damping and armature
  values are known even though the remaining inertial values are not.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`MjModel.from_xml_path`);
  `AGENTS.md` (MuJoCo version).
- **Discriminating evidence:** Inspecting the compiled model's body/DOF
  inertial fields and measuring controlled acceleration or free decay at
  several configurations would establish the dynamic scale. Observed
  configuration-dependent overshoot inconsistent with a constant-inertia
  approximation would revise any simplified model.

### Integrator, solver, and effective constraint numerics

**Unresolved quantity.** The XML fixes the timestep but does not explicitly
set integrator, solver, iteration, tolerance, or constraint parameters. The
installed MuJoCo defaults fill these values. The source therefore does not
establish numerical damping, constraint stabilization, or the exact behavior
of near-limit and near-contact motion.

- **Decision relevance:** This can change whether a 20 ms action update is
  dynamically adequate, whether a trajectory is reproducible near tolerance,
  and whether a measured failure is physical or numerical.
- **Assumptions:** The protected and research environments use the same loaded
  model and installed simulator configuration.
- **Source references:** `contracts/robots/two_joint_arm.xml` (`option`);
  `robot_learning/scenario/environment.py` (`mj_step`); `AGENTS.md`
  (locked simulator stack).
- **Discriminating evidence:** Compiled `MjModel.opt` fields, repeatability
  under identical seeds, and state traces at 2 ms and 20 ms resolution would
  support or revise the assumed numerical behavior. Constraint residuals and
  contact impulses would distinguish solver effects from policy effects.

### Link self-collision and contact filtering

**Unresolved quantity.** The base, plane, and target explicitly disable
contact, but the upper-arm and forearm capsule geoms do not specify
`contype` or `conaffinity`. The XML therefore does not, by itself, establish
whether folded branch trajectories encounter active self-contact under
MuJoCo's compiled filtering rules, or how such contact changes the feasible
configuration set.

- **Decision relevance:** Active self-contact could remove or slow a nominal
  IK branch and create force-mediated failures that look like poor control.
  The availability of elbow-folded targets is therefore not fully established
  until contacts are known.
- **Assumptions:** Only the declared geoms are present and no hidden exclusion
  or contact override is applied.
- **Source references:** `contracts/robots/two_joint_arm.xml` (all geom
  contact attributes); `robot_learning/scenario/environment.py` (`mj_step`).
- **Discriminating evidence:** Contact counts, contact pairs, normal forces,
  and joint trajectories at both IK branches would support or weaken this
  unknown. A compiled collision-filter inspection would resolve it without
  attributing behavior to learning.

### Effective motor effort and closed-loop transient

**Unresolved quantity.** The control path establishes the clipped command and
the motor gear, but not the realized acceleration, torque saturation under
all defaults, or settling response at every posture. The effect of the
`0.5` damping and `0.01` armature relative to the compiled inertia is
therefore unresolved. It is also unknown whether the policy's action varies
rapidly enough that endpoint samples conceal a meaningful internal oscillation.

- **Decision relevance:** This can change whether hold failures are caused by
  insufficient authority, excessive overshoot, action noise, or an
  observation/control rate mismatch.
- **Assumptions:** The current environment is the action application path and
  policy action mapping is the saved mapping used by the evaluated runtime.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py` (`np.clip`, `data.ctrl`, inner
  stepping); `contracts/policy_runtime.py`.
- **Discriminating evidence:** Per-substep `q`, `qdot`, distance, control,
  actuator force, and acceleration traces at representative targets would
  separate effort limitation from overshoot and endpoint aliasing.

### Hold-progress observability and policy memory

**Unresolved quantity.** It is established that `_held_steps` is absent from
the observation, but it is not established whether a candidate policy's saved
runtime has recurrent state that retains enough episode history to infer hold
progress. A memoryless policy can maintain a target without knowing the
counter, while a recurrent policy may encode elapsed inside time; the physical
task outcome alone does not identify which mechanism is used.

- **Decision relevance:** This can change whether a hold-failing policy is
  treated as a stabilization problem or as a task-progress observability
  problem, and whether a controller comparison is scientifically interpretable.
- **Assumptions:** The saved runtime is the one actually executed, its
  `reset` behavior is called once per episode, and no unrecorded observation
  augmentation exists.
- **Source references:** `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/environment.py`; `contracts/policy_runtime.py`
  (`PolicyIO`, `PolicyRuntime.reset`, `predict`).
- **Discriminating evidence:** The saved observation/action contract, recurrent
  state traces where available, and matched-state episodes with different
  hold histories would support or reject a memory explanation.

### Continuous-time hold versus coded hold

**Unresolved quantity.** The contract describes an uninterrupted two-second
  hold, while the current environment checks distance once after each
  ten-substep action block. It is unresolved whether any candidate's apparent
  100-step hold contains substep excursions outside 1 cm, and whether the
  protected implementation adds a finer check. The coded success result is
  authoritative for the official assessment, but it does not by itself answer
  the stricter continuous-time physical question.

- **Decision relevance:** A material endpoint/substep difference changes the
  physical interpretation of success and the credibility of any stabilization
  mechanism inferred from endpoint diagnostics.
- **Assumptions:** The implementation shown is the relevant research semantics;
  official protected semantics must be verified from its human-owned contract.
- **Source references:** `contracts/scenario.md`; `contracts/task_spec.py`;
  `robot_learning/scenario/environment.py` (`frame_skip`, distance sampling).
- **Discriminating evidence:** A protected or exact simulator trace of all
  internal states during successful holds would support, weaken, or revise the
  equivalence between coded and continuous hold.

## Decision-relevant synthesis

### Nominal reachability is not the likely first bottleneck

**Reasoned implication.** Under point kinematics, official targets lie inside
the radial workspace and have at least one joint-limit-compatible IK branch,
but the reset is a rank-one fully extended singularity and close targets
require large elbow folds.

- **Decision relevance:** This could change whether the first campaign decision
  emphasizes branch-aware transient control and coverage rather than treating
  all failures as unreachable targets.
- **Assumptions:** No active self-collision or unexpected compiled constraint
  removes the nominal branch; the centerline site defines success.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/observations.py`.
- **Discriminating evidence:** Radius/angle-stratified success, first-reach
  time, joint trajectories, branch errors, and Jacobian conditioning would
  distinguish singularity escape, branch limits, and true geometric failure.

### The official distribution includes an unexposed inner regime

**Reasoned implication.** The current training range starts at 14 cm while the
official range starts at 6 cm. The omitted 6-14 cm targets demand more folded
postures and can have different transient and contact behavior, even though
they are nominally reachable.

- **Decision relevance:** The first decision about what evidence to trust can
  change if apparent performance is driven by the outer training interval
  rather than the official distribution.
- **Assumptions:** The candidate uses the current training environment and no
  other exposure compensates for the missing radii.
- **Source references:** `robot_learning/training/environment.py`;
  `contracts/task_spec.py`; `robot_learning/scenario/environment.py`.
- **Discriminating evidence:** Official-distribution diagnostics conditioned on
  radius and angle, with the same success and hold definitions, would support
  or weaken an inner-regime generalization explanation.

### Direct torque authority and timing are quantitatively unresolved

**Unresolved quantity.** The action is applied as a clipped, gear-scaled
command every 20 ms, with explicit damping and armature but unspecified
compiled inertia and numerical defaults. The physical response time, overshoot,
and control authority therefore cannot be inferred from the action range alone.

- **Decision relevance:** This is the most consequential unknown for deciding
  whether early failures call for a different control timescale, trajectory
  representation, or a dynamics-focused investigation.
- **Assumptions:** MuJoCo motor semantics and the current action path are the
  operative semantics; no hidden force limit or contact dominates.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `AGENTS.md`.
- **Discriminating evidence:** Compiled inertial/actuator fields and
  per-substep torque, acceleration, velocity, and distance traces would
  discriminate insufficient authority from overshoot or poor branch choice.

### The objective is a stabilization objective, with hidden progress

**Reasoned implication.** A policy must enter a 1 cm task-space region and
remain there for 100 consecutive control samples; the observation exposes
physical motion but not the hold counter. Reach, convergence, and stability
are coupled, while task progress is only inferable through policy memory or
continued maintenance.

- **Decision relevance:** A first campaign comparison can change materially
  depending on whether failures show no reach, late exits, or repeated sampled
  interruptions; a reach-only proxy is insufficient for the 98% objective.
- **Assumptions:** The current observation and endpoint hold implementation
  govern evaluation, and the target remains static.
- **Source references:** `contracts/scenario.md`;
  `robot_learning/scenario/environment.py`;
  `robot_learning/scenario/observations.py`;
  `robot_learning/scenario/evaluation.py`.
- **Discriminating evidence:** Complete episode diagnostics, especially first
  reach, maximum held steps, interruption count, final distance, and
  radius/angle strata, would support or revise the dominant failure class.

### Contact and substep semantics can revise the physical interpretation

**Unresolved quantity.** The XML disables environmental target/base/plane
contact but does not explicitly settle link self-contact, and the environment
checks the hold at control-step endpoints rather than every integration
substep. These two simulator details can make nominal branch feasibility and
endpoint success differ from continuous collision-free, continuously bounded
motion.

- **Decision relevance:** If either effect is material, conclusions about
  stabilization, branch choice, or physical robustness would need to be
  limited to the official coded semantics rather than generalized to the
  continuous embodied behavior.
- **Assumptions:** The source omissions are filled by simulator defaults and
  are not overridden by the protected evaluator.
- **Source references:** `contracts/robots/two_joint_arm.xml`;
  `robot_learning/scenario/environment.py`; `contracts/scenario.md`.
- **Discriminating evidence:** Compiled contact filtering, contact-force
  traces, and all-substep distance traces during successful and failed
  episodes would support, weaken, or revise this interpretation.
