# Hand-check list (10% sample)

Status: NOT hand-checked. Claude drew this sample; no human has verified any row yet. Tick a box only after a person has read the text and the expected command together.

How the sample was drawn: `random.Random(20261120).sample(train_rows, 26)` over `data/train.jsonl` (212 rows, includes the new batch 3 rows that went to train). Test rows are never sampled, so the held-out file is not read for checking or tuning. 26 is 10% of the 261-row set.

What to check for each row: (1) the text is something an operator could say; (2) the expected action is right; (3) every number in expected appears in the text, with feet and kilometers converted and rounded to whole meters; (4) place is a real place (north_field, buildings, bridge) or an old placeholder (see docs/dataset-notes.md); (5) for clarify rows the reason fits and the question is one short question. If a row is wrong, do not edit it silently: write the row id and the fix in the Notes column and tell Lane M.

| Done | id | tag | text | expected | Notes |
|---|---|---|---|---|---|
| [ ] | D030 | search-coords | Survey 37.4170 -122.0010 for anything, radius two hundred meters, at 60 meters. | `{"action":"search_area","params":{"lat":37.417,"lon":-122.001,"radius_m":200,"alt_m":60,"target":"any"}}` | |
| [ ] | D036 | loiter-event | Stay over E21 for a minute, 30 meter radius. | `{"action":"loiter","params":{"event_id":"E21","radius_m":30,"duration_s":60}}` | |
| [ ] | D042 | loiter-place | Stay around the old barn for twenty minutes, 40 meter radius. | `{"action":"loiter","params":{"place":"old_barn","radius_m":40,"duration_s":1200}}` | |
| [ ] | D045 | loiter-coords | Orbit 37.4182, -121.9928, radius 150 feet, for 6 minutes. | `{"action":"loiter","params":{"lat":37.4182,"lon":-121.9928,"radius_m":46,"duration_s":360}}` | |
| [ ] | D046 | loiter-coords | Loiter at 37.4165, -122.0005 for 8 minutes with a 55 meter radius. | `{"action":"loiter","params":{"lat":37.4165,"lon":-122.0005,"radius_m":55,"duration_s":480}}` | |
| [ ] | D053 | move | Go 100 meters at bearing 0 at 25 meters. | `{"action":"move","params":{"distance_m":100,"bearing_deg":0,"alt_m":25}}` | |
| [ ] | D069 | report-status | What has turned up since the last report? | `{"action":"report_status","params":{}}` | |
| [ ] | D070 | report-status | Read out what you have found. | `{"action":"report_status","params":{}}` | |
| [ ] | D095 | clarify-unsupported | Take a photo of the truck. | `{"action":"clarify","params":{"reason":"unsupported_action","question":"I can't take photos. Do you want me to search for it?"}}` | |
| [ ] | D097 | climb | Go up 200 feet. | `{"action":"climb","params":{"amount_m":61}}` | |
| [ ] | D100 | clarify-unclear-speech | [inaudible] north [static] meters. | `{"action":"clarify","params":{"reason":"unclear_speech","question":"I didn't catch that. Can you repeat it?"}}` | |
| [ ] | D107 | climb | Ascend 100 meters. | `{"action":"climb","params":{"amount_m":100}}` | |
| [ ] | D118 | goto-place | Head over to the bridge at 100 feet. | `{"action":"goto","params":{"place":"bridge","alt_m":30}}` | |
| [ ] | D122 | goto-place | Fly to the buildings at forty meters. | `{"action":"goto","params":{"place":"buildings","alt_m":40}}` | |
| [ ] | D133 | goto-place | Go on over to the bridge at 15 meters. | `{"action":"goto","params":{"place":"bridge","alt_m":15}}` | |
| [ ] | D136 | goto-place | Position the drone over the bridge at 65 meters. | `{"action":"goto","params":{"place":"bridge","alt_m":65}}` | |
| [ ] | D143 | search-place | Search the bridge for vehicles, 300 feet radius, 150 feet up. | `{"action":"search_area","params":{"place":"bridge","radius_m":91,"alt_m":46,"target":"vehicle"}}` | |
| [ ] | D150 | search-place | search the buildings for anyone radius 60 meters altitude 30 meters | `{"action":"search_area","params":{"place":"buildings","radius_m":60,"alt_m":30,"target":"person"}}` | |
| [ ] | D165 | goto-coords | Fly to 37.4135, -121.9990 at 55 meters. | `{"action":"goto","params":{"lat":37.4135,"lon":-121.999,"alt_m":55}}` | |
| [ ] | D175 | loiter-event | Stay on E11, 100 foot radius, for one minute. | `{"action":"loiter","params":{"event_id":"E11","radius_m":30,"duration_s":60}}` | |
| [ ] | D186 | move | Fly 150 meters at 0 degrees, altitude 30 meters. | `{"action":"move","params":{"distance_m":150,"bearing_deg":0,"alt_m":30}}` | |
| [ ] | D208 | return-home | Come back to the base. | `{"action":"return_home","params":{}}` | |
| [ ] | D226 | clarify-missing-altitude | uh go to the north field | `{"action":"clarify","params":{"reason":"missing_altitude","question":"How high should I fly?"}}` | |
| [ ] | D228 | clarify-missing-location | Loiter for 90 seconds, radius 30 meters. | `{"action":"clarify","params":{"reason":"missing_location","question":"Where should I loiter?"}}` | |
| [ ] | D233 | clarify-missing-location | Move at bearing 90 at 40 meters. | `{"action":"clarify","params":{"reason":"missing_location","question":"How far should I fly, in meters?"}}` | |
| [ ] | D259 | clarify-unclear-speech | [inaudible] [inaudible]. | `{"action":"clarify","params":{"reason":"unclear_speech","question":"I didn't catch that. Can you repeat it?"}}` | |
