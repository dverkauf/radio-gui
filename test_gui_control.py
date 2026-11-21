"""SSH ownership/controller checks; no sudo, desktop or DRM access."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import gui_control as control


class GuiControlTest(unittest.TestCase):
    def test_proc_start_parser_matches_current_process(self):
        self.assertTrue(control.process_start(os.getpid()).isdigit())

    def test_record_cannot_target_unrelated_process(self):
        record={'pid':os.getpid(),'start':control.process_start(os.getpid())}
        self.assertIsNone(control.owned_pid(record))
        self.assertIsNone(control.owned_pid({'pid':1,'start':'wrong'}))

    def test_stale_start_identity_is_rejected(self):
        with patch.object(control,'process_start',return_value='new'):
            self.assertIsNone(control.owned_pid({'pid':os.getpid(),'start':'old'}))

    def test_stopping_without_session_does_not_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(signal,'pidfd_send_signal') as send:
                self.assertEqual(control.stop(Path(directory)),0)
                send.assert_not_called()

    def test_runtime_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'la-calma-gui').symlink_to(root,target_is_directory=True)
            with patch.dict(os.environ,{'XDG_RUNTIME_DIR':directory}):
                with self.assertRaises(RuntimeError):control.runtime_directory()

    def test_stop_uses_pidfd_and_waits_for_exact_owned_process(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'session.json').write_text(json.dumps({'pid':123,'start':'test'}))
            with patch.object(control,'owned_pid',return_value=123), \
                 patch.object(os,'pidfd_open',return_value=999) as pin, \
                 patch.object(signal,'pidfd_send_signal') as send, \
                 patch.object(os,'close') as close, \
                 patch('select.select',return_value=([999],[],[])):
                self.assertEqual(control.stop(Path(directory)),0)
                pin.assert_called_once_with(123)
                send.assert_called_once_with(999,signal.SIGTERM)
                close.assert_called_once_with(999)

    def test_duplicate_start_does_not_touch_desktop(self):
        import argparse
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with (root/'launcher.lock').open('a+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with patch.object(subprocess,'run') as run:
                    self.assertEqual(control.start(root,argparse.Namespace(rotation=90,config_dir=None)),0)
                    run.assert_not_called()

    def test_main_stays_running_and_exits_cleanly_on_term(self):
        # Exercise readiness through the existing offscreen application in the
        # native suite. Isolated process avoids sharing QML lifecycle state.
        import importlib.util
        if importlib.util.find_spec('PySide6') is None:
            self.skipTest('Native Qt required')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config.json').write_text('{}')
            env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen';env['QT_QUICK_BACKEND']='software'
            ready=root/'ready.json'
            p=subprocess.Popen([sys.executable,str(control.BASE/'main.py'),'--radio','--platform','offscreen',
                '--config-dir',str(root),'--ready-file',str(ready)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                import time
                deadline=time.monotonic()+6
                while not ready.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.05)
                self.assertTrue(ready.exists(),'GUI failed to report ready')
                self.assertIsNone(p.poll())
                p.terminate()
                out,err=p.communicate(timeout=20)
                self.assertEqual(p.returncode,0,out+err)
            finally:
                if p.poll() is None:p.kill();p.wait()
