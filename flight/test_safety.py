#!/usr/bin/env python3
"""Unit tests for flight/safety.py (Task 6.1 / contracts.md section 3).

Run:
    python3 -m pytest flight/test_safety.py -v
"""
import pytest
from flight.safety import (
    DroneState,
    SafetyConfig,
    SafetyGate,
    destination_point,
    haversine_distance_m,
)

BAYLANDS_HOME = (37.412173, -121.998878)


@pytest.fixture
def gate():
    return SafetyGate(SafetyConfig(
        max_alt_m=120.0,
        min_alt_m=1.0,
        geofence_radius_m=1500.0,
        min_battery_percent=25.0,
        max_loiter_radius_m=500.0,
    ))


@pytest.fixture
def default_state():
    return DroneState(
        mode="ai",
        battery_percent=100.0,
        link_ok=True,
        home_lat=BAYLANDS_HOME[0],
        home_lon=BAYLANDS_HOME[1],
        current_lat=BAYLANDS_HOME[0],
        current_lon=BAYLANDS_HOME[1],
        current_alt_m=40.0,
        places={
            "north_field": {"lat": 37.413972, "lon": -121.996161},
            "buildings": {"lat": 37.412892, "lon": -121.997066},
        },
        known_event_ids=["E01", "E02", "E03"],
    )


# --- Geometry & Distance Tests ---

def test_haversine_zero_distance():
    d = haversine_distance_m(BAYLANDS_HOME[0], BAYLANDS_HOME[1], BAYLANDS_HOME[0], BAYLANDS_HOME[1])
    assert d == pytest.approx(0.0, abs=1e-3)


def test_haversine_known_distance():
    # 200m North, 240m East is ~312.4m
    target_lat = 37.413972
    target_lon = -121.996161
    d = haversine_distance_m(BAYLANDS_HOME[0], BAYLANDS_HOME[1], target_lat, target_lon)
    assert d == pytest.approx(312.4, abs=5.0)


def test_destination_point():
    lat, lon = destination_point(BAYLANDS_HOME[0], BAYLANDS_HOME[1], 0.0, 500.0)
    d = haversine_distance_m(BAYLANDS_HOME[0], BAYLANDS_HOME[1], lat, lon)
    assert d == pytest.approx(500.0, abs=0.5)


# --- Schema Gate Tests ---

def test_reject_invalid_schema(gate, default_state):
    bad_cmd = {"action": "goto", "params": {}}
    ok, reason = gate.check_command(bad_cmd, default_state)
    assert not ok
    assert "not schema-valid" in reason


def test_reject_unknown_action(gate, default_state):
    bad_cmd = {"action": "barrel_roll", "params": {}}
    ok, reason = gate.check_command(bad_cmd, default_state)
    assert not ok
    assert "not schema-valid" in reason


# --- Mode, Lost-Link & Battery Tests ---

def test_manual_mode_refuses_ai_commands(gate, default_state):
    default_state.mode = "manual"
    cmd = {"action": "goto", "params": {"lat": 37.413972, "lon": -121.996161, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "manual mode" in reason


def test_lost_link_refuses_flight(gate, default_state):
    default_state.link_ok = False
    cmd = {"action": "goto", "params": {"lat": 37.413972, "lon": -121.996161, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "link lost" in reason


def test_lost_link_permits_hold_and_return_home(gate, default_state):
    default_state.link_ok = False
    assert gate.check_command({"action": "hold", "params": {}}, default_state) == (True, "ok")
    assert gate.check_command({"action": "return_home", "params": {}}, default_state) == (True, "ok")


def test_low_battery_refuses_flight(gate, default_state):
    default_state.battery_percent = 20.0  # below 25% floor
    cmd = {"action": "goto", "params": {"lat": 37.413972, "lon": -121.996161, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "battery low" in reason


def test_low_battery_permits_return_home(gate, default_state):
    default_state.battery_percent = 10.0
    cmd = {"action": "return_home", "params": {}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok
    assert reason == "ok"


# --- Fail-Safe on Missing State Tests ---

def test_missing_home_refuses_geofence_checks(gate, default_state):
    default_state.home_lat = None
    default_state.home_lon = None
    cmd = {"action": "goto", "params": {"lat": 37.413972, "lon": -121.996161, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "home position unknown" in reason


def test_missing_current_position_refuses_move(gate, default_state):
    default_state.current_lat = None
    cmd = {"action": "move", "params": {"distance_m": 300, "bearing_deg": 90, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "current position unknown" in reason


def test_missing_current_altitude_refuses_climb_and_descend(gate, default_state):
    default_state.current_alt_m = None
    ok1, reason1 = gate.check_command({"action": "climb", "params": {"amount_m": 10}}, default_state)
    assert not ok1 and "current altitude unknown" in reason1
    ok2, reason2 = gate.check_command({"action": "descend", "params": {"amount_m": 10}}, default_state)
    assert not ok2 and "current altitude unknown" in reason2


# --- Goto & Altitude Tests ---

def test_goto_valid(gate, default_state):
    cmd = {"action": "goto", "params": {"lat": 37.413972, "lon": -121.996161, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok
    assert reason == "ok"


def test_goto_place_resolution(gate, default_state):
    cmd = {"action": "goto", "params": {"place": "north_field", "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok
    assert reason == "ok"


def test_goto_unlisted_place_refused(gate, default_state):
    cmd = {"action": "goto", "params": {"place": "unknown_base", "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "not in places table" in reason


def test_goto_altitude_too_high_refused(gate, default_state):
    cmd = {"action": "goto", "params": {"place": "north_field", "alt_m": 150}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "exceeds maximum limit" in reason


def test_goto_outside_geofence_refused(gate, default_state):
    cmd = {"action": "goto", "params": {"lat": 37.7749, "lon": -122.4194, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "outside" in reason and "geofence" in reason


# --- Move, Climb, Descend Tests ---

def test_move_within_geofence(gate, default_state):
    cmd = {"action": "move", "params": {"distance_m": 300, "bearing_deg": 90, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok
    assert reason == "ok"


def test_move_exceeds_geofence(gate, default_state):
    cmd = {"action": "move", "params": {"distance_m": 2000, "bearing_deg": 0, "alt_m": 40}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "geofence" in reason


def test_climb_within_limit(gate, default_state):
    cmd = {"action": "climb", "params": {"amount_m": 30}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok


def test_climb_exceeds_limit(gate, default_state):
    default_state.current_alt_m = 100.0
    cmd = {"action": "climb", "params": {"amount_m": 30}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "exceeding 120 m limit" in reason


def test_descend_within_limit(gate, default_state):
    cmd = {"action": "descend", "params": {"amount_m": 20}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok


def test_descend_below_min_limit(gate, default_state):
    default_state.current_alt_m = 10.0
    cmd = {"action": "descend", "params": {"amount_m": 15}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "below 1 m limit" in reason


# --- Search Area Tests ---

def test_search_area_valid(gate, default_state):
    cmd = {
        "action": "search_area",
        "params": {"place": "north_field", "radius_m": 100, "alt_m": 50, "target": "vehicle"}
    }
    ok, reason = gate.check_command(cmd, default_state)
    assert ok


def test_search_area_boundary_exceeds_geofence(gate, default_state):
    lat, lon = destination_point(BAYLANDS_HOME[0], BAYLANDS_HOME[1], 0.0, 1400.0)
    cmd = {
        "action": "search_area",
        "params": {"lat": lat, "lon": lon, "radius_m": 200, "alt_m": 50, "target": "vehicle"}
    }
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "geofence" in reason


# --- Loiter, Event ID & Radius Tests ---

def test_loiter_known_event_passes(gate, default_state):
    cmd = {"action": "loiter", "params": {"event_id": "E03", "radius_m": 30, "duration_s": 120}}
    ok, reason = gate.check_command(cmd, default_state)
    assert ok
    assert reason == "ok"


def test_loiter_unknown_event_refused(gate, default_state):
    cmd = {"action": "loiter", "params": {"event_id": "E99", "radius_m": 30, "duration_s": 120}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "not recognized" in reason


def test_loiter_radius_too_large_refused(gate, default_state):
    # S40: 1000m loiter radius
    cmd = {"action": "loiter", "params": {"event_id": "E03", "radius_m": 1000, "duration_s": 120}}
    ok, reason = gate.check_command(cmd, default_state)
    assert not ok
    assert "exceeds maximum limit" in reason


def test_config_loader():
    cfg = SafetyConfig.from_file()
    assert cfg.max_alt_m == 120.0
    assert cfg.min_battery_percent == 25.0
    assert cfg.geofence_radius_m == 1500.0


def test_hold_and_clarify_always_pass(gate, default_state):
    assert gate.check_command({"action": "hold", "params": {}}, default_state) == (True, "ok")
    cmd = {"action": "clarify", "params": {"reason": "missing_altitude", "question": "How high?"}}
    assert gate.check_command(cmd, default_state) == (True, "ok")
