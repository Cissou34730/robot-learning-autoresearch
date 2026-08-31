# AGENTS.md

Repository operational contract: environment and tooling, commands, layout,
ownership boundaries and working conventions.

The authoritative scientific protocol lives in `research/program.md`. When you
act as the Researcher, follow it there; this file neither restates nor overrides
it.

Virtual robotics RL playground (MuJoCo + Gymnasium + Stable-Baselines3, CPU-first).
Code pipeline: robot -> environment -> reward -> training -> saved policy -> viewer.
Stable-Baselines3 PPO is the currently implemented learning method, not a fixed
part of the architecture; the Researcher may replace it.
Readability and tunability beat performance. Never hard-code movement logic.

## Python environment

This repository is managed with `uv`. All project Python execution goes through
`uv run` — project commands, tests, lightweight research analysis, diagnostics
and temporary analysis scripts alike. Never invoke system `python`, `python3`,
`pytest` or `ruff` directly, and never call the interpreter inside `.venv`.

```bash
uv run python <script>
uv run python -m <module>
uv run pytest ...
uv run ruff ...
```

## Commands

```bash
uv sync                                  # install dependencies
uv run python -m robot_learning.train    # train (see --help)
uv run python -m robot_learning.play --model <model.zip>   # watch in MuJoCo viewer
uv run pytest                            # tests
```

## Layout

- `robot_learning/benchmark/final_contract.py`, `final_benchmark.py` - protected
  Human-owned final task semantics and evaluator, left untouched by other work
- `robot_learning/benchmark/reference_contract.py`, `reference_evaluation.py` -
  protected task-reference panel: an independent execution of the same human
  task producing comparable development evidence, never an objective verdict
- `robot_learning/benchmark/` - final task metric implementation
- `robot_learning/scenario/` - everything specific to the current research
  problem: environment, observations, reward, evaluation, brief evidence, and
  thin adapters over the protected benchmark and task-reference panels. Generic
  code imports only the functions re-exported by
  `robot_learning/scenario/__init__.py`.
- `robot_learning/train.py`, `play.py` - CLIs
- `research/run_experiment.py` - the Runner: CLI, phase determination and
  lifecycle orchestration. It sequences Runner operations; the implementation
  of each one lives in a `research/runner_*.py` module.
- `research/runner_paths.py` - every filesystem location the Runner operates on
- `research/runner_console.py` - what a human sees: cards, plans, progress
- `research/runner_protocol.py` - what is admissible and what a decision means:
  proposal and evaluation-request validation, protected and researcher-owned
  surfaces, experiment identity, measurement identity, and the `plan_*`
  operations that resolve a lineage decision without applying it
- `research/runner_repository.py` - what is durable: campaign state, campaign
  history, checkpoints, artifacts, and every Git operation
- `research/runner_execution.py` - what actually runs: subprocesses, training,
  research evaluations, timeouts and interruption handling. The training and
  physics stack is imported inside these execution paths, so validation-only
  commands never load it.
- `research/current_params.json` - runtime configuration of the currently
  active training method. Reward and other scenario science
  live in `robot_learning/scenario/` as code.
- `research/results.jsonl` - the authoritative experiment history
- `research/EXPERIMENTS.md` - a human-readable view derived from
  `results.jsonl`, never an independent record
- `research/program.md` - authoritative research protocol (read before touching
  `research/`)
- `research/scenario.md` - the current scientific problem
- `research/checkpoints/accepted/` - Git-versioned accepted policy
- `models/candidates/` - disposable training candidates
- `tests/benchmark/` - immutable official-task tests: the objective, the official
  robot, the benchmark contract and the final goal verdict
- `tests/autoresearch/` - immutable generic AutoResearch harness tests: proposal
  and evaluation validation, execution lifecycle, persistence, lineage,
  protected paths, scenario boundary, console and brief presentation, and the
  generic training-artifact contract
- `tests/scenario/` - researcher-owned scenario tests: environment, reward,
  observations, curriculum, research evaluation
- `tests/training/` - researcher-owned learning-method tests: they describe the
  currently active method and evolve with it

## Conventions

- Training is headless; rendering only in play/viewer paths.
- Do not run repo-wide lint/format passes; format only files you touched.
- `research/results.jsonl` is the experiment history. A record is appended
  there first, then `research/EXPERIMENTS.md` is regenerated in full and
  replaced atomically, so an interruption can never leave two competing
  histories. The Runner reconciles the derived view when it enters a mutable
  phase; validation and check-only commands stay non-mutating.
- `research/run_experiment.py` and every `research/runner_*.py` module are the
  enforcement mechanism and are human-owned; the Runner rejects any proposal
  that touches them. Splitting a responsibility into a new `runner_*` module
  therefore never hands part of the protocol to the researcher.
- Tests are organized by repository domain. During a research campaign the
  researcher may modify only `tests/scenario/` and `tests/training/`;
  `tests/benchmark/` and `tests/autoresearch/` are human-owned and the runner
  rejects any proposal that creates, modifies, renames or deletes a file under
  them, before any suite is selected or run.
- `tests/benchmark/` freezes the human-owned task and its verdict.
  `tests/autoresearch/` freezes the architecture and protocol contract that
  researcher-owned code must keep satisfying — scenario boundary, evaluation
  opacity, training-artifact compatibility, execution lifecycle.
  `tests/scenario/` and `tests/training/` are the executable specification of
  the current scientific implementation and are expected to change with it.
- Each test asserts the behaviour its own domain owns: environment tests assert
  environment contracts, reward tests assert reward semantics, evaluation tests
  assert research-evaluation behaviour, training tests assert the active
  learning method. A cross-component assertion is only justified when it states
  a deliberate integration contract.
- Researcher-owned tests are ordinary research code: they travel with the
  experiment's `code_changes` and its Git code lineage.
- `tests/benchmark/` and `tests/autoresearch/` must stay method-neutral: they
  never import or assert against a concrete RL algorithm class.
- Architecture guards derive the surface they protect rather than naming one
  file, so a guard follows the code when a responsibility moves into a new
  Runner module instead of silently guarding nothing.
- Validation timing, decided by `research/runner_protocol.py` and executed by
  `research/runner_execution.py`:
  - fresh campaign baseline - complete validation over all four suites before
    training, even with an unchanged worktree;
  - experiment whose changes all fall inside the researcher-owned surface
    (`RESEARCHER_OWNED_PREFIXES` / `RESEARCHER_OWNED_PATHS`) - complete
    validation before training, minus `tests/benchmark`: a researcher change
    cannot reach the frozen task, and every other suite still guards code the
    experiment may have rewritten;
  - any change outside that surface, including unclassified paths - complete
    validation over all four suites;
  - parameter-only experiment - proposal and effective configuration only, no
    pytest;
  - continuation, evaluation or lineage decision without code changes - no test
    suites.
- The researcher-owned surface is declared positively, never as
  "everything unprotected": an unfamiliar path is validated completely rather
  than assumed mutable, and protected-path rejection runs first so a protected
  file never becomes researcher-owned by sharing a prefix.
- Complete validation is: syntax check plus `ruff check` on changed Python
  files, JSON parse of changed `.json` files, a non-mutating `uv lock --check`
  when dependency metadata changed, then `pytest -q` over the selected suites.
