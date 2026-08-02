---
name: reference-adcp-sdk-spec-mapping
description: "adcp Python SDK release ↔ AdCP spec version mapping. SDK 4.3.0 targets spec 3.0.1; 4.4.x→3.0.5; 5.0–5.6→3.0.7; 5.7.x→3.1.0-beta.3; 6.6.0→3.1.1 (STABLE, current repo pin as of 2026-07-22). Verified via wheel's bundled ADCP_VERSION file. Mapping is not documented in PyPI metadata — only discoverable per-wheel."
metadata: 
  node_type: memory
  type: reference
  originSessionId: acdcab63-786c-4cc7-9c58-54f2c30d2c24
  modified: 2026-07-22T13:20:43.637Z
---

The `adcp` Python SDK ships Pydantic models code-generated from a specific AdCP spec version. The mapping is NOT documented in PyPI release metadata — it's only discoverable by inspecting the bundled `ADCP_VERSION` file inside each wheel.

**Verified SDK → spec mapping (as of 2026-05-24):**

| adcp SDK release | AdCP spec |
|---|---|
| 4.3.x | 3.0.1 |
| 4.4.x (4.4.0–4.4.3) | 3.0.5 |
| 4.5.x – 4.6.x | 3.0.5 |
| 5.0.x – 5.6.x | 3.0.7 |
| 5.7.x | 3.1.0-beta.3 (verified 2026-06-10 via installed wheel: `get_adcp_spec_version()`) |
| 6.6.0 | **3.1.1 (STABLE) — current repo pin as of 2026-07-22** (verified 4 ways: `get_adcp_spec_version()`, `pyproject.toml`, `docs/adcp-spec-version.md`, `test_adcp_spec_version.py`). NOTE: 3.1.1 is a stable release, not a beta — the earlier "6.x beta→3.1.0-beta" guess was superseded. The repo bumped 5.7.0→6.6.0 (spec 3.1.0-beta.3→3.1.1) between early-July reviews. |

**Verification commands:**

```python
import adcp
adcp.get_adcp_sdk_version()   # Python package version (e.g. "4.3.0")
adcp.get_adcp_spec_version()  # AdCP spec target (e.g. "3.0.1")
```

```bash
# Per-wheel without installing:
pip download adcp==X.Y.Z --no-deps && \
  python -c "import zipfile; z=zipfile.ZipFile('adcp-X.Y.Z-py3-none-any.whl'); print(z.read('adcp/ADCP_VERSION').decode())"
```

**Important context:**

1. **No SDK release targets spec 3.0.6.** Scope3 skipped from 3.0.5 (SDK 4.4-4.6) to 3.0.7 (SDK 5.x).
2. **Salesagent (Prebid Sales Agent) IS the AAO-tracked Python AdCP reference implementation.** The reference agents `signals-agent` and `creative-agent` are both archived (2025-10-28 and 2026-02-22). Salesagent is the only non-archived Python AdCP server AAO points at via `salesagent-ptr`.
3. **TS-first ecosystem.** `@adcp/sdk` (TS) has a daily auto-sync cron from the spec repo. Python SDK requires human-authored commits to bump. May 2026 release velocity: TS 48, Python 17, Go 0 (1 release in 7 months), Java 0 (never released).
4. **The spec repo IS a TypeScript application** — `package.json` at root, depends on `@adcp/sdk` as runtime dep. Spec's own conformance harness tests TS only.
5. **Wire-level adcp_version is release-precision only** (`"3.0"`, `"3.1"`) — patch-precision strings are accepted on input but normalized to release-precision on the wire.

6. **Spec-citation convention (set by #1355/#1356):** a code comment/docstring citing a spec version must name the version where the feature **entered the spec** (its introduction tag), NOT the SDK pin and NOT a later version that merely *references* the feature. Verify against upstream spec git tags (`github.com/adcontextprotocol/adcp`) — check that the cited section/field actually first appears at that tag (e.g. grep the section heading across `3.0.0` vs `3.0.0-rc`/`-beta`). Concrete corrections made: the two-layer error envelope + `context` echo are **3.0.0** (`error-handling.mdx`), not 3.0.6 (3.0.6 only added GOVERNANCE wire-placement guidance and referenced the model as pre-existing); `AUTH_REQUIRED` recovery is `correctable` in the spec's `error-code.json` since **3.0.0** — adcp 4.3.0's `STANDARD_ERROR_CODES` table classified it `terminal` (SDK-spec divergence); **adcp 5.7.0 fixed the table to `correctable`** (verified 2026-06-10; the only STANDARD_ERROR_CODES delta 4.3→5.7, same 36 codes). Salesagent's AdCPAuthenticationError/AuthorizationError still hardcode `_default_recovery=terminal` with docstrings citing the old 4.3 table — wire unaffected (explicit recovery always passed) but rationale now inverted. When unsure of the exact tag, cite the doc/schema file (`error-handling.mdx`, `core/product.json`) rather than guessing a patch version.

7. **Typed `AdCPError` subclass wire codes are constrained by the SDK's standard set (verify before creating one).** `adcp.server.helpers.STANDARD_ERROR_CODES` holds ~36 codes (4.3.0); `src/core/exceptions.py:117` HARD-ASSERTS every subclass's `_default_error_code` is standard, in `INTERNAL_CODES`, or remapped via `ERROR_CODE_MAPPING` to a standard target — so a class with a non-standard code FAILS the build unless mapped. Standard *entity* not-found codes that EXIST: `PRODUCT_NOT_FOUND`, `MEDIA_BUY_NOT_FOUND`, `PACKAGE_NOT_FOUND`, `ACCOUNT_NOT_FOUND`, `SIGNAL_NOT_FOUND`, `SESSION_NOT_FOUND`. Do NOT exist (must map to `INVALID_REQUEST`): `CREATIVE_NOT_FOUND`, `TASK_NOT_FOUND`, `FORMAT_NOT_FOUND`, `CONTEXT_NOT_FOUND`, bare `NOT_FOUND`. Consequence: a new creative/task/format not-found subclass gives the buyer NO distinct wire code (just `INVALID_REQUEST`) — the only wire gain is `recovery` (subclasses commonly flip `terminal`→`correctable`) + typed identity + guard-enforceability. A subclass declared in `exceptions.py` auto-registers in the status table (no P32 edit). **`context_id` ↔ spec session:** a non-resolving `context_id` is NOT_FOUND (`SESSION_NOT_FOUND`, correctable), NOT `AdCPGoneError`/`INVALID_STATE` — `Context` rows have no TTL/expiry/delete path in `src/`, so they never "expire."

**For verifying ANY adcp version in this codebase:** the canonical doc is `docs/adcp-spec-version.md` (will exist after Tier 1 PR lands). Also has bump procedure.
