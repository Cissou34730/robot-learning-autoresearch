# Executable policy artifacts

A saved policy is weights plus its executable input/output contract, not weights
plus whichever scientific code happens to be checked out during evaluation.

`policy_runtime.pkl` stores the observation and action callables, the model
loader, and the normalization object by value using the existing cloudpickle
dependency. It binds these to the hashes of `model.zip` and the saved statistics.
The installed SB3/Gymnasium/MuJoCo/Python stack is still assumed; this is not a
cross-version or arbitrary-platform model export format. Load trusted artifacts
only, as with SB3's own pickle-containing archives.

The researcher-owned `scenario/policy_io.py` defines policy observations and
physical action conversion. The training environment and checkpoint exporter
use the same interface. Resolve scientific helper imports at export time
(module globals or captured objects), not through deferred imports of mutable
project modules during inference. External mutable files are not an inference
dependency: capture their needed values in the exported objects.

The standard writer captures custom scientific definitions by value when saving
SB3 weights too. Runtime schema version 1 does not alter training budgets,
lineage choices, reward semantics or the fixed task. Recurrent inference state
returned by `predict` is preserved within an episode and cleared between them.

All three evaluators and playback load the artifact runtime. The benchmark
continues to own targets, initial conditions, timing, physical command limits
and success; it does not execute the old training environment. Different input
sizes and same-sized representations therefore coexist on the same task.

Runtime bytes participate in artifact identity, copying, retention and cleanup.
Legacy artifacts may still be inspected/copied for migration, but cannot be
evaluated without an explicit runtime. Missing or changed statistics and weights
are errors, never reasons to substitute the current implementation.

## Existing campaigns

Do not overwrite an active campaign. First select the exact historical science
commit associated with each old artifact. The human-only migration tool exports
a new copy using that code in a temporary checkout, without switching branches:

```powershell
uv run python research/migrate_policy_runtime.py `
  --artifact research/checkpoints/accepted --output ../migrated-champion `
  --source-ref <scientific-commit> --identity-actions
```

`--identity-actions` is an explicit attestation for older code without
`policy_io.py`: verify that training applied policy outputs directly to physical
commands. Do not use it for a policy trained with action preprocessing. Such an
artifact needs its actual historical mapping exported. Legacy migration requires
saved normalization. The tool checks input shape and performs one inference;
it does not train or run an evaluation panel. Equal shape does not prove the
chosen commit has the correct semantics: selecting the historical source is a
human provenance decision, never guessed from vector length.

Review migrated artifacts and adopt them only in an isolated, stopped campaign.
Their identity changes. Previously cached measurements/pending requests cannot
be treated as measurements of this new artifact without reconciliation. This
change does not automatically rewrite a running campaign's state or history.
