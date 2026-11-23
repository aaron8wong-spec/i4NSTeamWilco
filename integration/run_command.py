#!/usr/bin/env python3
"""Smoke test: one JSON command (or typed text through the grammar) -> PX4 SITL moves.

This is a test bridge, not the final R1/R5 code. It proves the contract:
schema-valid JSON -> safety check -> MAVSDK -> drone moves.
It handles goto (lat/lon), move, climb, descend, hold and return_home. Other actions are printed and skipped.
A move, climb or descend is turned into a goto from the drone's current position, then gated like any goto.

The seed coordinates are around the Gazebo Baylands world (home 37.412173, -121.998878).
Start PX4 in that world, or every goto is hundreds of km from home and the gate refuses it
(the default world is in Zurich). The script prints "[SIM] home ..." so you can check it:
  cd ~/PX4-Autopilot
  HEADLESS=1 make px4_sitl gz_x500   # start it in the Baylands world your team uses

Then, from the repo root:
  # A) JSON directly (no model needed)
  python3 integration/run_command.py '{"action":"goto","params":{"lat":37.4123,"lon":-121.9925,"alt_m":40}}'
  # B) typed text through the grammar, using a llama-server on another machine
  python3 integration/run_command.py --text "Fly to 37.4123, -121.9925 at 40 meters." --llm http://<IP>:8080
  # Check a command without flying (no sim needed)
  python3 integration/run_command.py --dry-run '{"action":"hold","params":{}}'
"""
import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCHEMA_PATH = ROOT / "integration" / "schemas.json"
PLACES_PATH = ROOT / "integration" / "places.json"

from integration.geo import destination_point, distance_m
from flight.safety import DroneState, SafetyConfig, SafetyGate

_GATE = None


def get_safety_gate():
    global _GATE
    if _GATE is None:
        _GATE = SafetyGate.from_config()
    return _GATE


def load_places():
    if PLACES_PATH.exists():
        try:
            data = json.loads(PLACES_PATH.read_text())
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception:
            pass
    return {}


# Flight limits and parameters
GATE_CONFIG = get_safety_gate().config
MAX_ALT_M = GATE_CONFIG.max_alt_m
GEOFENCE_M = GATE_CONFIG.geofence_radius_m
TAKEOFF_ALT_M = 10
ARRIVE_HORIZ_M = 3.0
ARRIVE_VERT_M = 2.0
GOTO_TIMEOUT_S = 180
SUPPORTED = {"goto", "move", "climb", "descend", "hold", "return_home"}


def load_validator():
    return get_safety_gate().validator


def new_altitude(current_alt_m, action, amount_m):
    """Altitude (whole meters above home) after a climb or descend. Raises ValueError if it would be below 1 m."""
    alt = round(current_alt_m + (amount_m if action == "climb" else -amount_m))
    if alt < 1:
        raise ValueError(f"descending {amount_m} m from {current_alt_m:.0f} m would go below 1 m")
    return alt


def check_command(cmd, validator=None, home=None, state=None):
    """Return (ok, reason). Validated through SafetyGate."""
    gate = get_safety_gate()
    action = cmd.get("action")
    if action not in SUPPORTED:
        return False, f"'{action}' is valid JSON but this smoke test only flies {sorted(SUPPORTED)}"

    if state is None:
        home_lat, home_lon = home if home is not None else (None, None)
        state = DroneState(
            mode="ai",
            battery_percent=100.0,
            link_ok=True,
            home_lat=home_lat,
            home_lon=home_lon,
            current_lat=home_lat,
            current_lon=home_lon,
            current_alt_m=40.0 if home_lat is not None else None,
            places=load_places(),
        )

    # Unit test / dry-run convenience for move: if state has no position/home yet,
    # validate schema and altitude ceiling so pre-flight checks report meaningful altitude errors.
    if action == "move" and (state.current_lat is None or state.home_lat is None):
        errors = sorted(gate.validator.iter_errors(cmd), key=lambda e: list(e.path))
        if errors:
            return False, f"not schema-valid: {errors[0].message}"
        alt = cmd.get("params", {}).get("alt_m", 0)
        if alt > gate.config.max_alt_m:
            return False, f"alt_m {alt} is above the {gate.config.max_alt_m:.0f} m limit"
        return True, "ok"

    return gate.check_command(cmd, state)


def command_from_llm(text, url):
    sys.path.insert(0, str(ROOT / "language"))
    from guard import check_grounding, normalize_units
    from run_llm import command_from_text
    text2 = normalize_units(text)
    if text2 != text:
        print(f"[NORM] {text2}")
    raw, latency = command_from_text(text2, url=url)
    print(f"[LLM] {latency:.1f}s -> {raw}")
    cmd, why = check_grounding(json.loads(raw), text2)
    if why:
        print(f"[GUARD] changed to clarify: {why}")
    return cmd


async def fly(cmd):
    from mavsdk import System

    drone = System()
    await drone.connect(system_address="udp://:14540")
    async for s in drone.core.connection_state():
        if s.is_connected:
            break
    async for h in drone.telemetry.health():
        if h.is_global_position_ok and h.is_home_position_ok:
            break
    async for home in drone.telemetry.home():
        break
    async for here in drone.telemetry.position():
        break
    battery_pct = 100.0
    async for b in drone.telemetry.battery():
        battery_pct = b.remaining_percent * 100.0
        break

    print(f"[SIM] home lat={home.latitude_deg:.6f} lon={home.longitude_deg:.6f} amsl={home.absolute_altitude_m:.1f}")

    places = load_places()
    state = DroneState(
        mode="ai",
        battery_percent=battery_pct,
        link_ok=True,
        home_lat=home.latitude_deg,
        home_lon=home.longitude_deg,
        current_lat=here.latitude_deg,
        current_lon=here.longitude_deg,
        current_alt_m=here.relative_altitude_m,
        places=places,
    )

    validator = load_validator()
    if cmd["action"] == "move":
        ok, reason = check_command(cmd, validator, state=state)
        if not ok:
            print(f"[GATE] refused: {reason}")
            return 2
        m = cmd["params"]
        lat, lon = destination_point(here.latitude_deg, here.longitude_deg, m["bearing_deg"], m["distance_m"])
        print(f"[MOVE] {m['distance_m']} m at {m['bearing_deg']} deg from {here.latitude_deg:.6f}, "
              f"{here.longitude_deg:.6f} -> {lat:.6f}, {lon:.6f}")
        cmd = {"action": "goto", "params": {"lat": round(lat, 6), "lon": round(lon, 6), "alt_m": m["alt_m"]}}

    if cmd["action"] in ("climb", "descend"):
        ok, reason = check_command(cmd, validator, state=state)
        if not ok:
            print(f"[GATE] refused: {reason}")
            return 2
        try:
            alt = new_altitude(here.relative_altitude_m, cmd["action"], cmd["params"]["amount_m"])
        except ValueError as e:
            print(f"[GATE] refused: {e}")
            return 2
        print(f"[{cmd['action'].upper()}] {here.relative_altitude_m:.0f} m -> {alt} m over {here.latitude_deg:.6f}, {here.longitude_deg:.6f}")
        cmd = {"action": "goto", "params": {"lat": round(here.latitude_deg, 6), "lon": round(here.longitude_deg, 6), "alt_m": alt}}

    # Pre-resolve place to lat/lon for the backend if given by place name
    if cmd["action"] == "goto" and "place" in cmd.get("params", {}):
        ok, reason = check_command(cmd, validator, state=state)
        if not ok:
            print(f"[GATE] refused: {reason}")
            return 2
        p_name = cmd["params"]["place"]
        loc = places[p_name]
        cmd = {"action": "goto", "params": {"lat": round(loc["lat"], 6), "lon": round(loc["lon"], 6), "alt_m": cmd["params"]["alt_m"]}}

    ok, reason = check_command(cmd, validator, state=state)
    if not ok:
        print(f"[GATE] refused: {reason}")
        return 2
    print(f"[GATE] passed: {cmd['action']}")

    async for in_air in drone.telemetry.in_air():
        break
    if not in_air and cmd["action"] != "return_home":
        print(f"[CMD] arm + takeoff to {TAKEOFF_ALT_M} m")
        await drone.action.set_takeoff_altitude(TAKEOFF_ALT_M)
        await drone.action.arm()
        await drone.action.takeoff()
        async for pos in drone.telemetry.position():
            if pos.relative_altitude_m >= 0.9 * TAKEOFF_ALT_M:
                break

    action, p = cmd["action"], cmd["params"]
    if action == "hold":
        await drone.action.hold()
        print("[CMD] hold")
        return 0
    if action == "return_home":
        await drone.action.return_to_launch()
        print("[CMD] return_to_launch")
        return 0

    # goto: MAVSDK wants altitude above sea level, our schema uses meters above home.
    target_amsl = home.absolute_altitude_m + p["alt_m"]
    await drone.action.goto_location(p["lat"], p["lon"], target_amsl, float("nan"))
    print(f"[CMD] goto {p['lat']}, {p['lon']} at {p['alt_m']} m above home")

    async def wait_arrival():
        # Do not sleep inside this loop: the position stream queues updates, so sleeping
        # makes us read old positions. Check every update, print about once per second.
        last_print = 0.0
        async for pos in drone.telemetry.position():
            horiz = distance_m(pos.latitude_deg, pos.longitude_deg, p["lat"], p["lon"])
            vert = abs(pos.relative_altitude_m - p["alt_m"])
            arrived = horiz <= ARRIVE_HORIZ_M and vert <= ARRIVE_VERT_M
            now = time.monotonic()
            if arrived or now - last_print >= 1.0:
                print(f"[TELEMETRY] to target: {horiz:6.1f} m horiz, {vert:4.1f} m vert")
                last_print = now
            if arrived:
                return horiz, vert

    try:
        horiz, vert = await asyncio.wait_for(wait_arrival(), GOTO_TIMEOUT_S)
    except asyncio.TimeoutError:
        print(f"[FAIL] did not arrive within {GOTO_TIMEOUT_S} s")
        return 1
    print(f"[PASS] arrived: {horiz:.1f} m horiz, {vert:.1f} m vert")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", help="JSON command string")
    ap.add_argument("--text", help="typed request; sent to llama-server with the grammar")
    ap.add_argument("--llm", default="http://127.0.0.1:8080", help="llama-server URL")
    ap.add_argument("--dry-run", action="store_true", help="validate and gate only, no sim")
    args = ap.parse_args()

    if args.text:
        cmd = command_from_llm(args.text, args.llm)
    elif args.command:
        cmd = json.loads(args.command)
    else:
        ap.error("give a JSON command or --text")

    if args.dry_run:
        ok, reason = check_command(cmd, load_validator())
        print(("[GATE] passed" if ok else "[GATE] refused: " + reason))
        return 0 if ok else 2
    return asyncio.run(fly(cmd))


if __name__ == "__main__":
    sys.exit(main())
