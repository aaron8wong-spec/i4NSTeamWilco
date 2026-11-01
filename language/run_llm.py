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

import jsonschema

HERE = Path(__file__).parent
ROOT = HERE.parent
GRAMMAR = (HERE / "command.gbnf").read_text()
VALIDATOR = jsonschema.Draft202012Validator(json.loads((HERE / "schemas.json").read_text()))

SYSTEM = """You turn an operator's typed request into exactly one JSON drone command.
Actions: goto, search_area, loiter, hold, return_home, clarify.
Units: meters, seconds, WGS84 lat/lon. Altitude is meters above home.
Use clarify (with one short question) when the request is vague, is missing a
location, altitude, radius, duration or target, or is unsafe. Never guess numbers.
Examples:
Request: Land the plane at the airport.
{"action":"clarify","params":{"question":"I can only fly the commands I know. Do you want me to return home?"}}
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
