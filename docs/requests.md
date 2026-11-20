# Requests between lanes

One line each: date, from lane, what, why. Do not wait for an answer. Use the fake and keep going.
- 2026-11-20, Lane M to both: MissionState.geofence is required in the schema but centered on home, which is unknown until the sim reports it. Until set_home() it holds a fake 0,0 center. Gate and pipeline must check home is not None. Fix needs a schema change (nullable geofence) and a vote.
- 2026-11-20, Lane M to Lane S: docs/places-candidates.md uses 111320 and 88419.9 m per degree. integration/geo.py uses WGS84 values at the home latitude (110985.4 and 88528.9). Please import integration/geo.py instead of using your own constants.
- 2026-11-20, Lane M to Lane S: D3 sets battery floor 25 in integration/config.json; flight/safety.py defaults to 20. Please read the limit from config.json (contracts section 3 item 3).
