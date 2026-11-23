# Targets (written before any test runs)

Status of every row: PROPOSED. Nothing here is agreed until the team says so in the group channel.
Owner of every number: the team. No number comes from the sponsor; the sponsor sheet gives no numeric targets.
Rule: we report the real number whether or not it meets the target. A missed target is a finding, not a reason to change the target afterwards.

## Targets table

| Area | Metric | How measured | Proposed target | Who decides | Status |
|---|---|---|---|---|---|
| Command accuracy | Action accuracy | `language/eval.py --split test --final`, once, at the end. Predicted `action` equals the expected `action`. | >= 90% | Team | proposed |
| Command accuracy | Parameter accuracy | Same run. Only rows where the action is right; every param equals the expected value. Scored separately from action. | Report only, no target | Team | proposed |
| Command accuracy | Exact match | Same run. Whole JSON equals the expected JSON. Report with and without `language/guard.py`. | Report only | Team | proposed |
| Command accuracy | Clarify rate on vague and unsafe rows | Same run. Of rows whose expected action is `clarify`, the share where the model also says `clarify`. Also report false clarifies on clear rows. | Report only (a missed clarify on an unsafe row is the costly error; list those rows by hand) | Team | proposed |
| LoRA decision | "Accuracy clearly low" threshold | Train-split action accuracy, after the prompt changes (M8, mission_state context) are in. Never use the test split for this decision. | If train-split action accuracy is below 85%, do the LoRA fine-tune. At or above 85%, do not. | Team | proposed, needs team agreement |
| Flight | Arrival error | 20+ runs per action (goto, search_area, loiter, hold, return_home) in PX4 SITL. Log final position and distance to target. | Within 5 m of target | Team | proposed |
| Flight | Safety-limit violations | Same runs. Count any run that leaves the geofence, exceeds max altitude or drops below min altitude. | Zero over all runs | Team | proposed |
| Safety gate | Unsafe commands refused | `tools/regression.py` dry-run cases, each with an expected gate result. | All expected refusals refused; reason text present | Team | proposed |
| Reporting | Interrupt recall | Labeled events (`data/labeled_events.json`). Of events labeled interrupt, the share the scorer interrupts. Report the 15 non-frozen events and the 15 frozen events separately. | >= 0.9 | Team | proposed |
| Reporting | Interrupt precision | Same set. Of events the scorer interrupts, the share labeled interrupt. | >= 0.7 | Team | proposed |
| Reporting | Alerts per 10-minute mission | Count interrupt plus ask messages in a full mission log (JSONL run log) divided by mission minutes, scaled to 10. Fewer is better only if recall holds. | Report only | Team | proposed |
| Voice | Word error rate, quiet clips | 30 clips (10 noisy) with reference text, whisper.cpp model size written next to the number. | Report only | Team | proposed |
| Voice | Word error rate, noisy clips | Same. Write down the noise source. | Report only | Team | proposed |
| Latency | End of speech to first drone motion | 20 runs, typed-to-motion and voice-to-motion reported separately. Report median and p95. State the hardware. | No target set yet | Team | proposed |
| Failure demos | Three demos recorded | Screen recordings in `docs/videos/` (S14): unsafe command refused, low-confidence event asks first, lost link returns home. | All three recorded | Team | proposed |

## Notes on the numbers

- The 90% action target and 85% LoRA threshold are ours. 85% sits below 90% on purpose: the LoRA question is about the train split before final tuning, and the 90% is the final held-out goal.
- Held-out set size: CLAUDE.md says 50 rows is the test minimum. The set has 49 rows (checked 2026-11-23), so a percentage on it moves by about 2 points per row. State the row count with every accuracy number.
- Latency has no target because we have no measurement yet. Set one only after the first 20-run measurement, and say it was set afterwards.
- Hardware numbers (tokens per second, time to first output, whisper real-time factor, power) are in `docs/hardware.md`, not here. They have no target; they are a table.

## Honest limits (state in every presentation)

- Perception is simulated. Events are scripted and fired when the drone is within about 60 m of a planted find. Nothing is detected by vision.
- Results are from a simulator (PX4 SITL + Gazebo), not real flights.
- Accuracy numbers come from our own synthetic command data, written by the team. They do not predict accuracy on real operators.
- Voice numbers come from our own recordings, not from field audio. We make no field claim.
- Latency was measured on student laptops and is not a statement about edge hardware.
- Each number is from one run or a small number of runs unless the table says otherwise.
- No jamming tests, no real hardware, no power measurement unless a wall meter was used (see `docs/hardware.md`).

## Where we stand against the proposals (train split only, 2026-11-23)

The test set has not been scored. These are train-split numbers from one run (`language/eval_results/train_20261123-015607.json`), so they do not say whether a held-out target is met. Thresholds are not changed here.

- **LoRA threshold (85% action accuracy on the train split):** not met. Action accuracy is 74.5% for the model alone and 77.8% after the guard. By the rule above, this says to do the LoRA fine-tune. LoRA is a stretch item and not done; this needs a team decision, and the week 8 feature freeze applies.
- **Action accuracy >= 90% (final, held-out):** train-split action accuracy is 77.8% after the guard, so a miss is likely unless something changes. Report the real number either way.
- **Unsafe commands refused (`tools/regression.py`):** 27 of 27 with the scripted model. With the real model 25 of 27; both misses were the model answering clarify instead of goto, so nothing flew.
- **Voice (quiet clips, `ggml-base.en`, one speaker):** word error rate 12.1% after number normalization (29.5% strict) on 20 clips. The noisy clips are synthetic (pink noise at 5 dB SNR): 10.0% on 10 clips, against 3.3% on the same 10 phrases quiet. Not field accuracy.
