"""Validate reporting/rules.json against the Rule definition in integration/schemas.json."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = json.loads((ROOT / "integration" / "schemas.json").read_text())
RULES = json.loads((ROOT / "reporting" / "rules.json").read_text())["rules"]

# Rule refers to other defs with "#/$defs/...", so wrap it in a schema that carries all defs.
VALIDATOR = Draft202012Validator(
    {"$schema": SCHEMAS["$schema"], "$defs": SCHEMAS["$defs"], "$ref": "#/$defs/Rule"}
)


def test_fifteen_rules():
    assert len(RULES) == 15


@pytest.mark.parametrize("rule", RULES, ids=[r.get("id", "?") for r in RULES])
def test_rule_matches_schema(rule):
    errors = [e.message for e in VALIDATOR.iter_errors(rule)]
    assert not errors, errors


def test_ids_unique():
    ids = [r["id"] for r in RULES]
    assert len(ids) == len(set(ids))
