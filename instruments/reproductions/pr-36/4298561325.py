import contextlib
import importlib.util
import io
import re
from pathlib import Path
import shutil
import tempfile

repo = Path.cwd()
spec = importlib.util.spec_from_file_location('harness', repo / 'hooks/harness_check.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
claim = 'AGENTS.md says "A made-up mandatory policy."\n'
samples = {
    'baseline': '',
    'bare_claim': claim,
    'fenced_claim': '~~~text\n' + claim + '~~~\n',
    'mixed_fence_then_claim': '~~~text\n```\n~~~\n\n' + claim,
    'shorter_fence_then_claim': '````text\n```\n````\n\n' + claim,
    'inline_span_then_claim': '```AGENTS.md``` is a filename.\n\n' + claim,
}
observed = {}
with tempfile.TemporaryDirectory() as raw:
    root = Path(raw)
    for name in ('skills', 'contracts'):
        shutil.copytree(repo / name, root / name)
    shutil.copyfile(repo / 'AGENTS.md', root / 'AGENTS.md')
    reference = root / 'skills/ground-claims/references/review-fence-case.md'
    for name, content in samples.items():
        reference.write_text(content)
        run = harness.Run(str(root), ci=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run.c12_claim_binding()
        count = int(re.search(r'over (\d+) governed file', output.getvalue()).group(1))
        assert count == 86
        observed[name] = (len(run.failures), run.counters['C12']['claims'])
        print(name, 'governed_files=', count, 'failures, claims =', observed[name])
    base_claims = observed['baseline'][1]
    assert observed['baseline'][0] == 0
    assert observed['bare_claim'][0] > 0 and observed['bare_claim'][1] == base_claims + 1
    assert observed['fenced_claim'] == (0, base_claims)
    # These claims are OUTSIDE the example and are found like the bare one.
    for name in ('mixed_fence_then_claim', 'shorter_fence_then_claim', 'inline_span_then_claim'):
        assert observed[name] == observed['bare_claim']
