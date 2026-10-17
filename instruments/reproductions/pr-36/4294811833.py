"""Review reproduction for PR 36 thread 4294811833: [P2] Preserve source order when binding elided quotations

Posted by the reviewer against head 2aea1fb at hooks/harness_check.py:1324, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811833.py
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
source = Path('hooks/harness_check.py').resolve()
spec = importlib.util.spec_from_file_location('subject', source)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

policy = (source.parent.parent / 'AGENTS.md').read_text()
normalized = m.normalize_policy_text(policy)
first, second = 'trailers to commits', 'do not add ai co-author'
assert normalized.count(first) == normalized.count(second) == 1
assert normalized.index(first) > normalized.index(second)
for text in [
    'AGENTS.md "Do not add AI co-author ... trailers to commits"',
    'AGENTS.md "trailers to commits ... Do not add AI co-author"',
]:
    findings, counts = m.claim_findings('skills/example/SKILL.md', text, policy)
    print(repr(text), 'findings=', len(findings), 'bound=', counts['bound'])
    if text.startswith('AGENTS.md "Do not add'):  # expected: source order binds, reversed does not
        assert not findings and counts['bound'] == 1
    else:
        assert findings and counts['bound'] == 0
