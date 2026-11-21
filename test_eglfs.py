#!/usr/bin/env python3
"""Direct-display launcher. Temporarily ends/restores an active desktop session."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import select
import shutil
import subprocess
import sys
import tempfile


def gui_command(base, args):
    command = [sys.executable, str(base / 'main.py'), '--platform', 'eglfs',
               '--rotation', str(args.rotation), '--timeout', str(args.seconds)]
    if getattr(args, 'control_dir', None):
        command += ['--ready-file', str(args.control_dir / 'ready.json')]
    if getattr(args, 'config_dir', None):
        command += ['--config-dir', str(args.config_dir)]
    command += ['--keyboard-test'] if args.keyboard_test else []
    command += ['--internet'] if args.internet else []
    command += ['--radio'] if args.radio else []
    if args.seconds:
        command = ['timeout', '--signal=TERM', '--kill-after=35s', f'{args.seconds + 10}s'] + command
    return command


def desktop_guard():
    # Authorize restoration while sudo credentials are fresh. This helper only
    # waits for our pipe to close and starts display-manager; the GUI stays user-owned.
    script = "import signal,subprocess,sys; signal.signal(signal.SIGHUP,signal.SIG_IGN); signal.signal(signal.SIGINT,signal.SIG_IGN); print('READY',flush=True); sys.stdin.buffer.read(); raise SystemExit(subprocess.run(['systemctl','start','display-manager']).returncode)"
    guard = subprocess.Popen(['sudo', '-n', 'setsid', '--wait', sys.executable, '-c', script],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    ready, _, _ = select.select([guard.stdout], [], [], 10)
    if not ready or guard.stdout.readline().strip() != b'READY':
        guard.stdin.close()
        try:
            guard.wait(timeout=5)
        except subprocess.TimeoutExpired:
            guard.terminate()
        raise RuntimeError('Cannot prepare desktop restoration; desktop has not been stopped.')
    return guard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rotation', type=int, choices=[0, 90, 180, 270], default=90)
    parser.add_argument('--seconds', type=int, default=60, help='Duration: 10..3600 seconds; 0 disables the timeout')
    parser.add_argument('--no-timeout', action='store_true', help='Run until stopped')
    parser.add_argument('--keyboard-test', action='store_true')
    parser.add_argument('--radio', action='store_true')
    parser.add_argument('--internet', action='store_true')
    parser.add_argument('--config-dir', type=Path)
    parser.add_argument('--control-dir', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--control-lock-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.internet or args.radio) and args.keyboard_test:
        parser.error('Playback and --keyboard-test cannot be combined')
    if args.no_timeout:
        args.seconds = 0
    if args.seconds != 0 and not 10 <= args.seconds <= 3600:
        parser.error('--seconds must be 0 or between 10 and 3600')
    if os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY'):
        parser.error('Run from SSH or a native text console, not a desktop terminal.')
    base = Path(__file__).resolve().parent
    if not (base / 'main.py').is_file() or not Path('/dev/dri/card0').exists():
        parser.error('Prototype files or the observed /dev/dri/card0 are missing; rerun diagnostics.')
    connectors = list(Path('/sys/class/drm').glob('card0-*/status'))
    if not any(p.read_text().strip() == 'connected' for p in connectors):
        parser.error('No connected output on the previously observed card0; rerun diagnostics.')
    if args.seconds and shutil.which('timeout') is None:
        parser.error('GNU timeout is required.')
    desktop_was_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'display-manager']).returncode == 0
    if desktop_was_active:
        subprocess.run(['sudo', '-n', '-v'] if args.control_dir else ['sudo', '-v'], check=True)
    process = None
    stop_requested = False
    guard = None

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
            if args.control_dir:
                env['QT_LOGGING_RULES'] = 'qt.qpa.egldeviceintegration=false;qt.qpa.eglfs.kms=false;qt.qpa.input=false'
            if desktop_was_active:
                # Set first so a partial stop is followed by a restoration attempt.
                guard = desktop_guard()
                stop_requested = True
                subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'display-manager'], check=True, timeout=30)
            duration = f'{args.seconds}s' if args.seconds else 'no timeout'
            if args.control_dir:
                # Root restoration is already authorized; detach only now.
                os.setsid()
                with open(os.devnull, 'rb') as null:
                    os.dup2(null.fileno(), 0)
            print(f'EGLFS: card0, rotation {args.rotation}, {duration}; use stop_gui from SSH to stop.', flush=True)
            process = subprocess.Popen(gui_command(base, args), env=env, start_new_session=True)
            return process.wait(timeout=args.seconds + 50 if args.seconds else None)
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
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass
        finally:
            if guard is not None:
                guard.stdin.close()
                try:
                    result = guard.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    result = 1
                guard.stdout.close()
                if result:
                    print('Desktop restart failed. Run: sudo systemctl start display-manager', file=sys.stderr)
                else:
                    print('Desktop display-manager restarted.', flush=True)
            elif stop_requested:
                print('Desktop needs restoration: sudo systemctl start display-manager', file=sys.stderr)



if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'EGLFS qualification failed: {error}', file=sys.stderr)
        print('If the desktop is absent, run: sudo systemctl start display-manager', file=sys.stderr)
        raise SystemExit(1)
