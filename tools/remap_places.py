#!/usr/bin/env python3
"""Rename place names in a dataset jsonl, in both the text and expected.params.place.

  python3 tools/remap_places.py data/dataset_batch3.jsonl old_barn=buildings water_tower=bridge --dry-run
  python3 tools/remap_places.py rows.jsonl --map mapping.json

In the text, the old name matches case-insensitively, with underscores or spaces ("old_barn", "old barn"),
and is written back with spaces ("the buildings"). All renames happen in one pass, so a=b and b=c do not chain.
WARNING: do not run this on data/train.jsonl or data/test.jsonl without a team decision (D4); it edits held-out rows.
"""
import argparse
import json
import re
from pathlib import Path


def build_pattern(mapping):
    forms = {}
    for old, new in mapping.items():
        forms[old.replace("_", " ").lower()] = new
    alt = "|".join(re.escape(k).replace(r"\ ", r"[ _]") for k in sorted(forms, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9_])(?:{alt})(?![A-Za-z0-9_])", re.I), forms


def remap_text(text, mapping):
    pat, forms = build_pattern(mapping)
    return pat.sub(lambda m: forms[m.group(0).replace("_", " ").lower()].replace("_", " "), text)


def remap_row(row, mapping):
    """Return (new_row, changed)."""
    new = json.loads(json.dumps(row))
    new["text"] = remap_text(row["text"], mapping)
    place = new.get("expected", {}).get("params", {}).get("place")
    if place in mapping:
        new["expected"]["params"]["place"] = mapping[place]
    return new, new != row


def parse_mapping(pairs, map_file=None):
    mapping = json.loads(Path(map_file).read_text()) if map_file else {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"bad mapping {p!r}, expected old=new")
        old, new = p.split("=", 1)
        mapping[old.strip()] = new.strip()
    if not mapping:
        raise SystemExit("no mapping given")
    return mapping


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("pairs", nargs="*", help="old=new")
    ap.add_argument("--map", help="JSON file {old: new}")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    mapping = parse_mapping(a.pairs, a.map)
    path = Path(a.file)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    out, changed = [], 0
    for r in rows:
        n, c = remap_row(r, mapping)
        out.append(n)
        if c:
            changed += 1
            print(f"{r['id']}: {r['text']!r} -> {n['text']!r}")
    print(f"{changed} of {len(rows)} rows change" + (" (dry run, nothing written)" if a.dry_run else ""))
    if not a.dry_run and changed:
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    return changed


if __name__ == "__main__":
    main()
