"""Message templates for the operator. Plain strings, no model. Max 240 chars (OperatorMessage)."""

MAX_LEN = 240
NO_RULE = "R00"  # rule_id used when no rule decided the tier (duplicate or no match); schema needs an id

_NAMES = {"vehicle": "Vehicle", "person": "Person", "structure": "Structure",
          "wildlife": "Wildlife", "unknown": "Unknown object"}


def subject(event: dict) -> str:
    """Short noun phrase, for example 'Vehicle (truck), 2 people nearby'."""
    s = _NAMES.get(event["type"], "Object")
    if event.get("subtype"):
        s += f" ({event['subtype']})"
    n = event.get("people_visible", 0)
    if n and event["type"] != "person":
        s += f", {n} {'person' if n == 1 else 'people'} nearby"
    elif n > 1 and event["type"] == "person":
        s = f"Group of {n} people"
    return s


def _split_question(reason: str):
    """Split a reason into (statement, question). The question is a trailing sentence ending in '?'."""
    reason = reason.strip()
    if not reason.endswith("?"):
        return reason.rstrip("."), None
    cut = max(reason.rfind(". "), -1)
    if cut < 0:
        return "", reason
    return reason[:cut].strip().rstrip("."), reason[cut + 2:].strip()


def _fit(text: str) -> str:
    return text if len(text) <= MAX_LEN else text[: MAX_LEN - 3].rstrip() + "..."


def render(tier: str, event: dict, rule: dict) -> str:
    """Text for one message. Always names the rule id and its reason."""
    subj, rid, reason = subject(event), rule["id"], rule["reason"]
    if tier == "ask":
        statement, question = _split_question(reason)
        why = f" {statement}" if statement else ""
        return _fit(f"{subj} (rule {rid}:{why or ' ' + reason}). {question or 'Loiter there?'}"
                    .replace(": .", ":"))
    return _fit(f"{subj} (rule {rid}: {reason.rstrip('.')}).")


def render_log(event: dict, why: str, rule_id: str = NO_RULE) -> str:
    return _fit(f"{subject(event)} logged (rule {rule_id}: {why}).")
