#!/usr/bin/env python3
"""Full demo loop on the mock backend (Lane M, task M6): command in -> fly -> events -> score -> alert -> answer.

  python3 integration/main.py --script integration/demo_script.txt --time-scale 0 --llm http://127.0.0.1:8080
  python3 integration/main.py                      # type lines on stdin; "quit" ends

Script/stdin lines are operator text. Lines starting with "/" are directives:
  /manual, /ai   set the mode      @wait   wait until the drone finishes the current command
A "yes"/"no" line in a script waits until the scorer has asked a question.
Perception is simulated: events are scripted (fake_events.py), not detected.
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integration import pipeline  # noqa: E402
from integration.fake_events import FakeEvents  # noqa: E402
from integration.mission_state import MissionState  # noqa: E402
from integration.mock_flight import MockFlight  # noqa: E402
from reporting import scorer  # noqa: E402


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
              time_scale=0.0, dry_run=False, log=None, script=True):
    """Run the loop. `lines` is a list (script) or an async callable returning the next line or None.
    Returns the list of printed lines (deterministic for a given script, fake llm and time_scale 0)."""
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

    async def operator_line(text):
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
    a = ap.parse_args(argv)
    log = pipeline.RunLog(a.log) if a.log else pipeline.RunLog()
    print(f"[LOG] {log.path}")
    if a.script:
        lines, script = Path(a.script).read_text().splitlines(), True

    else:

        async def lines():
            return await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline) or None
        script = False
    asyncio.run(run(lines, llm_url=a.llm, time_scale=a.time_scale, dry_run=a.dry_run, log=log, script=script))
    return 0


if __name__ == "__main__":
    sys.exit(main())
