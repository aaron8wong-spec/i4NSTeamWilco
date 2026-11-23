"""Word error rate on the recorded clips (Lane M, task M11).

    python3 voice/eval_wer.py            # reads voice/reference.csv, writes voice/results_wer.csv

Each row of reference.csv is a clip (id, file, text, noise_source). Clips whose WAV is missing are
skipped and counted. The model file name is printed next to every number. Results come from our own
recordings (one speaker unless the README says otherwise), so they are not field accuracy.
"""
import argparse
import csv
import time
from pathlib import Path

from transcribe import TranscribeError, model_name, transcribe
from wer import wer

HERE = Path(__file__).parent


def condition(row):
    return "noisy" if row["file"].endswith("_noisy.wav") else "quiet"


def evaluate(rows, wav_dir, transcribe_fn=transcribe):
    """Return (results, skipped). Each result has strict and number-normalized error counts."""
    results, skipped = [], []
    for row in rows:
        wav = Path(wav_dir) / row["file"]
        if not wav.is_file():
            skipped.append(row["file"])
            continue
        t0 = time.perf_counter()
        try:
            hyp = transcribe_fn(str(wav))
        except TranscribeError as e:
            raise SystemExit(f"{row['file']}: {e}")
        secs = time.perf_counter() - t0
        e1, n = wer(row["text"], hyp)
        e2, _ = wer(row["text"], hyp, number_norm=True)
        results.append({"id": row["id"], "file": row["file"], "condition": condition(row),
                        "noise_source": row.get("noise_source", ""), "reference": row["text"],
                        "transcript": hyp, "ref_words": n, "errors_strict": e1,
                        "errors_numnorm": e2, "transcribe_s": round(secs, 2)})
    return results, skipped


def summarize(results):
    """{condition: {clips, words, wer_strict, wer_numnorm, exact_numnorm}} (rates as fractions)."""
    out = {}
    for cond in ("quiet", "noisy"):
        rs = [r for r in results if r["condition"] == cond]
        if not rs:
            continue
        words = sum(r["ref_words"] for r in rs)
        out[cond] = {"clips": len(rs), "words": words,
                     "wer_strict": sum(r["errors_strict"] for r in rs) / words,
                     "wer_numnorm": sum(r["errors_numnorm"] for r in rs) / words,
                     "exact_numnorm": sum(r["errors_numnorm"] == 0 for r in rs)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default=str(HERE / "reference.csv"))
    ap.add_argument("--wav-dir", default=str(HERE / "clips_wav"))
    ap.add_argument("--out", default=str(HERE / "results_wer.csv"))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.reference)))
    results, skipped = evaluate(rows, a.wav_dir)
    if not results:
        raise SystemExit("no clips found to score")
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    print(f"model: {model_name()}   clips scored: {len(results)}   skipped (no WAV): {len(skipped)}")
    for cond, s in summarize(results).items():
        print(f"{cond:6} clips {s['clips']:2}  words {s['words']:3}  WER strict {s['wer_strict']:.1%}  "
              f"number-normalized {s['wer_numnorm']:.1%}  exact {s['exact_numnorm']}/{s['clips']}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
