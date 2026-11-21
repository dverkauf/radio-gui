#!/usr/bin/env python3
"""Preview on the existing user's Wayland desktop; never starts/stops a compositor."""
import os
from pathlib import Path
import subprocess
import sys

runtime = Path('/run/user') / str(os.getuid())
sockets = sorted(path for path in runtime.glob('wayland-*') if path.is_socket())
if len(sockets) != 1:
    raise SystemExit(f'Expected one Wayland socket; found: {sockets}')
env = os.environ.copy()
env['XDG_RUNTIME_DIR'] = str(runtime)
env['WAYLAND_DISPLAY'] = sockets[0].name
raise SystemExit(subprocess.call([
    sys.executable, str(Path(__file__).with_name('main.py')),
    '--platform', 'wayland', '--timeout', '120', *sys.argv[1:],
], env=env))
