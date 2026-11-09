#!/usr/bin/env python3
"""Typed text -> JSON command, using llama-server with the GBNF grammar.

Start the server first (see language/README.md), then:
  python3 language/run_llm.py "Hold position."
  python3 language/run_llm.py --seeds        # task 5.5 check: all 40 seeds, valid-JSON rate
"""
import argparse
import csv
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

from make_grammar import SCHEMA_PATH, command_validator

HERE = Path(__file__).parent
ROOT = HERE.parent
GRAMMAR = (HERE / "command.gbnf").read_text()
VALIDATOR = command_validator(json.loads(SCHEMA_PATH.read_text()))

SYSTEM = """You turn an operator's typed request into exactly one JSON drone command.
Actions: goto, search_area, loiter, hold, return_home, report_status, clarify.
Units: whole meters and whole seconds (convert feet and minutes). Altitude is meters above home.
Location: use a snake_case place name (north_field) when the operator names a place, lat and lon
when they give coordinates, and for loiter an event_id (E03) when they name an event. Never mix them.
loiter has no altitude. search_area target is vehicle, person, structure or any.
report_status reads out what has been found so far.
Use clarify when the request is vague, is missing a location, altitude, radius, duration or
target, is outside these actions, or is unsafe. Never guess numbers or coordinates.
clarify reason is one of missing_location, missing_altitude, ambiguous_reference,
unsupported_action, unsafe_request, unclear_speech. Add one short question.
Examples:
Request: Land the plane at the airport.
{"action":"clarify","params":{"reason":"unsupported_action","question":"I can only fly the commands I know. Do you want me to return home?"}}
Request: Stay in the air.
{"action":"hold","params":{}}"""

# Llama 3.1 chat format. The server adds the BOS token itself.
TEMPLATE = (
    "<|start_header_id|>system<|end_header_id|>\n\n{system}<|eot_id|>"
    "<|start_header_id|>user<|end_header_id|>\n\nRequest: {text}<|eot_id|>"
    "<|start_header_id|>assistant<|end_header_id|>\n\n"
)


def command_from_text(text, url="http://127.0.0.1:8080"):
    """Return (raw_output, latency_s). The grammar forces valid JSON."""
    body = json.dumps({
        "prompt": TEMPLATE.format(system=SYSTEM, text=text),
        "grammar": GRAMMAR,
        "temperature": 0,
        "n_predict": 300,
        "cache_prompt": True,
    }).encode()
    req = urllib.request.Request(f"{url}/completion", body, {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)["content"]
    return out, time.perf_counter() - t0


def run_seeds(url):
    seeds = [json.loads(l) for l in (ROOT / "data" / "seeds.jsonl").read_text().splitlines()]
    rows = []
    for s in seeds:
        raw, dt = command_from_text(s["text"], url)
        try:
            cmd = json.loads(raw)
            valid = VALIDATOR.is_valid(cmd)
        except json.JSONDecodeError:
            cmd, valid = None, False
        rows.append({
            "id": s["id"], "valid": valid, "latency_s": round(dt, 2),
            "action_match": bool(cmd) and cmd.get("action") == s["expected"]["action"],
            "output": raw.strip(),
        })
        print(f"{s['id']} valid={valid} {dt:5.2f}s {raw.strip()[:90]}")
    out = HERE / "results_5_5.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    lat = [r["latency_s"] for r in rows]
    print(f"\nvalid JSON (schema-checked): {sum(r['valid'] for r in rows)}/{n}")
    print(f"action matches seed (informational, not the 6.5 eval): {sum(r['action_match'] for r in rows)}/{n}")
    print(f"latency s: median {statistics.median(lat):.2f}, max {max(lat):.2f}  (wall clock, incl. HTTP)")
    print(f"wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?")
    ap.add_argument("--seeds", action="store_true")
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    a = ap.parse_args()
    if a.seeds:
        run_seeds(a.url)
    elif a.text:
        print(command_from_text(a.text, a.url)[0])
    else:
        sys.exit("give a request or --seeds")
