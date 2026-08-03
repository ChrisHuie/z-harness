# Memory Index

- [AdCP kernel empirical anchors](adcp-kernel-empirical-anchors.md) — firsthand-verified drift/recovery/envelope facts grounding the cross-surface kernel API + runtime conformance-helper
- [Standalone & decoupled build](adcp-kernel-standalone-decoupled.md) — kernel/tooling built in repos we control; never coupled to salesagent or adcontextprotocol repos; inputs = published tarball + dump-hook only
- [Kernel tool is Go](adcp-kernel-tool-is-go.md) — the vendor/build/guards/CLI is a Go single static binary; per-language pieces (dump-hook, bindings, runtime helper) stay per-language
- [Synthetic tests self-confirm](synthetic-tests-self-confirm.md) — fixtures mirroring the parser's assumptions are a self-referential oracle; pair with a real-corpus fixture + completeness oracle
