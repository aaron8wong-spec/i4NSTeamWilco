#!/usr/bin/env python3
import asyncio
from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw

async def run():
    drone = System()
    print("[INIT] Connecting to SITL on udp://:14540...")
    await drone.connect(system_address="udp://:14540")

    print("[INIT] Waiting for drone connection...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[STATUS] Connected to vehicle.")
            break

    print("[STATUS] Waiting for global position lock...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("[STATUS] Position lock acquired.")
            break

    print("[CMD] Arming...")
    await drone.action.arm()

    print("[CMD] Taking off...")
    await drone.action.takeoff()
    await asyncio.sleep(8)

    # Relative NED coordinates: 10m North, 10m East, 5m altitude (NED down is negative)
    target_north = 10.0
    target_east = 10.0
    target_down = -5.0
    tolerance_m = 0.5

    print("[CMD] Starting offboard navigation...")
    # Send an initial setpoint before starting offboard mode
    await drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, target_down, 0.0))
    try:
        await drone.offboard.start()
    except OffboardError as e:
        print(f"[FAIL] Offboard start failed: {e._result.result}")
        await drone.action.land()
        return

    print(f"[NAV] Routing to target (N: {target_north}m, E: {target_east}m, Alt: 5m)...")
    await drone.offboard.set_position_ned(PositionNedYaw(target_north, target_east, target_down, 45.0))

    async for pos in drone.telemetry.position_velocity_ned():
        cur_n = pos.position.north_m
        cur_e = pos.position.east_m
        cur_d = pos.position.down_m

        dist_error = ((target_north - cur_n)**2 + (target_east - cur_e)**2 + (target_down - cur_d)**2)**0.5
        print(f"[TELEMETRY] N: {cur_n:5.2f}m | E: {cur_e:5.2f}m | Alt: {-cur_d:4.2f}m | Err: {dist_error:4.2f}m")

        if dist_error <= tolerance_m:
            print(f"[GATE PASS] Waypoint reached within {tolerance_m}m tolerance.")
            break
        await asyncio.sleep(1)

    print("[CMD] Stopping offboard and landing...")
    try:
        await drone.offboard.stop()
    except OffboardError as e:
        print(f"[WARN] Offboard stop notice: {e._result.result}")

    await drone.action.land()

    async for in_air in drone.telemetry.in_air():
        if not in_air:
            print("[STATUS] Touchdown detected. Mission complete.")
            break
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run())
