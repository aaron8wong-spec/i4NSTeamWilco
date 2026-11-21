"""Scorer v0 (CLAUDE.md section 6). Plain code, no model. See docs/scoring-spec.md."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    from integration import geo
except ImportError:  # run from inside integration/ or with it on the path
    import geo
try:
    from reporting import templates
except ImportError:
    import templates

ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS = json.loads((ROOT / "integration" / "schemas.json").read_text())
_wrap = lambda name: Draft202012Validator(
    {"$schema": _SCHEMAS["$schema"], "$defs": _SCHEMAS["$defs"], "$ref": f"#/$defs/{name}"})
RULE_VALIDATOR, MESSAGE_VALIDATOR = _wrap("Rule"), _wrap("OperatorMessage")

PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}
DUPLICATE_RADIUS_M = 25.0
LOITER_RADIUS_M, LOITER_DURATION_S = 30, 120


def load_rules(path) -> list:
    """Load rules.json and validate each rule against Rule in schemas.json. Raises ValueError."""
    rules = json.loads(Path(path).read_text())["rules"]
    for r in rules:
        errs = [e.message for e in RULE_VALIDATOR.iter_errors(r)]
        if errs:
            raise ValueError(f"rule {r.get('id', '?')} invalid: {errs}")
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ids")
    return rules


def _target_matches(event, target) -> bool:
    return target is None or target == "any" or target == event["type"]


def _in_area(event, area) -> bool:
    if not area:
        return False
    return geo.distance_m(event["lat"], event["lon"], area["lat"], area["lon"]) <= area["radius_m"]


def _rule_matches(rule, event, st) -> bool:
    if rule["event_type"] not in ("any", event["type"]):
        return False
    c = rule["condition"]
    if "people_visible_min" in c and event["people_visible"] < c["people_visible_min"]:
        return False
    if "in_search_area" in c and _in_area(event, st["area"]) != c["in_search_area"]:
        return False
    if "matches_target" in c and _target_matches(event, st["target"]) != c["matches_target"]:
        return False
    return True


def _sort_key(rule):
    # best first: priority, most condition keys, higher people_visible_min (a stricter threshold
    # is more specific; needed so R04 beats R01, which both have one key), highest min_confidence, lowest id
    c = rule["condition"]
    return (-PRIORITY_RANK[rule["priority"]], -len(c), -c.get("people_visible_min", 0),
            -rule["min_confidence"], rule["id"])


def best_rule(event, st, rules):
    matches = [r for r in rules if _rule_matches(r, event, st)]
    return min(matches, key=_sort_key) if matches else None


def _is_duplicate(event, st, reported_events) -> bool:
    if event["id"] in st["already_reported"]:
        return True
    for p in reported_events or []:
        if p.get("type") == event["type"] and geo.distance_m(
                event["lat"], event["lon"], p["lat"], p["lon"]) <= DUPLICATE_RADIUS_M:
            return True
    return False


def _msg(tier, event, rule_id, text):
    m = {"tier": tier, "event_id": event["id"], "rule_id": rule_id, "text": text,
         "expects_reply": tier == "ask"}
    errs = [e.message for e in MESSAGE_VALIDATOR.iter_errors(m)]
    assert not errs, errs
    return m


def score(event: dict, state, rules: list, reported_events=None) -> dict:
    """Return an OperatorMessage for one event. Updates state (mark_reported, set_pending).

    reported_events: optional list of {"type","lat","lon"} for earlier events, used only
    for the near-duplicate check. The caller keeps it (MissionState has no positions).
    """
    st = state.as_dict()
    if event["id"] in st["already_reported"]:
        return _msg("log", event, templates.NO_RULE, templates.render_log(event, "already reported"))
    if _is_duplicate(event, st, reported_events):
        state.mark_reported(event["id"])
        return _msg("log", event, templates.NO_RULE,
                    templates.render_log(event, "near a thing already reported"))

    state.mark_reported(event["id"])
    rule = best_rule(event, st, rules)
    if rule is None:
        return _msg("log", event, templates.NO_RULE, templates.render_log(event, "no rule matches"))

    rid = rule["id"]
    if not _target_matches(event, st["target"]) and not rule["safety_relevant"]:
        return _msg("log", event, rid, templates.render_log(event, "not the mission target", rid))

    low_conf = event["confidence"] < rule["min_confidence"]
    if rule["priority"] == "high" and low_conf:
        tier = "ask"
    elif low_conf:
        tier = "log"  # medium or low rule, confidence below the rule's minimum
    elif rule["priority"] == "high":
        tier = rule["action"] if rule["action"] in ("interrupt", "ask") else "interrupt"
    elif rule["priority"] == "medium":
        tier = "summarize"
    else:
        tier = "log"

    text = templates.render(tier, event, rule)
    if tier == "ask":
        proposed = {"action": "loiter", "params": {
            "event_id": event["id"], "radius_m": LOITER_RADIUS_M, "duration_s": LOITER_DURATION_S}}
        state.set_pending(text, event["id"], proposed)
    return _msg(tier, event, rid, text)
