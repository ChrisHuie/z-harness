I cannot write that file. The Write tool is blocked by a harness hook that fires deterministically on this path — both attempts returned:

> `Subagents should return findings as text, not write report files. Include this content in your final response instead.`

This is a harness policy on subagent output, not a transient failure. I'm not going to route around it with `Bash`/heredoc, since that would be evading an intercept that was deliberately placed. The full report is below — this message is the deliverable, and it reaches you the same way the file would have.

The triage is complete: all 8 files read and checked. Nothing was left unreached.

---

# Dormant CLAUDE.md triage — 8 repos

Shallow pass, scoped to the four categories. Everything verified against the repo (`ls`, `package.json` / `pyproject.toml`, and actually running the command where cheap).

**Verdict:** 2 repos need attention before reopening, 4 have small fixable defects, 2 are clean.

| Repo | Findings | Severity |
|---|---|---|
| docs-tools | duplicate clone of another repo's remote + 2 dead paths | **high** |
| prebid-server-go-agent-plugin | plan doc read as fact; ~20 unbuilt paths, 2 fake slash commands | **high** |
| prebid-integration-monitor | false "pre-commit runs automatically" claim; `rm` of live DB | medium |
| repo-activity-dashboard | 2 non-existent npm scripts; undocumented S3 fetch on build | medium |
| pr-agents | 1 wrong subcommand, 2 dead paths | low |
| documentation-toolkit | 2 dead paths | low |
| github-activity-db | 1 dead path in setup block | low |
| AgentORC | no findings | — |

---

## 1. docs-tools — `/Users/quantum/Documents/GitHub/docs-tools/CLAUDE.md` (175 lines)

### Wrong repo identity — duplicate clone (highest-harm finding in the set)

Not a line in the file; a property of the checkout that the file gives no warning about.

```
docs-tools             origin = https://github.com/ChrisHuie/documentation-toolkit.git
documentation-toolkit  origin = https://github.com/ChrisHuie/documentation-toolkit.git
```

Both directories track the **same remote**. `docs-tools` is the stale clone:

- `docs-tools` HEAD: `1afdd9e` 2025-06-27
- `documentation-toolkit` HEAD: `57ccece` 2025-10-07

Its CLAUDE.md describes the *old* layout (`src/repo_modules_by_version/`, 1 tool) while the live repo is at `src/repo_modules/` with 6 CLI entry points. Reopening `docs-tools`, making changes, and pushing would push ~3.5 months of regressions to `documentation-toolkit`'s origin. Neither CLAUDE.md flags the overlap.

### Dead paths

- `/Users/quantum/Documents/GitHub/docs-tools/CLAUDE.md:17` — `src/dev_tools/cleanup.py` ("Artifact cleanup utilities"). Evidence: `src/dev_tools/` contains only `__init__.py`, `cli.py`, `docs_sync.py`, `validator.py`.
- `/Users/quantum/Documents/GitHub/docs-tools/CLAUDE.md:22`, `:142` — `src/repo_modules_by_version/parsers/`. Evidence: that directory holds only `__init__.py`, `config.py`, `main.py`, `github_client.py`, `parser_factory.py`, `repos.json`, `version_cache.py`.

### Checked and correct

`repo-modules-by-version` and `validate-project` are both real `[project.scripts]` entries **in this clone's** `pyproject.toml` — correct here, even though upstream renamed the first to `repo-modules`.

---

## 2. prebid-server-go-agent-plugin — `/Users/quantum/Documents/ComputedChaos/prebid-server-go-agent-plugin/CLAUDE.md` (557 lines)

### Framing problem that causes every finding below

`:7` says "Implementation Plan", `:9` "Start small. Verify each step before moving on.", `:13` "Step 2: ...". This is a **forward-looking plan** sitting in CLAUDE.md, so it loads as always-on fact. An agent reopening this repo treats ~20 unbuilt files as existing. Fix is one sentence of framing, not a rewrite.

### Dead paths — "Directory Structure" block, `:455-493`

Evidence: full `find` over the repo. Actual contents are `commands/`, `hooks/`, `skills/`, `tests/`, `.claude-plugin/`, `.claude/`.

- `:456-480` — the entire `skills/pr-classification/` tree (`SKILL.md`, `SCHEMA.md`, `TAXONOMY.md`, `FIELD-MAPPING.md`, `rules/scope-detection.md`, `rules/yaml-only/*.md` ×12, `rules/multi-file/*.md` ×2). None exist. Real `skills/` holds 8 unrelated meta-skills: `writing-hooks`, `plugin-structure`, `writing-agents`, `writing-skills`, `writing-metadata`, `mcp-integration`, `writing-commands`, `component-decisions`.
- `:482-485` — `agents/` directory with `pr-scope-detector.md`, `bidder-info-yaml.md`, `multi-file-classifier.md`. Evidence: `ls -d agents` → No such file or directory.
- `:487-489` — `commands/classify-pr.md`, `commands/test-classification.md`. Evidence: `commands/` holds only `test-skills.md` and `.gitkeep`.
- `:492` — `tests/classification-cases.json`. Evidence: `tests/` holds `expected-skills.json`, `test-cases.json`, `validate-structure.sh`.
- Same unbuilt files re-asserted as a priority table at `:499-510`.

### Wrong commands

- `:518-524` — verification checklist runs `/classify-pr .../pull/NNNN` seven times. No `classify-pr` command exists.
- `:537` — `/test-classification`. Does not exist.

### Checked and correct

`:527` `./tests/validate-structure.sh` exists and is executable. Remote `ChrisHuie/prebid-server-go-agent-plugin` correct. Note: last commit `c6426cd` 2026-01-14, ~6.5 months old, not the 10-13 assumed.

---

## 3. prebid-integration-monitor — `/Users/quantum/Documents/GitHub/prebid-integration-monitor/CLAUDE.md` (813 lines)

### False safety-gate claim + broken command

`CLAUDE.md:419-427`:
```bash
npm run setup:hooks
# Pre-commit validation runs automatically
git commit -m "message"
npm run validate:pre-commit
```
Also asserted at `:731`.

Three verified facts:
1. `.githooks/` contains exactly one file: `pre-commit.disabled`. There is no `pre-commit`.
2. `git config core.hooksPath` already returns `.githooks` — `setup:hooks` has already been run, so **no hook fires on commit**. The comment at `:422` is false.
3. Running it: `npm run validate:pre-commit` → `sh: .githooks/pre-commit: No such file or directory`.

Someone deliberately renamed the hook to `.disabled`; CLAUDE.md never caught up. An agent trusting `:422` believes commits are validated when nothing runs.

### Destructive command, listed first among alternatives

- `:275-277` — under "Database issues", `rm data/url-tracker.db`. That DB exists and holds dedupe/scan state behind ~50k processed URLs (`batch-progress-*.json` ×8, `logs-batch-001`…`018`). The safer `--resetTracking` flag is offered at `:280`, *after* the `rm`.
- `:539` — `rm data/url-tracker.db-shm data/url-tracker.db-wal`, framed as removing "stale lock files". Both exist right now; if SQLite is live this drops uncommitted WAL data. No "stop the process first" caveat.

### Checked and correct

Every documented npm script exists (`build`, `build:check`, `test`, `test:all`, `test:critical`, `test:regression`, `test:stress`, `test:health`, `test:resilience`, `test:integration`, `validate:all`, `validate:integration`, `lint`, `format`, `docs:generate`, `sync-agent-docs`, `setup:hooks`). I expected `npm run lint` (`eslint . --ext .ts` on ESLint 9.28) to be rejected under flat config — **ran it, it works** and reports real errors, so not a finding. `bin/run.js`, `typedoc.json`, `scripts/sync-agent-docs.js`, `scripts/validate-integration.js` all exist. Remote `prebid/prebid-integration-monitor` matches `package.json`. Path scan clean — the only two misses (`:784`, `:786`) are naming-convention examples.

---

## 4. repo-activity-dashboard — `/Users/quantum/Documents/ComputedChaos/repo-activity-dashboard/CLAUDE.md` (252 lines)

### Wrong commands (both confirmed by running them)

- `:104` — `npm run lint  # Run ESLint`. Not defined in `package.json`; `npm error ... To see a list of scripts, run: npm run`.
- `:105` — `npm run typecheck  # Run TypeScript type checking`. Not defined; same failure. Nearest real script is `build:cli` (`tsc`).

### Undocumented side effect on the documented build command

`:102` — `npm run build`. `package.json` defines `"prebuild": "tsx src/scripts/syncMappingFromS3.ts"`, which npm runs automatically first. That script imports `@aws-sdk/client-s3`, reads `.env.local`/`.env`, and writes `store/sheets/github-mapping.json`. A plain build therefore makes a network call to S3 and can overwrite local mapping data. CLAUDE.md documents neither the prebuild nor the AWS dependency, and never mentions the `sync:mapping` or `validate` scripts that also exist.

### Checked and correct

`dev`, `start`, `test`, `test:watch`, `test:coverage`, `generate:stats`, `process:mapping` all exist. File-structure block `:113-138` fully verified, incl. `src/components/HorizontalBarChart.tsx`, `src/scripts/generateContributorStats.ts`, `src/scripts/processGithubMapping.ts`, `store/repos/`, `store/sheets/`. `:6` "Next.js 14" matches `"next": "^14.2.32"`. The `:176` security claim ("company affiliations, in .gitignore") is **true** — `git check-ignore` resolves to `.gitignore:54 store/sheets/` and neither file is tracked. Remote `prebid/repo-activity-dashboard` correct.

---

## 5. pr-agents — `/Users/quantum/Documents/GitHub/pr-agents/CLAUDE.md` (1004 lines)

### Wrong command

`:426` — `python -m src.pr_agents.config.cli test-pattern "modules/exampleBidAdapter.js"`. No `test-pattern` subcommand. Evidence: `grep -rn 'test-pattern' src/` returns nothing; `cli.py` registers `validate`, `migrate`, `test`, `check`, `watch`, `list`, `show`. Nearest real subcommand is `test`.

### Dead paths — "Component 2: Repository Structure Configuration", `:719-722`

- `:721` — `src/pr_agents/config/repo_structure.py`. Does not exist.
- `:722` — `config/repository_structures.json`. Does not exist; `config/` holds `repositories.json`, `README.md`, `prebid/`, `prebid-context/`, `schema/`.

### Checked and correct

`:8-11` `uv run black/ruff/pytest` and `pytest -m unit` all valid (the `unit` marker is declared in `pytest.ini`). `:14-15`, `:417-423` — I expected `python -m src.pr_agents.config.cli` to break given `packages.find where = ["src"]`, but **verified via `importlib.util.find_spec` that it resolves** as a namespace package from the repo root; not a finding. `:19-23` Key Components paths all exist; `:101-116` coordinator paths all exist (most bare-filename "misses" in my first sweep were tree-diagram entries relative to a parent dir — discarded as false positives). No dangerous instructions: credentials at `:283-289`, `:873-876` are placeholders, and `:461`/`:996-999` require env-var storage. Remote `ChrisHuie/pr-agents`; no `salesagent`/`affinity-com` references.

---

## 6. documentation-toolkit — `/Users/quantum/Documents/GitHub/documentation-toolkit/CLAUDE.md` (756 lines)

### Dead paths

- `:596` (and the structure block ~`:62`) — `docs/cli_implementation_plan.md`. Evidence: `docs/` contains `checkpoint_manager.md`, `cli_consistency_analysis.md`, `module-compare.md`, `output_manager.md`. Note `cli_consistency_analysis.md`, cited on the adjacent line `:600`, **does** exist — only the implementation-plan file is missing.
- `:668` — "Add parser class to `src/repo_modules/parsers/`". Evidence: `src/repo_modules/` holds only `__init__.py`, `config.py`, `main.py`, `parser_factory.py`, `repos.json`.

### Worth knowing (not dangerous, but surprising)

`:727-745` — the mandated `validate-project` step 6 is "Sync docs — Syncs all agent instruction files (CLAUDE.md, AGENTS.md, GEMINI.md)". Running the validation the file requires rewrites CLAUDE.md/AGENTS.md/GEMINI.md in place. An agent should know the command edits the context file it is reading. Same caveat at `docs-tools/CLAUDE.md:163`.

### Checked and correct

All six `[project.scripts]` entry points exist and match documented CLI names (`repo-modules`, `module-history`, `validate-project`, `alias-mappings`, `supported-mediatypes`, `module-compare`). Structure block `:9-70` verified file-by-file across `shared_utilities/`, `dev_tools/`, `module_history/`, `alias_mappings/`, `supported_mediatypes/`, `module_compare/`. Remote `ChrisHuie/documentation-toolkit` — this is the *live* copy; `docs-tools` is the stale duplicate (finding 1).

---

## 7. github-activity-db — `/Users/quantum/Documents/ComputedChaos/github-activity-db/CLAUDE.md` (146 lines)

### Dead path in the first setup block

`:10` — `cp .env.example .env  # Add GITHUB_TOKEN`. Evidence: `ls .env.example` → No such file or directory. The `cp` errors out, and `GITHUB_TOKEN` is listed Required at `:99`, so setup stalls on the very first command block a returning agent would run.

### Checked and correct

`uv sync`, `uv run alembic upgrade head` (`alembic/` + `alembic.ini` present), `uv run ghactivity` (entry point `ghactivity = "github_activity_db.cli.app:app"`), mypy/ruff/pytest/pre-commit all valid. All seven doc links `:31-37` resolve. Key Modules `:71-93` all exist (`github/client.py`, `github/rate_limit/`, `github/pacing/`, `github/sync/`, `db/repositories/`). Remote `prebid/github-activity-db`. Not verified (low value): the "573+ tests" count at `:23`.

---

## 8. AgentORC — `/Users/quantum/Documents/GitHub/AgentORC/CLAUDE.md` (134 lines)

**No findings.** The most accurate file of the eight.

All 9 claimed `frontend/src/` subdirectories exist plus `main.tsx`. All 9 frontend scripts at `:75-83` exist in `frontend/package.json`; `packageManager: "pnpm@10.12.1"` + `pnpm-lock.yaml` confirm the pnpm-only rule at `:18`. Config files at `:51-54` exist with the exact names given (`tailwind.config.js`, `postcss.config.js` — `.js` not `.cjs`). Backend deps at `:96-104` match `backend/pyproject.toml` (`google-adk`, `pydantic`, `mypy`, `pytest`, `ruff`, `black`, `requires-python >=3.13` matching the "Python 3.13" claim at `:111`). Remote `ChrisHuie/AgentORC`.

One cosmetic note, not raised as a finding: `:125` `uv run pytest` exits 5 ("no tests collected") because `backend/` contains only `main.py`. Command valid, suite empty.

---

## Cross-cutting

- **No dangerous instructions in the classic sense** across all 8 files — no force-push, `--no-verify`, auto-merge, committed secrets, or `rm -rf`. The two behavioral ones worth calling dangerous are the false pre-commit claim in `prebid-integration-monitor` and the `rm data/url-tracker.db` listed ahead of the safe flag.
- **No `affinity-com/salesagent` fork references** in any of the 8 files. That defect is not present in this batch.
- **Remotes otherwise all correct** — `prebid/*` for the three org-owned repos, `ChrisHuie/*` for the personal ones. The single identity problem is `docs-tools` sharing `documentation-toolkit`'s remote.

## NOT COVERED

None. All 8 target files were read and checked against their repos.