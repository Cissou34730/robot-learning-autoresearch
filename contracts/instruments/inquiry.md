# Scientific instruments: inquiry and conclusion

Part of the instrument contract indexed in `contracts/instruments.md`.

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

Set `action` to `open` or `reframe`.
All other fields are required and must be non-empty.
The Runner accepts `open` only during goal review when no inquiry is active.
The Runner accepts `reframe` only during the active inquiry session.

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

Set `action` to `close`.
The `outcome` and `reason` fields are required and must be non-empty.
The Runner accepts `close` only during the active inquiry session.
Inquiry operations do not allocate a training identity.

## Campaign conclusion

```json
{
  "campaign_conclusion": {
    "action": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Set `action` to `request_official_assessment`.
The `reason` field is required and must be non-empty.
The Runner accepts the request only during goal review when no inquiry is active.
The request also requires an explicit best-known candidate.
The Runner executes the protected official assessment and records its result.
No other campaign-conclusion action is supported.
