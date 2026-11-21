"""Cross-source selection behavior using an owned fake protocol peer."""
import json
import unittest
import test_internet_bridge as helpers


class RadioBridgeTest(unittest.TestCase):
    setUpClass = classmethod(helpers.BridgeTest.setUpClass.__func__)
    setUp = helpers.BridgeTest.setUp
    tearDown = helpers.BridgeTest.tearDown
    launch = helpers.BridgeTest.launch
    until = helpers.BridgeTest.until

    def radio_peer(self):
        return self.launch('''
rows=[{'id':s+'/one','name':'Shared name','source':s} for s in ['fm','dab','internet']]
print(json.dumps({'type':'ready','protocol':1,'stations':rows,'catalogue_errors':{},'volume':.1}),flush=True)
active=None
for line in sys.stdin:
    r=json.loads(line)
    if r['command']=='quit': break
    if r['command']=='play':
        if active is not None: raise RuntimeError('Overlapping sources')
        active=r['id']
        print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
        print(json.dumps({'type':'metadata','kind':'broadcast_text','text':active}),flush=True)
    if r['command']=='stop':
        time.sleep(.06)
        active=None
        print(json.dumps({'type':'state','state':'stopped','volume_control':False}),flush=True)
''')

    def test_tabs_filter_without_stopping_current_source(self):
        bridge = self.radio_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.setSource('fm')
        self.assertEqual(bridge.stations[0]['id'], 'fm/one')
        bridge.play('fm/one')
        self.until(lambda: bridge.broadcastText == 'fm/one')
        bridge.setSource('dab')
        self.assertEqual(bridge.stations[0]['id'], 'dab/one')
        self.assertEqual(bridge.state, 'playing')
        self.assertEqual(bridge.activeSource, 'fm')
        bridge.setSource('invalid')
        self.assertEqual(bridge.source, 'dab')

    def test_rapid_cross_source_switch_uses_latest_choice(self):
        bridge = self.radio_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.play('fm/one')
        self.until(lambda: bridge.broadcastText == 'fm/one')
        bridge.setSource('dab'); bridge.play('dab/one')
        bridge.setSource('internet'); bridge.play('internet/one')
        # Browsing a tab must not discard or reinterpret the pending ID.
        bridge.setSource('fm')
        self.until(lambda: bridge.broadcastText == 'internet/one' and bridge.state == 'playing')
        self.assertEqual(bridge.activeSource, 'internet')
        self.assertEqual(bridge.source, 'fm')

    def test_recoverable_source_error_allows_next_tap(self):
        bridge = self.launch('''
print(json.dumps({'type':'ready','protocol':1,'stations':[{'id':'fm/a','source':'fm','name':'A'},{'id':'internet/b','source':'internet','name':'B'}],'volume':.1}),flush=True)
for line in sys.stdin:
    r=json.loads(line)
    if r['command']=='quit': break
    if r['command']=='play' and r['id']=='fm/a':
        print(json.dumps({'type':'session_error','message':'Receiver busy'}),flush=True)
        print(json.dumps({'type':'state','state':'stopped','volume_control':False}),flush=True)
    elif r['command']=='play': print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
''')
        self.until(lambda: bridge.state == 'idle')
        bridge.play('fm/a')
        self.until(lambda: bridge.state == 'stopped')
        self.assertEqual(bridge.error, 'Receiver busy')
        bridge.play('internet/b')
        self.until(lambda: bridge.state == 'playing')
        self.assertEqual(bridge.error, '')
        self.assertEqual(bridge.activeSource, 'internet')

    def test_invalid_source_metadata_is_rejected(self):
        bridge = self.launch('''
print(json.dumps({'type':'ready','protocol':1,'stations':[{'id':'one','name':'One','source':'unknown'}],'volume':.1}),flush=True)
for line in sys.stdin: pass
''')
        self.until(lambda: bridge.state == 'failed')
        self.assertIn('Invalid response', bridge.error)


if __name__ == '__main__':
    unittest.main()
