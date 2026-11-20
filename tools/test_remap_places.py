import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from remap_places import main, remap_row, remap_text  # noqa: E402

ROWS = [
    {"id": "X1", "tag": "goto-place", "text": "Go to the Old Barn at 40 meters.",
     "expected": {"action": "goto", "params": {"place": "old_barn", "alt_m": 40}}},
    {"id": "X2", "tag": "search-place", "text": "Search old_barn and the water tower for trucks.",
     "expected": {"action": "search_area", "params": {"place": "old_barn", "radius_m": 50, "alt_m": 30, "target": "vehicle"}}},
    {"id": "X3", "tag": "hold", "text": "Hold position.", "expected": {"action": "hold", "params": {}}},
    {"id": "X4", "tag": "goto-place", "text": "Fly to the old barnyard.",
     "expected": {"action": "goto", "params": {"place": "barnyard", "alt_m": 40}}},
]
MAP = {"old_barn": "buildings", "water_tower": "bridge"}


def write(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    return p


def test_text_matches_case_and_spaces_and_underscores():
    assert remap_text("Go to the Old Barn.", MAP) == "Go to the buildings."
    assert remap_text("old_barn and WATER TOWER", MAP) == "buildings and bridge"


def test_no_partial_word_match():
    assert remap_text("Fly to the old barnyard.", MAP) == "Fly to the old barnyard."


def test_row_text_and_place_both_change():
    new, changed = remap_row(ROWS[0], MAP)
    assert changed and new["text"] == "Go to the buildings at 40 meters."
    assert new["expected"]["params"]["place"] == "buildings"
    assert ROWS[0]["expected"]["params"]["place"] == "old_barn"  # input not mutated


def test_unrelated_rows_unchanged():
    assert remap_row(ROWS[2], MAP) == (ROWS[2], False)
    assert remap_row(ROWS[3], MAP)[1] is False


def test_swap_does_not_chain():
    assert remap_text("old barn then water tower", {"old_barn": "water_tower", "water_tower": "old_barn"}) == \
        "water tower then old barn"


def test_dry_run_writes_nothing(tmp_path):
    p = write(tmp_path)
    before = p.read_text()
    assert main([str(p), "old_barn=buildings", "--dry-run"]) == 2
    assert p.read_text() == before


def test_real_run_rewrites_file(tmp_path):
    p = write(tmp_path)
    main([str(p), "old_barn=buildings"])
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    assert rows[0]["expected"]["params"]["place"] == "buildings"
    assert rows[1]["text"] == "Search buildings and the water tower for trucks."
    assert rows[2] == ROWS[2]
