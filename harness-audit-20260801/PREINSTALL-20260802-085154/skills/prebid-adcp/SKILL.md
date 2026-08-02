---
name: prebid-adcp
description: AdCP protocol authority and version resolution - grounds AdCP behavior in spec prose plus the graded conformance storyboard for the version pinned at runtime, treating SDK types, error codes and reference implementations as a read-only cross-check and never as the authority. Use when implementing, reviewing, or verifying AdCP protocol behavior, error taxonomy, recovery semantics, or SDK-to-spec version mapping.
---

# AdCP / Prebid protocol authority

## Precedence

When a project skill or repo doc names a different source of truth for AdCP behavior,
**this rule wins on the authority question** — the project skill still owns its own
workflow. Some project skills hardcode a stale spec pin or a local clone path belonging to
another machine; the authority order below supersedes those regardless.

## Authority order

1. **Spec prose** + the graded conformance storyboard for the pinned version, fetched
   verbatim via `gh api`.
2. **The installed artifact** — introspect it.
3. **Source.**

Cite **section + version** before implementing or reviewing.

**SDK error codes, types, and reference implementations are a read-only cross-check, never
the authority.** A code existing tells you nothing about *when* to emit it. This is not
theoretical: a change once shipped the **inverse** of the idempotency rule and survived
three review rounds because it was grounded in an SDK error code instead of spec prose.

**Do not trust WebFetch summaries** for normative MUST or version-timing questions — fetch
the text. Internal contract items still require a spec cross-check.

## Version resolution

**The adcp SDK release → spec-version mapping is discoverable only per-wheel.** Read
`ADCP_VERSION` / `adcp.get_adcp_spec_version()` from the installed package rather than
assuming a pin.

> Any literal version quoted in a rule — including in this file — is already stale. The pin
> moves; resolve it at runtime.

**Verify an SDK bump by introspecting the model and enum surface in BOTH versions and
diffing field-by-field.** Fix-what-broke scoping misses non-breaking schema changes that no
test catches.

## Error taxonomy and recovery

**A clean recovery-coherence check never closes the recovery question.** Ground
condition→recovery in AdCP spec prose, not in how a sibling surface happens to use it. The
substance lives in the error taxonomy — `error.json`'s recovery enum and
`transport-errors.mdx`.

## External claims

**Treat press and vendor blogs as leads only.** Ground external-system claims in the
installed artifact, then the spec repo, then source — in that order.
