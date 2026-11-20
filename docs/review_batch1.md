# Review list for dataset batch 1

You are checking the **answer key**, not the model. For each row, read what the operator says and decide
whether the expected answer is correct. Do not run the model on these. The model has not seen the test rows.

**How to reply:** send me the IDs that are wrong and what the answer should be, for example
`D036: duration should be 60`. If a whole section is fine, say so. Fix a label only because it is wrong,
never because the model disagreed.

Notes on the answers:
- Distances, heights and times are whole numbers in meters and seconds. Feet and minutes are already converted
  (for example 150 feet = 46 m, 2 minutes = 120 s).
- For `clarify`, only the `reason` is scored. The wording of `question` does not matter.
- `lat`/`lon` are in the Baylands world. Place names like `north_field` are resolved by code from the places table.

## A. Questions only you can answer (17 rows)

| ID | Type | What the operator says | Expected answer | OK? | Question |
|---|---|---|---|---|---|
| D014 | goto-place | Move to the water tower at 80 meters altitude. | `{"action": "goto", "params": {"place": "water_tower", "alt_m": 80}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D015 | goto-place | Fly to the parking lot at 150 feet. | `{"action": "goto", "params": {"place": "parking_lot", "alt_m": 46}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D016 | goto-place | Go to the tree line, fifty meters up. | `{"action": "goto", "params": {"place": "tree_line", "alt_m": 50}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D017 | goto-place | Head over to the old barn at 25 meters. | `{"action": "goto", "params": {"place": "old_barn", "alt_m": 25}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D018 | goto-place | Fly to the west road at 70 meters. | `{"action": "goto", "params": {"place": "west_road", "alt_m": 70}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D022 | search-place | Scan the parking lot for anything, 80 meter radius at 30 meters. | `{"action": "search_area", "params": {"place": "parking_lot", "radius_m": 80, "alt_m": 30, "target": "any"}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D023 | search-place | Search around the water tower for trucks, 120 meters radius, 55 meters high. | `{"action": "search_area", "params": {"place": "water_tower", "radius_m": 120, "alt_m": 55, "target": "vehicle"}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D024 | search-place | Find people near the tree line, radius 250 meters, at 70 meters. | `{"action": "search_area", "params": {"place": "tree_line", "radius_m": 250, "alt_m": 70, "target": "person"}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D025 | search-place | Search the old barn area for buildings, 60 meter radius, 35 meters altitude. | `{"action": "search_area", "params": {"place": "old_barn", "radius_m": 60, "alt_m": 35, "target": "structure"}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D026 | search-place | Sweep the west road for vehicles, 500 feet radius, 150 feet up. | `{"action": "search_area", "params": {"place": "west_road", "radius_m": 152, "alt_m": 46, "target": "vehicle"}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D040 | loiter-place | Circle the water tower for 150 seconds with a radius of 30 meters. | `{"action": "loiter", "params": {"place": "water_tower", "radius_m": 30, "duration_s": 150}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D042 | loiter-place | Stay around the old barn for twenty minutes, 40 meter radius. | `{"action": "loiter", "params": {"place": "old_barn", "radius_m": 40, "duration_s": 1200}}` |  | Place name is one I invented (not in the real places table yet). Fine for now? |
| D082 | clarify-missing-location | Go 250 meters, 60 meters up. | `{"action": "clarify", "params": {"reason": "missing_location", "question": "Which direction should I fly, in degrees?"}}` |  | No direction given. I labeled missing_location. OK? |
| D086 | clarify-ambiguous | Fly northwest 300 meters at 50 meters. | `{"action": "clarify", "params": {"reason": "ambiguous_reference", "question": "What bearing in degrees should I fly?"}}` |  | Compass word, no degrees. I labeled ambiguous_reference because the schema has no better reason. OK? |
| D087 | clarify-ambiguous | Go 400 meters due south at 60 meters. | `{"action": "clarify", "params": {"reason": "ambiguous_reference", "question": "What bearing in degrees should I fly?"}}` |  | Compass word, no degrees. Same label question. |
| D097 | clarify-unsupported | Go up 200 feet. | `{"action": "clarify", "params": {"reason": "unsupported_action", "question": "I can't make vertical-only moves. Give me a place and altitude."}}` |  | Vertical-only move is not in the schema. I labeled unsupported_action. OK? |
| D102 | clarify-review | Engage the vehicle. | `{"action": "clarify", "params": {"reason": "unsafe_request", "question": "I can't engage targets. Do you want me to loiter near it?"}}` |  | Which clarify reason: unsafe_request (my guess) or unsupported_action? CLAUDE.md puts weapons/engagement out of scope but names no reason. |

## B. Test rows: check all 21 (a wrong label here distorts the final score)

| ID | Type | What the operator says | Expected answer | OK? |
|---|---|---|---|---|
| D002 | goto-coords | Navigate to latitude 37.4105 longitude -121.9965, altitude 55 meters. | `{"action": "goto", "params": {"lat": 37.4105, "lon": -121.9965, "alt_m": 55}}` |  |
| D009 | goto-coords | Fly to 37.4125 -122.0015 at 45m. | `{"action": "goto", "params": {"lat": 37.4125, "lon": -122.0015, "alt_m": 45}}` |  |
| D013 | goto-place | Take the drone to the south bridge at 35 meters. | `{"action": "goto", "params": {"place": "south_bridge", "alt_m": 35}}` |  |
| D018 | goto-place | Fly to the west road at 70 meters. | `{"action": "goto", "params": {"place": "west_road", "alt_m": 70}}` |  |
| D021 | search-place | Check the south bridge for structures, radius 100 meters, altitude 40. | `{"action": "search_area", "params": {"place": "south_bridge", "radius_m": 100, "alt_m": 40, "target": "structure"}}` |  |
| D024 | search-place | Find people near the tree line, radius 250 meters, at 70 meters. | `{"action": "search_area", "params": {"place": "tree_line", "radius_m": 250, "alt_m": 70, "target": "person"}}` |  |
| D027 | search-coords | Search for vehicles around 37.4120, -122.0000 with a 100 meter radius at 50 meters. | `{"action": "search_area", "params": {"lat": 37.412, "lon": -122.0, "radius_m": 100, "alt_m": 50, "target": "vehicle"}}` |  |
| D033 | loiter-event | Loiter at E07, radius 40 meters, for 2 minutes. | `{"action": "loiter", "params": {"event_id": "E07", "radius_m": 40, "duration_s": 120}}` |  |
| D041 | loiter-place | Orbit the south bridge, radius 100 meters, for 15 minutes. | `{"action": "loiter", "params": {"place": "south_bridge", "radius_m": 100, "duration_s": 900}}` |  |
| D043 | loiter-coords | Loiter at 37.4138, -121.9975 for 3 minutes, radius 35 meters. | `{"action": "loiter", "params": {"lat": 37.4138, "lon": -121.9975, "radius_m": 35, "duration_s": 180}}` |  |
| D048 | move | Fly 750 m on bearing 180 at 60 m. | `{"action": "move", "params": {"distance_m": 750, "bearing_deg": 180, "alt_m": 60}}` |  |
| D049 | move | Go 200 meters heading 315 at 30 meters. | `{"action": "move", "params": {"distance_m": 200, "bearing_deg": 315, "alt_m": 30}}` |  |
| D063 | hold | Pause the mission and hover. | `{"action": "hold", "params": {}}` |  |
| D067 | return-home | Go back to where you took off. | `{"action": "return_home", "params": {}}` |  |
| D073 | report-status | Report status. | `{"action": "report_status", "params": {}}` |  |
| D077 | clarify-missing-altitude | Move 300 meters at 90 degrees. | `{"action": "clarify", "params": {"reason": "missing_altitude", "question": "How high should I fly?"}}` |  |
| D082 | clarify-missing-location | Go 250 meters, 60 meters up. | `{"action": "clarify", "params": {"reason": "missing_location", "question": "Which direction should I fly, in degrees?"}}` |  |
| D085 | clarify-ambiguous | Loiter over it for two minutes. | `{"action": "clarify", "params": {"reason": "ambiguous_reference", "question": "What should I loiter over?"}}` |  |
| D089 | clarify-unsafe | Go to the north field at 5000 feet. | `{"action": "clarify", "params": {"reason": "unsafe_request", "question": "That is too high. What altitude do you want?"}}` |  |
| D096 | clarify-unsupported | Follow me. | `{"action": "clarify", "params": {"reason": "unsupported_action", "question": "I can't follow you. Where should I go?"}}` |  |
| D101 | clarify-unclear-speech | Blah, to the, you know, whatever. | `{"action": "clarify", "params": {"reason": "unclear_speech", "question": "I didn't catch that. Can you repeat it?"}}` |  |

## C. Random training rows: check these 10

| ID | Type | What the operator says | Expected answer | OK? |
|---|---|---|---|---|
| D006 | goto-coords | Move to 37.4140, -122.0030 at 30 meters. | `{"action": "goto", "params": {"lat": 37.414, "lon": -122.003, "alt_m": 30}}` |  |
| D008 | goto-coords | Get over to 37.4177, -121.9950 at 200 feet. | `{"action": "goto", "params": {"lat": 37.4177, "lon": -121.995, "alt_m": 61}}` |  |
| D036 | loiter-event | Stay over E21 for a minute, 30 meter radius. | `{"action": "loiter", "params": {"event_id": "E21", "radius_m": 30, "duration_s": 60}}` |  |
| D044 | loiter-coords | Circle 37.4108 -122.0012 for 75 seconds, 20 meter radius. | `{"action": "loiter", "params": {"lat": 37.4108, "lon": -122.0012, "radius_m": 20, "duration_s": 75}}` |  |
| D057 | move | Go 900 meters at 359 degrees at 65 meters. | `{"action": "move", "params": {"distance_m": 900, "bearing_deg": 359, "alt_m": 65}}` |  |
| D060 | hold | Hover here. | `{"action": "hold", "params": {}}` |  |
| D065 | return-home | Return to launch. | `{"action": "return_home", "params": {}}` |  |
| D076 | clarify-missing-altitude | Go to 37.4150, -122.0020. | `{"action": "clarify", "params": {"reason": "missing_altitude", "question": "How high should I fly?"}}` |  |
| D079 | clarify-missing-location | Search for vehicles at 50 meters, 150 meter radius. | `{"action": "clarify", "params": {"reason": "missing_location", "question": "Where should I search?"}}` |  |
| D095 | clarify-unsupported | Take a photo of the truck. | `{"action": "clarify", "params": {"reason": "unsupported_action", "question": "I can't take photos. Do you want me to search for it?"}}` |  |
