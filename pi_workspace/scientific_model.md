## Established facts

### Morphology and geometry

**[Repository fact]** The MJCF defines a fixed-base, serial two-hinge arm. The shoulder is at height 0.02 m; both hinge axes are world-parallel to z. The upper-arm geometry extends 0.12 m along local x, the forearm extends another 0.10 m, and the `end_effector` site is at the forearm tip. There are two actuated configuration coordinates and no base, wrist, or gripper degree of freedom. Sources: `contracts\robots\two_joint_arm.xml`; `contracts\robots\two_joint_arm.py` (`UPPER_ARM_LENGTH`, `FOREARM_LENGTH`, `MAX_REACH`).

**[Repository fact]** Both hinges have a range of -170 to 170 in the MJCF's default degree convention, damping 0.5, and armature 0.01. The arm geoms are capsules with radii 0.015 m and 0.012 m. The XML's declared maximum centerline reach, 0.22 m, is the sum of link lengths. Sources: `contracts\robots\two_joint_arm.xml`; `contracts\robots\two_joint_arm.py`.

**[Repository fact]** The MJCF declares angular position ranges, but no joint speed or acceleration limits. It does not define a joint-position servo or command smoother. Sources: `contracts\robots\two_joint_arm.xml`; `robot_learning\scenario\environment.py` (`step`).

**[Repository fact]** The target is a mocap body with a 0.012 m sphere, but the target, plane, and base geoms have collision disabled. The task measures the end-effector site's position against the mocap position; it does not require contact with the visible sphere, a particular end-effector orientation, or manipulation of an object. Sources: `contracts\robots\two_joint_arm.xml`; `robot_learning\scenario\environment.py` (`_distance_to_target`).

### Dynamics, actuation, and timing

**[Repository fact]** The MJCF sets gravity to zero and the physics timestep to 0.002 s. It defines one `motor` on each hinge, each with control range [-1, 1] and gear 5. It does not explicitly declare link inertial elements, geom density, or an integrator/solver. Sources: `contracts\robots\two_joint_arm.xml`; the pinned scientific stack is identified in `AGENTS.md`.

**[Repository fact]** The current scenario environment exposes a two-value action in [-1, 1], applies the current `policy_io.action`, clips its result to that range, assigns it to `data.ctrl`, and calls `mujoco.mj_step` ten times before returning the next observation. With the declared timestep and frame skip, the action is held for 0.020 s and feedback is returned at 50 Hz. The default `physical_action` is the identity map. Sources: `contracts\task_spec.py`; `robot_learning\scenario\environment.py` (`__init__`, `step`); `robot_learning\scenario\policy_io.py`.

### Reset, target distribution, and outcome

**[Repository fact]** On reset, the current environment sets both joint positions and velocities to zero, forwards the model, samples target angle uniformly over [-pi, pi] and radius uniformly over [0.06, 0.20] m, and sets target height to the end-effector's height. The target stays fixed during that episode. Thus the reset posture is straight along +x, with end effector at (0.22, 0, 0.02) m. Sources: `robot_learning\scenario\environment.py` (`reset`, `_sample_target_position`); `contracts\scenario.md`.

**[Repository fact]** The official task requires end-effector distance no greater than 0.01 m for 2.0 s, corresponding to 100 consecutive 0.020 s control steps. An episode allows at most 500 control steps (10 s). The final assessment uses a fixed 200-episode panel; at least 196 successes (98%) meet the stated objective. Sources: `contracts\scenario.md` (`Official task`, `Success criterion`, `Official final assessment`); `contracts\task_spec.py`.

**[Repository fact]** In the readable research environment, distance is evaluated after the ten physics substeps of each control action. An in-tolerance sample increments the hold counter; an out-of-tolerance sample resets it. This is the research implementation's boundary-sampled check, not independent proof of the protected evaluator's substep semantics. Sources: `robot_learning\scenario\environment.py` (`step`); `contracts\instruments.md` (`Saved controller execution`).

**[Repository fact]** The current training constructor samples radii only from [0.14, 0.20] m, whereas the official band is [0.06, 0.20] m. The current training reward shapes distance progress, closeness, hold progress, action cost, and completion; official success remains the threshold-and-hold outcome, not reward. Sources: `robot_learning\training\environment.py`; `robot_learning\training\reward.py`; `contracts\scenario.md`.

### Observation and saved controller interface

**[Repository fact]** The current default observation has 11 float32 values: two joint positions, two joint velocities, the three-dimensional vector `end_effector - target`, and four wrapped joint-angle residuals to the two analytical inverse-kinematic elbow branches. It reads simulator qpos, qvel, site position, and mocap target directly; this function adds no sensor noise, image processing, or state estimator. It does not expose motor force or acceleration as observation fields. Sources: `robot_learning\scenario\observations.py` (`reach_observation`); `robot_learning\scenario\policy_io.py`.

**[Repository fact]** The current default policy I/O pairs that observation with an identity action map. The runtime contract saves the observation, action, optional reset callback, normalization state, and model identity with the candidate. Protected evaluation executes the candidate's saved I/O functions rather than substituting current research-environment code. Sources: `robot_learning\scenario\policy_io.py`; `contracts\policy_runtime.py`; `contracts\instruments.md` (`Saved controller execution`).

**[Repository fact]** The current research evaluator records target radius and angle, minimum and final distance, first in-tolerance step, maximum held steps, in-tolerance steps, interruptions, and episode outcome. Its listed episode diagnostics do not include joint trajectories, joint velocities, applied motor command, or branch choice. Source: `robot_learning\scenario\evaluation.py` (`evaluate_research_model`).

## Physical consequences

### Reachability and the singular reset

**[Reasoned implication]** For link lengths L1 = 0.12 m and L2 = 0.10 m, planar forward kinematics are x = L1 cos(q1) + L2 cos(q1 + q2), y = L1 sin(q1) + L2 sin(q1 + q2), and r^2 = L1^2 + L2^2 + 2 L1 L2 cos(q2). The official target radii imply |q2| from about 150.1 degrees at 0.06 m to 49.5 degrees at 0.20 m. Across the full target-bearing range, at least one of the two elbow branches has a shoulder angle within the stated +/-170 degree limits. The exact target centers are therefore positionally reachable; their inverse-kinematic configurations are also away from the straight/folded singularities, with |sin(q2)| at least about 0.499. Sources: `contracts\robots\two_joint_arm.xml`; `contracts\robots\two_joint_arm.py`; `contracts\scenario.md`.

**[Reasoned implication]** That static reachability does not make the initial motion trivial. Reset has q1 = q2 = 0, so the arm is fully extended at 0.22 m and the planar Jacobian determinant L1 L2 sin(q2) is zero. Its instantaneous endpoint velocity has only one independent Cartesian direction; radial inward motion requires bending the elbow first. The sampled target is always inside the initial radius, and the reset endpoint-to-target distance ranges from 0.02 to 0.42 m depending on target radius and bearing. Sources: `robot_learning\scenario\environment.py` (`reset`, `_sample_target_position`); `contracts\robots\two_joint_arm.xml`.

- **[Reasoned implication — decision relevance]** A failure should not be attributed to an unreachable target merely because the target is near the inner or outer part of the official band. Initial singularity, branch choice, target-dependent travel, and dynamic convergence are more plausible physical distinctions to examine before changing workspace or link geometry.
- **[Reasoned implication — assumptions]** This conclusion assumes rigid links of the declared lengths, targets in the declared plane, the stated hinge limits, and no additional obstacle or self-contact constraint that blocks the chosen configuration.
- **[Reasoned implication — sources]** `contracts\robots\two_joint_arm.xml`; `contracts\robots\two_joint_arm.py`; `contracts\scenario.md`; `robot_learning\scenario\environment.py`.
- **[Reasoned implication — discriminating evidence]** A limit-aware inverse-kinematic reachability map and episode traces of target bearing, q1/q2, branch, endpoint error, and first-reach time would distinguish a true geometric/limit failure from a trajectory or timing failure.

### Direct motor control couples travel, convergence, and hold

**[Reasoned implication]** With standard MuJoCo `motor` semantics, gear 5 maps each unit control to five units of hinge generalized effort; with the declared control range, nominal effort is bounded at +/-5 per joint (equivalent to N m under the usual SI interpretation). This is a torque-like command, not a desired joint position or a configured lower-level position servo. The policy therefore has to generate the motion and any braking through two bounded commands held for 20 ms at a time. Sources: `contracts\robots\two_joint_arm.xml`; `robot_learning\scenario\environment.py` (`step`); `robot_learning\scenario\policy_io.py`.

**[Reasoned implication]** The 2 s hold consumes 100 of at most 500 control steps. If the first in-tolerance sample is at step 401, a perfect 100-sample uninterrupted run can finish at step 500; later arrival cannot succeed within the episode. Distance, not velocity, defines the tolerance, but any sampled excursion beyond 1 cm resets the hold. A fast arrival can therefore be worse than a slower arrival with low residual endpoint velocity. Sources: `contracts\scenario.md`; `contracts\task_spec.py`; `robot_learning\scenario\environment.py` (`step`).

**[Reasoned implication]** Zero gravity and disabled target/ground contact remove gravitational support and target-contact requirements. At zero joint velocity, zero motor command is an equilibrium at any interior posture; the declared viscous damping dissipates motion but is not a position-restoring controller. It can help settle a moving arm, but it cannot pull an incorrectly placed endpoint toward the target. Holding success consequently requires reaching an in-tolerance posture and managing residual motion; the task supplies no external force that pins the endpoint there. Sources: `contracts\robots\two_joint_arm.xml`; `robot_learning\scenario\environment.py`.

- **[Reasoned implication — decision relevance]** The task couples gross movement, braking/settling, and persistence for 2 s; optimizing first contact or minimum distance alone cannot establish episode success. Trajectory and hold diagnostics are decision-relevant alongside the binary outcome.
- **[Reasoned implication — assumptions]** The effort interpretation assumes standard MuJoCo motor transmission and the default identity action map; a saved candidate may implement a different action mapping. The equilibrium statement assumes no external disturbance and a posture away from active joint-limit constraints.
- **[Reasoned implication — sources]** `contracts\robots\two_joint_arm.xml`; `contracts\task_spec.py`; `contracts\scenario.md`; `robot_learning\scenario\environment.py`; `contracts\policy_runtime.py`.
- **[Reasoned implication — discriminating evidence]** Applied commands, saturation, qvel and endpoint speed at first tolerance, time-to-first-reach, consecutive held run length, hold interruptions, and truncation together separate insufficient authority, overshoot, slow convergence, and hold instability.

### Multiple postures and the usable observation

**[Reasoned implication]** A generic reachable planar target has two inverse-kinematic postures with opposite elbow signs. They are distinct configurations, not redundant continuous freedom; the shoulder angle and end-effector orientation differ between them. Joint limits can make one branch infeasible for some bearings, while the other remains feasible. Since the reset starts at q2 = 0, selecting a branch also determines which way the elbow initially bends away from the singular extension. Sources: `contracts\robots\two_joint_arm.xml`; `robot_learning\scenario\observations.py`.

**[Reasoned implication]** Under the current default observation, qpos and known link lengths determine the endpoint by forward kinematics; subtracting the supplied endpoint-minus-target vector reconstructs target position. qvel supplies joint motion, and the four IK residuals present both candidate configurations relative to the current joints. The default simulated task therefore does not require visual target detection or latent-state inference for position reaching. This is an information-rich simulator observation, not evidence of equivalent real-robot sensing. Sources: `robot_learning\scenario\observations.py`; `robot_learning\scenario\policy_io.py`; `contracts\robots\two_joint_arm.xml`.

- **[Reasoned implication — decision relevance]** Branch feasibility/proximity and the policy's actual observation can change a controller's path and learning burden; conclusions based on the default observation apply only when the candidate preserves it.
- **[Reasoned implication — assumptions]** Reconstruction assumes the candidate uses the current `reach_observation`, fixed model geometry, and the current target convention. A candidate-specific saved runtime can replace those functions.
- **[Reasoned implication — sources]** `robot_learning\scenario\observations.py`; `robot_learning\scenario\policy_io.py`; `contracts\policy_runtime.py`; `contracts\instruments.md`.
- **[Reasoned implication — discriminating evidence]** Inspecting the candidate's saved I/O and comparing its observation to qpos, qvel, target, and both IK solutions will establish which physical state is actually available and whether action commands retain the default meaning.

### Training coverage and behavior-wide quantities

**[Reasoned implication]** If the current training constructor is used unchanged, it omits radii 0.06-0.14 m. Under the contract's uniform radial sampling, that omitted interval is 8/14, or about 57%, of the official radius probability mass; full angular coverage does not compensate for missing radial cases. The training reward's shaping terms also do not substitute for the official hold-based episode outcome. Sources: `robot_learning\training\environment.py`; `robot_learning\training\reward.py`; `contracts\scenario.md`; `robot_learning\scenario\environment.py` (`_sample_target_position`).

**[Reasoned implication]** To explain complete episodes, scientifically meaningful quantities span: target radius/bearing and reset error; q1/q2, qvel, branch and joint-limit margin; endpoint position/error/velocity; applied control, delivered effort and saturation; time to first tolerance, minimum error, uninterrupted hold duration, interruptions, and episode completion/truncation. Success stratified by radius and bearing distinguishes geometric and directional biases from general instability. The current research diagnostics cover only a subset: target coordinates, distance, reach step, hold counts/interruption, and outcome. Sources: `robot_learning\scenario\evaluation.py`; `robot_learning\scenario\environment.py`; `contracts\scenario.md`.

- **[Reasoned implication — decision relevance]** Training coverage and complete-trajectory measurements can change whether early results are interpreted as general task competence, outer-radius specialization, late reaching, or failure to stabilize.
- **[Reasoned implication — assumptions]** The 57% calculation assumes the official radius law is uniform in radius, as specified by the task description and implemented by the visible sampler; it is not an area-uniform annulus calculation.
- **[Reasoned implication — sources]** `contracts\scenario.md`; `robot_learning\scenario\environment.py`; `robot_learning\training\environment.py`; `robot_learning\scenario\evaluation.py`.
- **[Reasoned implication — discriminating evidence]** A target histogram and success/first-reach/hold outcomes by radius and bearing, paired with action and joint-state traces, would show whether failures cluster in unsampled radii, particular directions, or the convergence/hold phase.

## Unknowns

### Compiled inertia and effort-to-motion response

**[Unresolved quantity]** The XML provides link shape, joint damping, armature, and motor gear, but no explicit body masses, inertias, or geom density. The exact compiled mass matrix, torque-to-acceleration response, transient settling time, and effect of MuJoCo's undeclared integrator/solver defaults have not been established from source values alone. Thus the physical definitions do not show whether bounded motor effort can reach and settle every target within the remaining episode time.

- **[Unresolved quantity — decision relevance]** These values could change whether the main constraint is action authority, inertia/damping, or the policy's trajectory; they bear on control scale and the useful time available for settling.
- **[Unresolved quantity — assumptions]** This uncertainty is about the compiled MuJoCo model and its response under the pinned simulator, not about the explicit dimensions or joint coefficients.
- **[Unresolved quantity — sources]** `contracts\robots\two_joint_arm.xml`; `AGENTS.md` (pinned MuJoCo version); `robot_learning\scenario\environment.py`.
- **[Unresolved quantity — discriminating evidence]** Compiled-model masses/inertias and mass matrix, together with measured joint/endpoint response to bounded commands from representative poses, would resolve the numerical authority and transient scales.

### Meaning of “continuous” at the protected evaluation boundary

**[Unresolved quantity]** The official contract requires an uninterrupted 2 s hold and describes it as 100 consecutive control steps. The readable research implementation samples distance only after each 10-substep action. The available contract text does not establish whether the protected evaluator also rejects an excursion occurring and recovering entirely between control observations.

- **[Unresolved quantity — decision relevance]** This could change the required stabilization bandwidth and whether a policy passing the visible boundary-sampled check satisfies the official uninterrupted-hold criterion.
- **[Unresolved quantity — assumptions]** The uncertainty applies only to excursions within a 20 ms control interval; the required duration, tolerance, and control-step count are explicit.
- **[Unresolved quantity — sources]** `contracts\scenario.md`; `contracts\instruments.md` (`Saved controller execution`); `robot_learning\scenario\environment.py` (`step`).
- **[Unresolved quantity — discriminating evidence]** An authoritative protected-evaluator definition or an evaluation case with an out-of-tolerance substep excursion but in-tolerance control-boundary samples would determine the rule.

### Candidate-specific sensing and action mapping

**[Unresolved quantity]** The current default observation and identity action are known, but the I/O functions of any future candidate are not. The protected evaluator uses the saved runtime, so a later policy need not receive the current 11-value observation or issue an untransformed action.

- **[Unresolved quantity — decision relevance]** This changes whether conclusions about full-state observability, branch cues, or nominal torque commands actually apply to a candidate.
- **[Unresolved quantity — assumptions]** The saved-runtime contract is followed and the candidate artifact is inspected rather than inferred from current source alone.
- **[Unresolved quantity — sources]** `contracts\policy_runtime.py`; `contracts\instruments.md`; `robot_learning\scenario\policy_io.py`; `robot_learning\scenario\observations.py`.
- **[Unresolved quantity — discriminating evidence]** The saved candidate runtime, observation values, action transform, and clipped command trace identify the actual information and actuation path.

### Dynamic success and performance over the official panel

**[Unresolved quantity]** Geometric reachability does not establish that any learned policy reaches, settles, and holds the targets often enough to achieve 196/200 successes. No physical derivation here predicts that empirical success rate or how failures vary with radius, bearing, and time-to-reach.

- **[Unresolved quantity — decision relevance]** This is the central campaign uncertainty: it can change candidate selection and whether the 98% objective is met, despite all targets being statically reachable.
- **[Unresolved quantity — assumptions]** The criterion and 200-episode official panel remain fixed as defined by the human task contract.
- **[Unresolved quantity — sources]** `contracts\scenario.md`; `contracts\task_spec.py`; `robot_learning\scenario\evaluation.py`.
- **[Unresolved quantity — discriminating evidence]** Episode outcomes under the official distribution, supported by radius/bearing, first-reach, minimum-distance, hold-run, interruption, and truncation diagnostics, distinguish failure mechanisms; the protected final assessment determines the stated panel objective.

### Scope beyond the simulated robot

**[Unresolved quantity]** The repository defines a MuJoCo model and simulated state/action interface, not a calibrated physical arm, hardware sensor suite, actuator electronics, or sim-to-real correspondence. No claim about hardware reach, torque, sensing, or transfer follows from this model alone.

- **[Unresolved quantity — decision relevance]** This matters if conclusions are extended from the official simulated benchmark to a physical robot; it does not alter the specified simulation-only campaign objective.
- **[Unresolved quantity — assumptions]** The campaign's success criterion remains the official simulated task rather than an unstated hardware deployment requirement.
- **[Unresolved quantity — sources]** `contracts\scenario.md`; `contracts\robots\two_joint_arm.xml`; `contracts\policy_runtime.py`.
- **[Unresolved quantity — discriminating evidence]** Hardware geometry, inertial and actuator calibration, sensor timing/noise measurements, and matched simulated-versus-physical trajectories would be needed for transfer claims.

## Decision-relevant synthesis

### Static targets are reachable, but every episode starts at a singular extension

**[Reasoned implication]** The 6-20 cm target centers fit the 12/10 cm arm's joint-limited planar workspace with at least one feasible elbow branch; reset is fully extended and Jacobian-singular, with initial target error from 2 to 42 cm.

- **[Reasoned implication — decision relevance]** Early interpretation should separate the singular-start trajectory and branch choice from workspace impossibility.
- **[Reasoned implication — assumptions]** Declared rigid geometry, joint limits, planar target placement, and no additional obstacle constraint.
- **[Reasoned implication — sources]** `contracts\robots\two_joint_arm.xml`; `contracts\robots\two_joint_arm.py`; `robot_learning\scenario\environment.py`; `contracts\scenario.md`.
- **[Reasoned implication — discriminating evidence]** Joint/endpoint trajectories and first-reach time by target radius and bearing, checked against a limit-aware IK map.

### Success is torque-driven motion plus a timed hold, not a reach event

**[Reasoned implication]** The default loop is two bounded motor commands held for 20 ms; the task allows 10 s total and requires 2 s (100 steps) uninterrupted within 1 cm, leaving at most 400 preceding steps if the first in-tolerance sample is step 401.

- **[Reasoned implication — decision relevance]** The behavior must arrive with enough control authority and low enough residual motion to persist; reach-only metrics or reward cannot settle the campaign objective.
- **[Reasoned implication — assumptions]** Current identity action map and the contract's 100-step control timing; protected substep checking remains unresolved above.
- **[Reasoned implication — sources]** `contracts\task_spec.py`; `contracts\scenario.md`; `contracts\robots\two_joint_arm.xml`; `robot_learning\scenario\environment.py`.
- **[Reasoned implication — discriminating evidence]** Time-to-first-tolerance, entry speed, command saturation, consecutive hold length, interruptions, and episode outcome.

### The exact dynamic authority is not numerically established

**[Unresolved quantity]** Mass/inertia and compiled-model response determine how the gear-scaled motor input moves and settles the arm; the XML does not state the needed inertial quantities explicitly.

- **[Unresolved quantity — decision relevance]** This could change whether early control difficulty is effort-limited or policy-limited and how much horizon is practically available for settling.
- **[Unresolved quantity — assumptions]** MuJoCo compiles the declared geoms and defaults under the repository's pinned version.
- **[Unresolved quantity — sources]** `contracts\robots\two_joint_arm.xml`; `AGENTS.md`; `robot_learning\scenario\environment.py`.
- **[Unresolved quantity — discriminating evidence]** Compiled inertial/mass-matrix values and bounded-command response traces from the reset and representative target postures.

### The current training range omits most official radial probability mass

**[Reasoned implication]** Current training covers 14-20 cm while the official contract covers 6-20 cm; under uniform radius, 57% of official radial probability lies below the current training minimum.

- **[Reasoned implication — decision relevance]** A result from the unchanged training constructor cannot by itself establish performance across the official radial distribution.
- **[Reasoned implication — assumptions]** Uniformity is in radius and angle, as in the visible target sampler and the task's radial-band definition.
- **[Reasoned implication — sources]** `robot_learning\training\environment.py`; `robot_learning\scenario\environment.py`; `contracts\scenario.md`.
- **[Reasoned implication — discriminating evidence]** Actual training-target coverage and official-distribution success stratified across the omitted inner radii.

### Verify the candidate's actual I/O and the protected hold rule

**[Unresolved quantity]** The current observation is direct simulator state with two IK-branch cues, but saved candidates may replace observation/action functions; protected substep continuity is not established by the readable research checker.

- **[Unresolved quantity — decision relevance]** These determine what the controller can know, what its outputs physically command, and whether boundary-sampled holding matches official success.
- **[Unresolved quantity — assumptions]** Candidate runtime functions are frozen and executed as specified; the contract's uninterrupted-hold requirement is authoritative.
- **[Unresolved quantity — sources]** `contracts\policy_runtime.py`; `contracts\instruments.md`; `robot_learning\scenario\observations.py`; `robot_learning\scenario\environment.py`; `contracts\scenario.md`.
- **[Unresolved quantity — discriminating evidence]** The saved I/O and clipped command trace, plus an authoritative protected-evaluator rule or boundary-case evaluation of substep excursions.
