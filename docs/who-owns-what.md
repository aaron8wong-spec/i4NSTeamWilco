# Who owns what (two-person split, from 2026-11-19)

Superseded by `docs/work-plan.md`, which has the full task list, fakes and meeting points. Keep this file only as the short overview.

Lane M = Mac, has the model. Lane S = WSL2, has the simulator. Nothing is cut. The last column is a target, not a promise. Items that slip move down the list in the order shown at the bottom.

Status marks come from the repo on main as of 2026-11-19 (see section 13 of `CLAUDE.md`).

## Lane M

| ID | Task | Target |
|---|---|---|
| prep | `integration/config.json`, `integration/geo.py` with tests | Fri |
| prep | `integration/places.json` from `baylands.sdf` (needs the file from Lane S) | Fri |
| prep | Migrate `reporting/rules.json` to the frozen Rule schema, validate it | Fri |
| 7.1 | `mission_state.py` with tests | Fri |
| prep | `integration/mock_flight.py` | Fri |
| 6.8, 7.2 | `reporting/scorer.py` with tests, templates that cite the rule | Sat |
| 7.8 | 30 labeled events, 15 marked frozen | Sat |
| 7.7 | Operator message templates for four tiers | Sat |
| 6.6, 7.5 | `pipeline.py`, `main.py` (mock first, then real backend), JSONL run log | Sat to Sun |
| 6.4 | Dataset to 200-300 rows, clarify at 25% or more, real place names, hand-check 10% | Sat |
| 7.4 | Follow-up prompt with mission_state, about 40 examples, 20% held out | Sat |
| 6.5 | Re-run eval. Test set scored once, at the end, with `--split test --final` | Mon |
| 6.9 | `docs/targets.md` written before any test run | Fri |
| 6.7 | `transcribe()`, push-to-talk recorder, 30 clips with reference text | Sun |
| 7.6 | Voice loop into the same pipeline function | Sun to Mon |
| 8.1 | Voice timing by stage (needs Lane S's sim) | Mon |
| 8.2 | Hardware table: Mac CPU and GPU rows, plus a second device if one can be found | Mon |
| 8.4 | Steps grammar, about 30 multi-step rows, one other model size, LoRA decision | Mon |
| 8.5 | Rules tuned from interview findings (not on the frozen events) | Mon |
| 8.6 | Demo script, slides, roadmap | Mon |
| 8.8 | Dry-run regression script (about 25 commands) | Sun |
| 6.10, 7.9 | More interviews, show the demo recording to two people | ongoing, human time |
| 9.2, 9.3, 9.4, 9.6 | Final accuracy, precision and recall, voice error rate, write-up | after freeze |

## Lane S

| ID | Task | Target |
|---|---|---|
| 5.3 | Second machine or second documented run, versions in `flight/README.md` | Fri |
| 6.1 | `flight/safety.py` with tests, wired into `run_command.py` | Fri |
| prep | Send `baylands.sdf` to Lane M | tonight |
| prep | Remove the stray `nano flight/README.md` line | Fri |
| 6.2 | `search_area` sweep, `loiter`, real `hold` and `return_home` through `flight/backend_px4.py` | Sat |
| 6.3 | Position stream at 2 Hz or faster, log committed | Sat |
| 7.3 | `flight/emitter.py`, `scenarios/demo.json` and a second layout | Sat |
| 8.3 | Multi-step executor and lost-link demo (hold, then return home) | Sun to Mon |
| 8.8 | Simulator half of the regression suite (about 10 commands) | Mon |
| 8.1 | Help time the voice loop in the sim | Mon |
| 9.1 | 20 or more runs per action, final position and limit violations logged | after freeze |
| 9.5 | Screen recordings: main demo and three failure demos | after freeze |

## Shared

- Both agree before any schema change (`integration/schemas.json`), in writing.
- Tag v0.8 together after both lanes pass their tests.
- Check each other's work in person: run the demo from a clean clone.

## If time runs short, cut in this order (last item first)

1. Voice loop in `main.py`
2. Multi-step commands
3. Lost-link demo
4. Hardware table
5. 20-runs-per-action flight tests
6. Rule tuning from interviews
7. LoRA (stays off unless accuracy is clearly low)

Not cut, ever: the safety gate, the ask-first loop, the honest limits.
