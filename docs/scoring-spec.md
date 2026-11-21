# Scoring spec (scorer v0)

Code: `reporting/scorer.py`, `reporting/templates.py`. Tests: `reporting/test_scorer.py`. Labels: `data/labeled_events.json`.

## API

- `load_rules(path)` validates each rule against `Rule` in `integration/schemas.json` and raises `ValueError`.
- `score(event, state, rules, reported_events=None)` returns an `OperatorMessage`. `reported_events` is an optional list of `{type, lat, lon}` kept by the caller, used only for the near-duplicate check (MissionState holds ids only and has no positions).

## Order

1. Id in `already_reported` -> log (rule_id `R00`, text says "already reported").
2. Same type within 25 m of a reported event position -> log (`R00`). The new id is marked reported.
3. Match rules: `event_type` equals the type or `any`; every condition key holds. `people_visible_min`: event people >= value. `matches_target`: type equals `state.target` (target `any` or no target matches everything). `in_search_area`: within `area.radius_m` of the area center (false if no area).
4. No match -> log (`R00`).
5. Pick the rule: highest priority, then most condition keys, then the larger `people_visible_min`, then highest `min_confidence`, then lowest id.
6. Target set and type does not match the target and the rule is not `safety_relevant` -> log, with the rule id.
7. Priority high and confidence below `min_confidence` -> ask, and `state.set_pending(text, event_id, loiter proposal)` with radius 30 m, 120 s.
8. Confidence below `min_confidence` and priority not high -> log. (Decision for the gap named in CLAUDE.md section 6.)
9. Otherwise high -> the rule's action (`interrupt`, or `ask` for R12); medium -> summarize; low -> log.

Every event handled, except one already in `already_reported`, is passed to `state.mark_reported`. `expects_reply` is true only for ask. Text is at most 240 characters and always has `(rule Rxx: reason)`; ask text ends with a question. R12's reason already contains the question, so it is moved to the end.

## Choices to confirm

- Tie-break: R01 and R04 both have one condition key, so "most condition keys" does not make R04 win a 3-person vehicle. I added "larger `people_visible_min`" after the key count. `docs/rules-migration.md` should be updated to say this.
- Step 9 uses the rule's `action` for high priority (R12 is `ask` at any confidence). A high rule with confidence at or above its minimum and action `ask` therefore asks; one with action `interrupt` interrupts.
- `rule_id` for duplicates and no-match is `R00` because the schema requires an id.

## Labeled events

30 events, 15 frozen. Labels were written first, from what an operator under stress would want (`why` field), not from scorer output. The 15 frozen events were not scored or looked at when tuning. Extra field `state_hint.reported_events` (positions) is used only by the duplicate-by-position case.

Non-frozen result (scorer on the 15 non-frozen events, compared with the labels): 12 of 15 match. Mismatches, labels not changed:

| Event | Label | Scorer | Why they differ |
|---|---|---|---|
| E08 person 0.90, target vehicle | interrupt | log (R05) | Off-target and R05 is not safety relevant. Judgement says a lone person is worth hearing about. Possible fix: make R05 safety relevant, or keep it as a summarize. |
| E12 person 0.20, target any | log | ask (R05) | Round 2 change: high rule below `min_confidence` asks. A 0.20 detection is probably noise. Possible fix: a floor below which high rules log. |
| E21 unknown 0.20, target vehicle | log | ask (R12) | R12 `min_confidence` 0 asks at any confidence. Same noise-floor issue. |

Per tier on the non-frozen 15 (counts of tp / fp / fn): interrupt 5/0/1, summarize 1/0/0, log 4/1/2, ask 2/2/0. Precision and recall are over 15 events from one labeler on synthetic events, so treat them as a smoke check, not a result.
