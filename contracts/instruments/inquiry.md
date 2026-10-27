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

Set `action` to `open` or `reframe`. All other fields are required and must not
be empty. The Runner accepts `open` only in a goal-review session when no
inquiry is active. The Runner accepts `reframe` only in the inquiry session of
the active inquiry.

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

Set `action` to `close`. The `outcome` and `reason` fields are required and must
not be empty. The Runner accepts `close` only in the inquiry session of the
active inquiry. Inquiry operations do not use a training identity.

## Request for the official assessment

```json
{
  "campaign_conclusion": {
    "action": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Set `action` to `request_official_assessment`. The `reason` field is required
and must not be empty. The Runner accepts the request only in a goal-review
session when no inquiry is active. The request also needs a best-known
candidate. The Runner executes the protected official assessment and records
its result. No other action is available for `campaign_conclusion`.
