# i4NSTeamWilco

- Frozen schemas, now v1.2.0 (task 5.2; v1.1.0 added `move`, v1.2.0 added `climb` and `descend`, see the change log in `docs/schemas.md`): `integration/schemas.json` is the source of truth, `docs/schemas.md` explains it. `language/make_grammar.py` builds the grammar from it.
- Flight safety gate (task 6.1): `flight/safety.py` enforces schema validation, geofence (1500 m), altitude bounds (1..120 m), manual mode override, and minimum battery cutoff (20%); 22 unit tests pass in `flight/test_safety.py`.
