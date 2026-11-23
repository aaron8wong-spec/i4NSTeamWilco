# Roadmap (draft, 2026-11-23)

This is what comes after the 10-week MVP. Nothing here is built. No item has a date or a number attached, because we have not measured anything that would support one. Every MVP result in this project comes from a simulator, our own scripted events and our own synthetic data (see "Honest limits" in `docs/targets.md`).

## What the MVP shows

One loop works end to end in simulation: spoken or typed text becomes one of ten fixed JSON commands, a plain-code safety gate checks it, and a simulated drone flies it. Scripted events come back and code decides which ones interrupt the operator, which are summarized, which are logged, and when to ask first. The language model only suggests. It never talks to the autopilot.

## Decisions that shape the roadmap

- **No multi-step commands in the MVP** (decided 2026-11-23). The schema stays at v1.2.0. Long tasks such as "go over the ridge and search for vehicles, then identify any people inside" are not supported yet.
- **Only three verified places** (decided 2026-11-23): `north_field`, `buildings`, `bridge`. Each was flown to in the simulator. None of them has been checked by eye in the Gazebo view yet.
- **A place name that is not in the table is refused**, not guessed. That is a safety choice, not a model failure.

## Next: make the MVP result stronger

These need no new hardware.

1. **Score the held-out test set once** (49 rows) and report action and parameter accuracy separately. On the train split the model alone gets 74.5% action accuracy and 77.8% after the guard, below our proposed 85% LoRA threshold and the 90% held-out goal. The open question is whether to fine-tune (LoRA) or change the prompt and model size. We have not tried a second model size yet.
2. **Fewer wrong confident commands.** After the guard, 11 of 212 train rows still produce a wrong command that would reach the gate. The gate catches many of them, but not all. Candidates: a stricter grounding check on distance and bearing, and more clarify examples.
3. **Real noise for voice.** The noisy clips are synthetic. Record real noisy clips and re-score.
4. **Voice to motion timing**, at least 20 runs, once the real flight backend is connected.
5. **Operator feedback.** Show the demo to operators and let their answers change the rules table. The rules and message wording have not been tested with any real operator.

## Later: the parts the sponsor sheet asks for that we did not build

| Item | Why it matters | What it needs |
|---|---|---|
| **Real perception** | Events are scripted, not detected. The sponsor's closed loop needs a local model that looks at imagery and reports terrain changes and anomalies. | A camera feed or recorded imagery, a lightweight vision model, a way to measure detection quality. |
| **Real drone hardware** | All flight results are from PX4 SITL and Gazebo. | A test aircraft, flight approvals, a bench test of the gate against real telemetry. |
| **Jamming and degraded comms** | The sponsor asks what the drone does when it loses contact mid-task. Lost-link (hold, then return home) is specified in the gate but is a stretch item and may not be demonstrated. | A comms model or a real link test, and operator input on how much autonomy they trust. |
| **Alternative low-power edge hardware** | The sponsor suggests evaluating chips other than Nvidia. We measured one laptop only (see `docs/hardware.md`), under memory pressure, with no power reading. | Several devices, the same model and prompts on each, and a wall power meter. |
| **Multi-step and compass-word commands** | Operators say "10 m north" and chain tasks. Both are outside the v1.2.0 schema. | A schema vote and version bump, a grammar rebuild, new data, and an executor that gates each step with the state at that time. |
| **More places** | Three places is a demo, not a map. | Places defined from a real map, each verified in the world it is used in. |
| **Spoken output** | The operator reads text on a screen now. Hands-free operation needs speech back. | A local text-to-speech model and a plan for noisy environments. |
| **Using the language model for wording** | Alert text is templated. A model could reword it. | Evidence from operators that the wording helps, and the rule that code, not the model, decides what to say. |

## Not planned

- Anything involving weapons or engagement.
- Cloud services. The system must run locally with no external network.
- ROS 2 or Micro-XRCE-DDS. MAVSDK is enough for the MVP.

## Open questions from the interviews

- What should the drone do when it loses contact mid-task?
- How much autonomy will operators trust for long tasks?
- What reporting helps an operator under stress, and what is noise?
- What latency and hardware budget does on-device speech and language processing allow?
- Voice adds failure modes (noise, stress, misrecognition). Our voice numbers come from one speaker and are not a field claim.
