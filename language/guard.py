"""Plain-code helpers around the language model (R2). The model suggests; this code checks.

1. normalize_units(text): runs BEFORE the model. Turns number words into digits and feet,
   kilometers and minutes into meters and seconds, so the model does no arithmetic.
2. check_grounding(cmd, text): runs AFTER the model. If climb or descend points the opposite way
   from the direction words in the text, or if a value in the command (altitude,
   bearing, coordinates, a place or event name, ...) is not in the operator's words, the command
   becomes a clarify. This stops the model inventing values such as alt_m 1 or lat/lon 0, 0.

Limits (not handled): numbers written like "1,000", mixed fractions ("half a minute"), and
number words that are not followed by a unit ("go to forty"). A number that appears in the text
for a different reason can still hide an invented value of the same size. Report raw and guarded
accuracy side by side, so the guard does not hide the model's errors.
"""
import re

_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_NUM = "|".join([*_ONES, *_TENS, "hundred", "thousand"])
_UNITS = (r"(?:meters?|metres?|m|feet|foot|ft|kilometers?|kilometres?|km|minutes?|mins?|"
          r"seconds?|secs?|degrees?|deg)")
_WORD_RUN = re.compile(
    rf"\b((?:a(?=\s+(?:hundred|thousand))|(?:{_NUM}))(?:[\s-]+(?:and\s+)?(?:{_NUM}))*)(?=\s+{_UNITS}\b)", re.I)
_UNIT_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(feet|foot|ft|kilometers?|kilometres?|km|minutes?|mins?)\b", re.I)
_A_MINUTE = re.compile(r"\b(?:a|one)\s+minute\b", re.I)
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")

# Order matters: the first missing slot decides the question.
_SLOTS = [
    ("location", ("lat", "lon", "place", "event_id"), "missing_location", "Where should I go?"),
    ("bearing_deg", ("bearing_deg",), "missing_location", "Which direction should I fly, in degrees?"),
    ("distance_m", ("distance_m",), "missing_location", "How far should I fly, in meters?"),
    ("alt_m", ("alt_m",), "missing_altitude", "How high should I fly?"),
    ("radius_m", ("radius_m",), "ambiguous_reference", "What radius should I use, in meters?"),
    ("duration_s", ("duration_s",), "ambiguous_reference", "For how many seconds?"),
    ("amount_m", ("amount_m",), "missing_altitude", "By how many meters?"),
]


_DOWN = re.compile(r"\b(?:down|drop|lower|lose|descend|descent|sink|decrease)\b", re.I)
_UP = re.compile(r"\b(?:up|climb|ascend|ascent|rise|gain|raise|higher|increase)\b", re.I)


def _direction_conflict(action, text):
    """True when the words say the opposite way from the command (climb vs descend).

    The model sometimes swaps them. Both are valid and inside the limits, so the safety gate
    cannot tell. Only a one-sided text counts: if the text has both kinds of words, we leave it.
    """
    down, up = bool(_DOWN.search(text)), bool(_UP.search(text))
    return (action == "climb" and down and not up) or (action == "descend" and up and not down)


def _words_to_int(run):
    total = current = 0
    for w in re.findall(r"[a-z]+", run.lower()):
        if w in _ONES:
            current += _ONES[w]
        elif w in _TENS:
            current += _TENS[w]
        elif w == "hundred":
            current = max(current, 1) * 100
        elif w == "thousand":
            total += max(current, 1) * 1000
            current = 0
    return total + current


def _half_up(x):
    return int(x + 0.5)


def normalize_units(text):
    """Return text with number words as digits and feet / km / minutes as meters / seconds."""
    text = _WORD_RUN.sub(lambda m: str(_words_to_int(m.group(1))), text)
    text = _A_MINUTE.sub("60 seconds", text)

    def convert(m):
        n, unit = float(m.group(1)), m.group(2).lower()
        if unit in ("feet", "foot", "ft"):
            return f"{_half_up(n * 0.3048)} meters"
        if unit.startswith(("kilomet", "km")):
            return f"{_half_up(n * 1000)} meters"
        return f"{_half_up(n * 60)} seconds"

    return _UNIT_NUM.sub(convert, text)


def numbers_in(text):
    return [float(x) for x in _NUMBER.findall(text)]


def _has_number(value, nums):
    return any(abs(n - value) < 1e-6 for n in nums)


def _grounded(key, value, nums, text, context_event_ids):
    if key == "place":
        return all(re.search(rf"\b{re.escape(t)}\b", text, re.I) for t in value.split("_"))
    if key == "event_id":
        return bool(re.search(rf"\b{re.escape(value)}\b", text, re.I)) or value in context_event_ids
    return _has_number(value, nums)


def check_grounding(cmd, text, context_event_ids=()):
    """Return (command, reason). reason is None when nothing changed.

    text should be the normalized text the model saw. context_event_ids are event ids the model
    may use without the operator saying them (the pending question in mission_state, task 7.4).
    """
    if not isinstance(cmd, dict) or cmd.get("action") == "clarify":
        return cmd, None
    params = cmd.get("params") or {}
    if _direction_conflict(cmd.get("action"), text):
        clarify = {"action": "clarify", "params": {"reason": "ambiguous_reference",
                                                   "question": "Do you want me to climb or descend?"}}
        return clarify, f"{cmd['action']} does not match the direction words in the request"
    nums = numbers_in(text)
    for name, keys, reason, question in _SLOTS:
        for key in keys:
            if key in params and not _grounded(key, params[key], nums, text, context_event_ids):
                clarify = {"action": "clarify", "params": {"reason": reason, "question": question}}
                return clarify, f"{key}={params[key]!r} is not in the request"
    return cmd, None
