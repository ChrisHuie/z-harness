"""Review reproduction for PR 36 thread 4294811805: [P2] Recognize an AGENTS.md quotation across the whole sentence

Posted by the reviewer against head 2aea1fb at hooks/harness_check.py:1399, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811805.py
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
samples = [
    'AGENTS.md "Do not add AI co-author trailers to commits."',
    'AGENTS.md "Add a made-up mandatory policy."',
    'AGENTS.md says "Add a made-up mandatory policy."',
    'The policy "Add a made-up mandatory policy" is required by AGENTS.md.',
]
actual = []
for text in samples:
    findings, counts = m.claim_findings('skills/example/SKILL.md', text, policy)
    actual.append((len(findings), counts['claims']))
    print(repr(text), 'findings=', len(findings), 'claims=', counts['claims'])
assert actual == [(0, 1), (1, 1), (1, 1), (1, 1)]  # expected: a quote anywhere in the sentence is a claim
