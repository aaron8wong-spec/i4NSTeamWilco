"""Voice in the main loop (M12): a fake transcriber, no whisper and no microphone."""
import asyncio
import json

from integration import main as demo
from integration import pipeline
from integration.test_pipeline import SEARCH, SEARCH_TEXT, llm_for_demo


def run_voice(tmp_path, lines, said, llm=llm_for_demo, name="v.jsonl"):
    log = pipeline.RunLog(tmp_path / name)
    out = asyncio.run(demo.run(lines, llm=llm, time_scale=0, log=log, out=lambda s: None,
                               transcribe_fn=lambda wav: said[wav]))
    return out, [json.loads(l) for l in (tmp_path / name).read_text().splitlines()]


def test_transcript_is_shown_before_the_command_runs(tmp_path):
    out, _ = run_voice(tmp_path, ["@voice a.wav"], {"a.wav": SEARCH_TEXT})
    heard = next(i for i, l in enumerate(out) if l.startswith("[HEARD]"))
    cmd = next(i for i, l in enumerate(out) if l.startswith("[CMD] search_area"))
    assert heard < cmd and out[heard] == f"[HEARD] {SEARCH_TEXT}"
    assert not any(l.startswith("> ") for l in out)  # no duplicate echo


def test_voice_and_typed_give_the_same_command_lines(tmp_path):
    typed = asyncio.run(demo.run([SEARCH_TEXT, "yes, loiter", "@wait", "report status"], llm=llm_for_demo,
                                 time_scale=0, log=pipeline.RunLog(tmp_path / "t.jsonl"), out=lambda s: None))
    said = {"1.wav": SEARCH_TEXT, "2.wav": "yes, loiter", "3.wav": "report status"}
    voiced, _ = run_voice(tmp_path, ["@voice 1.wav", "@voice 2.wav", "@wait", "@voice 3.wav"], said)
    strip = lambda out: [l for l in out if l[:1] == "[" and not l.startswith("[HEARD]")]
    assert strip(typed) == strip(voiced)


def test_empty_or_garbled_transcript_is_logged_and_ignored(tmp_path):
    for i, said in enumerate(["", "  ", "?!", "5 ."]):
        out, rows = run_voice(tmp_path, ["@voice a.wav"], {"a.wav": said}, name=f"g{i}.jsonl")
        assert out == ["[HEARD] (nothing understood, ignored)"]
        v = next(r for r in rows if r["stage"] == "voice")
        assert v["data"]["ignored"] is True
        assert not any(r["stage"] in ("llm", "gate", "execute") for r in rows)


def test_transcriber_failure_does_not_stop_the_loop(tmp_path):
    def boom(wav):
        raise RuntimeError("whisper-cli not found")
    log = pipeline.RunLog(tmp_path / "e.jsonl")
    out = asyncio.run(demo.run(["@voice a.wav", "@wait", "/manual"], llm=llm_for_demo, time_scale=0, log=log,
                               out=lambda s: None, transcribe_fn=boom))
    assert out[0].startswith("[HEARD] (could not transcribe") and out[-1] == "[MODE] manual"


def test_voice_log_has_timing_fields(tmp_path):
    _, rows = run_voice(tmp_path, ["@voice a.wav"], {"a.wav": SEARCH_TEXT})
    d = next(r for r in rows if r["stage"] == "voice")["data"]
    assert d["transcript"] == SEARCH_TEXT and d["transcribe_s"] >= 0 and d["speech_end_ts"] > 0


def test_unsafe_spoken_command_is_still_refused(tmp_path):
    bad = {"action": "goto", "params": {"place": "bridge", "alt_m": 800}}
    out, _ = run_voice(tmp_path, ["@voice a.wav"], {"a.wav": "Go to the bridge at 800 meters"}, llm=lambda t: bad)
    assert any(l.startswith("[REFUSED]") for l in out) and not any(l.startswith("[CMD]") for l in out)


def test_is_garbled():
    assert demo.is_garbled("") and demo.is_garbled("12 !") and not demo.is_garbled("No.")


def test_spoken_yes_with_no_question_pending_does_not_hang(tmp_path):
    """Regression: a spoken 'yes' used to wait for itself (it is in the task list) when no question
    was ever asked, for example because the search line was not understood. It must finish."""
    said = {"1.wav": "uh search the field", "2.wav": "yes, loiter"}
    clarify = {"action": "clarify", "params": {"reason": "missing_location", "question": "Where?"}}

    async def go():
        log = pipeline.RunLog(tmp_path / "y.jsonl")
        return await asyncio.wait_for(
            demo.run(["@voice 1.wav", "@voice 2.wav", "@wait"], llm=lambda t: clarify, time_scale=0, log=log,
                     out=lambda s: None, transcribe_fn=lambda w: said[w]), timeout=10)

    out = asyncio.run(go())
    assert sum(l.startswith("[CLARIFY]") for l in out) == 2 and not any(l.startswith("[CMD]") for l in out)


def test_spoken_yes_answers_the_question_when_one_is_asked(tmp_path):
    said = {"1.wav": SEARCH_TEXT, "2.wav": "yes, loiter"}
    out, _ = run_voice(tmp_path, ["@voice 1.wav", "@voice 2.wav", "@wait"], said)
    assert any(l.startswith("[ASK]") for l in out) and any(l.startswith("[CMD] loiter") for l in out)


def test_transcripts_are_shown_in_the_order_given(tmp_path):
    import time as _t
    delays = {"1.wav": 0.15, "2.wav": 0.05, "3.wav": 0.0}   # the first clip is the slowest to transcribe

    def slow(w):
        _t.sleep(delays[w])
        return {"1.wav": "Hold position.", "2.wav": "Return home.", "3.wav": "Report status."}[w]

    log = pipeline.RunLog(tmp_path / "o.jsonl")
    out = asyncio.run(demo.run(["@voice 1.wav", "@voice 2.wav", "@voice 3.wav"], llm=llm_for_demo, time_scale=0,
                               log=log, out=lambda s: None, transcribe_fn=slow))
    assert [l for l in out if l.startswith("[HEARD]")] == [
        "[HEARD] Hold position.", "[HEARD] Return home.", "[HEARD] Report status."]
