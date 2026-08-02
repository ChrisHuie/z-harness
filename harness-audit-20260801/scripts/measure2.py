#!/usr/bin/env python3
"""Corrected measurement: dedup by requestId, include subagent transcripts."""
import json, glob, os
from collections import defaultdict

D = "/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent"
agg = defaultdict(lambda: dict(calls=0, inp=0, cc=0, cr=0, out=0))

def scan(paths, kind):
    for p in paths:
        seen = set()
        for line in open(p, errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            m = r.get("message")
            if not isinstance(m, dict) or not isinstance(m.get("usage"), dict):
                continue
            rid = r.get("requestId") or m.get("id")
            if rid and rid in seen:
                continue          # same API call, another content block
            if rid:
                seen.add(rid)
            u = m["usage"]
            a = agg[kind]
            a["calls"] += 1
            a["inp"] += u.get("input_tokens", 0) or 0
            a["cc"] += u.get("cache_creation_input_tokens", 0) or 0
            a["cr"] += u.get("cache_read_input_tokens", 0) or 0
            a["out"] += u.get("output_tokens", 0) or 0

scan(glob.glob(f"{D}/*.jsonl"), "main")
scan(glob.glob(f"{D}/*/subagents/*.jsonl"), "subagent")

def h(n):
    return f"{n/1e9:.2f}B" if n >= 1e9 else (f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k")

print(f"{'':<10}{'calls':>9}{'input':>9}{'cache_wr':>10}{'cache_rd':>10}{'output':>9}{'cost units':>12}")
tot = defaultdict(int)
for k in ("main", "subagent"):
    a = agg[k]
    cost = a["inp"] + a["cc"] * 1.25 + a["cr"] * 0.10 + a["out"] * 5.0
    print(f"{k:<10}{a['calls']:>9,}{h(a['inp']):>9}{h(a['cc']):>10}{h(a['cr']):>10}{h(a['out']):>9}{h(cost):>12}")
    for f in ("calls", "inp", "cc", "cr", "out"):
        tot[f] += a[f]
    tot["cost"] += cost

print("-" * 69)
print(f"{'TOTAL':<10}{tot['calls']:>9,}{h(tot['inp']):>9}{h(tot['cc']):>10}{h(tot['cr']):>10}{h(tot['out']):>9}{h(tot['cost']):>12}")
print()
sub_share = 100 * agg["subagent"]["calls"] / max(tot["calls"], 1)
sub_cost = agg["subagent"]["inp"] + agg["subagent"]["cc"]*1.25 + agg["subagent"]["cr"]*0.10 + agg["subagent"]["out"]*5.0
print(f"  subagents = {sub_share:.0f}% of API calls, {100*sub_cost/max(tot['cost'],1):.0f}% of cost")
print(f"  re-read multiplier (cache_read / cache_write) = {tot['cr']/max(tot['cc'],1):.1f}x")
print()
print("  BILLED SHARE:")
for label, v in [("cache read", tot["cr"]*0.10), ("output", tot["out"]*5.0),
                 ("cache write", tot["cc"]*1.25), ("fresh input", tot["inp"]*1.0)]:
    print(f"    {label:<13} {100*v/max(tot['cost'],1):>5.1f}%")
