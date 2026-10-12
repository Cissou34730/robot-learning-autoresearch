"""Read-only definitions from the installed, human-owned scientific libraries."""

from __future__ import annotations

import codecs
import dataclasses
import hashlib
import importlib
import inspect
import json
from importlib.metadata import version
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScientificAPIReferenceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library: Literal["mujoco", "gymnasium", "stable_baselines3"]
    symbol: str = Field(default="", max_length=512)
    action: Literal["definition", "members"] = "definition"
    contains: str = Field(default="", max_length=128)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    max_bytes: int = Field(default=16_384, ge=512, le=65_536)


def _owned_definition(value: object, library: str) -> bool:
    if inspect.ismodule(value):
        owner = value.__name__
    elif inspect.isclass(value) or inspect.isroutine(value):
        owner = getattr(value, "__module__", "") or ""
    else:
        return isinstance(
            value, (property, classmethod, staticmethod)
        ) or inspect.isdatadescriptor(value)
    return owner == library or owner.startswith(library + ".")


def _kind(value: object) -> str:
    if inspect.ismodule(value):
        return "module"
    if inspect.isclass(value):
        return "class"
    if inspect.isroutine(value):
        return "function"
    if isinstance(value, property) or inspect.isdatadescriptor(value):
        return "attribute"
    return type(value).__name__


def _native_declaration(symbol: str) -> dict | None:
    parts = symbol.split(".")
    if len(parts) == 2 and parts[0] in {"MjModel", "MjData"}:
        from mujoco.introspect.structs import STRUCTS

        declaration = STRUCTS["mj" + parts[0][2:]]
        field = next(
            (field for field in declaration.fields if field.name == parts[1]), None
        )
        return dataclasses.asdict(field) if field is not None else None
    if len(parts) == 1:
        from mujoco.introspect.functions import FUNCTIONS

        function = FUNCTIONS.get(symbol)
        return dataclasses.asdict(function) if function is not None else None
    return None


def read_reference(params: ScientificAPIReferenceParams) -> dict:
    parts = params.symbol.split(".") if params.symbol else []
    if any(not part.isidentifier() or part.startswith("_") for part in parts):
        raise ValueError(
            "Select a public dotted API symbol, not a path or private attribute."
        )
    module = importlib.import_module(params.library)
    result = {
        "library": params.library,
        "version": version(params.library.replace("_", "-")),
        "symbol": params.symbol,
        "execution_scope": "Installed definitions only; no API function or constructor is called.",
    }
    value = module
    for index, part in enumerate(parts):
        if not (inspect.ismodule(value) or inspect.isclass(value)):
            raise ValueError(
                "API symbols may descend through library modules and classes only."
            )
        try:
            value = inspect.getattr_static(value, part)
        except AttributeError:
            return {
                **result,
                "status": "symbol_not_found",
                "missing_member": part,
                "container": ".".join(parts[:index]),
            }
        if not _owned_definition(value, params.library):
            raise ValueError(
                "This symbol is not an API definition owned by the selected library."
            )

    if params.action == "members":
        if not (inspect.ismodule(value) or inspect.isclass(value)):
            raise ValueError("Member browsing selects a library module or class.")
        members = [
            {"name": name, "kind": _kind(member)}
            for name, member in inspect.getmembers_static(value)
            if not name.startswith("_")
            and params.contains.casefold() in name.casefold()
        ]
        if params.offset > len(members):
            raise ValueError("Member offset exceeds the available API members.")
        page = members[params.offset : params.offset + params.limit]
        next_offset = params.offset + len(page)
        return {
            **result,
            "status": "members",
            "members": page,
            "count": len(members),
            "offset": params.offset,
            "next_offset": next_offset if next_offset < len(members) else None,
        }

    sections = []
    signature = None
    signature_unavailable = None
    definition = (
        value.__func__ if isinstance(value, (classmethod, staticmethod)) else value
    )
    try:
        signature = str(inspect.signature(definition))
        sections.append("Python signature:\n" + signature)
    except (TypeError, ValueError) as error:
        signature_unavailable = str(error)
    doc = inspect.getdoc(definition)
    if doc:
        sections.append("Installed documentation:\n" + doc)
    if params.library == "mujoco":
        declaration = _native_declaration(params.symbol)
        if declaration is not None:
            sections.append(
                "Installed native declaration:\n" + json.dumps(declaration, indent=2)
            )
    source_unavailable = None
    try:
        sections.append("Installed Python source:\n" + inspect.getsource(definition))
    except (OSError, TypeError) as error:
        source_unavailable = str(error)
    content = "\n\n".join(sections).encode("utf-8")
    if params.offset > len(content):
        raise ValueError("Definition offset exceeds the available UTF-8 content.")
    if params.offset < len(content) and content[params.offset] & 0xC0 == 0x80:
        raise ValueError("Definition offset must start at a UTF-8 character boundary.")
    decoder = codecs.getincrementaldecoder("utf-8")()
    page = decoder.decode(
        content[params.offset : params.offset + params.max_bytes], final=False
    )
    next_offset = params.offset + len(page.encode("utf-8"))
    return {
        **result,
        "status": "definition",
        "kind": _kind(value),
        "signature": signature,
        "signature_unavailable": signature_unavailable,
        "source_unavailable": source_unavailable,
        "content": page,
        "content_bytes": len(content),
        "content_fingerprint": hashlib.sha256(content).hexdigest(),
        "offset": params.offset,
        "next_offset": next_offset if next_offset < len(content) else None,
    }
