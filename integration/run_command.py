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
SCHEMA_PATH = ROOT / "integration" / "schemas.json"

# Test limits only. The real values come from config and R1's safety.py.
MAX_ALT_M = 120
GEOFENCE_M = 1500        # max horizontal distance from home
TAKEOFF_ALT_M = 10
ARRIVE_HORIZ_M = 3.0
ARRIVE_VERT_M = 2.0
GOTO_TIMEOUT_S = 180
SUPPORTED = {"goto", "move", "climb", "descend", "hold", "return_home"}


def load_validator():
    from jsonschema import Draft202012Validator
    schema = json.loads(SCHEMA_PATH.read_text())
    cmd_schema = {"$schema": schema.get("$schema"), "$defs": schema["$defs"], "$ref": "#/$defs/Command"}
    return Draft202012Validator(cmd_schema)


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters (haversine)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def destination_point(lat, lon, bearing_deg, dist_m):
    """Point reached by going dist_m meters from (lat, lon) on a bearing (degrees clockwise from north)."""
    r = 6371000.0
    p1, l1, th, dr = math.radians(lat), math.radians(lon), math.radians(bearing_deg), dist_m / r
    p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def new_altitude(current_alt_m, action, amount_m):
    """Altitude (whole meters above home) after a climb or descend. Raises ValueError if it would be below 1 m."""
    alt = round(current_alt_m + (amount_m if action == "climb" else -amount_m))
    if alt < 1:
        raise ValueError(f"descending {amount_m} m from {current_alt_m:.0f} m would go below 1 m")
    return alt


def check_command(cmd, validator, home=None):
    """Return (ok, reason). Schema first, then simple test limits."""
    errors = sorted(validator.iter_errors(cmd), key=lambda e: list(e.path))
    if errors:
        return False, f"not schema-valid: {errors[0].message}"
    action, p = cmd["action"], cmd["params"]
    if action not in SUPPORTED:
        return False, f"'{action}' is valid JSON but this smoke test only flies {sorted(SUPPORTED)}"
    if action == "move":
        # The destination depends on the live position, so the geofence is checked on the goto it becomes.
        if p["alt_m"] > MAX_ALT_M:
            return False, f"alt_m {p['alt_m']} is above the {MAX_ALT_M} m limit"
    if action == "goto":
        if "place" in p:
            return False, f"place '{p['place']}' needs the places table (not built yet); use lat/lon"
        if p["alt_m"] > MAX_ALT_M:
            return False, f"alt_m {p['alt_m']} is above the {MAX_ALT_M} m limit"
        if home is not None:
            d = distance_m(home[0], home[1], p["lat"], p["lon"])
            if d > GEOFENCE_M:
                return False, (f"target is {d:.0f} m from home, outside the {GEOFENCE_M} m geofence "
                               "(is PX4's home where the seed coordinates are, e.g. the Baylands world?)")
    return True, "ok"


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
    print(f"[SIM] home lat={home.latitude_deg:.6f} lon={home.longitude_deg:.6f} amsl={home.absolute_altitude_m:.1f}")

    validator = load_validator()
    if cmd["action"] == "move":
        ok, reason = check_command(cmd, validator)
        if not ok:
            print(f"[GATE] refused: {reason}")
            return 2
        m = cmd["params"]
        async for here in drone.telemetry.position():
            break
        lat, lon = destination_point(here.latitude_deg, here.longitude_deg, m["bearing_deg"], m["distance_m"])
        print(f"[MOVE] {m['distance_m']} m at {m['bearing_deg']} deg from {here.latitude_deg:.6f}, "
              f"{here.longitude_deg:.6f} -> {lat:.6f}, {lon:.6f}")
        cmd = {"action": "goto", "params": {"lat": round(lat, 6), "lon": round(lon, 6), "alt_m": m["alt_m"]}}

    if cmd["action"] in ("climb", "descend"):
        ok, reason = check_command(cmd, validator)
        if not ok:
            print(f"[GATE] refused: {reason}")
            return 2
        async for here in drone.telemetry.position():
            break
        try:
            alt = new_altitude(here.relative_altitude_m, cmd["action"], cmd["params"]["amount_m"])
        except ValueError as e:
            print(f"[GATE] refused: {e}")
            return 2
        print(f"[{cmd['action'].upper()}] {here.relative_altitude_m:.0f} m -> {alt} m over {here.latitude_deg:.6f}, {here.longitude_deg:.6f}")
        cmd = {"action": "goto", "params": {"lat": round(here.latitude_deg, 6), "lon": round(here.longitude_deg, 6), "alt_m": alt}}

    ok, reason = check_command(cmd, validator, (home.latitude_deg, home.longitude_deg))
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
