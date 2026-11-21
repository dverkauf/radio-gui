"""SSH start/stop controller for the one owned native GUI launcher."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent


def process_start(pid):
    # /proc comm may contain spaces and parentheses; fields follow the final ')'.
    text = Path(f'/proc/{pid}/stat').read_text()
    return text[text.rfind(')') + 2:].split()[19]


def runtime_directory():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    if not runtime.is_dir() or runtime.stat().st_uid != os.getuid():
        raise RuntimeError('User runtime directory is unavailable.')
    directory = runtime / 'la-calma-gui'
    if directory.is_symlink():
        raise RuntimeError('Unexpected runtime symlink.')
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory


def owned_pid(record):
    pid = record.get('pid')
    if type(pid) is not int or pid <= 1:
        return None
    try:
        if Path(f'/proc/{pid}').stat().st_uid != os.getuid() or process_start(pid) != record.get('start'):
            return None
        args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        launchers = [str(BASE / name).encode() for name in ('test_eglfs.py','run_gui_vnc.py')]
        if not any(path in args for path in launchers) or b'--control-dir' not in args:
            return None
    except (OSError, ValueError, IndexError):
        return None
    return pid


def read_record(directory):
    path = directory / 'session.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def stop(directory):
    record = read_record(directory)
    pid = owned_pid(record)
    if pid is None:
        print('No owned GUI launcher is running.')
        return 0
    # Pin the process identity before signalling: never kill an unrelated reused PID.
    fd = os.pidfd_open(pid)
    try:
        if owned_pid(record) != pid:
            print('GUI launcher already stopped.')
            return 0
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        deadline = time.monotonic() + 85
        import select
        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], 1)
            if readable:
                print('GUI stopped; the Wayland desktop remains running.' if record.get('mode') == 'vnc' else
                      'GUI stopped. Desktop restoration was handled by the launcher; check gui.log if it failed.')
                return 0
        raise RuntimeError('GUI shutdown is still pending. See gui.log; no unrelated processes were signalled.')
    finally:
        os.close(fd)


def vnc_environment():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    sockets = sorted(p for p in runtime.glob('wayland-*') if p.is_socket())
    selected = os.environ.get('WAYLAND_DISPLAY')
    if selected and (runtime / selected) in sockets:
        display = selected
    elif len(sockets) == 1:
        display = sockets[0].name
    else:
        raise RuntimeError('No unique existing Wayland display. Restore the desktop with stop_gui first.')
    env = os.environ.copy()
    env.update({'XDG_RUNTIME_DIR':str(runtime),'WAYLAND_DISPLAY':display})
    env.pop('DISPLAY',None)
    env.pop('QT_QPA_EGLFS_KMS_CONFIG',None)
    env.pop('QT_QPA_EGLFS_INTEGRATION',None)
    return env


def start(directory, args):
    vnc = getattr(args, 'action', 'start') == 'start-vnc'
    if not vnc and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise RuntimeError('Run start_gui from SSH or a text console.')
    if os.geteuid() == 0:
        raise RuntimeError('Run start_gui as your normal user, not with sudo.')
    lock = (directory / 'launcher.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        print('GUI launcher is already running or starting.')
        return 0
    desktop = not vnc and subprocess.run(['systemctl','is-active','--quiet','display-manager']).returncode == 0
    if desktop:
        subprocess.run(['sudo','-v'], check=True)
    ready = directory / 'ready.json'
    ready.unlink(missing_ok=True)
    state_home = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))
    logs = state_home / 'radio-gui'
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = logs / 'gui.log'
    # Keep one previous log rather than accumulating sessions indefinitely.
    if log.exists(): log.replace(log.with_suffix('.previous.log'))
    rotation = args.rotation if args.rotation is not None else (0 if vnc else 90)
    command = [sys.executable,str(BASE/('run_gui_vnc.py' if vnc else 'test_eglfs.py'))]
    if not vnc: command += ['--radio','--no-timeout']
    command += ['--rotation',str(rotation),'--control-dir',str(directory),
                '--control-lock-fd',str(lock.fileno())]
    if args.config_dir: command += ['--config-dir',str(args.config_dir.resolve())]
    env = vnc_environment() if vnc else os.environ.copy()
    env['PYTHONFAULTHANDLER'] = '1'
    # Keep normal diagnostics small; full Qt debug logs are only enabled on request.
    with log.open('wb') as output:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL if vnc else None, stdout=output, stderr=subprocess.STDOUT,
                                   pass_fds=(lock.fileno(),), env=env, start_new_session=vnc)
    record = {'pid':process.pid,'start':process_start(process.pid),'mode':'vnc' if vnc else 'eglfs'}
    temporary = directory/'session.tmp'
    temporary.write_text(json.dumps(record));temporary.replace(directory/'session.json')
    # The supervisor inherited the same open lock and holds it until cleanup exits.
    lock.close()
    deadline = time.monotonic()+50
    while time.monotonic()<deadline:
        code=process.poll()
        if code is not None:
            raise RuntimeError(f'GUI launcher exited with status {code}. See {log}')
        if ready.exists():
            print(f'GUI started without timeout. Stop with ./stop_gui\nLog: {log}')
            return 0
        time.sleep(.1)
    # Do not leave an unreported GUI instance running after startup failure.
    stop(directory)
    raise RuntimeError(f'GUI did not report readiness. See {log}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','start-vnc','stop'])
    parser.add_argument('--rotation',type=int,choices=[0,90,180,270],default=None)
    parser.add_argument('--config-dir',type=Path)
    args=parser.parse_args()
    directory=runtime_directory()
    return stop(directory) if args.action=='stop' else start(directory,args)


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f'GUI control failed: {error}',file=sys.stderr)
        raise SystemExit(1)
