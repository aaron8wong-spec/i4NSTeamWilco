"""Tests for language/guard.py (no model needed). Run: cd language && python3 -m pytest -q"""
import json
from pathlib import Path

import pytest

from guard import check_grounding, normalize_units

ROOT = Path(__file__).resolve().parent.parent
SEEDS = [json.loads(line) for line in (ROOT / "data" / "seeds.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("text,expected", [
    ("Go 1500 feet at 135 degrees at 100 feet altitude.", "Go 457 meters at 135 degrees at 30 meters altitude."),
    ("Fly 2 kilometers at 90 degrees at 80 meters.", "Fly 2000 meters at 90 degrees at 80 meters."),
    ("Loiter for 2 minutes, radius 30 meters.", "Loiter for 120 seconds, radius 30 meters."),
    ("Loiter for ten minutes.", "Loiter for 600 seconds."),
    ("Fly forty meters up.", "Fly 40 meters up."),
    ("Go two hundred fifty meters.", "Go 250 meters."),
    ("Go a hundred and twenty feet up.", "Go 37 meters up."),
    ("Stay for a minute.", "Stay for 60 seconds."),
    ("Climb twenty-five meters.", "Climb 25 meters."),
    ("Fly to 37.4123, -121.9925 at 40 meters.", "Fly to 37.4123, -121.9925 at 40 meters."),  # coordinates untouched
    ("Check the one near the road.", "Check the one near the road."),                        # no unit, left alone
])
def test_normalize_units(text, expected):
    assert normalize_units(text) == expected


def test_invented_altitude_becomes_clarify():
    cmd = {"action": "goto", "params": {"lat": 37.4123, "lon": -121.9925, "alt_m": 1}}
    out, why = check_grounding(cmd, "Fly to 37.4123, -121.9925.")
    assert out == {"action": "clarify", "params": {"reason": "missing_altitude", "question": "How high should I fly?"}}
    assert "alt_m" in why


def test_invented_coordinates_become_clarify():
    cmd = {"action": "search_area", "params": {"lat": 0, "lon": 0, "radius_m": 100, "alt_m": 5, "target": "structure"}}
    out, _ = check_grounding(cmd, "Search for something suspicious.")
    assert out["action"] == "clarify" and out["params"]["reason"] == "missing_location"


def test_move_without_direction_or_altitude():
    no_dir = {"action": "move", "params": {"distance_m": 500, "bearing_deg": 0, "alt_m": 40}}
    assert check_grounding(no_dir, "Fly 500 meters at 40 meters altitude.")[0]["params"]["reason"] == "missing_location"
    no_alt = {"action": "move", "params": {"distance_m": 500, "bearing_deg": 45, "alt_m": 1}}
    assert check_grounding(no_alt, "Move 500 meters at 45 degrees.")[0]["params"]["reason"] == "missing_altitude"


def test_compass_word_is_not_a_bearing():
    cmd = {"action": "move", "params": {"distance_m": 500, "bearing_deg": 45, "alt_m": 40}}
    out, why = check_grounding(cmd, "Move 500 meters northeast at 40 meters.")
    assert out["action"] == "clarify" and "bearing_deg" in why


def test_bearing_zero_is_grounded_when_said():
    cmd = {"action": "move", "params": {"distance_m": 800, "bearing_deg": 0, "alt_m": 45}}
    assert check_grounding(cmd, "Head 800 m at 0 degrees, 45 meters high.") == (cmd, None)


def test_event_id_must_be_said_or_in_context():
    cmd = {"action": "loiter", "params": {"event_id": "E03", "radius_m": 10, "duration_s": 60}}
    assert check_grounding(cmd, "Loiter for 60 seconds, radius 10 meters.")[0]["action"] == "clarify"
    assert check_grounding(cmd, "Yes, loiter 60 seconds, radius 10 meters.", context_event_ids={"E03"}) == (cmd, None)
    assert check_grounding(cmd, "Loiter at E03, radius 10 meters, 60 seconds.") == (cmd, None)


def test_clarify_and_no_param_commands_pass_through():
    for cmd in ({"action": "hold", "params": {}}, {"action": "return_home", "params": {}},
                {"action": "clarify", "params": {"reason": "unsafe_request", "question": "Where?"}}):
        assert check_grounding(cmd, "anything") == (cmd, None)


@pytest.mark.parametrize("seed", [s for s in SEEDS if s["expected"]["action"] != "clarify"], ids=lambda s: s["id"])
def test_guard_never_blocks_a_correct_seed_command(seed):
    """The seed's own correct command must pass its own normalized text. A false clarify would be a regression."""
    out, why = check_grounding(seed["expected"], normalize_units(seed["text"]))
    assert out == seed["expected"], why
