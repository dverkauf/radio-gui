#!/usr/bin/env python3
"""Owned Wayland GUI supervisor; never changes the desktop/display manager."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys


def gui_command(base, args):
    command=[sys.executable,str(base/'main.py'),'--platform','wayland','--radio',
             '--rotation',str(args.rotation),'--timeout','0',
             '--ready-file',str(args.control_dir/'ready.json')]
    if args.config_dir:command+=['--config-dir',str(args.config_dir)]
    return command


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rotation',type=int,choices=[0,90,180,270],default=0)
    parser.add_argument('--control-dir',type=Path,required=True)
    parser.add_argument('--control-lock-fd',type=int,required=True)
    parser.add_argument('--config-dir',type=Path)
    args=parser.parse_args()
    # Confirm the controller's inherited lock exists and keep it until shutdown.
    os.fstat(args.control_lock_fd)
    process=None
    def interrupted(*_):raise KeyboardInterrupt
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupted)
    try:
        process=subprocess.Popen(gui_command(Path(__file__).resolve().parent,args),start_new_session=True)
        return process.wait()
    except KeyboardInterrupt:return 130
    finally:
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid,signal.SIGTERM)
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=5)
            except ProcessLookupError:pass


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,subprocess.SubprocessError) as error:
        print(f'Wayland GUI failed: {error}',file=sys.stderr)
        raise SystemExit(1)
