# Runbook: serve locally with one worker

Terminal 1, in the repository:

```bash
swamp worker token create laptop --duration 1h          # copy the plaintext; it is shown once
swamp serve --port 9090                                  # loopback, no auth: local experiments only
```

Terminal 2:

```bash
swamp worker connect ws://localhost:9090 --token <name.secret> --cache-dir ~/.swamp/worker-cache --label os=mac
```

Terminal 3:

```bash
swamp worker list                                        # the worker is connected with its labels
swamp worker verify                                      # fleet probe: enrollment, scheduling, data plane
swamp workflow run <name> --server ws://localhost:9090 --detach
swamp workflow history get <run id> --server ws://localhost:9090
swamp worker queue                                       # steps waiting for a matching worker
```

Give the workflow, a job, or a step `labels: { os: mac }` or `target: laptop`. A placed step
needs `--server`; locally it queues up to the server's queue timeout (default 10m).

Leaving loopback: add `--cert-file` and `--key-file`, choose `--auth-mode token` or `oauth`,
name `--admins`, create grants (references/concepts/platform.md), mint user tokens with
`swamp access token mint`, and have clients run `swamp auth server-login --server wss://...`.
Run `swamp serve check-config` before starting. Revoke the worker token with
`swamp worker token revoke <name>` when done; connected workers are disconnected.
