"""Tests for the follow-up set (task 7.4, M8). No model needed. Run: python3 -m pytest -q language"""
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

import run_llm
from make_grammar import SCHEMA_PATH, command_validator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
CMD = command_validator(SCHEMA)
MS = jsonschema.Draft202012Validator({"$ref": "#/$defs/MissionState", "$defs": SCHEMA["$defs"]})


def read(name):
    return [json.loads(l) for l in (DATA / name).read_text().splitlines() if l.strip()]


ALL, TRAIN, TEST = read("followups.jsonl"), read("followups_train.jsonl"), read("followups_test.jsonl")


def test_ids_unique_and_formatted():
    ids = [r["id"] for r in ALL]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("F") and i[1:].isdigit() and len(i) == 4 for i in ids)


@pytest.mark.parametrize("row", ALL, ids=lambda r: r["id"])
def test_row_valid(row):
    assert set(row) == {"id", "tag", "text", "mission_state", "expected"}
    assert not list(CMD.iter_errors(row["expected"]))
    assert not list(MS.iter_errors(row["mission_state"]))


def test_splits_partition_and_never_overlap():
    tr, te = {r["id"] for r in TRAIN}, {r["id"] for r in TEST}
    assert not tr & te
    assert tr | te == {r["id"] for r in ALL}
    assert {json.dumps(r, sort_keys=True) for r in TRAIN + TEST} == {json.dumps(r, sort_keys=True) for r in ALL}
    assert 0.15 <= len(TEST) / len(ALL) <= 0.3


def test_yes_rows_give_exactly_the_proposed_command():
    for r in ALL:
        if r["tag"] in ("yes_loiter", "yes_noisy", "loiter_there"):
            assert r["expected"] == r["mission_state"]["pending_question"]["proposed_command"]


def test_no_pending_rows_have_no_pending_question():
    for r in ALL:
        if r["tag"] == "no_pending":
            assert r["mission_state"]["pending_question"] is None
            assert r["expected"]["params"]["reason"] == "ambiguous_reference"


def test_prompt_without_state_is_byte_identical_to_before():
    # sha256 of the no-state prompt after the 2026-11-22 few-shot place examples (was the pre-7.4 hash). Update on any deliberate SYSTEM change.
    want = {"Hold position.": "26e01f3f4b049ef11919ce8bc44c69e733bda5912be3645576a6bb7e6bbc641b", "Yes.": "1955b02cfe9475203f97f17b61f219ad61e71bb4f16a8c3a895a580ae95aa633"}
    for t, h in want.items():
        assert run_llm.build_prompt(t) == run_llm.TEMPLATE.format(system=run_llm.SYSTEM, text=t)
        assert run_llm.build_prompt(t, None) == run_llm.build_prompt(t)
        assert hashlib.sha256(run_llm.build_prompt(t).encode()).hexdigest() == h


def test_prompt_with_state_has_context():
    r = next(x for x in ALL if x["tag"] == "yes_loiter")
    p = run_llm.build_prompt(r["text"], r["mission_state"])
    pq = r["mission_state"]["pending_question"]
    assert pq["text"] in p and json.dumps(pq["proposed_command"], separators=(",", ":")) in p
    assert "Target: vehicle" in p and "Already reported: E01" in p and f"Request: {r['text']}" in p
    none = run_llm.build_prompt("Yes.", next(x for x in ALL if x["tag"] == "no_pending")["mission_state"])
    assert "Pending question: none" in none
