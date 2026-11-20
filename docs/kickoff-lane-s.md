# Kickoff prompt: Lane S (paste into your coding agent)

Paste `CLAUDE.md` first, then this.

---

I am Lane S of a two-person team (see docs/who-owns-what.md). I own `flight/` and have PX4 SITL + Gazebo on WSL2. My teammate has the language model and does not have the simulator. We work asynchronously and merge through `docs/contracts.md`. Read that file, `integration/schemas.json` and `integration/run_command.py` before writing code.

Rules:
- Work only in `flight/`. The one exception is wiring the new gate into `integration/run_command.py`, in a small separate PR.
- Follow `docs/contracts.md` exactly. If a contract is wrong or missing, stop, say so, and draft the change. Do not guess.
- Do not change `integration/schemas.json` and do not add actions, features or dependencies.
- `safety.py` is pure Python with no model calls and no MAVSDK. It refuses and never repairs.
- Read home from the simulator. Never hardcode it. Check MAVSDK and PX4 commands against the official docs and say when unsure.
- I have no model. Test with JSON commands from `data/seeds.jsonl` and `python3 integration/run_command.py '<json>'`. Use `--llm http://<Mac IP>:8080` only for the final end-to-end test.
- Every function gets a pytest test or a logged number. Say how any number was measured. Do not invent numbers.
- Plain, simple technical English. Small commits on a branch named `lane-s/<topic>`. Run `python3 -m pytest -q` before each commit.

Do these in order. Stop after each and show me the test output or the simulator log.

1. Send `baylands.sdf` (from PX4-Autopilot, `Tools/simulation/gz/worlds/`) to my teammate. Note the PX4 version and Gazebo version in `flight/README.md` and remove the stray `nano flight/README.md` line.
2. `flight/safety.py` with the signature in contracts.md section 3. Tests: a pass, a fail and a boundary case per check. The seed outputs S34, S35, S36, S38 and S40 in `language/results_5_5.csv` must be refused with a reason. Then wire it into `run_command.py` in place of the test limits.
3. `flight/backend_px4.py` implementing `FlightBackend` (contracts.md section 4): `connect`, `execute` for `goto`, `move`, `climb`, `descend`, `hold`, `return_home`, and the position stream at 2 Hz or better.
4. `search_area` as a lawnmower sweep inside the radius (spacing from config) and `loiter` (circle for `duration_s`, then hold). Run each once in SITL and save the log.
5. `flight/emitter.py` (contracts.md section 6) with unit tests on a made-up track. Then `flight/scenarios/demo.json` and a second layout. Run the sweep in SITL: all four events fire once each, and the same seed gives the same events.
6. Continue with the Lane S list in docs/who-owns-what.md.

After that, read docs/work-plan.md and work through the Lane S table in order (M1... or S1...). Keep your progress in docs/status-lane-s.md. If a task needs the other lane's code, use the fake the plan names and keep going.

Start with step 1.
