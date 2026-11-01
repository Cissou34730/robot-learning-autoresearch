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

The session prompt gives the training allocation and the longest permitted run.
In a startup session, `steps` can be any positive value up to the allocation.
In an inquiry session, `steps` is between the allocation and the longest run.
You cannot change these values. The Runner rejects other values during
validation, acceptance and the start of training.

A standard run uses the allocation.

For `transfer` training, `parent` is required and must not be empty. For
`fresh` training, do not give `parent`.

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
its rollout. This rounding does not permit a different allocation.

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
