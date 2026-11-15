#!/usr/bin/env python3
"""Smoke test: one JSON command (or typed text through the grammar) -> PX4 SITL moves.

This is a test bridge, not the final R1/R5 code. It proves the contract:
schema-valid JSON -> safety check -> MAVSDK -> drone moves.
It handles goto (lat/lon), hold and return_home. Other actions are printed and skipped.

Start PX4 with home near the seed coordinates (UCSD), or every goto is thousands of km away:
  cd ~/PX4-Autopilot
  PX4_HOME_LAT=32.8800 PX4_HOME_LON=-117.2400 PX4_HOME_ALT=100 HEADLESS=1 make px4_sitl gz_x500

Then, from the repo root:
  # A) JSON directly (no model needed)
  python3 integration/run_command.py '{"action":"goto","params":{"lat":32.8801,"lon":-117.2340,"alt_m":40}}'
  # B) typed text through the grammar, using a llama-server on another machine
  python3 integration/run_command.py --text "Fly to 32.8801, -117.2340 at 40 meters." --llm http://<IP>:8080
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
SUPPORTED = {"goto", "hold", "return_home"}


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


def check_command(cmd, validator, home=None):
    """Return (ok, reason). Schema first, then simple test limits."""
    errors = sorted(validator.iter_errors(cmd), key=lambda e: list(e.path))
    if errors:
        return False, f"not schema-valid: {errors[0].message}"
    action, p = cmd["action"], cmd["params"]
    if action not in SUPPORTED:
        return False, f"'{action}' is valid JSON but this smoke test only flies {sorted(SUPPORTED)}"
    if action == "goto":
        if "place" in p:
            return False, f"place '{p['place']}' needs the places table (not built yet); use lat/lon"
        if p["alt_m"] > MAX_ALT_M:
            return False, f"alt_m {p['alt_m']} is above the {MAX_ALT_M} m limit"
        if home is not None:
            d = distance_m(home[0], home[1], p["lat"], p["lon"])
            if d > GEOFENCE_M:
                return False, (f"target is {d:.0f} m from home, outside the {GEOFENCE_M} m geofence "
                               "(did you start PX4 with PX4_HOME_LAT/LON?)")
    return True, "ok"


def command_from_llm(text, url):
    sys.path.insert(0, str(ROOT / "language"))
    from run_llm import command_from_text
    raw, latency = command_from_text(text, url=url)
    print(f"[LLM] {latency:.1f}s -> {raw}")
    return json.loads(raw)


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

    ok, reason = check_command(cmd, load_validator(), (home.latitude_deg, home.longitude_deg))
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
