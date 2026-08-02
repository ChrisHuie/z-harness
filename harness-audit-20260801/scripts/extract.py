#!/usr/bin/env python3
"""Pull the final JSON classification array out of a subagent transcript."""
import json, re, sys, glob, os

def texts(path):
    """Yield assistant text blocks in file order."""
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
            content = msg.get("content")
            if isinstance(content, str):
                out.append(content)
            elif isinstance(content, list):
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        out.append(blk.get("text", ""))
    return out

def find_array(blocks):
    """Return the largest valid JSON array of dicts with a 'tier' key."""
    best = None
    for txt in blocks:
        for m in re.finditer(r"\[", txt):
            depth, start = 0, m.start()
            for i in range(start, len(txt)):
                if txt[i] == "[":
                    depth += 1
                elif txt[i] == "]":
                    depth -= 1
                    if depth == 0:
                        chunk = txt[start:i + 1]
                        try:
                            val = json.loads(chunk)
                        except Exception:
                            break
                        if (isinstance(val, list) and val
                                and all(isinstance(x, dict) for x in val)
                                and any("tier" in x for x in val)):
                            if best is None or len(val) > len(best):
                                best = val
                        break
    return best

for path in sorted(sys.argv[1:]):
    name = re.search(r"agent-a?(mem-sa-[abc])", path)
    label = name.group(1) if name else os.path.basename(path)
    blocks = texts(path)
    arr = find_array(blocks)
    if arr is None:
        print(f"{label}: NO JSON ARRAY FOUND ({len(blocks)} assistant blocks)")
        continue
    out = f"/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/result-{label}.json"
    with open(out, "w") as fh:
        json.dump(arr, fh, indent=2)
    tiers = {}
    for r in arr:
        tiers[r.get("tier", "?")] = tiers.get(r.get("tier", "?"), 0) + 1
    print(f"{label}: {len(arr)} entries -> {out}")
    print(f"    tiers: {tiers}")
