# Review reproductions for pull request 36

One script per inline review thread, kept verbatim from the reviewer's comment except for the
final assertion, which is inverted from the observed defect to the expected outcome. The selftest
of the tool each script exercises runs it as an acceptance case: the script must exit 0 and print
the expected observation line.

| thread | subject | run by |
|---|---|---|
| 4294811755 | interrupted switch: rollback restores one version's entries | `tools/install-claude.py --selftest` |
| 4294811762 | ownership identity carries event and matcher | `tools/install-claude.py --selftest` |
| 4294811773 | final stat to rename: the lost write is the documented residual; assertion unchanged | `tools/install-claude.py --selftest` |
| 4294811785 | a required scenario absent from the corpus makes `--run` red | `tools/run-skill-evals.py --selftest` |
| 4294811795 | a required scenario grades only after a child exit of 0 | `tools/run-skill-evals.py --selftest` |
| 4294811805 | a straight-quoted phrase anywhere in a sentence naming AGENTS.md is a claim | `hooks/harness_check.py --selftest` |
| 4294811820 | the worklist identity is the whole claim text | `hooks/harness_check.py --selftest` |
| 4294811833 | an elided quote binds only in source order | `hooks/harness_check.py --selftest` |
| 4294811841 | a disabled bound counter fails a named proof | `hooks/harness_check.py --selftest` |
| 4298561313 | the receipt vouches for the modules the interpreter loads, in its search order | `tools/install-claude.py --selftest` |
| 4298561334 | a staged target that no longer matches its receipt is refused before any write | `tools/install-claude.py --selftest` |

Each script loads the tool from its repository path and works in temporary directories or
in-memory copies; run from the repository root. The scripts define no selftest of their own and
are not registered suites. `ZH_REVIEW_REPRODUCTIONS=nested` in the environment tells a suite
launched by one of them not to run the reproductions again.
