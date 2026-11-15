"""Checks on data/train.jsonl and data/test.jsonl (no model needed). Run: cd language && python3 -m pytest -q"""
import json
from pathlib import Path

import pytest

from guard import check_grounding, normalize_units
from make_grammar import SCHEMA_PATH, command_validator

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = command_validator(json.loads(SCHEMA_PATH.read_text()))


def read(name):
    return [json.loads(l) for l in (ROOT / "data" / name).read_text().splitlines()]


TRAIN, TEST, SEEDS = read("train.jsonl"), read("test.jsonl"), read("seeds.jsonl")
ROWS = TRAIN + TEST


def test_ids_and_texts_are_unique_across_train_test_and_seeds():
    allrows = ROWS + SEEDS
    assert len({r["id"] for r in allrows}) == len(allrows)
    assert len({r["text"] for r in allrows}) == len(allrows)


def test_test_split_is_about_a_fifth_and_has_every_action():
    assert 0.12 <= len(TEST) / len(ROWS) <= 0.28
    assert {r["expected"]["action"] for r in TEST} >= {"goto", "search_area", "loiter", "move", "hold",
                                                        "return_home", "report_status", "clarify"}


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_expected_is_schema_valid(row):
    VALIDATOR.validate(row["expected"])


@pytest.mark.parametrize("row", [r for r in ROWS if r["expected"]["action"] != "clarify"], ids=lambda r: r["id"])
def test_expected_values_are_grounded_in_the_text(row):
    """Catches a wrong unit conversion or a typo in the answer key."""
    out, why = check_grounding(row["expected"], normalize_units(row["text"]))
    assert out == row["expected"], why
