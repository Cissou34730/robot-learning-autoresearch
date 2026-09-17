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
  assert.equal(commandDenial("python robot_learning/train.py"), EXECUTION_DENIAL);
  assert.equal(commandDenial("python -m research.migrate_policy_runtime"), EXECUTION_DENIAL);
});

test("inline code names no target, by design", () => {
  assert.equal(commandDenial("uv run python -c \"print('hi')\""), null);
});

test("only read-only git subcommands are permitted", () => {
  assert.equal(commandDenial("git status --porcelain"), null);
  assert.equal(commandDenial("git log -1"), null);
  assert.equal(commandDenial("git commit -m wip"), GIT_DENIAL);
  assert.equal(commandDenial("git push origin HEAD"), GIT_DENIAL);
  assert.equal(commandDenial("git"), GIT_DENIAL);
});

test("a repository-wide pytest run belongs to the runner", () => {
  assert.equal(commandDenial("uv run pytest"), SUITE_DENIAL);
  assert.equal(commandDenial("pytest"), SUITE_DENIAL);
  assert.equal(commandDenial("uv run pytest tests/autoresearch/test_x.py"), null);
  assert.equal(commandDenial("uv run pytest -k foo"), null);
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
