# Scientific instruments: measurement

Part of the instrument contract indexed in `contracts/instruments.md`.

## Measurement operation

```json
{
  "measurement": {
    "description": {"type": "string"},
    "rationale": {"type": "string"},
    "measurements": {"type": "array"},
    "paired_comparisons": {"type": "array"}
  }
}
```

The `description`, `rationale`, and `measurements` fields are required.
The `description` and `rationale` strings must be non-empty.
The `measurements` array must be non-empty.
The `paired_comparisons` field is optional.

A `research_evaluation` entry uses this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "episodes": {"type": "integer"},
  "seed": {"type": "integer"},
  "label": {"type": "string"}
}
```

Set `instrument` to `research_evaluation`.
The `candidate`, `episodes`, and `seed` fields are required.
The `label` field is optional.
The candidate value must be non-empty.
The episode count must be positive.
The seed must be non-negative.

The episode panel starts at `seed` and contains `episodes` consecutive episode seeds.
The Runner rejects overlap with protected benchmark evidence.

A `task_reference` entry uses this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "label": {"type": "string"}
}
```

Set `instrument` to `task_reference`.
The `candidate` field is required and must be non-empty.
The `label` field is optional.
This instrument uses its protected fixed panel.
Its episodes are deterministic: measuring the same saved artifact again
reproduces the recorded result and supplies no additional sample.
Its controller execution follows the saved-runtime contract under
[Saved controller execution](coding.md#saved-controller-execution), not the PI-owned
research environment.

A `python_module` entry runs one PI-owned Python module as a measurement.
It can characterize the embodied system, simulation, learning process, or
another scientific quantity. It does not require a learned candidate.

Use this interface:

```json
{
  "instrument": {"type": "string"},
  "module": {"type": "string"},
  "args": {"type": "array", "items": {"type": "string"}},
  "artifact": {"type": "string"},
  "label": {"type": "string"},
  "inputs": {
    "type": "object",
    "additionalProperties": {
      "type": "object",
      "properties": {
        "operation_id": {"type": "string"},
        "artifact_index": {"type": "integer"}
      },
      "required": ["operation_id", "artifact_index"],
      "additionalProperties": false
    }
  }
}
```

Set `instrument` to `python_module`.
The `module`, `args`, and `artifact` fields are required.
The `label` and `inputs` fields are optional.
Each `args` element is one literal module argument, not a full launch command.
Do not include the module name or launcher in `args`.
Pass a concrete output path in the arguments when the module requires it.
`artifact` declares the expected output. It does not substitute an argument.
Unresolved `{artifact}` tokens are rejected before acceptance.
The module must be under `robot_learning.lab`, `robot_learning.scenario`, or
`robot_learning.training`.
The artifact must be a campaign JSON path under
`campaigns/evaluations/<current-campaign-id>/`.
`campaigns/brief.md` gives the exact evaluation root for the current campaign.

`inputs` binds PI-selected names to recorded JSON artifacts from completed
measurements in the current campaign. Names must be identifiers.
Each argument placeholder `{input:NAME}` uses a declared name.
Every declared input must appear in the arguments.
The output artifact cannot overwrite a named input.
The Runner resolves the selected operation and artifact index, verifies the
recorded fingerprint, and replaces the placeholder with its canonical path.
Acceptance freezes the resolved identities. Execution checks them again before
the module runs. Results retain the input identities in their compact metadata.
Missing, changed, or unavailable inputs are errors. The Runner never chooses
another artifact, changes the module, or decides how the PI repairs the request.
Arguments without input placeholders remain unchanged.
Execution errors identify the accepted module arguments and declared output.
A successful module exit without that output is an operation failure.
Runner reports these facts without diagnosing the source or selecting a repair.

A paired-comparison entry uses this interface:

```json
{
  "candidate": {"type": "string"},
  "reference": {"type": "string"}
}
```

Both fields are required and must be non-empty.
Both candidates must appear in planned `research_evaluation` measurements that
use the same episode seeds.

The result keeps the accepted candidate artifacts, evaluator semantics, module
sources, PI-owned scientific changes, and effective parameters.
It also keeps reused-panel identities and paired-comparison integrity facts.

Under the same evaluation semantics or task-reference panel, an episode seed
identifies a deterministic episode for a saved artifact. When a
`research_evaluation` or `task_reference` measurement shares episodes with an
earlier completed measurement of the same saved artifact and instrument, its
result lists `repeats_earlier_measurements` with the earlier operation ID,
label and number of shared episodes. Shared episodes reproduce recorded
outcomes; they are not independent confirmation.

### Artifact contents metadata

A completed measurement record keeps compact result facts, the artifact path,
and the immutable artifact fingerprint.
`evaluation_artifact_contents` adds navigation metadata from the JSON artifact:

```json
{
  "scope": {"type": "string"},
  "truncated": {"type": "boolean"},
  "sections": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "path": {"type": "string"},
        "type": {"type": "string"},
        "entries": {"type": "integer"},
        "field_names": {"type": "array", "items": {"type": "string"}},
        "field_count": {"type": "integer"},
        "fields_omitted": {"type": "boolean"}
      }
    }
  }
}
```

The scope is `structure_only`.
The inventory contains no measurement values or scientific interpretation.
Paths use JSON Pointer syntax.
The empty pointer identifies the root.
Escaped tokens identify object members.
Object and array sections include their entry counts.

The inventory traverses object members breadth-first.
It does not expand array elements into individual paths.
When present, `field_names` contains the union of keys in actual object rows of
an array. It is not a schema inferred from one sample row.

The inventory has a bounded metadata size.
`truncated` identifies omitted sections or field names.
`fields_omitted` and `field_count` identify an array whose field list did not fit.
An untruncated inventory still describes structure, not the full evidence.
The full artifact remains unchanged at its recorded path in the local archive
`campaigns/evaluations/<current-campaign-id>/`.

This metadata applies to all measurement instruments.
It does not require a scenario-specific section or field.
Live feedback and the brief distinguish the reduced result summary from the
artifact contents. They also identify results with no recorded inventory.
