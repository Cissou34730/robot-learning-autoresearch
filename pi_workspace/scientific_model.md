## Established facts

### Robot morphology and simulator

- **[Repository fact]** The MuJoCo model is a fixed-base planar serial arm with two hinge joints, both rotating about world-local \(z\): shoulder and elbow. The upper link is 0.12 m long with a 15 mm capsule radius; the forearm is 0.10 m long with a 12 mm capsule radius; the end-effector site is at the forearm tip. There is no wrist joint or commanded vertical motion. Sources: [robot geometry constants](../contracts/robots/two_joint_arm.py#L3-L7), [MJCF bodies and site](../contracts/robots/two_joint_arm.xml#L12-L20).
- **[Repository fact]** Each hinge has range \(-170\) to \(170\) degrees, damping 0.5 and armature 0.01. The model sets gravity to zero and the physics timestep to 0.002 s. The locked simulator is MuJoCo 3.12.0. Sources: [MJCF options and joints](../contracts/robots/two_joint_arm.xml#L2-L18), [runtime versions](../AGENTS.md#L15-L19).
- **[Repository fact]** Each joint is driven by a motor with control range \([-1,1]\) and gear 5. The XML has no explicit body mass, inertial block, geom density, solver choice or integrator choice. Link capsules have no explicit per-geom contact flags; the plane, base cylinder and target sphere explicitly disable contact. Sources: [MJCF geometry and actuators](../contracts/robots/two_joint_arm.xml#L4-L33).
- **[Repository fact]** The task measures Euclidean distance from the `end_effector` site to the target mocap position. The target is a 12 mm visual sphere with contact disabled; success is not defined by physical contact or by the rendered site/sphere surfaces. Sources: [target and site](../contracts/robots/two_joint_arm.xml#L19-L27), [distance and success check](../robot_learning/scenario/environment.py#L75-L80), [step semantics](../robot_learning/scenario/environment.py#L134-L163).

### Task, reset and assessment

- **[Repository fact]** The official task samples targets 6–20 cm from the base over the full angular range. The end effector must be within 1 cm for an uninterrupted 2 s; with the official timing this is 100 consecutive control steps. Episodes have at most 500 steps. Sources: [official task and success](../contracts/scenario.md#L7-L20), [task constants](../contracts/task_spec.py#L6-L11).
- **[Repository fact]** The final assessment uses one frozen policy on a fixed 200-episode panel; at least 196 episodes must succeed. This panel is distinct from the task-reference development panel. Source: [official final assessment](../contracts/scenario.md#L22-L31).
- **[Repository fact]** On reset, the accessible scenario environment zeros both joint positions and velocities, forwards the model, samples a target angle uniformly over \([-\pi,\pi]\) and radius uniformly over its configured interval, and sets target height to the end-effector height. The target then remains fixed for the episode. Its initial target radius defaults to the official 0.06–0.20 m interval. Sources: [reset and sampler](../robot_learning/scenario/environment.py#L83-L120), [task constants](../contracts/task_spec.py#L6-L11).
- **[Repository fact]** The scenario environment defaults to the official tolerance, duration, frame skip and horizon, but its source states that the protected benchmark enforces the human-defined task. The public scenario implementation is therefore evidence about its own execution semantics, not a substitute for the official contract. Sources: [scenario environment contract note and defaults](../robot_learning/scenario/environment.py#L1-L58), [immutable task boundary](../contracts/scenario.md#L32-L34).

### Control loop and observation

- **[Repository fact]** The baseline action space has two values in \([-1,1]\). Its `physical_action` mapping is the identity; the environment clips the result, writes it to `data.ctrl`, and holds it through ten MuJoCo steps before returning the next observation. Sources: [action space and stepping](../robot_learning/scenario/environment.py#L59-L72), [action application](../robot_learning/scenario/environment.py#L122-L134), [baseline policy I/O](../robot_learning/scenario/policy_io.py#L11-L16).
- **[Repository fact]** The accessible environment computes hold steps from `timestep × frame_skip`, checks distance once after the ten physics steps, increments the hold count when distance is at most 0.01 m, and resets that count when it is outside. It terminates at the required count and truncates at the configured episode limit. Sources: [timing setup](../robot_learning/scenario/environment.py#L47-L58), [hold and episode logic](../robot_learning/scenario/environment.py#L134-L163).
- **[Repository fact]** The baseline observation is an 11-element `float32` vector: two joint positions, two joint velocities, the three-dimensional end-effector-minus-target vector, and four wrapped joint-angle errors to the two analytic elbow-sign inverse-kinematic branches. The absolute target and its polar coordinates, acceleration, applied torque, contact force, hold count and episode clock are not direct observation fields; the target and distance are derivable from the observed joint state, link geometry and relative vector. There is no image input or sensor-noise model in this function. Source: [observation construction](../robot_learning/scenario/observations.py#L11-L48); the XML camera is not used by this function ([camera](../contracts/robots/two_joint_arm.xml#L8-L10)).
- **[Repository fact]** Protected evaluation executes the saved `io.observe`, policy runtime and optional normalizer, then saved `io.action`, followed by validation and clipping; it does not automatically call current research-environment code. Source: [saved controller execution](../contracts/instruments.md#L74-L86), [runtime implementation](../contracts/policy_runtime.py).

### Training signal and available diagnostics

- **[Repository fact]** The baseline training environment samples radii from 0.14–0.20 m, while the evaluation environment defaults to the official 0.06–0.20 m range. Training changes that target range without changing the shared reach/hold mechanics. Sources: [training environment](../robot_learning/training/environment.py#L12-L19), [evaluation environment](../robot_learning/scenario/environment.py#L169-L176).
- **[Repository fact]** The current training reward combines distance progress and closeness shaping, hold-progress and hold-completion bonuses, an action cost, and an outside-band penalty. Episode success remains the environment's uninterrupted-hold termination, not the reward value. Sources: [reward terms](../robot_learning/training/reward.py#L16-L25), [reward calculation](../robot_learning/training/reward.py#L49-L99), [success check](../robot_learning/scenario/environment.py#L134-L163).
- **[Repository fact]** Research evaluation records episode success, steps, target radius and angle, minimum and final distance, first in-tolerance step, maximum held steps, total in-tolerance steps and hold interruptions. It does not record full joint/torque trajectories in those diagnostics. Source: [research evaluation diagnostics](../robot_learning/scenario/evaluation.py#L47-L105).

## Physical consequences

### Reachability and inverse-kinematic alternatives

- **[Reasoned implication]** With \(L_1=0.12\) m, \(L_2=0.10\) m, shoulder angle \(q_1\), and relative elbow angle \(q_2\), the endpoint is \(x=L_1\cos q_1+L_2\cos(q_1+q_2)\), \(y=L_1\sin q_1+L_2\sin(q_1+q_2)\), \(z=0.02\) m. The unconstrained radial workspace is 0.02–0.22 m. For target radius \(r\), \(\cos q_2=(r^2-L_1^2-L_2^2)/(2L_1L_2)\); the two solutions use \(q_2=\pm\arccos(\cdot)\), with \(q_1=\theta-\operatorname{atan2}(L_2\sin q_2,L_1+L_2\cos q_2)\).
- **[Reasoned implication]** Across the official 0.06–0.20 m band, both elbow-sign solutions fit the \(\pm170^\circ\) joint limits for every target direction: \(|q_2|\) ranges from about \(150.1^\circ\) at 6 cm to \(49.5^\circ\) at 20 cm; the largest required shoulder magnitude is about \(157.6^\circ\). Thus official targets are geometrically reachable in two distinct postures; the task does not constrain end-effector orientation.
- **[Reasoned implication] Research decisions:** A failure should not initially be attributed to a target outside the nominal reachable set. The choice between branch-aware control, a single consistent branch, and other trajectory strategies could matter because two feasible joint postures lead to the same point.
- **[Reasoned implication] Assumptions:** This conclusion uses the stated link lengths, planar target height, joint limits and point-distance task; it does not establish equal dynamic difficulty or absence of contact effects along both paths.
- **[Repository fact] Source references:** [link lengths](../contracts/robots/two_joint_arm.py#L5-L7), [joint axes, ranges and endpoint](../contracts/robots/two_joint_arm.xml#L12-L20), [official target range](../contracts/task_spec.py#L6-L11), [branch features](../robot_learning/scenario/observations.py#L13-L48).
- **[Reasoned implication] Discriminating evidence:** Forward-kinematic endpoint residuals and joint-limit margins for both inverse solutions across target radius and angle would support or revise the geometric result; branch-conditioned trajectories and contact counts would distinguish their dynamic/path costs.

### Initial singularity and finite approach budget

- **[Reasoned implication]** Reset at \(q_1=q_2=0\) places the links fully extended at \((0.22,0,0.02)\) m. The planar endpoint Jacobian has determinant \(L_1L_2\sin q_2=0\) there and rank one: instantaneous endpoint velocity has no first-order radial component. Since the furthest official target radius is 0.20 m, every initial target is at least 0.02 m from the endpoint, outside the 0.01 m tolerance. Every episode therefore requires motion away from the singular start before a hold can begin.
- **[Reasoned implication]** Under the accessible environment's one-sample-per-control-step counter, a first in-tolerance sample later than step 401 cannot leave 100 samples before the 500-step limit. This leaves a bounded approach-and-settle interval; geometric reachability alone does not ensure completion in time.
- **[Reasoned implication] Research decisions:** Whether early failures reflect poor escape from full extension, slow approach, or late arrival could change which control and evaluation distinctions matter; this is different from changing the robot's reachable geometry.
- **[Reasoned implication] Assumptions:** The reset and endpoint-count semantics must match the controller evaluation; targets are fixed after reset and retain the stated height.
- **[Repository fact] Source references:** [reset](../robot_learning/scenario/environment.py#L102-L120), [endpoint kinematics](../contracts/robots/two_joint_arm.xml#L12-L20), [hold and horizon](../contracts/task_spec.py#L6-L11), [counter logic](../robot_learning/scenario/environment.py#L134-L163).
- **[Reasoned implication] Discriminating evidence:** Per-target initial error, joint and endpoint trajectories, first in-tolerance step, and maximum consecutive hold would separate failure to approach from failure to arrive before the hold budget.

### Torque control, dynamics and stabilization

- **[Reasoned implication]** With the baseline identity action map, each bounded command \(u_i\) produces nominally \(5u_i\) N·m at its hinge through the motor gear. This is joint-torque control, not a desired joint angle or Cartesian position. Away from active limits/contacts, the coupled dynamics have the form \(M(q)\ddot q+C(q,\dot q)\dot q+D\dot q=\tau\). Zero gravity removes posture-dependent weight torque; joint damping and armature still shape response. The command is unchanged for 10 physics substeps, so feedback is only refreshed at the outer control rate; conclusions do not establish transfer to a gravity-loaded arm.
- **[Reasoned implication]** Damping opposes motion but is not a spring toward the target; there is no authored position servo. Reaching the tolerance is therefore distinct from removing velocity and keeping the endpoint inside the 1 cm ball. A transient crossing can begin a hold and later reset it; successful control must manage approach, braking and sustained bounded error.
- **[Reasoned implication] Research decisions:** The relative importance of torque scaling, approach speed, braking, feedback rate and stabilization could change the controller or training objective considered; reward improvement alone is not evidence of uninterrupted task success.
- **[Reasoned implication] Assumptions:** The motor behaves as the direct MuJoCo motor defined here, no unmodeled disturbance dominates, and the protected evaluator applies the saved action through the documented validation/clipping path.
- **[Repository fact] Source references:** [motor and joint parameters](../contracts/robots/two_joint_arm.xml#L2-L18), [action application and substeps](../robot_learning/scenario/environment.py#L122-L134), [saved evaluation action path](../contracts/instruments.md#L74-L86).
- **[Reasoned implication] Discriminating evidence:** Joint position/velocity, applied command or torque, endpoint error and error rate over the approach and entire hold would distinguish insufficient authority, overshoot, slow settling and hold drift. Control-step samples alone cannot establish what happened between samples.

### Official distribution versus baseline training distribution

- **[Reasoned implication]** Under the shared sampler's independent uniform radius and angle, the official 6–20 cm interval assigns \(8/14=4/7\), about 57%, of radial probability to 6–14 cm, which the baseline training range excludes. These inner targets remain reachable but require more folded elbow postures: approximately \(101.5^\circ\) elbow magnitude at 14 cm and \(150.1^\circ\) at 6 cm, versus \(49.5^\circ\) at 20 cm. Uniform radius is not uniform area density; for the polar sampler, probability per unit area is higher at smaller radii.
- **[Reasoned implication]** Any baseline policy trained only on 14–20 cm must generalize to a substantial, more-folded part of the official task; this is a coverage/generalization gap, not proof that those targets are physically impossible. The shaped reward also remains only a proxy for the official episode-success count.
- **[Reasoned implication] Research decisions:** The gap could change the value of training-range coverage, radius-stratified evaluation, or branch-sensitive diagnostics when judging progress toward 98%.
- **[Reasoned implication] Assumptions:** The shared polar sampler realizes the official radial distribution, and the baseline training environment is the training recipe being considered; the official contract, not a research override, governs assessment.
- **[Repository fact] Source references:** [official task](../contracts/scenario.md#L7-L20), [shared target sampler](../robot_learning/scenario/environment.py#L83-L94), [training range](../robot_learning/training/environment.py#L12-L19), [official range](../contracts/task_spec.py#L6-L11), [reward](../robot_learning/training/reward.py#L49-L99).
- **[Reasoned implication] Discriminating evidence:** Episode success, first reach, maximum held steps and interruptions stratified by radius and angle would show whether the lower-radius region is a meaningful performance gap; they should be interpreted separately from aggregate shaped reward.

### Observation, hidden task state and measurable behavior

- **[Reasoned implication]** Given known link lengths, joint positions and the observed endpoint-minus-target vector, the target position is reconstructible from forward kinematics; current endpoint distance is also derivable. The four IK-error features expose errors to both analytic branches. The physical robot state needed for deterministic joint dynamics is therefore substantially observed (positions and velocities), although the representation is redundant.
- **[Reasoned implication]** The observation omits held-step count and remaining episode time. Two histories can have identical observed physical state and different hidden hold progress or horizon, so the observation is not Markov with respect to the complete finite-horizon task state. A controller that simply stabilizes the same target may not need that information; whether a particular learned policy benefits from memory or explicit task state is not established.
- **[Reasoned implication] Research decisions:** This distinction could change whether observation changes or recurrent state are worth considering, but only if progress/time aliasing affects success rather than merely reward accounting.
- **[Reasoned implication] Assumptions:** The saved candidate uses the documented observation, without additional history or external timing input; the current runtime contract permits a saved recurrent state but does not determine the eventual policy architecture.
- **[Repository fact] Source references:** [11-element observation](../robot_learning/scenario/observations.py#L11-L48), [hold/time state](../robot_learning/scenario/environment.py#L72-L73), [runtime recurrence](../contracts/policy_runtime.py), [protected saved-I/O contract](../contracts/instruments.md#L74-L86).
- **[Reasoned implication] Discriminating evidence:** Compare decisions and success for matched physical observations reached with different hold histories or remaining horizons, and inspect the saved runtime's actual observation and recurrence. No image-based inference is needed for the current numeric observation.

### Quantities that distinguish complete-episode behavior

- **[Reasoned implication]** Mechanistically useful quantities span the whole episode: target radius/angle; \(q,\dot q\) and endpoint error from reset through arrival; applied commands/torques and saturation; first in-tolerance step; in-tolerance run lengths and interruptions; final position/velocity; and total steps to success or truncation. Joint trajectory and command work can distinguish similar endpoint scores produced by different physical responses.
- **[Reasoned implication] Research decisions:** These quantities separate geometric acquisition, dynamic approach, braking, hold stability and target-sector generalization, whereas a single terminal success or total reward cannot identify which mechanism limited the episode.
- **[Reasoned implication] Assumptions:** Samples are timestamped at the control rate; claims about continuous-in-time occupancy require finer trajectory samples than the current research-evaluation summary records.
- **[Repository fact] Source references:** [existing per-episode diagnostics](../robot_learning/scenario/evaluation.py#L47-L105), [observation and hold info](../robot_learning/scenario/environment.py#L134-L168).
- **[Reasoned implication] Discriminating evidence:** Existing diagnostics can distinguish many reach-versus-hold outcomes, but joint-state and applied-torque traces (and, where relevant, within-step endpoint samples) would be needed to identify the underlying dynamics rather than only the outcome.

## Unknowns

### Compiled inertial and contact response

- **[Unresolved quantity]** The source XML does not state compiled link masses/inertias or the resulting \(M(q)\), accelerations and braking response. It also leaves solver/integrator settings and link-geom contact behavior to MuJoCo defaults; the actuated links do not explicitly disable contact.
- **[Reasoned implication] Decision relevance:** These quantities could change judgments about torque authority, branch/path viability, approach time and how much stabilization is dynamically difficult.
- **[Reasoned implication] Assumptions:** The compiled model uses the locked MuJoCo version and the XML shown; no external forces or model changes are introduced by the protected evaluator.
- **[Repository fact] Source references:** [MJCF inertial, option and geom declarations](../contracts/robots/two_joint_arm.xml#L2-L33), [locked MuJoCo version](../AGENTS.md#L15-L19).
- **[Reasoned implication] Discriminating evidence:** Compiled body masses/inertias and mass matrix at representative configurations, together with bounded torque-response trajectories and contact counts, would support or revise this account.

### Dynamic feasibility and success reliability

- **[Unresolved quantity]** Kinematic feasibility does not establish that a policy can reach each target, settle, and complete the uninterrupted hold within 500 steps, nor that at least 196 of the official 200 episodes will succeed. No such performance follows from the robot geometry alone.
- **[Reasoned implication] Decision relevance:** Observed time-to-reach, settling and hold failure rates could change whether the main limitation is approach, stabilization, target generalization or the policy's learned control.
- **[Reasoned implication] Assumptions:** Evaluation uses the official target distribution, saved policy I/O and success definition; aggregate development reward is not treated as episode success.
- **[Repository fact] Source references:** [official criterion and panel](../contracts/scenario.md#L18-L31), [research episode diagnostics](../robot_learning/scenario/evaluation.py#L47-L105), [task-reference semantics](../contracts/instruments.md#L512-L527).
- **[Reasoned implication] Discriminating evidence:** Completed per-episode outcomes and target-stratified reach/hold diagnostics can support development judgments; only the protected official assessment establishes the final panel result.

### Within-control-step hold semantics

- **[Unresolved quantity]** The public scenario checks one endpoint distance after ten 2 ms integrations. The official contract requires a complete uninterrupted 2 s hold and specifies 100 consecutive control steps, but the protected checker’s treatment of excursions between those control samples is not exposed here.
- **[Reasoned implication] Decision relevance:** This matters if a policy oscillates or briefly leaves tolerance inside a 20 ms action interval; control-rate diagnostics alone may not distinguish continuous occupancy from repeated endpoint samples.
- **[Reasoned implication] Assumptions:** The official contract is authoritative; the accessible environment is not assumed to reveal hidden protected implementation details.
- **[Repository fact] Source references:** [official hold wording](../contracts/scenario.md#L11-L20), [public post-substep check](../robot_learning/scenario/environment.py#L122-L158), [protected assessment boundary](../contracts/instruments.md#L74-L86).
- **[Reasoned implication] Discriminating evidence:** A protected trajectory or evaluator diagnostic sampled within each control interval would resolve the implementation detail; absent that evidence, conclusions should be limited to the stated 100-step contract.

### Significance of omitted hold/time state

- **[Unresolved quantity]** The exact baseline observation omits hold progress and step count, but whether that omission reduces success for a learned policy is unknown. The runtime can carry policy recurrence, while the eventual saved architecture and behavior do not yet exist.
- **[Reasoned implication] Decision relevance:** This could change whether adding task-state inputs or relying on memory is worth considering; it is not a limitation on the physical reachability result.
- **[Reasoned implication] Assumptions:** The relevant comparison holds current physical state and target fixed while varying only hold history or remaining time.
- **[Repository fact] Source references:** [observation fields](../robot_learning/scenario/observations.py#L37-L48), [hidden counters](../robot_learning/scenario/environment.py#L72-L73), [runtime state](../contracts/policy_runtime.py).
- **[Reasoned implication] Discriminating evidence:** Matched-state histories with different hold counts/time-to-truncation, evaluated through the actual saved runtime, would show whether policy outputs or success depend on the missing task state.

## Decision-relevant synthesis

### Official geometry is feasible; the reset is singular

- **[Reasoned implication] Decision relevance:** The official region has two joint-limit-feasible IK branches, so geometric impossibility is not the default explanation; every episode instead begins outside tolerance at a rank-deficient full extension. This can change whether first campaign reasoning centers on geometry or on leaving the initial pose and selecting a trajectory.
- **[Reasoned implication] Assumptions:** The contract lengths, target plane, joint limits and reset state match the evaluation model; dynamic path costs remain unproven.
- **[Repository fact] Sources:** [robot dimensions and limits](../contracts/robots/two_joint_arm.xml#L12-L20), [official target range](../contracts/task_spec.py#L6-L11), [reset](../robot_learning/scenario/environment.py#L102-L120).
- **[Reasoned implication] Discriminating evidence:** Branch-specific IK residuals, initial endpoint error, joint-limit margins and trajectories from reset by target angle/radius would support or weaken the implication.

### Success is a reach-and-stabilize problem under torque control

- **[Reasoned implication] Decision relevance:** A first tolerance crossing is not success: 100 consecutive control steps must follow, while bounded motor commands update only once per 20 ms in the accessible loop. This can change whether progress is judged by reaching speed, settling, or uninterrupted hold rather than by reward or minimum distance alone.
- **[Reasoned implication] Assumptions:** The public timing and motor map represent the candidate’s execution; protected substep handling remains as specified in the Unknowns register.
- **[Repository fact] Sources:** [motor and timestep](../contracts/robots/two_joint_arm.xml#L2-L18), [frame skip and hold logic](../robot_learning/scenario/environment.py#L47-L58), [official hold](../contracts/scenario.md#L11-L20).
- **[Reasoned implication] Discriminating evidence:** Full error and velocity traces through the hold, maximum consecutive held steps, and interruptions distinguish transient reach from stable completion.

### Baseline training omits much of the official radial range

- **[Reasoned implication] Decision relevance:** Under the shared uniform-radius sampler, about 57% of official radial probability lies below the baseline training minimum, where more-folded elbow postures are required. This can change how much weight to place on coverage/generalization when interpreting early candidate performance.
- **[Reasoned implication] Assumptions:** The baseline 14–20 cm range is used for training and the shared sampler realizes the official radial distribution.
- **[Repository fact] Sources:** [official range](../contracts/task_spec.py#L6-L11), [baseline training range](../robot_learning/training/environment.py#L12-L19), [polar sampler](../robot_learning/scenario/environment.py#L83-L94).
- **[Reasoned implication] Discriminating evidence:** Episode success, first reach and hold interruption stratified by target radius/angle would show whether this coverage gap changes outcomes.

### Quantitative dynamic margin remains unknown

- **[Unresolved quantity] Decision relevance:** The XML fixes torque scale, damping and armature but not explicit body inertias or measured response; this could change judgments about available approach time, braking and hold stability, despite geometric reachability.
- **[Reasoned implication] Assumptions:** MuJoCo compiles the declared geometry under the locked version and the protected model uses the same effective physics.
- **[Repository fact] Sources:** [MJCF dynamic declarations](../contracts/robots/two_joint_arm.xml#L2-L33), [MuJoCo version](../AGENTS.md#L15-L19), [official horizon](../contracts/task_spec.py#L6-L11).
- **[Reasoned implication] Discriminating evidence:** Compiled inertial values and torque-response traces across representative postures, paired with episode-level reach/hold diagnostics, would reveal whether dynamic margin or policy behavior is the consequential limit.
