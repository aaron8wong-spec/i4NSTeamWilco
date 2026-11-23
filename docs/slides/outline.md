# Slides draft (2026-11-23)

Draft only. Numbers marked (train) or (quiet clips) are from our own runs; see `docs/targets.md` and `docs/hardware.md` for how each was measured. Fill the final numbers after the feature freeze (the held-out test set is not scored yet). Do not add a number that is not in the repo.

## 1. Title
Army-737 "Say Less, Fly More". Tell the drone what to do, and it only interrupts you when it matters.

## 2. The problem
- Dismounted operators carry a full combat load. A controller full of buttons does not work.
- Today's voice systems use rigid scripted phrases and break when conditions change.
- Sponsor: U.S. Army, through DIU Innovation with Academia.

## 3. Our idea
- Operator speaks a task. The drone flies it and reports only what matters.
- Manual flight is always available. AI mode is a separate switch.
- Runs locally. No cloud.

## 4. Core design rule
- The language model suggests. Plain code decides.
- The model only turns text into one of ten fixed JSON commands (grammar-constrained, so the JSON is always valid).
- A safety gate in plain code checks every command: geofence, altitude, battery, manual override, known places.
- The model never talks to the autopilot.

## 5. Two paths (diagram)
- Command path: voice, whisper.cpp, text, llama.cpp with grammar, JSON, safety gate, MAVSDK, PX4 + Gazebo.
- Report path: scripted events, rules table, scorer, tier (interrupt / summarize / log / ask), templated message.
- The operator's answer to a question goes back through the command path.

## 6. Demo (see `docs/demo-script.md`)
- "Search the north field for vehicles, radius 150 meters at 50 meters."
- Deer: logged, silent. Truck: summarized. Truck with people: interrupts and says why. Unknown low-confidence object: asks first.
- "Yes, loiter." The drone loiters.

## 7. Three failure demos
- Unsafe command refused with a reason.
- Low-confidence event: the system asks before acting.
- Lost link: hold, then return home (stretch; show only if recorded).

## 8. Results so far (all from simulation and our own data)
- Command accuracy (train split, 212 rows, one run, after guard): action 77.8%, exact 68.4%. Held-out test not scored yet. Fill in after the freeze.
- Wrong commands that reach the gate (train, after guard): 11 of 212. The gate catches many, not all.
- Safety gate regression: 27 of 27 cases with the scripted model; 25 of 27 with the real model (both misses were the model asking instead of flying).
- Voice (whisper base.en, one speaker, quiet clips): 12.1% word error rate after number normalization (20 clips).
- Noisy voice: synthetic noise only so far. Not a field result.
- Reporting precision and recall: not yet scored on the frozen events. Fill in after the freeze.

## 9. Hardware
- One laptop measured (Apple M2, 16 GB, under memory pressure): 3.0 tokens/s end to end without prompt cache, 4.67 s to first token, whisper real-time factor 0.06.
- Median 2.1 s per command with the prompt cache on (eval run).
- Power: not measured. Alternative low-power chips: not evaluated. This is roadmap.

## 10. Honest limits (say these out loud)
- Perception is simulated. Events are scripted, not detected by vision.
- Results are from a simulator, not real flights.
- Accuracy numbers come from our own synthetic data and one speaker.
- No jamming tests, no real hardware.
- One small model (3B, 4-bit) on one laptop. We expect a larger model and better hardware to improve accuracy, but we have not tested it.

## 11. What we found
- A small on-device model is fast enough to try, but it sometimes answers confidently when it should ask. The gate and the guard exist because of that.
- Voice adds failure modes: "come down" was heard as "calm down" and "loiter" as "water".
- Plain-code decisions are what make the system testable.
- Accuracy is limited by a small model on modest hardware. A larger model on better hardware is the obvious next step (untested).

## 12. Roadmap (see `docs/roadmap.md`)
- Real perception, real hardware, jamming and lost-link tests, alternative low-power chips, multi-step commands, more places, spoken output.
- Operator feedback changes the rules table.

## Speaker notes
- Every claim about accuracy, speed or safety should name how it was measured. If asked for a number we do not have, say it was not measured.
- Do not say "tested with operators" until the demo has been shown to at least two. 
