# Follow-up replies (task 7.4, M8)

Data: `data/followups.jsonl` (44 rows), split into `data/followups_train.jsonl` (34) and `data/followups_test.jsonl` (10, held out). Each row has `id` (F001..), `tag`, `text`, a compact `mission_state` (MissionState schema) and the `expected` command. The split is about 20% per tag, seeded by tag name through `split_batch` in `language/split_dataset.py`. Rows never move after the split; add new rows as new ids and a new batch name.

Prompt: `run_llm.build_prompt(text, mission_state=None)`. With no state the prompt is byte-identical to before (checked by hash in `language/test_followups.py`). With a state, the system prompt gets a few follow-up rules and the user turn gets a "Mission context" block: pending question text, proposed command, target, search area, already reported ids.

Eval: `python3 language/eval.py --set followups --split train`. Reported separately from the single-command numbers (label `followups_train`). The test split needs `--final` and logs to `language/followups_test_runs.log`. The grounding guard is given the mission context too, so ids and numbers copied from the pending question are not mistaken for invented values. Numbers are not measured yet (no model server was running when this was written).

## Decisions (only the ten schema actions are legal outputs)

| Operator says | Output | Why |
|---|---|---|
| yes / ok / do it / affirmative / "loiter there" with a pending question | exactly `pending_question.proposed_command` | The model copies the command, code decides. |
| bare "no", "negative", "don't loiter", "no, keep searching" | `clarify` with `ambiguous_reference` | There is no "do nothing" action. A clarify is never flown, so the drone carries on, and code clears the pending question. Wording of the question is not scored. |
| "no, go back" / "go back" / "come home" | `return_home` | Explicit and expressible. |
| "yes" / "no" with no pending question | `clarify` `ambiguous_reference` | Nothing to agree to. |
| "higher" / "go lower" with no meters | `clarify` `missing_altitude` | climb and descend need amount_m. |
| "climb 30 more meters", "lower, 15 meters" | `climb` / `descend` | Stated amount. |
| a fresh command while a question is open | that command | The question is ignored; code clears it. |

Rejected: mapping "no, keep searching" to `search_area` with the area from mission_state (it would restart the sweep), `hold` (stops the search), and `report_status` (answers a different question).

Open proposal (needs a team vote, not done here): a no-op or `continue` action, so "no" does not need a clarify.
