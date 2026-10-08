# Scientific model: two-joint arm reach-and-hold

## Established facts

### Task and episode semantics

- **[Repository fact]** The official target is sampled at a radius of 6–20 cm from the base over the full angular range. Success requires the end effector to be within 1 cm of that target for 2 uninterrupted seconds. At the official 20 ms control interval, this is 100 consecutive successful control steps; an episode has at most 500 control steps. Sources: `contracts/scenario.md:7-31`; `contracts/task_spec.py:6-11`.
- **[Repository fact]** The official result is binary per episode. The held-out assessment uses 200 episodes, and at least 196 successes are required for the 98% campaign objective. Sources: `contracts/scenario.md:17-31`.
- **[Repository fact]** The accessible environment samples angle and radius independently and uniformly from the configured ranges, places the target in the arm's horizontal plane, and treats the target as a MuJoCo mocap body. Sources: `robot_learning/scenario/environment.py:83-97`; `contracts/robots/two_joint_arm.xml:25-27`.

### Morphology, geometry, and constraints

- **[Repository fact]** The robot is a serial planar two-revolute-joint arm. The shoulder and elbow axes are both the world/body z axis. The upper arm is 0.12 m, the forearm is 0.10 m, and the end-effector site is at the forearm tip. Sources: `contracts/robots/two_joint_arm.xml:9-21`; `contracts/robots/two_joint_arm.py:5-7`.
- **[Repository fact]** The shoulder and elbow each declare a range of -170 to 170 degrees. The arm's plane is at z = 0.02 m after reset. The plane, base, and target explicitly disable collision; the link capsules do not specify collision filters, so their effective self-collision behavior follows MuJoCo defaults. There is no authored obstacle or target contact. Sources: `contracts/robots/two_joint_arm.xml:6-20,25-27`; `robot_learning/scenario/environment.py:90-97,109-114`.
- **[Reasoned implication]** With joint coordinates \(q=(q_s,q_e)\), the end-effector position is
  \(p=(0.12\cos q_s+0.10\cos(q_s+q_e),\ 0.12\sin q_s+0.10\sin(q_s+q_e),\ 0.02)\). Ignoring joint limits, the planar workspace is the annulus from 0.02 m to 0.22 m. Sources: `contracts/robots/two_joint_arm.xml:12-20`; `contracts/robots/two_joint_arm.py:5-7`.

### Simulator, actuation, and timing

- **[Repository fact]** MuJoCo is configured with zero gravity and a 0.002 s physics timestep. Each policy action is clipped to [-1, 1] per joint, written directly to the two motor controls, and held for 10 MuJoCo steps. Sources: `contracts/robots/two_joint_arm.xml:1`; `robot_learning/scenario/environment.py:52-68,122-133`.
- **[Repository fact]** Each motor has gear 5. Each joint declares damping 0.5 and armature 0.01. No explicit actuator dynamics, motor force range, link mass, link inertia, friction, or external disturbance is authored in the robot XML. Sources: `contracts/robots/two_joint_arm.xml:13-18,30-33`.
- **[Reasoned implication]** The policy-to-plant loop runs at 50 Hz with zero-order-hold commands. Under MuJoCo motor semantics, a scalar command \(u_i\) produces nominal generalized motor effort \(5u_i\); the actual acceleration also depends on the configuration-dependent link inertia, armature, damping, and any active joint-limit constraint. Sources: `contracts/robots/two_joint_arm.xml:1,13-18,30-33`; `robot_learning/scenario/environment.py:125-133`.

### Reset and sensing

- **[Repository fact]** Every reset sets both joint positions and velocities to zero, forwards the model, then samples a new target. The initial end effector is therefore at approximately (0.22, 0, 0.02) m, fully extended along +x. Sources: `robot_learning/scenario/environment.py:102-120`; `contracts/robots/two_joint_arm.xml:12-20`.
- **[Repository fact]** The 11-dimensional observation contains the two joint positions, two joint velocities, the three-dimensional end-effector-to-target displacement, and four signed angular residuals to the open-elbow and folded-elbow inverse-kinematic solutions. Sources: `robot_learning/scenario/observations.py:11-49`.
- **[Repository fact]** The observation has no explicit hold counter, episode time, target radius, target angle, acceleration, force, contact, or previous-action field. The target and end-effector positions used to construct it are exact simulator values, with no sensor-noise model in the accessible implementation. Sources: `robot_learning/scenario/observations.py:27-49`; `robot_learning/scenario/environment.py:75-100`.

### Outcome and learning signal

- **[Repository fact]** After each control interval, distance is tested against 0.01 m. Being outside resets the consecutive hold count to zero; reaching 100 held steps terminates successfully. The evaluator separately records first reach, minimum and final distance, maximum held steps, in-tolerance steps, and hold interruptions. Sources: `robot_learning/scenario/environment.py:134-168`; `robot_learning/scenario/evaluation.py:52-106`.
- **[Repository fact]** The current reward combines distance progress, a closeness potential, linear hold-progress credit, a small action cost, an outside-band penalty after a hold interruption, and a completion bonus. Reward is not the official success criterion. Sources: `robot_learning/training/reward.py:16-25,57-107`; `contracts/scenario.md:17-21`.

## Physical consequences

### Reachability and inverse-kinematic alternatives

- **[Reasoned implication]** Every official target radius is strictly inside the unconstrained workspace annulus: 0.06–0.20 m lies between 0.02 and 0.22 m. The two analytic elbow branches are
  \(q_e=\pm\arccos((r^2-0.12^2-0.10^2)/(2\cdot0.12\cdot0.10))\), with approximately 49–150 degrees of elbow magnitude over the official radius range. Sources: `contracts/scenario.md:7-13`; `contracts/robots/two_joint_arm.py:5-7`; `robot_learning/scenario/observations.py:27-35`.
- **[Reasoned implication]** The corresponding shoulder angle is \(q_s=\theta-\operatorname{atan2}(0.10\sin q_e,\ 0.12+0.10\cos q_e)\), modulo \(2\pi\). The two branches are physically distinct and generally both usable; the ±170-degree shoulder limit can remove one branch in angular sectors, while the other remains available for the official annulus. Sources: `contracts/robots/two_joint_arm.xml:13-18`; `robot_learning/scenario/observations.py:18-47`.
- **[Reasoned implication — decision relevance]** Branch choice can change the first controller representation or exploration strategy, especially near joint-limit sectors. It does not require a single globally preferred posture.
- **[Reasoned implication — assumptions]** This implication assumes the authored link lengths and native MuJoCo joint-limit semantics, with no active link self-contact in the selected posture.
- **[Reasoned implication — discriminating evidence]** For each radius-angle cell, forward-kinematically evaluate both branches and record valid-limit status, then compare approach and hold margins for the surviving branches. A branch-dependent failure pattern would weaken the claim that branch choice is interchangeable.

### Initial state, singularity, and trajectory control

- **[Reasoned implication]** The reset configuration \(q=(0,0)\) is fully extended. The planar Jacobian has rank one there because its determinant is proportional to \(0.12\cdot0.10\sin q_e\). The controller cannot initially command arbitrary Cartesian velocity; it must first create elbow bend before obtaining full two-dimensional local control. Sources: `robot_learning/scenario/environment.py:109-114`; `contracts/robots/two_joint_arm.xml:12-20`.
- **[Reasoned implication]** Initial target distance can range from about 0.02 m to 0.42 m. Targets opposite the initial arm direction require a large angular reorientation, while targets near the initial direction can still require inward motion from the 0.22 m initial reach. Sources: `robot_learning/scenario/environment.py:83-97,109-118`.
- **[Reasoned implication — decision relevance]** A first policy may need a reach trajectory that deliberately leaves the reset singularity and manages velocity, rather than a purely local Cartesian correction. Evaluation should distinguish slow convergence from failure to stabilize.
- **[Reasoned implication — assumptions]** The conclusion uses the exact reset and point-kinematic model; it assumes no actuator saturation beyond the documented command bound changes the qualitative rank argument.
- **[Reasoned implication — discriminating evidence]** Measure first-reach time, peak joint velocity, and path length by initial target angle and radius. Persistent slow or overshooting behavior only from the reset state would support a singularity/trajectory explanation.

### Dynamic control authority and stabilization

- **[Reasoned implication]** With gravity and explicit plane, base, and target contact absent, a configuration with zero joint velocity and zero motor command is an equilibrium when no link self-contact is active. Damping dissipates velocity, but finite inertia and the 20 ms command hold can carry the end effector outside the 1 cm tolerance after entry. Sources: `contracts/robots/two_joint_arm.xml:1,6-20,25-27`; `robot_learning/scenario/environment.py:125-143`.
- **[Reasoned implication]** Reaching and holding are coupled through the same nonlinear Jacobian: a joint correction that reduces radial error can create tangential error, and braking one joint changes both end-effector coordinates. The final behavior therefore requires convergence with low residual velocity, not merely a single close sample.
- **[Reasoned implication — decision relevance]** If the plant settles naturally inside the tolerance, a simple terminal stabilizing behavior may suffice; if not, the policy must learn active velocity shaping and possibly branch-specific local control.
- **[Reasoned implication — assumptions]** These implications assume the target remains fixed and that no active link self-contact or external disturbance is present in the selected posture.
- **[Reasoned implication — discriminating evidence]** From states just inside tolerance, compare zero command, small constant commands, and state-feedback rollouts using distance, radial/tangential error, and exit probability over 100 steps. A high zero-command retention rate supports passive stabilization; repeated exits require active correction.

### Hold semantics and failure classes

- **[Reasoned implication]** The task has qualitatively different failure classes: unreachable or limit-infeasible posture, slow or misdirected reach, overshoot during convergence, and interruption during an otherwise successful hold. The last class is decisive because one outside-tolerance control sample resets all accumulated hold progress.
- **[Reasoned implication]** The 1 cm tolerance is a disk in the arm plane, and the 100-step condition samples that disk only at 50 Hz. A continuous-time excursion between samples is not represented by the official success state, whereas an excursion visible at any sampled control boundary breaks the hold.
- **[Reasoned implication — decision relevance]** Aggregate success alone cannot identify the limiting mechanism. First-reach and hold-interruption diagnostics can change whether research should emphasize global reaching, local stabilization, or robustness margins.
- **[Reasoned implication — assumptions]** This interpretation treats the environment's post-integration distance test as authoritative for the discrete task, as specified by `environment.py`.
- **[Reasoned implication — discriminating evidence]** Stratify episodes by first-reach step, maximum held steps, interruptions, minimum distance, and final distance. Reach failures with no in-tolerance samples support a global-control issue; high first reach but low completion supports stabilization or timing margins.

### Observation, control, and task information

- **[Reasoned implication]** The observation is physically sufficient for the instantaneous plant state and target-relative geometry under the fixed model: joint positions and velocities are present, and the relative displacement directly gives distance and direction. Since the target is fixed, target velocity is not needed for Markov physical control.
- **[Reasoned implication]** Target radius and angle are not explicit but are recoverable from the relative displacement and known end-effector position; the four IK residuals additionally expose both posture alternatives. The observation does not reveal the hidden hold counter, so the physical state is Markov while the augmented success automaton is not fully observable from one observation.
- **[Reasoned implication — decision relevance]** A memoryless state-feedback policy should be physically capable of reaching and stabilizing, but it cannot condition explicitly on elapsed hold progress without using its own history or a learned recurrent state. Reward-driven behavior must therefore favor indefinite retention, not merely timed entry.
- **[Reasoned implication — assumptions]** This conclusion assumes exact observation values and the fixed target semantics in the accessible environment.
- **[Reasoned implication — discriminating evidence]** Re-run identical physical states with different hidden hold counters and compare observations; identical observations with different remaining success time confirm task-automaton partial observability. Compare memoryless and history-dependent policies only if the observed diagnostics show a hold-counter-related failure.

### Scientifically meaningful quantities

- **[Reasoned implication]** The most informative physical quantities are target radius and angle; joint position, velocity, and acceleration; end-effector position and radial/tangential error; distance-to-target; Jacobian conditioning or manipulability; motor command and inferred effort; first-reach time; peak speed; time in tolerance; hold interruptions; and final settling error. These quantities connect morphology, dynamics, control, and the binary outcome.
- **[Reasoned implication — decision relevance]** They separate geometry-limited, actuation-limited, transient, and stabilization-limited behavior, preventing reward or success percentage from being mistaken for a mechanism.
- **[Reasoned implication — assumptions]** Acceleration, effort, Jacobian, and conditioning are derived quantities that require access to simulator state and the exact model, while the official evaluator exposes only a subset directly.
- **[Reasoned implication — discriminating evidence]** Episode-level diagnostic records plus targeted simulator traces can support or revise the causal classification; a failure mode should not be treated as established unless it is localized consistently across comparable target geometries.

## Unknowns

### Effective mass, inertia, and numerical dynamics

- **[Unresolved quantity]** The XML does not state link mass, density, inertia tensors, integrator choice, solver settings, or other MuJoCo defaults. The compiler therefore determines important parts of \(M(q)\) and the discrete-time response from geometry and defaults that are not explicit in the authored robot definition. Source: `contracts/robots/two_joint_arm.xml:1-33`.
- **[Unresolved quantity — decision relevance]** This can change the achievable acceleration, braking distance, action scale, and whether a policy trained on one control pattern transfers across candidate recipes.
- **[Unresolved quantity — assumptions]** The concern matters only if the inferred defaults or numerical integration materially affect motion at 20 ms control resolution; zero gravity and the absence of authored external contacts remain fixed, while link self-contact is treated separately below.
- **[Unresolved quantity — discriminating evidence]** Inspect the compiled model's masses, inertias, actuator transmission, integrator, and solver settings, then measure one-step and multi-step responses from representative configurations. Agreement with predicted responses would narrow the uncertainty; unexplained response differences would revise the model.

### Link self-collision semantics

- **[Unresolved quantity]** The upper-arm and forearm capsule geoms omit `contype` and `conaffinity`, unlike the plane, base, and target. It is therefore unresolved from the authored XML whether native collision filtering permits link-link contacts in folded configurations and how those contacts affect the dynamics. Source: `contracts/robots/two_joint_arm.xml:6-20,25-27`.
- **[Unresolved quantity — decision relevance]** If folded postures contact, one analytic IK branch may be dynamically unavailable or may introduce contact impulses, changing branch selection and hold reliability.
- **[Unresolved quantity — assumptions]** This matters only for configurations in which the capsule geometries overlap or approach closely and native MuJoCo filtering does not exclude their contact.
- **[Unresolved quantity — discriminating evidence]** Inspect compiled contact pairs and roll out both IK branches across the target grid while recording contact count, impulses, and distance. No contacts across the grid would remove this concern; branch-localized contacts would revise the reachable-posture model.

### Closed-loop control margin

- **[Unresolved quantity]** It is not known before campaign evidence whether ±5 nominal motor effort, 0.5 damping, and 0.01 armature provide enough authority to stop every target trajectory within a 1 cm disk without repeated boundary crossings.
- **[Unresolved quantity — decision relevance]** This determines whether the first useful direction should prioritize global reach, local stabilizing control, action representation, or reward shaping.
- **[Unresolved quantity — assumptions]** The uncertainty depends on the actual compiled inertia and on the policy's ability to estimate velocity from the four observed joint-velocity components.
- **[Unresolved quantity — discriminating evidence]** Controlled rollouts from matched near-target states, reporting velocity, command, distance, and 100-step retention, would support adequate margin if retention is high across geometry; systematic exits at high speed or near limits would weaken it.

### Distributional difficulty across geometry

- **[Unresolved quantity]** The physical model establishes reachability, but it does not establish how a learned policy's success varies across radius, angle, branch availability, or distance from the reset singularity.
- **[Unresolved quantity — decision relevance]** A uniform aggregate can conceal a narrow angular or radial failure region that prevents the required 196/200 official successes.
- **[Unresolved quantity — assumptions]** This matters if policy approximation or exploration, rather than plant reachability alone, is the limiting factor.
- **[Unresolved quantity — discriminating evidence]** Use fixed-seed or stratified development panels with per-episode radius, angle, first reach, and hold diagnostics. Concentrated failures in one geometric stratum support a geometry-conditioned learning problem; broad failures support a common control problem.

### Reward-to-behavior relationship

- **[Unresolved quantity]** The current reward gives linear credit for accumulated hold steps and gives no hold-progress forfeiture fraction when a hold exits, while the official criterion requires an uninterrupted hold. It is unknown whether the resulting learning signal sufficiently distinguishes durable stabilization from repeated brief entries.
- **[Unresolved quantity — decision relevance]** This can change whether reward terms or policy/training changes are needed even though the physical plant is unchanged.
- **[Unresolved quantity — assumptions]** The issue matters only to learning dynamics; evaluation still uses the environment's binary uninterrupted-hold semantics.
- **[Unresolved quantity — discriminating evidence]** Compare reward totals with completion, maximum held steps, and interruption counts. High reward with low completion would weaken the reward's alignment and justify revising that interpretation; aligned reward and completion would support retaining it.

## Decision-relevant synthesis

### Reset singularity and global reach

- **[Reasoned implication — decision relevance]** The arm starts fully extended at a rank-deficient Jacobian, so early trajectory generation may dominate opposite-angle and inward-reaching failures.
- **[Reasoned implication — assumptions]** Exact zero-position reset, planar two-link kinematics, and no active link contact at reset.
- **[Repository fact — source references]** `robot_learning/scenario/environment.py:102-120`; `contracts/robots/two_joint_arm.xml:12-20`.
- **[Reasoned implication — discriminating evidence]** First-reach time and peak-speed/path diagnostics stratified by target angle and radius; concentration near the reset-opposed directions supports this consequence.

### Unknown dynamic margin

- **[Unresolved quantity — decision relevance]** Unspecified compiled inertia and numerical defaults determine whether the available motor effort can brake and hold within 1 cm at 50 Hz.
- **[Unresolved quantity — assumptions]** MuJoCo defaults materially contribute to the plant response and are not replaced by an external disturbance model.
- **[Repository fact — source references]** `contracts/robots/two_joint_arm.xml:1,13-18,30-33`; `robot_learning/scenario/environment.py:125-133`.
- **[Unresolved quantity — discriminating evidence]** Compiled-model parameters and near-target 100-step retention traces; measured overshoot or repeated hold exits would revise the assumed control margin.

### Potential link self-contact

- **[Unresolved quantity — decision relevance]** If folded-link contact is active, branch-aware behavior may be more important than the nominal two-solution kinematic picture, and contact transients may become a separate hold failure mode.
- **[Unresolved quantity — assumptions]** Native collision filtering and the capsule geometry determine whether this affects official target postures.
- **[Repository fact — source references]** `contracts/robots/two_joint_arm.xml:6-20,25-27`.
- **[Unresolved quantity — discriminating evidence]** Compiled contact-pair inspection and branch-conditioned contact traces would distinguish a purely free-space arm from a contact-constrained one.

### Branch and joint-limit geometry

- **[Reasoned implication — decision relevance]** The target set is reachable, but one of the two IK postures can be excluded in angular sectors by the ±170-degree shoulder limit; branch-aware behavior may protect coverage.
- **[Reasoned implication — assumptions]** Native joint-limit enforcement and the authored 0.12/0.10 m link lengths.
- **[Repository fact — source references]** `contracts/robots/two_joint_arm.xml:13-20`; `robot_learning/scenario/observations.py:18-47`.
- **[Reasoned implication — discriminating evidence]** A radius-angle feasibility map and failure/hold statistics by branch residual; localized failures where only one branch remains would support branch-sensitive control.

### Hold completion is the governing bottleneck

- **[Reasoned implication — decision relevance]** The official objective counts no partial credit: any sampled exit resets progress, so a policy that reaches quickly but cannot remain inside the tolerance cannot approach 98%.
- **[Reasoned implication — assumptions]** The 20 ms post-integration samples and 100 consecutive-step rule remain authoritative.
- **[Repository fact — source references]** `contracts/scenario.md:7-21`; `robot_learning/scenario/environment.py:134-168`; `robot_learning/scenario/evaluation.py:90-106`.
- **[Reasoned implication — discriminating evidence]** Compare first reach with maximum held steps, interruption count, and final distance. High reach with low uninterrupted completion identifies stabilization as the decision frontier.
