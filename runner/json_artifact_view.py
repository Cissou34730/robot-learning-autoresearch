"""Temporary, verified-byte snapshots and lazy views of large JSON documents."""

from __future__ import annotations

import codecs
import hashlib
import json
import mmap
import re
import sys
import tempfile
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from contextlib import ExitStack
from pathlib import Path
from threading import Lock
from typing import Any, Self

_WHITESPACE = re.compile(rb"[ \t\r\n]*")
_STRING_SPECIAL = re.compile(rb'["\\\x00-\x1f]')
_STRUCTURE = re.compile(rb'["{}\[\]]')
_NUMBER = re.compile(rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_FLOAT_PART = re.compile(rb"[.eE]")
_HEX = frozenset(b"0123456789abcdefABCDEF")
SCALAR_BYTES = 32 * 1024 * 1024
_VALIDATED_ROOT_LIMIT = 128
_VALIDATED_ROOTS: OrderedDict[tuple[str, int, int], tuple[int, int]] = OrderedDict()
_VALIDATION_LOCK = Lock()


class OutputBudgetExceeded(ValueError):
    pass


class TraversalBudgetExceededError(Exception):
    pass


class JsonDocument:
    def __init__(self, path: Path):
        self.resources = ExitStack()
        self.buffer: mmap.mmap
        digest = hashlib.sha256()
        self.original_bytes = 0
        try:
            self.snapshot = self.resources.enter_context(tempfile.TemporaryFile())  # noqa: SIM115 - ExitStack owns the snapshot.
            with path.open("rb") as source:
                encoding = json.detect_encoding(source.read(4))
                source.seek(0)
                decoder = codecs.getincrementaldecoder(encoding)("surrogatepass")
                while block := source.read(1024 * 1024):
                    digest.update(block)
                    self.original_bytes += len(block)
                    self.snapshot.write(
                        decoder.decode(block).encode("utf-8", "surrogatepass")
                    )
                self.snapshot.write(
                    decoder.decode(b"", final=True).encode("utf-8", "surrogatepass")
                )
            self.fingerprint = digest.hexdigest()
            self.snapshot.flush()
            if not self.snapshot.tell():
                raise ValueError("artifact is not valid JSON: empty document")
            self.buffer = self.resources.enter_context(
                mmap.mmap(self.snapshot.fileno(), 0, access=mmap.ACCESS_READ)
            )
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self.resources.close()

    def space(self, position: int) -> int:
        return _WHITESPACE.match(self.buffer, position).end()

    def invalid(self, position: int) -> None:
        raise ValueError(f"artifact is not valid JSON at normalized byte {position}")

    def string_end(self, position: int) -> int:
        position += 1
        while match := _STRING_SPECIAL.search(self.buffer, position):
            position = match.start()
            character = self.buffer[position]
            if character == 34:
                return position + 1
            if character != 92 or position + 1 >= len(self.buffer):
                self.invalid(position)
            escape = self.buffer[position + 1]
            if escape in b'"\\/bfnrt':
                position += 2
            elif escape == 117 and position + 6 <= len(self.buffer):
                if any(
                    byte not in _HEX
                    for byte in self.buffer[position + 2 : position + 6]
                ):
                    self.invalid(position)
                position += 6
            else:
                self.invalid(position)
        self.invalid(position)

    def scalar_end(self, position: int) -> int:
        if self.buffer[position] == 34:
            return self.string_end(position)
        for literal in (b"true", b"false", b"null", b"NaN", b"Infinity", b"-Infinity"):
            if self.buffer[position : position + len(literal)] == literal:
                return position + len(literal)
        match = _NUMBER.match(self.buffer, position)
        if match is None:
            self.invalid(position)
        end = match.end()
        digits_limit = sys.get_int_max_str_digits()
        if (
            digits_limit
            and end - position - (self.buffer[position] == 45) > digits_limit
            and _FLOAT_PART.search(self.buffer, position, end) is None
        ):
            raise ValueError("JSON integer exceeds the installed Python digit limit")
        return end

    def root(self) -> Any:
        key = (
            self.fingerprint,
            sys.get_int_max_str_digits(),
            sys.getrecursionlimit(),
        )
        with _VALIDATION_LOCK:
            span = _VALIDATED_ROOTS.get(key)
            if span is None:
                span = self._validate_root()
                _VALIDATED_ROOTS[key] = span
                if len(_VALIDATED_ROOTS) > _VALIDATED_ROOT_LIMIT:
                    _VALIDATED_ROOTS.popitem(last=False)
            _VALIDATED_ROOTS.move_to_end(key)
        return self.value(*span)

    def _validate_root(self) -> tuple[int, int]:
        # Validate the complete snapshot, including data outside the selection.
        stack = ["root:value"]
        position = 0
        root_end = 0
        while stack:
            if stack == ["root:done"]:
                root_end = position
            position = self.space(position)
            state = stack[-1]
            character = self.buffer[position] if position < len(self.buffer) else None
            if state == "root:done":
                if character is not None:
                    self.invalid(position)
                break
            if state in {"array:first", "object:first"}:
                close = 93 if state.startswith("array") else 125
                if character == close:
                    stack.pop()
                    position += 1
                    continue
                stack[-1] = "array:value" if close == 93 else "object:key"
                continue
            if state == "object:key":
                if character != 34:
                    self.invalid(position)
                position = self.space(self.string_end(position))
                if position >= len(self.buffer) or self.buffer[position] != 58:
                    self.invalid(position)
                position += 1
                stack[-1] = "object:value"
                continue
            if state in {"array:after", "object:after"}:
                close = 93 if state.startswith("array") else 125
                if character == close:
                    stack.pop()
                    position += 1
                elif character == 44:
                    position += 1
                    stack[-1] = "array:value" if close == 93 else "object:key"
                else:
                    self.invalid(position)
                continue
            if character is None:
                self.invalid(position)
            stack[-1] = {
                "root:value": "root:done",
                "array:value": "array:after",
                "object:value": "object:after",
            }[state]
            if character in (91, 123):
                if len(stack) >= sys.getrecursionlimit():
                    raise ValueError(
                        "JSON nesting exceeds the installed Python recursion limit"
                    )
                stack.append("array:first" if character == 91 else "object:first")
                position += 1
            else:
                position = self.scalar_end(position)
        return self.space(0), root_end

    def value_end(self, position: int) -> int:
        if self.buffer[position] not in (91, 123):
            return self.scalar_end(position)
        depth = 1
        position += 1
        while match := _STRUCTURE.search(self.buffer, position):
            position = match.start()
            character = self.buffer[position]
            if character == 34:
                position = self.string_end(position)
                continue
            depth += 1 if character in (91, 123) else -1
            position += 1
            if depth == 0:
                return position
        self.invalid(position)

    def value(self, start: int, end: int) -> Any:
        cls = {123: JsonObject, 91: JsonArray}.get(self.buffer[start], JsonScalar)
        return cls(self, start, end)


class JsonScalar:
    def __init__(self, document: JsonDocument, start: int, end: int):
        self.document, self.start, self.end = document, start, end

    def decoded(self) -> Any:
        if self.end - self.start > SCALAR_BYTES:
            raise ValueError(
                "Selected JSON scalar exceeds the decode budget. Use action=read for its original bytes."
            )
        return json.loads(self.document.buffer[self.start : self.end])

    def __eq__(self, other: object) -> bool:
        value, other = self.decoded(), scalar_value(other)
        return value is other or value == other


class JsonObject(JsonScalar, Mapping):
    def __init__(self, document: JsonDocument, start: int, end: int):
        super().__init__(document, start, end)
        self._index: dict[str, tuple[int, int]] | None = None
        self._wide = False

    def entries(self) -> Iterator[tuple[str, int, int]]:
        document = self.document
        position = document.space(self.start + 1)
        while position < self.end - 1:
            key_end = document.string_end(position)
            key = JsonScalar(document, position, key_end).decoded()
            start = document.space(document.space(key_end) + 1)
            end = document.value_end(start)
            yield key, start, end
            position = document.space(end)
            if position < self.end - 1:
                position = document.space(position + 1)

    def cached_index(self) -> dict[str, tuple[int, int]] | None:
        if self._index is not None or self._wide:
            return self._index
        index = {}
        key_bytes = 0
        for key, start, end in self.entries():
            key_bytes += len(key)
            if len(index) >= 50_000 or key_bytes > SCALAR_BYTES:
                self._wide = True
                return None
            index[key] = (start, end)
        self._index = index
        return index

    def index(self) -> dict[str, tuple[int, int]]:
        index = self.cached_index()
        if index is None:
            raise TraversalBudgetExceededError(
                "JSON object field enumeration exceeded the bounded view budget. Narrow the path."
            )
        return index

    def __iter__(self) -> Iterator[str]:
        return iter(self.index())

    def __len__(self) -> int:
        return len(self.index())

    def __getitem__(self, key: str) -> Any:
        index = self.cached_index()
        if index is not None:
            return self.document.value(*index[key])
        found = None
        for candidate, start, end in self.entries():
            if candidate == key:
                found = (start, end)
        if found is None:
            raise KeyError(key)
        return self.document.value(*found)

    def items(self) -> Iterator[tuple[str, Any]]:
        for key, span in self.index().items():
            yield key, self.document.value(*span)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (dict, JsonObject)):
            return False
        return dict(self.items()) == dict(other.items())


class JsonArray(JsonScalar):
    def spans(self) -> Iterator[tuple[int, int]]:
        document = self.document
        position = document.space(self.start + 1)
        while position < self.end - 1:
            end = document.value_end(position)
            yield position, end
            position = document.space(end)
            if position < self.end - 1:
                position = document.space(position + 1)

    def __iter__(self) -> Iterator[Any]:
        for start, end in self.spans():
            yield self.document.value(start, end)

    def __len__(self) -> int:
        return sum(1 for _ in self.spans())

    def __getitem__(self, index: int) -> Any:
        for current, span in enumerate(self.spans()):
            if current == index:
                return self.document.value(*span)
        raise IndexError(index)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (list, JsonArray)):
            return False
        return len(self) == len(other) and all(
            left == right for left, right in zip(self, other, strict=True)
        )


def scalar_value(value: Any) -> Any:
    if isinstance(value, JsonScalar) and not isinstance(value, (JsonObject, JsonArray)):
        return value.decoded()
    return value


def bounded_value(value: Any, byte_limit: int) -> Any:
    remaining = byte_limit

    def charge(text: str) -> None:
        nonlocal remaining
        remaining -= len(text.encode("utf-8"))
        if remaining < 0:
            raise OutputBudgetExceeded("selected value exceeds the output byte budget")

    def convert(item: Any) -> Any:
        if isinstance(item, (dict, JsonObject)):
            if isinstance(item, JsonObject) and item.cached_index() is None:
                raise OutputBudgetExceeded(
                    "selected object exceeds the output byte budget"
                )
            charge("{}")
            output = {}
            for key, child in item.items():
                charge(("," if output else "") + json.dumps(key) + ":")
                output[key] = convert(child)
            return output
        if isinstance(item, (list, JsonArray)):
            charge("[]")
            output = []
            for child in item:
                if output:
                    charge(",")
                output.append(convert(child))
            return output
        if (
            isinstance(item, JsonScalar)
            and item.document.buffer[item.start] == 34
            and item.end - item.start > max(remaining, 0) * 6
        ):
            raise OutputBudgetExceeded("selected string exceeds the output byte budget")
        item = scalar_value(item)
        charge(json.dumps(item, separators=(",", ":")))
        return item

    return convert(value)
