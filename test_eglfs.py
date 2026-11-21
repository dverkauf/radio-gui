#!/usr/bin/env python3
"""Timed direct-display check. Temporarily ends/restores an active desktop session."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rotation', type=int, choices=[0, 90, 180, 270], default=90)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--keyboard-test', action='store_true')
    args = parser.parse_args()
    if not 10 <= args.seconds <= 120:
        parser.error('--seconds must be between 10 and 120')
    if os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY'):
        parser.error('Run from SSH or a native text console, not a desktop terminal.')
    base = Path(__file__).resolve().parent
    if not (base / 'main.py').is_file() or not Path('/dev/dri/card0').exists():
        parser.error('Prototype files or the observed /dev/dri/card0 are missing; rerun diagnostics.')
    connectors = list(Path('/sys/class/drm').glob('card0-*/status'))
    if not any(p.read_text().strip() == 'connected' for p in connectors):
        parser.error('No connected output on the previously observed card0; rerun diagnostics.')
    if shutil.which('timeout') is None:
        parser.error('GNU timeout is required.')
    subprocess.run(['sudo', '-v'], check=True)
    desktop_was_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'display-manager']).returncode == 0
    process = None
    stop_requested = False

    def interrupted(*_):
        raise KeyboardInterrupt
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, interrupted)
    try:
        with tempfile.NamedTemporaryFile(mode='w', prefix='radio-eglfs-', suffix='.json') as config:
            json.dump({'device': '/dev/dri/card0', 'hwcursor': False}, config)
            config.flush()
            env = os.environ.copy()
            for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'QT_QUICK_BACKEND', 'QT_QPA_EGLFS_ROTATION'):
                env.pop(name, None)
            env.update({'QT_QPA_EGLFS_INTEGRATION': 'eglfs_kms',
                'QT_QPA_EGLFS_KMS_CONFIG': config.name, 'QSG_RHI_BACKEND': 'opengl',
                'QT_LOGGING_RULES': 'qt.qpa.egldeviceintegration=true;qt.qpa.eglfs.kms=true;qt.qpa.input=true'})
            if desktop_was_active:
                # Set first so a partial stop is followed by a restoration attempt.
                stop_requested = True
                subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'display-manager'], check=True, timeout=30)
            print(f'EGLFS check: card0, rotation {args.rotation}, {args.seconds}s; Exit returns to desktop.', flush=True)
            process = subprocess.Popen(['timeout', '--signal=TERM', '--kill-after=5s',
                f'{args.seconds + 10}s', sys.executable, str(base / 'main.py'),
                '--platform', 'eglfs', '--rotation', str(args.rotation), '--timeout', str(args.seconds)]
                + (['--keyboard-test'] if args.keyboard_test else []),
                env=env, start_new_session=True)
            return process.wait(timeout=args.seconds + 20)
    except KeyboardInterrupt:
        return 130
    finally:
        # Repeated terminal interrupts must not interrupt display restoration.
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, signal.SIG_IGN)
        try:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass
        finally:
            if stop_requested:
                result = subprocess.run(['sudo', '-n', 'systemctl', 'start', 'display-manager'], timeout=30)
                if result.returncode:
                    print('Desktop restart failed. Run: sudo systemctl start display-manager', file=sys.stderr)
                else:
                    print('Desktop display-manager restarted.', flush=True)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError) as error:
        print(f'EGLFS qualification failed: {error}', file=sys.stderr)
        print('If the desktop is absent, run: sudo systemctl start display-manager', file=sys.stderr)
        raise SystemExit(1)
