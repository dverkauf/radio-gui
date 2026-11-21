"""Worker acknowledgement and repeated jobs use one owned QProcess."""
from pathlib import Path
import sys
import unittest
from location_bridge import LocationBridge
from test_discovery_bridge import DiscoveryBridgeTest


class LocationBridgeTest(unittest.TestCase):
    setUpClass = classmethod(DiscoveryBridgeTest.setUpClass.__func__)
    setUp = DiscoveryBridgeTest.setUp
    tearDown = DiscoveryBridgeTest.tearDown
    until = DiscoveryBridgeTest.until

    def launch(self, script):
        path = Path(self.tmp.name) / 'peer.py'
        path.write_text('import json,sys,time\nr=json.load(sys.stdin)\n' + script)
        self.bridge = LocationBridge(self.tmp.name, process_command=[sys.executable, str(path)])
        return self.bridge

    def test_location_acknowledgement_and_repeated_jobs(self):
        bridge = self.launch('''
time.sleep(.03)
print(json.dumps({'type':'locations','items':[{'key':'Κρήτη','name':'Κρήτη','channels':['7A'],'detail':'7A'}], 'selected':'Κρήτη','revision':'revision','message':'Ready'}))
''')
        saved = []
        bridge.saved.connect(lambda: saved.append(True))
        bridge.open()
        self.until(lambda: not bridge.busy)
        self.assertEqual(saved, [])
        self.assertEqual(bridge.selected, 'Κρήτη')
        process = bridge._process
        bridge.savePlan('Κρήτη', ['7A'], 'Κρήτη')
        self.assertTrue(bridge.saving)
        self.assertEqual(saved, [])
        self.until(lambda: not bridge.busy)
        self.assertEqual(saved, [True])
        self.assertIs(bridge._process, process)

    def test_failed_location_write_has_no_saved_signal(self):
        bridge = self.launch("print(json.dumps({'type':'error','message':'Settings changed elsewhere'}));sys.exit(1)")
        saved = []
        bridge.saved.connect(lambda: saved.append(True))
        bridge.deletePlan('Hannover')
        self.until(lambda: not bridge.busy)
        self.assertEqual(saved, [])
        self.assertIn('changed elsewhere', bridge.message)

    def test_invalid_location_response_is_recoverable(self):
        bridge = self.launch("print('[]')")
        bridge.open()
        self.until(lambda: not bridge.busy)
        self.assertIn("Invalid location response", bridge.message)


del DiscoveryBridgeTest
