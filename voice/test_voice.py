import csv
import subprocess
import wave

import pytest

import eval_wer
import record
import transcribe as tr
import wer as werlib


# ---- wer.py ----

def test_wer_identical_is_zero():
    assert werlib.wer("Return home.", "return HOME") == (0, 2)


def test_wer_counts_sub_del_ins():
    assert werlib.wer("fly to the bridge", "fly the bridge")[0] == 1          # one deletion
    assert werlib.wer("fly to the bridge", "fly to a bridge")[0] == 1         # one substitution
    assert werlib.wer("hold", "hold it now")[0] == 2                          # two insertions


def test_wer_empty_transcript_is_all_deletions():
    assert werlib.wer("return home", "") == (2, 2)


def test_number_words_vs_digits():
    ref, hyp = "climb twenty meters", "climb 20 meters"
    assert werlib.wer(ref, hyp)[0] == 1
    assert werlib.wer(ref, hyp, number_norm=True)[0] == 0


@pytest.mark.parametrize("words,digits", [
    ("one hundred fifty", "150"), ("forty five", "45"), ("five hundred", "500"),
    ("one hundred twenty", "120"), ("thirty seven", "37"),
])
def test_normalize_numbers(words, digits):
    assert werlib.normalize_numbers(words.split()) == [digits]


def test_spoken_digit_string_stays_separate():
    assert werlib.normalize_numbers("one two one".split()) == ["1", "2", "1"]


# ---- transcribe.py ----

def test_clean_removes_tags_and_spaces():
    assert tr.clean(" [BLANK_AUDIO]\n") == ""
    assert tr.clean("  Return   home. (wind blowing)\n") == "Return home."


def _files(tmp_path):
    cli, model, wav = tmp_path / "cli", tmp_path / "m.bin", tmp_path / "a.wav"
    for p in (cli, model, wav):
        p.write_bytes(b"x")
    return cli, model, wav


def test_transcribe_runs_cli_and_cleans(tmp_path, monkeypatch):
    cli, model, wav = _files(tmp_path)
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=" Hold position.\n", stderr="")

    monkeypatch.setattr(tr.subprocess, "run", fake_run)
    assert tr.transcribe(wav, cli=cli, model=model) == "Hold position."
    assert seen["cmd"][0] == str(cli) and "-nt" in seen["cmd"] and str(wav) in seen["cmd"]


def test_transcribe_missing_pieces_raise(tmp_path):
    cli, model, wav = _files(tmp_path)
    with pytest.raises(tr.TranscribeError, match="audio file"):
        tr.transcribe(tmp_path / "nope.wav", cli=cli, model=model)
    with pytest.raises(tr.TranscribeError, match="whisper-cli not found"):
        tr.transcribe(wav, cli=tmp_path / "nope", model=model)
    with pytest.raises(tr.TranscribeError, match="model not found"):
        tr.transcribe(wav, cli=cli, model=tmp_path / "nope")


def test_transcribe_failure_and_timeout_raise(tmp_path, monkeypatch):
    cli, model, wav = _files(tmp_path)
    monkeypatch.setattr(tr.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom"))
    with pytest.raises(tr.TranscribeError, match="boom"):
        tr.transcribe(wav, cli=cli, model=model)

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(tr.subprocess, "run", slow)
    with pytest.raises(tr.TranscribeError, match="timed out"):
        tr.transcribe(wav, cli=cli, model=model)


def test_model_name_follows_environment(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "/x/ggml-small.en.bin")
    assert tr.model_name() == "ggml-small.en.bin"


# ---- record.py ----

class FakeStream:
    def __init__(self, callback, chunks):
        self.callback, self.chunks = callback, chunks

    def __enter__(self):
        for c in self.chunks:
            self.callback(c, len(c) // 2, None, None)
        return self

    def __exit__(self, *a):
        return False


class FakeSD:
    def __init__(self, chunks):
        self.chunks, self.kw = chunks, None

    def RawInputStream(self, **kw):
        self.kw = kw
        return FakeStream(kw["callback"], self.chunks)


def test_recorder_writes_16k_mono_wav(tmp_path):
    sd = FakeSD([b"\x01\x00" * 8000, b"\x02\x00" * 8000])  # one second
    out = tmp_path / "r.wav"
    secs = record.record_push_to_talk(out, input_fn=lambda prompt: "", sd=sd, print_fn=lambda *a: None)
    assert secs == pytest.approx(1.0)
    assert sd.kw["samplerate"] == 16000 and sd.kw["channels"] == 1 and sd.kw["dtype"] == "int16"
    with wave.open(str(out)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 16000)


# ---- eval_wer.py ----

def test_evaluate_scores_skips_and_summarizes(tmp_path):
    for name in ("v01_quiet.wav", "v01_noisy.wav"):
        (tmp_path / name).write_bytes(b"x")
    rows = [
        {"id": "v01", "file": "v01_quiet.wav", "text": "Climb twenty meters.", "noise_source": "none"},
        {"id": "v01", "file": "v01_noisy.wav", "text": "Climb twenty meters.", "noise_source": "fan"},
        {"id": "v02", "file": "v02_quiet.wav", "text": "Return home.", "noise_source": "none"},  # no WAV
    ]
    said = {"v01_quiet.wav": "Climb 20 meters.", "v01_noisy.wav": "Climb meters."}
    results, skipped = eval_wer.evaluate(rows, tmp_path, lambda p: said[p.split("/")[-1]])
    assert skipped == ["v02_quiet.wav"] and len(results) == 2
    s = eval_wer.summarize(results)
    assert s["quiet"]["wer_strict"] == pytest.approx(1 / 3) and s["quiet"]["wer_numnorm"] == 0
    assert s["noisy"]["wer_numnorm"] == pytest.approx(1 / 3) and s["noisy"]["exact_numnorm"] == 0


def test_reference_csv_matches_the_plan():
    rows = list(csv.DictReader(open(eval_wer.HERE / "reference.csv")))
    assert len(rows) == 30
    assert sum(r["file"].endswith("_noisy.wav") for r in rows) == 10
    assert len({r["file"] for r in rows}) == 30
    assert all(r["text"].strip() for r in rows)


# ---- make_noisy.py ----

def test_mix_hits_the_requested_snr():
    import numpy as np
    import make_noisy
    rng = np.random.default_rng(0)
    speech = np.sin(np.linspace(0, 400, 16000)) * 5000
    noisy = make_noisy.mix(speech, 5.0, rng)
    noise = noisy - speech
    snr = 20 * np.log10(np.sqrt(np.mean(speech ** 2)) / np.sqrt(np.mean(noise ** 2)))
    assert snr == pytest.approx(5.0, abs=0.01)


def test_mix_is_repeatable_with_the_same_seed():
    import numpy as np
    import make_noisy
    s = np.ones(1000) * 1000.0
    assert np.array_equal(make_noisy.mix(s, 5, np.random.default_rng(7)), make_noisy.mix(s, 5, np.random.default_rng(7)))
