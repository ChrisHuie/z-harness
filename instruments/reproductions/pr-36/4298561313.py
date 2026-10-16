import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path.cwd()
spec = importlib.util.spec_from_file_location('installer', repo / 'tools/install-claude.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
prefix = 'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent / "guards"))\n'
cases = {
    'control': {'hooks/a.py': prefix + 'import lib\nprint(lib.VALUE)\n',
                'hooks/guards/lib.py': 'VALUE = 42\n'},
    'precedence': {'hooks/a.py': prefix + 'import lib\nprint(lib.VALUE)\n',
                   'hooks/lib.py': 'VALUE = 42\n',
                   'hooks/guards/lib.py': 'import missing_review_dependency\nVALUE = 43\n'},
    'inherited_path': {'hooks/a.py': prefix + 'import lib\nprint(lib.VALUE)\n',
                       'hooks/guards/lib.py': 'import helper_lib\nVALUE = helper_lib.VALUE\n',
                       'hooks/helper_lib.py': 'VALUE = 42\n'},
    'stdlib_shadow': {'hooks/a.py': 'import json\nprint(json.dumps({"ok": True}))\n',
                      'hooks/json.py': 'import missing_review_dependency\n'},
    'unexecuted_insert': {
        'hooks/a.py': 'import sys\nfrom pathlib import Path\nif False:\n    sys.path.insert(0, str(Path(__file__).parent / "guards"))\nimport lib\n',
        'hooks/guards/lib.py': 'VALUE = 42\n'},
}
observed = {}
for name, files in cases.items():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source, home = root / 'source', root / 'home'
        (source / 'hooks').mkdir(parents=True)
        (source / 'tools').mkdir()
        for filename in ('AGENTS.md', 'CLAUDE.md'):
            shutil.copyfile(repo / filename, source / filename)
        for relative, content in files.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (source / 'settings.json').write_text(json.dumps({'hooks': {'PreToolUse': [
            {'matcher': 'Bash', 'hooks': [{'type': 'command',
             'command': 'python3 ~/.claude/hooks/a.py', 'timeout': 5}]}]}}))
        receipt = installer.stage(str(source), str(home), version_id='v1')
        tree = Path(installer.tree_path(str(home), 'v1'))
        # All files and recorded digests match: these cases do not depend on corruption.
        assert all(installer.sha256_file(tree / rel) == record['sha256']
                   for rel, record in receipt['files'].items())
        problems = installer.hook_import_problems(str(tree), receipt)
        try:
            installer.activate(str(home), 'v1', processes=lambda: [])
            activated = True
        except installer.InstallError:
            activated = False
        check = installer.check(str(home), str(source), out=io.StringIO(), processes=lambda: [])
        child = subprocess.run([sys.executable, str(tree / 'hooks/a.py')],
            cwd=root, capture_output=True, text=True,
            env=dict(os.environ, HOME=str(home), PYTHONPATH='', PYTHONDONTWRITEBYTECODE='1'))
        observed[name] = (not problems, activated, check, child.returncode)
        print(name, 'preflight_clear, activated, check_exit, hook_exit =', observed[name])
        if name in ('precedence', 'stdlib_shadow'):
            assert 'ModuleNotFoundError' in child.stderr and 'missing_review_dependency' in child.stderr
        elif name == 'unexecuted_insert':
            assert "No module named 'lib'" in child.stderr
        else:
            assert child.stdout == '42\n'
assert observed == {
    'control': (True, True, 0, 0),
    'precedence': (False, False, 1, 1),
    'inherited_path': (True, True, 0, 0),
    'stdlib_shadow': (False, False, 1, 1),
    'unexecuted_insert': (False, False, 1, 1),
}
