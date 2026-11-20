"""Pipeline and main-loop tests on MockFlight and FakeEvents. No model server: a fake llm callable is used."""
import asyncio
import json
from pathlib import Path

from integration import main as demo
from integration import pipeline
from integration.mission_state import MissionState
from integration.mock_flight import MockFlight

CFG = pipeline.load_config()
SEARCH_TEXT = "Search the north field for vehicles, radius 150 meters at 50 meters"
SEARCH = {"action": "search_area", "params": {"place": "north_field", "radius_m": 150, "alt_m": 50, "target": "vehicle"}}


def fake(cmd):
    return lambda text: json.loads(json.dumps(cmd))


def setup():
    mf = MockFlight(time_scale=0)
    asyncio.run(mf.connect())
    st = MissionState(CFG)
    st.set_home(mf.home["lat"], mf.home["lon"])
    return mf, st


def handle(text, cmd, st, mf, tmp_path, **kw):
    log = pipeline.RunLog(tmp_path / "log.jsonl")
    return asyncio.run(pipeline.handle_text(text, st, mf, "http://unused", llm=fake(cmd), log=log, **kw))


def test_unknown_place_refused_never_executes(tmp_path):
    mf, st = setup()
    cmd = {"action": "goto", "params": {"place": "narnia", "alt_m": 40}}
    r = handle("Fly to narnia at 40 meters", cmd, st, mf, tmp_path)
    assert r["gate"][0] is False and "narnia" in r["gate"][1]
    assert mf.executed == [] and r["result"] is None


def test_known_place_resolved_to_latlon_for_backend(tmp_path):
    mf, st = setup()
    cmd = {"action": "goto", "params": {"place": "north_field", "alt_m": 40}}
    r = handle("Fly to the north field at 40 meters", cmd, st, mf, tmp_path)
    assert r["gate"][0] and r["result"]["ok"]
    sent = mf.executed[0]["params"]
    assert "place" not in sent and set(sent) == {"lat", "lon", "alt_m"}


def test_clarify_never_executes(tmp_path):
    mf, st = setup()
    cmd = {"action": "clarify", "params": {"reason": "missing_altitude", "question": "How high?"}}
    r = handle("Fly somewhere", cmd, st, mf, tmp_path)
    assert r["gate"][0] and mf.executed == [] and r["result"] is None


def test_gate_refusal_altitude_never_executes(tmp_path):
    mf, st = setup()
    cmd = {"action": "goto", "params": {"place": "north_field", "alt_m": 800}}
    r = handle("Fly to the north field at 800 meters", cmd, st, mf, tmp_path)
    assert not r["gate"][0] and "800" in r["gate"][1] and mf.executed == []


def test_manual_mode_ignores_ai_commands(tmp_path):
    mf, st = setup()
    st.set_mode("manual")
    r = handle("Hold position", {"action": "hold", "params": {}}, st, mf, tmp_path)
    assert not r["gate"][0] and "manual" in r["gate"][1] and mf.executed == []


def test_guard_turns_invented_values_into_clarify(tmp_path):
    mf, st = setup()
    r = handle("Search the north field for vehicles", SEARCH, st, mf, tmp_path)
    assert r["command"]["action"] == "clarify" and mf.executed == []


def test_dry_run_does_not_fly_or_set_search(tmp_path):
    mf, st = setup()
    r = handle(SEARCH_TEXT, SEARCH, st, mf, tmp_path, dry_run=True)
    assert r["gate"][0] and mf.executed == [] and st.as_dict()["target"] is None


def test_search_sets_target_and_area(tmp_path):
    mf, st = setup()
    r = handle(SEARCH_TEXT, SEARCH, st, mf, tmp_path)
    assert r["gate"][0] and r["result"]["ok"]
    d = st.as_dict()
    assert d["target"] == "vehicle" and d["area"]["radius_m"] == 150


def test_pending_yes_runs_proposed_loiter_and_clears(tmp_path):
    mf, st = setup()
    prop = {"action": "loiter", "params": {"event_id": "E04", "radius_m": 30, "duration_s": 5}}
    st.set_pending("Loiter?", "E04", prop)
    pos = {"E04": (mf.home["lat"] + 0.001, mf.home["lon"])}
    r = handle("yes, loiter", {"action": "hold", "params": {}}, st, mf, tmp_path, known_event_positions=pos)
    assert r["command"]["action"] == "loiter" and r["gate"][0]
    assert set(mf.executed[0]["params"]) == {"radius_m", "duration_s", "lat", "lon"}
    assert st.as_dict()["pending_question"] is None


def test_pending_no_clears_without_flying(tmp_path):
    mf, st = setup()
    st.set_pending("Loiter?", "E04", {"action": "loiter", "params": {"event_id": "E04", "radius_m": 30, "duration_s": 5}})
    r = handle("no, keep searching", SEARCH, st, mf, tmp_path)
    assert r["command"] is None and mf.executed == [] and st.as_dict()["pending_question"] is None


def test_loiter_unknown_event_refused(tmp_path):
    mf, st = setup()
    cmd = {"action": "loiter", "params": {"event_id": "E03", "radius_m": 30, "duration_s": 10}}
    r = handle("Loiter at E03 for 10 seconds, radius 30 meters", cmd, st, mf, tmp_path, known_event_positions={})
    assert not r["gate"][0] and mf.executed == []


def test_run_log_has_stages(tmp_path):
    mf, st = setup()
    handle(SEARCH_TEXT, SEARCH, st, mf, tmp_path)
    rows = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text().splitlines()]
    stages = [r["stage"] for r in rows]
    for s in ("input", "normalize", "llm", "guard", "gate", "execute", "result"):
        assert s in stages
    assert all({"ts", "stage", "data"} <= set(r) for r in rows)


# ---- main loop ----
DEMO = [SEARCH_TEXT, "yes, loiter", "@wait", "report status"]


def llm_for_demo(text):
    t = text.lower()
    if "report" in t:
        return {"action": "report_status", "params": {}}
    return json.loads(json.dumps(SEARCH))


def run_demo(tmp_path, name, lines=DEMO, llm=llm_for_demo):
    log = pipeline.RunLog(tmp_path / name)
    return asyncio.run(demo.run(lines, llm=llm, time_scale=0, log=log, out=lambda s: None)), tmp_path / name


def test_demo_end_to_end(tmp_path):
    out, logpath = run_demo(tmp_path, "a.jsonl")
    text = "\n".join(out)
    assert out[0].startswith("> Search the north field")
    assert "[CMD] search_area" in text
    ask = next(i for i, l in enumerate(out) if l.startswith("[ASK]"))
    alert = next(i for i, l in enumerate(out) if l.startswith("[ALERT]"))
    assert alert < ask  # E03 (truck with people) interrupts before E04 asks
    assert "Unknown object" in out[ask] and out[ask].rstrip().endswith("?")
    assert "[CMD] loiter" in text
    assert "superseded" in text  # the loiter redirected the search
    assert any(l.startswith("[STATUS]") and "truck" in l.lower() for l in out)  # E02 summarized
    assert "Wildlife" not in text  # deer (E01) is only logged
    stages = [json.loads(l)["stage"] for l in logpath.read_text().splitlines()]
    assert stages.count("event") == 4 and stages.count("score") == 4


def test_demo_runs_twice_identically(tmp_path):
    a, _ = run_demo(tmp_path, "a.jsonl")
    b, _ = run_demo(tmp_path, "b.jsonl")
    assert a == b and len(a) > 5


def test_demo_unknown_place_never_flies(tmp_path):
    bad = lambda t: {"action": "goto", "params": {"place": "narnia", "alt_m": 40}}
    mf = MockFlight(time_scale=0)
    log = pipeline.RunLog(tmp_path / "x.jsonl")
    out = asyncio.run(demo.run(["Fly to narnia at 40 meters"], llm=bad, backend=mf, log=log, out=lambda s: None))
    assert any(l.startswith("[REFUSED]") for l in out) and mf.executed == []


def test_demo_manual_mode_and_clarify_never_fly(tmp_path):
    mf = MockFlight(time_scale=0)
    log = pipeline.RunLog(tmp_path / "x.jsonl")
    out = asyncio.run(demo.run(["/manual", SEARCH_TEXT, "/ai", "Fly somewhere"],
                               llm=lambda t: SEARCH if "Search" in t else
                               {"action": "clarify", "params": {"reason": "missing_location", "question": "Where?"}},
                               backend=mf, log=log, out=lambda s: None))
    assert any("manual" in l and l.startswith("[REFUSED]") for l in out)
    assert any(l.startswith("[CLARIFY]") for l in out)
    assert mf.executed == []
