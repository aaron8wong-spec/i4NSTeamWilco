#!/usr/bin/env python3
"""Add a dataset batch to data/train.jsonl and data/test.jsonl (about 20% test, split per tag).

  python3 language/split_dataset.py data/dataset_batch1.jsonl

Each batch is split once, with a seed made from the batch name and the tag, so the same batch
always gives the same split and rows already in train.jsonl or test.jsonl never move. Tags with
fewer than 4 rows go to train. Refuses to add an id that is already in either file.
The test file is the held-out set: do not tune on it, and score it once at the end.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def split_batch(rows, name, frac=0.2):
    by_tag = defaultdict(list)
    for r in rows:
        by_tag[r["tag"]].append(r)
    train, test = [], []
    for tag, group in sorted(by_tag.items()):
        group = sorted(group, key=lambda r: r["id"])
        random.Random(f"{name}:{tag}").shuffle(group)
        n_test = max(1, round(frac * len(group))) if len(group) >= 4 else 0
        test += group[:n_test]
        train += group[n_test:]
    return sorted(train, key=lambda r: r["id"]), sorted(test, key=lambda r: r["id"])


def read(path):
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    batch = Path(a.batch)
    rows = read(batch)
    existing = {r["id"] for r in read(DATA / "train.jsonl") + read(DATA / "test.jsonl")}
    clash = existing & {r["id"] for r in rows}
    if clash:
        raise SystemExit(f"already split, not adding again: {sorted(clash)[:5]}")
    train, test = split_batch(rows, batch.name)
    print(f"{batch.name}: {len(rows)} rows -> train {len(train)}, test {len(test)}")
    if not a.dry_run:
        for name, part in (("train.jsonl", train), ("test.jsonl", test)):
            with (DATA / name).open("a") as f:
                f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part))
        print("appended to data/train.jsonl and data/test.jsonl")


if __name__ == "__main__":
    main()
