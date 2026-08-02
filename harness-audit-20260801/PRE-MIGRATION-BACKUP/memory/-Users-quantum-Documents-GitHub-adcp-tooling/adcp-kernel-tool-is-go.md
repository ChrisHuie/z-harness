---
name: adcp-kernel-tool-is-go
description: The AdCP conformance kernel TOOL (vendor/build/guards/CLI) is written in Go; per-language pieces stay per-language.
metadata: 
  node_type: memory
  type: project
  originSessionId: 0ec17d38-47f0-44c3-8dba-412e46a45e03
---

The kernel **tool** — vendor, build (→ `derived.json`), the guards (drift/linter/coupling/schema-shape), and the future verifier/grader CLI — is written in **Go**, distributed as a single static binary (`go install` / GoReleaser).

**Why:** single-binary, zero-runtime-dep distribution across every consumer's CI regardless of stack; avoids the Python-wheel fragility we're partly fixing; ecosystem-coherent with `cosign` (Go) and the already-hardened `adcp-go` vendor/verify code we mirror.

**Boundaries:** per-language pieces stay in their languages — the **dump-hook** (e.g. a ~10-line Python snippet that introspects a Python SDK), the **generated bindings** (Python `error_codes.py`, TS, …), and the **P3 runtime conformance-helper** (embedded per agent). The Go tool only consumes their JSON; it never imports another language's SDK. "Python-first" was only ever correct for the reference *binding*, not the tool.

The data + contracts (`derived.json`, the bundle, the dump-hook contract, the query API) are language-neutral, so this was purely an implementation-language choice. Go gotcha: don't name the tarball-cache dir `vendor/` (Go reserves it) — use `cache/`. See [[adcp-kernel-standalone-decoupled]].
