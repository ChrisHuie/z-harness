"""Differential fuzz over Stop-guard judge() verdicts: oracle vs candidate.

Usage: python3 fuzz_judge_diff.py <oracle_guard.py> <candidate_guard.py> <seed> <count>

Generates grammar-based final messages and prints every verdict divergence. An
allow-direction divergence (oracle blocks, candidate allows) is the finding direction;
classify each by mechanism before treating a stricter-direction change as intended. The
vocabulary bounds what "zero divergences" quantifies over -- extend it with the tokens a
change touches before trusting a null result.
"""
import importlib.util, random, sys, json
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
oracle = load(sys.argv[1], "oracle"); cand = load(sys.argv[2], "cand")
seed = int(sys.argv[3]); n = int(sys.argv[4])
random.seed(seed)
openers = ["Starting the", "Running the", "Proceeding with the", "Continuing on the",
           "Beginning a", "Kicking off the", "Let me check", "I'll now run",
           "Let me now start", "On it", "Doing that now", "Firing off the"]
words = ["audit", "sweep", "tests", "checks", "migration", "script", "run", "prior",
         "three", "3", "second", "remaining", "failed", "completed", "passed", "finished",
         "already", "previously", "recently", "of", "for", "with", "the", "a", "whether",
         "why", "where", "how", "into", "it", "quickly", "all", "both", "no", "will",
         "being", "never", "produced", "took", "landed", "showed", "found", "x-failed",
         "re/completed", "don't", "v1.2.3", "12:04", "https://x.test", "image:v1"]
joiners = [" ", " ", " ", " ", ". ", "; ", ", ", ": ", " — ", " -- ", " and ", " because ",
           " after ", " that ", " which ", " then ", "  ", "\n", ",", ";", ".", "?", "!"]
tails = ["", ".", "?", " in 4m.", " took four minutes.", " successfully.", " the migration.",
         " all checks.", " tests.", " checks completed.", ";failed", ",failed now."]
mismatches = []
for i in range(n):
    parts = [random.choice(openers)]
    for _ in range(random.randint(1, 14)):
        parts.append(random.choice(joiners))
        parts.append(random.choice(words))
    msg = "".join(parts) + random.choice(tails)
    payload = {"hook_event_name": "Stop", "last_assistant_message": msg}
    a = oracle.judge(payload); b = cand.judge(payload)
    if (a is None) != (b is None) or (a or "") != (b or ""):
        mismatches.append((msg, a, b))
print(f"FUZZ seed={seed} n={n} mismatches={len(mismatches)}")
for msg, a, b in mismatches[:25]:
    print(f"  oracle={a!r:20} cand={b!r:20} {msg!r}")
