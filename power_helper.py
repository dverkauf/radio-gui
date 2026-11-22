#!/usr/bin/python3
# La Calma GUI power helper v1
"""Installed root-owned snapshot: three fixed operations, no caller-supplied paths."""
from __future__ import annotations
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

BACKLIGHT = Path('/sys/class/backlight')
STATE = Path('/run/la-calma-radio-power')
SYSTEMCTL = '/usr/bin/systemctl'


def panel(root=BACKLIGHT):
    candidates = [p for p in root.iterdir() if (p / 'brightness').is_file()
                  and (p / 'max_brightness').is_file()]
    if len(candidates) > 1:
        candidates = [p for p in candidates if (p / 'display_name').is_file()
                      and (p / 'display_name').read_text().strip().startswith('DSI-')]
    if len(candidates) != 1:
        raise RuntimeError('Expected one touchscreen backlight; no brightness was changed.')
    selected = candidates[0]
    maximum = int((selected / 'max_brightness').read_text())
    current = int((selected / 'brightness').read_text())
    if not 1 <= maximum <= 65535 or not 0 <= current <= maximum:
        raise RuntimeError('Invalid touchscreen brightness range.')
    return selected, current, maximum


def replace(path, data):
    temporary = path.with_suffix('.tmp')
    if temporary.is_symlink():
        raise RuntimeError('Unexpected power state symlink.')
    with temporary.open('w') as output:
        os.chmod(temporary, 0o600)
        json.dump(data, output)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def backlight(action, root=BACKLIGHT, state=STATE):
    selected, current, maximum = panel(root)
    record = state / 'brightness.json'
    if action == 'standby':
        # Repeated standby must not replace the saved nonzero brightness with zero.
        previous = json.loads(record.read_text()) if record.exists() else {}
        restore = previous.get('brightness', maximum) if previous.get('panel') == selected.name else maximum
        if current > 0:
            restore = current
        if type(restore) is not int or not 1 <= restore <= maximum:
            restore = maximum
        replace(record, {'panel': selected.name, 'brightness': restore})
        (selected / 'brightness').write_text('0\n')
    elif action == 'wake':
        previous = json.loads(record.read_text()) if record.exists() else {}
        restore = previous.get('brightness', maximum) if previous.get('panel') == selected.name else maximum
        if type(restore) is not int or not 1 <= restore <= maximum:
            restore = maximum
        # Do not override a later desktop brightness change when already awake.
        if current == 0:
            (selected / 'brightness').write_text(str(restore) + '\n')
        if record.exists():
            record.unlink()
    else:
        raise ValueError('Invalid backlight operation.')


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('standby', 'wake', 'poweroff'):
        raise RuntimeError('Expected exactly standby, wake or poweroff.')
    if os.geteuid() != 0:
        raise RuntimeError('Use the installed, restricted power helper.')
    os.umask(0o077)
    if STATE.is_symlink():
        raise RuntimeError('Unexpected power state directory.')
    STATE.mkdir(mode=0o700, exist_ok=True)
    if STATE.stat().st_uid != 0:
        raise RuntimeError('Power state must be root-owned.')
    os.chmod(STATE, 0o700)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if sys.argv[1] == 'poweroff':
            subprocess.run([SYSTEMCTL, '--no-ask-password', 'poweroff'], check=True, timeout=10)
        else:
            backlight(sys.argv[1])
    print('OK', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
