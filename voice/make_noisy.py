"""Make the noisy clips by mixing synthetic pink noise into the quiet clips (Lane M, task M11).

    python3 voice/make_noisy.py [--snr-db 5]

For each *_noisy.wav row in reference.csv, reads the matching *_quiet.wav, adds pink noise scaled to
the chosen signal-to-noise ratio, and writes the noisy WAV. The seed is fixed, so the output is the
same every time. SNR uses the RMS of the whole clip (speech plus pauses), so the real SNR over the
speech alone is a little higher.

This is SYNTHETIC noise added in code, not recorded in a noisy place. It has no room echo and no
microphone noise, so it is easier than real noise. Every number from these clips must say so.
"""
import argparse
import csv
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
NOISE_NAME = "synthetic pink noise mixed in by voice/make_noisy.py"


def read_wav(path):
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth()) == (1, 2), "need mono 16-bit WAV"
        rate = w.getframerate()
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64), rate


def write_wav(path, samples, rate):
    pcm = np.clip(np.round(samples), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def pink_noise(n, rng):
    """White noise shaped to 1/f power (amplitude 1/sqrt(f)), unit RMS."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(spec), dtype=np.float64)
    f[0] = 1.0
    x = np.fft.irfft(spec / np.sqrt(f), n)
    return x / np.sqrt(np.mean(x ** 2))


def mix(speech, snr_db, rng):
    """speech + noise, with noise scaled so 20*log10(rms(speech)/rms(noise)) == snr_db."""
    rms = np.sqrt(np.mean(speech ** 2))
    noise = pink_noise(len(speech), rng) * rms / (10 ** (snr_db / 20))
    return speech + noise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snr-db", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--wav-dir", default=str(HERE / "clips_wav"))
    ap.add_argument("--reference", default=str(HERE / "reference.csv"))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.reference)))
    rng = np.random.default_rng(a.seed)
    label = f"{NOISE_NAME}, SNR {a.snr_db:g} dB, seed {a.seed}"
    made = 0
    for row in rows:
        if not row["file"].endswith("_noisy.wav"):
            continue
        quiet = Path(a.wav_dir) / row["file"].replace("_noisy", "_quiet")
        speech, rate = read_wav(quiet)
        write_wav(Path(a.wav_dir) / row["file"], mix(speech, a.snr_db, rng), rate)
        row["noise_source"] = label
        made += 1
    with open(a.reference, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {made} noisy clips at SNR {a.snr_db:g} dB ({label})")


if __name__ == "__main__":
    main()
