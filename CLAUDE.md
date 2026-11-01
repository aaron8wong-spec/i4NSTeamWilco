i4NS Army-737 "Say Less, Fly More": Team Context for AI Assistants
Last updated: week 5 (2026-10-29). Paste this whole document into your AI tool, then tell it: "I am role R_ (name the role). My current task is _." The AI should then work from this document and ask before breaking any rule in section 9.

0. Instructions to the AI assistant reading this
You are helping one member of a five-person university team build a 10-week MVP of a sponsor challenge. Use this document as the source of truth.
Be direct. If a request conflicts with the scope, schemas or rules below, say so before writing code.
Do not add features, actions or dependencies that are not listed here. If something seems missing, propose it and ask.
Do not change the schemas in section 5 on your own. Schema changes need a team vote. If the user's task needs a change, say that and draft the proposal instead.
Prefer small, testable Python functions with unit tests. Every deliverable needs a test or a logged number.
Package versions and install steps change. Check commands against the official docs for PX4, Gazebo, MAVSDK, llama.cpp and whisper.cpp instead of trusting memory, and say when you are unsure.
When you make a claim about accuracy, speed or safety, say how it was measured. Do not invent numbers.
Write in plain, simple technical English.

1. The challenge (from the sponsor sheet)
Title: Army-737 "Say Less, Fly More." Run through DIU's Innovation with Academia (IWA). Sponsor: U.S. Army.
Problem: Dismounted drone operators need to manage unmanned systems with intent-based natural-language control, because manual interfaces cause extreme cognitive overload during combat operations.
Key points from the sheet:
Operators already carry a full combat load, and a control interface full of buttons and knobs is not sustainable.
Current voice systems use rigid, scripted phrases. They break when conditions change.
An agentic AI should understand high-level intent: the operator describes what they need and the system works out how.
It must run locally, with no cloud and no external power, on low-power, portable edge hardware.
The edge hardware market is dominated by proprietary architectures (Nvidia). Finding alternative chips with lower power use is an open problem.
A closed-loop feedback mechanism is needed: the local model looks at imagery, tells the operator what it detects (terrain changes, anomalies), and takes follow-up natural-language commands without a mode switch.
Suggested starting point for an academic team: evaluate alternative edge hardware and tune a lightweight model for basic intent tracking, rather than attempting full system integration from the start.
Beneficiaries: airborne infantry squads, special operations teams, small-unit reconnaissance, robotic and autonomous systems program offices.
2. Our concept (in one paragraph)
Three parts: the drone, a local compute node, and the operator. The operator speaks a task, and the drone flies it and tells the operator only what matters. It works like a DJI Mavic: manual flight is always available, and AI mode is a separate switch. The AI narrates on request, not continuously. One request can imply a long multi-step task, for example: "Go over the ridge and search for vehicles; if you see some, identify the type and any people inside."
Open questions we are researching through interviews:
How does the system behave under jamming or degraded comms, and what should the drone do when it loses contact mid-task?
How much autonomy will operators trust for long tasks?
What reporting helps an operator under stress, and what is noise?
What latency and hardware budget does on-device speech and language processing allow?
Interview findings so far point to small on-device models, lower-power compute options, and the fact that voice adds failure modes (noise, stress, misrecognition).
3. The MVP we are building (weeks 5-9)
Two goals, one loop:
Deterministic flight from voice commands. The operator's words become a structured command, pass a safety gate, and move a simulated drone predictably.
Report only what matters. As the simulated drone flies, events come back. Code decides which ones to interrupt the operator about, which to summarize, which to log, and when to ask first.
What links them is the mission. A command like "search the north field for vehicles" sets a target in mission_state. That target drives both the flight (a search pattern) and the scoring (what counts as relevant). An alert can ask a question, and the operator's answer re-enters through the same command path.
One demo scenario (everything is built to serve this):
Operator: "Search the north field for vehicles."
Drone flies the search pattern in the simulator.
Scripted events appear at waypoints: a deer, a truck, a truck with two people, a low-confidence blob.
Scorer: deer → log; truck → summarize; truck with people → interrupt; low-confidence risky object → ask first.
Drone says: "Vehicle with two people at the east edge. Loiter?"
Operator: "Yes, loiter." The drone loiters.
Core design rule: the LLM suggests, deterministic code decides. The language model only turns text into one of a fixed set of JSON commands. A safety gate in plain code checks every command. The language model never talks to the autopilot directly.
Architecture:
COMMAND PATH:
  voice -> whisper.cpp -> text -> llama.cpp + GBNF grammar -> JSON command
        -> safety gate -> MAVSDK -> PX4 SITL + Gazebo -> drone moves

REPORT PATH:
  sim emits scripted events (with noisy confidence)
        -> rules lookup -> scorer -> tier (interrupt / summarize / log / ask)
        -> templated message -> operator (text on screen; speech is a stretch)

SHARED: schemas, mission_state, eval harness, hardware benchmarks

4. Scope: what we build, and what we do NOT build
In scope (must have):
Typed text -> JSON -> safe simulated flight, with the safety gate enforced.
Command dataset and measured accuracy on a held-out test set.
Scripted event feed, rules table and scorer, with measured precision and recall.
Ask-first loop.
Should have: live whisper.cpp voice input; one multi-step command; a hardware benchmark table.
Stretch: LoRA fine-tune (only if accuracy is clearly low); spoken output; lost-link demo polish; power measurements.
Out of scope. Plan only, in the roadmap: real camera perception, real drone hardware, jamming tests, alternative-chip deep dive, ROS 2 / Micro-XRCE-DDS, cloud services (Pinecone etc.), a vector database (ChromaDB is a stretch, not a requirement).
Honest limits we must state in every presentation:
Perception is simulated. Events are scripted, not detected by vision.
Results are from a simulator, not real flights.
Accuracy numbers come from our own synthetic data.
5. Schemas (DRAFT, to be frozen by end of week 5)
Units: meters, seconds, WGS84 lat/lon. Altitude is meters above home. Changes after the freeze need a team vote.
Command (the only things the language model may output):
{"action": "goto", "params": {"lat": 32.88, "lon": -117.24, "alt_m": 40}}
{"action": "search_area", "params": {"center": {"lat": 32.88, "lon": -117.24}, "radius_m": 150, "alt_m": 50, "target": "vehicle"}}
{"action": "loiter", "params": {"center": {"lat": 32.88, "lon": -117.24}, "radius_m": 30, "duration_s": 120, "alt_m": 40}}
{"action": "hold", "params": {}}
{"action": "return_home", "params": {}}
{"action": "clarify", "params": {"question": "How high should I fly?"}}

clarify is used for vague, impossible or unsafe requests. Multi-step commands (week 8) use {"steps": [ ...commands... ]}.
Event (what the simulated drone "sees"):
{"id": "E07", "type": "vehicle", "confidence": 0.82, "lat": 32.881, "lon": -117.239, "time_s": 135, "people_visible": 2}

type is one of vehicle, person, wildlife, structure, unknown.
mission_state (shared by both paths):
{
  "target": "vehicle",
  "area": {"center": {"lat": 32.88, "lon": -117.24}, "radius_m": 150},
  "geofence": {"max_alt_m": 120, "radius_m": 500},
  "already_reported": ["E03"],
  "pending_question": null,
  "mode": "ai"
}

Rule (in rules.json):
{"id": "R07", "applies_to": "vehicle", "condition": "people_visible >= 1", "priority": "high", "min_confidence": 0.6, "action": "interrupt", "reason": "A vehicle with people nearby is high priority."}

6. Scoring logic (version 0, plain code)
For each event, in this order:
If event.id is already in already_reported, or it is a near-duplicate of one, tier = log.
Find rules matching event.type (and the condition). Take the highest priority.
If the type does not match mission_state.target and the rule is not safety-relevant, tier = log.
If priority is high and event.confidence < rule.min_confidence, tier = ask, and set pending_question.
Otherwise: high priority -> interrupt; medium -> summarize; low -> log.
The message is a template that includes the rule's reason, so every alert can say why.
The LLM may be used later to reword messages. It does not make the decision.
7. Safety gate (every command must pass)
Geofence (stay inside the radius from home).
Maximum altitude.
Minimum battery to continue (below it, force return home).
Lost-link behavior: hold, then return home.
Manual override: if mode is manual, AI commands are ignored.
Anything outside the schema or outside limits is refused, not "fixed."
8. Roles, tasks and gates
Five roles. Owner names are filled in by the team: R1 ____, R2 ____, R3 ____, R4 ____, R5 ____.
Definition of done for every task: merged to main, has a test or a logged number, and has one line in the README.
R1: Flight (simulator, MAVSDK, safety gate)
ID
Task
Week
5.3
Linux environment, PX4 SITL + Gazebo (headless option too)
5
5.4
MAVSDK script: arm, take off, fly to a point, land
5
6.1
safety.py with unit tests
6
6.2
Implement the five actions, including a search_area sweep pattern
6
6.3
Waypoint callback that reports the drone's position
6
7.3
Event emitter: fire a scripted event when the drone is within a set distance, with confidence noise
7
8.3
Multi-step command and lost-link demo
8
9.1
Flight tests: 20+ runs per action, log final position and limit violations
9

R2: Language (command model, grammar, dataset, eval)
ID
Task
Week
5.5
llama.cpp with a 3-8B quantized model; GBNF grammar generated from schemas.json
5
5.6
40 seed commands with correct JSON, including 8 vague or unsafe ones that map to clarify
5
6.4
Expand to 200-300 commands, hand-check 10%, hold out 20% for testing
6
6.5
eval.py: action accuracy, parameter accuracy, clarify rate, latency
6
7.4
Add mission_state context to the prompt so replies like "yes, loiter there" become commands
7
8.4
Re-run eval; LoRA only if accuracy is clearly low (default: no)
8
9.2
Final accuracy numbers on the held-out set
9

R3: Voice and hardware
ID
Task
Week
5.7
Build whisper.cpp; transcribe 10 recorded clips
5
6.7
transcribe(wav) -> text, a push-to-talk recorder, and 30 test clips (10 noisy)
6
7.6
Voice loop stub: push-to-talk -> whisper -> text -> pipeline
7
7.7
Text output to the operator (spoken output is a stretch)
7
8.1
Voice in main.py; measure time from end of speech to drone motion
8
8.2
Hardware table: tokens/sec, time to first output, power if measurable (laptop CPU plus one more device)
8
9.4
Voice error rate on quiet and noisy clips
9

R4: Reporting (events, rules, scorer)
ID
Task
Week
5.8
15 rules in rules.json
5
6.8
15 labeled events (interrupt / summarize / ignore / ask) and a first scorer with tests
6
7.2
Final scorer: tiers, deduplication, ask-first, templates, rule text as the reason
7
8.5
Tune thresholds and rules using interview findings
8
9.3
Precision and recall on the labeled event set
9

R5: Integration and discovery
ID
Task
Week
5.1
Repo and folder structure
5
5.2
schemas.json and schemas.md; get them frozen
5
5.9
Book 3 interviews; log them
5
6.6
run_command.py: text -> model -> JSON -> safety gate -> flight
6
7.1
mission_state.py
7
7.5
main.py, the full loop (command in -> fly -> events -> score -> alert -> answer)
7
8.6
Demo script, slide drafts, roadmap draft
8
8.7
Feature freeze, tag v0.8
8
9.5
Record the demo and three failure demos (unsafe command refused, low-confidence ask, lost-link return)
9
9.6
Results, limits and roadmap write-up
9

Gates
End of week 5: the sim flies from a script, and the model outputs valid JSON for typed text. If the sim is not flying, escalate right away and consider ArduPilot SITL as a fallback.
End of week 6: a typed command moves the drone for all five actions, and there is a first accuracy number.
End of week 7: the full scenario runs end to end with typed input.
End of week 8: voice works in the loop. Feature freeze.
Week 9: testing and bug fixes only. P0 (breaks the demo) gets fixed, P1 gets fixed if time allows, everything else goes to the roadmap.
Week 10: buffer for write-up and submission.
9. Team rules
Schema changes need a team vote, posted in the group channel.
Never merge code that breaks run_command.py or main.py.
Any blocker lasting more than one day gets escalated, not worked around quietly.
Three short standups a week: done, blocked, next.
Do not add new actions, features or dependencies after the week 8 freeze.
Do not claim real-world perception, real flight results, or field-ready speech accuracy.
10. Tech stack
Layer
Tool
Notes
OS
Ubuntu (22.04 is the safest match for PX4)
A Mac VM can be slow; keep at least one Linux machine
Simulator
PX4 SITL + Gazebo
Run headless if graphics are slow
Flight link
MAVSDK-Python
takeoff, goto_location, return_to_launch. No ROS 2 needed
Language model
llama.cpp (or llama-cpp-python), 3-8B quantized (GGUF)
Output forced by a GBNF grammar
Speech to text
whisper.cpp
base or small model; test with noisy audio
Audio capture
Python sounddevice
Push-to-talk
Schemas
JSON Schema with pydantic or jsonschema
One source of truth: schemas.json
Rules and events
Plain JSON files and Python
ChromaDB only as a stretch
Tests and eval
pytest, pandas, CSV results
Every task logs a number or passes a test
Project
Python 3.10+, Git and GitHub issues



Suggested repo layout:
flight/        # sim launch, MAVSDK actions, safety.py, event emitter
language/      # llama.cpp wrapper, grammar, prompts, eval.py
voice/         # whisper.cpp wrapper, recorder, audio clips
reporting/     # rules.json, events, scorer, templates
integration/   # mission_state.py, run_command.py, main.py
data/          # seeds.jsonl, train.jsonl, test.jsonl, labeled_events.json
docs/          # schemas.md, results, hardware table, roadmap

11. Week 9 test targets (proposed, not yet agreed)
Test
Method
Proposed target
Command accuracy
Held-out set, action and parameters scored separately
About 90% on action; report the real number either way
Flight
20+ runs per action, final position checked
Within an agreed tolerance, with zero safety-limit violations
Reporting
Labeled events, precision and recall on the "interrupt" tier
High recall (a missed interrupt matters most)
Voice
Quiet and noisy clips
A measured error rate; make no field claims
Latency
End of speech to drone motion
Report what we measure
Failure demos
Unsafe command, low-confidence event, lost link
All three recorded

12. How to describe it to different audiences
Engineers / technical judges: grammar-constrained decoding gives valid JSON every time; a deterministic state machine gates every command; MAVSDK talks to PX4 SITL; rules are retrieved and scored in code; results are measured on held-out data.
Program officers / sponsor: an operator cannot fly a controller and watch their surroundings. They give one spoken task and the drone only interrupts when it matters. It runs offline. The roadmap covers real perception, real hardware, jamming tests and alternative low-power chips.
Operators / interviewees: show the scenario video and ask what they would want to be interrupted about. Their answers change the rules table.
One-sentence version: "Tell the drone what to do, and it only interrupts you when it matters."

