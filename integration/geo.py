"""Geometry helpers shared by both lanes.

Local frame: north_m and east_m from a home point. Local conversions use WGS84
degree lengths computed at the home latitude (flat-earth, fine for a few km).
distance_m is haversine on a sphere of radius 6371000 m, matching run_command.py.
"""
import math

EARTH_RADIUS_M = 6371000.0


def meters_per_degree(lat_deg):
    """(m per degree latitude, m per degree longitude) at lat_deg, WGS84 series."""
    p = math.radians(lat_deg)
    m_lat = 111132.92 - 559.82 * math.cos(2 * p) + 1.175 * math.cos(4 * p) - 0.0023 * math.cos(6 * p)
    m_lon = 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p) + 0.118 * math.cos(5 * p)
    return m_lat, m_lon


def latlon_to_local(lat, lon, home_lat, home_lon):
    """(north_m, east_m) of a point relative to home."""
    m_lat, m_lon = meters_per_degree(home_lat)
    return (lat - home_lat) * m_lat, (lon - home_lon) * m_lon


def local_to_latlon(north_m, east_m, home_lat, home_lon):
    """(lat, lon) of a point north_m and east_m from home."""
    m_lat, m_lon = meters_per_degree(home_lat)
    return home_lat + north_m / m_lat, home_lon + east_m / m_lon


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def destination_point(lat, lon, bearing_deg, dist_m):
    """Point reached by going dist_m meters from (lat, lon) on a bearing (degrees clockwise from north)."""
    p1, l1, th, dr = math.radians(lat), math.radians(lon), math.radians(bearing_deg), dist_m / EARTH_RADIUS_M
    p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180
