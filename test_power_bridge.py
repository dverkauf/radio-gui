"""Power state tests with fake helper subprocesses; never invoke sudo/systemctl."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from PySide6.QtCore import QProcess
from power_bridge import PowerBridge
from test_internet_bridge import BridgeTest


class PowerBridgeTest(unittest.TestCase):
    setUpClass = classmethod(BridgeTest.setUpClass.__func__)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.playback=SimpleNamespace(state='playing', stops=0)
        def stop():self.playback.stops+=1
        self.playback.stop=stop
        self.worker=SimpleNamespace(busy=False)
        self.bridge=None

    def tearDown(self):
        if self.bridge:
            self.bridge.shutdown()
            self.assertEqual(self.bridge._process.state(),QProcess.NotRunning)
        self.tmp.cleanup()

    def launch(self, body='print("OK")'):
        path=self.root/'helper.py'
        path.write_text('import sys,time\nfrom pathlib import Path\nPath('+repr(str(self.root/'calls'))+').open("a").write(sys.argv[1]+"\\n")\n'+body+'\n')
        self.bridge=PowerBridge(self.playback,[self.worker],command=[sys.executable,str(path)])
        return self.bridge

    def calls(self):
        path=self.root/'calls'
        return path.read_text().splitlines() if path.exists() else []

    def until(self, predicate):
        deadline=time.monotonic()+4
        while not predicate() and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.005)
        self.assertTrue(predicate(),self.bridge.message)

    def test_standby_waits_for_stopped_ack_and_wake_does_not_resume_audio(self):
        bridge=self.launch()
        bridge.standby()
        self.assertTrue(bridge.busy);self.assertEqual(self.playback.stops,1)
        self.assertEqual(self.calls(),[])
        self.playback.state='stopped'
        self.until(lambda:bridge.sleeping and not bridge.busy)
        self.assertEqual(self.calls(),['standby'])
        bridge.wake();self.until(lambda:not bridge.busy)
        self.assertFalse(bridge.sleeping)
        self.assertEqual(self.calls(),['standby','wake'])
        self.assertEqual(self.playback.state,'stopped')

    def test_busy_scan_or_save_blocks_power_request(self):
        bridge=self.launch();self.worker.busy=True
        bridge.standby();bridge.poweroff()
        self.assertFalse(bridge.busy);self.assertEqual(self.calls(),[])
        self.assertEqual(self.playback.stops,0)

    def test_full_shutdown_waits_for_cleanup_and_sends_only_poweroff(self):
        bridge=self.launch();bridge.poweroff()
        self.assertEqual(self.calls(),[])
        self.playback.state='completed'
        self.until(lambda:bridge._job=='' and self.calls()==['poweroff'])
        self.assertIn('power button',bridge.message)
        self.assertFalse(bridge.sleeping)
        # Accepted shutdown remains busy until the OS ends this GUI.
        self.assertTrue(bridge.busy)

    def test_failed_cleanup_never_turns_off_display_or_pi(self):
        bridge=self.launch();bridge.poweroff()
        self.playback.state='failed'
        self.until(lambda:not bridge.busy)
        self.assertEqual(self.calls(),[])
        self.assertIn('not confirmed',bridge.message)

    def test_stop_deadline_does_not_issue_power_request(self):
        bridge=self.launch();bridge.standby();bridge._stop_by=0
        bridge._check_stopped()
        self.assertFalse(bridge.busy);self.assertEqual(self.calls(),[])

    def test_helper_failure_is_reported_and_retry_allowed(self):
        bridge=self.launch('print("denied",file=sys.stderr);sys.exit(1)')
        self.playback.state='idle'
        bridge.standby();self.until(lambda:not bridge.busy)
        self.assertFalse(bridge.sleeping);self.assertIn('denied',bridge.message)

    def test_normal_gui_stop_restores_backlight(self):
        bridge=self.launch();self.playback.state='idle'
        bridge.standby();self.until(lambda:bridge.sleeping and not bridge.busy)
        bridge.shutdown()
        self.assertEqual(self.calls(),['standby','wake'])
        self.bridge=None

    def test_offscreen_mode_never_launches_privileged_helper(self):
        self.bridge=PowerBridge(self.playback,[],platform='offscreen')
        self.bridge.standby();self.bridge.poweroff()
        self.assertFalse(self.bridge.busy)
        self.assertEqual(self.playback.stops,0)
        self.assertEqual(self.bridge._process.state(),QProcess.NotRunning)


del BridgeTest
