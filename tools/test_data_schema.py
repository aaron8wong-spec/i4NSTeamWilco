"""Checks every row in data/*.jsonl: expected validates against the Command schema, ids and texts are not reused
for different rows. Run: python3 -m pytest -q tools"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "language"))
from make_grammar import SCHEMA_PATH, command_validator  # noqa: E402

VALIDATOR = command_validator(json.loads(SCHEMA_PATH.read_text()))
FILES = sorted((ROOT / "data").glob("*.jsonl"))


def rows_of(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


ALL = [(p.name, r) for p in FILES for r in rows_of(p)]


@pytest.mark.parametrize("name,row", ALL, ids=[f"{n}:{r['id']}" for n, r in ALL])
def test_expected_validates(name, row):
    VALIDATOR.validate(row["expected"])


def test_same_id_always_means_same_row():
    seen = {}
    for _, r in ALL:
        assert seen.setdefault(r["id"], r) == r, r["id"]


def test_texts_are_not_shared_between_different_ids():
    seen = {}
    for _, r in ALL:
        assert seen.setdefault(r["text"], r["id"]) == r["id"], r["text"]
