"""Fake flight backend (Lane M). Implements the FlightBackend contract in docs/contracts.md section 4.

Moves a point along straight lines at 10 m/s and emits positions at 5 Hz of
simulated time. No simulator, no MAVSDK. Commands must already carry lat/lon
(the pipeline resolves place names and event ids before execute).

`time_scale` speeds up the wait between ticks: 1.0 is real time, 0 does not wait
(used by tests). Simulated time (`time_s`) is always exact.
"""
import asyncio
import math

try:
    from integration import geo
except ImportError:  # run from inside integration/
    import geo

SPEED_MPS = 10.0
HZ = 5
DT = 1.0 / HZ
ARRIVE_M = 0.5


class MockFlight:
    def __init__(self, home_lat=37.412173071650805, home_lon=-121.998878727967,
                 search_spacing_m=60, time_scale=1.0):
        self.home = {"lat": home_lat, "lon": home_lon, "alt_amsl_m": 38.0}
        self.search_spacing_m = search_spacing_m
        self.time_scale = time_scale
        self.north_m = 0.0
        self.east_m = 0.0
        self.alt_m = 0.0
        self.time_s = 0.0
        self._callbacks = []
        self.executed = []  # every command received, in order (for tests)

    # ---- contract ----
    async def connect(self):
        return dict(self.home)

    def subscribe_positions(self, callback):
        self._callbacks.append(callback)

    async def close(self):
        self._callbacks.clear()

    def position(self):
        lat, lon = geo.local_to_latlon(self.north_m, self.east_m, self.home["lat"], self.home["lon"])
        return {"time_s": round(self.time_s, 2), "lat": lat, "lon": lon, "alt_m": self.alt_m,
                "north_m": self.north_m, "east_m": self.east_m}

    async def execute(self, cmd):
        self.executed.append(cmd)
        action, p = cmd.get("action"), cmd.get("params", {})
        try:
            if action == "goto":
                await self._fly_to(*self._local(p), p.get("alt_m", self.alt_m))
            elif action == "move":
                lat, lon = geo.destination_point(*self._latlon(), p["bearing_deg"], p["distance_m"])
                await self._fly_to(*self._local({"lat": lat, "lon": lon}), p["alt_m"])
            elif action == "climb":
                await self._fly_to(self.north_m, self.east_m, self.alt_m + p["amount_m"])
            elif action == "descend":
                await self._fly_to(self.north_m, self.east_m, max(0.0, self.alt_m - p["amount_m"]))
            elif action == "hold":
                await self._tick()
            elif action == "return_home":
                await self._fly_to(0.0, 0.0, self.alt_m)
                await self._fly_to(0.0, 0.0, 0.0)
            elif action == "search_area":
                await self._search(p)
            elif action == "loiter":
                await self._loiter(p)
            else:
                return {"ok": False, "action": action, "detail": "unsupported by mock"}
        except KeyError as e:
            return {"ok": False, "action": action, "detail": f"missing param {e}"}
        return {"ok": True, "action": action, "detail": "done"}

    # ---- internals ----
    def _latlon(self):
        p = self.position()
        return p["lat"], p["lon"]

    def _local(self, p):
        if "lat" not in p or "lon" not in p:
            raise KeyError("lat/lon")
        return geo.latlon_to_local(p["lat"], p["lon"], self.home["lat"], self.home["lon"])

    async def _tick(self):
        self.time_s += DT
        pos = self.position()
        for cb in list(self._callbacks):
            cb(pos)
        if self.time_scale > 0:
            await asyncio.sleep(DT / self.time_scale)
        else:
            await asyncio.sleep(0)

    async def _fly_to(self, north, east, alt):
        step = SPEED_MPS * DT
        while True:
            dn, de, da = north - self.north_m, east - self.east_m, alt - self.alt_m
            dist = math.hypot(dn, de, da)
            if dist <= ARRIVE_M:
                self.north_m, self.east_m, self.alt_m = north, east, alt
                return
            f = min(1.0, step / dist)
            self.north_m += dn * f
            self.east_m += de * f
            self.alt_m += da * f
            await self._tick()

    async def _search(self, p):
        """Lawnmower: north-south passes spaced search_spacing_m apart across a square of side 2*radius_m."""
        cn, ce = self._local(p)
        r, alt = p["radius_m"], p["alt_m"]
        east = -r
        going_north = True
        while east <= r:
            a, b = (-r, r) if going_north else (r, -r)
            await self._fly_to(cn + a, ce + east, alt)
            await self._fly_to(cn + b, ce + east, alt)
            east += self.search_spacing_m
            going_north = not going_north

    async def _loiter(self, p):
        cn, ce = self._local(p)
        r, dur = p["radius_m"], p["duration_s"]
        await self._fly_to(cn, ce + r, self.alt_m)
        angle, rate = 0.0, SPEED_MPS / max(r, 1)  # rad/s at cruise speed
        for _ in range(int(dur * HZ)):
            angle += rate * DT
            self.north_m = cn + r * math.sin(angle)
            self.east_m = ce + r * math.cos(angle)
            await self._tick()
        # then hold at the last point
