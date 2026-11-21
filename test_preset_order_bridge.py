"""Ordering waits for a worker acknowledgement and preserves playback."""
from pathlib import Path
import sys
import unittest
from preset_bridge import PresetBridge
from test_discovery_bridge import DiscoveryBridgeTest


class PresetOrderBridgeTest(unittest.TestCase):
    setUpClass = classmethod(DiscoveryBridgeTest.setUpClass.__func__)
    setUp = DiscoveryBridgeTest.setUp
    tearDown = DiscoveryBridgeTest.tearDown
    until = DiscoveryBridgeTest.until

    def launch(self, script):
        path = Path(self.tmp.name) / 'peer.py'
        path.write_text('import json,sys,time\nr=json.load(sys.stdin)\n' + script)
        class Playing:
            state = 'playing'
            def stop(self): raise AssertionError('Ordering must not stop playback')
        self.bridge = PresetBridge(self.tmp.name, Playing(), process_command=[sys.executable, str(path)])
        return self.bridge

    def test_move_waits_for_acknowledgement_while_playing(self):
        bridge = self.launch('''
items=[{'key':'a','name':'Same','detail':'FM'},{'key':'b','name':'Same','detail':'FM'}]
if r['action']=='move':
 assert r['key']=='b' and r['direction']==-1 and r['revision']=='before'
 time.sleep(.04);items.reverse()
print(json.dumps({'type':'ordered' if r['action']=='move' else 'presets','items':items,'revision':'after' if r['action']=='move' else 'before'}))
''')
        saved = []
        bridge.saved.connect(lambda: saved.append(True))
        bridge.open('fm');self.until(lambda: not bridge.busy)
        bridge.move(1,-1)
        self.assertTrue(bridge.saving)
        self.assertEqual(bridge.items[0]['key'],'a')
        self.assertEqual(saved,[])
        self.until(lambda: not bridge.busy)
        self.assertEqual(bridge.items[0]['key'],'b')
        self.assertEqual(saved,[True])

    def test_failed_move_keeps_display_order(self):
        bridge = self.launch('''
if r['action']=='move':
 print(json.dumps({'type':'error','message':'Presets changed elsewhere'}));sys.exit(1)
print(json.dumps({'type':'presets','items':[{'key':'a','name':'One','detail':''},{'key':'b','name':'Two','detail':''}],'revision':'before'}))
''')
        bridge.open('internet');self.until(lambda: not bridge.busy)
        bridge.move(0,1);self.until(lambda: not bridge.busy)
        self.assertEqual([i['key'] for i in bridge.items],['a','b'])
        self.assertIn('changed elsewhere',bridge.message)

    def test_end_buttons_cannot_send_invalid_move(self):
        bridge = self.launch("raise AssertionError('No request expected')")
        bridge._items = [dict(key='a',name='One',detail='')]
        bridge.move(0,-1);bridge.move(0,1);bridge.move(0,2)
        self.assertFalse(bridge.busy)


del DiscoveryBridgeTest
