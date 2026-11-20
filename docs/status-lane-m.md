# Status: Lane M (Mac, model)

One line per finished task: date, task id, test result. Edit only this file for Lane M status.

- 2026-11-19 prep: integration/places.json created from Lane S's verified candidates (north_field, buildings, bridge). WGS84 degree lengths used. No tests yet.
- 2026-11-20 M1: integration/config.json (D3 limits) + geo.py. 7 tests pass. places.json matches the formula within 4 cm.
- 2026-11-20 M2: reporting/rules.json migrated to the Rule schema, docs/rules-migration.md lists what lost meaning. 17 tests pass (15 rules validate). Open: R01/R02, R05/R06/R07 etc. now tie, so the scorer needs a tie-break rule.
- 2026-11-20 M3: integration/mission_state.py. 10 tests pass, as_dict() validates after every setter. Note: geofence is required but centered on home, so it is lat/lon 0,0 before set_home().
- 2026-11-20 M4: integration/mock_flight.py + fake_events.py. 7 tests pass (10 m/s, 5 Hz, search sweep, loiter circle, events fire once and match the Event schema).
