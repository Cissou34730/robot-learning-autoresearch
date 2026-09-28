# Preliminary scientific model

This is the campaign-start model of the embodied learning problem. It is based
on `research/scenario.md`, the protected benchmark implementation, and the
human-owned MuJoCo robot asset. It is a reference model, not campaign evidence:
no policy-performance claim is made here.

## System boundary and causal picture

The system is a deterministic simulated, planar two-joint arm. At reset, the
task samples a stationary target, initializes the arm at rest, and exposes a
policy observation. At each control step the policy emits two bounded motor
commands; MuJoCo holds those commands for ten physics steps; the resulting
end-effector position determines both the next observation and whether the
current hold streak continues. An episode succeeds only if the target-distance
condition remains true for the complete required streak.

The causal route to the human goal is therefore:

`target geometry -> observation -> policy action -> joint dynamics -> end-effector
trajectory -> uninterrupted tolerance streak -> episode success`.

The consequential learning problem is not merely inverse kinematics or first
arrival. It is the acquisition of a target-conditioned transient controller
followed by a low-variance, low-overshoot holding controller across the full
official target distribution.

## Established facts

These are repository facts, with sources in parentheses.

- The robot has two serial planar hinge joints, shoulder and elbow, with link
  lengths 0.12 m and 0.10 m. Each joint range is -170 to 170 degrees. The
  end-effector site is at the end of the forearm. (`two_joint_arm.xml`,
  `two_joint_arm.py`)
- Gravity is zero. The physics timestep is 0.002 s. Both joints have damping
  0.5 and armature 0.01. Each joint is driven by a motor with control range
  [-1, 1] and gear 5. (`two_joint_arm.xml`)
- The arm starts every episode with both joint positions and velocities set to
  zero. The target is fixed for the episode, lies in the arm's plane, and is
  sampled with angle uniform over [-pi, pi] and radius uniform over [0.06, 0.20]
  m. (`final_benchmark.py`, `scenario.md`)
- The official interface applies one policy action for ten physics steps. Thus
  the control interval is 0.020 s (50 Hz), and the two-second hold requires 100
  consecutive control steps. A single step outside the 0.01 m tolerance resets
  the consecutive streak. (`final_contract.py`, `final_benchmark.py`)
- An official episode is capped at 500 control steps, or 10 s. The final panel
  contains 200 fixed-seed episodes; success requires at least 196 successes
  (98%). (`scenario.md`, `final_contract.py`)
- The protected evaluator clips physical actions to [-1, 1], advances the
  simulator, measures Euclidean 3-D distance from the end-effector to the
  target, and counts only the complete uninterrupted hold as success. The
  evaluator's reward is not the success criterion. (`final_benchmark.py`)
- The robot and plane geoms have contact disabled. There is no modeled
  obstacle, grasp interaction, target motion, gravity, or external disturbance.
  (`two_joint_arm.xml`)
- The current policy-facing observation contains joint positions, joint
  velocities, end-effector-to-target displacement, and angular residuals to the
  two analytic inverse-kinematics branches: 11 scalar values in total. The
  current action mapping is the identity, so policy outputs are physical motor
  commands. (`scenario/observations.py`, `scenario/policy_io.py`)
- The current research training constructor samples only radii 0.14--0.20 m,
  whereas the official distribution includes 0.06--0.20 m. This is a mutable
  research choice, not an official task definition. (`scenario/training_environment.py`,
  `final_contract.py`)

## Physical consequences

These are deductions from the established facts, not separately measured
results.

- The nominal geometric reach is 0.02--0.22 m. The official radial interval is
  inside that annulus, so every sampled radius has inverse-kinematic solutions
  in the ideal two-link geometry. The inner end of the interval requires a
  substantially folded arm, while the outer end requires a more extended arm.
  Joint limits remain part of the feasibility question even though the sampled
  interval is nominally inside the geometric workspace.
- The target distribution is uniform in radius, not uniform in planar area.
  Equal radial bands receive equal probability, so the distribution's areal
  density is higher toward the inner radii. Full angular coverage also removes
  any fixed directional shortcut; with zero gravity and no contacts, the main
  directional variation should arise from configuration choice, joint limits,
  and numerical/dynamic effects rather than a preferred world direction.
- Actions are piecewise-constant motor commands over 20 ms intervals. The
  policy must control both the approach transient and the residual oscillation
  after entering a 1 cm ball. Because success is a streak property, a small
  overshoot or one-step excursion is as consequential as failure to reach the
  target in the first place.
- The hold requirement is 2 s, not simply a terminal proximity check. A policy
  can reach the tolerance early and still fail after an interruption; therefore
  time-to-first-entry, distance margin while holding, velocity at entry, and
  interruption behavior are causal diagnostics for success but are not
  substitutes for success.
- With joint position, joint velocity, and target-relative displacement
  available, the observation exposes the principal instantaneous state needed
  for target-conditioned feedback in this deterministic model. The two
  inverse-kinematics residual pairs expose both elbow branches, so branch
  selection can be learned or represented without reconstructing target
  coordinates from pixels. The observation does not itself guarantee that a
  policy will choose a dynamically stable branch.
- The absence of contact and disturbances makes the task a clean control and
  exploration problem rather than a contact-rich manipulation problem. It also
  means a policy that succeeds in the simulator need only be shown robust to
  target geometry and its own transient/hold dynamics; robustness to unmodeled
  physical disturbances is outside this official objective.
- The current training-radius restriction omits radii 0.06--0.14 m from the
  official radial range. A policy optimized there has not, by that fact alone,
  learned the official distribution; generalization to folded configurations is
  a central potential gap. The current shaped reward may help discover
  proximity, but only the protected uninterrupted-hold outcome establishes
  progress toward the human goal.

## Unknowns

These quantities are unresolved before campaign evidence exists and should not
be treated as facts.

- The effective link masses, inertias, actuator torque response, numerical
  integration details, and resulting position/velocity settling times have not
  been characterized as control-relevant quantities. XML defaults and geometry
  determine some of them inside MuJoCo, but their effect on the 20 ms sampled
  controller is unknown.
- It is unknown whether the available motor authority can enter and remain
  inside the 1 cm ball with adequate margin for every target, especially for
  inner-radius folded configurations and for targets near the joint-limit
  envelope. This requires measurement of transient error, velocity, and hold
  margins, not just inspection of kinematic reachability.
- The relative difficulty of the two inverse-kinematics branches is unknown.
  Their nominal geometric availability does not establish equal dynamic
  stability, equal time-to-target, or equal tolerance to policy error.
- The distribution of failure causes is unknown: slow approach, branch choice,
  overshoot, residual oscillation, joint-limit effects, observation/action
  scaling, or learning instability may dominate. No campaign measurement yet
  identifies the limiting mechanism.
- It is unknown whether the current 11-value observation and deterministic
  policy execution are sufficient for at least 98% success, or whether
  normalization, recurrence, action holding, or another policy-side change is
  needed. The observation is state-like, but sufficiency for the learned
  controller is an empirical question.
- It is unknown how much training on 0.14--0.20 m transfers to the official
  0.06--0.20 m distribution, and whether a change in sampling or curriculum
  improves complete-hold success without sacrificing the already-covered
  outer targets.
- There is no pre-campaign estimate of episode success, confidence around a
  98% rate, or the number and geometry of failures on an independent panel.
  Development panels can diagnose these quantities, but only the frozen
  200-episode official assessment can determine whether the human goal is met.
