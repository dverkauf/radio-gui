"""Wayland SSH mode checks without touching the user's desktop."""
import argparse
import os
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch
import gui_control as control
from run_gui_vnc import gui_command


class VncLauncherTest(unittest.TestCase):
    def test_command_has_wayland_and_no_timeout(self):
        args=argparse.Namespace(rotation=0,control_dir=Path('/tmp/control'),config_dir=None)
        command=gui_command(Path('/tmp/gui'),args)
        self.assertEqual(command[command.index('--platform')+1],'wayland')
        self.assertEqual(command[command.index('--timeout')+1],'0')
        self.assertEqual(command[command.index('--rotation')+1],'0')
        self.assertNotIn('sudo',command)

    def test_existing_socket_is_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                sock = socket.socket(socket.AF_UNIX)
            except PermissionError:
                self.skipTest('This execution environment blocks Unix sockets')
            with sock:
                sock.bind(str(Path(directory)/'wayland-1'))
                with patch.dict(os.environ,{'XDG_RUNTIME_DIR':directory,'WAYLAND_DISPLAY':''}):
                    env=control.vnc_environment()
                    self.assertEqual(env['WAYLAND_DISPLAY'],'wayland-1')
                    self.assertEqual(env['XDG_RUNTIME_DIR'],directory)
                    self.assertNotIn('DISPLAY',env)

    def test_missing_socket_does_not_start_desktop(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,{'XDG_RUNTIME_DIR':directory,'WAYLAND_DISPLAY':''}), \
                 patch.object(control.subprocess,'run') as run:
                with self.assertRaises(RuntimeError):control.vnc_environment()
                run.assert_not_called()

    def test_start_vnc_never_invokes_sudo_or_stops_display_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def spawn(command,**kwargs):
                (root/'ready.json').write_text('{"pid":456}')
                self.assertIn(str(control.BASE/'run_gui_vnc.py'),command)
                self.assertTrue(kwargs['start_new_session'])
                self.assertEqual(command[command.index('--rotation')+1],'0')
                return types.SimpleNamespace(pid=123,poll=lambda:None)
            with patch.dict(os.environ,{'XDG_STATE_HOME':str(root/'state')}), \
                 patch.object(control,'vnc_environment',return_value={}), \
                 patch.object(control,'process_start',return_value='ticks'), \
                 patch.object(control.subprocess,'Popen',side_effect=spawn), \
                 patch.object(control.subprocess,'run') as run:
                args=argparse.Namespace(action='start-vnc',rotation=None,config_dir=None)
                self.assertEqual(control.start(root,args),0)
                run.assert_not_called()
                self.assertIn('vnc',(root/'session.json').read_text())
