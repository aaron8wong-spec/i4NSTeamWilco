"""Unit tests for the run_command.py smoke test (no sim needed). Run: python3 -m pytest integration -q"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import run_command as rc  # noqa: E402

BAYLANDS = (37.412173, -121.998878)


def test_destination_north_1000_m():
    lat, lon = rc.destination_point(*BAYLANDS, 0, 1000)
    assert lat == pytest.approx(BAYLANDS[0] + 0.008993, abs=1e-5)
    assert lon == pytest.approx(BAYLANDS[1], abs=1e-6)


def test_destination_east_uses_latitude_scaling():
    lat, lon = rc.destination_point(*BAYLANDS, 90, 500)
    assert lat == pytest.approx(BAYLANDS[0], abs=1e-5)
    assert lon - BAYLANDS[1] == pytest.approx(0.005657, abs=2e-5)  # 500 m / (111195 m * cos 37.41 deg)


@pytest.mark.parametrize("bearing", [0, 45, 90, 135, 180, 225, 270, 315])
def test_destination_is_the_requested_distance_away(bearing):
    lat, lon = rc.destination_point(*BAYLANDS, bearing, 500)
    assert rc.distance_m(*BAYLANDS, lat, lon) == pytest.approx(500, abs=0.5)


def test_destination_wraps_longitude_at_the_date_line():
    lat, lon = rc.destination_point(0.0, 179.99, 90, 5000)
    assert -180 <= lon <= 180 and lon < 0


def test_climb_and_descend_altitude():
    assert rc.new_altitude(40, "climb", 61) == 101
    assert rc.new_altitude(40, "descend", 15) == 25
    assert rc.new_altitude(40.4, "climb", 10) == 50


def test_descend_below_one_meter_is_refused():
    with pytest.raises(ValueError):
        rc.new_altitude(10, "descend", 10)


V = None


def validator():
    global V
    V = V or rc.load_validator()
    return V


def test_move_passes_the_gate():
    cmd = {"action": "move", "params": {"distance_m": 500, "bearing_deg": 45, "alt_m": 40}}
    assert rc.check_command(cmd, validator()) == (True, "ok")


def test_move_too_high_is_refused_with_a_reason():
    cmd = {"action": "move", "params": {"distance_m": 500, "bearing_deg": 45, "alt_m": 800}}
    ok, reason = rc.check_command(cmd, validator())
    assert not ok and "800" in reason


@pytest.mark.parametrize("params", [
    {"distance_m": 500, "bearing_deg": 400, "alt_m": 40},   # bearing out of range
    {"distance_m": 500, "bearing_deg": 45},                 # missing altitude
    {"distance_m": 0, "bearing_deg": 45, "alt_m": 40},      # zero distance
])
def test_bad_move_is_not_schema_valid(params):
    ok, reason = rc.check_command({"action": "move", "params": params}, validator())
    assert not ok and reason.startswith("not schema-valid")
