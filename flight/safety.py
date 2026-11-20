#!/usr/bin/env python3
"""Deterministic flight safety gate (Task 6.1).

Enforces hard safety constraints on all drone commands before they can reach the autopilot:
1. Schema conformity: Command must be valid according to integration/schemas.json.
2. Manual override: Rejects commands when drone mode is 'manual'.
3. Battery gate: Rejects flight commands when battery is below minimum threshold.
4. Altitude limits: Enforces minimum (1 m) and maximum (120 m) altitude limits.
5. Geofence: Enforces maximum distance from home position (default 1500 m).
6. Strict rejection: Commands outside limits are refused with an explanation; never silently 'fixed'.
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "integration" / "schemas.json"

# Safety limits (configurable via SafetyConfig)
DEFAULT_MAX_ALT_M = 120.0
DEFAULT_MIN_ALT_M = 1.0
DEFAULT_GEOFENCE_RADIUS_M = 1500.0
DEFAULT_MIN_BATTERY_PERCENT = 20.0
EARTH_RADIUS_M = 6371000.0


@dataclass
class SafetyConfig:
    max_alt_m: float = DEFAULT_MAX_ALT_M
    min_alt_m: float = DEFAULT_MIN_ALT_M
    geofence_radius_m: float = DEFAULT_GEOFENCE_RADIUS_M
    min_battery_percent: float = DEFAULT_MIN_BATTERY_PERCENT


@dataclass
class DroneState:
    mode: str = "ai"  # "ai" or "manual"
    battery_percent: float = 100.0
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_alt_m: Optional[float] = None
    places: Dict[str, Dict[str, float]] = field(default_factory=dict)


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS coordinates in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def destination_point(lat: float, lon: float, bearing_deg: float, dist_m: float) -> Tuple[float, float]:
    """Calculates destination GPS coordinates given start point, bearing in degrees, and distance in meters."""
    phi1 = math.radians(lat)
    lambda1 = math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = dist_m / EARTH_RADIUS_M

    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2)
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540.0) % 360.0 - 180.0


class SafetyGate:
    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()
        self._validator = None

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

        # 3. Battery Threshold Check
        if state.battery_percent < self.config.min_battery_percent and action != "return_home":
            return False, (
                f"refused: battery low ({state.battery_percent:.1f}% < {self.config.min_battery_percent:.1f}%); "
                f"only return_home is permitted"
            )

        # 4. Action-Specific Physical Boundary Checks
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
        if state.home_lat is None or state.home_lon is None:
            return True, "ok"
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
        # Loiter uses current altitude, so alt_m is not checked here
        if "place" in params or ("lat" in params and "lon" in params):
            lat, lon, err = self._resolve_location(params, state)
            if err:
                return False, err
            return self._check_geofence(lat, lon, state, extra_margin_m=float(params.get("radius_m", 0)))
        return True, "ok"

    def _check_move(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        alt_ok, alt_reason = self._check_altitude(params["alt_m"])
        if not alt_ok:
            return False, alt_reason

        if state.current_lat is None or state.current_lon is None:
            return True, "ok"

        dest_lat, dest_lon = destination_point(
            state.current_lat, state.current_lon,
            params["bearing_deg"], params["distance_m"]
        )
        return self._check_geofence(dest_lat, dest_lon, state)

    def _check_climb(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        if state.current_alt_m is None:
            return True, "ok"
        target_alt = state.current_alt_m + params["amount_m"]
        if target_alt > self.config.max_alt_m:
            return False, (
                f"climbing {params['amount_m']} m from current {state.current_alt_m:.1f} m "
                f"would reach {target_alt:.1f} m, exceeding {self.config.max_alt_m:.0f} m limit"
            )
        return True, "ok"

    def _check_descend(self, params: Dict[str, Any], state: DroneState) -> Tuple[bool, str]:
        if state.current_alt_m is None:
            return True, "ok"
        target_alt = state.current_alt_m - params["amount_m"]
        if target_alt < self.config.min_alt_m:
            return False, (
                f"descending {params['amount_m']} m from current {state.current_alt_m:.1f} m "
                f"would reach {target_alt:.1f} m, below {self.config.min_alt_m:.0f} m limit"
            )
        return True, "ok"
