"""A small JSON Schema check for values the UI sends, without a runtime dependency.

It covers the keywords the contracts use for settings (type, enum, const, pattern, properties, required,
additionalProperties, items, minItems, maxItems). The full jsonschema library checks the contracts in the tests.
"""
from __future__ import annotations

import json
import re
from functools import cache

from . import settings

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}


@cache
def contract(name: str) -> dict:
    return json.loads(settings.resource_path("contracts", f"{name}.schema.json").read_text(encoding="utf-8"))


def is_valid(value, schema: dict) -> bool:
    kind = schema.get("type")
    if kind:
        if isinstance(value, bool) and kind in ("integer", "number"):
            return False
        if not isinstance(value, TYPES[kind]):
            return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if "const" in schema and value != schema["const"]:
        return False
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            return False
        if schema.get("additionalProperties") is False and any(key not in props for key in value):
            return False
        if not all(is_valid(v, props[k]) for k, v in value.items() if k in props):
            return False
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            return False
        if "items" in schema and not all(is_valid(item, schema["items"]) for item in value):
            return False
    return True


def setting_schema(name: str) -> dict | None:
    """The schema for one setting that `set` may change, or None. Lists have their own actions (revoke,
    source:<id>), so only single values and quiet hours can be set directly."""
    schema = contract("settings")["properties"].get(name)
    return schema if schema and schema.get("type") != "array" else None
