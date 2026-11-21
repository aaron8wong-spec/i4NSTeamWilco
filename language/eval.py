#!/usr/bin/env python3
"""Score the command model (task 6.5). Needs llama-server running (see language/README.md).

  python3 language/eval.py                    # the training split (data/train.jsonl): use this while tuning
  python3 language/eval.py --split seeds      # the 57 seeds
  python3 language/eval.py --split test --final   # the held-out set: run ONCE, at the end
  python3 language/eval.py --set followups --split train   # follow-up replies with a mission_state (task 7.4)

Every row is run twice over: "model" is what the model said, "guarded" is what would reach the safety
gate after guard.py (units normalized first, values checked after). Report both side by side.

How each row is judged (the `question` wording of a clarify is never scored):
  exact           expected command and params match, or expected clarify with the same reason
  false_ask       a command was expected, the system asked a question instead (safe, annoying)
  wrong_reason    a clarify was expected and a clarify came back, with a different reason
  wrong_action    the wrong action came back (would fly unless it is a clarify)
  wrong_params    right action, wrong numbers or place (would fly)
  invented_command a clarify was expected and a command came back (would fly)
"would fly wrong" = wrong_action + wrong_params + invented_command: the errors that reach the gate.

The test split is the held-out exam. It prints totals only (no per-row failures), needs --final, and every
run is logged to language/test_runs.log. Do not change prompts or the guard in response to test results.

Measured on our own synthetic data, in a simulator project: say so wherever a number is quoted.
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPLITS = {"train": "train.jsonl", "test": "test.jsonl", "seeds": "seeds.jsonl"}
WOULD_FLY_WRONG = ("wrong_action", "wrong_params", "invented_command")


def is_clarify(cmd):
    return isinstance(cmd, dict) and cmd.get("action") == "clarify"


def outcome(exp, got):
    """Classify one prediction against the expected command. got is None for unparseable output."""
    if not isinstance(got, dict) or "action" not in got:
        return "invalid"
    if exp["action"] == "clarify":
        if is_clarify(got):
            return "exact" if got.get("params", {}).get("reason") == exp["params"]["reason"] else "wrong_reason"
        return "invented_command"
    if is_clarify(got):
        return "false_ask"
    if got["action"] != exp["action"]:
        return "wrong_action"
    return "exact" if got.get("params") == exp["params"] else "wrong_params"


def action_ok(exp, got):
    return isinstance(got, dict) and got.get("action") == exp["action"]


def _rate(num, den):
    return None if den == 0 else num / den


def summarize(rows, key):
    """rows: dicts with 'exp' and a prediction under `key` ('model' or 'guarded')."""
    n = len(rows)
    outs = [outcome(r["exp"], r[key]) for r in rows]
    counts = Counter(outs)
    cmd_rows = [(r, o) for r, o in zip(rows, outs) if r["exp"]["action"] != "clarify"]
    clar_rows = [(r, o) for r, o in zip(rows, outs) if r["exp"]["action"] == "clarify"]
    right_action_cmds = [(r, o) for r, o in cmd_rows if action_ok(r["exp"], r[key])]
    asked = [(r, o) for r, o in clar_rows if is_clarify(r[key])]
    swaps = sum(1 for r in rows if r["exp"]["action"] in ("climb", "descend")
                and isinstance(r[key], dict) and r[key].get("action") in ("climb", "descend")
                and r[key]["action"] != r["exp"]["action"])
    return {
        "n": n,
        "action_acc": _rate(sum(action_ok(r["exp"], r[key]) for r in rows), n),
        "param_acc": _rate(sum(o == "exact" for _, o in right_action_cmds), len(right_action_cmds)),
        "exact_acc": _rate(counts["exact"], n),
        "clarify_recall": _rate(len(asked), len(clar_rows)),
        "clarify_reason_acc": _rate(sum(o == "exact" for _, o in asked), len(asked)),
        "false_ask_rate": _rate(counts["false_ask"], len(cmd_rows)),
        "would_fly_wrong": sum(counts[o] for o in WOULD_FLY_WRONG),
        "climb_descend_swaps": swaps,
        "outcomes": dict(counts),
    }


def latency_stats(rows):
    xs = sorted(r["latency_s"] for r in rows)
    if not xs:
        return {}
    return {"median": xs[len(xs) // 2], "p90": xs[min(len(xs) - 1, int(0.9 * len(xs)))], "max": xs[-1]}


def by_tag(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["tag"]].append(r)
    return {t: {"n": len(g), "model_exact": sum(outcome(x["exp"], x["model"]) == "exact" for x in g),
                "guarded_exact": sum(outcome(x["exp"], x["guarded"]) == "exact" for x in g)}
            for t, g in sorted(groups.items())}


def load(split, dataset="commands"):
    """dataset "followups" reads data/followups_<split>.jsonl; each row also carries its mission_state."""
    path = ROOT / "data" / (f"followups_{split}.jsonl" if dataset == "followups" else SPLITS[split])
    items = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    return [{"id": i["id"], "tag": i.get("tag") or i["expected"]["action"], "text": i["text"], "exp": i["expected"],
             "mission_state": i.get("mission_state")} for i in items]


def predict(text, url, normalize=True, mission_state=None):
    """Return (model_cmd, guarded_cmd, guard_reason, latency_s). Commands are None if the output is not JSON."""
    from guard import check_grounding, normalize_units
    from run_llm import command_from_text, context_block
    seen = normalize_units(text) if normalize else text
    if mission_state is None:
        raw, latency = command_from_text(seen, url)
    else:
        raw, latency = command_from_text(seen, url, mission_state)
    try:
        model = json.loads(raw)
    except json.JSONDecodeError:
        return None, None, "", latency
    if mission_state is None:
        guarded, why = check_grounding(model, seen)
    else:
        # Values the model copies from the mission context (event id, area numbers) count as grounded.
        pq = mission_state.get("pending_question") or {}
        ids = [pq["event_id"]] if pq.get("event_id") else []
        guarded, why = check_grounding(model, seen + "\n" + context_block(mission_state), ids)
    return model, guarded, why or "", latency


def pct(x):
    return "  n/a" if x is None else f"{100 * x:5.1f}%"


def report(rows, split):
    n = len(rows)
    m, g = summarize(rows, "model"), summarize(rows, "guarded")
    lat = latency_stats(rows)
    print(f"\n{split}: {n} rows (our own synthetic commands; simulator project, no real flights)\n")
    print(f"{'':38}{'model':>9}{'guarded':>9}")
    for label, k in [("action accuracy", "action_acc"), ("parameter accuracy (right action)", "param_acc"),
                     ("exact (action + params, or clarify reason)", "exact_acc"),
                     ("clarify recall (asked when it should)", "clarify_recall"),
                     ("clarify reason accuracy (when asked)", "clarify_reason_acc"),
                     ("false-ask rate (asked, command expected)", "false_ask_rate")]:
        print(f"{label:38}{pct(m[k]):>9}{pct(g[k]):>9}")
    print(f"{'WOULD FLY WRONG (count)':38}{m['would_fly_wrong']:>9}{g['would_fly_wrong']:>9}")
    print(f"{'climb/descend direction swaps':38}{m['climb_descend_swaps']:>9}{g['climb_descend_swaps']:>9}")
    print(f"\noutcomes (guarded): {g['outcomes']}")
    if lat:
        print(f"latency per request (model only, wall clock): median {lat['median']:.2f}s, "
              f"p90 {lat['p90']:.2f}s, max {lat['max']:.2f}s")
    return m, g, lat


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=SPLITS, default="train")
    ap.add_argument("--set", dest="dataset", choices=["commands", "followups"], default="commands",
                    help="followups: replies to a pending question, with a mission_state (reported separately)")
    ap.add_argument("--final", action="store_true", help="required for --split test")
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--no-normalize", action="store_true", help="send the text to the model as typed")
    ap.add_argument("--limit", type=int, help="only the first N rows (quick check)")
    a = ap.parse_args()

    if a.split == "test" and not a.final:
        sys.exit("data/test.jsonl is the held-out set. Run it once, at the end, with --final. "
                 "Use --split train while you are tuning.")
    if a.dataset == "followups" and a.split == "seeds":
        sys.exit("followups has train and test splits only")
    rows = load(a.split, a.dataset)[: a.limit]
    label = a.split if a.dataset == "commands" else f"followups_{a.split}"
    sys.path.insert(0, str(HERE))
    for i, r in enumerate(rows, 1):
        r["model"], r["guarded"], r["guard_reason"], r["latency_s"] = predict(
            r["text"], a.url, not a.no_normalize, r["mission_state"])
        print(f"\r{i}/{len(rows)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    m, g, lat = report(rows, label)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "eval_results"
    out_dir.mkdir(exist_ok=True)
    summary = {"split": label, "time": stamp, "model_summary": m, "guarded_summary": g, "latency": lat,
               "normalize_input": not a.no_normalize}
    if a.split == "test":
        log_name = "test_runs.log" if a.dataset == "commands" else "followups_test_runs.log"
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        with (HERE / log_name).open("a") as f:
            f.write(json.dumps({"time": stamp, "commit": commit, "n": len(rows), "guarded": g, "model": m}) + "\n")
        print(f"\nheld-out run logged to language/{log_name}. No per-row output is shown or saved for the test set.")
    else:
        print("\nper type (exact: model / guarded):")
        for tag, v in by_tag(rows).items():
            print(f"  {tag:28} n={v['n']:3}  {v['model_exact']:3} / {v['guarded_exact']:3}")
        bad = [r for r in rows if outcome(r["exp"], r["guarded"]) != "exact"]
        print(f"\nnot exact after guard ({len(bad)}):")
        for r in bad:
            print(f"  {r['id']} [{outcome(r['exp'], r['guarded'])}] {r['text']}\n      expected {json.dumps(r['exp'])}"
                  f"\n      got      {json.dumps(r['guarded'])}")
        csv_path = out_dir / f"{label}_{stamp}.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "tag", "text", "expected", "model", "guarded", "guard_reason", "model_outcome",
                        "guarded_outcome", "latency_s"])
            for r in rows:
                w.writerow([r["id"], r["tag"], r["text"], json.dumps(r["exp"]), json.dumps(r["model"]),
                            json.dumps(r["guarded"]), r["guard_reason"], outcome(r["exp"], r["model"]),
                            outcome(r["exp"], r["guarded"]), round(r["latency_s"], 2)])
        print(f"\nper-row results: {csv_path}")
    (out_dir / f"{label}_{stamp}.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
