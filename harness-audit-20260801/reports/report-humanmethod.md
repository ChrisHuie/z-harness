# Reverse-engineering the independent reviewer's method

**Bottom line.** The method is not a secret. It is already written down, in full, inside the harness — the charter and the lens catalogs contain explicit rules for every behaviour I could isolate, most of them authored *from* this reviewer's past findings. The panel reads those rules, runs the detectors that mechanize them (198–330 invocations each), and still misses 52%. **The advantage is not knowledge the panel lacks. It is a different unit of work: the human reviews *relations between sites*; the panel reviews *sites*.** That difference is structural, only partly encodable, and one specific piece of the harness actively suppresses the encodable part.

Scripts: `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/km/` (`markers.py`, `hops.py`, `clusters.py`, `persistence.py`, `volume.py`, `brevity.py`, `inverse.py`, `anchor.py`).

---

## 1. The shape of the findings

985 comments, 29 PRs, median 425 chars, **0 replies**, 138 review submissions, median 6 anchored threads per submission (max 19). Every finding is its own `path:line` thread. Nothing is prose in a summary comment.

The recurring form is: *this line is the Nth instance of a thing that lives at another line* — plus a named symbol to create.

> This ~10-line setup block (`DeliveryPollEnv("t1","p1")` → `TenantFactory` → `PrincipalFactory` → mid-flight `MediaBuyFactory` with `_DAILY_WEBHOOK` → `set_adapter_response(..., impressions=5000)`) repeats 8× in this file (73/124/256/295/351/401/452/520) with only the flight window varying — `_DAILY_WEBHOOK` was extracted but the surrounding block wasn't. Extract one helper, e.g. `_serving_webhook_buy(env, *, flight="live", mb_id=None)`; this PR's own `_make_serving_buy_attrs()` in `test_delivery_webhooks.py` is the precedent.
> — PR1575, `tests/integration/test_delivery_poll_behavioral.py:73`

Then seven more threads, one per site, each a single sentence pointing back. Six lenses had that file open. They cited 15 sites in it and hit **1 of those 8**.

Four distinguishing moves, all present in that one comment:

**(a) Mutation as the default oracle** — 11.9% of comments, and the whole point of the test-facing ones:

> This new failed-send branch (raise -> batch counts an error, not a "Sent") is the PR's headline correctness fix, but no test exercises it: every `fake_send_notification` in the changed suite returns `True`. … **Deleting this raise currently leaves the whole suite green.**

> Append `|| true` here (or add `continue-on-error: true` to the step) and ipr-gate goes green on an unsigned PR with **every guard still green**. — PR1669, `.github/workflows/ci.yml:658`

> Mutating line 184 to `return 0` keeps all 16 tests green while the gate silently passes a refuse-to-verify. — PR1669, `scripts/ci/ipr_verify.py:199`

**(b) The PR's own new code as the consistency reference.** Not repo convention — *this diff's* convention:

> This PR parametrizes its other new tests, so these two diverge from its own convention.

> …the two IPR test files added in this same PR import `repo_root()` from `_architecture_helpers`. Route through the same helper so all three new files share one repo-root anchor.

**(c) A named taxonomy of defect *shapes*, carried across PRs** — "extract-then-skip-a-sibling", "the partial-copy shape #1556 fixed for the serving set", "the PR #1299 silent-suite-drop class". 6.4% of comments cite a PR/issue number.

**(d) A standing ledger.** 12.9% carry an explicit re-raise marker with a date:

> ↩ raised 2026-07-23, still open.
> The previously stated approval condition is still not met (raised at this exact head, unaddressed)…
> (↩ raised 2026-07-13 and 2026-07-22, still open.)

**31 of those re-raises credit `@ChrisHuie` — i.e. they are the panel's own findings, which the panel then dropped and the human carried.** The panel re-raises only **10.8%** of its own ≥SHOULD-FIX sites in the next round. It starts fresh every time.

---

## 2. What evidence do they bring that the panel does not?

I tested the five candidates you listed. **Four of them are wrong.**

| candidate | measured | verdict |
|---|---|---|
| production/runtime behaviour | 0.12 vs panel **0.54** per 10k chars | **panel is stronger** — inverted |
| a caller the diff doesn't show | 33.3% ref another file, 13.0% ref ≥2 | real, but panel matches it (5.69/10k vs 7.59/10k) |
| memory of a prior incident/PR | 6.4% cite a PR/issue number (panel 6.8%) | **no advantage** |
| intent behind the code | 1.7% (panel 6.0%) | **panel is stronger** |
| ad-serving / AdCP domain knowledge | 8.4% spec/wire (panel 21.8%) | **panel is stronger** |

Normalized per 10k characters, only three markers separate them:

- **enumerates-every-site: 1.94 vs 0.40 — 4.9×**
- proposes-a-concrete-mutation: 1.53 vs 0.67 — 2.3×
- names-a-helper-to-create: 9.51 vs 3.35 — 2.8×

The reviewer essentially **never runs the system**. My "runtime evidence" regex fired 26 times and every hit on inspection was matching the word "probe" *in the code under review*. There is one genuine execution in 985 comments, and it is used to *falsify the panel*:

> Verified: `uv run python -c "from adcp import CreativeStatus; print(str(CreativeStatus.approved))"` → `approved`. Drop the `str(enum)` clause. — PR1621, `↩ Raised in R6 (@ChrisHuie 2026-07-20)`

**Learnability.** Bucketing all 985 by what the evidence requires: repo-derivable 25.5%; GitHub-derivable (issue state, CI) 15.9%; runtime ~0%; **not present in any artefact: 16 comments, 1.6%** — and on reading them, most are still repo-derivable ("two reports read side-by-side" refers to two files in the repo). The genuinely un-encodable residue:

> An operator grepping the approval tag for a buy's finalize trail won't surface the hold. — PR1718, `src/services/media_buy_creative_readiness.py:127`

> If the team accepts a separate-boundary deferral, annotate this tuple with an OPEN, author-assigned issue number like the `#1418` sibling above — **today no such ticket exists.** — PR1677

That is taste about what a deferral *means* and how a human will read a log. It is maybe 1–2% of output. **There is no large body of privileged context here.** That is the good news and the bad news: nothing is being withheld from the agents, so nothing can be handed to them.

---

## 3. Do they read differently?

Not by reading more, and not by reading deeper per file. I expected both and both are false.

| | panel | human |
|---|---|---|
| distinct sites cited, 28 shared PRs | 4,988 | 873 |
| distinct files cited | 1,404 | 251 |
| **median sites per file** | **3.33** | **3.43** |
| sites in files *both* commented on | 2,482 | 834 |

The panel cites 5.7× more sites at *identical* per-file density, in the same files (91.6% file-level agreement per prior work) — and still lands on the human's specific line only 48% of the time.

So it is a **selection** difference, not coverage or depth. The panel selects lines by pattern match (P1–P42 catalog hit, detector output, grep hit). The human selects lines by *relation to another line*: **60.3% of comments are a repeat-site of a defect named elsewhere in the same review submission**, and 58% of submissions carry more than 5 threads.

I tried to settle this with a harder measurement — whether the human anchors on unchanged context lines while the panel anchors on added lines — and **it does not survive**. The apparent 14× lift toward context lines is identical for all four comment authors including the disposition-bot-like one (12.7–14.1×), so it is an artifact of GitHub's `position` field going stale against the stored `diff_hunk`, not behaviour. Reconstructing added-line sets from git gives the opposite sign (human 75.2% on added lines vs panel 51.4%) but the panel's cites include reference citations, not just findings, so that is confounded too. **I could not settle this one.**

---

## 4. How far from the diff do the findings live?

Every anchor is inside the diff — GitHub permits nothing else, and prior work confirmed 100% of missed sites were in-diff. The real question is where the *evidence that makes it a finding* sits. I hand-graded 30 random MISSes and verified every cross-file reference against the PR's actual changed-file list (`verify_hops.py`, git `merge-base...head`):

| hops from the anchor | n | |
|---|---|---|
| 0 — evidence inside the hunk | **1** | 3.3% |
| 1 — rest of the anchored file | 11 | 36.7% |
| 2 — another file the PR changed | 11 | 36.7% |
| 3 — a file the PR did **not** change | 4 | 13.3% |
| 4 — repo history / another PR / a norm | 3 | 10.0% |

**96.7% are ≥1 hop out; 60% require opening a second file.** But note where the mass sits: hop 2, *inside the diff*. Only 23% needs anything outside the changed-file set.

That kills the simple version of the diff-anchoring hypothesis. The panel is not failing because evidence is out of scope — it is failing because "in the diff" is not a bound when the diff is 255 files (PR1544) or 173 (PR1547). The panel reads a large diff *hunk by hunk*; this method reads it *relation by relation*.

An automatic pass over all 985 (conservative — only fires on explicit textual references) gives the same shape: hop ≥1 = 49.7%, ≥2 = 40.3%, ≥3 = 21.5%.

---

## 5. What to add to the harness

**Read this first, because it disqualifies the obvious answers.** `review-charter.md` already contains:

- §1.5b — *"COUNT THE COPIES BEFORE PROPOSING THE FIX… If N > 1 the finding is 'this operation has no home'"*
- §1.5c — *"a new shared helper is graded on ADOPTION COMPLETENESS… report `N adopted / M eligible`"*
- §1.12 — *"Mutation-test the claim: break the line that would violate the invariant and confirm a test reddens"*
- §4b.0 — *"a unified SSOT finding carries **one ledger row per site** (never 'N homes' prose)"*
- §4c.3 — *"Every confirmed finding was sibling-swept — enumerated, not asserted"*
- §4c.4 — *"New TEST code is DRY-swept by hand… repeated ≥3×… check EACH site for drift"*

`review-code-patterns.md:111` names the exact file and line pair from this reviewer's own PR1534 findings as the canonical miss. `review-test-integrity.md:75-80` is a section titled *"Test craftsmanship… a colleague raised four test-craftsmanship items on #1534 that every pass here missed."* Nine separate "a colleague found that" provenance notes across the charter and lenses. **The charter is an archaeology of this reviewer's findings.** And the detectors that mechanize it run: `ssot_docstring_duplication` 198×, `disposition_ledger` 330×, `compound_guard_operands` 69×, `pr_import_cycle` 68×.

So: do not propose a prompt. The prompt exists, is excellent, is read, and does not work. Four things that are not prompts:

**(1) Remove the ≤5 finding cap. It is a measured, binding constraint.**
Charter §3: *"Cap the body at the top ~5 findings by severity; list the rest as one-line `also:` entries."* Findings-per-report across 663 reports: `1:72 2:138 3:166 4:105 **5:134** 6:28 7:14 8:3 9:2 10:1`. A local minimum at 4 and a local maximum at exactly 5 followed by a 5× cliff is a cap artifact, not a distribution. **92.8% of reports have ≤5.** The escape hatch is barely used — `also:` lines appear in 6.0% of reports. Meanwhile reports carry a median of **13 distinct `path:line` cites for 3 severity-headed findings** (4.2 cites per finding): the enumeration happens internally and is discarded at emission. This directly contradicts §4b.0's one-row-per-site rule in the same file. It cleanly explains the 16.2% under-call; whether it also suppresses cites I could not measure.

**(2) A sibling-enumeration pass that runs *after* the lenses and takes their findings as input.**
Every existing rule makes the sweep conditional and internal to a lens that has already written its report. Sizing, honestly: of 133 identifiable multi-site defect clusters, the panel got **every** site 37.6% of the time, **some but not all** 33.8%, and **none** 28.6%. Partial enumeration costs **60 sites = 13.4% of the 448 misses.** That is a real, mechanically-recoverable block — not the majority. The other 28.6% (never detected at all) is not an enumeration problem and this pass will not touch it.

**(3) A structural-clone detector for `tests/`, keyed on AST shape, not tokens.**
63% of the human's findings are in `tests/`, and DRY is the worst class (69.2% miss+under). The only mechanism is `.pre-commit-hooks/check_code_duplication.py`, which is a **pylint R0801 count ratchet** with `.duplication-baseline` = `{"src":35,"tests":83,"scripts":0}`. Three failures: it is a count, so add-one/remove-one is green; it cannot see "same setup block, different flight window" or "same assertion, 2 of 3 fields"; and 83 pre-existing tests clones means no pressure. Charter §4c.4 explicitly concedes this and delegates to *"by hand."* (Aside: `review-code-patterns.md:51` states the baseline as `{"src":36,"tests":99}` — stale against the actual file.)

**(4) A standing findings ledger keyed to `(path, symbol)`, carried across rounds.**
The panel re-raises 10.8% of its own unfixed ≥SHOULD-FIX sites next round; prior work shows 80–100% of each round's sites are new. The human re-raises with dates and provenance and had to carry 31 of the panel's own abandoned findings. This is pure state management, needs no model capability, and is the cheapest item here.

**What is not encodable.** The 1–2% operational-taste residue (§2). And more importantly: the 28.6% of clusters where the panel found *no* site. There is no instruction for that. The reviewer's advantage there is that they hold "the shape of a defect I have seen before" as an active retrieval index while reading, and the panel holds it as a 39,867-byte document read once at Step 0. I have no proposal that closes that honestly.

---

## 6. The inverse — where the panel is genuinely stronger

Substantially, and in ways the human does not attempt.

**Coverage.** **49.4% of the panel's 2,868 ≥SHOULD-FIX cites on these 28 PRs are in files the human never commented on.** 29.2% more are the same file, a different site. The panel sweeps 5.7× the surface at a 0.098% phantom-cite rate.

**It runs the system. The human does not.** This is the clearest asymmetry in the corpus:

> Evidence: probe I ran against real Postgres (one tenant, `principal_a` + `principal_b`, both holding `creative_id="cre_dup"`…): `PROBE_XP ready=False count=1 unapproved=['cre_dup'] reason=unapproved_creatives` — PR1718, `review-error-wire`

> Evidence: real wire, `TestClient` → `/a2a`, unauthenticated `tasks/get`: `{"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"Missing authentication token","data":null}}` — PR1547, `review-error-wire`

> posting `governance_agent` / `authentcation` / `credential` (each a one-character typo of a real field) makes `format_validation_error`'s `extra_forbidden` branch `json.dumps(input_val)` the credential into `AdCPValidationError.message`… observed in the INSERT parameters: `'error_message': '...\"credentials\": \"S3CRETzzz…\"...'` — PR1682, `review-security`

That last one is a credential-disclosure finding reachable from a single misspelled request key in production, proven by execution. Nothing in the human's 985 comments is of that kind.

**Third-party library internals.** *"Class mapping proven through the production path (`Connection._handle_dbapi_exception` → `DBAPIError.instance(...)`): `QueryCanceled`, `DeadlockDetected`, `SerializationFailure`, `LockNotAvailable`, `TooManyConnections`, `AdminShutdown`, `DiskFull` **all** → `sqlalchemy.exc.OperationalError` ⇒ non-isolatable."* And: *"The SDK `adcp.exceptions.ADCPError` is a **different class hierarchy** from internal `src.core.exceptions.AdCPError`."*

**Git provenance.** *"The 3 exception imports were added at `4dcc2f076` and removed as dead by `de041fdcf`"*; *"`git grep -c safe_adcp_error d912a7ee9 -- src/` → exit 1 (absent)."* The panel shows its commands 5× more often (1.07 vs 0.21 per 10k chars).

**CI reality.** *"the author's 'make quality green' claim could not have seen it because `make quality` does not run `tests/harness/` — CI Unit Tests is FAILURE on exactly that test."*

**Spec grounding.** *"**74 INVALID_REQUEST gradings, 0 VALIDATION_ERROR**"* counted out of a `.feature` storyboard. The panel's spec/wire marker rate is 2.3× the human's per 10k chars.

The fair summary: the panel produces **deep, executed, single-site** findings across a wide surface. The human produces **shallow-per-site, exhaustively-enumerated, relational** findings across a narrow one. Neither dominates. The panel's real weakness is not depth, it is that its unit of output is a site and the defect's unit is a set. Its second weakness — established by prior work, not by me — is that depth can be confidently inverted: on issue #1775 the lens found the exact line, named the exact mechanism, and concluded the opposite of the truth under an `[observed]` tag. Nothing the human does has that failure mode, because a one-sentence relational claim has less room to be wrong.

---

## What I could not determine

- **Whether the ≤5 cap causes misses or only under-calls.** MISS is defined as "never cited at any severity," so the cap provably explains the 16.2% under-call and cannot directly explain the 51.9%. The 4.2-cites-per-finding ratio is suggestive of suppressed investigation; I have no way to test it.
- **Whether the human anchors on unchanged code more than the panel.** Both instruments failed (§3). This was my sharpest planned test.
- **Whether the human's findings are correct.** I graded shape, not truth. One case shows the reviewer falsifying a panel finding by execution; I have no sample on the other direction.
- **Hop 2 vs hop 3 is weak for the mega-PRs.** In a 255-file diff (PR1544) or 173-file (PR1547), "another file the PR changed" is nearly unconstrained. PR1673 and PR1682 heads were not fetched locally, so I used the cached `gh` file lists for those two.
- **Whether the detectors' *output is acted on*.** I measured invocation counts (198–330), not whether reports reflect the results. `detector-exec-test` and `detector-sweep-9` own that.
- **The 28.6% never-detected clusters.** I can size the block but have no mechanism for it, and no proposal I would defend.