# Scientific instruments: training and candidates

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Training operation

```json
{
  "training": {
    "initialization": {"type": "string"},
    "parent": {"type": "string"},
    "seed": {"type": "integer"},
    "steps": {"type": "integer"},
    "description": {"type": "string"},
    "rationale": {"type": "string"}
  }
}
```

Set `initialization` to `fresh` or `transfer`. The `seed`, `steps`,
`description` and `rationale` fields are required. The seed must not be
negative. The `description` and `rationale` strings must not be empty. The
`steps` value must be a positive integer.

In a recipe-development session, you choose `steps` from 10,000 through 500,000
for each run. In startup, you choose a positive `steps` value up to the
configured allocation. In an inquiry, you choose `steps` from the configured
allocation through the maximum. The session prompt gives the allocation and
the maximum for that session.

Transfer training starts from the saved training checkpoint of a parent candidate.
A single transfer run requires a non-empty `parent` string.
Fresh training uses no `parent` fields.

The `steps` value is the requested training allocation for each run.
For transfer training, this allocation applies to the new training.
The parent training checkpoint remains a separate source of learned state.
Its recorded training steps are not part of the requested allocation.
The Runner preserves the parent training checkpoint.

### Training variants

```json
{
  "training": {
    "variants": {
      "type": "array",
      "items": {
        "label": {"type": "string"},
        "parameters": {"type": "object"},
        "parent": {"type": "string"}
      }
    }
  }
}
```

The `variants` field is optional and is permitted only in a recipe-development
session. You can always train a single design without it.

Use it to compare 2 to 4 designs in one training operation.
Each variant has a `label`. A label starts with a lowercase letter and contains
only lowercase letters, digits and underscores. It has a maximum of
16 characters. Each label must be unique in the request.

A variant can change any PI-owned source file and any parameter:

- Source files: put the changed files of a variant in
  `robot_learning/variants/<label>/`, with the same relative paths that they
  have below `robot_learning/`. For the training of that variant, each of these
  files replaces the file at the same path. Other files do not change.
- Parameters: the optional `parameters` object replaces the values of the same
  keys in `robot_learning/training/current_params.json`. The other values do
  not change. The trainer reads these parameters through
  `load_experiment_config()` in `robot_learning/training/research_config.py`.
  Put the parameter changes of a variant only in its `parameters` object: the
  Runner rejects a request when a variant folder contains
  `training/current_params.json`.

For transfer training, each variant can declare a non-empty `parent` string.
A variant without this field uses the root `parent`.
When the root `parent` is absent, every variant declares its own parent.

The Runner resolves all parent identities when it accepts the operation.
Each variant starts from its own saved parent training checkpoint.
The active parameters and the declared overrides determine its parameters.
The parent parameters remain a record of the earlier training.

Training checkpoint loading checks mechanical compatibility and reports failures.
Successful loading alone does not establish semantic compatibility.

The Runner trains each variant in a separate process. All variants train at the
same time, with the same initialization, seed and steps. Measurements
of a candidate use its saved runtime. They do not use the files or the
parameters of its variant.

The variants share the computer. Thus each variant can train more slowly than a
single run.

The candidate of a variant has the identity
`T<n>:<label>-checkpoint-<steps>`. The completed result contains `variants`:
for each variant, its `label`, its `parameters`, its `parent` and its `candidates`.

The variant `parent` is the resolved candidate identity or null for fresh training.
The root `parent` records only the declared root parent.
Earlier results without a variant `parent` use their recorded root parent.
Each variant has a separate training log. Omit `variant` in
`training_log_query` with `action=discover` to list the available labels. Then
give one label as `variant` to `training_log_query` or
`training_series_statistics`.

The Runner validates the changed PI-owned source files and the active
parameters. It executes the accepted seed and step count. It archives all
candidates that the run makes. It records the parent, the recipe and the facts
of the learning dynamics. A completed training run does not give the working,
best-known or retained role.

The candidate archive also records versioned SHA-256 fingerprints of the
identifiable serialized components of the learned state. For the supported
Stable-Baselines3 ZIP format, these components are the policy, the optimizer,
the additional tensor state and the normalization file. The Runner
fingerprints the executable saved runtime separately. The archive states each
format that it does not support and each optional component that is not
available. These do not stop the normal archive of the candidate.

The completed training result contains an optional
`saved_component_comparisons` object with these field types:

| Field | Type |
|---|---|
| `schema_version` | integer |
| `scope` | string |
| `current_context` | object |
| `current_context.parent` | string or null |
| `current_context.seed` | integer |
| `current_context.requested_steps` | integer |
| `comparisons` | array |
| `comparisons[].operation` | string |
| `comparisons[].context` | object |
| `comparisons[].current_checkpoint_count` | integer |
| `comparisons[].prior_checkpoint_count` | integer |
| `comparisons[].corresponding_checkpoint_count` | integer |
| `comparisons[].step_sets_equal` | boolean |
| `comparisons[].components` | object |
| `comparisons[].runtime` | object |
| `comparisons[].exact_component_matches` | array |

Component and runtime entries contain the integer counts `compared` and
`equal`. Exact-match entries contain the integer `training_steps` and the
string identities `candidate` and `prior_candidate`. The comparisons use
corresponding saved training-step counts of earlier completed candidates in
the same campaign.

They report only exact equality of the serialized components. They do not
declare semantic equivalence of policies, activation of an intervention,
scientific independence of results or adequacy of a candidate. The integrity
fingerprint of the complete artifact does not change.

The learning algorithm can round the actual completed steps up to the end of
its rollout. This rounding does not permit a value outside the range.

## Role operation

```json
{
  "model_role": {
    "action": {"type": "string"},
    "candidate": {"type": "string"},
    "label": {"type": "string"},
    "reason": {"type": "string"},
    "evidence": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

Set `action` to `set_working`, `set_best_known` or `retain`. The `candidate`,
`reason` and `evidence` fields are required. The evidence array must not be
empty. Each evidence item must identify a completed operation.

The `label` field is required only for `retain`. The label must not be empty
and must be unique. It must be different from the fixed role names.

Each action copies the complete artifact of the candidate to
`campaigns/checkpoints/retained/`, into a folder that has the name of its
origin operation and fingerprint. The recorded artifact path of the candidate
then points to this copy. The fingerprint stays its identity. The `retain`
action also records the candidate under the requested label. Each action
changes only the requested role.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Both fields are required. The candidate and the reason must not be empty.

This operation returns you to the selected candidate and its complete
scientific recipe. It restores the PI-owned recipe source and training
parameters from the candidate's recorded code version. It removes recipe
files that were added after that version. It sets the working role to the
selected candidate. The saved candidate stays unchanged. The operation does
not rerun training.

The campaign history, session records, measurements and other saved candidates
stay available. Laboratory tools are not restored or removed. The best-known
and retained roles stay unchanged.

Current recipe changes are replaced. Request this operation before you
implement a new method change. A transfer training request does not restore
source code.

The result identifies the candidate, code version, parameters, restored files
and removed files. The Runner checks that the restored recipe matches the
recorded code version and parameters.

The Runner does not infer which code implements learning and which code
implements measurement. When one source file contains both, the restoration of
the file restores both.
