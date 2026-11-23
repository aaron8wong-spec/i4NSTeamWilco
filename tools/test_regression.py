"""Tests for tools/regression.py (M15)."""
import regression


def test_at_least_25_cases_with_unique_ids():
    ids = [c[0] for c in regression.CASES]
    assert len(ids) >= 25 and len(set(ids)) == len(ids)


def test_all_cases_pass_with_fake_model():
    lines = []
    passed, total = regression.run_all(out=lines.append)
    assert passed == total, "\n".join(lines)


def test_wrong_expectation_is_reported_as_fail():
    bad = ("bad", "Hold position", {"action": "hold", "params": {}}, False, "hold", {})
    lines = []
    passed, total = regression.run_all([bad], out=lines.append)
    assert (passed, total) == (0, 1) and lines[0].startswith("FAIL")


def test_main_exit_code_zero_when_all_pass():
    assert regression.main([]) == 0


def test_dry_run_never_reaches_backend():
    for case in regression.CASES:
        ok, *_ , problems = regression.run_case(case)
        assert not any("backend" in p for p in problems), case[0]
