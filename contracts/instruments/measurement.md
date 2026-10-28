# Scientific instruments: measurement

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

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

The `description`, `rationale` and `measurements` fields are required. The
`description` and `rationale` strings must not be empty. The `measurements`
array must not be empty. The `paired_comparisons` field is optional.

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

Set `instrument` to `research_evaluation`. The `candidate`, `episodes` and
`seed` fields are required. The `label` field is optional. The candidate value
must not be empty. The episode count must be positive. The seed must not be
negative.

The episode panel starts at `seed` and contains `episodes` consecutive episode
seeds. The Runner rejects a panel that overlaps the protected benchmark
evidence.

A `task_reference` entry uses this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "label": {"type": "string"}
}
```

Set `instrument` to `task_reference`. The `candidate` field is required and
must not be empty. The `label` field is optional.

This instrument uses its
protected fixed panel. Its episodes are deterministic. A second measurement of
the same saved artifact reproduces the recorded result and adds no sample. Its
controller execution follows the saved-runtime contract under
[Saved controller execution](coding.md#saved-controller-execution), not the
PI-owned research environment.

A `python_module` entry runs one PI-owned Python module as a measurement.
It can characterize the embodied system, the simulation, the learning process,
or another scientific quantity. It does not require a candidate.

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
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "operation_id": {"type": "string"},
            "artifact_index": {"type": "integer"}
          },
          "required": ["operation_id", "artifact_index"],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {"candidate": {"type": "string"}},
          "required": ["candidate"],
          "additionalProperties": false
        }
      ]
    }
  }
}
```

Set `instrument` to `python_module`. The `module`, `args` and `artifact` fields
are required. The `label` and `inputs` fields are optional.

Each `args` element is one literal argument of the module, not a full launch
command. Do not put the module name or a command prefix such as `python -m`
in `args`. When the module needs an output path, give a specific output path
in the arguments. `artifact`
declares the expected output. It does not replace an argument. Before
acceptance, the Runner rejects unresolved `{artifact}` tokens.

The module must be in `robot_learning.lab`, `robot_learning.scenario` or
`robot_learning.training`. The artifact must be a campaign JSON path in
`campaigns/evaluations/<current-campaign-id>/`. `campaigns/brief.md` gives the
exact evaluation folder of the current campaign.

`inputs` binds names that the PI selects to recorded JSON artifacts of
completed measurements in the current campaign, or to a candidate. Names must
be identifiers. A candidate input names a candidate identity or a role. It
resolves to the `model.zip` file in the verified archive of this candidate. The
saved runtime and the normalization files are in the same folder.

Each argument placeholder `{input:NAME}` uses a declared name. Each declared
input must occur in the arguments. The output artifact cannot replace a named
input. The Runner finds the selected operation and artifact index, verifies the
recorded fingerprint and replaces the placeholder with the canonical path.

Acceptance freezes the resolved identities. Before the module runs, the
execution checks them again. The results keep the input identities in their
compact metadata. Missing, changed or unavailable inputs are errors.

The Runner
never chooses another artifact or changes the module. It does not decide how
the PI repairs the request. Arguments without input placeholders do not change.

Execution errors give the accepted module arguments and the declared output.
When a module ends with success but does not write that output, the operation
fails. The Runner reports these facts. It does not diagnose the source code or
select a repair. When a module runs episodes, its artifact can list their seeds
in a top-level `episode_seeds` array. The Runner then reports the overlap with
other measurements.

A paired-comparison entry uses this interface:

```json
{
  "candidate": {"type": "string"},
  "reference": {"type": "string"}
}
```

Both fields are required and must not be empty. The candidate must occur in a
planned `research_evaluation` measurement. The reference must agree with one of
these two conditions:

- it occurs in a planned `research_evaluation` measurement on the same episode
  seeds
- it has an earlier completed `research_evaluation` of the same saved artifact
  on these seeds, under the current evaluation semantics

In the second case, the Runner pairs the candidate with the recorded episode
outcomes of the reference. It does not run the reference again. Deterministic
episodes reproduce these episode outcomes exactly.

The development panel is the `research_evaluation` with seed 100000 and 400
episodes.

The result keeps the accepted candidate artifacts, the evaluator semantics, the
module sources, the PI-owned scientific changes and the effective parameters. It
also keeps the identities of reused panels and the integrity facts of the
paired comparisons.

### Shared episodes

Under the same evaluation semantics or the same task-reference panel, an
episode seed identifies one deterministic episode for a saved artifact. A
`research_evaluation` or `task_reference` measurement can share episodes with
an earlier completed measurement of the same saved artifact and instrument.
Then its result lists `repeats_earlier_measurements`, with the earlier
operation identity, the label and the number of shared episodes. Shared
episodes reproduce the recorded episode outcomes. They are not an independent
confirmation.

An episode seed also identifies the same situation for other candidates. When
a `research_evaluation` measurement shares episode seeds with any earlier
completed measurement, its result lists `episodes_seen_in_earlier_measurements`.
This list gives each earlier operation identity, label, instrument, candidate
and number of shared episodes.

A `python_module` artifact can declare the episode seeds that it used, as a
top-level `episode_seeds` list of integers that are not negative. Its result
then records them as `declared_episode_seed_ranges` and lists the same overlap
with earlier measurements. A declaration with an incorrect format makes the
measurement fail.

Earlier exposure of the episodes does not change the recorded result. But a
result on episodes that you already used to select or change a candidate can
be higher than the result on new episodes. You decide if the situations are
fresh enough for the intended use.

### Artifact contents metadata

A completed measurement record keeps the compact result facts, the artifact
path and the immutable fingerprint of the artifact. `evaluation_artifact_contents` adds
navigation metadata from the JSON artifact:

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

The scope is `structure_only`. The inventory contains no measured values and no
scientific interpretation. Paths use the JSON Pointer syntax. The empty pointer
identifies the root. Escaped tokens identify object members. Object sections
and array sections include their entry counts.

The inventory traverses the object members breadth-first. It does not expand
array elements into separate paths. When `field_names` is present, it contains
the union of the keys of the actual object rows of an array. It is not a schema
inferred from one sample row.

The inventory has a bounded metadata size. `truncated` shows that sections or
field names are missing. `fields_omitted` and `field_count` identify an array
whose field list did not fit. An inventory that is not truncated still shows
the structure, not the full evidence. The full artifact does not change. It
stays at its recorded path in the local archive
`campaigns/evaluations/<current-campaign-id>/`.

This metadata applies to all measurement instruments. It does not require a
task-specific section or field. The live feedback and the brief distinguish the
reduced result summary from the artifact contents. They also identify the
results that have no recorded inventory.
