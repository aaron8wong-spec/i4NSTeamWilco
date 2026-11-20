"""Fake event source (Lane M): fires the four demo events at fixed simulated times.

Stand-in for flight/emitter.py (Lane S). Same Event shape as `Event` in schemas.json.
Positions come from the demo scenario in docs/contracts.md section 6 (meters from home).
"""
try:
    from integration import geo
except ImportError:
    import geo

DEMO_FINDS = [
    {"id": "E01", "type": "wildlife", "north_m": 230, "east_m": 170, "people_visible": 0, "confidence": 0.90, "subtype": "deer", "at_s": 20},
    {"id": "E02", "type": "vehicle", "north_m": 180, "east_m": 230, "people_visible": 0, "confidence": 0.85, "subtype": "truck", "at_s": 40},
    {"id": "E03", "type": "vehicle", "north_m": 200, "east_m": 310, "people_visible": 2, "confidence": 0.82, "subtype": "truck", "at_s": 60},
    {"id": "E04", "type": "unknown", "north_m": 235, "east_m": 255, "people_visible": 0, "confidence": 0.40, "at_s": 80},
]


class FakeEvents:
    def __init__(self, home_lat, home_lon, finds=None):
        self._pending = [dict(f) for f in (finds or DEMO_FINDS)]
        self.home = (home_lat, home_lon)
        self.positions = {}  # id -> (lat, lon), so the pipeline can resolve loiter event_id

    def on_time(self, time_s):
        """Return the events whose time has come. Each event is returned once."""
        due, rest = [], []
        for f in self._pending:
            (due if time_s >= f["at_s"] else rest).append(f)
        self._pending = rest
        return [self._make(f, time_s) for f in due]

    def on_position(self, position):
        return self.on_time(position["time_s"])

    def _make(self, f, time_s):
        lat, lon = geo.local_to_latlon(f["north_m"], f["east_m"], *self.home)
        self.positions[f["id"]] = (lat, lon)
        ev = {"id": f["id"], "type": f["type"], "confidence": f["confidence"], "lat": lat, "lon": lon,
              "time_s": float(time_s), "people_visible": f["people_visible"]}
        if "subtype" in f:
            ev["subtype"] = f["subtype"]
        return ev
