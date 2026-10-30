# Runbook: publish an extension

Preconditions: signed in to a collective that owns the `@collective` prefix
(`swamp auth whoami`); for CI, a collective token with `extensions:push`.

```bash
swamp extension version --manifest extensions/<kind>/manifest.yaml      # next CalVer
swamp extension fmt extensions/<kind>/manifest.yaml                     # --check in CI
swamp extension quality extensions/<kind>/manifest.yaml                 # scorecard; --isolated matches the registry
swamp extension push extensions/<kind>/manifest.yaml --dry-run --json   # review report skeleton, no upload
swamp extension push extensions/<kind>/manifest.yaml --channel beta --release-notes '<text>'
swamp extension promote @collective/name <version> --channel stable
```

Before `push`: set `version` in the manifest to the computed CalVer, keep a sibling `_test.ts`
beside each type and run it with the Deno binary that `swamp doctor extensions --json` names,
pin every dependency, and make sure no file exceeds the limits in
references/concepts/extensions.md. Treat a scorecard below 14 of 16 locally as a list of
rules to address or to accept with a documented reason.

After: consumers run `swamp extension pull @collective/name --channel beta`; a bad release is
withdrawn with `swamp extension yank @collective/name <version> --reason '<text>'` and
restored with `unyank`. `deprecate --superseded-by` points users at a replacement.
