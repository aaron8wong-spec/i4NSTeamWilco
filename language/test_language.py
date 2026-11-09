import json
import re
import shutil
import subprocess
from pathlib import Path

import jsonschema
import pytest

from schema_to_gbnf import SCHEMA_PATH, command_validator, int_range, pattern_to_gbnf, schema_to_gbnf

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads(SCHEMA_PATH.read_text())
SEEDS = [json.loads(line) for line in (ROOT / "data" / "seeds.jsonl").read_text().splitlines()]
VALIDATOR = command_validator(SCHEMA)


# --- seeds (task 5.6) ---

def test_seed_count_and_clarify_count():
    assert len(SEEDS) == 40
    assert sum(s["expected"]["action"] == "clarify" for s in SEEDS) == 8


def test_seed_ids_and_texts_are_unique():
    assert len({s["id"] for s in SEEDS}) == 40
    assert len({s["text"] for s in SEEDS}) == 40


@pytest.mark.parametrize("seed", SEEDS, ids=[s["id"] for s in SEEDS])
def test_seed_matches_schema(seed):
    VALIDATOR.validate(seed["expected"])


def test_every_action_is_covered():
    actions = {s["expected"]["action"] for s in SEEDS}
    assert actions == {"goto", "search_area", "loiter", "hold", "return_home", "report_status", "clarify"}


# --- grammar (task 5.5) ---

GBNF = schema_to_gbnf(SCHEMA)


def test_grammar_matches_committed_file():
    assert (ROOT / "language" / "command.gbnf").read_text() == GBNF


def test_every_referenced_rule_is_defined():
    defined = set(re.findall(r"^([a-z0-9-]+) ::=", GBNF, flags=re.M))
    body = re.sub(r'"(?:[^"\\]|\\.)*"', "", GBNF)  # drop string literals
    body = re.sub(r"\[(?:[^\]\\]|\\.)*\]", "", body)  # drop character classes
    body = re.sub(r"^[a-z0-9-]+ ::=", "", body, flags=re.M)
    used = set(re.findall(r"[a-z][a-z0-9-]*", body))
    assert used <= defined, used - defined


def test_root_lists_all_seven_actions():
    root = next(l for l in GBNF.splitlines() if l.startswith("root ::="))
    assert root.count("cmd-") == 7


def test_unsupported_schema_raises():
    bad = {"$defs": {"Command": {"oneOf": [{"type": "object", "properties": {"action": {"const": "x"}},
                                             "required": [], "additionalProperties": False}]}}}
    with pytest.raises(NotImplementedError):
        schema_to_gbnf(bad)


@pytest.mark.parametrize("lo,hi", [(1, 1000), (5, 5000), (1, 3600), (7, 7), (1, 9), (95, 105), (0, 12)])
def test_int_range_matches_exactly_lo_to_hi(lo, hi):
    regex = re.compile(re.sub(r'"(\d)"', r"\1", int_range(lo, hi)).replace(" ", "") + "$")
    for n in range(0, hi + 50):
        assert bool(regex.match(str(n))) == (lo <= n <= hi), n
    assert not regex.match("0" + str(lo))  # no leading zeros


def test_pattern_to_gbnf():
    assert pattern_to_gbnf("^E[0-9]{2,4}$") == '"\\"" "E" [0-9]{2,4} "\\""'
    with pytest.raises(NotImplementedError):
        pattern_to_gbnf("^a+$")


# --- the frozen docs/schemas.md examples must validate ---

EXAMPLE_DEFS = {"command": "Command", "event": "Event", "mission_state": "MissionState",
                "rule": "Rule", "message": "OperatorMessage"}
MD = (ROOT / "docs" / "schemas.md").read_text()
EXAMPLES = re.findall(r"```json (\w+)\n(.*?)\n```", MD, flags=re.S)


@pytest.mark.parametrize("kind,text", EXAMPLES)
def test_schemas_md_example_validates(kind, text):
    v = jsonschema.Draft202012Validator({"$ref": f"#/$defs/{EXAMPLE_DEFS[kind]}", "$defs": SCHEMA["$defs"]})
    v.validate(json.loads(text))


def test_schemas_md_has_all_example_kinds():
    assert {k for k, _ in EXAMPLES} == set(EXAMPLE_DEFS)


@pytest.mark.skipif(shutil.which("llama-gbnf-validator") is None,
                    reason="llama-gbnf-validator (from llama.cpp) not on PATH")
@pytest.mark.parametrize("seed", SEEDS, ids=[s["id"] for s in SEEDS])
def test_grammar_accepts_seed_output(seed, tmp_path):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(seed["expected"]))
    out = subprocess.run(
        ["llama-gbnf-validator", str(ROOT / "language" / "command.gbnf"), str(sample)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr
