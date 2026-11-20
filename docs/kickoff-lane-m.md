# Kickoff prompt: Lane M (paste into your coding agent)

Paste `CLAUDE.md` first, then this.

---

I am Lane M of a two-person team (see docs/who-owns-what.md). My teammate owns `flight/` and has the simulator. I have the language model and a Mac. We work asynchronously and merge through `docs/contracts.md`. Read that file and `integration/schemas.json` before writing code.

Rules:
- Work only in `integration/`, `reporting/`, `language/`, `voice/`, `data/`, `docs/`. Do not edit `flight/`.
- Follow `docs/contracts.md` exactly. If a contract is wrong or missing, stop, say so, and draft the change. Do not guess.
- Do not change `integration/schemas.json` and do not add actions, features or dependencies.
- The LLM suggests and plain code decides. Never let model output reach the backend without the safety gate.
- Every function gets a pytest test or a logged number. Say how any number was measured. Do not invent numbers.
- Do not tune on `data/test.jsonl` or on the 15 frozen events. Score the test set once, at the end.
- Use plain, simple technical English.
- Small commits on a branch named `lane-m/<topic>`. Run `python3 -m pytest -q` in every folder before each commit.

Do these in order. Stop after each and show me the test output.

1. `integration/config.json` with the defaults in contracts.md section 1, and `integration/geo.py` with round-trip tests. Move `distance_m` and `destination_point` out of `run_command.py` and import them.
2. Migrate `reporting/rules.json` to the frozen Rule schema (`event_type`, `condition` object, `safety_relevant`). List every rule that loses meaning (for example "at most 2 people" and confidence in the condition) and ask me what to do. Add a test that validates every rule against `schemas.json`.
3. `integration/mission_state.py` with tests for each state change. `as_dict()` must validate against `MissionState` in the schema.
4. `integration/mock_flight.py` implementing `FlightBackend` from contracts.md section 4.
5. `reporting/scorer.py` following section 6 of CLAUDE.md, plus 15 labeled events and tests. Mismatches are listed, not hidden.
6. `integration/pipeline.py` and `integration/main.py` running on the mock backend with a JSONL run log. Demo: type "search the north field for vehicles", fake events fire, the scorer asks "Loiter?", I type "yes, loiter", a `loiter` command comes out.
7. Continue with the Lane M list in docs/who-owns-what.md.

After that, read docs/work-plan.md and work through the Lane M table in order (M1... or S1...). Keep your progress in docs/status-lane-m.md. If a task needs the other lane's code, use the fake the plan names and keep going.

Start with step 1.
