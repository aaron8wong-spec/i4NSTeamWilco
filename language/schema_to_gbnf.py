#!/usr/bin/env python3
"""Generate a llama.cpp GBNF grammar from schemas.json.

Handles only the JSON Schema subset the command schema uses: oneOf, const, enum,
object (all properties required, fixed order), number, string, and local $defs refs.
Anything else raises, so a schema change cannot silently produce a wrong grammar.

The grammar cannot enforce numeric ranges (minimum, maximum, exclusiveMinimum).
Those are checked by jsonschema and the safety gate, not by decoding.

Usage: python3 language/schema_to_gbnf.py [schemas.json] [out.gbnf]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

PRIMITIVES = r'''ws ::= [ \t\n]{0,2}
num ::= "-"? [0-9]+ ("." [0-9]+)?
strchar ::= [^"\\\x00-\x1f] | "\\" ["\\/bfnrt]'''


def lit(text):
    """GBNF string literal that matches `text` exactly."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


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
        if "const" in s:
            return lit(json.dumps(s["const"]))
        if "enum" in s:
            return "(" + " | ".join(lit(json.dumps(v)) for v in s["enum"]) + ")"
        t = s.get("type")
        if t == "number":
            return "num"
        if t == "string":
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
        for branch in schema["oneOf"]:
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
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "schemas.json"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "command.gbnf"
    out.write_text(schema_to_gbnf(json.loads(src.read_text())))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
