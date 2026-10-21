# Scientific instruments: training and candidates

Part of the instrument contract indexed in `contracts/instruments.md`.

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

Set `initialization` to `fresh` or `transfer`.
The `seed`, `steps`, `description`, and `rationale` fields are required.
The seed must be non-negative.
The `description` and `rationale` strings must be non-empty.
The `steps` value must be a positive integer.

The session context states the training allocation. During startup, `steps`
can be any positive value up to the allocation. During an inquiry, `steps` must
equal the allocation. The PI cannot change the allocation. Runner rejects
other values during validation, acceptance and training dispatch.

For transfer training, `parent` is required and must be non-empty.
For fresh training, omit `parent`.

The Runner validates changed PI-owned sources and active parameters.
It executes the accepted seed and step count.
It archives all produced candidates.
It records the parent, scientific recipe, and learning-dynamics facts.
Completion does not assign working, best-known, or retained roles.

Candidate archival also records versioned SHA-256 fingerprints for identifiable
serialized learned-state components. For the supported Stable-Baselines3 ZIP
format these components are the policy, optimizer, additional tensor state and
normalization file. The executable policy runtime is fingerprinted separately.
Unsupported formats and unavailable optional components remain explicit; they
do not prevent normal candidate archival.

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

Component and runtime entries contain integer `compared` and `equal` counts.
Exact-match entries contain integer `training_steps` and string `candidate` and
`prior_candidate` identities. Comparisons use corresponding saved training-step
counts from earlier completed candidates in the same campaign. They report
exact serialized-component equality only. They do not declare semantic policy
equivalence, intervention activation, scientific independence, or candidate
adequacy. The complete-artifact integrity fingerprint remains unchanged.

The learning algorithm can round actual completed steps up to its rollout
boundary. This does not authorize a different allocation.

## Model-role operation

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

Set `action` to `set_working`, `set_best_known`, or `retain`.
The `candidate`, `reason`, and `evidence` fields are required.
The evidence array must be non-empty.
Each evidence item must identify a completed operation.

The `label` field is required only for retention.
The label must be non-empty and unique.
It must differ from the fixed role names.

The `retain` action archives the candidate under the requested label.
Each action updates only the requested role.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": {"type": "string"},
    "reason": {"type": "string"},
    "paths": {"type": "array", "items": {"type": "string"}}
  }
}
```

All fields are required. Candidate and reason must be non-empty. `paths` is a
non-empty list of distinct exact repository-relative scientific files, including
`robot_learning/training/current_params.json` for the recorded parameters.
The operation restores only those files from the candidate's recorded recipe.
It removes a selected file when absent from that recipe.
Unselected source files remain unchanged; campaign laboratory tools cannot
be selected. Directory and wildcard scopes are refused.
The Runner does not infer which code implements learning versus measurement.
When one source file contains both, restoring the whole file also restores both.
There is no automatic whole-recipe rollback.
It verifies the result.
It does not assign a model role.
