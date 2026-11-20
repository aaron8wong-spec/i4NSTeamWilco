# rules.json migration to the frozen Rule schema (task M2, decision D1)

What changed in every rule: `applies_to` became `event_type`; the text `condition` became an object; the file is wrapped as `{"rules": [...]}`. Ids, priority, action, reason, safety_relevant and min_confidence are unchanged.

Decision D1: the condition object may only use `people_visible_min`, `in_search_area`, `matches_target`. "At most N people" and confidence parts are dropped. `min_confidence` is the only confidence control (scorer step 4: high priority and confidence below `min_confidence` -> ask).

No rule used `in_search_area` or `matches_target` before, so none do now.

## Rules whose meaning is unchanged apart from confidence moving to min_confidence
- R04: `people_visible >= 3 and confidence >= 0.6` -> `{people_visible_min: 3}`, min_confidence 0.6 stays.
- R07: `people_visible >= 3 and confidence >= 0.3` -> `{people_visible_min: 3}`, min_confidence 0.3 stays.
- R10: `people_visible >= 1 and confidence >= 0.6` -> `{people_visible_min: 1}`, min_confidence 0.6 stays.
- R13: `people_visible >= 1 and confidence >= 0.3` -> `{people_visible_min: 1}`, min_confidence 0.3 stays.
- R15: `null` -> `{}` (always holds).

Small difference for R04, R07, R10, R13: before, an event below the confidence floor did not match the rule at all. Now it matches and the scorer turns it into `ask` (step 4). That is arguably better, but it is a behavior change.

## Rules that lost meaning

| Rule | Old condition | New condition | Effect on the scorer |
|---|---|---|---|
| R01 | `people_visible >= 1 and <= 2 and confidence >= 0.6` | `{people_visible_min: 1}` | Upper bound of 2 gone, so it also matches vehicles with 3+ people and overlaps R04 (both high, interrupt). Confidence floor stays via min_confidence 0.6. |
| R02 | `people_visible >= 1 and confidence < 0.6` | `{people_visible_min: 1}` | The "below 0.6" band is gone. It now matches every vehicle with people, at any confidence, so it always ties with R01 (both high). If the scorer picks R02 on a tie, high-confidence vehicles with people would become `ask` instead of `interrupt`. Largely redundant with step 4 applied to R01. |
| R03 | `people_visible == 0` | `{}` | Now matches vehicles with people too. Harmless in practice: R01/R02 are high and outrank this medium rule. Only wins for empty vehicles, as before. |
| R05 | `people_visible <= 2 and confidence >= 0.7` | `{}` | Upper bound gone, so it also matches groups of 3+ and overlaps R07. Confidence floor stays via min_confidence 0.7. |
| R06 | `people_visible <= 2 and 0.3 <= confidence < 0.7` | `{}` | Both the upper bound and the confidence band are gone. It now matches every person event and ties with R05 and R07 (all high). If it wins a tie, every person becomes `ask`, even a confident one. |
| R08 | `confidence < 0.3` | `{}` | Now matches every person event. It is low priority, so it never beats R05/R06/R07 (high). Effectively dead: very-low-confidence persons are handled by step 4 (ask) on the high rules, not logged. This differs from the old intent (log below 0.3). |
| R09 | `people_visible == 0` | `{}` | Now matches structures with people too. Outranked by R10/R11 (high), so no practical change. |
| R11 | `people_visible >= 1 and confidence < 0.6` | `{people_visible_min: 1}` | Same problem as R02: confidence band gone, always ties with R10 (both high). |
| R12 | `people_visible == 0 and confidence >= 0.3` | `{}` | Now also matches unknown objects with people, so it ties with R13 (both high, both safety_relevant). Old confidence floor of 0.3 is lost (min_confidence is 0.0), so a very low confidence unknown object now gets `ask` instead of being logged by R14. |
| R14 | `confidence < 0.3` | `{}` | Now matches every unknown event. Low priority, so it never beats R12/R13 (high). Effectively dead, same as R08. |

## Ties
Several rules can now match one event with the same priority:
- vehicle with people: R01, R02 (and R04 if 3+ people), all high.
- person: R05, R06, R08 (low, loses), and R07 if 3+ people.
- structure with people: R10, R11, plus R09 (medium, loses).
- unknown: R12 always; R13 if people; R14 (low, loses).

Their actions differ (interrupt vs ask) so which one wins changes the tier. This migration does not decide that. The tie-break rule belongs in R4's scoring spec (open question already listed in CLAUDE.md section 6). Until then, results from rules in the tables above are order-dependent.

## Round 2: merge confidence pairs (2026-11-20)

After D1 several rules tied. Fix: one rule per situation, and let scorer step 4 turn "high priority, confidence below `min_confidence`" into `ask`. So an interrupt rule and an ask rule that only differed by confidence are one rule now.

Removed: R02 (into R01), R06 (into R05), R11 (into R10), R08 and R14 (low-priority catch-alls that could never win). 10 rules remain. Ids are not renumbered, so old logs still make sense.

Tie-break (scorer must implement): take the highest priority. Among equal priority, take the rule with the most condition keys. Then the highest `min_confidence`. Then the lowest id. Example: a vehicle with 3 people matches R01 and R04. R04 wins (more specific, safety relevant).

Known change in behavior: a person or unknown object with very low confidence (below 0.3) used to be logged. Now it asks. Check this against the labeled events (M5) and the interviews before deciding if it is noise.

Demo check: deer -> R15 log. Empty truck -> R03 summarize. Truck with 2 people at 0.82 -> R01 interrupt. Unknown blob at 0.40, no people -> R12 ask.
