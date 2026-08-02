#!/usr/bin/env python3
"""Aggregate real token usage across salesagent session transcripts."""
import json, glob, os, sys
from collections import defaultdict

D = "/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent"
rows = []

for path in glob.glob(f"{D}/*.jsonl"):
    inp = cc = cr = out = 0
    turns = 0
    title = None
    first_ts = last_ts = None
    tools = defaultdict(int)

    for line in open(path, errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue

        if r.get("type") == "custom-title" and not title:
            title = (r.get("title") or r.get("customTitle") or "")[:90]

        ts = r.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts

        m = r.get("message")
        if not isinstance(m, dict):
            continue

        if m.get("role") == "assistant":
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tools[b.get("name", "?")] += 1

        u = m.get("usage")
        if isinstance(u, dict):
            turns += 1
            inp += u.get("input_tokens", 0) or 0
            cc += u.get("cache_creation_input_tokens", 0) or 0
            cr += u.get("cache_read_input_tokens", 0) or 0
            out += u.get("output_tokens", 0) or 0

    if turns == 0:
        continue

    rows.append({
        "file": os.path.basename(path),
        "title": title or "",
        "turns": turns,
        "input": inp, "cache_create": cc, "cache_read": cr, "output": out,
        "billed_in": inp + cc,          # cache reads are ~10% cost; creation is full
        "total_ctx": inp + cc + cr,      # total context volume moved
        "start": first_ts, "end": last_ts,
        "tools": dict(sorted(tools.items(), key=lambda x: -x[1])[:8]),
        "agent_spawns": tools.get("Agent", 0) + tools.get("Task", 0),
    })

rows.sort(key=lambda r: -r["billed_in"])
json.dump(rows, open(f"{os.path.dirname(os.path.abspath(__file__))}/token-measurements.json", "w"), indent=1)

def h(n):
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k"

T = lambda k: sum(r[k] for r in rows)
print(f"sessions with usage data: {len(rows)} of 159\n")
print("=== CORPUS TOTALS ===")
print(f"  turns (API calls):     {T('turns'):,}")
print(f"  fresh input:           {h(T('input'))}")
print(f"  cache CREATION:        {h(T('cache_create'))}   <- full price")
print(f"  cache READ:            {h(T('cache_read'))}   <- ~10% price")
print(f"  output:                {h(T('output'))}")
print(f"  total context moved:   {h(T('total_ctx'))}")
cr_tot, cc_tot = T("cache_read"), T("cache_create")
if cr_tot + cc_tot:
    print(f"  cache hit ratio:       {100*cr_tot/(cr_tot+cc_tot):.1f}%")
print()
print("=== TOP 15 SESSIONS BY BILLED INPUT ===")
print(f"{'billed':>8} {'ctx':>8} {'out':>7} {'turns':>6} {'agents':>7}  title")
for r in rows[:15]:
    print(f"{h(r['billed_in']):>8} {h(r['total_ctx']):>8} {h(r['output']):>7} "
          f"{r['turns']:>6} {r['agent_spawns']:>7}  {r['title'][:58]}")
print()
n = len(rows)
print("=== DISTRIBUTION (billed input) ===")
for label, lo, hi in [("top 10%", 0, n//10), ("next 40%", n//10, n//2), ("bottom 50%", n//2, n)]:
    seg = rows[lo:hi] or [{"billed_in": 0}]
    s = sum(x["billed_in"] for x in seg)
    print(f"  {label:<11} {len(seg):>3} sessions  {h(s):>8}  ({100*s/max(T('billed_in'),1):.0f}% of billed input)")
