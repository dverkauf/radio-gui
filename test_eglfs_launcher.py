"""Pure launcher checks; never stops a desktop or opens DRM."""
import argparse
from pathlib import Path
import unittest
from test_eglfs import gui_command


class EglfsLauncherTest(unittest.TestCase):
    def args(self, seconds):
        return argparse.Namespace(seconds=seconds, rotation=90, keyboard_test=False, internet=False, radio=True)

    def test_untimed_has_no_external_deadline(self):
        command = gui_command(Path('/tmp/gui'), self.args(0))
        self.assertNotEqual(command[0], 'timeout')
        self.assertEqual(command[command.index('--timeout')+1], '0')
        self.assertIn('--radio', command)
        self.assertEqual(command[command.index('--rotation')+1], '90')

    def test_timed_retains_outer_cleanup_deadline(self):
        command = gui_command(Path('/tmp/gui'), self.args(900))
        self.assertEqual(command[:4], ['timeout','--signal=TERM','--kill-after=35s','910s'])
        self.assertEqual(command[command.index('--timeout')+1], '900')

    def test_keyboard_mode_is_forwarded(self):
        args = self.args(0); args.radio = False; args.keyboard_test = True
        command = gui_command(Path('/tmp/gui'), args)
        self.assertIn('--keyboard-test',command)
        self.assertNotIn('--radio',command)
