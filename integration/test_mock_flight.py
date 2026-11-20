import asyncio
import json
import pathlib

import jsonschema

from integration import geo
from integration.fake_events import FakeEvents
from integration.mock_flight import MockFlight, SPEED_MPS

SCHEMAS = json.loads((pathlib.Path(__file__).parent / "schemas.json").read_text())


def run(coro):
    return asyncio.run(coro)


def make():
    mf = MockFlight(time_scale=0)
    run(mf.connect())
    mf.positions = []
    mf.subscribe_positions(mf.positions.append)
    return mf


def test_connect_returns_home():
    assert set(run(MockFlight().connect())) == {"lat", "lon", "alt_amsl_m"}


def test_goto_speed_and_rate():
    mf = make()
    lat, lon = geo.local_to_latlon(100, 0, mf.home["lat"], mf.home["lon"])
    res = run(mf.execute({"action": "goto", "params": {"lat": lat, "lon": lon, "alt_m": 0}}))
    assert res["ok"]
    assert abs(mf.north_m - 100) < 1e-6
    assert abs(mf.time_s - 100 / SPEED_MPS) < 0.5  # 10 m/s
    ts = [p["time_s"] for p in mf.positions]
    assert all(abs((b - a) - 0.2) < 0.011 for a, b in zip(ts, ts[1:]))  # 5 Hz


def test_climb_descend_hold_return_home():
    mf = make()
    run(mf.execute({"action": "climb", "params": {"amount_m": 40}}))
    assert abs(mf.alt_m - 40) < 1e-6
    run(mf.execute({"action": "descend", "params": {"amount_m": 15}}))
    assert abs(mf.alt_m - 25) < 1e-6
    run(mf.execute({"action": "move", "params": {"distance_m": 50, "bearing_deg": 90, "alt_m": 25}}))
    assert abs(mf.east_m - 50) < 1.0
    n = len(mf.positions)
    run(mf.execute({"action": "hold", "params": {}}))
    assert len(mf.positions) == n + 1
    run(mf.execute({"action": "return_home", "params": {}}))
    assert abs(mf.north_m) < 1e-6 and abs(mf.east_m) < 1e-6 and abs(mf.alt_m) < 1e-6


def test_search_covers_area():
    mf = make()
    lat, lon = geo.local_to_latlon(200, 240, mf.home["lat"], mf.home["lon"])
    run(mf.execute({"action": "search_area", "params": {"lat": lat, "lon": lon, "radius_m": 150, "alt_m": 50, "target": "vehicle"}}))
    norths = [p["north_m"] for p in mf.positions]
    easts = [p["east_m"] for p in mf.positions]
    assert min(norths) < 200 - 149 and max(norths) > 200 + 149
    assert min(easts) < 240 - 140 and max(easts) > 240 + 140 - 1
    assert all(p["alt_m"] <= 50 + 1e-6 for p in mf.positions)


def test_loiter_stays_on_circle_for_duration():
    mf = make()
    lat, lon = geo.local_to_latlon(100, 100, mf.home["lat"], mf.home["lon"])
    run(mf.execute({"action": "goto", "params": {"lat": lat, "lon": lon, "alt_m": 40}}))
    start = mf.time_s
    run(mf.execute({"action": "loiter", "params": {"lat": lat, "lon": lon, "radius_m": 30, "duration_s": 20}}))
    circle = [p for p in mf.positions if p["time_s"] > start + 3.5]
    assert all(abs(((p["north_m"] - 100) ** 2 + (p["east_m"] - 100) ** 2) ** 0.5 - 30) < 0.5 for p in circle)
    assert mf.time_s - start >= 20


def test_missing_latlon_and_unknown_action_fail_cleanly():
    mf = make()
    assert not run(mf.execute({"action": "goto", "params": {"place": "north_field", "alt_m": 40}}))["ok"]
    assert not run(mf.execute({"action": "report_status", "params": {}}))["ok"]


def test_fake_events_fire_once_in_order_and_match_schema():
    fe = FakeEvents(37.412173, -121.998879)
    assert fe.on_time(10) == []
    got = fe.on_time(61)
    assert [e["id"] for e in got] == ["E01", "E02", "E03"]
    assert fe.on_time(61) == []
    got += fe.on_time(500)
    assert [e["id"] for e in got] == ["E01", "E02", "E03", "E04"]
    schema = {"$ref": "#/$defs/Event", "$defs": SCHEMAS["$defs"]}
    for e in got:
        jsonschema.validate(e, schema)
    assert fe.positions["E03"] == (got[2]["lat"], got[2]["lon"])
