#!/usr/bin/python3
"""Install a fixed root-owned helper and exact sudo commands for the radio user."""
from pathlib import Path
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile

HELPER = Path('/usr/local/libexec/la-calma-power-helper.py')
RULE = Path('/etc/sudoers.d/la-calma-radio-power')
HEADER = '# La Calma GUI power controls v1\n'


def rule_for(user):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user):
        raise ValueError('Unsupported user name.')
    commands = ', '.join('/usr/bin/python3 -I ' + str(HELPER) + ' ' + action
                         for action in ('standby', 'wake', 'poweroff'))
    return HEADER + user + ' ALL=(root) NOPASSWD: ' + commands + '\n'


def install(user):
    if os.geteuid() != 0:
        raise RuntimeError('Run ./setup_power_controls as your normal radio user.')
    account = pwd.getpwnam(user)
    if account.pw_uid == 0:
        raise RuntimeError('Choose the normal radio user, not root.')
    source = Path(__file__).resolve().with_name('power_helper.py')
    code = source.read_text()
    if '# La Calma GUI power helper v1' not in code[:150]:
        raise RuntimeError('Unexpected helper source.')
    compile(code, str(source), 'exec')
    rule = rule_for(user)
    visudo = shutil.which('visudo')
    if not visudo:
        raise RuntimeError('visudo is required; nothing installed.')
    for path, marker in ((HELPER, '# La Calma GUI power helper v1'), (RULE, HEADER.strip())):
        if path.is_symlink() or (path.exists() and marker not in path.read_text()[:200]):
            raise RuntimeError('Refusing to replace an unrelated file: ' + str(path))
    if not RULE.parent.is_dir():
        raise RuntimeError('/etc/sudoers.d is unavailable.')
    fd, temporary = tempfile.mkstemp(prefix='.la-calma-power-', dir=RULE.parent)
    candidate = Path(temporary)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(rule)
        os.chmod(candidate, 0o440)
        subprocess.run([visudo, '-cf', str(candidate)], check=True)
        HELPER.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        helper_tmp = HELPER.with_suffix('.installing')
        if helper_tmp.is_symlink():
            raise RuntimeError('Unexpected helper temporary link.')
        # Snapshot code into a root-owned file; sudo never executes a writable checkout.
        with helper_tmp.open('w') as output:
            output.write(code)
        os.chown(helper_tmp, 0, 0)
        os.chmod(helper_tmp, 0o644)
        helper_tmp.replace(HELPER)
        os.chown(candidate, 0, 0)
        candidate.replace(RULE)
    finally:
        candidate.unlink(missing_ok=True)
    print('Installed restricted standby, wake and shutdown controls for ' + user + '.')
    print('GUI and PHP workers continue to run as the normal user.')


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise RuntimeError('Expected one normal user name.')
        install(sys.argv[1])
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
