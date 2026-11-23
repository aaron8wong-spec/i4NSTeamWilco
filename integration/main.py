#!/usr/bin/env python3
"""Full demo loop on the mock backend (Lane M, task M6): command in -> fly -> events -> score -> alert -> answer.

  python3 integration/main.py --script integration/demo_script.txt --time-scale 0 --llm http://127.0.0.1:8080
  python3 integration/main.py                      # type lines on stdin; "quit" ends

Script/stdin lines are operator text. Lines starting with "/" are directives:
  /manual, /ai   set the mode      @wait   wait until the drone finishes the current command
  @voice FILE.wav   transcribe a recording and run the text like a typed line (task M12)
With --voice the loop records from the microphone (Enter to talk, Enter to stop, q to quit).
A "yes"/"no" line in a script waits until the scorer has asked a question.
Perception is simulated: events are scripted (fake_events.py), not detected.
"""
import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integration import pipeline  # noqa: E402
from integration.fake_events import FakeEvents  # noqa: E402
from integration.mission_state import MissionState  # noqa: E402
from integration.mock_flight import MockFlight  # noqa: E402
from reporting import scorer  # noqa: E402


def is_garbled(text):
    """True when a transcript cannot be a command: empty, or no word of two or more letters.
    Anything else goes on to the model and the guard, which may still answer with a clarify."""
    return not any(len(w) >= 2 for w in re.findall(r"[A-Za-z]+", text))


class FlightSlot:
    """Wraps a backend. A new flight command supersedes the one still running (the operator
    redirects the drone). Delegates everything else, so the pipeline sees an ordinary backend."""

    def __init__(self, backend):
        self._b = backend
        self._current = None

    def __getattr__(self, name):
        return getattr(self._b, name)

    async def execute(self, cmd):
        if self._current is not None and not self._current.done():
            self._current.cancel()
            await asyncio.gather(self._current, return_exceptions=True)
        task = self._current = asyncio.ensure_future(self._b.execute(cmd))
        try:
            return await task
        except asyncio.CancelledError:
            if task.cancelled():
                return {"ok": False, "action": cmd.get("action"), "detail": "superseded by a newer command"}
            raise


async def run(lines, llm=None, llm_url="http://127.0.0.1:8080", backend=None, events=None, out=print,
              time_scale=0.0, dry_run=False, log=None, script=True, transcribe_fn=None):
    """Run the loop. `lines` is a list (script) or an async callable returning the next line or None.
    Returns the list of printed lines (deterministic for a given script, fake llm and time_scale 0).
    transcribe_fn: wav path -> text, used by "@voice FILE.wav" lines (default: voice/transcribe.py)."""
    printed = []

    def say(s):
        printed.append(s)
        out(s)

    log = log or pipeline.RunLog()
    config = pipeline.load_config()
    backend = backend or MockFlight(time_scale=time_scale, search_spacing_m=config["search_spacing_m"])
    home = await backend.connect()
    state = MissionState(config)
    state.set_home(home["lat"], home["lon"])
    log.write("home", home)
    events = events or FakeEvents(home["lat"], home["lon"])
    rules = scorer.load_rules(ROOT / "reporting" / "rules.json")
    slot = FlightSlot(backend)

    queue = asyncio.Queue()
    reported_events = []   # {"type","lat","lon"} of events already handled, for the near-duplicate check
    summarize = []         # texts waiting for report_status

    backend.subscribe_positions(lambda pos: [queue.put_nowait(e) for e in events.on_position(pos)])

    async def event_worker():
        while True:
            ev = await queue.get()
            try:
                log.write("event", ev)
                msg = scorer.score(ev, state, rules, reported_events)
                reported_events.append({"type": ev["type"], "lat": ev["lat"], "lon": ev["lon"]})
                log.write("score", msg)
                if msg["tier"] == "interrupt":
                    say(f"[ALERT] {msg['text']}")
                elif msg["tier"] == "ask":
                    say(f"[ASK] {msg['text']}")
                elif msg["tier"] == "summarize":
                    summarize.append(msg["text"])
                # log tier: run log only
            finally:
                queue.task_done()

    async def operator_line(text, echo=True):
        if echo:
            say(f"> {text}")
        r = await pipeline.handle_text(text, state, slot, llm_url, dry_run=dry_run, llm=llm,
                                       known_event_positions=events.positions, log=log)
        cmd, (ok, reason) = r["command"], r["gate"]
        if cmd is None:
            say(f"[OK] {reason}")
        elif not ok:
            say(f"[REFUSED] {reason}")
        elif cmd["action"] == "clarify":
            say(f"[CLARIFY] {cmd['params'].get('question', '')}")
        elif cmd["action"] == "report_status":
            if summarize:
                say("[STATUS] " + " | ".join(summarize))
                summarize.clear()
            else:
                say("[STATUS] nothing new since the last report")
        else:
            say(f"[CMD] {cmd['action']} {cmd['params']}" + ("" if r["result"] is None else f" -> {r['result']['detail']}"))

    transcribe_lock = asyncio.Lock()

    async def voice_line(wav):
        """Same path as a typed line: transcribe, show the transcript, then operator_line()."""
        nonlocal transcribe_fn
        if transcribe_fn is None:
            sys.path.insert(0, str(ROOT / "voice"))
            from transcribe import transcribe as transcribe_fn  # noqa: E402
        speech_end = time.time()
        try:
            async with transcribe_lock:  # transcripts come out in the order the lines were given
                text = await asyncio.to_thread(transcribe_fn, wav)
        except Exception as e:  # missing binary, bad file, timeout: say so, do not crash the loop
            log.write("voice", {"wav": str(wav), "error": str(e), "ignored": True})
            say(f"[HEARD] (could not transcribe: {e})")
            return
        text = text.strip()
        log.write("voice", {"wav": str(wav), "transcript": text, "speech_end_ts": round(speech_end, 3),
                            "transcribe_s": round(time.time() - speech_end, 3),
                            "ignored": is_garbled(text)})
        if is_garbled(text):
            say("[HEARD] (nothing understood, ignored)")
            return
        say(f"[HEARD] {text}")
        if script and pipeline.parse_reply(text):
            me = asyncio.current_task()  # this task is in `tasks` too; do not wait for ourselves
            while state.as_dict()["pending_question"] is None and any(not t.done() and t is not me for t in tasks):
                await asyncio.sleep(0)
        await operator_line(text, echo=False)

    worker = asyncio.ensure_future(event_worker())
    tasks = []

    async def wait_tasks():
        while any(not t.done() for t in tasks):
            await asyncio.sleep(0)

    async def next_line(it):
        if isinstance(lines, list):
            return next(it, None)
        return await lines()

    it = iter(lines) if isinstance(lines, list) else None
    while True:
        line = await next_line(it)
        if line is None or line.strip().lower() == "quit":
            break
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "@wait":
            await wait_tasks()
        elif line.startswith("@voice "):
            tasks.append(asyncio.ensure_future(voice_line(line[len("@voice "):].strip())))
            await asyncio.sleep(0)
        elif line in ("/manual", "/ai"):
            state.set_mode(line[1:])
            say(f"[MODE] {line[1:]}")
        else:
            if script and pipeline.parse_reply(line):
                # an answer: wait until the scorer has asked a question (or the drone is idle)
                while state.as_dict()["pending_question"] is None and any(not t.done() for t in tasks):
                    await asyncio.sleep(0)
            tasks.append(asyncio.ensure_future(operator_line(line)))
            await asyncio.sleep(0)
    await wait_tasks()
    await queue.join()
    worker.cancel()
    await asyncio.gather(worker, return_exceptions=True)
    await backend.close()
    return printed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", help="file of operator lines (default: read stdin)")
    ap.add_argument("--llm", default="http://127.0.0.1:8080", help="llama-server URL")
    ap.add_argument("--time-scale", type=float, default=1.0, help="1.0 real time, 0 no waiting")
    ap.add_argument("--dry-run", action="store_true", help="gate only, nothing flies")
    ap.add_argument("--log", help="run log path (default: runs/run-<time>.jsonl)")
    ap.add_argument("--voice", action="store_true", help="push-to-talk from the microphone instead of typing")
    a = ap.parse_args(argv)
    log = pipeline.RunLog(a.log) if a.log else pipeline.RunLog()
    print(f"[LOG] {log.path}")
    if a.script:
        lines, script = Path(a.script).read_text().splitlines(), True

    elif a.voice:
        sys.path.insert(0, str(ROOT / "voice"))
        import tempfile
        from record import record_push_to_talk
        tmp = Path(tempfile.mkdtemp(prefix="wilco-voice-"))
        count = [0]

        def record_one():
            ans = input("Enter = talk, q = quit: ").strip().lower()
            if ans == "q":
                return None
            count[0] += 1
            wav = tmp / f"say{count[0]:03d}.wav"
            started = [False]

            def input_fn(prompt):  # the first Enter was already pressed above
                if not started[0]:
                    started[0] = True
                    return ""
                return input(prompt)
            record_push_to_talk(wav, input_fn=input_fn)
            return f"@voice {wav}"

        async def lines():
            return await asyncio.get_running_loop().run_in_executor(None, record_one)
        script = False
    else:

        async def lines():
            return await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline) or None
        script = False
    asyncio.run(run(lines, llm_url=a.llm, time_scale=a.time_scale, dry_run=a.dry_run, log=log, script=script))
    return 0


if __name__ == "__main__":
    sys.exit(main())
