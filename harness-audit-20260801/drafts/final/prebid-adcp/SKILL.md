---
name: prebid-adcp
description: AdCP spec authority and version resolution — what the pinned version's prose and graded conformance storyboard require, with SDK types, error codes and reference implementations as a read-only cross-check, never the authority. Use when implementing or reviewing AdCP behavior, error codes or recovery classes, before citing an AdCP or SDK version, or when mapping an SDK release to a spec.
---

# AdCP / Prebid protocol authority

When a project skill or repo doc names a different source of truth for AdCP behavior, **this
skill wins on the authority question** — the project skill still owns its own workflow.

## Which version, and which text

- **Establish which version is authoritative before anything else** — the pin resolved at
  runtime by default, unless declared work targets a different one. Never ground against a
  version that is neither.
- **The SDK↔spec mapping is not in package metadata.** It is discoverable per-artifact only:
  read `ADCP_VERSION` / `adcp.get_adcp_spec_version()` off the installed wheel, never from
  release notes. Any literal version in a rule — including in this file — is already stale.
- **Cite the version where the feature ENTERED**, not the version you happen to pin.
- **A release-precision identifier space and a full-semver one false-positive on a naive
  equality check** — normalize both sides before comparing them.
- **Fetch normative text verbatim and read it yourself** (`gh api`). A summarizing fetch is
  unreliable for MUST/SHOULD and for version-timing questions. Cite section + version.

## What is authoritative — on what an implementation MUST do

1. **Spec prose + the graded conformance storyboard** for the pinned version.
2. **The installed artifact** — introspect it.
3. **Source.**

This specializes always-on's normative ladder; it does not compete with the other one. For
what an artifact **does** — which version it resolved, what it actually ships — the installed
thing is still read first, as the `ADCP_VERSION` rule above requires.

- **The SDK is a read-only cross-check that can diverge** — even when it ships a full reference
  implementation. Bind semantics to the **frozen objects**, never to a churning reference SDK;
  the SDK is the capture surface even where the spec reads neutral.
- **A downstream artifact shipping an error code tells you nothing about WHEN to emit it**, and
  an internal contract or gap item is not the spec. A change once shipped the **inverse** of the
  idempotency rule and survived three rounds because it was grounded in an SDK error code: two
  reviewers and three rounds can polish the wrong feature without questioning the premise.
- **An umbrella standard that delegates its transport owns only frozen-object semantics** — the
  object substrate is ratified, the agent-wire layer is reference-code-only, and the neutral
  cross-org primitives are the unowned seat.

## Error taxonomy and recovery

- **Ground condition→recovery in spec prose**, not in how a sibling surface happens to use it —
  the substance is `error.json`'s recovery enum and `transport-errors.mdx`. A clean
  recovery-coherence check never closes the recovery question.
- **Match the condition to the cited precedent's specific branch.** A surface match is a false
  premise, and a strong reviewer will confirm it and be wrong.

## Conformance and declarations

- **A grader clears your own system and only corroborates a third party's** — you own your
  internal log; for them you have observable responses only, which cannot distinguish a real
  implementation from a schema-valid shell.
- **Surface-minimization inflates a score.** Declaring few capabilities makes a slice look
  conformant, because **undeclared reads as "not tested", never as "failed"**. Grade declared
  breadth as first-class, cross-check it against observed behavior, and link every declaration
  to the per-item obligation it creates.
- **Grading an unknown check as PASS is forward-compat laundering** while the counterparty pins
  an old version — set a version floor at current-minus-N.
- **Extensions are additive-and-ignorable** — strip them and the payload is still valid under
  the base spec; prove it with a guard test.
- **A code generator can diverge from its spec and FORCE a value**, so the wire can carry a
  spec-questionable value that no local choice can fix.
