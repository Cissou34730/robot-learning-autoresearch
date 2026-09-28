import assert from "node:assert/strict";
import { test } from "node:test";

import {
  commandDenial,
  DEPENDENCY_DENIAL,
  EXECUTION_DENIAL,
  GIT_DENIAL,
  permissionCommandText,
  SUITE_DENIAL,
} from "../src/policy.ts";

test("reading a protected path is research, not execution", () => {
  assert.equal(commandDenial("Get-Content research/run_experiment.py"), null);
  assert.equal(commandDenial("rg run_experiment.py research/"), null);
  assert.equal(commandDenial("Select-String -Path research/runner_protocol.py foo"), null);
});

test("naming a reserved path to a reader is allowed but running it is not", () => {
  assert.equal(commandDenial("uv run python research/run_experiment.py"), EXECUTION_DENIAL);
  assert.equal(
    commandDenial("uv run python -m research.run_experiment --check-operation"),
    EXECUTION_DENIAL,
  );
  assert.equal(commandDenial("python robot_learning/train.py"), EXECUTION_DENIAL);
  assert.equal(commandDenial("python -m research.migrate_policy_runtime"), EXECUTION_DENIAL);
  assert.equal(commandDenial(".\\run_research.ps1"), EXECUTION_DENIAL);
  assert.equal(commandDenial("& .\\run_research.ps1"), EXECUTION_DENIAL);
  assert.equal(commandDenial(".\\reset_research.ps1 -Mode Fresh"), EXECUTION_DENIAL);
  assert.equal(commandDenial("pwsh -File run_research.ps1"), EXECUTION_DENIAL);
  assert.equal(
    commandDenial("powershell.exe -File reset_research.ps1 -Mode Fresh"),
    EXECUTION_DENIAL,
  );
});

test("inline code names no target, by design", () => {
  assert.equal(commandDenial("uv run python -c \"print('hi')\""), null);
});

test("only read-only git subcommands are permitted", () => {
  assert.equal(commandDenial("git status --porcelain"), null);
  assert.equal(commandDenial("git log -1"), null);
  assert.equal(commandDenial("git commit -m wip"), GIT_DENIAL);
  assert.equal(commandDenial("git push origin HEAD"), GIT_DENIAL);
  assert.equal(commandDenial("git.exe commit -m wip"), GIT_DENIAL);
  assert.equal(
    commandDenial('"C:\\Program Files\\Git\\cmd\\git.exe" -C . push origin HEAD'),
    GIT_DENIAL,
  );
  assert.equal(
    commandDenial('"C:\\Program Files\\Git\\cmd\\git.exe" -C . status --porcelain'),
    null,
  );
  assert.equal(commandDenial("git"), GIT_DENIAL);
  assert.match(GIT_DENIAL, /restore_recipe/);
  assert.doesNotMatch(GIT_DENIAL, /lineage proposal/);
});

test("a repository-wide pytest run belongs to the runner", () => {
  assert.equal(commandDenial("uv run pytest"), SUITE_DENIAL);
  assert.equal(commandDenial("pytest"), SUITE_DENIAL);
  assert.equal(
    commandDenial("uv run pytest tests/autoresearch/test_copilot_researcher.py"),
    null,
  );
  assert.equal(
    commandDenial(
      "uv run pytest --maxfail 1 tests/autoresearch/test_copilot_researcher.py",
    ),
    null,
  );
  assert.equal(commandDenial("uv run pytest -k foo"), SUITE_DENIAL);
  assert.equal(commandDenial("pytest.exe -k foo"), SUITE_DENIAL);
});

test("uv run option arity cannot hide denied commands", () => {
  for (const flag of [
    "--locked",
    "--frozen",
    "--offline",
    "--no-sync",
    "--no-project",
  ]) {
    assert.equal(commandDenial(`uv run ${flag} git commit -m x`), GIT_DENIAL);
    assert.equal(commandDenial(`uv run ${flag} pytest`), SUITE_DENIAL);
  }
  assert.equal(commandDenial("uv run --project . git commit -m x"), GIT_DENIAL);
  assert.equal(commandDenial("uv run --python 3.12 pytest"), SUITE_DENIAL);
});

test("pytest no-value aliases leave targeted selectors visible", () => {
  const existing = "tests/autoresearch/test_copilot_researcher.py";
  for (const flag of [
    "--markers",
    "--no-showlocals",
    "--stepwise-reset",
    "--traceconfig",
    "--fulltrace",
    "-h",
    "-V",
  ]) {
    assert.equal(commandDenial(`uv run pytest ${flag} ${existing}`), null);
  }
});

test("dependency management is refused", () => {
  assert.equal(commandDenial("uv add numpy"), DEPENDENCY_DENIAL);
  assert.equal(commandDenial("uv sync"), DEPENDENCY_DENIAL);
  assert.equal(commandDenial("uvx ruff check ."), DEPENDENCY_DENIAL);
  assert.equal(commandDenial("pip install requests"), DEPENDENCY_DENIAL);
  assert.equal(commandDenial("uv run --with rich python -c 'pass'"), DEPENDENCY_DENIAL);
});

test("every segment is judged, not just the first", () => {
  assert.equal(commandDenial("git status; git commit -m x"), GIT_DENIAL);
  assert.equal(commandDenial("rg foo && uv sync"), DEPENDENCY_DENIAL);
});

test("a non-shell permission is never judged as a command", () => {
  // An edit of a researcher-owned file merely names a reserved script name.
  assert.equal(permissionCommandText({ type: "edit", title: "robot_learning/train.py" }), "");
  assert.equal(
    permissionCommandText({ type: "external_directory", pattern: "C:/elsewhere" }),
    "",
  );
});

test("a shell permission yields the command it will run", () => {
  assert.equal(
    permissionCommandText({
      type: "bash",
      metadata: { command: "uv run python research/run_experiment.py" },
    }),
    "uv run python research/run_experiment.py",
  );
  assert.equal(
    permissionCommandText({ type: "bash", title: "git push origin HEAD" }),
    "git push origin HEAD",
  );
  assert.equal(
    permissionCommandText({
      type: "bash",
      metadata: { commands: ["git status", "git push"] },
    }),
    "git status\ngit push",
  );
});

test("a shell-shaped permission still yields text to judge", () => {
  // The permission type alone is enough to know this is an invocation.
  const denial = commandDenial(
    permissionCommandText({ type: "bash", metadata: { command: "git reset --hard" } }),
  );
  assert.equal(denial, GIT_DENIAL);
});
