import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import geo

HOME = (37.412173071650805, -121.998878727967)
HERE = os.path.dirname(__file__)


def test_degree_lengths_match_work_plan():
    m_lat, m_lon = geo.meters_per_degree(HOME[0])
    assert abs(m_lat - 110985.4) < 0.5
    assert abs(m_lon - 88528.9) < 0.5


def test_round_trip():
    for n, e in [(0, 0), (200, 240), (-500, 700), (1500, -1500)]:
        lat, lon = geo.local_to_latlon(n, e, *HOME)
        n2, e2 = geo.latlon_to_local(lat, lon, *HOME)
        assert abs(n - n2) < 0.01 and abs(e - e2) < 0.01


def test_100m_north():
    lat, lon = geo.local_to_latlon(100, 0, *HOME)
    assert lat - HOME[0] == pytest.approx(0.0009, abs=0.00002)
    assert lon == pytest.approx(HOME[1])


def test_distance_sanity():
    assert geo.distance_m(*HOME, *HOME) == 0
    lat, lon = geo.local_to_latlon(300, 400, *HOME)
    assert geo.distance_m(*HOME, lat, lon) == pytest.approx(500, abs=1.5)
    assert geo.distance_m(0, 0, 1, 0) == pytest.approx(111195, abs=50)


def test_destination_point():
    lat, lon = geo.destination_point(*HOME, 0, 100)
    assert geo.distance_m(*HOME, lat, lon) == pytest.approx(100, abs=0.01)
    assert lon == pytest.approx(HOME[1])
    lat, lon = geo.destination_point(*HOME, 90, 100)
    assert lat == pytest.approx(HOME[0], abs=1e-6) and lon > HOME[1]


def test_places_json_north_field_within_1m():
    with open(os.path.join(HERE, "places.json")) as f:
        p = json.load(f)["north_field"]
    lat, lon = geo.local_to_latlon(200, 240, *HOME)
    d = geo.distance_m(lat, lon, p["lat"], p["lon"])
    print("north_field diff m:", d)
    assert d < 1.0


def test_config_keys():
    with open(os.path.join(HERE, "config.json")) as f:
        c = json.load(f)
    assert c["battery_floor_pct"] == 25 and c["max_alt_m"] == 120 and c["geofence_radius_m"] == 1500
