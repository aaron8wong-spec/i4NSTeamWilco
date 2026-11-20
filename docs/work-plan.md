# Work plan for two people and two coding agents

Written 2026-11-19. Goal: finish as much of weeks 6 to 9 as possible in about four days, with two people working at the same time and not waiting on each other.

**How to use this file.** Each person pastes `CLAUDE.md`, then this file, then says which lane they are. The agent works its own lane from top to bottom. It does not touch the other lane's folders. When a task needs something from the other lane, it uses the fake described here and keeps going.

## 1. Why this works without waiting

- Each lane owns different folders, so there are no merge conflicts.
- `docs/contracts.md` fixes how the two lanes connect (function names, inputs, outputs). Each lane builds against a **fake** of the other lane, so every task below can be finished and tested on its own.
- The two lanes meet at only four points (section 5). Everything else is independent.

| Lane | Person | Owns | Has |
|---|---|---|---|
| **M** | you | `language/`, `reporting/`, `voice/`, `integration/`, `data/`, `docs/` | the Mac, the model, the microphone |
| **S** | teammate | `flight/` | WSL2, PX4 SITL, Gazebo |

## 2. Rules for both agents

1. Follow `docs/contracts.md`. If it is wrong or missing something, stop, write the problem in `docs/requests.md` (one line: who, what, why), use a sensible fake, and carry on. Do not wait for an answer.
2. Never change `integration/schemas.json` except as stated in decision D2 below.
3. Every function gets a pytest test or a logged number. Say how any number was measured. Do not invent numbers.
4. Work on a branch (`lane-m/<topic>` or `lane-s/<topic>`). Run `python3 -m pytest -q` in every folder before each commit. Merge to main at least twice a day, at noon and at night, only when tests pass.
5. Keep your progress in your own file: `docs/status-lane-m.md` or `docs/status-lane-s.md`. One line per finished task with the date and the test result. Do not edit the other lane's file.
6. Do not tune on `data/test.jsonl` or on the 15 frozen events. Score the test set once, at the end.
7. Plain, simple technical English. State the honest limits in anything that reports results: perception is simulated, results are from a simulator, data is our own synthetic data.

## 3. Decisions to confirm tonight

If nobody objects, the default applies and the agents proceed.

| # | Decision | Default |
|---|---|---|
| D1 | Rules that use "at most 2 people" or `confidence` in the condition | Drop those parts. `min_confidence` already covers confidence. Lane M lists every rule that loses meaning in `docs/rules-migration.md`. |
| D2 | Multi-step commands | Approve: add `{"steps": [command, ...]}` as schema v1.3.0 (max 5 steps, each step one existing command). Lane M edits `schemas.json`, rebuilds the grammar and adds data. Lane S builds the executor. |
| D3 | Safety limits | Battery floor 25%, max altitude 120 m, min altitude 1 m, geofence 1500 m, lost-link hold 10 s. Write them in `integration/config.json`. |
| D4 | Place names | Keep the three verified places (`north_field`, `buildings`, `bridge`). Lane S verifies 5 more open-ground points. Lane M then renames the dataset's place names to the real ones with a script. |

## 4. Lane M tasks (Mac, model)

Needs nothing from Lane S. The flight code is replaced by `integration/mock_flight.py` until Lane S's backend lands.

| # | Task | Files | Done when |
|---|---|---|---|
| M1 | Config and geometry | `integration/config.json`, `integration/geo.py` | Round-trip tests pass. Uses WGS84 degree lengths (110985.4 m per degree of latitude, 88528.9 m per degree of longitude at this latitude). `safety.py` and `run_command.py` can import it. |
| M2 | Migrate rules | `reporting/rules.json`, `docs/rules-migration.md` | A test validates all 15 rules against `Rule` in `schemas.json`. The doc lists every rule that lost meaning. |
| M3 | Mission state | `integration/mission_state.py` | One test per state change. `as_dict()` validates against the `MissionState` schema. |
| M4 | Fakes | `integration/mock_flight.py`, `integration/fake_events.py` | `MockFlight` implements `FlightBackend` and moves a point along lines at 10 m/s with positions at 5 Hz. `FakeEvents` fires the four demo events at fixed times. Both have tests. |
| M5 | Scorer, labeled events, templates | `reporting/scorer.py`, `data/labeled_events.json`, `reporting/templates.py` | One test per tier, a duplicate case and a low-confidence ask case. 30 labeled events, 15 marked frozen. Scorer output on the 15 non-frozen events matches the labels, or each mismatch is listed. |
| M6 | Pipeline and main loop on the mock | `integration/pipeline.py`, `integration/main.py` | Typed demo runs end to end on `MockFlight` and `FakeEvents`: "Search the north field for vehicles", four events, interrupt asks "Loiter?", "yes, loiter" produces a `loiter`. Runs twice in a row. JSONL run log written. The pipeline builds a fresh `DroneState` for `flight/safety.py` from `MissionState` before each check, and converts `place` and `event_id` to lat/lon before calling the backend (section 6). |
| M7 | Dataset | `data/`, `tools/remap_places.py` | 200 to 300 rows, clarify at 25% or more, 10% hand-checked, 20% held out, split per tag. `remap_places.py` takes a mapping and renames place names in both the text and the answer. |
| M8 | Follow-up prompt | `language/` | About 40 follow-up examples with a mission_state attached ("yes, loiter", "no, keep searching", "go back"). 20% held out. Reported next to the single-command number. |
| M9 | Steps grammar (after D2) | `integration/schemas.json`, `language/`, `data/` | Grammar rebuilt. About 30 multi-step rows, 20% held out. Grammar tests pass. |
| M10 | Eval and model comparison | `language/eval.py` | Train-split run after each prompt change. One other model size run. The test set is scored once, at the end, with `--split test --final`. LoRA only if the number in `docs/targets.md` says accuracy is clearly low. |
| M11 | Voice | `voice/` | `transcribe(wav)`, a push-to-talk recorder, 30 clips (10 noisy, with the noise source written down) and reference text. Word error rate for quiet and noisy clips logged with the model size. |
| M12 | Voice in the loop | `integration/main.py` | Same pipeline function as typed input. The transcript is shown before the command runs. An empty or garbled transcript is logged and ignored. |
| M13 | Docs and targets | `docs/targets.md`, `docs/hardware.md`, `docs/demo-script.md`, `docs/roadmap.md`, slides draft | Targets are written before any test runs. Hardware table has the Mac rows (CPU and GPU), measured the way `docs/hardware.md` states. Unmeasured cells say "not measured". |
| M14 | Benchmark script for Lane S | `language/bench.py` | One command prints tokens per second, time to first output and whisper real-time factor for the same model file, same prompt and 10 commands (3 runs, first run thrown away). Lane S runs it on his machine for the second hardware row. |
| M15 | Regression script, dry-run half | `tools/regression.py` | About 25 typed commands through the pipeline in dry-run mode, each with the expected gate result. Prints pass or fail per case. |

## 5. Lane S tasks (WSL2, simulator)

Needs nothing from Lane M. Test with JSON commands from `data/seeds.jsonl`. Lane M's pieces that Lane S uses (`config.json`, `geo.py`, `places.json`, `mission_state.py`) are small. If one is not on main yet, use a local stub and swap it in when it lands.

| # | Task | Files | Done when |
|---|---|---|---|
| S1 | Close the gate gaps | `flight/safety.py`, `flight/test_safety.py` | See `docs/contracts.md` section 3, items 1 to 5. Missing home or position refuses flight commands. A `loiter` with an unknown `event_id` is refused. Limits come from `config.json`. `link_ok` added. Tests added for each. |
| S2 | Wire the gate in | `integration/run_command.py` (small PR) | `run_command.py` uses `SafetyGate` instead of its test limits. Dry-run still works. |
| S3 | Real backend | `flight/backend_px4.py` | Implements `FlightBackend` for `goto`, `move`, `climb`, `descend`, `hold`, `return_home`. Position stream at 2 Hz or better, log committed. Home is read from the sim. |
| S4 | Search and loiter | `flight/backend_px4.py` | `search_area` flies a lawnmower sweep (spacing from config). `loiter` circles for `duration_s` then holds. Each run once in SITL, log committed. The backend only ever receives lat/lon (never `place` or `event_id`). |
| S5 | Event emitter | `flight/emitter.py`, `flight/scenarios/demo.json`, a second layout | Unit tests on a made-up track: each find fires once, the same seed gives the same events. In SITL the sweep fires all four events once each. |
| S6 | Places and the world | `docs/places-candidates.md` | Five more open-ground points verified by flying there, with north and east meters. Each one looked at in the Gazebo view and described in one line. `buildings` and `bridge` confirmed or renamed. A screenshot of each is saved. |
| S7 | Multi-step executor (after D2) | `flight/steps.py` | Runs a list of commands in order, gates each one with the state at that time, stops on a refusal, and pauses while `is_paused()` is true (a function Lane M passes in). Tests use fakes. Demo: "Go to the bridge, search for vehicles, then come home" runs 3 of 3 times. |
| S8 | Lost link | `flight/lost_link.py` | When the link drops, hold for `lost_link_hold_s`, then `return_home`. Unit tests with fake telemetry. Battery floor tested the same way. Demo in SITL 3 of 3 times, log committed. |
| S9 | Timing hooks | `flight/backend_px4.py` | Run log records the time of the first motion (position changed by more than 0.5 m) so voice timing can be computed. |
| S10 | Flight tests | `flight/flight_tests.py` | One command runs 20 or more runs per action and writes a CSV: final position error and any limit violations. Run it early to find bugs. Repeat after the freeze for the numbers that go in the write-up. |
| S11 | Regression, sim half | `tools/regression_sim.py` | About 10 commands through SITL, each with the expected final action. Prints pass or fail per case. |
| S12 | Hardware row | `docs/hardware.md` (his rows only) | Runs Lane M's `language/bench.py` on his machine. Writes device, RAM, model and quantization, tokens per second, time to first output. Power: "not measured" unless he has a wall meter. |
| S13 | Second machine | `flight/README.md` | The waypoint test runs on a second machine, or the README says only one machine was tested. |
| S14 | Recordings | `docs/videos/` (links or files) | Screen recordings of the main demo and three failure demos: unsafe command refused, low-confidence event asks first, lost link returns home. Made after the freeze. |

## 6. How the lanes connect (the only shared rules)

1. **The backend only receives lat/lon.** The pipeline (Lane M) resolves `place` through `integration/places.json` and `event_id` through the emitted events, then rewrites the command (for example `loiter` with `event_id` becomes `loiter` with `lat` and `lon`). The gate still sees the original place name and event id where it needs them, and checks them against its own lists.
2. **The gate checks a fresh snapshot.** `DroneState` is built from `MissionState` and the backend telemetry before every check.
3. **Event ids** come from the emitter. `MissionState` stores which ones were reported. The gate gets the list of known ids.

## 7. The four meeting points

These are the only times one lane needs the other's real code.

| Meeting | When | What happens | Who does it |
|---|---|---|---|
| I1 | After M6 and S3, S4, S5 are on main (target: Saturday night) | `main.py` runs on the real backend instead of the mock. One full demo run. | Both, in person or on a call |
| I2 | Same session as I1 | The model runs on your Mac and his machine sends text to it with `--llm http://<Mac IP>:8080`. Same demo again with typed input through the model. | Both |
| I3 | After M12 and S9 | Voice timing: end of speech to first motion, at least 20 runs. | Both |
| I4 | After all tasks above | Feature freeze and tag v0.8. Clean clone, `main.py` runs from the README. Then final numbers: M10 test set, S10 flight tests, precision and recall, voice error rate. | Both |

## 8. Order of work

| When | Lane M | Lane S |
|---|---|---|
| Thu night | Decisions D1 to D4. M1. | Decisions. S1 (the gaps found in review). |
| Fri | M2, M3, M4, M7 starts, M14 | S2, S3, S6 |
| Sat | M5, M6, M8, M7 finishes | S4, S5, S9 |
| Sat night | **I1 and I2** | **I1 and I2** |
| Sun | M9, M10, M11, M15 | S7, S8, S10, S11, S12 |
| Mon | M12, M13, then **I3** | S13, S14 starts, **I3** |
| Mon night | **I4** freeze and tag v0.8, then final numbers | **I4** |

If time runs short, cut in this order, last item first: voice in the loop (M12), multi-step (M9, S7), lost-link (S8), hardware table (M13 and S12), the 20-runs flight tests (S10), rule tuning from interviews, LoRA. Not cut: the safety gate, the ask-first loop, the honest limits.

## 9. Things the agents cannot speed up

- Interviews and operator feedback (show the demo to at least two people and write their answers in the template).
- Recording the 30 voice clips (noisy ones with real background noise).
- Having two outside people read the alert messages.
- Power measurements, which need a wall meter.

Put these on a human list and do them in the gaps while agents run.
