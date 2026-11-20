import json
from pathlib import Path

import pytest

from integration.mission_state import MissionState
from reporting import scorer, templates

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "integration" / "config.json").read_text())
RULES = scorer.load_rules(ROOT / "reporting" / "rules.json")
LAT, LON = 37.4135, -121.9960


def ev(id="E03", type="vehicle", conf=0.82, people=0, lat=LAT, lon=LON, **kw):
    return {"id": id, "type": type, "confidence": conf, "lat": lat, "lon": lon,
            "time_s": 10.0, "people_visible": people, **kw}


def state(target="vehicle", area=True):
    s = MissionState(CFG)
    if target:
        s.set_search(target, LAT, LON, 150, 50)
    return s


def run(e, s=None, **kw):
    s = s or state()
    m = scorer.score(e, s, RULES, **kw)
    assert not list(scorer.MESSAGE_VALIDATOR.iter_errors(m))
    return m, s


def test_interrupt():
    m, _ = run(ev(people=2, subtype="truck"))
    assert (m["tier"], m["rule_id"], m["expects_reply"]) == ("interrupt", "R01", False)
    assert "rule R01" in m["text"] and "Person inside a vehicle" in m["text"]


def test_summarize():
    m, _ = run(ev(subtype="truck", conf=0.85))
    assert (m["tier"], m["rule_id"]) == ("summarize", "R03")


def test_log_wildlife():
    m, _ = run(ev(type="wildlife", subtype="deer", conf=0.9))
    assert (m["tier"], m["rule_id"]) == ("log", "R15")


def test_ask_low_confidence_sets_pending():
    m, s = run(ev(people=1, conf=0.45))
    assert m["tier"] == "ask" and m["expects_reply"] and m["text"].endswith("?")
    p = s.as_dict()["pending_question"]
    assert p["event_id"] == "E03" and p["text"] == m["text"]
    assert p["proposed_command"] == {"action": "loiter", "params": {"event_id": "E03", "radius_m": 30, "duration_s": 120}}


def test_ask_rule_action_unknown_object():
    m, s = run(ev(id="E04", type="unknown", conf=0.40))
    assert (m["tier"], m["rule_id"]) == ("ask", "R12")
    assert s.as_dict()["pending_question"]["event_id"] == "E04"


def test_duplicate_by_id():
    s = state(); s.mark_reported("E03")
    m, s = run(ev(people=2), s)
    assert m["tier"] == "log" and "already reported" in m["text"]
    assert s.as_dict()["pending_question"] is None


def test_duplicate_by_position():
    s = state()
    near = {"type": "vehicle", "lat": LAT + 0.0001, "lon": LON}  # about 11 m away
    m, s = run(ev(id="E09", people=2), s, reported_events=[near])
    assert m["tier"] == "log"
    assert "E09" in s.as_dict()["already_reported"]
    far = {"type": "vehicle", "lat": LAT + 0.001, "lon": LON}  # about 111 m away
    m2, _ = run(ev(id="E10", people=2), state(), reported_events=[far])
    assert m2["tier"] == "interrupt"


def test_tie_break_three_people_picks_r04():
    m, _ = run(ev(people=3, conf=0.9))
    assert (m["tier"], m["rule_id"]) == ("interrupt", "R04")


def test_off_target_not_safety_is_logged():
    m, _ = run(ev(type="person", conf=0.95, people=1), state("vehicle"))
    assert (m["tier"], m["rule_id"]) == ("log", "R05")


def test_off_target_safety_relevant_not_logged():
    m, _ = run(ev(type="person", conf=0.95, people=4), state("vehicle"))
    assert (m["tier"], m["rule_id"]) == ("interrupt", "R07")


def test_target_any_and_none_match_everything():
    assert run(ev(type="person", conf=0.9), state("any"))[0]["tier"] == "interrupt"
    assert run(ev(type="person", conf=0.9), state(None))[0]["tier"] == "interrupt"


def test_non_high_below_min_confidence_logs():
    rules = [{"id": "R90", "event_type": "vehicle", "condition": {}, "priority": "medium", "min_confidence": 0.5,
              "action": "summarize", "reason": "test", "safety_relevant": False}]
    m = scorer.score(ev(conf=0.3), state(), rules)
    assert (m["tier"], m["rule_id"]) == ("log", "R90")


def test_no_matching_rule_logs():
    m = scorer.score(ev(), state(), [])
    assert (m["tier"], m["rule_id"]) == ("log", "R00")


def test_in_search_area_condition():
    rule = {"id": "R91", "event_type": "any", "condition": {"in_search_area": True}, "priority": "medium",
            "min_confidence": 0.0, "action": "summarize", "reason": "in area", "safety_relevant": True}
    assert scorer.score(ev(), state(), [rule])["tier"] == "summarize"
    far = ev(id="E05", lat=LAT + 0.01)
    assert scorer.score(far, state(), [rule])["rule_id"] == "R00"


def test_marks_reported_and_text_length():
    m, s = run(ev(people=2, subtype="truck"))
    assert "E03" in s.as_dict()["already_reported"]
    assert len(m["text"]) <= 240 and len(templates.render_log(ev(), "x" * 400)) <= 240


def test_load_rules_rejects_bad_rule(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"rules": [{"id": "R01"}]}))
    with pytest.raises(ValueError):
        scorer.load_rules(p)


def test_demo_four_events():
    s = state()
    got = [run(e, s)[0]["tier"] for e in [
        ev(id="E01", type="wildlife", subtype="deer", conf=0.9, lat=LAT + 0.0003),
        ev(id="E02", subtype="truck", conf=0.85, lat=LAT + 0.0006),
        ev(id="E03", people=2, subtype="truck", conf=0.82, lat=LAT + 0.0009),
        ev(id="E04", type="unknown", conf=0.4, lat=LAT + 0.0012)]]
    assert got == ["log", "summarize", "interrupt", "ask"]
