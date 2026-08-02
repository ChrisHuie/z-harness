Verification complete. Here is the report.

---

# Claim accuracy: 52 TRUE / 3 PARTLY / 0 FALSE across 55 findings

**Headline: the panel's claims about the lines it cites are true at a rate of 94.5%, with zero outright FALSE findings. Accuracy does *not* degrade with severity — every BLOCKER checked out, and the only inaccurate claims in the sample are severity-*lowering* mitigation rationales. The prior work's hypothesis (promoted findings are the weaker ones) is not supported; in this sample the direction is reversed.**

---

## 0. A method error I made and corrected — repeat this check if you rebuild the frame

My first SHA extractor excluded all-digit tokens as "not a SHA." PR1417's reviewed head is `796375517` — all digits. I silently fell back to `7832ddbb7`, which the report itself labels the **merge-base**, not the head. Three findings graded at that SHA produced spurious "file does not exist" results:

```
$ git show 7832ddbb7:tests/integration/test_audit_budget_serialization.py
fatal: path ... exists on disk, but not in '7832ddbb7'
$ git show 796375517:tests/integration/test_audit_budget_serialization.py   # resolves
```

I re-resolved by scoring each candidate SHA on how many of the report's cited paths exist in its tree (`796375517` → 9, `7832ddbb7` → 8) and regraded. **Anyone repeating this grading against the wrong SHA would manufacture three false "phantom file" defects that are entirely the grader's fault.** This is the same class of error the escaped-defects pass caught in itself (its basename-guesser producing 15 fake phantoms).

---

## 1. How I sampled — stated precisely, because a biased sample makes the number meaningless

**Frame.** 82 artifacts in `.claude/reports/` + 9 in `pr1312-fleet/`. 84 of 91 carry a resolvable reviewed-HEAD SHA (the 7 without are undated audits/issue notes). From those I extracted every table row or bullet that carries **both** a severity tag and at least one `path:line` cite → **363 finding units across 46 files**.

**Draw** (seed `20260801`, per-file cap of 4 to stop the two biggest reports dominating):
- **all 18** units my regex tagged BLOCKER (the stratum is too small to sample)
- 21 SHOULD-FIX and 16 NIT, round-robin over (primary lens × src/tests/both) strata

**Result: 55 findings, 26 report files, 22 distinct PRs**, spanning all 8 lenses plus 9 units with no lens label in the row. src 26 / tests 18 / both 11.

**Two frame limitations, stated up front:**

1. **My regex takes the max severity mentioned in a row, which over-assigns BLOCKER.** Reading the 18 "BLOCKER" rows, only **11** are finally BLOCKER; 5 are explicitly adjudicated down (`BLOCKER→SHOULD-FIX*`, "so SHOULD-FIX not BLOCKER", "**SHOULD-FIX** (error-wire dissents at BLOCKER)") and 2 are status rows about a *prior* round's BLOCKER. All tables below use the **re-derived final severity**, not the regex tag.
2. **One-line extraction under-captures the richest findings.** These reports are header-line + sub-bullets; the header alone sometimes reads terser than the finding is. Where the matched line was a header I pulled the full block before grading (this mattered for #34 below, where the sub-bullets carry the entire argument).

---

## 2. Results

| final severity | n | TRUE | PARTLY | FALSE | % TRUE |
|---|---|---|---|---|---|
| **BLOCKER** | 11 | **11** | 0 | 0 | **100.0%** |
| **SHOULD-FIX** | 26 | 23 | **3** | 0 | 88.5% |
| **NIT** | 16 | **16** | 0 | 0 | **100.0%** |
| status/other | 2 | 2 | 0 | 0 | 100.0% |
| **total** | **55** | **52** | **3** | **0** | **94.5%** |

| area | n | TRUE | % |
|---|---|---|---|
| `src/` | 26 | 26 | 100.0% |
| `tests/` | 18 | 15 | 83.3% |
| both | 11 | 11 | 100.0% |

**By lens I cannot separate signal from noise and will not pretend otherwise.** With 3 non-TRUE gradings spread over 9 lens buckets (max n=9), every per-lens rate is 0 or 1 events. For the record: error-wire 9/9, bdd 8/8, architecture-guards 6/6, code-patterns 6/6, spec-conformance 5/5, admin-ui 3/3, security 3/3, test-integrity 5/6, unlabeled 7/9. **The only defensible lens statement is that all 3 non-TRUE findings are test-coverage claims** (`test-integrity` / TI-class) — a hypothesis at n=3, not a result.

---

## 3. The only real defect: a fabricated second oracle, used to justify a demotion

`full-review-pr1605-rereview-20260720.md`, finding **TI1**, reviewed head `c323bfc5`. The finding correctly identifies that the httpx `content=` sender is graded only at a mock. Then it asserts two corroborating oracles — and that assertion is the **stated basis for rating it SHOULD-FIX rather than BLOCKER**.

**The claim (L166, verbatim):**

> BUT #1441 regression IS pinned at mock: `test_delivery.py:1874` + **`test_delivery_service_behavioral.py:340`** recompute HMAC over `content=` kwarg (catch sign-A-send-B + content→json revert via KeyError), unix-ts pinned `:1870`/**`:288`** → **hence SHOULD-FIX not BLOCKER.**

**The code:**

```
$ git show c323bfc5:tests/unit/test_delivery_service_behavioral.py | sed -n '340p'
            assert cb.can_attempt() is False          # circuit-breaker state
$ git show c323bfc5:tests/unit/test_delivery_service_behavioral.py | sed -n '288p'
            )                                          # a closing paren
$ git show c323bfc5:tests/unit/test_delivery_service_behavioral.py | grep -c 'hmac\|isdigit\|x-adcp-signature'
0                                                      # 639 lines, zero HMAC code
```

The **first** oracle is real and exactly as described — `test_delivery.py:1866` reads `post_mock.call_args.kwargs["content"]`, `:1874-1876` recomputes the HMAC over those bytes, `:1870` is `assert timestamp.isdigit()  # spec: unix seconds, not ISO`. The **second** does not exist. The nearest real analogue is `tests/unit/test_webhook_delivery.py:302-305` — different file, and it recomputes over `call_args.kwargs["data"]` (the `requests` sender), **not** the `content=` kwarg this finding is about, with no unix-ts pin anywhere in it.

So the mitigation is wrong three ways: wrong file, wrong mechanism, and the corroboration it claims would not have covered the gap even if it were where it says. The demotion survives on one oracle, not two. Graded **PARTLY** (the observation is right; the corroboration is fabricated), and it appears twice in my sample because the same mitigation is restated at L61 — hence 2 of the 3 non-TRUE gradings.

**The third PARTLY** (`full-review-pr1417-20260710.md`, T-SF1): the finding flags *stale present-tense narration* at `test_audit_budget_serialization.py:13,25,92` and quotes two phrases. `"It FAILS against current production"` is verbatim at `:24-25`, and `:13`/`:92` are genuinely present-tense. But `"RED today"` **does not appear anywhere in that file** (`grep -in 'red today\|\bRED\b'` → empty). The sites are right; one of the two quotation marks is unearned.

---

## 4. Why this is not the reassuring number it looks like: cite drift

**10 of 55 findings (18.2%) have a cite that lands off the code it describes**, while the substance holds. This is invisible to the phantom-line test — every one of these lines exists.

| finding | cite says | code actually is | off by |
|---|---|---|---|
| PR1719 A1 | `models.py:909` — *"start_date/end_date are Date, nullable=False"* | `:909` is `budget: Mapped[Decimal \| None]`; start/end_date are `:911-912` | 2 |
| PR1719 A1 | `:911-912` — *"start_time/end_time are DateTime(timezone=True)"* | those are `:913-914` | 2 |
| PR1718 D5 | `workflows.py:203` for `if not readiness.ready:` | `:203` is an import continuation; the gate is `:207` | 4 |
| PR1621 R8-J4 | `conftest.py:3366` — `_wired_statuses_scenarios` | the set is defined `:3372-3376`; `:3366` is a comment | 6 |
| PR1720 B1 | `test_architecture_no_error_code_kwarg_in_impl.py:23` scans two dirs | `SCAN_DIRS` is `:22` | 1 |
| PR1621 SF7 | `conftest.py:3387` generic reason | `:3387` is `else:`; the `pytest.xfail` is `:3388` | 1 |
| PR1605 AG1 | `test_delivery.py:1837-1845` ⟷ `test_webhook_delivery_service.py:98-107` | the dup blocks are `:1838-1846` / `:99-108` | 1 |
| PR1669 A2 | `test_ipr_verify.py:23` | `:23` blank; the test is `:24` | 1 |
| PR1616 C4e | `test_uc018_list_creatives.py:81-83` lists the wired set | the wired set is enumerated `:78-79` | 3 |
| PR1718 E4 | `MEDIA_ASSET_FALLBACK_IDS` at `:653-665` | set spans `:653-671` (membership claim still holds) | range short |

Under the lead's rubric these are TRUE — the observation is right and the consequence follows, and a ≤6-line miss still lands a human in the right block. But it is the measurable cost of a review that cites by line without re-anchoring, and it compounds: **the same drift that puts you 4 lines off in a 20-line function is what puts you in the wrong file entirely in §3.**

---

## 5. The severity question — the answer is the opposite of the hypothesis

I could identify the consolidation history for 11 sampled findings. **Every promoted finding graded TRUE; the only inaccurate claims sit in demotion rationales.**

| direction | finding | lens disagreement → final | grade |
|---|---|---|---|
| **promoted** | PR1676 A4 | security=SHOULD-FIX → **BLOCKER** ("promoted by the referent") | TRUE |
| **promoted** | PR1718 A1 | error-wire=BLOCKER · security=SF → **BLOCKER** | TRUE |
| **promoted** | PR1718 A2 | cp=BLOCKER · guards=BLOCKER · admin-ui=SF → **BLOCKER** | TRUE |
| **promoted** | PR1718 E4 | ti=BLOCKER · ew=SF → **BLOCKER** | TRUE |
| **promoted** | PR1675 A1 | spec=BLOCKER · ew=SF → **BLOCKER** | TRUE |
| **promoted** | PR1720 A-1 | security=SF · cp+ti=BLOCKER → **BLOCKER** (§4b.0 max) | TRUE |
| **promoted** | PR1719 D2 | guards=SF · cp=NIT → **SHOULD-FIX** | TRUE |
| demoted | PR1719 A1 | ew dissents BLOCKER → **SHOULD-FIX** | TRUE |
| demoted | PR1567 F1 | `BLOCKER→SHOULD-FIX*` | TRUE |
| demoted | PR1417 ARCH-SF1 | *"strict reading = BLOCKER; I rate SHOULD-FIX"* | TRUE |
| **demoted** | **PR1605 TI1** | *"hence SHOULD-FIX not BLOCKER"* | **PARTLY** |

The mechanism this suggests: a promotion is a claim that gets **re-argued in front of a second lens and the orchestrator**, and it survives that. A demotion is a claim that *ends* an argument — nobody re-checks the mitigation that closed it, because closing it is what the mitigation is for. In §3 the discharging evidence was never verified and was wrong. **If severity inflation is running 3.7:1, the 262 promotions are not where the risk is; the 71 demotions are the unaudited surface** — and they are exactly where the escaped-defects pass already found its most damning artifact (#1775: cited, cleared as NIT under an `[observed]` tag, filed as a defect 12 days later).

---

## 6. Failure modes I specifically hunted for and did *not* find

The lead named four. I checked each directly rather than inferring:

- **"A guard is missing when it exists elsewhere."** Not found. PR1718 A2 claims `creatives.py:612` is the only `._session` reach in `src/` outside `uow.py` — `git grep -n '\._session' 9da6c4606 -- 'src/*.py' | grep -v 'self\._session'` returns **exactly one line**, that one. PR1720 B1 claims its site is the only `error_code=` kwarg outside the guard's two scanned dirs — the grep returns 3 hits, of which one is inside `src/core` (scanned) and one is docstring prose. Both exclusivity claims hold.
- **"A test is vacuous when it does assert something real."** Not found — and the panel got the hardest instance right. PR1650 S1 calls an A2A "wire" test a serializer tautology. My first read of `_base.py:_run_a2a_handler` suggested the panel was wrong (that path *does* parse a real artifact DataPart). The panel's sub-bullet is more precise than my first pass: `CreativeSyncEnv.call_a2a` **does not use** `_run_a2a_handler` — `tests/harness/creative_sync.py:205` returns `sync_creatives_raw(**kwargs)`, and its own docstring at `:195-198` says so. `_base.py:543` resets `_last_wire_response = None` and only the two real-transport paths set it. The test's docstring claim to read the wire is false, exactly as the finding says.
- **"Mechanism wrong though the site is worth changing."** One instance, §3.
- **"Code described correctly, wrong conclusion about impact."** None found in this sample. Note this is the failure mode of #1775, so its absence here is a statement about 55 findings, not about the corpus.

**Representative commands** (each grading used `git show <reviewed-sha>:<path>`, never the working tree):

```
git show 564d62315e6812f73b779eb77a86142ab7e1e6fe:src/a2a_server/adcp_a2a_server.py | awk 'NR>=740&&NR<=790'
git show 9da6c4606:src/core/database/models.py | awk 'NR>=660&&NR<=675'
git show 6e22da280:tests/conftest_db.py | awk 'NR==139'
git grep -n 'get_by_media_buy' 8cb8d0ed6 -- 'src/'      # base main, to prove the caller existed
git show 796375517:tests/bdd/e2e_rest_known_failures.txt | grep -v '^\s*#' | grep -c '[^[:space:]]'   # 307
```

Two spot-checks worth recording because they falsify-tested a *numeric* claim rather than a locational one: PR1417 ARCH-SF1 says the ledger grew 303→307 and the ceiling went 308→309 — base 303, head 307, `_LEDGER_CEILING` 308 → 309, all four exact. PR1605 AG1 says `.duplication-baseline` tests went 80→75 — base `c45b0b1f0` has `"tests": 80`, head `c323bfc5` has `"tests": 75`.

---

## 7. What I could not determine

- **Runtime sub-claims inside otherwise-verified findings.** 6 of the 11 BLOCKERs rest partly on something I did not re-execute: real-Postgres reproductions (PR1718 A1, PR1719 B1), mutation-survival counts (PR1718 D5's "survives 5588 tests", E4's "6/6 pass"), live-wire probes (PR1675 A1's `HTTP 200`), and xpass-frequency (PR1665 B1). **I graded the source-checkable mechanism, which held in every case** — and in several the code corroborates the runtime claim independently (PR1675 A1's `api_v1.py:89` comment literally reads *"Accept-and-ignore: no transport acts on it yet"*). But "the mechanism is real" is weaker than "the reproduction is real," and only the panel ran the latter.
- **Whether 0 FALSE generalises.** 55 of 363 units, and the frame is single-line-extractable findings only. A multi-paragraph finding whose severity and cite sit on different lines never entered the frame. The reports' longest prose findings are systematically under-sampled.
- **Per-lens accuracy.** Genuinely not measurable at this n. Separating even a 10-point lens difference would need ~250 gradings.
- **Whether cite drift misleads humans in practice.** I measured that 18.2% of cites are off; I have no evidence about whether a reviewer following a 4-line-off cite fails to find the code. It is plausibly harmless. It is not plausibly harmless at the §3 magnitude.
- **The `dist/compliance/3.1.1/` sub-claim** in PR1675 F1 (*"has no UC-001 artifact"*) — `dist/` has **zero tracked files** at that SHA, so it is a build artifact I cannot inspect from git. Every in-repo cite in that finding was exact.

**Repo state:** read-only throughout. No `git fetch`, no checkout, no writes to the working tree, nothing pushed. All reads were `git show <sha>:<path>`, `git grep <sha>`, `git ls-tree <sha>`.