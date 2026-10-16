import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path.cwd()
source = repo / 'tools/install-claude.py'
spec = importlib.util.spec_from_file_location('installer', source)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
with tempfile.TemporaryDirectory() as home:
    for version in ('v1', 'v2'):
        installer.stage(str(repo), home, version_id=version)
    def cli(*args):
        return subprocess.run([sys.executable, str(source), *args, '--home', home],
                              capture_output=True, text=True)
    assert cli('--activate', 'v1').returncode == 0
    assert cli('--check').returncode == 0
    tree = Path(installer.tree_path(home, 'v2'))
    settings = Path(home) / '.claude/settings.json'
    before = settings.read_bytes()
    target = tree / 'hooks/bash_command_guard.py'
    target.write_text('raise RuntimeError("damaged staged hook")\n')
    activation = cli('--activate', 'v2')
    check = cli('--check')
    child = subprocess.run([sys.executable, str(target)], capture_output=True, text=True)
    print('damaged target: activation_exit=', activation.returncode,
          'check_exit=', check.returncode, 'hook_exit=', child.returncode,
          'settings_changed=', settings.read_bytes() != before)
    assert activation.returncode == 1 and check.returncode == 0 and child.returncode == 1
    assert 'changed hooks/bash_command_guard.py' in activation.stdout
    assert 'damaged staged hook' in child.stderr and settings.read_bytes() == before
    # A repair must still be able to switch away from a damaged active version.
    assert cli('--activate', 'v1').returncode == 0
    assert cli('--check').returncode == 0
    print('healthy target restores consistency: check_exit=0')
    shutil.copyfile(repo / 'hooks/bash_command_guard.py', target)
    (tree / 'CLAUDE.generated.md').unlink()
    before = settings.read_bytes()
    missing = cli('--activate', 'v2')
    state = installer.installation_state(home)
    print('missing instruction: activation_exit=', missing.returncode,
          'settings_changed=', settings.read_bytes() != before,
          'active_receipt=', state['active']['version'],
          'wired_versions=', sorted(state['wired_versions']),
          'pending=', state['pending'] is not None)
    assert missing.returncode == 1 and 'FileNotFoundError' not in missing.stderr
    assert 'missing CLAUDE.generated.md' in missing.stdout
    assert settings.read_bytes() == before and state['active']['version'] == 'v1'
    assert state['wired_versions'] == {'v1'} and state['pending'] is None
