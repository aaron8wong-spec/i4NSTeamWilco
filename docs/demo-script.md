# Demo script

Everything here runs in the simulator with scripted events. Say that first. Typed input is the safe path; voice is the same pipeline with whisper.cpp in front.

Event positions and times come from `integration/fake_events.py` (mock) and the scenario file (real emitter). Alert wording comes from templates; exact text may differ slightly on the day. Check the real output before recording.

## Setup

- PX4 SITL + Gazebo (Baylands) running, or `MockFlight` for a dry run.
- `integration/main.py` started. Mission state: mode `ai`, no target, nothing reported.
- Screen shows: operator line, parsed JSON command, gate result, alerts.

## Main demo: search the north field

| Step | Operator says | System does and shows |
|---|---|---|
| 1 | "Search the north field for vehicles, radius 150 meters at 50 meters." | Command: `search_area`, place `north_field`, target `vehicle`, radius_m 150, alt_m 50. Gate passes. Drone takes off and flies the search pattern. mission_state target becomes `vehicle`. |
| 2 | (nothing) | E01, deer (wildlife, 0.90): scorer tier log. No message to the operator. |
| 3 | (nothing) | E02, truck, no people (vehicle, 0.85): tier summarize. Held until the operator asks. |
| 4 | (nothing) | E03, truck with 2 people (0.82): tier interrupt. Alert says why, for example "Vehicle with people visible (rule R01: vehicle with people is high priority)." |
| 5 | (nothing) | E04, low-confidence unknown object (0.40): tier ask. The question is stored as pending_question. The drone says something like "Unknown object, low confidence. Loiter there?" |
| 6 | "Yes, loiter." | The answer goes through the same command path with pending_question attached. Command: `loiter` with that event_id. Gate passes. Drone loiters. |
| 7 | "Report status." | Command: `report_status`. System reads out the summarize list (E02, the truck). |
| 8 | "Return home." | Command: `return_home`. Drone returns. |

Note on step 1 (decided 2026-11-22): CLAUDE.md section 3 shows the operator line without a radius or altitude. The rules say do not guess a value, and the grounding guard turns an invented radius or altitude into a clarify, so the bare line correctly asks a question. The demo uses the full line above (same as `integration/demo_script.txt`) and keeps it fixed. The bare line is shown separately as a clarify example: the system asks "How high should I fly?" and the operator answers. Section 3 of CLAUDE.md should say the same.

Note on steps 4 and 5: CLAUDE.md section 3 describes the ask-first alert as the "truck with two people" ("Vehicle with two people at the east edge. Loiter?"). The rules table now interrupts for that event and asks for the low-confidence one. Show what the current scorer does, and fix whichever document is wrong.

## Failure demo 1: unsafe command refused

1. Operator: "Fly to 800 meters." (Or "Fly 3 kilometers north." which is beyond the geofence.)
2. Model returns valid JSON. The gate refuses: altitude above the limit (120 m) or outside the geofence (1500 m from home).
3. Screen shows the refusal and the reason. The drone does not move.
4. Say: the model suggests, plain code decides. The gate refuses, it does not fix the command.

## Failure demo 2: low-confidence event asks first

1. Mission running as in the main demo.
2. E04 fires (confidence 0.40, unknown type).
3. The scorer does not interrupt and does not log it. It asks "Loiter?" and waits.
4. Operator: "No, keep searching." The drone continues. (Or "Yes, loiter" as in the main demo.)
5. Say: a weak detection costs the operator one short question, not a wrong action.

## Failure demo 3: lost link returns home

1. Mission running.
2. Cut the link in the sim (the method is set by Lane S in task S8).
3. Expected: the drone holds, then after the hold time (10 s in `integration/config.json`) returns home. Only `hold` and `return_home` are allowed while the link is down.
4. Say: this is simulated link loss only. No jamming was tested.

## Honest limits (say these out loud)

- Perception is simulated. The drone does not see anything. Events are scripted and fire when the drone is about 60 m from a planted find.
- Everything ran in a simulator, not on a real drone.
- Accuracy numbers come from our own synthetic commands.
- Voice was tested on our own recordings. No field claim.
- Latency was measured on student laptops.

## Two-minute talk track

0:00 "An operator carrying a full combat load cannot fly a controller and watch their surroundings. Our idea: tell the drone what to do, and it only interrupts you when it matters."

0:15 "Two parts. First, voice to safe flight. Your words become one of ten fixed JSON commands. A language model running locally makes the suggestion, but plain code checks every command before the drone moves. The model never talks to the autopilot."

0:35 [Run the main demo, steps 1 to 4.] "I said search the north field for vehicles. The drone flies the pattern. A deer is logged and I hear nothing. A truck is summarized for later. A truck with two people interrupts me, and it tells me why."

1:05 [Step 5 and 6.] "A low-confidence object makes the drone ask first. I say yes, and my answer goes through the same command path. It loiters."

1:25 [Show the refusal.] "If I ask for something unsafe, the gate refuses and shows the reason. If the link drops, the drone holds and returns home."

1:40 "Honest limits: perception is simulated, everything ran in a simulator, and our accuracy numbers come from our own synthetic data. Next steps are real camera perception, real hardware, jamming tests and low-power chips."

1:55 "Tell the drone what to do, and it only interrupts you when it matters."
