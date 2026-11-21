"""Native Qt process/protocol checks, no audio devices or network access."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
from PySide6.QtCore import QCoreApplication, QProcess
from internet_bridge import InternetBridge


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.bridge = None

    def tearDown(self):
        if self.bridge is not None:
            self.bridge.shutdown()
            self.assertEqual(self.bridge._process.state(), QProcess.NotRunning)
        self.temporary.cleanup()

    def launch(self, script):
        path = Path(self.temporary.name) / 'peer.py'
        path.write_text('import json,sys,time\n' + script)
        self.bridge = InternetBridge(self.temporary.name, process_command=[sys.executable, str(path)])
        return self.bridge

    def until(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(predicate(), self.bridge.error)

    def test_fragmented_unicode_metadata_and_acknowledged_volume(self):
        bridge = self.launch('''
ready = json.dumps({'type':'ready','protocol':1,'stations':[{'id':'one','name':'עברית Ελληνικά'}],'volume':0.1},ensure_ascii=False).encode()+b'\\n'
sys.stdout.buffer.write(ready[:7]); sys.stdout.buffer.flush(); time.sleep(.02)
sys.stdout.buffer.write(ready[7:]); sys.stdout.buffer.flush()
for line in sys.stdin:
    r=json.loads(line)
    if r['command']=='quit': break
    if r['command']=='play':
        print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
        print(json.dumps({'type':'metadata','kind':'broadcast_text','text':'שיר / τραγούδι'}),flush=True)
    if r['command']=='volume': print(json.dumps({'type':'volume','value':r['value']}),flush=True)
    if r['command']=='stop': print(json.dumps({'type':'state','state':'stopped','volume_control':False}),flush=True)
''')
        self.until(lambda: bridge.state == 'idle')
        self.assertEqual(bridge.stations[0]['name'], 'עברית Ελληνικά')
        bridge.play('one')
        self.until(lambda: bridge.broadcastText == 'שיר / τραγούδι')
        self.assertEqual(bridge.state, 'playing')
        bridge.setVolume(.35)
        self.until(lambda: bridge.volume == .35)
        bridge.stop()
        self.until(lambda: bridge.state == 'stopped')
        self.assertFalse(bridge.volumeControl)

    def test_invalid_response_closes_input_and_peer_exits(self):
        bridge = self.launch("print('not json',flush=True)\nfor line in sys.stdin: pass\n")
        self.until(lambda: bridge._process.state() == QProcess.NotRunning)
        self.assertEqual(bridge.state, 'failed')
        self.assertIn('Invalid response', bridge.error)

    def test_crashed_peer_reports_failure(self):
        bridge = self.launch("sys.stderr.write('fixture startup failed\\n')\nraise SystemExit(1)\n")
        self.until(lambda: bridge.state == 'failed')
        self.assertIn('fixture startup failed', bridge.error)

    def test_shutdown_closes_input_even_without_quit_handling(self):
        bridge = self.launch("for line in sys.stdin: pass\n")
        self.until(lambda: bridge._process.state() == QProcess.Running)
        bridge.shutdown()
        self.assertEqual(bridge._process.state(), QProcess.NotRunning)
        bridge.shutdown()

    def switching_peer(self):
        return self.launch("""
print(json.dumps({'type':'ready','protocol':1,'stations':[{'id':s,'name':s} for s in ['a','b','c']],'volume':.1}),flush=True)
active = None
for line in sys.stdin:
    r=json.loads(line)
    if r['command']=='quit': break
    if r['command']=='play':
        if active is not None: raise RuntimeError('Overlapping playback')
        active=r['id']
        print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
        print(json.dumps({'type':'metadata','kind':'broadcast_text','text':active}),flush=True)
    if r['command']=='stop':
        time.sleep(.08)
        # A response already in transit must not undo the pending stop.
        print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
        active=None
        print(json.dumps({'type':'state','state':'stopped','volume_control':False}),flush=True)
""")

    def test_station_tap_switches_to_latest_without_overlap(self):
        bridge = self.switching_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.play('a')
        self.until(lambda: bridge.broadcastText == 'a')
        bridge.play('b')
        bridge.play('c')
        self.assertEqual(bridge.selectedId, 'c')
        self.until(lambda: bridge.broadcastText == 'c' and bridge.state == 'playing')
        self.assertEqual(bridge.station, 'c')

    def test_stop_cancels_pending_station_switch(self):
        bridge = self.switching_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.play('a')
        self.until(lambda: bridge.broadcastText == 'a')
        bridge.play('b')
        bridge.stop()
        self.until(lambda: bridge.state == 'stopped')
        self.assertIsNone(bridge._pending_id)
        self.assertEqual(bridge.selectedId, '')
        bridge.play('c')
        self.until(lambda: bridge.broadcastText == 'c')

    def test_switch_during_startup_and_repeated_tap(self):
        bridge = self.switching_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.play('a')
        bridge.play('b')
        self.until(lambda: bridge.broadcastText == 'b' and bridge.state == 'playing')
        bridge.play('b')
        self.assertEqual(bridge.state, 'playing')
        self.assertIsNone(bridge._pending_id)

    def test_delayed_volume_acknowledgement_does_not_move_requested_target(self):
        bridge = self.launch("""
print(json.dumps({'type':'ready','protocol':1,'stations':[{'id':'one','name':'one'}],'volume':.1}),flush=True)
for line in sys.stdin:
    r=json.loads(line)
    if r['command']=='quit': break
    if r['command']=='play': print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
    if r['command']=='volume':
        time.sleep(.08)
        print(json.dumps({'type':'volume','value':r['value']}),flush=True)
""")
        self.until(lambda: bridge.state == 'idle')
        bridge.play('one')
        self.until(lambda: bridge.state == 'playing')
        bridge.setVolume(.3)
        bridge.setVolume(.7)
        self.assertEqual(bridge.requestedVolume, .7)
        self.assertEqual(bridge.volume, .1)
        self.until(lambda: bridge.volume == .3)
        self.assertEqual(bridge.requestedVolume, .7)
        self.until(lambda: bridge.volume == .7)
        self.assertEqual(bridge.requestedVolume, .7)


if __name__ == '__main__':
    unittest.main()
