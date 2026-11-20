# integration/

`pipeline.py` turns one typed line into a gated flight command. `main.py` runs the full demo loop on `MockFlight` and `FakeEvents` (no simulator). Perception is simulated: events are scripted.

## Run the demo

From the repo root, with a llama-server running (see `language/README.md`):

    python3 integration/main.py --script integration/demo_script.txt --time-scale 0 --llm http://127.0.0.1:8080

`--time-scale 0` does not wait (fast, same output every run); `1` is real time. Without `--script`, type lines on stdin (`quit` ends). Directives in a script: `/manual`, `/ai`, `@wait`. A `yes`/`no` line waits until the scorer has asked something. `--dry-run` gates but never flies. The run log (JSONL: `ts`, `stage`, `data`) goes to `runs/` (git-ignored) or `--log PATH`.

The grounding guard turns a number the operator did not say into a `clarify`, so the demo line includes radius and altitude. The bare "Search the north field for vehicles" gets a clarify from the guard.

## Tests (no server, fake model)

    python3 -m pytest -q integration reporting

## What the pipeline does

normalize units -> model (grammar) -> guard -> `event_id` to lat/lon (loiter) -> fresh `DroneState` -> `flight/safety.py` gate -> `place` to lat/lon -> `backend.execute`. Refused, `clarify` and `report_status` never reach the backend. A short "yes"/"no" with a pending question is handled in the pipeline (yes runs `proposed_command` through the same gate). TODO M8: pass `pending_question` to the model prompt.

## DroneState fields and gaps

Filled fresh before every check: `mode` and home (MissionState), `places`, position and altitude (`backend.position()`, which `MockFlight` has but the `FlightBackend` contract does not list), `battery_percent` (`backend.battery_percent` if present, else 100).
Not possible yet (contracts section 3): no `link_ok`, no `known_event_ids` (the pipeline refuses an unknown loiter `event_id` itself), no max loiter radius. The gate still fails open on missing home or position.
`set_search` is called when the gate passes, just before `execute`, so events fired during the sweep are scored against the target.
