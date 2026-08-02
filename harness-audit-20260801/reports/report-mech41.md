All measurements done. Here is the report.

---

# Validating the 41-rule mechanizable backlog

**Verdict: 4 survive as things worth building, and 2 of those 4 are not detectors — they are config lines. Two more are worth building only if reframed away from being gates. The other 35 fail the occurrence filter, the determinism test, or both.**

The reframing that produced this: for these rules, occurrence alone proves nothing. Every one of the 80 rules exists *because* something happened — they were distilled from memory files, and a memory file is written after an incident. So "has it ever occurred" is satisfied by construction and is not a filter. The filter that discriminates is **occurrence × non-compliance**: does the corpus show the rule being *violated* after it existed, or does it show the rule being *obeyed* at high frequency? A rule at 5,000 firings and full compliance needs a shortcut, not a gate. A rule at 3 firings and 100% violation needs a gate.

I measured compliance, not just occurrence, wherever the artifacts made it possible.

---

## Tier A — build these four

### A1. `[88,28]` Outbound-op permission entries — **cost 5, and it is four lines of JSON**

**Would it have fired?** It is firing right now, silently. Every settings file, read directly:

| file | `ask` | `deny` |
|---|---|---|
| `/Users/quantum/.claude/settings.json` | `Agent`, `Task` | *(empty)* |
| `salesagent/.claude/settings.json` | *(empty)* | *(empty)* |
| `salesagent/.claude/settings.local.json` | `git commit`, **`git push`**, `git reset`, `git rebase`, `git merge`, `git cherry-pick`, `git branch -d/-D` | *(empty)* |

`allow` in `.claude/settings.local.json` contains `Bash(git:*)`, `Bash(gh:*)`, and `Bash(gh pr:*)`. The rule names five outbound operations. **`git push` is gated. `gh pr create`, `gh pr merge`, `gh pr comment` and `gh issue create` are not gated anywhere — they are explicitly pre-approved, and `deny` is empty in all three files.** Corpus counts of unique command strings: `gh pr comment` **100**, `gh issue create` **25**, `gh api --method POST` **6**, `gh pr create` **5**, `git push` 7.

This is the highest-cost rule class on the list (cost 5, harness-critical, a trust boundary), mechanized for one of five commands, with the other four allow-listed by name.

**Determinism:** total. The permission layer either prompts or it does not.

**The false-green:** prefix matching is not command parsing. `Bash(gh pr comment:*)` does not cover `gh api repos/o/r/issues/N/comments --method POST` (6 occurrences already in the corpus), nor `gh` reached through a variable, a heredoc, or a `&&` chain where `gh pr comment` is not the leading token. A rule set that gates the literal spelling and reports itself green is precisely the argv-unparsed failure mode. Gate `Bash(gh api:*)` with a POST/PATCH/DELETE `ask` as well, and accept that shell indirection is uncoverable — state that limit rather than implying completeness.

**Positive control:** a `gh pr comment` invocation must prompt; **and** a `gh api --method POST` invocation must prompt. Negative: `gh pr view`, `gh run list`, `git log` must not. Both arms must be exercised, because a `deny` regex broad enough to catch the POST form is also broad enough to block every read.

Bundle `[53,93]` (bulk auto-rewriter) into the same change — `deny` on `--unsafe-fixes`, `pyupgrade`, `isort`. It has **zero recurrences in the entire command corpus** (grep for `unsafe-fixes|pyupgrade|isort` returns 0 across 48,048 unique command strings), so it does not earn its own line item, but it is free inside an edit already being made, and it is cost 5. Same false-green: it matches spellings, not intent.

### A2. `[56]` Personal harness stays out of the shared repo — **cost 5, and it needs one ignore line, not a detector**

**Would it have fired?** It already failed, and the damage is still in the tree. `git ls-files .claude/notes` returns **27 tracked files**; `.claude/reports` returns 1. Eleven of them landed on a single day inside two large commits:

- `9ac08dad3` — *"feat: UC-002/003 validation wiring + canonical error-code reconciliation on adcp 5.7 (#1417)"*, **239 files changed**, of which **9 are `.claude/notes/`** including `pr1417-reply-draft.md`, `pr1417-reply-rereview.md`, `session-2026-07-08-1417-review-fixes.md`, `session-pr1417-rereview-batch2-20260701.md`.
- `d1e69d717` — *"test: transport-aware BDD harness (#1430)"*, 112 files, **2 more `.claude/notes/`**.

That is the `git add -A` sweep the rule exists to prevent, twice, inside review-session artifacts. Re-confirmed today: `git check-ignore .claude/reports` → rc=1, `.claude/notes` → rc=1 (not ignored), while `.claude/rules/private` → rc=0 and `.claude/worktrees` → rc=0 via `.git/info/exclude:12`.

**The honest recommendation is not a detector.** `.claude/worktrees/` is already handled by one line in `.git/info/exclude`. Adding `.claude/reports/` and `.claude/notes/` to the same file is the entire fix, costs nothing, and cannot lie green. `review-charter.md:96` currently spends prose on *"never stage with `-A`"* — the file that documents the workaround should be replaced by the two lines that make the workaround unnecessary.

**If you build the hook anyway, its false-green is severe and worth stating:** a `PreToolUse` hook on `Write`/`Edit` does not see files created by `Bash` — `>`, `>>`, `tee`, `cp`, `python -c "...write..."`. Review artifacts in this corpus are frequently produced by Bash redirect. A hook that covers Write/Edit and reports itself as enforcing the invariant is covering a minority of the creation paths. This is the same scan-set defect that let a live stale pin sit in `CLAUDE.md` outside `citation_freshness`'s roots.

**Positive control:** `Write` to `.claude/reports/x.md` blocked; `Write` to `.claude/rules/private/y.py` allowed; **and** a `Bash` heredoc to `.claude/reports/z.md` — which must be shown either blocked or explicitly declared out of scope in the hook's own output.

### A3. `[22,3,2]` Fan-out disk/docker preflight — **cost 5, numeric, recurring**

**Would it have fired?** Yes, on 2026-07-30, during a live review: `.claude/reports/full-review-pr1675-rereview-20260730.md:235` — *"**Disk sat at 98% (11 GiB free) throughout.** No ENOSPC symptoms appeared and every run completed, but per the tooling reference that is the threshold where tooling starts lying."* And `.claude/reports/full-review-pr1547-rereview-20260730.md:881` records the same hazard being weighed. The corpus contains an explicit ENOSPC probe (`"--- can a new file be created? (ENOSPC probe) ---"`) and a `gh run view --log | grep "No space left"` — the condition is being hunted, by hand, after the fact.

I also found a live contributor nobody has mentioned: **`.claude/worktrees/` holds three leftover agent worktrees, 1.2 GB, all clean, all detached at `e5f674e38`, last touched 2026-07-30** — the harness's own `isolation: "worktree"` copies, which the tooling documents as auto-cleaned when unchanged. They were unchanged and are still there. `git worktree list` shows **29 registered worktrees** total. The disk pressure the rule guards against is partly self-inflicted by the fan-out mechanism itself.

**Determinism:** a percentage against a threshold. The rule even names the exact target — `df -h /System/Volumes/Data`, not `/` — and prior measurement found 33 of 140 invocations using the wrong one. My independent count of unique command strings: **49 of 57 `df` calls now use the correct target**, so this half is improving under prose.

**The false-green:** `df` reports the *filesystem*, and macOS APFS containers share space across volumes; a threshold met on `/System/Volumes/Data` says nothing about a Docker.raw disk image that is separately capped. A hook that checks one number and prints "preflight OK" asserts a readiness it did not measure. It must print both the number and the volume it measured — the scan set — and treat `docker info` failure as a hard stop, not a warning.

**Positive control:** set the threshold to 99.99% and assert the `Agent` dispatch is blocked with the free-space number in the message; set it to 0% and assert it proceeds; stop the Docker daemon (or point `DOCKER_HOST` at a dead socket) and assert a block. The middle case is what most hooks skip, and it is the one that proves the hook is reading the number rather than always passing.

### A4. `[106]` Finding-ID reuse across review rounds — **cost 4, 3 real occurrences, the only true detector on this list**

**Would it have fired?** Yes — three times in 27 multi-round PRs (11%), and I confirmed each by reading the finding bodies rather than trusting the ID collision:

| PR | round 1 | round 2 | same ID, different finding |
|---|---|---|---|
| 1665 | `N1 [NIT][code-patterns + bdd]` *Cross-script xpass vocabulary divergence* (07-21) | `N1 [test-integrity]` *`_append_if_new` intra-call `existing_keys.add(key)` unpinned* (07-22) | yes — consecutive days |
| 1720 | `A2 [SHOULD-FIX]` *`error.recovery` absent from every error on these six methods* (07-28) | `A2 [NIT] [error-wire + main-session]` (07-29) | yes — severity also changed |
| 1697 | `SF1`–`SF4` (07-23) | `SF1`–`SF4` (07-23, later) | yes |

A reviewer or contributor referring to "A2 on 1720" is ambiguous across a one-day gap, and the ledger that reconciles rounds is keyed on exactly these IDs.

**Determinism, and the residue:** the set intersection is exact. The residue is that an ID *carried forward unchanged* is also a collision, and distinguishing "same finding, still open" from "new finding, recycled ID" requires comparing bodies. Narrow but real. Resolve it by requiring the carried-forward case to be explicitly marked rather than inferred.

**The false-green — and I hit it myself while measuring.** My extraction regex is `\*\*([A-Z]{1,3}\d{1,2}[a-z]?) \[`. Any artifact that writes `**BLOCKER — A2 …**` instead of `**A2 [BLOCKER]…**` yields **zero IDs and passes clean**. That is bit-for-bit the `disposition_ledger` N2 defeat, where an unbracketed severity zeroes three checks at once and prints "Contract met". Any ID detector must **return 2 when it extracts zero IDs from a non-empty artifact**, never 0.

**Positive control:** two fixtures for the same PR sharing `A2` with different bodies must trip. Negative: two rounds with disjoint IDs must pass. Third, mandatory: an artifact with findings written in an unmodelled heading form must exit 2, not 0.

---

## Tier B — build, but not as a gate

### B1. `[6,91,90,97]` `repo_state.py` — a cost reduction, and it should be sold as one

**No correctness gap found.** I looked for wrong state claims and found the opposite: the artifacts carry a standardized footer, e.g. `full-review-pr1719-rereview-20260728.md:218` — *"origin head for the branch: `a26c2c50…`; local-only commits: none — nothing was written to any tree… Worktree `../salesagent-wt-pr1719` HEAD asserted at the PR head with an empty porcelain before and after every read"*; `pr1697-rereview2:86`; `pr1546:162`; `pr1621:150`. The discipline is visibly held on every report I sampled.

What is *not* held is the cost: ~5,254 hand-assembled state queries (2,461 `--porcelain`, 1,933 `rev-parse`, 520 local-vs-origin, 340 `mergeStateStatus`), 6,022 of 7,344 unique command strings compound. The model rebuilds the same composite report thousands of times.

Build it, but do not claim it closes a gap — it closes an expense. And its exit code must come from structured fields (`porcelain == ""`, `HEAD == expected`, `mergeStateStatus != "DIRTY"`, `len(runs) > 0`), never from grepping its own printed output. That is `bump_check`'s exact defect: `is_stale = "WARNING" in out and …` where **no detector on disk ever emits the token `WARNING`**, making its entire exit-1 arm dead code while it printed reassurance quoted in five shipped artifacts.

### B2. `[13,55]` `sibling_sweep.py` — a worklist generator, never a verdict

This is ranked #1 on the backlog and it has the **strongest occurrence record of any rule on the list** — at least six documented incomplete sweeps, including one where the review's own prior round missed them:

- `full-review-pr1544-rereview-20260723.md:49` — *"**the SF1 sweep missed the cross-read siblings** (charter §4c-3)"*
- `pr1544-comment-20260721.md:24` — the log-injection fix applied at 14 + 18 sites, **not** at the sibling approve/reject routes (`workflows.py:278,284`, `creatives.py:641,643`, 0 sanitized sites in either)
- `full-review-pr1650-rereview-20260721.md:36` — *"Sibling advisory sites emit an incoherent `(SERVICE_UNAVAILABLE, terminal)` pair — the same defect class this PR fixes, unfixed"*
- `full-review-pr1567-rereview-20260710.md:6`, `full-review-pr1575-rereview-20260720.md:103`, `full-review-pr1719-rereview-20260728.md:47` (*"the fix does not reach the class"*)

**And yet it must not be a gate, for two reasons I can quantify.**

First, precision. `full-review-pr1575-rereview-20260720.md:103` shows the adjudication in full: the sweep produced five candidates; **one** was a real serving-concept sibling (`operations.py:219`); `api.py:67` and `dashboard_service.py:74,192` were *"plausibly a different concept (revenue recognition)"*; `creatives.py:56` was *"a genuinely different concept (#1038 liveness)"*. Roughly 1 in 5 candidates survived. A tool that emits a verdict at that precision is a false-red machine; a tool that emits an adjudicated candidate list is exactly what the reviewer already builds by hand.

Second, and more important: **the proposed check `assert N==0 at HEAD after the fix` is defeated by whoever chooses the pattern, and that is the same agent being checked.** A rule whose determinism depends on an input the checked party supplies is not a gate. Narrow the regex and the sweep goes green. This is the sharpest determinism failure on the entire backlog, and it applies to any "prove you swept it" detector.

Build it as `sibling_sweep.py --pattern P` that prints N and every `path:line` and **exits 0 always**, with a mandatory per-candidate disposition slot. Do not give it an exit code, because an exit code here is a lie with a number attached.

---

## The 35 rejections, grouped by why

**Rejected — measured at or near zero violations; the prose is holding (11 rules).** Each of these was checked against the shipped corpus, not assumed:

| rule | measurement |
|---|---|
| `[24]` no `/tmp` paths in reports | **0** in any outbound draft. The 10 files containing `/tmp` are legitimate: a security finding *about* `inspect_parallel.sh:29` writing to a fixed `/tmp` path (`pr1665-rereview-20260730:388`), and raw `<output-file>` headers in `pr1312-fleet/`. A regex here fires on real findings. |
| `[58]`,`[14 partial]` mandatory sections | **59 of 60** full-review reports carry a could-not-verify / not-run footer. The single miss is `full-review-pr1534-20260711.md`, the second-oldest report in the set. |
| `[17]` gratitude openers | **0** in every `*comment*` / `*posting*` artifact. |
| `[43,50]` cheap-win framing | **0** across `.claude/reports/` and `.claude/notes/`. |
| `[42]` fenced not blockquote | **0** `^> ` in any pasteable draft. |
| `[12]` confession markers | The two phrases the rule names — `keep in sync`, `only verifies setup` — have **0** hits in `src/**.py`. The broad patterns are dominated by legitimate use: 209 `placeholder`, 32 `for now`, and all 4 `stay in sync` hits are docstrings *praising* SDK inheritance (`creative.py:523` *"ensuring we stay in sync with spec updates"*). Inverted-polarity noise. |
| `[46,49]` PR numbers in code comments | 92 live in `src/`, but blame attributes **76 to Constantine Mirin and 6 to Chris Huie**. More decisively, a shipped review already adjudicated the convention: `pr1616-rereview-2026-07-28.md` — *"`(#1508)` in an added `src/` code comment: **conforms** to repo practice — broadened grep finds 29 pre-existing non-FIXME `(#NNN)` refs in `src/`"*. A detector would fight the house. Cost 2, the lowest tier on the list. |
| `[66]` two-dot and three-dot | Held and reported: every report header declares its diff range (`pr1665-rereview-20260721:3` *"three-dot"*, `:22 "two-dot vs CURRENT main"`), and `:52-53` shows it finding two genuinely already-upstream commits. The value is the adjudication, not the two `git diff` calls. |
| `[92]` prove pre-existing | Held: `pr1650-rereview-20260721:39` — *"**pre-existing** (blame 5f2245e9b2 2026-06-08; pickaxe empty in the PR range)"*. My proximity heuristic scored 21.6% compliance across 1,019 mentions, but reading the misses showed the heuristic wrong, not the practice: `pr1547-rereview-2026-07-30-orchestrator.md` proves provenance with `git diff base..HEAD -- src/app.py`, a valid method my regex did not model. I am reporting my own measurement as unreliable rather than the rule as violated. |
| `[53,93]` bulk auto-rewriter | **0** occurrences of `unsafe-fixes`/`pyupgrade`/`isort` in 48,048 unique command strings. Folded into A1 as a free `deny` line, not as its own build. |
| `[105]` `git grep -E` vs `\b` | 0 violations in 5,363 `git grep` calls, per prior measurement. |

**Rejected — the check itself produces unusable noise (2 rules).**

`[16]` grep repo-wide for every new def: I built the index and ran it. Within `src/` alone, **2,393 names are defined in more than one file**. Repo-wide, 7,924 non-dunder non-test names collide. "Report any name added by the diff that already exists elsewhere" has no signal at that floor. (The full-tree scan also picked up the three `.claude/worktrees/` copies of `src/` — 14,386 names appearing in exactly 4 files — which is itself the scan-set defect, live, in a five-minute prototype.)

`[78]` allowlist entries reachable from production: I ran the reachability check. **Zero real violations.** Of the 31 entries I could extract, 3 symbol-shaped entries all resolve in `src/`, and the two "stale paths" my prototype flagged — `enum_helpers.py` and `core/idempotency_canonical.py` — are **both false positives**: the allowlists are relative to `src/core/` and `src/` respectively (`test_architecture_enum_value_normalization.py:35`, `test_architecture_sdk_idempotency_seam.py:21`), and both files exist. My extractor also failed to model 19 of 48 allowlist collections (`UNMODELLED:Call`, `UNMODELLED:BinOp`) — a 40% scan-set gap. In fifteen minutes this prototype produced two confident wrong findings and silently skipped 40% of its input. That is the whole argument against building it.

**Rejected — high non-compliance but zero recorded harm (2 rules).** These are the two I would most like to be wrong about.

`[37]` the `-k` selector claim: 59 unique `pytest -k` command strings, **4 paired with a `--collect-only` baseline** (7%). `[108]` never judge from the runner tail: 133 `run_all_tests`/`make quality`/`tox` calls vs **21** reads of `test-results/*.json` (16%). Both look like live gaps. But I searched the entire artifact corpus for the harm — `empty red set`, `nothing failed`, `selected 0`, `collected 0`, `tox banner`, `terminal tail` — and found **nothing**. Non-compliance with a rule whose violation has never been observed to produce a wrong conclusion is not evidence the gate is needed; it may be evidence the rule is over-specified. If someone can produce one artifact where an empty red set or a tox banner produced a wrong verdict, `[37]` moves to Tier A immediately — the check ("did the selector select anything") is a count, and the positive control is trivial.

**Rejected — low firing, deterministic but not worth the verification burden (8 rules).** `[1,10]` `;` not `&&` before cleanup: **1** occurrence of `&& git stash pop`, 3 stash pops total. `[23]` branch first: 6 branch cuts. `[98]` `git mv` + old path: 6. `[34]` confirm the PR number, `[26]` run flaky tests 5×, `[8]` gated CI no-op (52), `[21]` exception-tuple reuse, `[20]` missing-test row.

**Rejected — belongs to judgment, restated (7 rules).** `[38,82]` helper needs a production caller — the floor is a grep but `N adopted / M eligible` is the finding, and the floor without the ratio is noise at this repo's duplication level. `[57,44]` plan-approval gate — "ambiguous stage means planning" is the whole rule and it is a judgment about intent; a path allowlist gates edits without knowing the stage. `[19,27,51]` memory hygiene — 169 memory files; "is this a cross-session pattern or a per-PR snapshot" is the judgment, and `#\d{3,4}` catches the easy 10%. `[40]` don't alarm mid-operation, `[54]` re-mutation-test (the oracle registry does not exist; building it is the whole cost), `[77]` full suite after the first CI surprise, `[31]` pos+neg self-tests — this last one is not a detector, it is the house standard, below.

**Rejected — already adequately handled (5 rules).** `[80,81,104]` dispatch mechanics: I could not independently confirm the violation rates because `agent-dispatches.json` truncates **all 851 prompts to exactly 700 characters** — my Step-0 measurement (579/851 present) is bounded by truncation and my `SendMessage` measurement (0/851) is an artifact of it, not a finding. The `model`-parameter half (30/859) is exact and worth one line in a dispatch hook, but not a detector. `[33,47,103]`, `[39,87]`, `[25 anchor half]` (74% anchored, and the residue — *"a refused anchor is a SCOPE signal"* — means the remainder is not violation), `[107]` SDK model surface.

---

## The house standard — the thing worth more than any detector

Twelve of thirteen detectors carry a confirmed defect. Across the two execution reports I count **32 distinct defects**, and they collapse into **eleven failure classes**. The critical observation is what they are *not*: these self-tests are not lazy. `citation_freshness` runs 22 cases including file-iteration and a verbatim regression corpus; `disposition_ledger` has an explicit precision arm with the comment *"Each case below keeps a matching NEGATIVE so precision cannot be bought with blindness"*; `compound_guard_operands` drives `main()` end-to-end because a leaf-only self-test once said 13/13 on a detector that crashed on invocation.

**They already meet the "positive and negative self-test" bar. That bar is not what failed.**

What failed is that every self-test is a closed case table, written by the same author, in the same sitting, from the same mental model of the input — and every confirmed false-green lives in a form the author never imagined: `not (a or b)`, an unbracketed severity, a line break between a heading and a version token, `CLAUDE.md` sitting outside the default roots, a base ref that does not resolve. **You cannot test your way out of an unimagined input form, because the negative cases come from the same imagination as the positives.** So the standard cannot be "write more tests." It has to be structural — properties another program can check about the detector's *shape*.

### The checklist

Nine rules. Each is mechanically checkable, and I have named the defects each one kills.

1. **Derive every list at runtime; never enumerate.** Any hardcoded set of names, codes, paths, or versions must be computed from the filesystem, the SDK, or the pin at execution time, or carry a self-check that hard-fails on drift. *Kills:* `disposition_ledger`'s 9-of-13 stale detector-name list; `suggestion_audit`'s 64-code frozen fixture against a 92-code live pin, which its docstring claims "moves with the repo pin, no separate snapshot to rot."

2. **Declare the scan set in the output, and exit 2 when it is empty.** Every run prints what it looked at — roots, file count, base ref, resolved commit. Zero inputs is an error, never a clean verdict. *Kills:* the live stale `3.1.0-beta.3`/`adcp==5.7.0` pair sitting in `CLAUDE.md:127` outside `citation_freshness`'s roots; `fixme_format`'s silent all-clear when run from a subdirectory (`repo = Path.cwd()`); `changed_field_grading_coverage`'s confident green on an unresolvable `origin/main`; `github_workflow_duplication`'s `roots = [r for r in roots if r.exists()] or roots`, where a typo'd path yields "0 run-bodies scanned" and rc=0.

3. **The exit code comes from the structured return, never from the printed text.** No `"TOKEN" in output`. If a sub-tool is invoked, propagate its `returncode` and read both streams. *Kills:* `bump_check`'s `is_stale = "WARNING" in out and …` — a token that appears in **none** of the 13 detectors, making `return 1` unreachable while it printed "both spec snapshots are fresh" over two children that had each exited 2 with `STALE SNAPSHOT (hard fail)` on stderr; `ssot_docstring_duplication --base`, which prints `✗ SSOT-CONTRADICTED (1)` and exits 0.

4. **Parse argv, and fail on anything unrecognized.** Including `--flag=value` forms. `--help` must print help. *Kills:* `bump_check`, which reads `sys.argv` not at all and returns rc=2 with identical output for `--help`, `--selftest`, and `--totally-bogus-flag`; `fixme_format`, where a typo'd `--selftests` runs a full scan and prints "No non-compliant FIXME markers found," indistinguishable from a passing self-test; the silently-dropped `--base=`, `--fields=`, `--scope=` equals-forms in `changed_field_grading_coverage` and `recovery_audit`. `disposition_ledger:324-331` already diagnosed and fixed this *in itself* — *"an UNRECOGNISED flag used to be silently ignored… a false green in the one tool whose job is catching false greens"* — and the fix was never propagated.

5. **Every gate that can be skipped must announce the skip and return 2.** No `if x and x != Y:` where a falsy `x` silently means "pass." *Kills:* `recovery_audit`'s `if pin and pin != SNAPSHOT_SPEC_VERSION`, where a renamed accessor — most likely precisely during a bump, the one moment the gate matters — prints the full CLEAN text with no mention that the freshness check never ran; the same shape in `sdk_spec_drift:211` on an empty-string pin.

6. **Assert per item, never in aggregate.** Counts of X versus counts of Y across a document prove nothing about the pairing. *Kills:* `disposition_ledger`'s `deficit = max(0, n_findings - n_dispositions)` over the whole artifact — 3 findings, all 4 tokens clustered under the first, `deficit=0`, `clean=True`; the same detector's `LEDGER_HEADING` matching the sentence *"No Actions ledger was produced for this round"*; an ordinary `"Summary: 1 FIX-NOW, 1 FOLD-IN, 1 FOLLOW-UP."` line padding the count while all three real dispositions are charter-banned hedges; `github_workflow_duplication`'s longest-*contiguous*-run score, where one inserted line reports a 9-of-10-identical clone between two signature verifiers as clean.

7. **Normalize before matching; enumerate equivalent forms in a table the code walks, not in prose.** Unwrap negation, resolve dotted prefixes, qualify names by scope, widen the context window past a single line. *Kills:* `compound_guard_operands` missing `not (a or b)`, `bool(a or b)`, `lambda: a or b`, `x |= a or b`, dict values and bare expressions — where the positive control and its exact De Morgan rewrite differ only in exit code; `citation_freshness` requiring the context token on the same physical line as the version, defeated by one line break, its #1616 regression case passing only because the fixture happens to be single-line; `pr_import_cycle:104`'s `node.level == 0`, which drops **62 relative imports across 17 `src/` files** from the graph; `recovery_audit`'s `raise TaskNotFoundError(` matching only the undotted, called form while the module is literally `a2a.utils.errors`; `fixme_format` blind to `# FIXME (` with one space; `ssot_docstring_duplication` indexing bare `node.name`, making 5 of its 7 live findings cross-scope collisions.

8. **The docstring may not claim a completeness the code does not have.** Every scope limit is stated in the *output*, not only in the source header. *Kills:* `suggestion_audit`'s *"reaches the wire two ways, and BOTH are audited here"* against **48 inline `suggestion="…"` literals at raise sites** across 10 files that neither surface touches; `pr_import_cycle`'s unqualified "No first-party import cycles found" over a 2-module pairwise scan; `ssot_docstring_duplication` positively asserting a name is "unique-named" when one file defines it twice and the second definition shadows the first. `recovery_audit` is the counter-example that proves the rule is achievable — it documents its own condition-blindness, and the two artifacts quoting it (`pr1719-ledger-2026-07-28.md:68`, `full-review-pr1720-rereview-20260728.md:100`) both cite the limitation instead of the clean verdict.

9. **Something automatic runs every self-test, and the meta-runner is itself covered.** *Kills:* the finding that `grep -rlE 'detectors/|--selftest|--self-test' .github/ Makefile tests/ scripts/` returns **nothing**, and the only aggregate runner — `bump_check` — lists **4 of 13**, omitting `disposition_ledger` and `ssot_docstring_duplication`, the first- and third-most-invoked. Nine detectors' self-tests run only when a human types the flag.

### The one thing that makes this standard different from the prose it replaces

Rules 1–9 are all statically checkable. Write them as `detector_lint.py`: walk `detectors/*.py`, and for each one assert that argv is parsed and rejects unknowns; that no module-level literal collection is used as ground truth without a drift check; that every `return`/`SystemExit` path is reachable from a structured value rather than a string membership test; that the output includes a scan-set line; that a `--selftest` entry point exists; and that the zero-input path returns 2. Then run `detector_lint.py` **and** all 13 self-tests from one command that CI or a `Stop` hook invokes.

Otherwise this document becomes the thirty-ninth mandatory read in a charter that already ships 3.35M tokens of detector-restating prose 738 times — a rule about mechanization that nothing mechanizes. `[19,27,51]`'s own detail line already states the principle and it is the right one to end on: *"Leverage runs soft memory < turn instruction < CLAUDE.md < a mechanical gate that FAILS."*

---

## What I could not verify

- **Dispatch-mechanics rates `[80,81,104]`.** `agent-dispatches.json` truncates every prompt to exactly 700 characters, so my Step-0 (579/851) and SendMessage (0/851) counts are artifacts of the extract, not measurements. The prior report's figures came from full transcripts; I neither confirmed nor challenged them.
- **Whether the 11 leaked `.claude/notes/` files were staged by Chris or by the PR author.** Both commits are squash merges authored by Constantine Mirin. The files are review-side artifacts, which suggests Chris's tree, but I could not establish the staging path, and the fix (an ignore line on this machine) is unaffected either way.
- **`[37]` and `[108]` harm.** I proved the non-compliance rates (7% and 16% respectively) and searched the full artifact corpus for a resulting wrong conclusion. Absence of a recorded miss is not proof there was none — these artifacts record what the reviewer noticed.
- **Whether the 90 tracked `tests/unit/test_architecture_*.py` guards violate `[56]`'s second clause** ("enforce conventions in a private detector, never a repo guard"). Many predate the rule and appear to be agreed project-level guards. Distinguishing "personal tooling that leaked into everyone's CI" from "an agreed shared guard" is judgment I did not have grounds to exercise.
- **`git grep -c` on the deduped `bash-commands.txt` counts unique command strings, not invocations.** Where I cite raw firing frequencies (5,363 `git grep`, 5,254 state queries, 490 `pytest -k`) those are the prior report's deduped corpus counts; where I cite my own (100 `gh pr comment`, 59 `pytest -k`, 57 `df`) those are unique strings and are lower bounds on invocations.
- **The three leftover worktrees.** All clean at `e5f674e38`, which is neither current HEAD (`6881e8da4`) nor current main (`d912a7ee9`). Whether that SHA was the launching HEAD on 2026-07-30 — the specific hazard `[33,47,103]` names — I could not reconstruct.