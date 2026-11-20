import json
from pathlib import Path

import jsonschema
import pytest

from mission_state import MissionState

_defs = json.loads((Path(__file__).parent / "schemas.json").read_text())["$defs"]
_SCHEMA = {"$ref": "#/$defs/MissionState", "$defs": _defs}
CFG = {"geofence_radius_m": 1500, "max_alt_m": 120}
LOITER = {"action": "loiter", "params": {"event_id": "E03", "radius_m": 30, "duration_s": 120}}


def check(ms):
    d = ms.as_dict()
    jsonschema.validate(d, _SCHEMA)
    return d


def test_fresh():
    d = check(MissionState(CFG))
    assert d["target"] is None and d["area"] is None and d["home"] is None
    assert d["already_reported"] == [] and d["pending_question"] is None
    assert d["mode"] == "ai"
    assert d["geofence"]["radius_m"] == 1500 and d["geofence"]["max_alt_m"] == 120


def test_set_home_centers_geofence():
    ms = MissionState(CFG)
    ms.set_home(37.41, -121.99)
    d = check(ms)
    assert d["home"] == {"lat": 37.41, "lon": -121.99}
    assert (d["geofence"]["lat"], d["geofence"]["lon"]) == (37.41, -121.99)


def test_set_search():
    ms = MissionState(CFG)
    ms.set_search("vehicle", 37.4, -121.9, 150, 50)
    d = check(ms)
    assert d["target"] == "vehicle"
    assert d["area"] == {"lat": 37.4, "lon": -121.9, "radius_m": 150, "alt_m": 50}


def test_mark_reported_no_duplicates():
    ms = MissionState(CFG)
    ms.mark_reported("E01")
    ms.mark_reported("E01")
    ms.mark_reported("E02")
    assert check(ms)["already_reported"] == ["E01", "E02"]


def test_pending_set_and_clear():
    ms = MissionState(CFG)
    ms.set_pending("Loiter there?", "E03", LOITER)
    d = check(ms)
    assert d["pending_question"] == {"text": "Loiter there?", "event_id": "E03", "proposed_command": LOITER}
    ms.clear_pending()
    assert check(ms)["pending_question"] is None


def test_pending_open_ended():
    ms = MissionState(CFG)
    ms.set_pending("Continue?", None, None)
    assert check(ms)["pending_question"]["proposed_command"] is None


def test_set_mode():
    ms = MissionState(CFG)
    ms.set_mode("manual")
    assert check(ms)["mode"] == "manual"
    ms.set_mode("ai")
    assert check(ms)["mode"] == "ai"


def test_set_mode_rejects_other():
    ms = MissionState(CFG)
    with pytest.raises(ValueError):
        ms.set_mode("auto")
    assert ms.as_dict()["mode"] == "ai"


def test_as_dict_is_a_copy():
    ms = MissionState(CFG)
    ms.set_home(37.4, -121.9)
    ms.set_search("vehicle", 37.4, -121.9, 150, 50)
    ms.mark_reported("E01")
    ms.set_pending("Loiter?", "E03", LOITER)
    d = ms.as_dict()
    d["home"]["lat"] = 0
    d["area"]["radius_m"] = 1
    d["already_reported"].append("E99")
    d["pending_question"]["proposed_command"]["params"]["radius_m"] = 999
    d["geofence"]["radius_m"] = 1
    d["mode"] = "manual"
    d2 = check(ms)
    assert d2["home"]["lat"] == 37.4 and d2["area"]["radius_m"] == 150
    assert d2["already_reported"] == ["E01"]
    assert d2["pending_question"]["proposed_command"] == LOITER
    assert d2["geofence"]["radius_m"] == 1500 and d2["mode"] == "ai"


def test_input_command_is_copied():
    ms = MissionState(CFG)
    cmd = json.loads(json.dumps(LOITER))
    ms.set_pending("Loiter?", "E03", cmd)
    cmd["params"]["radius_m"] = 999
    assert ms.as_dict()["pending_question"]["proposed_command"] == LOITER
