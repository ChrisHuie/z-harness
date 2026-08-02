Settled. Repo untouched, tokens redacted, scratch clean.

## Answer: the nine are **copied**, not reconstructed — from `MEMORY.md`, auto-injected

### The capability

`--debug-file` alone does **not** expose the assembled prompt. It logs only `[API REQUEST] /v1/messages x-client-request-id=… source=sdk` — headers, no body (`/private/tmp/…/scratchpad/sp/dbg1.log`, 151 lines).

Two things do, and I used both:
- `ANTHROPIC_LOG=debug` — logs the request body, but Bun's console depth elides it to `system: [[Object ...], [Object ...], [Object ...], [Object ...]]`. Confirms shape, not content.
- **`BUN_CONFIG_VERBOSE_FETCH=curl`** — dumps every fetch as a complete curl command with `--data-raw` carrying the full JSON body. **This is the assembled request, verbatim.** Caveat: it also prints the OAuth bearer in cleartext. I redacted `sk-ant-*` from every capture; 0 residual hits.

### Q1 — Yes. Not a directory listing: the index itself, verbatim

Every agent's **first user message** carries a `<system-reminder>` containing:

```
Contents of <memory-dir>/MEMORY.md (user's auto-memory, persists across conversations):
```

…followed by the file verbatim. **Proven on a subagent with zero tools and a custom system prompt** — so it is unconditional, not gated on tools, agent definition, or CLAUDE.md.

For salesagent: `/Users/quantum/.claude/projects/-Users-quantum-Documents-ComputedChaos-salesagent/memory/MEMORY.md` is **118 lines / 19,355 B** and indexes **all 168** memory files — 0 missing, 0 dangling. Truncation caps are 200 lines / 25,000 bytes (binary constants `fie=200`, `PRe=25000`, applied by `Rtr()`), so it is injected **in full, unwarned**.

The nine §5 files sit at MEMORY.md lines **4, 5, 6, 8, 9, 37, 37, 53, 73** — strictly non-decreasing, i.e. **exactly §5's order**.

That one fact discharges every observation at once: naming nine files with no Read (the list is in context from token zero); 39/95 emitting all nine Reads in a single response (the whole list is visible before any result returns); 99.96% accuracy over a 169-file namespace (the exact filename list is verbatim in context); read by 0 of 759 runs (it never needs reading); and in-§5-order *higher* without the charter (they follow MEMORY.md; the charter adds a second, differently formatted copy that can perturb it).

### Why the falsification chain could not see it

**The JSONL strips the injected block from subagent transcripts.** Control, same request measured both ways: my pinger subagent's on-wire `msg[0]` was **11,308 B** of `<system-reminder>` (global CLAUDE.md + MEMORY.md); its transcript `/Users/quantum/.claude/projects/-Users-quantum-Documents-GitHub-agenticads-sim-plan/015393c8-5100-40e7-8e3a-15ba3db482d3/subagents/agent-a6f9e54c7d3120bec.jsonl` is **1,878 B across 2 records**, with zero occurrences of `CLAUDE.md` or `MEMORY.md`.

The JSONL omits more than system prompts. `report-close.md:21` marked "MEMORY.md auto-injected into context — dead" using an instrument that cannot observe the channel.

### Q2 — subagent assembly, decomposed

Structure measured live (2.1.220). A subagent gets 3 system blocks; it does **not** receive the main thread's 17,543 B `system[3]` — that block is main-thread only.

| block | bytes | content |
|---|---:|---|
| `system[0]` | 106 | billing header, carries `cc_is_subagent=true` |
| `system[1]` | 62 | "You are a Claude agent, built on Anthropic's Claude Agent SDK." |
| `system[2]` | agent-def + 1,676 | agent definition prompt, then standard subagent notes, `<env>`, gitStatus, recent commits |
| tools JSON | 32,145 | 9 tools — `Bash` 11,817 + `Agent` 8,868 = 64% of it |
| `msg[0]` | — | the injected reminder: claudeMd + **MEMORY.md** + userEmail + currentDate |
| `msg[1]` role=system | 5,451 | deferred-tool list + skills listing |

Applying salesagent's real file sizes (read from disk; I did not run a capture inside that repo):

| component | bytes | ~tokens |
|---|---:|---:|
| lens agent definition (median 8.2 KB; range 4,594–14,453) | 8,250 | 3,200 |
| subagent notes + env + gitStatus | 1,676 | 645 |
| tool definitions (9 tools) | 32,145 | 12,400 |
| `salesagent/CLAUDE.md` | 34,620 | 13,300 |
| `~/.claude/CLAUDE.md` | 10,368 | 4,000 |
| **MEMORY.md auto-memory index** | **19,355** | **7,400** |
| deferred-tools + skills listing | 5,581 | 2,150 |
| **total** | **112,163** | **~43,100** |

~43k of the ~55k floor. The residual ~12k is most plausibly a wider tool roster than my 9-tool capture — I did not measure salesagent's roster and am not claiming that number. The lens-vs-others spread has a sufficient explanation in the agent definitions alone: 4,594 → 14,453 B is ~3.8k tokens, the same order as the observed 5–9k gap.

### Q3 — what enumerates memory files

1. **`AutoMem` = MEMORY.md, verbatim.** Built by `Sn_()` → `{path: join(memoryDir,"MEMORY.md"), type:"AutoMem", content: Rtr(raw).content}`. Truncation is the only transform.
2. **`AutoMemPinned`** — up to 8 most-recently-modified memory files whose frontmatter has `pinned: true`, injected in full. **salesagent has 0 pinned files**; this channel contributed nothing.
3. **A recall index** (`memory_scan` → term index over all memory docs, `excludeBasenames:["MEMORY.md"]`, `memory_recall_select … via_index`) that can surface memories as later system-reminders. Not the first-turn channel.
4. **No directory listing is ever injected.** The dir scan `bds()` collects filename/description/type/pinnedState, but feeds only the pinned selector and the recall index — it is never rendered as a manifest.

### What this changes

- **"The nine are reconstructed, not copied" is falsified.** They are copied, through a channel that leaves no Read and no transcript trace. `FINDINGS.md:208-210` ("How a lens names 9 files it never read — Unreachable from transcripts") is answered and should move out of §7.
- **The audit's operational conclusion survives, with a stronger basis.** §5 all-nine "compliance" measures index-following, not charter-following. Dropping it as a compliance metric is still right.
- **A cost line item nobody attributed:** 19,355 B ≈ 7.4k tokens of MEMORY.md enter *every* dispatch, main and subagent — 32,060 subagent calls' worth of cache-resident bytes. §6's "cut the nine mandated memory files" removes the Read cost but not this; only editing MEMORY.md does.

### Not tested

- **No capture inside salesagent** (per your constraint). The mechanism is project-independent code captured live; salesagent's byte counts are read from its files, not from its wire.
- **Version coverage.** Captures are 2.1.220 (2026-07-25); the lens corpus spans 11 versions across June–July. I did not install older builds, and the JSONL cannot show the channel retroactively. The order evidence is version-independent — MEMORY.md's order *is* §5's order, a property of the files — but "auto-memory injection was live in every one of those 11 versions" is inferred, not measured.
- The ~12k residual in the floor decomposition.

**State:** no repo modified (`agenticads-sim-plan` clean; salesagent only read via absolute paths, never cwd). Side effects of invoking the CLI: session JSONL under `~/.claude/projects/`, and claude's own atomic rewrite of `~/.claude.json`. All artifacts in `/private/tmp/claude-501/-Users-quantum-Documents-GitHub-agenticads-sim-plan/e2367c8b-0c8b-43ae-a5d4-98ce3fbcecea/scratchpad/sp/` — captures `runD.err` (subagent with memory), `runE.err` (full decomposition), scripts `extract.py`, `dump.py`, `decomp.py`.