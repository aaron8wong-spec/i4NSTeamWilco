# Schemas

`schemas.json` is the contract between the five tracks. If a piece of code produces or consumes one of these shapes, it follows this file and does not invent its own field names.

| Schema | Produced by | Consumed by |
|---|---|---|
| `Command` | language model (R2) | safety gate and flight executor (R1), `run_command.py` (R5) |
| `Event` | scripted event emitter (R1, R4 scenarios) | scorer (R4) |
| `MissionState` | `mission_state.py` (R5) | safety gate, scorer, prompt builder |
| `Rule` / `RulesFile` | `rules.json` (R4) | scorer (R4) |
| `OperatorMessage` | scorer and message templates (R4) | operator output (R3, R5) |

Version: 1.0.0. Schemas are frozen. A change needs a team vote, then a version bump, then a re-run of `make_grammar.py`, an update of the seeds, and a re-run of the accuracy eval, because earlier numbers no longer apply.

## Conventions

- Units are metres, seconds and degrees (WGS84). Names carry the unit: `alt_m`, `radius_m`, `duration_s`, `time_s`.
- `alt_m` is altitude above the home point, not above sea level.
- Distances and times are whole numbers in commands. This lets the grammar enforce the ranges. The model converts feet and minutes to metres and seconds. That conversion is a known weak spot, so the eval should include feet and minutes phrasings.
- Locations in a command are given one of three ways, never mixed: a `place` name, a `lat`/`lon` pair, or (for `loiter` only) an `event_id`.
- The model should prefer `place` and use `lat`/`lon` only when the operator states coordinates. The first accuracy run showed the model inventing coordinates when none were given. When the operator gives no location for an action that needs one, the correct output is `clarify`.
- Ranges in the schema are outer bounds. The grammar only keeps the model inside them. The safety gate applies the real limits (geofence, maximum altitude, battery, lost link) from config and refuses with a reason. For example, `alt_m: 800` is valid JSON that the gate can refuse. Nothing in the schema is a safety limit.
- JSON key order is fixed as written in the tables (`action` before `params`). The generated grammar depends on it.
- Ids: events are `E03` style, rules are `R03` style.

## Command

A command is one JSON object: `{"action": "<name>", "params": {...}}`. Seven actions.

| Action | Params | Meaning |
|---|---|---|
| `goto` | location, `alt_m` | Fly to a point and stop there. |
| `search_area` | location, `radius_m`, `alt_m`, `target` | Sweep a circle for a target type. Sets `target` and `area` in mission state. |
| `loiter` | location, `radius_m`, `duration_s` | Circle a point, then hold. Altitude stays as it is. |
| `hold` | none | Stop and hold position. |
| `return_home` | none | Fly to the home point and land. |
| `report_status` | none | Read out what has been found since the last report (the summarize list). |
| `clarify` | `reason`, `question` | Ask the operator instead of acting. |

Location is `place` or `lat` + `lon`. For `loiter` it can also be `event_id`.

`target` is one of `vehicle`, `person`, `structure`, `any`.

`clarify.reason` is one of `missing_location`, `missing_altitude`, `ambiguous_reference`, `unsupported_action`, `unsafe_request`, `unclear_speech`. `question` is one short question, up to 160 characters.

Use `clarify` when the request is missing something an action needs, refers to something that cannot be resolved ("over there"), asks for something outside this list, or sounds unsafe. Do not guess a value.

Examples:

```json command
{"action": "search_area", "params": {"place": "north_field", "radius_m": 150, "alt_m": 50, "target": "vehicle"}}
```

```json command
{"action": "goto", "params": {"lat": 32.8812, "lon": -117.2371, "alt_m": 40}}
```

```json command
{"action": "loiter", "params": {"event_id": "E03", "radius_m": 30, "duration_s": 120}}
```

```json command
{"action": "hold", "params": {}}
```

```json command
{"action": "return_home", "params": {}}
```

```json command
{"action": "report_status", "params": {}}
```

```json command
{"action": "clarify", "params": {"reason": "missing_location", "question": "Which area should I search?"}}
```

### What the code does with a command

The language model only suggests a command. Plain code decides.

1. The grammar guarantees the output matches the schema. It does not guarantee the meaning is right. The accuracy eval measures that.
2. Code resolves `place` to coordinates from the places table. A name that is not in the table is refused with a reason. It is not treated as a model failure.
3. The safety gate checks the resolved command against the limits in config and either approves it or refuses it with a reason sent to the operator.
4. A `clarify` is never flown. It goes to the operator as a question.

### Not in the schema yet

These came up in interviews or in testing and are deliberately left out of the MVP. Adding any of them is a schema change.

- Relative moves such as "go up 200 feet" or "10 m north".
- "Follow me".
- Multi-step missions as a list of commands. One request maps to one command for now.
- Weapons or engagement of any kind. Positive identification and engagement stay with the human.

## Event

One simulated detection. Perception is simulated in the MVP: the emitter fires a planted event when the drone comes near it.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `E` plus 2 to 4 digits. |
| `type` | string | `vehicle`, `person`, `structure`, `wildlife`, `unknown`. |
| `confidence` | number | 0 to 1. |
| `lat`, `lon` | number | Degrees. |
| `time_s` | number | Seconds since the simulation started. |
| `people_visible` | integer | 0 to 99. |
| `subtype` | string, optional | Up to 32 characters, for example `truck`. |

```json event
{"id": "E03", "type": "vehicle", "confidence": 0.79, "lat": 32.8821, "lon": -117.2384, "time_s": 142.5, "people_visible": 2, "subtype": "truck"}
```

## MissionState

The one shared copy of mission memory. `mission_state.py` owns it. Other modules read it and do not keep their own copies.

| Field | Type | Notes |
|---|---|---|
| `target` | string or null | From the last `search_area`. |
| `area` | object or null | `lat`, `lon`, `radius_m`, `alt_m` after place resolution. |
| `geofence` | object | `lat`, `lon`, `radius_m`, `max_alt_m`. Values come from config. |
| `home` | object or null | `lat`, `lon`. Read from the sim, so null until it reports. |
| `already_reported` | array of event ids | Used for deduplication. |
| `pending_question` | object or null | `text`, `event_id`, `proposed_command`. Passed to the model so it knows what "yes" means. |
| `mode` | string | `manual` or `ai`. Manual flight is always available. |

```json mission_state
{
  "target": "vehicle",
  "area": {"lat": 32.8815, "lon": -117.2380, "radius_m": 150, "alt_m": 50},
  "geofence": {"lat": 32.8800, "lon": -117.2400, "radius_m": 500, "max_alt_m": 120},
  "home": {"lat": 32.8800, "lon": -117.2400},
  "already_reported": ["E01"],
  "pending_question": {
    "text": "Vehicle, 2 people nearby (rule R03: vehicle with people is high priority). Loiter there?",
    "event_id": "E03",
    "proposed_command": {"action": "loiter", "params": {"event_id": "E03", "radius_m": 30, "duration_s": 120}}
  },
  "mode": "ai"
}
```

The geofence values above are an example, not the project's limits.

## Rule and rules.json

`rules.json` is `{"rules": [ ... ]}`. Each rule says what to do with a kind of event.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `R` plus 2 or 3 digits. |
| `event_type` | string | An event type, or `any`. |
| `condition` | object | Optional keys: `people_visible_min` (integer), `in_search_area` (boolean), `matches_target` (boolean). All listed keys must hold. `{}` always holds. |
| `priority` | string | `high`, `medium`, `low`. |
| `min_confidence` | number | 0 to 1. Confidence needed for `action` to apply as written. |
| `action` | string | The tier: `interrupt`, `summarize`, `log`, `ask`. |
| `reason` | string | Plain-language reason, up to 200 characters. It is quoted in the operator message. |
| `safety_relevant` | boolean | True when missing the event could put people or the aircraft at risk. |

| Tier | What happens |
|---|---|
| `interrupt` | The operator is told now. |
| `summarize` | Held until the operator asks (`report_status`). |
| `log` | Recorded only. |
| `ask` | The operator gets a yes/no question first. `pending_question` is set. |

```json rule
{
  "id": "R03",
  "event_type": "vehicle",
  "condition": {"people_visible_min": 1},
  "priority": "high",
  "min_confidence": 0.6,
  "action": "interrupt",
  "reason": "vehicle with people is high priority",
  "safety_relevant": true
}
```

The scorer (R4) owns matching, tie-breaking and deduplication. This file only fixes the fields. Two behaviours still need to be written down in the scoring spec: what happens when an event matches a rule but falls below `min_confidence` (the `safety_relevant` field exists so a risky low-confidence event can go to `ask` instead of `log`), and which rule wins when several match.

## OperatorMessage

| Field | Type | Notes |
|---|---|---|
| `tier` | string | Same values as the rule tiers. |
| `event_id` | string | The event this message is about. |
| `rule_id` | string | The rule that produced it. |
| `text` | string | Up to 240 characters. Built from a template and includes the rule's `reason`. |
| `expects_reply` | boolean | True for `ask`. The text then ends with a yes/no question. |

```json message
{"tier": "ask", "event_id": "E03", "rule_id": "R03", "text": "Vehicle, 2 people nearby (rule R03: vehicle with people is high priority). Loiter there?", "expects_reply": true}
```

## Using the schema

- The grammar is generated from `$defs/Command`. Run `make_grammar.py` after any change to that definition.
- llama.cpp's schema-to-grammar converter handles `oneOf`, `const`, `enum`, integer ranges, `pattern` and string lengths. It ignores numeric bounds on non-integer numbers, so `lat`, `lon` and `confidence` ranges are enforced by validation, not by the grammar. Validate model output and every seed with a standard JSON Schema validator as well.
- `Place` only constrains the format. If you want the grammar to allow only known places, generate an enum from the places table at build time.
- Every `expected` value in `data/seeds.jsonl` must validate against `$defs/Command`.
- Validate `rules.json` against `$defs/RulesFile` in CI or at load time.

## Change log

### 1.0.0

Freezes the three items from task 5.2. Confirm the team vote result before tagging `schemas-v1`.

- Adds `report_status`.
- Lets the model output a `place` name. Code resolves it from the places table. `lat`/`lon` stays available.
- Adds `safety_relevant` to rules.

Also in this version, not previously written down:

- `loiter` accepts an `event_id`, so a yes to "Loiter there?" does not need coordinates.
- `clarify` carries a `reason` and a `question`.
- `OperatorMessage` and `RulesFile` are defined here.
- Event `type` includes `unknown`, and `subtype` is optional.
