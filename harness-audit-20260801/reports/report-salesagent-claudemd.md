The write was blocked by a harness hook (subagents must return findings as text, not report files). Full report follows.

---

# Audit: `salesagent/CLAUDE.md` vs. the CORE + skill rule structure

**Target:** `/Users/quantum/Documents/ComputedChaos/salesagent/CLAUDE.md` — 750 lines, last modified 2026-07-06 (`6cb856768`).
**Repo HEAD at audit time:** `6881e8da4`. Canonical remote `origin` = `https://github.com/prebid/salesagent.git` (confirmed; `github-desktop-affinity-com` is a second remote pointing at the fork).
**Rule source:** `result-arbitration.json` — 15 CORE rules, 4 skill buckets.
**Status:** read-only. No file in the repo was modified.

A second context file exists: `/Users/quantum/Documents/ComputedChaos/salesagent/tests/CLAUDE.md` (443 lines), auto-loaded for work under `tests/`. It is a party to one of the contradictions below.

---

## 1. Overlap — already covered by CORE or a skill bucket

| salesagent lines | What it says | Covering rule | Notes |
|---|---|---|---|
| **704-741** (38) | "Decision Tree for Claude" — 5 canned procedures | CORE(74,35) turn structure; CORE(57,44) plan gate; SKILL:review-practice(16,13,55) | Almost entirely generic. Only repo tokens: `make quality`, `tox -e integration`, the import-check one-liner. Also *conflicts* — C5. |
| **29-59** (31) | DRY invariant + example + "what DRY is NOT" | SKILL:review-practice(13,55) "grep the repo for the pattern, count the copies, fix every instance in the same commit"; (73,76) SSOT; (38,82); (16) | Principle covered four ways. Non-covered residue: `check_code_duplication.py`, pylint R0801, `.duplication-baseline`. ~4 lines. |
| **132-139** (8) | Spec-Grounding Gate | SKILL:prebid-adcp(30,102) — near-verbatim, incl. "SDK is a cross-check, not the authority" | Cleanest overlap in the file. Even its paths are adcp-spec-repo paths, not salesagent paths — they belong in the skill. |
| **519-527** (9) | Test Integrity Policy items 1/2/4 | SKILL:testing-ci(5), (37); CORE(85,52) | Items 3 and 5 are repo-specific and should stay. |
| **61-67** (7) | "What to Avoid" | Every bullet restates a section *in the same file*: L352-362, L145-162, L277-286, L29-59 | Pure intra-file duplication. Zero unique content. |
| **350-370** (21) | "Key Patterns → SQLAlchemy 2.0" + "Database JSON Fields" | Verbatim restatement of Pattern #3 (L171-184) | Intra-file duplication. |
| **641-646** (6) | Git Workflow | CORE(88,28); SKILL:git-workflow(23) | Covered *and* contradictory — C1, C7. |
| **565-583** (19) | Code Style + Type Checking | Generic except the mypy invocation, `Mapped[]`, `\| None` | ~6 lines survive. |
| **118-121** (4) | Guard rules | SKILL:testing-ci(78), (31), (56) | Partially covered; FIXME format is repo-local — and violated (C4). |
| **8-12** (5) | "Always read before writing", "pre-commit hooks are your friend" | CORE(89,84,83); base harness | L12 carries no instruction. |
| **380-389** (10) | "No Quiet Failures" | Weakly: CORE(85), SKILL:testing-ci(9) | Generic; harmless. |
| **745-750** (6) | "Support" | Nothing — content-free | |
| **648-655** (8) | "Hosting Options" | Nothing — a hosting brochure, partly false (S12) | |

**Subtotal: ~160-170 lines** become redundant or content-free once CORE + the four skills exist.

---

## 2. Contradiction

### C1 — HIGH. `gh pr create` is a mandatory step.

`CLAUDE.md:641-647`:
> ### Git Workflow (MANDATORY)
> **Never push directly to main**
>
> 1. Work on feature branches: `git checkout -b feature/name`
> 2. Create PR: `gh pr create`
> 3. Merge via GitHub UI

CORE (88, 28):
> Never run `git push`, `gh pr create/merge/comment` or `gh issue create` on your own initiative — prepare the artifact and stop. On explicit delegation, confirm once, then execute and report the URL.

The repo file marks `gh pr create` **MANDATORY** and numbers it as the routine second step. A repo-level file loading in every session in Chris's most-used repo currently authorizes the exact action CORE exists to gate.

### C2 — HIGH. The database-fixture examples contradict the file's own rule *and* `tests/CLAUDE.md`.

`CLAUDE.md:328`:
> - Never call `get_db_session()` in test bodies — test data setup belongs in factory fixtures

`CLAUDE.md:498-511`, 170 lines later:
```python
# Integration tests - use integration_db
@pytest.mark.requires_db
def test_something(integration_db):
    with get_db_session() as session:
        # Test with real PostgreSQL
        pass

# Unit tests - mock the database
def test_something():
    with patch('src.core.database.database_session.get_db_session') as mock_db:
        # Test with mocked database
        pass
```

`tests/CLAUDE.md:200-210` marks the first WRONG by name ("`get_db_session()` in test bodies … # WRONG — exists in 130+ test files"). `tests/CLAUDE.md:232-245` marks the second WRONG by name ("Manual mock setup instead of harness" — its WRONG example is literally `with patch("src.core.database.database_session.get_db_session") as mock_db`).

Three-way: root against itself, root against the nested file that loads simultaneously under `tests/`. Most dangerous of the set — the losing side is **copy-pasteable example code** presented as recommended, and `test_architecture_repository_pattern.py` rejects anything written from it.

### C3 — HIGH. Hardcoded versions, both stale, against a skill rule forbidding hardcoding them.

`CLAUDE.md:127`:
> This project targets AdCP spec **3.1.0-beta.3** via the `adcp==5.7.0` Python SDK.

Verified: `pyproject.toml:10` → `"adcp==6.6.0"`; `tests/unit/test_adcp_spec_version.py:5` → `EXPECTED_SPEC_VERSION = "3.1.1"`; installed `adcp.get_adcp_spec_version()` → `3.1.1`.

SKILL:prebid-adcp (101):
> read `ADCP_VERSION` / `adcp.get_adcp_spec_version()` from the installed package rather than assuming a pin. **Any literal version quoted in a rule is already stale; the pin moves.**

Wrong by a full SDK major version. Compounding it, `CLAUDE.md:136` gives the *correct* instruction ("the version the repo currently PINS") nine lines below the false literal.

### C4 — MEDIUM. The FIXME-id convention is contradicted 4.5:1 by the code it governs.

`CLAUDE.md:120`:
> Every allowlisted violation has a `# FIXME(#<gh-issue>)` comment at the source location — reference a GitHub issue/PR number, never a local beads id (beads ids don't resolve for outside contributors)

Measured across `src/` + `tests/`: **32** `FIXME(#nnnn)` vs **143** `FIXME(salesagent-…)`/`FIXME(beads-…)`. Beads-style ids sit inside the guard allowlists themselves — `tests/unit/test_architecture_repository_pattern.py:52` → `# FIXME(salesagent-qo8a): all _impl functions should use repositories instead of get_db_session()`, and `:85`.

Directionally it agrees with CORE(109,4) ("no beads/`bd` workflow"), so keep it — but it is intent stated as fact.

### C5 — MEDIUM. The Decision Tree pre-commits to multi-step plans with no approval gate.

`CLAUDE.md:706-713`:
> **User asks to add a new feature:**
> 1. Search existing code: `Glob` for similar features
> 2. Read relevant files to understand patterns
> 3. Design solution following critical patterns
> 4. Write tests first (TDD)
> 5. Implement feature
> 6. Run tests: `make quality`
> 7. Commit with clear message

CORE (57, 44): "Research-complete is not authorization: present the plan with every [DECISION] flagged and wait for approval before the first code edit, even in auto/accept-edits mode."
CORE (74, 35): "Work in single verified steps: restate the contract before executing, never pre-commit to multi-step plans."

Step 3 flows straight into step 5 with no gate. L715-721 (bug procedure) has the same shape. Step 7 is fine — CORE(88) pre-authorizes local git.

### C6 — MEDIUM, latent. DRY-now vs. scope-is-a-contract.

`CLAUDE.md:33,35`:
> - If you write a block of logic that is structurally similar to an existing block … you **MUST** extract a shared helper function
> - **NEVER** cite "avoid over-engineering" or "keep it simple" to justify leaving duplicated logic in place

CORE (53), detail:
> **PR scope is a contract, and a rule that would rewrite 3+ source files is its own PR.**

Opposite answers when duplication spans many files, and the repo file forecloses the scope objection *by name*. Not purely salesagent's doing: SKILL:review-practice(13,55) sides with the repo file. Flagging, not resolving — the seam is already in the arbitration output.

### C7 — LOW. Branch creation under-specified.

`CLAUDE.md:644` `git checkout -b feature/name` vs SKILL:git-workflow(23) "`--no-track origin/main` … verify with `git branch -vv`". If the repo file is what's in context, the agent loses the `--no-track` protection.

### C8 — LOW, voice.

`CLAUDE.md:3` `## 🤖 For Claude (AI Assistant)`; `:5` "This guide helps you work effectively with…"; `:12` "**Pre-commit hooks are your friend**". CORE(17) bans "marketing adjectives, praise, gratitude openers, **teaching framing** and soft sign-offs from every prose artifact."

---

## 3. Genuinely repo-specific — must stay

All verified present at HEAD.

| Lines | Content | Verification |
|---|---|---|
| 21-27 | Key file map | All 6 paths exist |
| 82-121 | Structural guard system | 90 `tests/unit/test_architecture_*.py` present; **all 27 files named in the table exist**; `docs/development/structural-guards.md` exists (22 KB) |
| 143-333 | The 8 critical architecture patterns | Non-derivable. Exception: L497-511 is wrong (C2); L352-370 duplicates L171-184 |
| 69-80 | Conventional Commits + release-please | `.github/workflows/pr-title-check.yml` enforces it — but allows **12** types (`feat fix docs refactor perf chore test ci build style revert security`); CLAUDE.md documents 6 |
| 393-461 | Docker/nginx at `localhost:8000`, `test123`, `ADCP_AUTH_TEST_MODE`, `uvx adcp`, migrations | Verified in `docker-compose.yml`, `src/admin/blueprints/auth.py`, `templates/login.html`; `adcp` console script ships in the wheel; `scripts/ops/migrate.py` exists; 180 alembic versions |
| 463-468 | Tenant → CurrencyLimit (USD) → PropertyTag (`all_inventory`) → Products | `CurrencyLimit` `src/core/database/models.py:496`; `PropertyTag` `:1997`; `all_inventory` in 5 `src/` files. High value |
| 474-480 | Test directory taxonomy | All 6 exist (repo also has `benchmarks/ migration/ smoke/ manual/ harness/ helpers/ fixtures/`, undocumented) |
| 482-486 | Error verification → `tests/CLAUDE.md § "Error Verification Policy"` | Resolves at `tests/CLAUDE.md:310`. Correct mechanism — the model for the rest of the file |
| 488-495 | Entity markers + `make test-entity ENTITY=` | Exact match against `tests/conftest.py:25 _ENTITY_MARKERS`, all 17; `Makefile:106` |
| 529-546 | Test infrastructure decision tree | `scripts/run-test.sh`, `.claude/skills/agent-db/agent-db.sh`, `make test-stack-up`/`.test-stack.env` all exist. Ports verified: `scripts/test-stack.sh:33` and `agent-db.sh:50` scan 50000-60000; `tests/e2e/conftest.py:213,216` scan 20000-25000 / 25000-30000 |
| 588-597 | `.env.secrets` keys | `APPROXIMATED_API_KEY` → `src/admin/blueprints/settings.py`; `GEMINI_API_KEY` → `src/core/config.py` |
| 599-602 | Schema map + **"legacy `tasks`/`human_tasks` no longer exist"** | Zero `__tablename__ = "tasks"/"human_tasks"` in `src/`. Unguessable negative fact — keep verbatim |
| 606-627 | Adapter registry + `creative_engine` caveat | Exact match against `src/adapters/__init__.py:18-25` |
| 461 | "Never modify existing migrations after commit!" | Repo convention |

**Gap (not staleness):** `make quality-full`, `make pre-pr`, `make test-int`, `make test-bdd`, `make test-e2e` exist in the Makefile and appear nowhere in CLAUDE.md. `make quality` = `quality-ci` + `pytest tests/unit/ -x`, where `quality-ci` runs 13 named hook scripts (`Makefile:15-29`); the file calls it "Format + lint + typecheck + unit tests".

---

## 4. Stale — verified

| # | Line(s) | Claim | Reality |
|---|---|---|---|
| **S1** | 127 | "spec 3.1.0-beta.3 via `adcp==5.7.0`" | `adcp==6.6.0`; spec `3.1.1`. **Wrong by a major version.** |
| **S2** | 85 | "73 `tests/unit/test_architecture_*.py`" | **90.** ("over 70" still true; the literal isn't.) |
| **S3** | 659-669 | Documentation index (9 entries) | **6 of 9 do not exist.** Present: `docs/security.md`, `docs/adapters/`. Missing: `docs/ARCHITECTURE.md`, `docs/SETUP.md`, `docs/DEVELOPMENT.md`, `docs/TROUBLESHOOTING.md`, `docs/deployment.md`, `docs/testing/`. Real: `docs/development/architecture.md`, `docs/development/GETTING_STARTED.md`, `docs/development/contributing.md`, `docs/development/troubleshooting.md`, `docs/deployment/` (dir), `docs/test-obligations/` + `docs/test-redesign/` |
| | | *Why it survived* | `check_docs_links.py` runs pre-push and in `make quality-ci`, and its filter `^(docs/.*\.md\|[^/]+\.md)$` **does** cover `CLAUDE.md` — but it only parses `[text](path)` and strips inline-code spans first. These are bare backticked paths. I ran it: "All documentation links are valid." |
| **S4** | 675-687 | `products = await client.tools.get_products(brief="video ads")` | fastmcp **3.2.0** `Client` has no `tools` attribute (`hasattr(Client,'tools')` → `False`); API is `call_tool`. Repo's own code: `await client.call_tool("get_products", {...})` (`tests/e2e/adcp_request_builder.py:35`, `tests/e2e/test_a2a_webhook_payload_types.py:43`). **Copy-pasteable and broken.** |
| **S5** | 37, 107 | "`check_code_duplication.py` pre-commit hook" / "(pre-commit + make quality)" | Zero `duplicat` matches in `.pre-commit-config.yaml`. Runs **only** from `make quality-ci` (`Makefile:19`). |
| **S6** | 514 | "Max 10 mocks per test file (pre-commit enforces)" | No such hook in `.pre-commit-config.yaml`, no script in `.pre-commit-hooks/`, not in `quality-ci`. Over-mocking tooling removed in the `#891` cleanup. **Unenforced.** |
| **S7** | 538 vs 432/558 | "all **5** envs" vs "all **6** suites" | `tox.ini:6` → `env_list = unit, integration, e2e, admin, bdd, ui` = **6**. File disagrees with itself. |
| **S8** | 433 | "`./run_all_tests.sh` — starts Docker, runs **tox -p**, tears down" | Rewritten to an in-network runner over `docker-compose.e2e.yml` publishing **no host ports** (`run_all_tests.sh:1-38`). Host `tox -p` now only on delegated `quick`/targeted paths (`:77` `exec run_all_tests_host.sh`). Outcome holds; mechanism doesn't. |
| **S9** | 448 | "`test-results/<ddmmyy_HHmm>/*.json` (last 10 runs kept)" | True for the **delegated** path (`run_all_tests_host.sh:23-27`, with `tail -n +11 \| xargs rm -rf`). The **default** path writes `test-results/innet_<ddmmyy_HHmm>/` (`run_all_tests.sh:100`) with **no retention**. Both the dir name and retention are wrong for the default command. |
| **S10** | 544 | "Port conflicts are minimized…" | Describes the superseded design. Default runner publishes no host ports at all, and `run_all_tests.sh:6-10` documents `scripts/test-stack.sh` as *still* subject to the TOCTOU race this paragraph calls fixed. |
| **S11** | 342 | "A2A Server: **python-a2a**" | `a2a-sdk[http-server]>=1.0.1` + `a2a-cli>=0.2.0` (`pyproject.toml:33-34`). No `python-a2a` installed. |
| **S12** | 651 | "Kubernetes - Full k8s manifests supported" | No `kind: Deployment` / `apiVersion: apps/v1` manifest anywhere in the repo. |
| **S13** | 120 | FIXME-id convention | See C4 — contradicted 143:32, including inside guard allowlists. |
| **S14** | 182 | "All tests require PostgreSQL: `./run_all_tests.sh` runs Docker + tox" | Superseded by S8; `tox -e unit` needs no DB, which `CLAUDE.md:429` states correctly. |

**Checked and NOT stale — do not touch:** adapter registry keys and the `creative_engine` caveat; `src/core/tools/` and `src/core/schemas/` as packages; all 27 guard files in the table; `.duplication-baseline`; `check_route_conflicts.py`; the 17 entity markers; the tenant dependency chain; `tasks`/`human_tasks` removal; **`session.query(` count in `src/` is 0**, so the SQLAlchemy 2.0 ban is currently clean and worth keeping as a regression guard; `uvx adcp` CLI; `test123`/`ADCP_AUTH_TEST_MODE`; `.env.secrets` keys; `scripts/run-test.sh`; `agent-db.sh`; `make test-stack-up`/`.test-stack.env`; `make test-entity`; `assert_envelope_shape` and the `tests/CLAUDE.md:310` pointer.

---

## 5. Size

Current **750 lines**; `craft-context-file` budget for a CLAUDE.md-class file is **under 200**.

| Block | Lines | Disposition |
|---|---|---|
| Header / task patterns / key files | 1-28 | Keep ~12 |
| DRY invariant | 29-59 | → review-practice; keep ~4 (enforcement) |
| What to Avoid | 61-67 | Drop — restates sections below it |
| Commit / PR titles | 69-80 | Keep; correct to the 12 accepted types |
| Structural guards + table | 82-121 | Keep the frame. The 31-line table is a self-described subset of 90 already pointing at `ls tests/unit/test_architecture_*.py`; compressing to that pointer + ~8 high-signal rows saves ~22. **Judgment call — I would keep the table and cut elsewhere.** |
| AdCP spec + Spec-Grounding Gate | 125-139 | Gate → prebid-adcp. Keep ~4. **Delete the literal versions** (C3/S1) |
| 8 critical patterns | 143-333 | The legitimate core. Fix C2; ~35 lines of example are generic. Target ~150 |
| Project Overview | 337-346 | Keep ~8; fix `python-a2a` |
| Key Patterns | 350-389 | ~21 duplicate Pattern #3. Keep ~12 |
| Common Operations | 393-468 | Keep ~55; correct S8/S9 |
| Testing Guidelines | 472-561 | Keep ~55 — highest-value repo content. Delete C2 examples, S6, S7 |
| Dev Best Practices | 565-583 | Keep ~6 |
| Configuration | 586-602 | Keep |
| Adapter Support | 606-627 | Keep |
| Deployment | 631-655 | Keep ~8; Git Workflow → CORE; Hosting Options → drop |
| Documentation index | 659-669 | Keep ~4 corrected pointers |
| Quick Reference | 673-701 | Rewrite MCP snippet to `call_tool` or drop. Keep ~10 |
| Decision Tree | 704-741 | Drop — generic and conflicting |
| Support | 745-750 | Drop |

**Landing zones:**
- **~250-280 lines** by removing what CORE and the skills now own, deleting dead sections, collapsing intra-file duplication, and fixing the stale items. Low risk; recommended target.
- **~180-200 lines** additionally needs the guard table compressed to its `ls` pointer and roughly half the worked examples cut. Hits the budget but gives up detail that has plausibly been working across 159 sessions.

**Highest-value structural move is not deletion.** It's the `tests/CLAUDE.md:310` pattern already used once at L482-486: replace prose with a pointer to a file maintained next to the code. The guard table, infra decision tree and adapter matrix are all candidates. A pointer can't go stale the way `73`, `3.1.0-beta.3` and `client.tools.get_products` did.

**One mechanical fix worth more than any pruning:** `check_docs_links.py` already runs over `CLAUDE.md` and already catches broken `[text](path)` links. The six dead doc references survived only because they're bare backticked paths. Converting the Documentation index to real markdown links puts that whole drift class under an existing gate — CORE(19,27,51): "Never promise to remember — build the gate."

---

## Do-not-remove list

- **8 critical architecture patterns** (143-333) minus the one broken example — encode conventions reading the code won't reveal.
- **Structural guard frame** (82-86, 118-121) — even if the table compresses, "allowlists only shrink" and the `ls` pointer must survive.
- **Tenant dependency chain** (463-468) and the **`tasks`/`human_tasks` negative fact** (602) — unguessable, both cause real failures when missed.
- **Test infrastructure decision tree** (529-546) — verified accurate apart from the "5 envs" cell; it's what stops an agent inventing its own Docker choreography.
- **Entity marker list** (488-495) — verified exact.
- **`tests/CLAUDE.md` pointer** (482-486).

Where genuinely unsure I said keep: guard-table compression, "No Quiet Failures", and the `session.query()` ban (zero violations in `src/`, so it's doing preventive work).