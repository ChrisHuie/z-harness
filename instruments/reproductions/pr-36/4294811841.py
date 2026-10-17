"""Review reproduction for PR 36 thread 4294811841: [P3] Assert the bound-claim counters named by these tests

Posted by the reviewer against head 2aea1fb at hooks/harness_check.py:5649, kept verbatim;
the final assertion is inverted to the expected outcome.
Run from the repository root: python3 instruments/reproductions/pr-36/4294811841.py
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

import contextlib
import re
import types
text = source.read_text()
needle = 'counters["bound"] += 1'
assert text.count(needle) == 2
for label, code in [('baseline', text),
                    ('mutated', text.replace(needle, 'counters["bound"] += 0')),
                    ('restored', text)]:
    subject = types.ModuleType('counter_' + label)
    subject.__file__ = str(source)
    sys.modules[subject.__name__] = subject
    exec(compile(code, str(source), 'exec'), subject.__dict__)
    policy = (source.parent.parent / 'AGENTS.md').read_text()
    _, counts = subject.claim_findings('skills/example/SKILL.md',
        'AGENTS.md "Do not add AI co-author trailers to commits."', policy)
    assert counts['bound'] == (0 if label == 'mutated' else 1)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = subject.selftest()
    summary = re.findall(r'^SELFTEST-SUMMARY suite=harness_check .*$', output.getvalue(), re.M)[-1]
    print(label, 'bound_control=', counts['bound'], summary)
    if label == 'mutated':  # expected: the disabled counter fails a named C12 proof
        assert result == 1 and not summary.endswith('failures=0')
        assert any(line.startswith('  FAIL C12') and 'bound' in line
                   for line in output.getvalue().splitlines())
    else:
        assert result == 0 and summary.endswith('failures=0')
