# Scientific instruments: inquiry and official assessment

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Inquiry operations

Use this interface to open or reframe an inquiry:

```json
{
  "inquiry": {
    "action": {"type": "string"},
    "question": {"type": "string"},
    "goal_connection": {"type": "string"},
    "closure_condition": {"type": "string"},
    "rationale": {"type": "string"}
  }
}
```

Set `action` to `open` or `reframe`. All other fields are required and contain
text. The Runner accepts `open` in a goal-review session, after the earlier
inquiry closed. The Runner accepts `reframe` in the inquiry session of the
active inquiry.

Use this interface to close an inquiry:

```json
{
  "inquiry": {
    "action": {"type": "string"},
    "outcome": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Set `action` to `close`. The `outcome` and `reason` fields are required and
contain text. The Runner accepts `close` in the inquiry session of the active
inquiry. Inquiry operations use `E#` identities.

## Request for the official assessment

```json
{
  "campaign_conclusion": {
    "action": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Set `action` to `request_official_assessment`, the only action of
`campaign_conclusion`. The `reason` field is required and contains text. The
Runner accepts the request in a goal-review session, after the earlier inquiry
closed. The request also requires an explicit best-known candidate. The Runner
executes the protected official assessment and records its result.
