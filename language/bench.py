#!/usr/bin/env python3
"""Hardware benchmark (task M14): tokens/s, time to first token, whisper real-time factor.

Needs llama-server running (see language/README.md). Example:
  python3 language/bench.py --llm http://127.0.0.1:8080 --whisper-model ~/whisper.cpp/models/ggml-base.en.bin
Prints a markdown row to paste into docs/hardware.md. A number that cannot be measured prints
"not measured (reason)"; nothing is estimated.
"""
import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
NOT = "not measured"


# ---- pure helpers (unit tested, no server) ----

def summarize(values, drop_first=True):
    """Median/min/max of runs, dropping the first (warm-up) run. None if nothing is left."""
    vals = list(values[1:] if drop_first else values)
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"median": statistics.median(vals), "min": min(vals), "max": max(vals), "n": len(vals)}


def tokens_per_second(n_tokens, seconds):
    if not n_tokens or not seconds or seconds <= 0:
        return None
    return n_tokens / seconds


def rtf(processing_s, audio_s):
    """Real-time factor: processing time / audio length. Below 1 is faster than real time."""
    if not processing_s or not audio_s or audio_s <= 0:
        return None
    return processing_s / audio_s


def fmt(stat, digits=2, unit=""):
    if stat is None:
        return NOT
    return f"{stat['median']:.{digits}f}{unit}"


def quant_from_name(name):
    """'Llama-3.2-3B-Instruct-Q4_K_M.gguf' -> 'Q4_K_M' (or None)."""
    import re
    m = re.search(r"(Q\d_[A-Z0-9_]+|Q\d_\d|F16|F32|BF16)", name or "", re.I)
    return m.group(1).upper() if m else None


def format_row(device, ram, model, quant, tps, ttft, rtf_stat, rtf_note=""):
    cells = [device, ram or NOT, model or NOT, quant or NOT,
             fmt(tps, 1), fmt(ttft, 2, " s"), fmt(rtf_stat, 2) + (f" ({rtf_note})" if rtf_stat is None and rtf_note else "")]
    return "| " + " | ".join(cells) + " |"


HEADER = ("| Device | RAM | Model | Quantization | Tokens/s | Time to first token | Whisper RTF |\n"
          "|---|---|---|---|---|---|---|")


def device_name():
    return f"{platform.node() or 'unknown'} ({platform.system()} {platform.machine()}, {platform.processor() or 'cpu n/a'})"


def ram_text():
    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            b = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        else:
            b = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))
        return f"{b / 2**30:.0f} GB"
    except Exception:
        return None


def wav_seconds(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


# ---- LLM measurement ----

def stream_completion(url, prompt, grammar):
    """Stream one /completion. Returns (ttft_s, total_s, n_tokens). n_tokens is the server's
    count when the last event has it, else the number of streamed chunks."""
    body = json.dumps({"prompt": prompt, "grammar": grammar, "temperature": 0, "n_predict": 300,
                       "cache_prompt": False, "stream": True}).encode()
    req = urllib.request.Request(f"{url}/completion", body, {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    ttft, chunks, server_n = None, 0, None
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            if ev.get("content") and ttft is None:
                ttft = time.perf_counter() - t0
            if ev.get("content"):
                chunks += 1
            if ev.get("stop"):
                server_n = ev.get("tokens_predicted")
    return ttft, time.perf_counter() - t0, server_n or chunks


def server_props(url):
    try:
        with urllib.request.urlopen(f"{url}/props", timeout=5) as r:
            return json.load(r)
    except Exception:
        return {}


def model_name_from_props(props):
    for key in ("model_path", "model_alias"):
        v = props.get(key) or (props.get("default_generation_settings", {}) or {}).get("model")
        if v:
            return Path(v).name
    return None


def bench_llm(url, n, runs):
    sys.path.insert(0, str(HERE))
    import run_llm  # same prompt and grammar as the real pipeline
    rows = [json.loads(l) for l in (ROOT / "data" / "seeds.jsonl").read_text().splitlines()][:n]
    ttfts, tpss, per_run = [], [], []
    for i in range(runs):
        t_tok, t_time, t_first = 0, 0.0, []
        for s in rows:
            prompt = run_llm.TEMPLATE.format(system=run_llm.SYSTEM, text=s["text"])
            ttft, total, ntok = stream_completion(url, prompt, run_llm.GRAMMAR)
            t_first.append(ttft)
            t_tok += ntok
            t_time += total
        ok = [x for x in t_first if x is not None]
        ttfts.append(statistics.median(ok) if ok else None)
        tpss.append(tokens_per_second(t_tok, t_time))
        per_run.append({"run": i + 1, "tokens": t_tok, "total_s": round(t_time, 3),
                        "tokens_per_s": tpss[-1], "median_ttft_s": ttfts[-1], "discarded": i == 0})
        print(f"run {i + 1}/{runs}{' (discarded)' if i == 0 else ''}: {t_tok} tokens in {t_time:.1f} s", file=sys.stderr)
    return summarize(tpss), summarize(ttfts), per_run


# ---- whisper measurement ----

def find_whisper_bin(given=None):
    for c in [given, os.environ.get("WHISPER_BIN")]:
        if c and Path(c).expanduser().is_file():
            return str(Path(c).expanduser())
    return shutil.which("whisper-cli") or shutil.which("whisper-cpp")


def default_wav():
    wavs = sorted((ROOT / "voice" / "clips_wav").glob("*_quiet.wav"))
    return wavs[0] if wavs else None


def bench_whisper(binary, model, wav, runs):
    """Returns (summary_or_None, reason_if_none). RTF = wall time of the whisper-cli process
    (includes model load) / audio length. First run discarded."""
    binary = find_whisper_bin(binary)
    if not binary:
        return None, "whisper binary not found (use --whisper-bin)"
    if not model or not Path(model).expanduser().is_file():
        return None, "whisper model not found (use --whisper-model)"
    if not wav or not Path(wav).is_file():
        return None, "no wav file found (use --wav)"
    audio = wav_seconds(wav)
    vals = []
    for _ in range(runs):
        t0 = time.perf_counter()
        subprocess.run([binary, "-m", str(Path(model).expanduser()), "-f", str(wav)],
                       capture_output=True, check=True)
        vals.append(rtf(time.perf_counter() - t0, audio))
    return summarize(vals), ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", default="http://127.0.0.1:8080")
    ap.add_argument("--runs", type=int, default=3, help="runs per measurement; the first is thrown away")
    ap.add_argument("--n", type=int, default=10, help="first N rows of data/seeds.jsonl")
    ap.add_argument("--whisper-bin")
    ap.add_argument("--whisper-model")
    ap.add_argument("--wav")
    ap.add_argument("--json", help="write results to this path")
    a = ap.parse_args(argv)

    props = server_props(a.llm)
    model = model_name_from_props(props)
    tps = ttft = None
    per_run, llm_note = [], ""
    try:
        tps, ttft, per_run = bench_llm(a.llm, a.n, a.runs)
    except Exception as e:
        llm_note = f"llama-server at {a.llm} not reachable: {e}"
        print(llm_note, file=sys.stderr)
    wav = Path(a.wav) if a.wav else default_wav()
    rt, rtf_note = bench_whisper(a.whisper_bin, a.whisper_model, wav, a.runs)

    print(HEADER)
    print(format_row(device_name(), ram_text(), model, quant_from_name(model), tps, ttft, rt, rtf_note))
    print("\nHow measured:")
    print(f"- Tokens/s: total generated tokens / total wall time (HTTP, streamed) over the first {a.n} rows of "
          f"data/seeds.jsonl, same prompt and grammar as run_llm.py, temperature 0, no prompt cache; "
          f"median of {max(a.runs - 1, 0)} runs after discarding run 1. Includes prompt processing.")
    print("- Time to first token: from sending the request to the first streamed chunk with text; "
          "median over the commands, then median over runs.")
    print(f"- Whisper RTF: wall time of one whisper-cli call (includes model load) / audio length of "
          f"{wav.name if wav else 'n/a'}; median of {max(a.runs - 1, 0)} runs after discarding run 1. "
          + (f"Not measured: {rtf_note}." if rt is None else ""))
    if llm_note:
        print(f"- LLM: {NOT}. {llm_note}")
    print("- Power: not measured.")
    if a.json:
        Path(a.json).write_text(json.dumps({"device": device_name(), "ram": ram_text(), "model": model,
                                            "tokens_per_s": tps, "ttft_s": ttft, "whisper_rtf": rt,
                                            "whisper_note": rtf_note, "llm_note": llm_note,
                                            "runs": per_run}, indent=2))


if __name__ == "__main__":
    main()
