"""Command pipeline (Lane M, task M6). contracts.md section 8.

text -> normalize units -> model with grammar -> grounding guard -> resolve place / event_id
     -> fresh DroneState -> flight.safety gate -> backend.execute

The model suggests, plain code decides. A refused, clarify or report_status command never
reaches the backend. Every stage is written to a JSONL run log (ts, stage, data).
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "language"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from flight.safety import DroneState, SafetyConfig, SafetyGate  # noqa: E402  (Lane S's gate, import only)
from guard import check_grounding, normalize_units  # noqa: E402

CONFIG_PATH = ROOT / "integration" / "config.json"
PLACES_PATH = ROOT / "integration" / "places.json"
RUNS_DIR = ROOT / "runs"

NO_EXECUTE = ("clarify", "report_status")  # valid commands that are not flight commands

_YES = {"yes", "yeah", "yep", "yup", "ok", "okay", "affirmative", "confirm", "confirmed", "roger"}
_NO = {"no", "nope", "negative", "cancel", "never", "mind"}
_FILLER = {"loiter", "there", "please", "it", "do", "that", "go", "ahead", "sir", "keep", "searching",
           "continue", "carry", "on", "thanks", "thank", "you", "the", "search"}


def load_config():
    return json.loads(CONFIG_PATH.read_text())


def load_places(path=PLACES_PATH):
    """name -> {"lat", "lon"} (the extra keys in places.json are dropped)."""
    raw = json.loads(Path(path).read_text())
    return {k: {"lat": v["lat"], "lon": v["lon"]} for k, v in raw.items()
            if isinstance(v, dict) and "lat" in v and "lon" in v}


class RunLog:
    """Append-only JSONL log: one {"ts", "stage", "data"} object per line."""

    def __init__(self, path=None):
        if path is None:
            RUNS_DIR.mkdir(exist_ok=True)
            path = RUNS_DIR / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{time.monotonic_ns() % 10**6:06d}.jsonl"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, stage, data):
        with self.path.open("a") as f:
            f.write(json.dumps({"ts": round(time.time(), 3), "stage": stage, "data": data}) + "\n")


_default_log = None


def _get_log(log):
    global _default_log
    if log is not None:
        return log
    if _default_log is None:
        _default_log = RunLog()
    return _default_log


def make_llm(llm_url):
    """Default model call: text -> command dict, through llama-server with the grammar."""
    def call(text):
        from run_llm import command_from_text
        raw, _latency = command_from_text(text, url=llm_url)
        return json.loads(raw)
    return call


def parse_reply(text):
    """'yes' / 'no' / None. Only short replies made of known words count; anything else
    (for example 'yes, fly to the bridge') goes to the model."""
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return None
    if words[0] in _YES and all(w in _YES | _FILLER for w in words):
        return "yes"
    if words[0] in _NO and all(w in _NO | _FILLER for w in words):
        return "no"
    if words[:2] == ["keep", "searching"] and all(w in _FILLER for w in words):
        return "no"
    return None


def build_drone_state(state, backend, places):
    """A FRESH DroneState from MissionState plus backend telemetry. Nothing is cached.

    Filled: mode, home (MissionState), places, position and altitude (backend.position() if the
    backend has it), battery (backend.battery_percent if it has it, else 100.0).
    Not fillable today (gaps vs contracts.md section 3): DroneState has no link_ok and no
    known_event_ids field, and the FlightBackend contract has no position() or battery getter.
    """
    ms = state.as_dict()
    ds = DroneState(mode=ms["mode"], places=places)
    if ms["home"]:
        ds.home_lat, ds.home_lon = ms["home"]["lat"], ms["home"]["lon"]
    pos = backend.position() if hasattr(backend, "position") else None
    if pos:
        ds.current_lat, ds.current_lon, ds.current_alt_m = pos["lat"], pos["lon"], pos["alt_m"]
    ds.battery_percent = float(getattr(backend, "battery_percent", 100.0))
    return ds


def _make_gate(config):
    return SafetyGate(SafetyConfig(
        max_alt_m=config["max_alt_m"], min_alt_m=config["min_alt_m"],
        geofence_radius_m=config["geofence_radius_m"], min_battery_percent=config["battery_floor_pct"]))


def _resolve_for_backend(cmd, places):
    """Copy of cmd with place turned into lat/lon (the backend only sees lat/lon)."""
    out = json.loads(json.dumps(cmd))
    p = out["params"]
    if "place" in p:
        loc = places[p.pop("place")]
        p["lat"], p["lon"] = loc["lat"], loc["lon"]
    return out


async def handle_text(text, state, backend, llm_url, dry_run=False, llm=None,
                      known_event_positions=None, log=None, config=None, places=None):
    """Run one operator line. Returns {"text", "command", "gate": [ok, reason], "result"}.

    llm: callable text -> command dict (tests pass a fake). Default calls llama-server at llm_url.
    known_event_positions: {"E03": (lat, lon)}, used to turn a loiter event_id into lat/lon.
    log: RunLog (default: a new file in runs/). config/places: default to the repo files.
    """
    log = _get_log(log)
    config = config or load_config()
    places = places if places is not None else load_places()
    known = known_event_positions if known_event_positions is not None else {}
    gate = _make_gate(config)
    log.write("input", {"text": text, "dry_run": dry_run})

    def done(cmd, ok, reason, result=None):
        log.write("result", {"command": cmd, "gate": [ok, reason], "result": result})
        return {"text": text, "command": cmd, "gate": [ok, reason], "result": result}

    # 1. A short yes/no answers the pending question; the model is not involved.
    # TODO(M8): pass pending_question to the model prompt so longer replies work too.
    pending = state.as_dict()["pending_question"]
    reply = parse_reply(text) if pending else None
    if reply == "no":
        state.clear_pending()
        log.write("pending", {"answer": "no", "event_id": pending["event_id"]})
        return done(None, True, "pending question declined", None)
    if reply == "yes":
        cmd = json.loads(json.dumps(pending["proposed_command"]))
        state.clear_pending()
        log.write("pending", {"answer": "yes", "event_id": pending["event_id"], "command": cmd})
    else:
        # 2. normalize units, model with grammar, grounding guard
        text2 = normalize_units(text)
        log.write("normalize", {"text": text2})
        if llm is not None:
            cmd = llm(text2)  # a fake in tests: called inline so runs stay deterministic
        else:
            cmd = await asyncio.to_thread(make_llm(llm_url), text2)  # the real server is slow; keep the sim loop alive
        log.write("llm", {"command": cmd})
        cmd, why = check_grounding(cmd, text2)
        log.write("guard", {"command": cmd, "changed_to_clarify": why})

    action, params = cmd.get("action"), cmd.get("params", {})

    # 3. event_id -> lat/lon (loiter). An unknown id is refused here (gate gap, contracts 3 item 2).
    if action == "loiter" and "event_id" in params:
        eid = params["event_id"]
        if eid not in known:
            return done(cmd, False, f"refused: event '{eid}' is not a known event")
        lat, lon = known[eid]
        params = {k: v for k, v in params.items() if k != "event_id"}
        params["lat"], params["lon"] = lat, lon
        cmd = {"action": "loiter", "params": params}
        log.write("resolve", {"event_id": eid, "lat": lat, "lon": lon})

    # 4. gate: fresh state, original place name (the gate refuses a name not in the table)
    ds = build_drone_state(state, backend, places)
    ok, reason = gate.check_command(cmd, ds)
    log.write("gate", {"ok": ok, "reason": reason, "command": cmd,
                       "state": {"mode": ds.mode, "home": [ds.home_lat, ds.home_lon],
                                 "pos": [ds.current_lat, ds.current_lon, ds.current_alt_m]}})
    if not ok:
        return done(cmd, False, reason)
    if action in NO_EXECUTE:
        return done(cmd, True, reason)
    if "place" in cmd["params"] and cmd["params"]["place"] not in places:
        return done(cmd, False, f"refused: place '{cmd['params']['place']}' is not in places table")
    if dry_run:
        return done(cmd, True, reason)

    # 5. execute (backend sees lat/lon only)
    backend_cmd = _resolve_for_backend(cmd, places)
    log.write("resolve", {"backend_command": backend_cmd})
    if action == "search_area":
        p = backend_cmd["params"]
        state.set_search(p["target"], p["lat"], p["lon"], p["radius_m"], p["alt_m"])
    result = await backend.execute(backend_cmd)
    log.write("execute", {"result": result})
    return done(cmd, True, reason, result)
