#!/usr/bin/env python3
"""Recover an agent's final prose report from its transcript when it idled without writing."""
import json, sys, os

def blocks(path):
    out = []
    with open(path, errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            msg = rec.get("message") or rec
            if msg.get("role") != "assistant":
                continue
            c = msg.get("content")
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                        out.append(b["text"])
    return out

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
bs = blocks(path)
print(f"# transcript: {os.path.basename(path)}")
print(f"# assistant text blocks: {len(bs)}\n")
for i, b in enumerate(bs[-n:], 1):
    print(f"{'='*70}\n# BLOCK -{len(bs[-n:]) - i + 1}  ({len(b)} chars)\n{'='*70}")
    print(b[:6000])
    print()
