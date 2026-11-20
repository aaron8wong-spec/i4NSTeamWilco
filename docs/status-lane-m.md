# Status: Lane M (Mac, model)

One line per finished task: date, task id, test result. Edit only this file for Lane M status.

- 2026-11-19 prep: integration/places.json created from Lane S's verified candidates (north_field, buildings, bridge). WGS84 degree lengths used. No tests yet.
- 2026-11-20 M1: integration/config.json (D3 limits) + geo.py. 7 tests pass. places.json matches the formula within 4 cm.
- 2026-11-20 M2: reporting/rules.json migrated to the Rule schema, docs/rules-migration.md lists what lost meaning. 17 tests pass (15 rules validate). Open: R01/R02, R05/R06/R07 etc. now tie, so the scorer needs a tie-break rule.
- 2026-11-20 M3: integration/mission_state.py. 10 tests pass, as_dict() validates after every setter. Note: geofence is required but centered on home, so it is lat/lon 0,0 before set_home().
- 2026-11-20 M4: integration/mock_flight.py + fake_events.py. 7 tests pass (10 m/s, 5 Hz, search sweep, loiter circle, events fire once and match the Event schema).
- 2026-11-20 rules round 2: 15 rules merged to 10, tie-break written in docs/rules-migration.md. 14 rule tests pass.
- 2026-11-20 M5: reporting/scorer.py, templates.py, data/labeled_events.json (30 events, 15 frozen), docs/scoring-spec.md. 31 reporting tests pass. Non-frozen 15 events: 12 of 15 match labels (interrupt P 1.00 R 0.83; ask P 0.50 R 1.00). Mismatches E08, E12, E21 listed in the spec. Frozen events not scored.
- 2026-11-20 M7: dataset 114 -> 261 rows (212 train, 49 test), clarify 28.7%. tools/remap_places.py (7 tests) and tools/test_data_schema.py. 10% hand-check list in data/hand_check.md is NOT yet checked by a human. 7 placeholder place names (17 rows) not remapped, waiting on D4.
- 2026-11-20 M14: language/bench.py, 8 tests pass. No real benchmark run yet (no server or whisper on this Mac).
- 2026-11-20 M13 (part): docs/targets.md, hardware.md, demo-script.md written. All targets are proposed. Mac row has no measured numbers.
- 2026-11-20 M8: data/followups*.jsonl (44 rows, 34 train, 10 held out), optional mission_state in the prompt (old prompt byte-identical), eval.py --set followups. 50 tests pass. Accuracy NOT measured (no server). "no" maps to clarify/ambiguous_reference, see docs/followup-notes.md.
- 2026-11-20 M6: integration/pipeline.py + main.py on MockFlight/FakeEvents with a fake model in tests. 16 new tests pass (demo end to end, runs twice identically, unknown place and manual mode never execute). Not yet run against a real llama-server. Bare demo line "Search the north field for vehicles" becomes a clarify because the guard needs radius and altitude in the text.
