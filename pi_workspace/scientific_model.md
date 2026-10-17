# Scientific model: two-joint arm reach-and-hold

Physical and scientific model of the robot and the task, constructed before any
training or campaign evidence. It states mechanisms and the evidence that
discriminates between them. It selects no intervention.

**Statement tags.** `[fact]` = repository fact (read from a human-owned or
current-scenario source). `[implication]` = reasoned implication derived from
facts, with the derivation given. `[unknown]` = unresolved quantity, with the
evidence that would resolve it.

**Source index** (for verification):

| Id | Source |
|---|---|
| S1 | `contracts/scenario.md` |
| S2 | `contracts/task_spec.py` |
| S3 | `contracts/robots/two_joint_arm.py` |
| S4 | `contracts/robots/two_joint_arm.xml` |
| S5 | `robot_learning/scenario/environment.py` |
| S6 | `robot_learning/scenario/observations.py` |
| S7 | `robot_learning/scenario/policy_io.py` |
| S8 | `robot_learning/training/environment.py` |
| S9 | `robot_learning/training/reward.py` |
| S10 | `robot_learning/training/current_params.json` |
| S11 | `robot_learning/train.py` |
| S12 | `robot_learning/scenario/evaluation.py` |
| S13 | `contracts/policy_runtime.py` |
| S14 | `contracts/instruments.md` |
| S15 | `AGENTS.md` |
| S16 | `robot_learning/training/candidate_checkpoint_callback.py` |
| S17 | `robot_learning/training/research_config.py` |
| S18 | `contracts/program.md` |
| S19 | `robot_learning/training/normalization.py` |

## Established facts

### 1. Immutable task boundary and robot definition

- `[fact]` The official task samples a target uniformly from 6–20 cm of the
  robot base, over the full angular range; the end effector must enter a 1 cm
  tolerance and remain continuously inside it for 2 s; an episode succeeds only
  when the complete uninterrupted hold is achieved; the objective is ≥ 98%
  episode success (≥ 196/200) on a fixed protected panel of 200 episodes of at
  most 500 control steps each. *(S1)*
- `[fact]` The immutable constants are `TARGET_RADIUS_RANGE = (0.06, 0.20)`,
  `MAX_EPISODE_STEPS = 500`, `FRAME_SKIP = 10`, `SUCCESS_THRESHOLD = 0.01`,
  `HOLD_SECONDS = 2.0`. *(S2)*
- `[fact]` The robot contract fixes `UPPER_ARM_LENGTH = 0.12`,
  `FOREARM_LENGTH = 0.10`, `MAX_REACH = 0.22`, and the MuJoCo model path. *(S3)*

### 2. Kinematics: morphology, constraints, workspace, task geometry

- `[fact]` The model is a fixed base plus two serial hinge joints, both with
  axis `0 0 1` (parallel, vertical), `range="-170 170"` degrees,
  `damping="0.5"`, `armature="0.01"`; the `upper_arm` body is offset
  `0 0 0.02` from the base, the `forearm` body `0.12 0 0` from the upper arm, and
  the `end_effector` site is 0.10 m along the forearm. *(S4)*
- `[fact]` Gravity is zero (`gravity="0 0 0"`), the physics timestep is
  `0.002` s, and `frame_skip = 10` gives a control period of 0.02 s (50 Hz);
  2 s of hold is therefore exactly `round(2.0/0.02) = 100` control steps,
  matching S1. *(S2, S4, S5)*
- `[implication]` Because both axes are vertical and no other degrees of freedom
  exist, every point of the arm stays in the plane `z = 0.02` for all time; the
  end-effector z coordinate is the constant 0.02. The arm is exactly a planar 2R
  manipulator with joint limits at ±170°.
- `[implication]` The target is placed at radius `r` and angle `θ` measured in
  the XY plane from the world origin, at the end effector's current z. Since the
  shoulder axis pierces the world origin in XY, the target radius *is* the
  shoulder-centred reach radius, and the 3-D distance to the target reduces
  exactly to the planar Euclidean distance `d = |EE − target|`; z contributes
  nothing. *(S5)*
- `[implication]` Workspace: radius `r(q2) = sqrt(L1² + L2² + 2 L1 L2 cos q2)`
  spans `[0.02, 0.22]`. The official annulus `[0.06, 0.20]` lies strictly inside
  with 0.02 m margin to full extension and 0.04 m margin to the folded
  singularity. Every official target is reachable.
- `[implication]` Inverse kinematics is analytic and unique up to the elbow
  branch: with `cos q2* = (r² − L1² − L2²)/(2 L1 L2)`, `|q2*|` equals 150.0° at
  `r = 0.06`, 101.5° at `r = 0.14`, 49.5° at `r = 0.20`; and
  `q1* = θ ∓ β(r)` with `β = atan2(L2 sin|q2*|, L1 + L2 cos q2*)` equal to
  56.3°, 44.4°, 22.3° at those radii. *(derived from S3, S4)*
- `[implication]` Joint limits are never binding at any official solution:
  `|q2*| ≤ 150°` (≥ 20° margin) and `wrap(q1*) ≤ 180° − β(r) ≤ 157.7°`
  (≥ 12.3° margin). Target feasibility is therefore limited by neither the
  workspace boundary nor the joint ranges.
- `[implication]` The differential map is the standard planar 2R Jacobian with
  `σ_max σ_min = L1 L2 |sin q2|`. Over the annulus: `(σ_max, σ_min)` =
  (0.100, 0.060) at r = 0.06, (0.154, 0.076) at r = 0.14, (0.220, 0.042) at
  r = 0.20 (m/rad). Condition is worst at the *outer* edge (near extension) and
  best near r = 0.14.
- `[implication]` The 1 cm tolerance maps into joint space as an ellipse of
  semi-axes `0.01/σ`; across the annulus this is 2.6°–14°, i.e. the position
  tolerance is *generous* in joint units everywhere.
- `[implication]` The configuration-to-task map is triangular and exact:
  `r` depends only on `q2`, and `θ = q1 + β(q2)`. Radial motion is actuated
  solely by the elbow; angular motion primarily by the shoulder with an
  elbow-dependent offset.

### 3. Actuation and dynamic properties

- `[fact]` Both joints are direct torque actuators: `<motor joint=... 
  ctrlrange="-1 1" gear="5"/>`, i.e. joint torque `τ = 5·a` with `|τ| ≤ 5 N·m`.
  Actions are clipped to `[-1, 1]` by the environment after the policy's
  action mapping. There is no PD servo, velocity limit, gearing model, spring,
  or `frictionloss`. *(S4, S5, S7)*
- `[implication]` Segment masses from the default density 1000 kg/m³ and capsule
  geometry are `m1 ≈ 0.099 kg`, `m2 ≈ 0.0525 kg`. Arm inertia about the shoulder
  is `1.41e-3 + 6.30e-4 cos q2` (so 0.78–2.04e-3 kg·m²); about the elbow
  `1.75e-4 kg·m²`. The declared `armature = 0.01 kg·m²` therefore supplies
  ~83–93% of `M11` and ~98% of `M22`. Mass-matrix coupling
  `|M12| ≤ 4.9e-4` is ≤ 4% of the diagonal.
- `[implication]` Consequence: the plant is nearly decoupled, nearly
  configuration-independent, and inertia-dominated by rotor armature rather
  than by link mass. The nonlinearity of `M(q)` is a ≤ ~10% effect.
- `[implication]` With gravity zero and no dry friction, the only passive force
  is joint damping `0.5 N·m·s/rad`. The velocity time constant is
  `M/D ≈ 20–24 ms`, about one control period, and the terminal joint rate under
  a constant action is `q̇ = τ/D = 10·a` rad/s (per joint; ~573°/s at a = 1).
  Equivalently the arm behaves as a bounded velocity source with an effective
  gain of 0.2 rad of displacement per control step per unit action at terminal
  rate (≈ 11.5°·a per step). Torque authority is enormous: α ≈ 400–500 rad/s²
  at |a| = 1.
- `[implication]` Integration is well resolved: `dt·D/M ≈ 0.09` per 2 ms
  substep, 70× above the plant bandwidth. Discretization error is negligible;
  the meaningful discrete element is the 50 Hz control lattice.
- `[implication]` A static equilibrium at zero velocity requires zero net torque
  (`M q̈ = 5a` with `q̇ = 0`). There is no gravity load, no stiction and (absent
  contacts) no other static force, so *any* configuration is an equilibrium at
  `a = 0`, and at any configuration a nonzero action produces a steady drift at
  `10·a` rad/s. The zero-torque command is exactly the equilibrium command.

### 4. Episode construction and the initial physical state

- `[fact]` `reset` zeroes all `qpos` and `qvel`, runs `mj_forward`, samples the
  target as `angle ~ U(-π, π)` then `radius ~ U(0.06, 0.20)` from the
  environment's seeded generator, and sets the mocap target to
  `(r cos θ, r sin θ, z_EE)`. `step` clips the mapped action, writes it to
  `data.ctrl`, runs `frame_skip` physics steps, then computes distance, the hold
  counter, reward, termination and truncation. *(S5)*
- `[implication]` The initial state is always the same physical configuration:
  `q1 = q2 = 0`, `q̇ = 0`, end effector at `(0.22, 0, 0.02)` — the fully
  extended, workspace-boundary configuration, which is also a kinematic
  singularity (`det J = 0`). Every episode must fold inward from that state.
- `[implication]` Initial distance is `|EE₀ − target| =
  sqrt(0.22² + r² − 0.44 r cos θ)`, ranging from 0.02 m (θ = 0, r = 0.20) to
  0.42 m (θ = ±180°, r = 0.20). The reach is therefore strongly
  angle-dependent even though the tolerance is not.
- `[implication]` Near `q2 = 0` the radius changes only quadratically,
  `Δr ≈ −(L1 L2/(2 r)) q2²` (≈ 1 cm for `q2 ≈ 35°` at r = 0.22): the initial
  radial error is not actuable by first-order joint motion. Reaching requires
  first breaking the collinearity, and the distance is not monotone in the
  path.
- `[implication]` There is no initial-state or target randomness inside an
  episode and no process or sensor noise anywhere in the chain. Together with
  deterministic inference (`deterministic=True`), an episode outcome is a
  deterministic function of the sampled `(r, θ)`. *(S5, S13)*

### 5. Success semantics and official measurement

- `[fact]` The hold counter increments when the post-step distance is ≤ 0.01,
  resets to zero on any step outside, and the episode terminates as success when
  it reaches 100; truncation occurs at 500 steps. `info["is_success"]` is the
  termination flag. *(S5)*
- `[implication]` The criterion is evaluated only at the 20 ms control lattice.
  Sub-step motion is invisible to it; an EE faster than ~1 cm per step can pass
  through the tolerance ball without registering a single held step.
- `[implication]` Failure types are separable in configuration space: never
  entering (distance > 1 cm at every step), entering and drifting out, entering
  with boundary chatter (many resets), and timeout.
- `[fact]` The research evaluation runs a deterministic panel of consecutive
  episode seeds and records per-episode `success`, `reward_total`, `steps`, and
  in `research_evidence.episode_diagnostics`: `target_radius_cm`,
  `target_angle_degrees`, `min_distance_cm`, `final_distance_cm`,
  `first_reach_step`, `max_held_steps`, `in_tolerance_steps`,
  `hold_interruptions`. *(S12)*
- `[fact]` Development panel defaults are 160 episodes from seed 4200, kept
  deliberately distinct from the protected panels; overlap with protected
  benchmark evidence is rejected. *(S14, S17)*
- `[implication]` Because the episode outcome is deterministic given the target,
  the per-episode diagnostics from one panel can be joined with
  `target_radius_cm` and `target_angle_degrees` to construct a failure map over
  the annulus; the panel is a grid sample of the (r, θ) measure, so a policy's
  true success measure is the (r, θ)-measure of its success set.
- `[implication]` With 200 episodes, a policy whose true measure is 0.98 has a
  ~1% standard deviation in the panel count; the 196/200 threshold is
  coin-flip-risky at exactly 98% and only becomes robust well above it.

### 6. Observation, action and persistence model

- `[fact]` The observation is 11-dimensional: `qpos(2)`, `qvel(2)`,
  `EE − target(3)`, and four wrapped joint-angle errors to *both* analytic IK
  branches (open `+e` and folded `−e`). It is computed from `MjData` with no
  noise, no filtering and no delay. *(S6)*
- `[implication]` The third offset component (z) is identically 0, and the
  remaining entries are a deterministic function of a 6-dimensional state
  (`q1, q2, q̇1, q̇2, r, θ`). The observation is therefore fully informative but
  over-parameterized: 5 of 11 channels are redundant, one of them constant.
- `[implication]` The observation already contains the solution of the inverse
  kinematics for both branches. The learning problem is therefore *regulation to
  a stated setpoint* (plus branch selection), not IK discovery.
- `[implication]` Not observable: the accumulated hold count, the
  out-of-tolerance-after-hold flag, elapsed steps, and any explicit
  radial/angular (polar) decomposition or distance scalar. `r` and `θ` are
  derivable from `qpos` and the offset vector, but not presented.
- `[fact]` The policy I/O functions (`io.observe`, `io.action`, `io.reset`),
  the learned weights, and the observation-normalization statistics are frozen
  into the saved runtime, and the protected environment calls *these* functions
  to build each observation and to map each action before validating and
  clipping it. The protected environment is not the PI-owned environment.
  *(S13, S14)*
- `[implication]` Any change in the observation function, the action mapping or
  the reset hook travels with a candidate into the official assessment; any
  change in the PI-owned environment step semantics, reward, or target sampling
  does not. Research evaluation of an *older* artifact still uses that
  artifact's own frozen I/O.
- `[fact]` The observation is passed through a frozen affine normalizer (running
  mean/variance from training) with clipping, whose integrity is hash-checked
  against the weights. *(S13, S19)*
- `[fact]` `action_space` is `Box(-1, 1, shape=(2,))`; `physical_action` is the
  identity; the environment clips. *(S5, S7)*

### 7. Training recipe as part of the coupled system

- `[fact]` The active method is PPO with MLP `[64, 64]` tanh, `n_steps = 1024`,
  `batch_size = 64`, `gamma = 0.99`, `gae_lambda = 0.95`,
  `learning_rate = 3e-4`, `ent_coef = 0.01`, one environment, observation
  normalization on and reward normalization off, checkpoints every 5000 steps,
  and a default allocation of 120,000 timesteps. *(S10, S11, S18)*
- `[fact]` The *training* environment samples targets from
  `TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)` — a strict subset of the
  official `(0.06, 0.20)`. *(S8)*
- `[implication]` Since radius is uniform on the official interval, 57% of
  official episodes (r ∈ [0.06, 0.14)) fall outside the training distribution's
  support; these targets require larger elbow folds (up to 150° vs 101°) and
  larger shoulder offsets `β` (up to 56° vs 44°), and their conditioning is
  better (`σ_min ≥ 0.060` vs 0.042 at the outer edge).
- `[fact]` The reward is potential-based shaping (`progress` = 10·Δd,
  `closeness` = 4·Δ(exp(−d/0.05)), `hold_progress` = 50·Δclip(h/100,0,1)) plus a
  history-dependent `outside_band` penalty (−0.1 scaled over the first 1 cm),
  a terminal +50 at `h = 100`, and a control cost `−0.01·||a||²`; the exit
  forfeit fraction is 0. *(S9)*
- `[implication]` The hold phase dominates the return (~50 + 50) relative to the
  reach phase (≤ ~8 in the worst geometry), and the control cost is aligned with
  the plant's zero-torque equilibrium.
- `[implication]` `hold_progress` and `outside_band` depend on hidden state
  (`h`, `_outside_after_hold`) that is not in the observation, so the reward is
  non-Markovian as seen by a feed-forward policy and its critic.
- `[implication]` With one environment, a 1024-step rollout spans roughly 3–10
  episodes and therefore only that many distinct targets per gradient update;
  with `log_std_init` unset the exploration standard deviation is of order 1,
  roughly 500× the action precision the hold requires.
- `[fact]` The training success rate is computed from the rollout environment's
  episode buffer, i.e. from *stochastic* actions, and is stored per candidate.
  *(S16)*
- `[fact]` At campaign start there is no completed operation, no training
  candidate and no assigned model role: `campaigns/results.jsonl` is empty and
  `campaigns/EXPERIMENTS.md` has no rows.

## Physical consequences

### 8. The plant at the control timescale is a damped, armature-dominated velocity source

- `[implication]` Over one 20 ms control period the joints essentially reach
  `q̇_j = 10·a_j`; from rest the first step delivers about one third of that,
  and the terminal rate by the second or third step. Position increments are
  therefore nearly proportional to the commanded action:
  `Δq_j ≈ 0.2·a_j` rad per step at terminal rate.
- `[implication]` The first-order, decoupled, nearly configuration-independent
  model `q̇_j ≈ 10 a_j` is an accurate reduced representation. Consequences:
  (i) closed-loop stability is not the bottleneck — a proportional law
  `a = k·e` is stable for any `0 < k < 10`; (ii) the physical difficulty lies in
  *geometry, representation and the terminal torque*, not in the dynamics;
  (iii) torque saturation matters only for gross reach motions (|a| ≈ 1 needed
  to sweep 170° in ~15 steps).
- `[implication]` The nonlinearity that does exist is geometric, not inertial:
  the mapping from joint error to task error is configuration-dependent
  (`r` and `β` depend on `q2`), and radius is invisible in the position
  channel near extension.

### 9. What "hold" physically requires: a zero-net-torque equilibrium

- `[implication]` Because gravity is zero and there is no stiction, staying
  inside the 1 cm ball for 100 steps requires the closed loop to have an
  equilibrium — a state with zero net torque — inside the ball; a constant
  nonzero action drifts at `10·a` rad/s, i.e. up to `|J|·20·a` metres over the
  hold. With `σ_max ≈ 0.22` m/rad at the outer radius, a persistent mean action
  of `|a| ≈ 2e-3` (τ ≈ 0.01 N·m) already moves the EE ~1 cm in 2 s. The hold
  therefore demands *action* precision of order 0.2–0.5% of the control range,
  not position precision.
- `[implication]` Conversely, the ideal commanded torque at the target is
  exactly zero (no gravity compensation is needed), and the reward's control
  cost penalizes nonzero action, so the physics and the reward point at the same
  equilibrium. A learned mean action of ≈ 0 at the goal is simultaneously
  optimal for the task and cheap in reward.
- `[implication]` Bounded oscillatory actions are far more tolerable than a
  biased one: with a ~20 ms plant time constant, per-step displacement is
  `≈ 0.2·a` rad, so a sign-changing action of magnitude 0.1 moves the EE about
  0.4 cm per step without leaving the ball, while a *constant* bias of 0.01
  fails within ~0.5 s.
- `[implication]` Entry dynamics matter at the discrete sampling: to register a
  held step the EE must be inside the ball at a post-step instant, so entry
  speeds above ~0.5 m/s risk skipping the ball, and a residual speed of ~1 rad/s
  at entry is carried out of the tolerance within one or two steps by the
  damping (24 ms decay). Reaching fast and arriving slow are physically
  distinct requirements.
- `[implication]` Silent-hold failure is the physically predicted dominant
  failure class: a policy that reaches and then drifts or chatters produces
  `min_distance_cm < 1`, `in_tolerance_steps` substantial, `max_held_steps`
  between roughly 5 and 95, and `hold_interruptions ≥ 1`; a policy that never
  reaches produces `min_distance_cm > 1` and `first_reach_step = null`.

### 10. Branch structure and the geometry of the feasible set

- `[implication]` Each target has exactly two kinematic solutions (elbow
  positive and negative), separated in `q2` by `2|q2*| ≥ 99°` over the annulus,
  so the tolerance preimage in joint space is two disjoint regions of roughly
  2.6°–14° radius. Both branches map to the same EE point, and both are
  admissible at the sampled radii (≥ 20° and ≥ 12° limit margin).
- `[implication]` The branches are *not* interchangeable in reachability: the
  folded solution needs `q1 = θ + β`, whose representative lies outside ±170°
  whenever `θ + β ∈ (170°, 190°)`. With `β` from 22.3° (r = 0.20) to 56.3°
  (r = 0.06), the "only one branch admissible" sectors move from
  `|θ| ∈ (148°, 168°)` at the outer radius to `|θ| ∈ (114°, 134°)` at the inner
  radius. Over the annulus these arcs cover roughly 10–12% of the (r, θ) measure.
- `[implication]` Consequence: a policy that commits to one elbow sign can fail
  on a radius-dependent pair of angular arcs, while the mirrored branch stays
  available — a failure set that is an arc in angle whose position depends on
  radius, not a radius band. A branch-agnostic task-space policy would not have
  that failure mode.
- `[implication]` A second geometric alternative exists on the *torus*: a
  solution whose raw joint value exceeds ±170° can be admissible through its
  wrapped representative, so "the short way around" is not always available and
  the joint limits, not the annulus, define the admissible branch set.
- `[implication]` Because there are no obstacles, the C-space path between the
  start configuration and either branch is free within the joint limits; the
  reach has no homotopy obstruction, only limits and conditioning.

### 11. Observation-to-outcome relation and the two policy families

- `[implication]` The composite map is: target geometry → initial observation
  (a function of the target alone) → policy action → identity mapping → clip →
  10 substeps of damped, armature-dominated physics → EE displacement through
  the configuration-dependent Jacobian → sampled distance → hold counter →
  termination at 100. Every step of this chain is deterministic and
  noise-free.
- `[implication]` Two structurally different solutions are available from the
  same observation: (A) *joint-space regulation* — drive the wrapped error of
  one IK branch to zero, which is nearly a linear, well-conditioned control
  problem because the observation states the setpoint; it needs branch
  selection, and it inherits the branch-availability arcs of §10. (B)
  *task-space regulation* — act on the unambiguous `EE − target` vector, which
  has no branch ambiguity but requires the network to internalize the
  configuration-dependent Jacobian and is degenerate at the initial
  singularity. Mixtures (for example averaging both branch errors) have an
  equilibrium between the two branches, i.e. near full extension, and are
  physically unable to satisfy the tolerance.
- `[implication]` Because the observation contains both branch errors *and* the
  task-space error, it carries a redundant and potentially conflicting encoding
  of one goal; nothing in the reward distinguishes a pure representation error
  from a control error.
- `[implication]` The hidden hold count is not needed to *act* optimally — the
  stationary policy "stay at the equilibrium" is the same at held_step 1 and 99
  — but it is needed to *value* states correctly. A feed-forward critic sees
  identical inputs with returns differing by up to 50, so value/advantage
  estimates around the tolerance entry are biased by construction. The
  representable policy class is stationary feedback; for this task that class is
  sufficient (a stabilizing law exists at every target).

### 12. Proxy calibration: two opposing biases

- `[implication]` The training success metric is optimistic about the official
  goal because it is measured on the narrower training radius range (targets
  with `σ_min ≥ 0.042` and simpler folds), and it is pessimistic at the same
  time because it is measured under stochastic exploration actions of order
  `|a| ~ 1`, roughly 500× larger than the hold tolerance implies. A single
  number can therefore be wrong in either direction, and rank ordering by it is
  not a physical measurement of the official success measure.
- `[implication]` Discounting (`γ = 0.99`, horizon 100 steps = 2 s) matches the
  hold duration; the terminal +50 bonus is worth ~18 at hold onset. Within one
  episode the hold contributes ~100 of the return, so PPO's credit assignment
  is dominated by a phase whose state variable is unobservable.

### 13. Physically meaningful quantities for this system

- `[implication]` The quantities that carry the physics of the complete behavior
  are: the 3-D distance `d(t)` (cm) sampled at the control lattice; held-step
  count and interruptions; target radius and angle; joint-limit proximity
  `|q|/170°`; the analytic `(r, θ) ↔ (q1, q2)` map and `β(q2)`;
  `σ_min, σ_max` of the Jacobian and the resulting joint-space tolerance
  ellipse; the effective inertia `M(q)` and its armature share; the damping
  time constant `M/D`; the terminal-rate gain `q̇ = 10a` and the mean/oscillatory
  decomposition of the action during held steps; entry speed at first tolerance
  crossing; and the (r, θ)-measure of the success set. Reward components and
  the value/advantage statistics are training-side quantities with no official
  meaning.

## Unknowns

### 14. Whether the two arm capsules generate contact forces at the elbow

- `[unknown]` The `upper_arm` and `forearm` capsules are declared without
  `contype`/`conaffinity` (defaults enabled), their axes share the elbow point,
  and the XML declares no `<contact><exclude>`, while the plane, base and target
  geometries are explicitly disabled. If MuJoCo does not filter joint-connected
  body pairs, the two capsules overlap by `r1 + r2 = 0.027 m` at every
  configuration except as the closest-point solution moves, producing a deep,
  configuration-independent contact wrench at the elbow. *(S4)*
- `[implication]` Under the self-contact branch, the clean third-order
  conclusions of §3 and §9 weaken: the hold equilibrium need no longer be
  `τ = 0`, a systematic joint torque bias exists, and the reduced first-order
  plant of §8 acquires a static term.
- `[implication]` Discriminating evidence: a measurement that loads S4 and
  reports `data.ncon`, contact geom names, penetration, and
  `data.qfrc_constraint` at several `qpos` (including `q2 = 0` and
  `q2 = ±90°`); or action logging during successful holds — a hold sustained
  with `||a|| ≈ 0` confirms the clean equilibrium, a hold requiring a persistent
  nonzero action indicates a static contact bias.
- `[implication]` Decision relevance: whether the reduced physical model of §8–§9
  may be used as the basis for controller design or intervention reasoning, and
  whether a nonzero mean action during the hold is a failure signal or a
  physical necessity.

### 15. The protected environment's exact semantics

- `[unknown]` The protected benchmark and task-reference implementations are not
  readable. Their target-sampling code, `z` handling, reset state, hold-step
  computation, action clipping and `io.reset` usage are contractually described
  but not verifiable from the readable sources. *(S14, S15)*
- `[implication]` A divergence here would silently shift the official result
  relative to the research evaluation, including (in the worst case) a target
  plane mismatch that makes the tolerance unreachable.
- `[implication]` Discriminating evidence: measure one candidate with
  `research_evaluation` (official radius range, known seeds) and with
  `task_reference`, and compare pooled success rates and the
  radius/angle-resolved failure pattern. Systematic divergence is a property of
  the environments, not of the candidate.

### 16. The realized protected panel

- `[unknown]` The 200 official episodes' seeds and hence their realized target
  geometry are hidden and cannot be reproduced; only the distribution is
  defined. *(S1, S14)*
- `[implication]` The official verdict is a deterministic function of the
  policy and this fixed hidden sample; the campaign controls the true success
  measure, not the panel. For planning, the panel count behaves like 200 i.i.d.
  draws, so a policy with a true measure of 0.98 fails the 196/200 threshold
  about half the time.
- `[implication]` Discriminating evidence: pooled multi-seed panels with
  disjoint seeds (`summarize_research_evaluations`) give a tighter estimate of
  the true measure and of the residual failure set; the panel's own composition
  cannot be observed.

### 17. Default modeling parameters that the XML leaves unspecified

- `[unknown]` The XML does not set `integrator`, `solref`/`solimp` (including
  the joint-limit constraint response), `condim`, `frictionloss`, or the
  contact parameters; MuJoCo's defaults therefore govern, and the implicit
  damping treatment of the default integrator changes the approach transient by
  roughly 10% (it does not change the terminal rate `10a`). *(S4)*
- `[implication]` If a policy drives into the ±170° limit, the limit's finite
  stiffness (a ~20 ms constraint time constant) permits transient penetration
  and rebound; measured behavior near the limit cannot be predicted to better
  than a qualitative description without reading the defaults from the installed
  MuJoCo version.
- `[implication]` Discriminating evidence: a measurement of `model.opt`
  fields, the joint-limit constraint parameters, and the observed response to a
  saturated command aimed at the stop.

### 18. Numerical determinism across processes

- `[unknown]` The determinism argument of §4 and §5 rests on identical
  floating-point arithmetic and identical MuJoCo execution. Cross-process and
  cross-machine bitwise reproduction is assumed, not established, and the
  training path uses a subprocess vectorized environment when `n_envs > 1`.
  *(S5, S11)*
- `[implication]` If bitwise reproduction fails, "the same panel measured twice
  returns the same result" is false at the boundary of the success set, and
  near-threshold episodes become indeterminate.
- `[implication]` Discriminating evidence: repeat one panel with identical
  seeds and compare per-episode `success`, `steps`, and `final_distance_cm`;
  identical results support the deterministic map, disagreement localizes the
  instability.

### 19. Sample efficiency and the value of the current allocation

- `[unknown]` Whether 120,000 PPO timesteps (≈ 400–1000 episodes' worth of
  single-environment experience, ~8 targets per gradient update) suffice for a
  98–99.5% true measure is unknown; so is the gap between the training proxy and
  the deterministic official-distribution measurement for this specific recipe.
- `[implication]` The candidate pool contains only neutral checkpoints; no
  checkpoint is privileged. *(S11, S16, S18)*
- `[implication]` Discriminating evidence: research evaluations of several
  checkpoints from one run on the same panel seeds (paired), plus training-log
  learning curves; the size and the radius/angle structure of the remaining
  failure set is the quantity that decides whether more optimization or a
  structural change is the credible route.

### 20. Which failure mechanism actually dominates

- `[unknown]` The relative contributions of (i) the untrained inner radius band,
  (ii) branch-availability arcs, (iii) hold-phase action bias/drift,
  (iv) entry-speed overshoot, and (v) value-function bias from the hidden hold
  counter are not established before evidence exists.
- `[implication]` The mechanisms predict different signatures: (i) failures
  concentrated at `target_radius_cm < 14`; (ii) failures as arcs in
  `target_angle_degrees` whose location depends on radius; (iii) large
  `in_tolerance_steps` with `max_held_steps < 100` and small
  `min_distance_cm`; (iv) long `first_reach_step` with `in_tolerance_steps`
  small and `hold_interruptions` concentrated early; (v) broad, geometry-weak
  failure with high episode-to-episode variability.
- `[implication]` Discriminating evidence: the recorded
  `episode_diagnostics` fields joined across several disjoint panels, plus a
  lab measurement that logs the joint trajectory, the action, and the branch
  taken for a small set of representative targets.

## Decision-relevant synthesis

The items below are the physical consequences and unknowns most likely to change
the first campaign decisions. Each states the consequence, the assumptions it
rests on, its sources, and the evidence that would confirm, weaken or revise it.
The PI selects any intervention.

### A. Training support excludes 57% of the official distribution

- **Decision relevance:** whether the first work is to obtain an
  official-distribution baseline measurement and a radius-resolved failure map
  before any method change, and whether distribution coverage is treated as a
  property of the artifact rather than of the learner.
- **Assumptions:** the active training environment still samples
  `(0.14, 0.20)`; the official radius is uniform on `(0.06, 0.20)` in the
  protected sampler as well; the training environment is PI-owned and does not
  affect evaluation semantics.
- **Sources:** S8, S2, S1, S12.
- **Discriminating evidence:** per-episode `target_radius_cm` joined to
  `success` from a panel on the official distribution; the change in pooled
  success for a candidate trained with a range-matched environment evaluated on
  the same seeds.

### B. The hold is a zero-torque equilibrium problem, not a disturbance-rejection problem

- **Decision relevance:** how hold failures are classified (drift vs reach vs
  chatter), whether the terminal behavior is treated as a control-precision
  property (action magnitude and equilibrium location) rather than a position
  precision property, and whether the reward's control cost is read as
  physically aligned with the success criterion.
- **Assumptions:** gravity is zero, no stiction, no contacts (see §14), and the
  hold counter requires 100 consecutive sampled steps.
- **Sources:** S4, S5, S9, S12.
- **Discriminating evidence:** `in_tolerance_steps`, `max_held_steps`,
  `hold_interruptions`, `min_distance_cm` patterns; a lab measurement of the
  action norm and its sign structure during held steps, and of the entry speed
  at the first tolerance crossing.

### C. The verdict is a deterministic, quantized draw rather than a noisy measurement

- **Decision relevance:** how much development margin above 98% is worth
  demanding before a terminal assessment, and whether repeated identical panels
  are treated as adding information.
- **Assumptions:** deterministic inference and no noise in the chain; the
  hidden panel behaves like 200 i.i.d. draws from the official distribution.
- **Sources:** S5, S12, S13, S1.
- **Discriminating evidence:** identical repeats of one panel; pooled disjoint
  panels giving a tighter true-measure estimate with a residual-failure map.

### D. The observation fixes the difficulty: IK is given, but branches and the radial channel are ambiguous

- **Decision relevance:** whether the first structural question is about
  representation (which channels are offered to the policy) or about learning
  method; and, because the observation function travels into the official
  assessment with the artifact, whether representation changes are treated as
  part of the deliverable or as training-only scaffolding.
- **Assumptions:** the protected environment calls the saved `io.observe`;
  hence an observation change is honored officially, while an environment change
  is not.
- **Sources:** S6, S7, S13, S14, S12.
- **Discriminating evidence:** paired panel comparison of two artifacts that
  differ only in the observation function, evaluated on the same seeds; the
  recorded diagnostics of the failure set before and after.

### E. Branch availability makes the predicted failure set an arc, not a radius band

- **Decision relevance:** whether a joint-error-following policy is expected to
  fail on ~10% of the annulus by construction, which changes whether the first
  inquiry targets control structure or coverage/optimization.
- **Assumptions:** both IK branches are exposed and equally weighted by the
  policy; the joint limits ±170° are enforced as pure constraints; the elbow
  branch sign is the free discrete choice.
- **Sources:** S4, S6, S10 (limits), S12.
- **Discriminating evidence:** failures plotted against `target_angle_degrees`
  at fixed radius bands, and a lab measurement of the branch sign taken across
  the annulus.

### F. The learning proxy is biased in two opposite directions

- **Decision relevance:** whether candidate selection may rely on training
  success, and how a candidate's prospects are compared before a deterministic
  official-distribution measurement exists.
- **Assumptions:** the training success buffer is populated from stochastic
  rollouts on the narrower training range; deterministic evaluation is the
  official-distribution measurement.
- **Sources:** S16, S11, S12, S8, S9.
- **Discriminating evidence:** for one checkpoint, training success vs a
  deterministic panel on the official distribution with the failure map
  resolved by radius and angle; across checkpoints, the same comparison at
  several saved steps.

### G. Which code changes can reach the official goal is asymmetric

- **Decision relevance:** whether investment goes into environment/reward
  redesign (which cannot change the official verdict) or into the artifact's
  frozen I/O and weights (which can), and how a research-versus-protected
  divergence would be detected before a terminal commitment.
- **Assumptions:** only the saved runtime's `observe`/`action`/`reset`, weights
  and normalizer execute in the protected environment; the protected
  configuration sampling is not re-read from PI code.
- **Sources:** S13, S14, S15, S7, S5.
- **Discriminating evidence:** the same candidate measured by
  `research_evaluation` and by `task_reference`, compared pool-wide and by
  radius/angle; divergence indicates an environment rather than candidate
  difference.

### H. Self-contact at the elbow would change the physical basis of every estimate here

- **Decision relevance:** whether the reduced first-order, zero-torque
  equilibrium model may be used to size control authority, to interpret the
  hold action profile, or to justify a controller-structure argument.
- **Assumptions:** MuJoCo may or may not filter joint-connected body pairs; the
  capsules' surfaces overlap at the elbow under the default
  `contype`/`conaffinity`.
- **Sources:** S4 only.
- **Discriminating evidence:** `data.ncon`, contact geom identities and
  `qfrc_constraint` at several `qpos`; or whether a successful 2 s hold is
  sustained at `||a|| ≈ 0` or requires a persistent nonzero action.
