---
name: project-tech-stack-audit
description: "The 2026-07-13 tech-stack due-diligence audit (7 web-verified lenses): the stack is sound/current/convergent-with-industry; the concrete pins, flags, and two pending library decisions (pydantic-ai, FastMCP) not yet folded into the docs."
metadata:
  node_type: memory
  type: project
  originSessionId: 1a4d69cf-6b26-472b-b224-242ef8a4868a
---

<!-- audit-2026-08-01 -->
> **STALE as of 2026-08-01.** Verified no longer accurate during the memory-consolidation audit. Kept for history; do not act on it.
> Evidence: (1) The 'two library decisions — ANALYZED, NOT YET in the docs' claim is false: both landed. docs/BUILD-PLAN.md:157 now reads 'Language / packaging: Python 3.13 · uv + hatchling', and docs/design/tran


**A 7-lens, web-verified tech due-diligence audit (2026-07-13).** Headline: the stack is **sound, current, zero technology switches** — and *convergent with where the whole agentic-payments industry landed* (RFC 9421 everywhere; the A2A+AP2+x402 tri-layer = our exact model; DBOS same-DB atomicity = the correct money-kernel choice). Delivered as an **Artifact** (private): https://claude.ai/code/artifact/6c7f13a9-7064-40c7-8e45-f6b9b435b801 (favicon 🔍, republish the same scratchpad file path to update the same URL). Relates to [[project-configuration-first]] (own-the-port-swap-the-impl is what makes the two decisions below low-stakes).

**Pins (KEEP unless noted):** DBOS **2.26.0** · **Python 3.13** (resolves a real 3.12-vs-3.13 doc inconsistency — memory/docs said 3.12, pin 3.13) · pydantic **2.13.x** · **FastAPI 0.139 on Starlette 1.3** (NOT Litestar — decided by SDK integration; ends the "FastAPI/Starlette" slash in ARCHITECTURE §210) · **granian** prod + **uvicorn** dev · **psycopg 3** (not asyncpg) + **SQLAlchemy 2.x Core** (not ORM) · **Alembic** (app tables; DBOS self-migrates its own) · **pyright --strict** (type gate; pyrefly optional; ty deferred) · **uv + hatchling** · **ruff** (pin exact) · **Hypothesis** (its state-machine testing = THE way to test the I1–I15 kernel) + pytest-bdd + schemathesis · RFC-9421 + JCS(rfc8785, Trail-of-Bits) + Ed25519 via **pyca/cryptography** (not PyNaCl) · **a2a-sdk 1.1.0**. OTel comes ~free via DBOS `enable_otlp`.

**2 correctness fixes:** (1) Python 3.12→3.13 across docs+memory. (2) `DecisionRecord.SamplingParams` (model-layer.md §5) is **OpenAI-shaped** — current Claude rejects `temperature`/`top_p`/`seed` (400) and exposes no seed; record `effort`+thinking-mode as a **provider-tagged union**. (Bonus: hosted-Claude has no reproducibility guarantee → *upgrades* record-and-replay from prudent to necessary.)

**Supply-chain FLAGS:** the RFC-9421 Python lib (`http-message-signatures`, thin/single-maintainer, on the money path → vendor/own a thin impl over pyca/cryptography); **httpx** (last release Dec-2024, issues disabled, transitively on the money path via TestClient+SDKs → pin + wrap OWN rail/sink calls behind a thin swappable client, niquests/aiohttp); **Astral tooling** (uv/ruff/ty) is OpenAI-owned → keep the money-kernel *type-gate* on a non-Astral checker (pyright/pyrefly). **Design calls to weigh:** VC-**JOSE-COSE** profile vs JSON-LD for the VCs (dodges weak Python VC tooling); freeze an explicit **object-signature-base profile** (`Content-Digest(JCS(object))`) for signed Reading/SettlementEvidence.

**The "incomplete" finding the user caught:** the whole **web/API + data + dev-tooling layer was genuinely UNDER-SPECIFIED in the docs** (DB driver, ORM strategy, migrations, type-checker, hot-path JSON, observability never decided; FastAPI-vs-Starlette left as a slash) — the audit resolves them above; recording those decisions in the docs is a follow-up.

**Two library decisions — ANALYZED, NOT YET in the docs (the base `prebid/salesagent` uses BOTH):**
- **pydantic-ai → ADOPT-WITH-GUARDRAILS** as the default `ModelAdapter` impl. Its agent-loop usage would VIOLATE the decide seam (control-flow + effect surface); but **proposer-only mode** (`output_type=Proposal`, zero tools, NativeOutput) = exactly `ModelAdapter.decide`, upstream of the Gate, money-wall untouched. **MIT-licensed** (de-risks the VC-single-vendor flag). Guardrails: `pydantic-ai-slim` only · never register tools · capture raw I/O at the **httpx layer we own** (not its `ModelMessage`) · **Logfire OFF the money path** · retries controlled (each call = a recorded egress) · behind our hand-authored port (reversible). **Harvest-compatible** (keep the base's lib, constrain how). → fold guardrails into `model-layer.md`.
- **FastMCP → SWITCH** off the base's PrefectHQ standalone `fastmcp` (`>=3.2,<3.3`; broke our ASGI-mount surface twice in 5mo) **to the official `mcp` SDK** (`>=1.28,<2`; stable v2 ~2026-07-27 IS the 2026-07-28 stateless spec). Reframing fact: standalone fastmcp is *built ON* the official `mcp` (transitive dep) → switch is **down-stack-compatible**, not a rewrite. Wins on all 3 high-weight axes (LF/AAIF-governed neutral · steadier · IS the stateless impl); base's DX extras go unused by our hand-authored projections. Migration = 4 bounded spots (dep · tool-reg ~1:1 · mount · re-home the per-call auth/idempotency capture, which `transport-coex.md` §2/§6 already relocates out of the library). Keep swappable via an `MCPServerLike` `typing.Protocol` (~3 methods) both servers satisfy. → fold into `transport-coex.md`.

**Base (`prebid/salesagent`, live pyproject 2026-07-13):** `fastmcp>=3.2,<3.3` · `a2a-sdk[http-server]>=1.0.1` · `adcp==5.7.0` (spec 3.1.0-beta.3) · `fastapi>=0.133` + `starlette>=1.0.1` + `uvicorn` · `pydantic-ai-slim` · Python `>=3.12`. (Corroborates FastAPI/Starlette/a2a-sdk/adcp; diverges on granian, Python 3.13, and the MCP switch.)
