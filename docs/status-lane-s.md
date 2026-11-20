# Status: Lane S (WSL2, simulator)

One line per finished task: date, task id, test result. Edit only this file for Lane S status.

- 2026-11-19 S1 (partial): flight/safety.py and flight/test_safety.py written, 23 tests pass. Not yet on main. Gaps still open: see docs/contracts.md section 3.
- 2026-11-19 S6 (partial): three places flown to in SITL and verified (north_field, buildings, bridge). tools/baylands_map.py run on the Baylands model. Home matches the SDF origin. `buildings` and `bridge` are not yet checked by eye in Gazebo.
