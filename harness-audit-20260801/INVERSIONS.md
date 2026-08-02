# Why the conclusions kept inverting

Nine reversals in one working day, all on the same body of work. Catalogued here because the
*pattern* is more actionable than any individual fix — and because a lesson violated twice
needs a gate, not a restatement.

Each row: what was claimed → what replaced it → the instrument that produced the wrong one.

---

## The catalogue

| # | claimed | corrected to | instrument defect |
|---|---|---|---|
| 1 | skills score **100%**, they work | **1/5** in embedded work | isolated single-turn prompt used to test a claim about work where the skill's topic is a *sub-step* |
| 2 | **keep** the routing table, arm C proves it | **untested** — no arm varied it | concluded *necessity* from a test of *sufficiency*; the table was present in every arm |
| 3 | directive costs **~75 tok**/dispatch | **~1,680 tok**/dispatch | counted the intervention's own bytes, not what it *induces* |
| 4 | skills listing **8,426 B / 16** | **9,033 B / 20** | parser broke early; no second method to check the count against |
| 5 | delivered body **3,088 B** | **2,967 B** | `len(json.dumps(block))` — JSON-escaped, with wrapper — reported as a count of text |
| 6 | 3 **zero-file indexes**, −2,009 tok | stale **content** pasted into an always-on file | classified by a proxy (file count) without opening the file |
| 7 | **3.8 GB free — stop, do not fan out** | **91% free, 0 swap** — safe | `vm_stat` free+inactive ignores reclaimable file cache; `memory_pressure` is the OS's own metric |
| 8 | skills **reach subagents**, migration viable | **all 10 lenses skill-dead** | measured the general case, then applied it to the specific consumer without checking that consumer's config |
| 9 | `agentic-prebid` index is **malformed content** | properly-formed index, just **expensive** | bytes-per-file heuristic, again without opening the file |

## The shape

**Family A — proxy measured, target claimed (1, 2, 6, 7, 8, 9).** Six of nine. In each, a
cheaper measurement stood in for the real one and nobody checked whether its scope matched.

**Family B — unit and parse errors (4, 5).** Both were byte counts. Both would have been
caught by asserting the result against a second method.

**Family C — incomplete model (3).** The cost model had no term for behaviour the
intervention itself creates.

**The signature that matters: all nine resolved in the same direction.** Every correction made
the situation *worse or more complicated* than first reported. Not one simplified. A random
error process does not do that. That is the optimism bias leaving a fingerprint — the loose
instrument fails toward the reassuring answer, and the reassuring answer is the one that ends
inquiry.

## The gates

Not reminders. Each is a mechanical check with a failure mode.

**G1 — State the claim's scope before choosing the instrument.** Write the scope as a
sentence. Then ask of the instrument: *does it measure exactly this, or something adjacent?*
Adjacent means the claim is not yet supported. Catches 1, 6, 7, 8, 9.

**G2 — "Keep X" / "remove X" requires the arm that varies only X.** If no such arm was run,
the supported statement is "untested," never "keep it." Catches 2.

**G3 — Every enumerating parse asserts its count against a second method.** Catches 4.

**G4 — Byte counts of text are `len(text.encode())`.** Never a serialized length. Catches 5.

**G5 — Cost of an intervention = direct + induced.** Ask: *what does this cause to happen more
often, and what does that cost?* Catches 3.

**G6 — Before classifying a file, open it.** File count, size, and name are not contents.
Catches 6 and 9.

**G7 — A general result does not transfer to a specific consumer until that consumer's
configuration is read.** Catches 8 — and it is what turned "migration viable" into "all 10
lenses are skill-dead."

**G8 — When a correction makes things simpler, distrust it.** Given the observed direction of
all nine, a simplifying correction is the anomaly and needs more evidence than a complicating
one, not less.

## What did NOT invert

Worth recording, because a list of only failures distorts the picture:

- **The wire is authoritative.** Every claim made from a `BUN_CONFIG_VERBOSE_FETCH=curl`
  capture held: `Skill` in the roster, descriptions in `msg[1]`, `~/.claude/CLAUDE.md` in
  `msg[0]`, full body delivered on invoke. The instrument matched the claim every time.
- **The `MEMORY.md` auto-injection mechanism** — found via the wire, never revised.
- **The directional result**: skills do not fire unprompted in embedded work, and an
  imperative directive fixes it. Refined three times; never reversed.
- **`route.py`** runs clean: 241 assigned, 0 unassigned, 0 phantom.
- **Step 1** — 5,364 B / 2,009 tok — verified twice by different agents, matching to the token.

The pattern there is as sharp as the failure pattern: **claims built on direct observation of
the actual channel survived; claims built on proxies did not.**
