"""Fake owned scan workers; no receiver, audio or network access."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from PySide6.QtCore import QProcess
from scan_bridge import ScanBridge
import test_internet_bridge as helpers


class Playback:
    activeSource = 'internet'
    state = 'playing'
    stops = 0
    def stop(self): self.stops += 1; self.state = 'stopping'


class ScanBridgeTest(unittest.TestCase):
    setUpClass = classmethod(helpers.BridgeTest.setUpClass.__func__)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.playback = Playback()
        self.bridge = None

    def tearDown(self):
        if self.bridge: self.bridge.shutdown()
        self.tmp.cleanup()

    def launch(self, body):
        path = Path(self.tmp.name) / 'peer.py'
        path.write_text('import json,sys,time,signal\nr=json.load(sys.stdin)\n' + body)
        self.bridge = ScanBridge(self.tmp.name, self.playback, process_command=[sys.executable, str(path)])
        return self.bridge

    def until(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents(); time.sleep(.005)
        self.assertTrue(predicate(), self.bridge.message)

    def test_progress_and_results_leave_internet_playing(self):
        b = self.launch("print(json.dumps({'type':'progress','message':'DAB 7A'}),flush=True)\nprint(json.dumps({'type':'results','items':[{'key':'x','name':'Radio','detail':'One','count':1}]}),flush=True)\n")
        b._source = 'dab'; b.scan()
        self.until(lambda: not b.busy)
        self.assertEqual(len(b.items), 1)
        self.assertEqual(self.playback.stops, 0)

    def test_rf_playback_must_acknowledge_stop_before_worker_starts(self):
        b = self.launch("print(json.dumps({'type':'results','items':[]}),flush=True)\n")
        self.playback.activeSource = 'fm'
        b._source = 'fm'; b.scan()
        self.assertEqual(self.playback.stops, 1)
        self.assertEqual(b._process.state(), QProcess.NotRunning)
        self.assertTrue(b.busy)
        self.playback.state = 'stopped'
        self.until(lambda: not b.busy)

    def test_cancel_waits_for_worker_cleanup(self):
        b = self.launch("signal.signal(signal.SIGTERM,lambda *_: (time.sleep(.1),sys.exit(0)))\nprint(json.dumps({'type':'progress','message':'Ready'}),flush=True)\ntime.sleep(10)\n")
        b._source = 'fm'; b.scan()
        self.until(lambda: b.message == 'Ready')
        b.cancel()
        self.assertTrue(b.busy)
        self.assertTrue(b.cancelling)
        self.until(lambda: not b.busy)
        self.assertEqual(b._process.state(), QProcess.NotRunning)

    def test_cancel_queued_scan_never_starts_worker(self):
        b = self.launch("raise RuntimeError('Must not run')\n")
        self.playback.activeSource = 'dab'
        b._source = 'fm'; b.scan(); b.cancel()
        self.playback.state = 'stopped'
        self.app.processEvents()
        self.assertFalse(b.busy)
        self.assertEqual(b._process.state(), QProcess.NotRunning)

    def test_settings_and_location_selection(self):
        b = self.launch("print(json.dumps({'type':'settings','locations':[{'name':'Hannover','channels':['7A']}],'location':'Hannover'}),flush=True)\n")
        b.open('dab')
        self.until(lambda: not b.busy)
        self.assertEqual(b.location, 'Hannover')
        b.setLocation('unknown')
        self.assertEqual(b.location, 'Hannover')

    def test_identification_updates_preview_without_save_signal(self):
        b = self.launch("print(json.dumps({'type':'identified','key':'x','item':{'key':'x','name':'Radio','detail':'PI: 0xD382','can_save':True},'message':'Review RDS'}),flush=True)\n")
        b._source = 'fm'
        b._items = [{'key':'x','name':'96.2 MHz','detail':''}]
        saved = []
        b.saved.connect(lambda: saved.append(True))
        b.identify(0)
        self.until(lambda: not b.busy)
        self.assertTrue(b.items[0]['can_save'])
        self.assertEqual(saved, [])
