# Contracts between the two work lanes

Draft, 2026-11-19. Two people work in parallel: **Lane M** (Mac, has the model: language, reporting, voice, integration, docs) and **Lane S** (WSL2, has the simulator: flight). Each lane builds and tests against a fake of the other lane's code. These contracts say what the fakes must look like. If you need to change one, edit this file in the same PR and tell the other person. `integration/schemas.json` still wins for any JSON shape.

All units: meters, seconds, WGS84 lat/lon. Altitude is meters above home. `north_m` and `east_m` are meters from home.

## 0. Folder ownership

| Folder / file | Owner | Others may |
|---|---|---|
| `flight/` | Lane S | read, import |
| `language/`, `reporting/`, `voice/`, `data/`, `docs/` | Lane M | read, import |
| `integration/` | Lane M | Lane S edits only `run_command.py` gate wiring, in a small PR |
| `integration/schemas.json` | both must agree | no change without both agreeing in writing |

Nothing is merged unless `python3 -m pytest -q` passes in every folder that has tests. Every task needs a test or a logged number.

## 1. Config: `integration/config.json` (Lane M creates, Lane S reads)

Proposed defaults. Both of us confirm them before the safety gate is final.

```json
{
  "geofence_radius_m": 1500,
  "max_alt_m": 120,
  "min_alt_m": 1,
  "battery_floor_pct": 25,
  "lost_link_hold_s": 10,
  "detection_range_m": 60,
  "search_spacing_m": 60,
  "confidence_noise_sigma": 0.05,
  "arrive_horiz_m": 3.0,
  "arrive_vert_m": 2.0
}
```

`geofence_radius_m` and `max_alt_m` match the test limits now in `run_command.py`. The battery floor and hold time are new proposals.

## 2. `integration/geo.py` (Lane M; Lane S imports it)

```python
latlon_to_local(lat, lon, home_lat, home_lon) -> (north_m, east_m)
local_to_latlon(north_m, east_m, home_lat, home_lon) -> (lat, lon)
distance_m(lat1, lon1, lat2, lon2) -> float          # haversine
```

Tests: a round trip returns the start point within 0.01 m, and 100 m north changes lat by about 0.0009 degrees. Home always comes from the simulator. Never hardcode it. World origin from `baylands.sdf` (frame is ENU: x east, y north): lat 37.412173071650805, lon -121.998878727967, elevation 38 m. Use it only in tests and in the `places.json` conversion, not in flight code.

(Moved from `flight/geo.py` in the plan so the file has one owner. `run_command.py` already has `distance_m` and `destination_point`. Move them here and import them.)

## 3. Safety gate: `flight/safety.py` (Lane S, written; adopted as the contract on 2026-11-19)

```python
gate = SafetyGate(SafetyConfig(max_alt_m=120, min_alt_m=1, geofence_radius_m=1500, min_battery_percent=20))
gate.check_command(cmd: dict, state: DroneState) -> tuple[bool, str]   # (True, "ok") or (False, "reason")
```

- `DroneState` is a dataclass: `mode, battery_percent, home_lat, home_lon, current_lat, current_lon, current_alt_m, places`.
- It is a **per-call snapshot**. `pipeline.py` builds a fresh `DroneState` from `MissionState` and the backend telemetry before every check. Nothing may keep a long-lived copy (single source of truth is `mission_state.py`).
- The gate resolves `place` names from `state.places`, and refuses a name that is not in the table. It does not rewrite the command. `pipeline.py` resolves the place to lat/lon from `places.json` before calling `backend.execute`, so the backend only ever sees lat/lon.
- Pure Python, no model calls, no MAVSDK. Refuses and never repairs.
- Done and tested (23 tests): schema, manual mode, battery floor (only `return_home` passes), altitude min and max, geofence for `goto`, `move` and `search_area` (search radius included), climb and descend limits.

Open items for Lane S, in priority order:
1. **Fail open on missing state.** `_check_geofence` returns ok when home is unknown, and `move`, `climb`, `descend` return ok when the current position or altitude is unknown. A flight command with missing state must be refused with a reason.
2. **`loiter` with an `event_id`** passes without checking that the event exists. Seeds S36 and S40 show the model inventing `E03` (S40 also asks for a 1000 m radius) and the gate says ok. Add `known_event_ids` to `DroneState` (filled from the emitter and `mission_state`) and refuse an unknown id. Add a maximum loiter radius.
3. **Read limits from `integration/config.json`** instead of the dataclass defaults. The battery floor is 20 in the code and 25 in the config; pick one and write it in the config.
4. **Lost-link check:** add `link_ok` to `DroneState`. When it is false, only `hold` and `return_home` pass.
5. **One distance function.** `haversine_distance_m` and `destination_point` are now defined in `safety.py` and in `run_command.py`. Import both from `integration/geo.py` when it lands.
6. Wire the gate into `integration/run_command.py` in place of `check_command` and the test limits.

Seeds note: S34, S36 and S40 still pass the gate. S34 (invented altitude of 1 m) is the grounding guard's job (`language/guard.py`), not the gate's. S38 is a correct `clarify`, which is not a flight command and should pass. The gate refuses S35 (unknown place). Three expected seed commands are refused for expected reasons: S15 and S23 use placeholder place names, and S49 moves 2000 m, beyond the 1500 m geofence.

## 4. Flight backend (Lane S builds the real one, Lane M builds the fake)

One interface, two implementations. `main.py` takes a backend object and does not care which one.

```python
class FlightBackend:
    async def connect(self) -> dict            # {"lat":..., "lon":..., "alt_amsl_m":...}  home, read from the sim
    async def execute(self, cmd: dict) -> dict # {"ok": bool, "action": str, "detail": str}
    def subscribe_positions(self, callback) -> None   # callback(position) at 2 Hz or faster
    async def close(self) -> None
```

A position is:

```json
{"time_s": 41.5, "lat": 37.4131, "lon": -121.9990, "alt_m": 49.8, "north_m": 98.2, "east_m": 12.0}
```

- `execute` returns when the action is done or has failed. `search_area` returns when the sweep ends. `loiter` returns after `duration_s`, then the drone holds.
- The backend only receives lat/lon. The pipeline turns a `place` or an `event_id` into lat/lon before `execute`.
- `execute` must never be called with a command that the gate refused. `main.py` guarantees that. The backend can assume it.
- Real backend: `flight/backend_px4.py` (Lane S). Fake backend: `integration/mock_flight.py` (Lane M). It moves a point along straight lines at 10 m/s and emits positions at 5 Hz, so `main.py` and the emitter can be tested with no simulator.

## 5. `integration/mission_state.py` (Lane M)

```python
class MissionState:
    def __init__(self, config: dict): ...
    def set_home(self, lat, lon): ...
    def set_search(self, target, lat, lon, radius_m, alt_m): ...
    def mark_reported(self, event_id): ...
    def set_pending(self, text, event_id, proposed_command): ...
    def clear_pending(self): ...
    def set_mode(self, mode):  # "manual" | "ai"
    def as_dict(self) -> dict  # validates against MissionState in schemas.json
```

No other module keeps its own copy of any of this.

## 6. Event emitter: `flight/emitter.py` (Lane S)

```python
class EventEmitter:
    def __init__(self, scenario_path, home_lat, home_lon, config, seed=0): ...
    def on_position(self, position: dict) -> list[dict]   # zero or more Event dicts
```

- Pure Python. It needs only positions, so test it with a made-up track.
- Fires each find once, the first time the drone is within `detection_range_m` of it.
- Output matches `Event` in `schemas.json`: `id, type, confidence, lat, lon, time_s, people_visible` and optional `subtype`.
- Confidence = base confidence plus normal noise (sigma from config), clipped to 0 to 1, from a seeded random generator. The same seed gives the same events.

Scenario file (`flight/scenarios/demo.json`):

```json
{"name": "demo",
 "finds": [
  {"id": "E01", "type": "wildlife", "north_m": 230, "east_m": 170, "people_visible": 0, "confidence": 0.90, "subtype": "deer"},
  {"id": "E02", "type": "vehicle",  "north_m": 180, "east_m": 230, "people_visible": 0, "confidence": 0.85, "subtype": "truck"},
  {"id": "E03", "type": "vehicle",  "north_m": 200, "east_m": 310, "people_visible": 2, "confidence": 0.82, "subtype": "truck"},
  {"id": "E04", "type": "unknown",  "north_m": 235, "east_m": 255, "people_visible": 0, "confidence": 0.40}
 ]}
```

Positions are meters from home. `north_field` is at 200 m north, 240 m east (verified in the sim by Lane S). All four finds are inside a 150 m search radius around it and on open ground (`:` cells in the map). E03 is the east edge, matching the demo line "Vehicle with two people at the east edge". Lane S checks that each find is on open ground in Gazebo.

## 7. Scorer: `reporting/scorer.py` (Lane M)

```python
load_rules(path) -> list[dict]                                  # validates each rule against Rule in schemas.json
score(event: dict, state: MissionState, rules: list[dict]) -> dict   # an OperatorMessage
```

- Follows section 6 of `CLAUDE.md`. For an `ask`, it calls `state.set_pending(...)` and the text ends with a yes/no question. It calls `state.mark_reported(...)` for reported events.
- The text always names the rule's reason.

## 8. Pipeline: `integration/pipeline.py` (Lane M)

```python
handle_text(text, state, backend, llm_url, dry_run=False) -> dict
# {"text":..., "command":..., "gate": [ok, reason], "result": {...} | None}
```

Order: normalize units, model with grammar, grounding guard, resolve `place` to lat/lon through `places.json`, safety gate, then `backend.execute`. If `state.pending_question` is set, a short reply such as "yes" goes to the model with the pending question in the prompt. A refused or `clarify` command never reaches the backend. `main.py` calls this function and the emitter and scorer. It writes every stage to a JSONL run log (`ts`, `stage`, `data`).

## 9. Working without the other lane

- Lane S has no model. Use the JSON in `data/seeds.jsonl` and `python3 integration/run_command.py '<json>'`. Use `--llm http://<Mac IP>:8080` only for the final end-to-end test.
- Lane M has no simulator. Use `integration/mock_flight.py` and `run_command.py --dry-run`.
- Both: add new fixtures to `docs/fixtures/` (one small JSON file each) when the contract above does not give enough detail.

## 10. Merge points

| When | What must be on main |
|---|---|
| Fri night | `config.json`, `geo.py`, `safety.py`, `mission_state.py`, migrated `rules.json`, `mock_flight.py` |
| Sat midday | scorer, emitter, `search_area` and `loiter` in the real backend, `main.py` running on the mock |
| Sun | `main.py` on the real backend: one full run of the demo scenario, run log committed |
