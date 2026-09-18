# Issue 33-42 integration notes

This branch (`issue-33-42-integration`) carries only the reviewed harness
remediation commits. It is based on the harness tip `50049ae` of
`issue-33-42-decision-quality`, which sits on `fb87b98`
(`issue-30-decision-quality-remediation`).

No campaign commit is included. Campaign resets, scientific-recipe commits,
retained model artifacts, evaluation artifacts and campaign state live on the
original branch refs and are preserved separately:

- `issue-33-42-decision-quality` - implementation plus the experimental campaign
  that ran on top of it.
- `issue-30-decision-quality-remediation` - the campaign branch the work forked
  from.

Merging this branch therefore brings the harness changes without coupling them
to any campaign's state or artifacts.

## Harness commits

| Commit | Scope |
| --- | --- |
| `a3fb5aa` | #42 decouple research-evaluation defaults from the official panel |
| `c20ab00` | #35 protect shared-episode accounting (audit finding 6 follow-up: statistic split out) |
| `7523c65` | #36 training-only environment split |
| `ac3b69e` | #41.2 brief per-section seams |
| `830a726` | #38 neutral instrument presentation |
| `c04da0d` | #39 ordered evaluation-round provenance |
| `e89055c` | #34 cost and coverage visibility |
| `d2c417f` | audit findings 1 and 4: identity-level coverage accounting and reused-operation resolution |
| `f0b16c0` | #37 advisory stopping contract |
| `d9bad26` | #40 optional researcher tests (verification) |
| `b20dc86` | #41.1/41.4 ownership existence guard and housekeeping |
| `50049ae` | #33 v4 three-phase lifecycle verification |
| `051cd51` | audit findings 2, 3, 5, 6, 7, 8: purpose, designation tenure, integer successes, researcher-owned statistic, simulation |

## Compatibility

- Evaluation-semantics fingerprint: commits that add or move files under
  `robot_learning/scenario/` or the evaluation runtime paths change the
  fingerprint. Existing evidence stays readable, but measurements recorded under
  a previous fingerprint are not pooled automatically. #41's deferred relocation
  is a deliberate compatibility event and is scheduled at a campaign boundary.
- Measurement records now carry an integer `successes` and a `purpose`; records
  written before this branch normalise to `selection` and are not used as
  stopping evidence.
- New schema fields (`designation_ordinal`, `best_known_designation_counter`,
  `evaluation_rounds`, per-measurement `purpose`) are additive; readers tolerate
  their absence.

## Validation

`uv run pytest` (benchmark + autoresearch, the default selection) is green on
this branch. `tests/e2e` has pre-existing failures on the base commit caused by
retired `tests/scenario` / `tests/training` expectations; they are not introduced
here.
