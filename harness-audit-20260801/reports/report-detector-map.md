All measurements done. Here is the report.

---

# Detector ↔ rule map: what is mechanized, what should be, what can't be

**Corpus:** 1,018 transcripts (159 main + 859 subagent), all July 2026. **13** detectors, not 12 — `FACTS.md:66` undercounts by one (the 3,422-line total is right; there are 13 `.py` files in `.claude/rules/private/detectors/`).

**Correction to FACTS.md:66 / pass-1 Bash stats.** "7,475 Bash calls" is **main-thread only** (7,475 records / 7,391 unique tool_use ids). Corpus-wide the count is **38,451** — subagents contribute 31,060 (81%), with **zero** id overlap between main and subagent files. Trap #2 was applied to cost accounting but not to tool-call accounting. Every mechanization payback below is ~5x larger than pass-1 implied.

---

## Part 1 — Are the 12 (13) detectors used? Yes. 1,160 invocations. One is dormant.

Counted as Bash `tool_use` whose command matches `<name>\.py`, deduped by tool_use id, split by the invoking agent's `agentType` from `*/subagents/*.meta.json`.

| detector | total | MAIN | spec-conf | test-int | code-pat | arch-grd | err-wire | bdd | sec | sessions |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| disposition_ledger | **225** | 225 | · | · | · | · | · | · | · | 72 |
| citation_freshness | **189** | 85 | 87 | 1 | 3 | 8 | 3 | · | 1 | 105 |
| ssot_docstring_duplication | **159** | 52 | · | 69 | 35 | 2 | 1 | · | · | 97 |
| recovery_audit | **143** | 69 | 52 | · | · | · | 21 | 1 | · | 78 |
| review_completeness | **138** | 134 | 3 | · | · | · | · | 1 | · | 62 |
| compound_guard_operands | **61** | 39 | · | 11 | · | 2 | 8 | · | 1 | 29 |
| pr_import_cycle | **52** | 23 | · | · | 28 | 1 | · | · | · | 43 |
| fixme_format | **51** | 8 | · | · | 1 | 42 | · | · | · | 44 |
| sdk_spec_drift | **46** | 23 | 22 | · | · | · | 1 | · | · | 35 |
| suggestion_audit | **37** | 18 | 1 | · | · | · | 18 | · | · | 19 |
| changed_field_grading_coverage | **32** | 11 | 19 | · | · | · | · | 2 | · | 25 |
| bump_check | **24** | 20 | 4 | · | · | · | · | · | · | 19 |
| **github_workflow_duplication** | **3** | 2 | · | · | 1 | · | · | · | · | **2** |
| **TOTAL** | **1,160** | 709 | 188 | 81 | 68 | 55 | 52 | 4 | 2 | |

**Never meaningfully invoked: `github_workflow_duplication.py`.** 3 runs on 2 days — one is 2026-07-23, its own authoring date (docstring `:1-13` cites "PR #1669 review, 2026-07-23"), the other a single run on 07-28. Every other detector shows use spread across 7-13 distinct days. It is 275 lines of pure cost.

**Invoked constantly: `disposition_ledger` (225) and `citation_freshness` (189)** — and `ssot_docstring_duplication` has the widest reach (97 distinct sessions).

**Three findings the per-detector count hides:**

1. **`disposition_ledger` is 100% main-thread. Zero lens invocations across 738 dispatches.** It is an orchestrator tool. `review_completeness` is 97% main-thread (4 lens runs). Both are described at length in the charter every lens agent must read — see Part 3.
2. **Three of eight lenses run essentially no detectors:** `review-bdd` 4 runs / 85 dispatches, `review-security` 2 / 85, `review-admin-ui` **0 / 19**. That is 189 dispatches and 6 detector runs. Either those lenses have no mechanizable surface (plausible for admin-ui) or their detectors were never built (`changed_field_grading_coverage` exists *for* the bdd blind spot and bdd ran it twice; spec-conformance ran it 19 times).
3. **`review-spec-conformance` is the detector-heavy lens** — 188 runs / 112 dispatches = 1.68 per dispatch, vs 0.02-0.05 for security/bdd.

---

## Part 2 — The three-way map (all 80 rules)

**Totals: COVERED 13 · MECHANIZABLE-MISSING 41 · MUST-STAY-PROSE 25 · N/A 1** (rule `[100]`, DEMOTE-T3, is project state not a rule).

### COVERED — a detector already enforces the rule's mechanical core (13)

| rule ids | detector + line | note |
|---|---|---|
| `[63,64,99]` three-endpoint re-pull + GraphQL threads | `review_completeness.py:113-128` pulls reviews/comments/issue-comments/reviewThreads; `:154-155` gates unresolved in **both** states | Fully covered. Charter §4c.6 verdict-stamping is not. |
| `[41]` no author filter on first pass | `review_completeness.py:130-141` builds `events` from all three endpoints with no filter; `:174` prints authors | Clean. |
| `[75]` compound-guard operand coverage | `compound_guard_operands.py` entire; `:145-157` scan, `:194-199` prints "NOT evaluated when an earlier operand short-circuits" | Surfacing covered; the judgement is the documented residue (`:19-21`). |
| `[48]` ban "optional"/"non-blocking" as disposition | `disposition_ledger.py:78` BANNED, `:172-197` audit | **Has a false green** — see Part 4. |
| `[68]` preserve every site through consolidation | `disposition_ledger.py:161-169` `dropped_sites()` | Site half covered; cross-agent *unification* explicitly not attempted (`:26-27`). |
| `[45]` no internal vocab in outbound artifacts | `disposition_ledger.py:85-93` INTERNAL_VOCAB, `:183-187`, `:229-234` | **Partial** — misses 4 of 13 detector names and "meets our bar". Part 4. |
| `[15]` state the scan set with the verdict | `compound_guard_operands.py:206-215`, `citation_freshness.py:314-316` | Covered by convention in ~half the detectors, not universally. |
| `[101]` per-wheel SDK→spec mapping | `citation_freshness.py:65-77` `derive_pins()` calls `adcp.get_adcp_spec_version()` first; `sdk_spec_drift.py` hard-fails on snapshot/pin drift; `bump_check.py` runs both | Strong. |
| `[65]` recovery-coherence never closes the recovery question | `recovery_audit.py` — and the detector's own docstring states this exact limit ("condition-blindness — the #1698 miss-class") | The rule *is* the detector's documented residue. |
| `[30,102]` AdCP spec grounding | `citation_freshness.py:50-62` (version half), `sdk_spec_drift.py` (SDK-is-derived half) | Version-citation covered; "prose is the authority" stays prose. |
| `[107]` verify an SDK bump surface-by-surface | `sdk_spec_drift.py` | **Enum only.** Pydantic model surface uncovered → see backlog. |
| `[73,76]` semantic SSOT | `ssot_docstring_duplication.py:86-93` check A | Name-twins covered; shape-twins explicitly unprovable (`:28-29`). |
| `[67]` re-check live head after fan-out | `review_completeness.py:148`, `:165-170` `_head_delta` | Re-check covered (`--head` passed 104/138 runs); pin-on-dispatch is not. |

Prose in the charter/skills restating these 13 is redundant cost — quantified in Part 3.

### MECHANIZABLE-MISSING — the build backlog (41), ranked

Rank = `cost_of_forgetting` × measured firing frequency (deduped corpus counts). Firing counts are Bash `tool_use` matches — the hand-rolled operation the detector would replace.

| # | rule ids | cost | measured firing | the check, and what makes it deterministic |
|--:|---|--:|---|---|
| 1 | `[13,55]` count the copies before proposing the fix | 4 | **5,363** `git grep` calls (13.9% of all Bash) | `sibling_sweep.py <pattern> --diff`: run the grep, print N and every `path:line`; assert N==0 at HEAD after the fix. Counting matches is exact; only "is this the same shape" is judgment, and the pattern is supplied. |
| 2 | `[6]`,`[91]`,`[90]`,`[97]` repo/PR state before any claim | 4,4,3,4 | **5,254** (2,461 `--porcelain` + 1,933 `rev-parse` + 520 local-vs-origin + 340 `mergeStateStatus`) | One `repo_state.py --expect <sha>`: HEAD, `@{u}..HEAD`, porcelain, `mergeStateStatus`, `gh run list --commit <sha>`. Exits 1 on dirty tree, SHA mismatch, DIRTY/CONFLICTING, or zero runs for the SHA. Every input is a machine-readable field. **This is the largest single hand-assembled composite in the corpus.** |
| 3 | `[22,3,2]` df/docker preflight before fan-out | 5 | 859 dispatches vs **140** `df -h` — ≤16% coverage, and **33 of 140 used the wrong target** (only 107 used `/System/Volumes/Data`) | PreToolUse hook on `Agent`: run `df -h /System/Volumes/Data` + `docker info`, block below a free-space threshold. Thresholds on numbers; the wrong-target error the rule names is measurably still happening. |
| 4 | `[53,93]` no bulk auto-rewriter | 5 | rare, catastrophic (rewrote 3 schema files on a scope-locked PR) | PreToolUse Bash deny-regex: `--unsafe-fixes`, `pyupgrade`, `isort` over `src/`. A literal string match — the cheapest possible mechanization of a cost-5 rule. |
| 5 | `[56]` personal harness stays gitignored | 5 | 49 `git check-ignore` calls — **and the invariant is currently violated** | PreToolUse Write/Edit hook: `git check-ignore <path>`, block on miss. `review-charter.md:96` documents that `.claude/reports/` and `.claude/notes/` are **not** gitignored and handles it with prose ("never stage with `-A`"). Exit code of `git check-ignore` is the whole check. |
| 6 | `[33,47,103]` mutation agents get isolation | 5 | **175** `git worktree add` | Before dispatching an agent whose prompt matches mutation vocabulary: assert `git status --porcelain` empty, and assert the worktree HEAD equals the passed SHA. Two exact comparisons. |
| 7 | `[92]` prove "pre-existing" | 4 | **304** `git log -G` | `provenance.py <regex> --base --head`: `git log -G` over the range + site-set diff at base vs head (strip line numbers, sort, diff) + blame. The rule already specifies the three commands and their join. |
| 8 | `[37]` the `-k` selector claim | 4 | **490** `pytest -k` | Wrapper: collect with and without `-k`, print both counts and the node ids; fail when `-k` selects 0. "Did the selector select anything" is a count. |
| 9 | `[108]` never judge from the runner tail | 4 | 211 (137 `run_all_tests` + 74 `make quality`) | Parse `test-results/<ts>/*.json` per-suite, enumerate every non-passing outcome, ignore stdout. The structured record already exists — charter §2.1 tells you to read it and nothing does. |
| 10 | `[16]` grep repo-wide for every new def | 4 | index **already built** | `ssot_docstring_duplication.audit()` at `:80-83` indexes every def by name across the tree, then `:86-93` reports only SSOT-docstringed twins and `_`-prefixed test helpers. Report *any* name added by the diff that already exists elsewhere. Also: `_defs():58-69` walks only Function/AsyncFunction/ClassDef — **module-level constants are not indexed at all**. |
| 11 | `[25,106]` anchor every finding, never reuse an ID | 4 | — | `disposition_ledger.audit():172-197` returns no anchor check, yet `review-charter.md:90` claims "Mechanized: disposition_ledger.py". Add: every `FINDING_TAG:74` match must have a `SITE_TOKEN:96` match in its block; IDs must not repeat across rounds. Both regexes already exist in the file. |
| 12 | `[38,82]` new helper needs a production caller | 4 | — | For each new top-level def in the diff, grep for a call site outside `tests/`; report zero-caller helpers. The `N adopted / M eligible` numerator needs judgment; the **floor** is a grep. Charter §5c spends 1,300 B on it. |
| 13 | `[57,44]` plan-approval gate | 4 | — | PreToolUse Edit/Write path check against `src/ tests/ scripts/ CI Makefile config` while the stage is `planning`. The rule already ships the path list — it is a set-membership test. |
| 14 | `[19,27,51]` memory hygiene | 4 | — | Lint `memory/*.md` for PR/issue numbers, file lists, dates, external names. Charter §1.9 ends "Never persist per-PR specifics to memory"; `#\d{3,4}` is exact. **This whole re-routing exercise is the cost of this rule having no gate.** |
| 15 | `[80,81,104]` dispatch mechanics | 4 | **859** dispatches: 30 (3.5%) pass `model`; 80 (9.3%) lack a Step-0/MANDATORY block | PreToolUse `Agent` hook: reject an explicit `model`, require an absolute-path Step-0 list, require a SendMessage instruction on background dispatches. All three are input-field inspections. |
| 16 | `[78]` allowlist entries reachable from production | 4 | — | Parse each guard allowlist entry, grep for a call site outside test/allowlist files, report unreachable entries. Backward reachability over a name list. |
| 17 | `[66]` two-dot **and** three-dot diff on a behind-main PR | 4 | — | Run both `base...head` and `main..head`, report the delta between them. Two git invocations and a set difference. |
| 18 | `[12]` grep the diff for the codebase's confessions | 3 | — | Regex list ("keep in sync", "only verifies setup", "for now", "TODO before") over **added** diff lines. Detection is exact; only the fix is judgment. Cheapest item on this list. |
| 19 | `[24]` self-contained report, no `/tmp` paths | 4 | — | Regex `/tmp/`, `/private/tmp/` over the artifact. ~3 lines into `disposition_ledger._is_clean`. |
| 20 | `[58]`,`[14 partial]` mandatory sections present | 3-4 | — | Charter §3 mandates `## What I could not verify`. Nothing checks it. Section-heading presence test. |
| 21 | `[88,28]`,`[71]`,`[109 partial]` outward-facing ops need explicit delegation | 5 | 10 `git push`, 7 `gh pr create`, 104 `gh pr comment`, 24 `gh issue create` | Belongs in the **permission layer**, not a detector — `settings.json` deny/ask rules on those four commands plus `git clone`/fork. |
| 22 | `[97]` DIRTY skips `pull_request` CI | 4 | 340 | Folded into #2. |
| 23 | `[43,50]` no "cheap win" framing | 3 | 1 occurrence measured | One alternation into `disposition_ledger.py:78` BANNED. Near-free; charter §1.8 already names the words. |
| 24 | `[46,49]` no issue/PR numbers in code comments | 2 | — | `fixme_format.py:marker_violations` already tokenizes comments and already carves out the `FIXME(#N)` exception. Invert it for non-FIXME comments. |
| 25 | `[20]` a missing-test observation needs its own row | 4 | — | Finding body matching "no test"/"untested" must have its own ledger row. Add to `disposition_ledger`. |
| 26 | `[31]` every guard has pos+neg self-tests | 4 | **12 of 13 comply** | Meta-check in `bump_check.py`: assert every `detectors/*.py` exposes a self-test. `review_completeness.py` is the sole holdout — Part 4. |
| 27 | `[54]` re-mutation-test after a change to a guarded path | 4 | — | Deterministic *given an oracle registry* (oracle → guarded paths). The registry does not exist; that is the build cost. |
| 28 | `[77]` full suite after the first CI surprise | 4 | — | Session-scoped flag + pre-push hook. Deterministic once "CI surprise" is defined as a red check on a pushed SHA. |
| 29 | `[42]` fenced block, never a blockquote | 2 | — | Regex `^> ` inside a pasteable block. |
| 30 | `[26]` run flaky tests 5+ times | 3 | — | Wrapper with a repeat count. |
| 31 | `[34]` confirm the PR number | 3 | — | `gh pr list --head <branch>`. |
| 32 | `[8]` gated CI optimization no-ops | 3 | 52 `gh run view --log` | Grep the job log for the branch marker, then compare timings. |
| 33 | `[40]` don't alarm mid-operation | 4 | — | Check `~/.cache/pre-commit/patch*` mtime / lock presence before permitting a "files were reverted" claim. Partially deterministic. |
| 34 | `[1,10]` `;` not `&&` before cleanup | 4 | 8 `git stash pop` | Bash lint on `&&\s*git stash pop`. Deterministic, low firing. |
| 35 | `[23]` branch before the first edit | 3 | 6 branch cuts / 4 `git branch -vv` | Deterministic; low firing. |
| 36 | `[98]` `git mv` + `git add` old path | 3 | 6 | Deterministic; low firing. |
| 37 | `[105]` `git grep -E` vs `\b` | 4 | **0 violations** in 5,363 `git grep` calls | Deterministic Bash lint, but the prose is already holding. Build last. |
| 38 | `[107 partial]` SDK model-surface diff | 4 | — | Introspect pydantic model + enum surface in both wheels, diff field-by-field. `sdk_spec_drift` does the enum half. |
| 39 | `[21]` exception-class tuple reuse | 3 | — | Find `except (A, B, C)` tuples appearing in >1 module. Detection exact; adjudication judgment. |
| 40 | `[39,87 partial]` unprescribed fan-out | 5 | 859 dispatches, 738 the fixed panel | Hook warning above N concurrent agents when no skill prescribed it. Only the *counter* is mechanizable. |
| 41 | `[17 partial]` gratitude openers on outbound | 4 | 6 occurrences / 30,718 text blocks | First-line regex. Nearly free; measurably rare. |

### MUST-STAY-PROSE — genuinely needs judgment (25)

`[39,87]` when to fan out · `[14,79]` falsifying a subagent's because-Y · `[109,4]` who Chris is · `[89,84,83]` evidence hierarchy and premise re-verification · `[85,52]` truth over optimism · `[17]` voice and structure · `[74,35]` turn structure, lead with the better end state · `[36]` post-merge duplicate-helper sweep · `[61,7]` re-derive your own prior round · `[11]` verify clean verdicts as hard as violations · `[18]` enumerate readers on every except path · `[29]` grade remedy *composition* · `[32]` "infra can't host this" needs a prototype · `[60]` when a scope expansion is legitimate · `[62]` a pattern is a hypothesis about the rest · `[69]` grade against the behavioral done-contract · `[70]` cardinal invariant of a tooling PR · `[72]` four derivative levels · `[86]` when to run a second-pass audit · `[94]` verify a reviewer's proposed fix · `[95]` sibling patterns are hypotheses · `[9]` claimed invariant ⇒ failing oracle · `[5]` resurrect rather than delete tests · `[96]` cross-cutting wire-shape sweep · `[59]` external-system evidence ordering.

Two of these I checked rather than assumed, because the honest answer could have gone either way:

- **`[85,52]` banned language** — over **30,718** deduped assistant text blocks: "looks good" 2, LGTM 1, "should work" 5, "all set" 6, "good to push" 0, "free move" 0. A ~0.05% rate. The prose is working; mechanizing it would be effort against a solved problem. The one apparent outlier, "gold standard" at 285, is **not** a violation: of **620** outbound GitHub-writing Bash calls, only **16** contain internal vocabulary, and all 16 are the detector run or a `grep -ciE` self-check chained onto the `gh` call — not body text. Outbound leak rate is effectively zero.
- **`[9]` mutation testing** — the *surfacing* is covered (`compound_guard_operands.py:210-215` prints the mutation assignment), but choosing the mutation and reading the result is irreducibly a judgment loop.

---

## Part 3 — Prose the charter pays 738 times to restate a script

`review-charter.md` is 39,867 B / 150 lines, read at Step 0 by every one of the 738 lens dispatches.

| passage | bytes | ~tok | ×738 |
|---|--:|--:|--:|
| §4c readiness gate (`review_completeness.py`) — lines 117-134 | 6,777 | 1,694 | **1,250,172** |
| §4b.0 + §4b.5 + §3 disposition + §3 anchor + §1.9 (`disposition_ledger.py`) — 33, 83-88, 90, 108, 113 | 6,775 | 1,694 | **1,250,172** |
| §4b.1-4 + headers (orchestrator-only, no detector) — 104-107, 109-112, 114-115 | 1,901 | 474 | 349,812 |
| §1.5d short-circuit (`compound_guard_operands.py`) — line 25 | 1,171 | 292 | 215,496 |
| §3 PR-description scan (`citation_freshness.py --pr`) — line 92 | 666 | 166 | 122,508 |
| §1.8 banned language (`disposition_ledger` BANNED) — line 32 | 845 | 211 | 155,718 |
| §5 mandatory-read list, inside the file read because of it — 136-151 | 831 | 207 | 152,766 |
| **union (double-counting removed)** | **18,135** | **4,533** | **3,345,354** |

**That is 45.5% of the charter, ~3.35M tokens.**

The sharper version of the finding: **§4c (6,777 B) documents `review_completeness.py`, which lens agents invoked 4 times in 738 dispatches. The disposition_ledger passages (6,775 B) document a detector lens agents invoked *zero* times.** Combined, **13,552 B — 3,388 tokens — shipped 738 times (2.50M tokens) describing two orchestrator-only tools the recipients neither run nor can act on.** §4b and §4c are already *labelled* orchestrator-only at `review-charter.md:104` and `:117`; the label is in the payload the lens agent pays for.

This corroborates FACTS.md:41-43 independently (my §4b+§4c measurement: 11,742 B = 2,935 tok vs its ~2,936) and extends it: the redundancy is not only orchestrator-scoped prose, it is **detector-restating** prose, and the two sets overlap only partly.

`reviewer-tooling.md` (13,627 B) is *not* the offender — it names only 4 detectors, once each.

---

## Part 4 — Detector quality: four confirmed false-greens

All self-tests pass on the current tree: `disposition_ledger` PASS, `citation_freshness` 22/22, `compound_guard_operands` 15/15. These are unusually good guards — `compound_guard_operands:273-296` drives `main()` end-to-end specifically because a leaf-only self-test once said 13/13 on a detector that crashed on invocation, and `citation_freshness:220-245` tests file iteration, not just the matcher. That is the `testing-ci` standard, met.

Applying the same standard adversarially, four defects pass on a real violation:

**1. `disposition_ledger.py:189` — DISPOSITION-COVERAGE is a count, not a per-finding match. This is the detector's cardinal invariant and it is defeatable.**
```python
deficit = max(0, n_findings - n_dispositions)
```
`n_dispositions` is `len(DISPOSITION_TOKENS.findall(text))` over the **whole document**. Proved on a synthetic artifact with 3 severity-tagged findings where all 4 disposition tokens sit under finding A1 and A2/A3 have none:
```
n_findings=3  n_dispositions=4  deficit=0  clean=True
```
Two of three findings have no resolved next-action and the gate exits 0. That is precisely the #1547 drop the detector was built for (`:2-10`), passing.
**Fix:** split on `FINDING_TAG:74` boundaries and require a token inside each block.

**2. `disposition_ledger.py:90-91` — the INTERNAL-VOCAB detector-name list is stale against its own directory.** It enumerates 9 names; 13 exist. Missing: `compound_guard_operands`, `changed_field_grading_coverage`, `github_workflow_duplication`, `suggestion_audit`. An artifact reading *"compound_guard_operands and suggestion_audit both clean"* returns `internal_vocab_hits=0, clean=True` — a §1.9 leak of exactly the kind the check exists for, through the gate. `review-charter.md:33` also names **"meets our bar"** as banned; the regex does not match it.
**Fix:** derive the name alternation from `Path(__file__).parent.glob("*.py")` so it cannot drift.

**3. `citation_freshness.py:58-60` — CONTEXT must be on the same line as the version token, and the #1616 regression case only passes because the fixture happens to be single-line.** With the live pin (3.1.1/6.6.0):
```
"## Spec grounding\nAuthoritative version: **3.1.0-beta.3** (pinned `6.6.0`)"  -> NO HITS
"Authoritative version: AdCP **3.1.0-beta.3**"                                 -> flagged
```
Same stale claim, same surface, same PR description; a line break between the heading and the version defeats it. The self-test corpus at `:253-259` embeds `adcp==5.7.0` on the version line, so the fixture never exercises the split-line form.
**Fix:** evaluate CONTEXT over a small line window, or over the enclosing markdown block.

**4. `compound_guard_operands.py:94-96` — negation hides a compound guard entirely.**
```
if not (a or b):   -> 0 hits
if not a or not b: -> 1 hit
```
`_record` returns unless the node **is** a `BoolOp`; `not (a or b)` is a `UnaryOp`, so the De Morgan form of the very illusion the detector exists for is invisible. Also unreported: `{'k': a or b}` (0 hits) and a bare `Expr` BoolOp (0 hits). The call-argument limit at `:247-251` is deliberate and documented; **these are not** — they are unstated matcher gaps, which is `[31]`'s exact failure mode.
**Fix:** in `_record`, unwrap `ast.UnaryOp(op=ast.Not)` before the `BoolOp` test.

**5. `review_completeness.py` — no self-test at all.** It is the only detector of 13 without one, it is the readiness gate (the highest-stakes artifact the suite emits per `review-charter.md:119`), and it is the one with a *documented* prior false green (`:16-24`, PR #1616). `bump_check.py` cannot cover it. Its I/O-heavy shape is the reason, and also the finding: `_resolve_since`, `_head_delta`, and the event-merge at `:130-141` are pure enough to test.

**6. `review_completeness.py:149` — `--since` is a lexical string compare across mixed ISO offsets.**
```python
newer = [e for e in events if since and e[0] > since]
```
GitHub returns `...Z`; `_resolve_since:75-81` resolves a SHA via `git show -s --format=%cI`, which emits a **local offset**. With a positive offset: `since=2026-07-29T23:00:00+02:00` (21:00Z) vs event `2026-07-29T22:00:00Z` (genuinely 1h newer) → `False` → **silently dropped**, the exact miss the gate exists to prevent. This machine is at `-0600` and the repo's own commits carry `-04:00`, so the current failure direction is over-reporting (safe) — the defect is real but latent here. 9 of 81 `--since` uses passed a SHA.
**Fix:** parse both sides with `datetime.fromisoformat` and compare instants.

**7. Not a code defect but the biggest gap in practice: `--since` is unenforced and omitted 41% of the time.** Across 138 real invocations: `--since` present 81, **absent 57**; `--head` present 104, absent 34. `review-charter.md:126` states "**`--since` is not optional**" and `review_completeness.py:20-21` says "`--since` is the flag a hurried re-review omits" — and without it, `newer` is empty and only the thread arm gates. A prose rule *about a detector*, violated in 41% of that detector's runs, when `argparse` could require it. This is the single cheapest fix on the list.

---

## What I could not verify

- **Firing frequency is measured by proxy** — Bash commands matching the operation a detector would replace. It is a lower bound on how often a rule is *relevant* and says nothing about how often it was *violated*, except where I measured violations directly (df target, `model` param, Step-0 presence, banned words, `--since` omission).
- **COVERED/MISSING assignments are mine**, from reading all 13 detectors and the charter; only the ones with a cited `path:line` were traced to code. Rules I classified from docstrings alone: `[21]`, `[54]`, `[8]`, `[26]`.
- **The false-greens are proved on synthetic inputs**, not on real artifacts from `.claude/reports/`. Each reproduces the detector's own documented miss-mode, but I did not confirm any shipped artifact actually passed through one.
- **`review-charter.md:96` says `.claude/reports/` and `.claude/notes/` are not gitignored** — I did not re-run `git check-ignore` to confirm that is still true today.
- **Byte→token conversion is bytes/4**, not a tokenizer. FACTS.md's 3.8 chars/token calibration would make my Part 3 totals ~5% higher.
- **Not examined:** the 10 `.claude/agents/review-*.md` definitions (they may restate detector prose a *fourth* time), and whether `review-admin-ui`'s zero detector usage reflects a genuine absence of mechanizable surface or an unbuilt detector.