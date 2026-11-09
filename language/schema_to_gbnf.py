#!/usr/bin/env python3
"""Generate a llama.cpp GBNF grammar from $defs/Command in integration/schemas.json.

Handles only the JSON Schema subset the command schema uses: oneOf, const, enum,
object (all properties required, fixed order), number, integer with minimum and
maximum, string (length limits or a simple ^...$ pattern), and local $defs refs.
Anything else raises, so a schema change cannot silently produce a wrong grammar.

The grammar enforces integer ranges (alt_m, radius_m, duration_s) and string
patterns (place, event_id). It cannot enforce bounds on non-integer numbers, so
lat and lon ranges are checked by jsonschema, not by decoding. Real safety limits
belong to the safety gate.

Usage: python3 language/schema_to_gbnf.py [schemas.json] [out.gbnf]
"""
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).parent
SCHEMA_PATH = HERE.parent / "integration" / "schemas.json"

PRIMITIVES = r'''ws ::= [ \t\n]{0,2}
num ::= "-"? [0-9]+ ("." [0-9]+)?
strchar ::= [^"\\\x00-\x1f] | "\\" ["\\/bfnrt]'''


def lit(text):
    """GBNF string literal that matches `text` exactly."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def command_validator(schema):
    """jsonschema validator for one command (the Command def in the frozen schema)."""
    return jsonschema.Draft202012Validator(
        {"$ref": "#/$defs/Command", "$defs": schema["$defs"]}
    )


def _same_len(a, b):
    """GBNF group matching decimal strings a..b of equal length, no leading zeros."""
    n = len(a)
    if n == 1:
        return f"[{a}-{b}]"
    if a[0] == b[0]:
        return f'("{a[0]}" {_same_len(a[1:], b[1:])})'
    alts = [f'"{a[0]}" {_same_len(a[1:], "9" * (n - 1))}']
    if int(a[0]) + 1 <= int(b[0]) - 1:
        alts.append(f"[{int(a[0]) + 1}-{int(b[0]) - 1}] [0-9]{{{n - 1}}}")
    alts.append(f'"{b[0]}" {_same_len("0" * (n - 1), b[1:])}')
    return "(" + " | ".join(alts) + ")"


def int_range(lo, hi):
    """GBNF expression matching the whole numbers lo..hi (lo >= 0)."""
    if lo < 0 or hi < lo:
        raise NotImplementedError(f"unsupported integer range: {lo}..{hi}")
    alts = []
    for n in range(len(str(lo)), len(str(hi)) + 1):
        a = max(lo, 10 ** (n - 1) if n > 1 else 0)
        b = min(hi, 10**n - 1)
        alts.append(_same_len(str(a), str(b)))
    return "(" + " | ".join(alts) + ")"


def pattern_to_gbnf(pattern):
    """Quoted-string GBNF for a simple pattern: ^, literal chars, [classes], {m,n}, $."""
    if not (pattern.startswith("^") and pattern.endswith("$")):
        raise NotImplementedError(f"pattern must be anchored: {pattern}")
    body, items, i = pattern[1:-1], [], 0
    while i < len(body):
        if body[i] == "[":
            j = body.index("]", i)
            atom, i = body[i : j + 1], j + 1
        elif body[i] in "\\.*+?()|{}":
            raise NotImplementedError(f"unsupported pattern: {pattern}")
        else:
            atom, i = lit(body[i]), i + 1
        if i < len(body) and body[i] == "{":
            j = body.index("}", i)
            atom, i = atom + body[i : j + 1], j + 1
        items.append(atom)
    return '"\\"" ' + " ".join(items) + ' "\\""'


def rule_name(name):
    """GBNF rule names allow only lowercase letters, digits and dashes."""
    return name.lower().replace("_", "-")


class Builder:
    def __init__(self, schema):
        self.defs = schema.get("$defs", {})
        self.rules = {}  # rule name -> expression, in creation order

    def add(self, name, expr):
        self.rules[name] = expr
        return name

    def expr(self, s):
        if "$ref" in s:
            prefix = "#/$defs/"
            if not s["$ref"].startswith(prefix):
                raise NotImplementedError(f"unsupported $ref: {s['$ref']}")
            name = s["$ref"][len(prefix):]
            rname = rule_name(name)
            if rname not in self.rules:
                self.rules[rname] = ""  # reserve name so recursion cannot loop
                self.rules[rname] = self.expr(self.defs[name])
            return rname
        if "oneOf" in s:
            return "(" + " | ".join(self.expr(b) for b in s["oneOf"]) + ")"
        if "const" in s:
            return lit(json.dumps(s["const"]))
        if "enum" in s:
            return "(" + " | ".join(lit(json.dumps(v)) for v in s["enum"]) + ")"
        t = s.get("type")
        if t == "number":
            return "num"
        if t == "integer":
            if "minimum" not in s or "maximum" not in s:
                raise NotImplementedError("integer needs minimum and maximum")
            return int_range(s["minimum"], s["maximum"])
        if t == "string":
            if "pattern" in s:
                return pattern_to_gbnf(s["pattern"])
            lo, hi = s.get("minLength", 0), s.get("maxLength", "")
            return f'"\\"" strchar{{{lo},{hi}}} "\\""'
        if t == "object":
            return self.obj(s)
        raise NotImplementedError(f"unsupported schema: {s}")

    def obj(self, s):
        props = s.get("properties", {})
        if set(s.get("required", [])) != set(props):
            raise NotImplementedError("every property must be required")
        if s.get("additionalProperties") is not False:
            raise NotImplementedError("additionalProperties must be false")
        parts = [
            f'{lit(json.dumps(k))} ws ":" ws {self.expr(v)}' for k, v in props.items()
        ]
        body = ' ws "," ws '.join(parts)
        return f'"{{" ws {body} ws "}}"' if parts else '"{" ws "}"'

    def build(self, schema):
        names = []
        for branch in schema["$defs"]["Command"]["oneOf"]:
            action = branch["properties"]["action"]["const"]
            names.append(self.add(f"cmd-{rule_name(action)}", self.expr(branch)))
        # root is created last so it prints first
        rules = {"root": " | ".join(names), **self.rules}
        return rules


def schema_to_gbnf(schema):
    rules = Builder(schema).build(schema)
    lines = [f"{name} ::= {expr}" for name, expr in rules.items()]
    return "\n".join(lines) + "\n" + PRIMITIVES + "\n"


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SCHEMA_PATH
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "command.gbnf"
    out.write_text(schema_to_gbnf(json.loads(src.read_text())))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
