# Four ready-to-apply fixes — NOT APPLIED

> **CORRECTION 2026-08-02 — two claims in this file are FALSE, verified against the repo.**
> 1. **`"Contract met"` appears in no report.** It is `disposition_ledger.py:372`'s clean-exit
>    banner. Any statement of the form "a report declared Contract met" is a category error —
>    it is detector stdout, not artifact text.
> 2. **`full-review-pr1682-rereview-20260729.md` FOUND the credential BLOCKER** — 1 BLOCKER /
>    13 SHOULD-FIX / 21 NIT, fully disposed at lines 223-225 (`A1`, `A2-A4`, `A5-A6` →
>    FIX-NOW, handed to author). It is not an example of an undisposed finding.
>    **The real miss is one round earlier**: `full-review-pr1682-rereview-20260722.md`
>    (head `cf0d5da32`, 7 specialists including `review-security`) shipped **0 BLOCKER** and
>    credited the PR with *"hardening a latent credential-leak path"* — while all three
>    defect sites existed at that head (`validation_helpers.py:209`,
>    `adcp_a2a_server.py:546,656`, `src/core/tools/governance.py`).
>
> Patch #2's *mechanism* (a document-wide count cannot prove per-finding pairing) stands.
> Its cited example does not. Find a real one before shipping the patch.

All in `prebid/salesagent`, which is gated. Nothing here has been written to that repo.
Each has a control that FAILS before and PASSES after — the control decides, not a claim.
Apply in this order; each is independent.

---

## 1. `disposition_ledger.py:74` — FINDING_TAG is blind to the corpus's own format

**Defect.** The regex requires a bracket. `/full-review` Step 7 prescribes cluster headers and
artifacts write `### Cluster A (BLOCKER)` with parentheses. Corpus-wide the detector sees
**632 of 2,750** raised findings; 8 artifacts declare 161 findings it counts as zero; 3 exit
0 "Contract met" vacuously because `_is_clean:204` treats zero findings as clean.

```diff
-FINDING_TAG = re.compile(r"\[(BLOCKER|SHOULD-FIX|NIT)\b", re.IGNORECASE)
+# Accept both the inline form `[BLOCKER]` and the cluster-header form `(BLOCKER)`
+# that /full-review Step 7 prescribes. Requiring the bracket made the gate blind to
+# 8 artifacts declaring 161 findings.
+FINDING_TAG = re.compile(r"[\[(](BLOCKER|SHOULD-FIX|NIT)\b", re.IGNORECASE)
```

**Control — run before and after:**
```bash
python3 .claude/rules/private/detectors/disposition_ledger.py \
        .claude/reports/full-review-pr1720-20260726.md
# BEFORE: "findings (severity-tagged): 0" + "Contract met"   exit 0
#         (the artifact's own line 9 reads: 1 BLOCKER / 10 SHOULD-FIX / 8 NIT)
# AFTER : non-zero finding count; deficit reflects reality
```
Then re-run `--selftest` — it must still pass.

---

## 2. `disposition_ledger.py:189` — DISPOSITION-COVERAGE is a document-wide count

**Defect.** `deficit = max(0, n_findings - n_dispositions)` counts tokens over the whole
document, so clustering all dispositions under one finding satisfies the gate for all of
them. Confirmed on a shipped artifact: `full-review-pr1682-rereview-20260729.md` reports
15 findings / 96 dispositions / "Contract met" while containing an **undisposed `[BLOCKER]`
about a credential reaching the buyer wire and three persisted sinks.**

**This is not a one-liner.** It needs per-finding block segmentation: split the text on
`FINDING_TAG` boundaries, and require at least one `DISPOSITION_TOKENS` match *inside each
block* (or an Actions-ledger row keyed to that finding's site). Sketch:

```python
blocks = split_on(FINDING_TAG, text)          # one block per severity-tagged finding
undisposed = [b for b in blocks if not DISPOSITION_TOKENS.search(b)
              and not ledger_row_exists_for(b)]
deficit = len(undisposed)                      # and report WHICH, not just how many
```

**Control — three artifacts already built at**
`~/.claude/harness-audit-20260801/experiments/` (`dtest/A-control-good.md`,
`B-control-bad.md`, `C-clustered.md`):
```
A (dispositions distributed)          BEFORE exit 0    AFTER exit 0   (must not regress)
B (3 findings, 0 dispositions)        BEFORE exit 1    AFTER exit 1   (proves it still works)
C (3 findings, 4 tokens under A1)     BEFORE exit 0    AFTER exit 1   <- the fix
```

---

## 3. `bump_check.py:76` — the exit-1 arm is unreachable

**Defect.** `is_stale = "WARNING" in out and "stale" in out.lower()`. **The token `WARNING`
appears nowhere in the detector suite except inside this test condition** (`grep -rn WARNING
detectors/*.py` → 1 hit, this line). The first operand is permanently false, so `stale` is
always empty and `return 1` at `:86` is dead code. It also discards `r.returncode` entirely
— both scanned detectors exit 2 with full `STALE SNAPSHOT (hard fail)` text on **stderr**,
while `_headline` reads only stdout. `harness-upgrade-spec.md:72` prescribes exactly this
unreachable arm as *"the drill to run on every `adcp` bump."*

```diff
     for name, uv, args in DETECTORS:
         r = _run(name, uv, args)
         out = r.stdout + r.stderr
-        is_stale = "WARNING" in out and "stale" in out.lower()
-        if is_stale:
-            stale.append(name)
-        tag = "STALE" if is_stale else "ctx "
-        print(f"  {tag} {name}: {_headline(r.stdout)}")
+        # Key on the exit code the scanned detectors already document (2 = stale/error).
+        # The previous string test gated on "WARNING", which no detector ever emits,
+        # making the exit-1 arm dead code. Read the headline from BOTH streams: the
+        # stale message is written to stderr.
+        is_stale = r.returncode == 2
+        if is_stale:
+            stale.append(name)
+        tag = "STALE" if is_stale else "ctx "
+        print(f"  {tag} {name}: {_headline(out)}")
```
Also fix `main()` (`:47`, `:94`) to accept `argv` — today `--help`, `--selftest`, and a bogus
flag all produce identical output, which is the same false-green class.

**Control:** build a fixture whose pin has moved past both snapshots.
```
BEFORE: exit 0, "Self-tests pass and both spec snapshots are fresh against the current pin."
AFTER : exit 1, naming the stale detector(s)
```

---

## 4. `CLAUDE.md:127` — a live stale spec pin in the always-on context file

**Defect.** Git-tracked, auto-loaded into every session in that repo, wrong on both values:

```diff
-This project targets AdCP spec **3.1.0-beta.3** via the `adcp==5.7.0` Python SDK. See
+This project targets AdCP spec **3.1.1** via the `adcp==6.6.0` Python SDK. See
```
Ground truth: `pyproject.toml:10` → `adcp==6.6.0`; `tests/unit/test_adcp_spec_version.py:5`
→ `EXPECTED_SPEC_VERSION = "3.1.1"`. The file cites that guard three lines later while
contradicting it. `3.1.0-beta.3` + `adcp==5.7.0` is the verbatim stale pair from the #1616
miss-class.

**Control:**
```bash
python3 .claude/rules/private/detectors/citation_freshness.py CLAUDE.md
# BEFORE: exit 1 — "CLAUDE.md:127: stale ['3.1.0-beta.3', '5.7.0'] (pin spec=3.1.1 sdk=6.6.0)"
# AFTER : clean
```

**Related, same class, not patched here** (see `reports/report-close.md` Q3):
`verify-spec/SKILL.md:46,78,148` points at `dist/schemas/3.0.0-beta.3/`;
`protocol_webhook_service.py:40` carries a FIXME whose stated deletion precondition
(`adcp` past 5.4.0) is already met at 6.6.0.

---

## Deliberately NOT included

**The enumeration mandate** (copy §4b.0's one-row-per-site rule into the lens-facing §3).
The effect is real and large — 4%/42% → 84%/94% recall across 4 files, precision 100%,
last-quartile 1/11 → 11/11. But: it costs **1.59x per dispatch ≈ 8% of corpus**, it
contributes **nothing** to retention once the ledger ships, and **the configuration it would
actually ship (cap retained + mandate) was never run** — and is arithmetically
self-contradictory against §3's own ≤6-line template. It needs its own experiment and its
own decision, not inclusion in a batch of gate repairs.
