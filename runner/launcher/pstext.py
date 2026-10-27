"""Text rendering of JSON state values exactly as the PowerShell launcher did.

PI-visible summaries were built from ``ConvertFrom-Json`` objects with string
interpolation and ``ConvertTo-Json -Compress``. These helpers reproduce that
rendering (.NET number formats, ISO strings parsed as local date-times) so the
text the PI receives does not change with the launcher's language.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

_ISO_DATE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?P<fraction>\.\d+)?(?P<zone>Z|[+-]\d{2}:\d{2})?$"
)


def _parsed_date(text: str) -> tuple[datetime, bool] | None:
    """Newtonsoft's ISO date detection; returns (value, has_zone)."""
    if not 19 <= len(text) <= 40 or not text[0].isdigit() or text[10] != "T":
        return None
    match = _ISO_DATE.match(text)
    if match is None:
        return None
    fraction = (match["fraction"] or "")[1:8]
    base = text[:19]
    zone = match["zone"]
    try:
        value = datetime.fromisoformat(
            base
            + (f".{fraction.ljust(6, '0')[:6]}" if fraction else "")
            + ("+00:00" if zone == "Z" else zone or "")
        )
    except ValueError:
        return None
    if zone:
        return value.astimezone(), True
    return value, False


def _shortest_digits(value: float) -> tuple[str, int, bool]:
    """Shortest round-trip digits, decimal exponent and sign of a float."""
    sign, digits, exponent = Decimal(repr(value)).as_tuple()
    text = "".join(str(digit) for digit in digits).rstrip("0") or "0"
    adjusted = len(digits) + exponent - 1
    return text, adjusted, bool(sign)


def _scientific(digits: str, exponent: int, negative: bool) -> str:
    mantissa = digits[0] + (f".{digits[1:]}" if len(digits) > 1 else "")
    sign = "-" if exponent < 0 else "+"
    return f"{'-' if negative else ''}{mantissa}E{sign}{abs(exponent):02d}"


def _fixed(digits: str, exponent: int, negative: bool) -> str:
    if exponent >= len(digits) - 1:
        text = digits + "0" * (exponent - len(digits) + 1)
    elif exponent >= 0:
        text = f"{digits[: exponent + 1]}.{digits[exponent + 1 :]}"
    else:
        text = f"0.{'0' * (-exponent - 1)}{digits}"
    return ("-" if negative else "") + text


def _special(value: float) -> str | None:
    if math.isnan(value):
        return "NaN"
    if value in {float("inf"), float("-inf")}:
        return "Infinity" if value > 0 else "-Infinity"
    return None


def interpolated_number(value: float) -> str:
    """A double inside a PowerShell string: .NET "G15", invariant culture."""
    special = _special(value)
    if special is not None:
        return special
    if value == 0:
        return "-0" if str(value).startswith("-") else "0"
    rounded = float(format(value, ".15g"))
    digits, exponent, negative = _shortest_digits(rounded)
    if exponent < -4 or exponent >= 15:
        return _scientific(digits, exponent, negative)
    return _fixed(digits, exponent, negative)


def json_number(value: float) -> str:
    """A double written by ``ConvertTo-Json``: shortest digits, ".0" when integral."""
    special = _special(value)
    if special is not None:
        return f'"{special}"'
    digits, exponent, negative = _shortest_digits(value)
    if value == 0:
        return "-0.0" if negative else "0.0"
    if exponent < -4 or exponent >= 17:
        return _scientific(digits, exponent, negative)
    text = _fixed(digits, exponent, negative)
    return text if "." in text else f"{text}.0"


def invariant_fixed_one(value: float) -> str:
    """``[string]::Format(InvariantCulture, "{0:0.0}", value)``."""
    rounded = Decimal(format(value, ".15g")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{rounded:.1f}"


def _date_text(value: datetime) -> str:
    return value.strftime("%m/%d/%Y %H:%M:%S")


def _date_json(value: datetime, has_zone: bool) -> str:
    text = value.strftime("%Y-%m-%dT%H:%M:%S")
    if value.microsecond:
        text += f".{value.microsecond:06d}".rstrip("0")
    if has_zone:
        offset = value.strftime("%z")
        text += f"{offset[:3]}:{offset[3:]}"
    return text


def text(value: object) -> str:
    """``"$($value)"`` for a value that came from ``ConvertFrom-Json``."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return interpolated_number(value)
    if isinstance(value, str):
        parsed = _parsed_date(value)
        return _date_text(parsed[0]) if parsed else value
    if isinstance(value, list):
        return " ".join(text(item) for item in value)
    if isinstance(value, dict):
        return (
            "@{" + "; ".join(f"{key}={text(item)}" for key, item in value.items()) + "}"
        )
    return str(value)


def to_json(value: object) -> str:
    """``ConvertTo-Json -Compress`` of a value that came from ``ConvertFrom-Json``."""
    if value is None or isinstance(value, bool | int):
        return json.dumps(value)
    if isinstance(value, float):
        return json_number(value)
    if isinstance(value, str):
        parsed = _parsed_date(value)
        rendered = _date_json(*parsed) if parsed else value
        return json.dumps(rendered, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(to_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"{json.dumps(str(key), ensure_ascii=False)}:{to_json(item)}"
                for key, item in value.items()
            )
            + "}"
        )
    return json.dumps(str(value), ensure_ascii=False)


def pipeline_json(items: list) -> str:
    """``$items | ConvertTo-Json -Compress``: one item is not wrapped in an array."""
    if len(items) == 1:
        return to_json(items[0])
    return to_json(items)


def truthy(value: object) -> bool:
    """PowerShell truthiness; a one-element array takes its element's value."""
    if isinstance(value, list):
        if not value:
            return False
        return truthy(value[0]) if len(value) == 1 else True
    if isinstance(value, dict):
        return True
    return bool(value)


def items(value: object) -> list:
    """``@($value)`` and pipeline input: ``$null`` is one item, a list its elements."""
    return list(value) if isinstance(value, list) else [value]


def count(value: object) -> int:
    """``$value.Count``: zero for ``$null``, one for a scalar."""
    if value is None:
        return 0
    return len(value) if isinstance(value, list) else 1


def field(value: object, name: str) -> object:
    """Property access on a ``ConvertFrom-Json`` object; ``$null`` otherwise."""
    return value.get(name) if isinstance(value, dict) else None


def same(left: object, right: object) -> bool:
    """``-eq`` between strings: case-insensitive."""
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return left == right


def join(values: object, separator: str) -> str:
    """``$values -join $separator``."""
    if values is None:
        return ""
    return separator.join(text(item) for item in items(values))
