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
`description` and `rationale` fields are required. The seed is zero or
positive. The `description` and `rationale` strings contain text. The `steps`
value is a positive integer.

In a recipe-development session, you choose `steps` from 10,000 through 500,000
for each run. In startup, you choose a positive `steps` value up to the
configured allocation. In an inquiry, you choose `steps` from the configured
allocation through the maximum. The session prompt gives the allocation and
the maximum for that session.

Transfer training starts from the saved training checkpoint of a parent
candidate. A single transfer run requires a `parent` string that names this
candidate. Fresh training omits the `parent` fields.

The `steps` value is the requested training allocation for each run. For
transfer training, this allocation applies to the new training. The parent
training checkpoint is a separate source of learned state, with its own
recorded training steps. The Runner preserves the parent training checkpoint.

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

The `variants` field is optional. The Runner accepts it in a
recipe-development session. In each session, you can train a single design
with a request that omits it.

Use it to compare 2 to 4 designs in one training operation. Each variant has a
`label`. A label starts with a lowercase letter and contains only lowercase
letters, digits and underscores. It has a maximum of 16 characters. Each label
is unique in the request.

A variant can change any PI-owned source file and any parameter:

- Source files: put the changed files of a variant in
  `robot_learning/variants/<label>/`, with the same relative paths that they
  have below `robot_learning/`. For the training of that variant, each of these
  files replaces the file at the same path. The other files stay the same.
- Parameters: the optional `parameters` object replaces the values of the same
  keys in `robot_learning/training/current_params.json`. The other values stay
  the same. The trainer reads these parameters through
  `load_experiment_config()` in `robot_learning/training/research_config.py`.
  The `parameters` object is the only place for the parameter changes of a
  variant: the Runner rejects a request when a variant folder contains
  `training/current_params.json`.

For transfer training, each variant can declare its own `parent` string. A
variant that omits this field uses the root `parent`. When the request omits
the root `parent`, each variant declares its own parent.

The Runner resolves all parent identities when it accepts the operation. Each
variant starts from its own saved parent training checkpoint. The active
parameters and the declared overrides determine its parameters. The parent
parameters remain a record of the earlier training.

Training checkpoint loading checks mechanical compatibility and reports
failures. You judge semantic compatibility.

The Runner trains each variant in a separate process. All variants train at the
same time, with the same initialization, seed and steps. Measurements of a
candidate use its saved runtime, independently of the files and the parameters
of its variant. The variants share the computer, so each variant can train more
slowly than a single run.

The candidate of a variant has the identity
`T<n>:<label>-checkpoint-<steps>`. The completed result contains `variants`:
for each variant, its `label`, its `parameters`, its `parent` and its
`candidates`. The variant `parent` is the resolved candidate identity, or null
for fresh training. The root `parent` records the declared root parent. Earlier
results that lack a variant `parent` use their recorded root parent.

Each variant has a separate training log. Omit `variant` in
`training_log_query` with `action=discover` to list the available labels. Then
give one label as `variant` to `training_log_query` or
`training_series_statistics`.

The Runner validates the changed PI-owned source files and the active
parameters. It executes the accepted seed and step count. It archives all
candidates that the run makes. It records the parent, the recipe and the facts
of the learning dynamics. You give the working, best-known and retained roles
with role operations.

The candidate archive also records versioned SHA-256 fingerprints of the
identifiable serialized components of the learned state. For the supported
Stable-Baselines3 ZIP format, these components are the policy, the optimizer,
the additional tensor state and the normalization file. The Runner
fingerprints the executable saved runtime separately. The archive names each
unsupported format and each unavailable optional component, and the normal
archive of the candidate continues.

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

They report exact equality of the serialized components, and this alone. You
judge the semantic equivalence of policies, the activation of an intervention,
the scientific independence of results and the adequacy of a candidate. The
integrity fingerprint of the complete artifact stays the same.

The learning algorithm can round the actual completed steps up to the end of
its rollout. The requested value stays in the permitted range.

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
`reason` and `evidence` fields are required. The evidence array has at least
one item. Each evidence item identifies a completed operation.

The `label` field is required for `retain` alone. The label contains text, is
unique and is different from the fixed role names.

Each action copies the complete artifact of the candidate to
`campaigns/checkpoints/retained/`, into a folder that has the name of its
origin operation and fingerprint. The recorded artifact path of the candidate
then points to this copy. The fingerprint stays its identity. The `retain`
action also records the candidate under the requested label. Each action
changes the requested role alone.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Both fields are required and contain text.

This operation returns you to the selected candidate and its complete
scientific recipe. It restores the PI-owned recipe source and training
parameters from the recorded code version of the candidate. It removes the
recipe files that were added after that version. It sets the working role to
the selected candidate. The saved candidate stays unchanged, and training
starts only with a training operation.

The campaign history, session records, measurements and other saved candidates
stay available. Laboratory tools stay as they are. The best-known and retained
roles stay unchanged.

The restoration replaces the current recipe changes. Request this operation
before you implement a new method change. A transfer training request keeps the
current source code.

The result identifies the candidate, code version, parameters, restored files
and removed files. The Runner checks that the restored recipe matches the
recorded code version and parameters.

The restoration works on complete files. When one source file contains
learning code and measurement code, the restoration of the file restores both.
