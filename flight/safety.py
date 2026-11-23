#!/usr/bin/env python3
"""Deterministic flight safety gate (Task 6.1 / contracts.md section 3).

Enforces hard safety constraints on all drone commands before they can reach the autopilot:
1. Schema conformity: Command must be valid according to integration/schemas.json.
2. Manual override: Rejects commands when drone mode is 'manual'.
3. Lost link: Rejects flight commands when link_ok is False (only hold and return_home pass).
4. Battery floor: Rejects flight commands when battery is below threshold (only return_home passes).
5. Altitude limits: Enforces minimum (min_alt_m) and maximum (max_alt_m) altitude limits.
6. Geofence: Enforces maximum distance from home position (geofence_radius_m).
7. Fail-safe on missing state: Refuses flight commands when required state (home, current pos/alt) is unknown.
8. Event verification: Refuses loiter commands when event_id is not in known_event_ids.
9. Strict rejection: Commands outside limits are refused with an explanation; never silently 'fixed'.
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "integration" / "schemas.json"
CONFIG_PATH = ROOT / "integration" / "config.json"

try:
    from integration.geo import destination_point, distance_m as haversine_distance_m
except ImportError:
    # Standalone fallback if integration is not on sys.path
    EARTH_RADIUS_M = 6371000.0

    def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = p2 - p1, math.radians(lon2 - lon1)
        a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
        return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))

    def destination_point(lat: float, lon: float, bearing_deg: float, dist_m: float) -> Tuple[float, float]:
        p1, l1, th, dr = math.radians(lat), math.radians(lon), math.radians(bearing_deg), dist_m / EARTH_RADIUS_M
        p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(th))
        l2 = l1 + math.atan2(math.sin(th) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
        return math.degrees(p2), (math.degrees(l2) + 540.0) % 360.0 - 180.0


# Default safety limits matching integration/config.json
DEFAULT_MAX_ALT_M = 120.0
DEFAULT_MIN_ALT_M = 1.0
DEFAULT_GEOFENCE_RADIUS_M = 1500.0
DEFAULT_BATTERY_FLOOR_PCT = 25.0
DEFAULT_MAX_LOITER_RADIUS_M = 500.0


@dataclass
class SafetyConfig:
    max_alt_m: float = DEFAULT_MAX_ALT_M
    min_alt_m: float = DEFAULT_MIN_ALT_M
    geofence_radius_m: float = DEFAULT_GEOFENCE_RADIUS_M
    min_battery_percent: float = DEFAULT_BATTERY_FLOOR_PCT
    max_loiter_radius_m: float = DEFAULT_MAX_LOITER_RADIUS_M

    @classmethod
    def from_file(cls, path: Optional[Path] = None) -> "SafetyConfig":
        """Loads limits from config.json, falling back to defaults for missing keys."""
        cfg_path = Path(path) if path else CONFIG_PATH
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
                return cls(
                    max_alt_m=float(data.get("max_alt_m", DEFAULT_MAX_ALT_M)),
                    min_alt_m=float(data.get("min_alt_m", DEFAULT_MIN_ALT_M)),
                    geofence_radius_m=float(data.get("geofence_radius_m", DEFAULT_GEOFENCE_RADIUS_M)),
                    min_battery_percent=float(data.get("battery_floor_pct", DEFAULT_BATTERY_FLOOR_PCT)),
                    max_loiter_radius_m=float(data.get("max_loiter_radius_m", DEFAULT_MAX_LOITER_RADIUS_M)),
                )
            except Exception:
                pass
        return cls()


@dataclass
class DroneState:
    mode: str = "ai"  # "ai" or "manual"
    battery_percent: float = 100.0
    link_ok: bool = True
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_alt_m: Optional[float] = None
    places: Dict[str, Dict[str, float]] = field(default_factory=dict)
    known_event_ids: List[str] = field(default_factory=list)


class SafetyGate:
    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig.from_file()
        self._validator = None

    @classmethod
    def from_config(cls, path: Optional[Path] = None) -> "SafetyGate":
        return cls(config=SafetyConfig.from_file(path))

    @property
    def validator(self):
        if self._validator is None:
            from jsonschema import Draft202012Validator
            schema = json.loads(SCHEMA_PATH.read_text())
            cmd_schema = {
                "$schema": schema.get("$schema"),
                "$defs": schema["$defs"],
                "$ref": "#/$defs/Command"
            }
            self._validator = Draft202012Validator(cmd_schema)
        return self._validator

    def check_command(self, cmd: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        """Validates command against schema and safety limits. Returns (ok, reason)."""
        # 1. Schema Validation
        errors = sorted(self.validator.iter_errors(cmd), key=lambda e: list(e.path))
        if errors:
            return False, f"not schema-valid: {errors[0].message}"

        action = cmd.get("action")
        params = cmd.get("params", {})

        # Non-flight commands (report_status, clarify) do not move vehicle
        if action in ("report_status", "clarify"):
            return True, "ok"

        # 2. Manual Override Check
        if state.mode == "manual":
            return False, "refused: vehicle is in manual mode; AI flight commands are ignored"

        # 3. Lost-Link Check
        if not state.link_ok and action not in ("hold", "return_home"):
            return False, "refused: link lost; only hold and return_home are permitted"

        # 4. Battery Floor Check
        if state.battery_percent < self.config.min_battery_percent and action != "return_home":
            return False, (
                f"refused: battery low ({state.battery_percent:.1f}% < {self.config.min_battery_percent:.1f}%); "
                f"only return_home is permitted"
            )

        # 5. Action-Specific Physical Boundary & Fail-Safe Checks
        if action == "return_home":
            return True, "ok"

        if action == "hold":
            return True, "ok"

        if action == "goto":
            return self._check_goto(params, state)

        if action == "search_area":
            return self._check_search_area(params, state)

        if action == "loiter":
            return self._check_loiter(params, state)

        if action == "move":
            return self._check_move(params, state)

        if action == "climb":
            return self._check_climb(params, state)

        if action == "descend":
            return self._check_descend(params, state)

        return False, f"refused: unrecognized action '{action}'"

    def _resolve_location(self, params: Dict[str, Any], state: DroneState) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """Resolves target lat/lon from either explicit coordinates or places table."""
        if "lat" in params and "lon" in params:
            return params["lat"], params["lon"], None
        if "place" in params:
            place_name = params["place"]
            if place_name not in state.places:
                return None, None, f"place '{place_name}' is not in places table"
            loc = state.places[place_name]
            return loc["lat"], loc["lon"], None
        return None, None, "missing location target"

    def _check_geofence(self, target_lat: float, target_lon: float, state: DroneState, extra_margin_m: float = 0.0) -> Tuple[bool, str]:
        # Fail-safe: refusing if home position is missing
        if state.home_lat is None or state.home_lon is None:
            return False, "refused: home position unknown; cannot verify geofence"
        dist = haversine_distance_m(state.home_lat, state.home_lon, target_lat, target_lon) + extra_margin_m
        if dist > self.config.geofence_radius_m:
            return False, (
                f"target is {dist:.1f} m from home (including {extra_margin_m:.1f} m margin), "
                f"outside {self.config.geofence_radius_m:.0f} m geofence"
            )
        return True, "ok"

    def _check_altitude(self, alt_m: float) -> Tuple[bool, str]:
        if alt_m > self.config.max_alt_m:
            return False, f"alt_m {alt_m} exceeds maximum limit of {self.config.max_alt_m:.0f} m"
        if alt_m < self.config.min_alt_m:
            return False, f"alt_m {alt_m} is below minimum limit of {self.config.min_alt_m:.0f} m"
        return True, "ok"

    def _check_goto(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        alt_ok, alt_reason = self._check_altitude(params["alt_m"])
        if not alt_ok:
            return False, alt_reason

        lat, lon, err = self._resolve_location(params, state)
        if err:
            return False, err
        return self._check_geofence(lat, lon, state)

    def _check_search_area(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        alt_ok, alt_reason = self._check_altitude(params["alt_m"])
        if not alt_ok:
            return False, alt_reason

        lat, lon, err = self._resolve_location(params, state)
        if err:
            return False, err

        # The search boundary extends to target center + radius_m
        return self._check_geofence(lat, lon, state, extra_margin_m=float(params["radius_m"]))

    def _check_loiter(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        # Loiter radius limit check
        radius_m = float(params.get("radius_m", 0))
        if radius_m > self.config.max_loiter_radius_m:
            return False, f"loiter radius {radius_m:.0f} m exceeds maximum limit of {self.config.max_loiter_radius_m:.0f} m"

        # Event ID verification check
        if "event_id" in params:
            event_id = params["event_id"]
            if event_id not in state.known_event_ids:
                return False, f"refused: event '{event_id}' is not recognized in reported events"
            return True, "ok"

        # Explicit location check (place or lat/lon)
        if "place" in params or ("lat" in params and "lon" in params):
            lat, lon, err = self._resolve_location(params, state)
            if err:
                return False, err
            return self._check_geofence(lat, lon, state, extra_margin_m=radius_m)

        return True, "ok"

    def _check_move(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        alt_ok, alt_reason = self._check_altitude(params["alt_m"])
        if not alt_ok:
            return False, alt_reason

        # Fail-safe: refusing if current position is missing
        if state.current_lat is None or state.current_lon is None:
            return False, "refused: current position unknown; cannot project move destination"

        dest_lat, dest_lon = destination_point(
            state.current_lat, state.current_lon,
            params["bearing_deg"], params["distance_m"]
        )
        return self._check_geofence(dest_lat, dest_lon, state)

    def _check_climb(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        # Fail-safe: refusing if current altitude is missing
        if state.current_alt_m is None:
            return False, "refused: current altitude unknown; cannot verify climb ceiling"
        target_alt = state.current_alt_m + params["amount_m"]
        if target_alt > self.config.max_alt_m:
            return False, (
                f"climbing {params['amount_m']} m from current {state.current_alt_m:.1f} m "
                f"would reach {target_alt:.1f} m, exceeding {self.config.max_alt_m:.0f} m limit"
            )
        return True, "ok"

    def _check_descend(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        # Fail-safe: refusing if current altitude is missing
        if state.current_alt_m is None:
            return False, "refused: current altitude unknown; cannot verify descent floor"
        target_alt = state.current_alt_m - params["amount_m"]
        if target_alt < self.config.min_alt_m:
            return False, (
                f"descending {params['amount_m']} m from current {state.current_alt_m:.1f} m "
                f"would reach {target_alt:.1f} m, below {self.config.min_alt_m:.0f} m limit"
            )
        return True, "ok"
