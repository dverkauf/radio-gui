"""Discovery isolation, cancellation and acknowledgement through fake owned peers."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from PySide6.QtCore import QProcess, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from discovery_bridge import DiscoveryBridge
from playback_bridge import PlaybackBridge
from keyboard_editor import KeyboardEditor
import test_internet_bridge as helpers


class DiscoveryBridgeTest(unittest.TestCase):
    setUpClass = classmethod(helpers.BridgeTest.setUpClass.__func__)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bridge = None

    def tearDown(self):
        if self.bridge:
            self.bridge.shutdown()
        self.tmp.cleanup()

    def launch(self, script):
        path = Path(self.tmp.name) / 'peer.py'
        path.write_text('import json,sys,time\nr=json.load(sys.stdin)\n' + script)
        self.bridge = DiscoveryBridge(self.tmp.name, process_command=[sys.executable, str(path)])
        return self.bridge

    def until(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(predicate(), self.bridge.message)

    def test_unicode_results_save_waits_for_acknowledgement(self):
        b = self.launch('''
if r['action']=='search':
 print(json.dumps({'type':'results','items':[{'key':'one','name':'עברית Ελληνικά','detail':'Publisher'}]}),flush=True)
else:
 time.sleep(.04)
 print(json.dumps({'type':'saved','name':'עברית Ελληνικά'}),flush=True)
''')
        saved = []
        b.saved.connect(lambda: saved.append(True))
        b.search('Ελληνικά')
        self.until(lambda: not b.busy)
        self.assertEqual(b.items[0]['name'], 'עברית Ελληνικά')
        b.save(0)
        self.assertTrue(b.saving)
        self.assertEqual(saved, [])
        self.until(lambda: not b.busy)
        self.assertEqual(saved, [True])

    def test_cancel_reaps_search_and_ignores_old_results(self):
        b = self.launch("time.sleep(2)\nprint(json.dumps({'type':'results','items':[]}),flush=True)\n")
        b.search('test')
        old = b._process
        old.waitForStarted(1000)
        b.cancel()
        self.assertEqual(old.state(), QProcess.NotRunning)
        b.open('podcast')
        self.app.processEvents()
        self.assertFalse(b.busy)
        self.assertEqual(b.source, 'podcast')
        self.assertEqual(b.items, [])

    def test_invalid_response_and_retry(self):
        b = self.launch("print('broken',flush=True)\n")
        b.search('test')
        self.until(lambda: not b.busy)
        self.assertIn('Invalid', b.message)
        b.search('retry')
        self.until(lambda: not b.busy)

    def test_timeout_reaps_process(self):
        b = self.launch('time.sleep(10)\n')
        b.search('test')
        old = b._process
        old.waitForStarted(1000)
        b._timeout()
        self.assertEqual(old.state(), QProcess.NotRunning)
        self.assertIn('timed out', b.message)

    def test_catalogue_refresh_preserves_playback_and_volume(self):
        path = Path(self.tmp.name) / 'playback.py'
        path.write_text('''import sys,json
print(json.dumps({'type':'ready','protocol':1,'stations':[],'volume':.1}),flush=True)
for line in sys.stdin:
 r=json.loads(line)
 if r['command']=='quit': break
 if r['command']=='reload':
  print(json.dumps({'type':'catalogue','protocol':1,'stations':[{'id':'internet/new','name':'New','source':'internet'}]}),flush=True)
''')
        p = PlaybackBridge(self.tmp.name, process_command=[sys.executable, str(path)])
        # Test helper's error display expects DiscoveryBridge; retain a harmless instance.
        self.bridge = DiscoveryBridge(self.tmp.name)
        try:
            self.until(lambda: p.state == 'idle')
            p._state = 'playing'
            p._volume = .35
            p._requested_volume = .5
            p.refreshCatalogue()
            self.until(lambda: len(p.stations) == 1)
            self.assertEqual(p.state, 'playing')
            self.assertEqual(p.volume, .35)
            self.assertEqual(p.requestedVolume, .5)
        finally:
            p.shutdown()

    def test_radio_scene_loads_with_discovery_and_keyboard(self):
        import os
        import subprocess

        root = Path(__file__).resolve().parent
        config = Path(self.tmp.name)
        (config / 'config.json').write_text('{}')
        env = os.environ.copy()
        env['QT_QPA_PLATFORM'] = 'offscreen'
        env['QT_QUICK_BACKEND'] = 'software'
        result = subprocess.run(
            [sys.executable, str(root / 'main.py'), '--platform', 'offscreen',
             '--windowed', '--radio', '--config-dir', str(config), '--timeout', '1'],
            cwd=root, env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('platform offscreen', result.stdout)
        self.assertNotIn('failed to load component', result.stderr.lower())
        self.assertNotIn('ReferenceError:', result.stderr)
        self.assertNotIn('TypeError:', result.stderr)
