# Runbook: share a repository's runtime data through a remote datastore

Definitions, workflows and vault configs are shared through git. Runtime data (`.swamp/`) is
shared through a datastore. Secrets are never shared this way: every machine holds its own
`local_encryption` values, or the team uses an extension vault such as `@swamp/aws-sm`.

```bash
swamp extension pull @swamp/s3-datastore                 # or @swamp/gcs-datastore
swamp datastore type search
swamp datastore setup extension @swamp/s3-datastore --config '{"bucket":"<b>","region":"<r>"}' --namespace <slug>
swamp datastore status
swamp datastore sync --pull                              # hydrate the local cache
```

The second machine clones the repository, runs `swamp extension install` to restore pulled
extensions from the lockfile, then `swamp datastore sync --pull`. For a team that wants one
writer, `swamp datastore claim --address <serve url>` makes serve the owner of a v3 store and
`swamp datastore release` undoes it. `swamp datastore config migrate` moves definitions,
workflows, vault configs and the lockfile into the datastore (`managedConfig: true`).

Diagnostics: `swamp datastore lock status`, `swamp doctor datastores --retention`,
`swamp datastore namespace list`. See assets/upstream/references/share/guide.md for the
full team promotion flow and joiner instructions.
