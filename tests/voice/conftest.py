import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@pytest.fixture(scope="session")
def contract():
    schemas = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in CONTRACTS.glob("*.schema.json")}
    registry = Registry().with_resources((n, Resource.from_contents(d)) for n, d in schemas.items())

    def check(name: str, data) -> list[str]:
        v = Draft202012Validator(schemas[f"{name}.schema.json"], registry=registry)
        return [f"{list(e.path)}: {e.message}" for e in v.iter_errors(data)]

    return check
