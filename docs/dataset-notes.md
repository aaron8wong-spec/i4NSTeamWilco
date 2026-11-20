# Dataset notes (task M7)

Written 2026-11-20 by Lane M. Numbers below were counted from `data/train.jsonl` and `data/test.jsonl` after running `python3 language/split_dataset.py data/dataset_batch3.jsonl`. All data is synthetic and written by us, so accuracy on it says little about real operators.

## Counts

| | rows |
|---|---|
| train | 212 |
| test (held out) | 49 |
| total | 261 |
| test share | 18.8% |
| clarify rows (total) | 75 (28.7%) |
| clarify rows in test | 14 of 49 (28.6%) |

Batch 3 (`data/dataset_batch3.jsonl`, ids D115 to D261) added 147 rows: 121 to train and 26 to test. The split is per tag with a seed made from the batch name and tag, so it is repeatable. The test share is a little under 20% because tags with fewer than 4 rows go to train and the earlier batches had been split already; the existing check in `language/test_dataset.py` (12% to 28%) passes.

Clarify reasons in the full set: see the tag counts in the files; every reason in the schema (missing_location, missing_altitude, ambiguous_reference, unsupported_action, unsafe_request, unclear_speech) has several rows in both train and test, except that `clarify-review` has only 1 row (the old "Engage the vehicle" row). No weapons or engagement rows were added.

Tag with fewer than 4 rows: `clarify-review` (1 row, in train). Every other tag has 4 or more rows, so each is split per tag and has at least one test row.

## What batch 3 covers

- Place rows use only the three real places (north_field, buildings, bridge): goto, search_area and loiter by place, with plain phrasing, spoken numbers ("fifty meters"), feet (rounded half up to whole meters), kilometers, and short noisy-ASR style text (lowercase, "uh", "um", no punctuation).
- Coordinate rows for goto and search_area (Baylands area).
- loiter by event id, move with a numeric bearing, climb, descend, hold, return_home, report_status.
- Clarify rows: missing altitude, missing location, ambiguous reference (including compass words such as "northeast" and "10 meters north", which the schema says must be clarify), unsafe (altitude above any limit, ignoring the geofence or battery, flying into things), unsupported (photo, follow, land, camera, figure eight, radio), unclear speech.
- No multi-step rows (schema v1.3.0 is not approved) and no "set absolute altitude" rows.

Judgement calls a human should look at: "Fly at 70 meters." is labeled missing_location, matching the older row "Fly at 40 meters." Compass-word moves are labeled ambiguous_reference with a bearing question, matching D086 and D087. Too-high altitudes are labeled unsafe_request, matching D089, even though the gate could also refuse them.

## Placeholder place names in older rows (not changed)

Seven placeholder names (plus the real `north_field`) appear in rows from batches 1 and 2. They are not in `integration/places.json`. Row counts by `expected.params.place`:

| placeholder | train | test | ids |
|---|---|---|---|
| water_tower | 3 | 0 | D014, D023, D040 |
| old_barn | 3 | 0 | D017, D025, D042 |
| south_bridge | 0 | 3 | D013, D021, D041 |
| east_ridge | 2 | 0 | D012, D020 |
| parking_lot | 2 | 0 | D015, D022 |
| tree_line | 1 | 1 | D016 / D024 |
| west_road | 1 | 1 | D026 / D018 |

That is 17 rows (12 train, 5 test). North_field is real and has 19 rows (14 train, 5 test). After batch 3, north_field has 19, bridge 18 and buildings 16 place rows.

Proposed mapping (NOT applied):

```
water_tower=buildings  old_barn=buildings  parking_lot=buildings
south_bridge=bridge    west_road=bridge
east_ridge=north_field tree_line=north_field
```

Applying it would edit 5 held-out rows, so it waits for decision D4 and for Lane S to verify 5 more places (then some names may map to real new places instead). To apply later, on a copy first:

```
python3 tools/remap_places.py data/train.jsonl water_tower=buildings ... --dry-run
```

After a remap, re-check for duplicate texts and re-run `python3 -m pytest -q tools language`. Do not tune the prompt toward the test rows after they are changed.

## Checks

- `tools/test_data_schema.py` validates every `expected` in `data/*.jsonl` against the Command schema and checks ids and texts are not reused.
- `language/test_dataset.py` also checks that numbers in expected values appear in the text after unit normalization (feet, km, minutes, number words).
- The 10% hand-check list is `data/hand_check.md`. It has NOT been hand-checked by anyone yet.
