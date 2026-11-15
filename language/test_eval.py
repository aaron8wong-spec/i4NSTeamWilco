"""Tests for language/eval.py scoring (no model needed). Run: cd language && python3 -m pytest -q"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import eval as ev

HERE = Path(__file__).parent
GOTO = {"action": "goto", "params": {"place": "north_field", "alt_m": 40}}
CLAR = {"action": "clarify", "params": {"reason": "missing_altitude", "question": "How high?"}}


@pytest.mark.parametrize("exp,got,expected", [
    (GOTO, GOTO, "exact"),
    (GOTO, {"action": "goto", "params": {"place": "north_field", "alt_m": 41}}, "wrong_params"),
    (GOTO, {"action": "hold", "params": {}}, "wrong_action"),
    (GOTO, CLAR, "false_ask"),
    (CLAR, CLAR, "exact"),
    (CLAR, {"action": "clarify", "params": {"reason": "missing_location", "question": "x"}}, "wrong_reason"),
    (CLAR, GOTO, "invented_command"),
    (GOTO, None, "invalid"),
])
def test_outcome(exp, got, expected):
    assert ev.outcome(exp, got) == expected


def test_clarify_question_wording_is_not_scored():
    other_words = {"action": "clarify", "params": {"reason": "missing_altitude", "question": "Altitude?"}}
    assert ev.outcome(CLAR, other_words) == "exact"


def row(exp, model, guarded=None, tag="t"):
    return {"id": "x", "tag": tag, "exp": exp, "model": model, "guarded": guarded if guarded is not None else model,
            "latency_s": 1.0}


def test_summarize_counts_and_rates():
    rows = [
        row(GOTO, GOTO),                                                        # exact
        row(GOTO, {"action": "goto", "params": {"place": "x", "alt_m": 40}}),   # wrong params, would fly
        row(GOTO, CLAR),                                                        # false ask
        row(CLAR, CLAR),                                                        # exact clarify
        row(CLAR, GOTO),                                                        # invented command, would fly
    ]
    s = ev.summarize(rows, "model")
    assert s["n"] == 5
    assert s["exact_acc"] == pytest.approx(2 / 5)
    assert s["action_acc"] == pytest.approx(3 / 5)          # wrong only for the false ask and the invented command
    assert s["param_acc"] == pytest.approx(1 / 2)           # two goto rows with the right action: one exact
    assert s["clarify_recall"] == pytest.approx(1 / 2)
    assert s["clarify_reason_acc"] == 1.0
    assert s["false_ask_rate"] == pytest.approx(1 / 3)
    assert s["would_fly_wrong"] == 2


def test_guard_column_is_scored_separately_from_the_model_column():
    rows = [row(CLAR, GOTO, guarded=CLAR)]
    assert ev.summarize(rows, "model")["would_fly_wrong"] == 1
    assert ev.summarize(rows, "guarded")["would_fly_wrong"] == 0


def test_climb_descend_swap_is_counted():
    up, down = {"action": "climb", "params": {"amount_m": 9}}, {"action": "descend", "params": {"amount_m": 9}}
    assert ev.summarize([row(down, up)], "model")["climb_descend_swaps"] == 1
    assert ev.summarize([row(up, up)], "model")["climb_descend_swaps"] == 0


def test_empty_denominators_give_none():
    s = ev.summarize([row(GOTO, GOTO)], "model")
    assert s["clarify_recall"] is None and s["false_ask_rate"] == 0.0


def test_load_gives_a_tag_for_seeds_and_rows():
    assert all(r["tag"] for r in ev.load("seeds")) and all(r["tag"] for r in ev.load("train"))


def test_test_split_refuses_without_final():
    out = subprocess.run([sys.executable, str(HERE / "eval.py"), "--split", "test"], capture_output=True, text=True)
    assert out.returncode != 0 and "--final" in (out.stderr + out.stdout)
