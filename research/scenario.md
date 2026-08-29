# Current Scenario: two-joint arm reach-and-hold

This file defines the scientific problem studied by this repository.
`research/program.md` defines the research protocol. Read both.

## Objective

The human-defined objective is fixed:

* target sampled 6–20 cm from the robot;
* end effector within 1 cm of the target;
* remain continuously within tolerance for 2 seconds;
* this currently corresponds to 100 control steps and is derived from control timing;
* achieve at least 98% success over the fixed 200-episode official benchmark.

`robot_learning/benchmark/final_contract.py` is human-owned and must not be modified by research.

## Official robot and mechanics

The official benchmark must preserve:

* the robot XML asset referenced by `TWO_JOINT_ARM_XML_PATH`;
* robot geometry and joints;
* actuators and actuator limits;
* action semantics and control limits;
* MuJoCo timestep and official control timing;
* official `frame_skip`;
* official reset/initial-state semantics;
* official target distribution;
* official success tolerance;
* official hold duration;
* official episode horizon;
* official success computation.

These define the physical problem and are not research variables.

## Researcher-mutable scenario code

The scenario lives in `robot_learning/scenario/`:

* `environment.py` — training task mechanics and `make_training_env()`;
* `observations.py` — the observation the policy receives;
* `reward.py` — the complete reward, including its coefficients;
* `evaluation.py` — research evaluation and its diagnostics;
* `brief.py` — how measured evidence is rendered into the brief;
* `final_benchmark.py` — thin adapter over the protected benchmark.

These are ordinary research code files. Changing them is a normal research
change recorded by the existing Git code lineage.

Reward coefficients are **not** in `research/current_params.json`. That file
holds generic runtime configuration only (`algorithm`, `ppo`, `sac`, `policy`,
`training`). To change the reward, change `robot_learning/scenario/reward.py`.

Research may change:

* reward;
* observations;
* normalization;
* exploration;
* curriculum;
* training target distribution;
* training randomization;
* wrappers;
* learning algorithm;
* optimizer;
* policy architecture;
* action representation, provided the resulting policy can still control the official robot correctly;
* other training mechanisms that do not redefine the official task.

`robot_learning/benchmark/` holds the protected task definition and the official
evaluator. Research proposals may not change `final_contract.py` or
`final_benchmark.py`.

## Terminology

* **reach** — moving the end effector toward the sampled target;
* **hold** — remaining continuously inside the 1 cm tolerance;
* **hold progress** — the longest unbroken run of in-tolerance control steps in an episode;
* **best window** — the most task-aligned window of the required hold length;
* **target radius** — distance of the sampled target from the robot base;
* **target direction** — angle of the sampled target, used to detect geometric asymmetry.

## Scenario-specific diagnosis

Reaching and holding are distinct control problems.

A policy that enters the 1 cm region frequently but cannot remain for 2 seconds
has a different failure mechanism from one that rarely reaches the region.

Use hold-progress distributions rather than relying only on averages when the
distribution matters.

Use target radius and direction when useful to detect geometric asymmetry.

## Official benchmark success criterion

Passing requires at least 98% success over the fixed 200 official episodes.

Only the human-owned official benchmark may declare the goal reached.
