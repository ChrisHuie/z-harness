---
name: reference-port-fidelity-vs-target-norms
description: Core rule for Java↔Go adapter ports — target-repo review norms beat literal source fidelity; what a lean Prebid Go adapter PR actually contains
metadata: 
  node_type: memory
  type: reference
  originSessionId: aa049dfd-aa09-4a10-a1e2-61f821d8e096
---

When porting a prebid-server adapter (Java→Go), a 1:1 fidelity port reproduces the source behavior EXCEPT where the source holds a latent anti-pattern the TARGET repo's reviewers reject. For a Go PR, the Go maintainer's standard governs merge; fidelity is the means, conformance the end. Where they conflict, the target norm wins — record the divergence in `port-report.json` quirks[] and file an upstream issue against the source repo so both sides re-align deliberately.

Known latent-Java patterns that must change in the Go port (verified on Teal #4765):
- `getBidType` SILENT/unvouched constant fallback (e.g. always banner, masking an undeterminable type) is the bug. NUANCE (verified across 261 upstream adapters: 135 return `(BidType,error)`, 63 return bare `BidType` w/ a vouched constant): error-on-miss is the MAJORITY and correct DEFAULT (model: `teqblaze::getMediaTypeForBid`), BUT a constant fallback matching the source's REAL default is legitimate (e.g. `adkernelAdn`→`BidTypeVideo`). So: prefer error-on-miss; allow an operator-VOUCHED constant; flag only silent/unvouched/mis-typing fallbacks — do NOT force `(BidType,error)` unconditionally. Teal's Java source returned `BidType.banner` silently → a latent bug; Teal's correct fix was error+skip. (impsByID map: only 14/261 adapters use it → optional, not a forced default.)
- Media type handled in code but NOT in `static/bidder-info/{bidder}.yaml` capabilities → REMOVE the branch (not add to YAML). `adapters/infoawarebidder.go::pruneImps` strips undeclared media types before MakeRequests, so the branch is dead. Confirm the bidder genuinely doesn't support it (Java meta-info + docs.prebid.org) before removing.
- O(n) imp scan inside the bid loop → build `impsByID map[string]openrtb2.Imp` once.
- Silent "first valid imp wins" for request-level keys (e.g. account→publisher.id) → validate and error on divergence, or document.

A lean Prebid Go adapter PR contains ONLY the canonical corpus: `{bidder}.go`, `{bidder}_test.go` (thin TestJsonSamples runner), `{bidder}test/exemplary/*.json` + `supplemental/*.json`, `params_test.go`, `openrtb_ext/imp_{bidder}.go`, `static/bidder-{info,params}/{bidder}.{yaml,json}`, plus registry lines. NO `doc.go`, NO `*_fuzz_test.go`, NO `*_bench_test.go`, NO large Go-unit-test files — coverage belongs in JSON fixtures. Fuzz/bench are dev-time tools; pin any bug they find with a normal unit test. One adapter (incl. each alias) per PR. `aliasOf` YAMLs self-register via `config/bidderinfo.go::SetAliasBidderName` — no Bidder constant or params file needed. See [[project-teal-pr-remediation]].
