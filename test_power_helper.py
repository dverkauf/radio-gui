"""Power helper checks use fake sysfs files; no real brightness or shutdown calls."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import power_helper as helper
import install_power_controls as installer


class PowerHelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sysfs = self.root / 'backlight'
        self.sysfs.mkdir()
        self.state = self.root / 'state'
        self.state.mkdir()
        self.device = self.sysfs / '11-0045'
        self.device.mkdir()
        (self.device / 'brightness').write_text('137')
        (self.device / 'max_brightness').write_text('255')

    def tearDown(self): self.tmp.cleanup()

    def action(self, value): helper.backlight(value, self.sysfs, self.state)
    def brightness(self): return int((self.device / 'brightness').read_text())

    def test_standby_and_wake_restore_previous_brightness(self):
        self.action('standby');self.assertEqual(self.brightness(),0)
        self.assertEqual((self.state/'brightness.json').stat().st_mode & 0o777,0o600)
        self.action('wake');self.assertEqual(self.brightness(),137)
        self.assertFalse((self.state/'brightness.json').exists())

    def test_repeated_standby_does_not_lose_original_brightness(self):
        self.action('standby');self.action('standby');self.action('wake')
        self.assertEqual(self.brightness(),137)

    def test_wake_without_state_preserves_awake_desktop_brightness(self):
        self.action('wake');self.assertEqual(self.brightness(),137)

    def test_crash_recovery_without_state_uses_nonzero_brightness(self):
        (self.device/'brightness').write_text('0')
        self.action('wake');self.assertEqual(self.brightness(),255)

    def test_missing_panel_does_not_guess(self):
        (self.device/'brightness').unlink()
        with self.assertRaises(RuntimeError):self.action('standby')

    def test_ambiguous_panels_are_not_modified(self):
        second=self.sysfs/'second';second.mkdir()
        (second/'brightness').write_text('80');(second/'max_brightness').write_text('255')
        with self.assertRaises(RuntimeError):self.action('standby')
        self.assertEqual(self.brightness(),137)
        (self.device/'display_name').write_text('DSI-2')
        self.action('standby');self.assertEqual(self.brightness(),0)
        self.assertEqual((second/'brightness').read_text(),'80')

    def test_invalid_saved_brightness_is_clamped_to_valid_default(self):
        (self.state/'brightness.json').write_text('{"panel":"11-0045","brightness":-1}')
        (self.device/'brightness').write_text('0')
        self.action('wake');self.assertEqual(self.brightness(),255)

    def test_shutdown_uses_normal_systemd_poweroff_without_force(self):
        with patch.object(helper,'STATE',self.state), patch.object(helper.os,'geteuid',return_value=0), \
             patch.object(helper.os,'umask'), patch.object(helper.subprocess,'run') as run, \
             patch.object(helper.sys,'argv',['helper','poweroff']):
            # Unit-test process may not run as root; simulate only this ownership check.
            real_stat=Path.stat
            def stat(path,*args,**kwargs):
                result=real_stat(path,*args,**kwargs)
                if path == self.state:
                    from types import SimpleNamespace
                    return SimpleNamespace(st_uid=0,st_mode=result.st_mode)
                return result
            with patch.object(Path,'stat',stat):helper.main()
            run.assert_called_once_with(['/usr/bin/systemctl','--no-ask-password','poweroff'],check=True,timeout=10)

    def test_invalid_argument_never_invokes_systemctl(self):
        with patch.object(helper.sys,'argv',['helper','poweroff','extra']), patch.object(helper.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):helper.main()
            run.assert_not_called()

    def test_sudo_rule_grants_only_three_fixed_snapshot_commands(self):
        rule=installer.rule_for('dverkauf')
        self.assertEqual(rule.count('/usr/bin/python3 -I /usr/local/libexec/la-calma-power-helper.py '),3)
        self.assertNotIn('*',rule)
        self.assertNotIn('projects',rule)
        self.assertIn(' standby, ',rule);self.assertIn(' wake, ',rule)
        self.assertTrue(rule.endswith(' poweroff\n'))
        with self.assertRaises(ValueError):installer.rule_for('user ALL=(ALL) ALL')
