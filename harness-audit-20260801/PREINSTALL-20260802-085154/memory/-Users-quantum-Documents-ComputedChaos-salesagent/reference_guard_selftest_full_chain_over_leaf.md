---
name: reference_guard_selftest_full_chain_over_leaf
description: "A structural-guard known-bad self-test must drive the guard's REAL entry point end-to-end, not a decomposed leaf — a leaf-only mutation oracle leaves the file-discovery/walker links un-covered"
metadata: 
  node_type: memory
  type: reference
  originSessionId: eaf223b9-a9a7-4c11-a176-b4b5209d97a3
---

When a structural guard scans discovered files for a bad pattern (e.g. `iter_hardcoded_python_version_yaml(repo)` → `git ls-files` → `_github_yaml_candidate` filter → read → line-matcher), its known-bad mutation self-test must call the **real public entry point** against a synthetic known-bad input, not a decomposed inner helper. Proven empirically (salesagent PR #1498, hardcoded-YAML-anchor detector): a self-test that calls only the extracted leaf line-matcher reddens when the matcher/regex is neutered but STAYS GREEN when the mid-chain walker or the `_github_yaml_candidate` file-filter is mutated to yield nothing — and the paired production guard (`assert not violations`) is green-when-empty, so a real violation escapes with the whole suite green. That is exactly the "mutating the detector to yield nothing keeps the suite green" hole such self-tests exist to close.

**Gold-standard pattern** — a full-chain self-test seeds a throwaway git repo and drives the real detector (mutation-matrix proved it reddens under leaf + walker + filter + regex mutations, all four):
```python
def _github_yaml_repo(tmp_path, rel, content):
    target = tmp_path / rel; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)  # ls-files needs a tracked file; no commit needed
    return tmp_path
# positive: bad workflow -> assert list(iter_hardcoded_python_version_yaml(repo))
# negative: python-version-file workflow -> assert list(...) == []   # covers skip_substr AND over-broad-regex false positives
```
`git add` (no commit, no user.name/email config) suffices — `git ls-files` lists staged files. These guards already shell to git, so a tmp-git fixture fits the convention.

**How to apply:**
- A leaf/in-memory matcher unit test is a PARTIAL oracle — acceptable as a fast complement, never as the sole known-bad self-test for a discovery-coupled guard.
- Add a NEGATIVE (known-good → yields nothing) case: it covers skip/allow branches and false positives that a truthiness-only `assert matches` can't. [[feedback_claimed_invariant_needs_failing_oracle]]
- Prove completeness by mutating EACH link to yield-nothing (monkeypatch the module attr in-process — no shared-tree edit) and confirming the test reddens for every one. [[feedback_no_mutation_agents_on_shared_worktree]]
- If a leaf was extracted from the walker SOLELY to enable a leaf test, and you replace it with a full-chain test, inline the single-use helper back — extraction of one-time code isn't required by DRY.
- Contrast: the sibling `assert_anchor_consistency(sources, ...)` detector takes injectable `(Path, text)` sources, so its self-test needs no git — discovery-coupled detectors don't have that seam. [[reference_review_patterns]]
