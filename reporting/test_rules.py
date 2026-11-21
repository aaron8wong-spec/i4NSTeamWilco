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


def test_ten_rules():
    assert len(RULES) == 10


@pytest.mark.parametrize("rule", RULES, ids=[r.get("id", "?") for r in RULES])
def test_rule_matches_schema(rule):
    errors = [e.message for e in VALIDATOR.iter_errors(rule)]
    assert not errors, errors


def test_ids_unique():
    ids = [r["id"] for r in RULES]
    assert len(ids) == len(set(ids))


def test_no_two_rules_are_identical_in_scope():
    """Same event_type, priority and condition would be an unbreakable tie."""
    keys = [(r["event_type"], r["priority"], json.dumps(r["condition"], sort_keys=True)) for r in RULES]
    assert len(keys) == len(set(keys))


def test_no_dead_low_priority_catch_alls():
    """A low rule with the same event_type as a high rule can never win (highest priority is taken)."""
    high = {r["event_type"] for r in RULES if r["priority"] == "high"}
    for r in RULES:
        if r["priority"] == "low":
            assert r["event_type"] not in high, r["id"]
