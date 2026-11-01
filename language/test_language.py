import json
import re
import shutil
import subprocess
from pathlib import Path

import jsonschema
import pytest

from schema_to_gbnf import schema_to_gbnf

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "language" / "schemas.json").read_text())
SEEDS = [json.loads(line) for line in (ROOT / "data" / "seeds.jsonl").read_text().splitlines()]
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


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
    assert actions == {"goto", "search_area", "loiter", "hold", "return_home", "clarify"}


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


def test_root_lists_all_six_actions():
    root = next(l for l in GBNF.splitlines() if l.startswith("root ::="))
    assert root.count("cmd-") == 6


def test_unsupported_schema_raises():
    bad = {"oneOf": [{"type": "object", "properties": {"action": {"const": "x"}},
                      "required": [], "additionalProperties": False}]}
    with pytest.raises(NotImplementedError):
        schema_to_gbnf(bad)


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
