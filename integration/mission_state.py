"""One shared copy of mission memory. Other modules read it and keep no copies.

Schema: MissionState in integration/schemas.json. as_dict() returns a deep copy.

Schema note: "geofence" is required and not nullable, but it is centered on
home, which is unknown until the sim reports it. Until set_home() is called,
as_dict() reports the geofence center as lat 0.0, lon 0.0 (a placeholder that
keeps the dict schema-valid). Callers must check that "home" is not None before
trusting the geofence center.
"""
import copy

MODES = ("manual", "ai")


class MissionState:
    def __init__(self, config: dict):
        self._radius_m = config["geofence_radius_m"]
        self._max_alt_m = config["max_alt_m"]
        self._target = None
        self._area = None
        self._home = None
        self._already_reported = []
        self._pending = None
        self._mode = "ai"

    def set_home(self, lat, lon):
        self._home = {"lat": lat, "lon": lon}

    def set_search(self, target, lat, lon, radius_m, alt_m):
        self._target = target
        self._area = {"lat": lat, "lon": lon, "radius_m": radius_m, "alt_m": alt_m}

    def mark_reported(self, event_id):
        if event_id not in self._already_reported:
            self._already_reported.append(event_id)

    def set_pending(self, text, event_id, proposed_command):
        self._pending = {
            "text": text,
            "event_id": event_id,
            "proposed_command": copy.deepcopy(proposed_command),
        }

    def clear_pending(self):
        self._pending = None

    def set_mode(self, mode):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self._mode = mode

    def as_dict(self) -> dict:
        home = self._home
        geofence = {
            "lat": home["lat"] if home else 0.0,
            "lon": home["lon"] if home else 0.0,
            "radius_m": self._radius_m,
            "max_alt_m": self._max_alt_m,
        }
        return copy.deepcopy({
            "target": self._target,
            "area": self._area,
            "geofence": geofence,
            "home": home,
            "already_reported": self._already_reported,
            "pending_question": self._pending,
            "mode": self._mode,
        })
