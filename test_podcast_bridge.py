"""Native Qt protocol tests with fake peers; no network, audio or saved-data writes."""
import unittest
import test_internet_bridge as helpers


class PodcastBridgeTest(unittest.TestCase):
    setUpClass = classmethod(helpers.BridgeTest.setUpClass.__func__)
    setUp = helpers.BridgeTest.setUp
    tearDown = helpers.BridgeTest.tearDown
    launch = helpers.BridgeTest.launch
    until = helpers.BridgeTest.until

    def podcast_peer(self):
        return self.launch('''
subs=[{'id':'a','name':'עושים תוכנה'},{'id':'b','name':'Ελληνικά'}]
print(json.dumps({'type':'ready','protocol':1,'stations':[{'id':'radio','name':'Radio','source':'fm'}],'subscriptions':subs,'volume':.1}),flush=True)
active=None
for line in sys.stdin:
    r=json.loads(line); command=r['command']
    if command=='quit': break
    if command=='episodes':
        time.sleep(.03)
        start=r['page']*40; count=min(40,41-start)
        items=[{'id':'podcast/'+r['feed']+'/key'+str(i),'name':'פרק '+str(i),'source':'podcast'} for i in range(start,start+count)]
        print(json.dumps({'type':'episodes','request_id':r['request_id'],'feed':r['feed'],'page':r['page'],'page_size':40,'total':41,'items':items}),flush=True)
    if command=='play':
        if active is not None: raise RuntimeError('Overlapping sessions')
        active=r['id']
        print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
        print(json.dumps({'type':'metadata','kind':'broadcast_text','text':active}),flush=True)
        print(json.dumps({'type':'timeline','can_pause':active.startswith('podcast/'),'can_seek':active.startswith('podcast/'),'position':30 if active.startswith('podcast/') else None,'duration':None,'seek_request':0}),flush=True)
    if command=='stop':
        time.sleep(.06); active=None
        print(json.dumps({'type':'state','state':'stopped','volume_control':False}),flush=True)
    if command in ('pause','resume'):
        print(json.dumps({'type':'state','state':'paused' if command=='pause' else 'playing','volume_control':True}),flush=True)
    if command=='seek':
        print(json.dumps({'type':'timeline','can_pause':True,'can_seek':True,'position':20,'duration':None,'seek_request':0}),flush=True)
        time.sleep(.08)
        print(json.dumps({'type':'timeline','can_pause':True,'can_seek':True,'position':r['seconds'],'duration':None,'seek_request':r['request_id']}),flush=True)
''')

    def open_episode(self):
        bridge = self.podcast_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.openPodcast('a')
        self.until(lambda: len(bridge.episodes) == 40)
        return bridge

    def test_paging_ignores_stale_feed_response_and_preserves_unicode(self):
        bridge = self.podcast_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.openPodcast('a'); bridge.openPodcast('b')
        self.until(lambda: not bridge.episodesLoading)
        self.assertEqual(bridge.episodeFeedName, 'Ελληνικά')
        self.assertTrue(all(e['id'].startswith('podcast/b/') for e in bridge.episodes))
        bridge.episodePageTo(1)
        self.until(lambda: not bridge.episodesLoading)
        self.assertEqual(len(bridge.episodes), 1)
        self.assertEqual(bridge.episodePage, 1)
        self.assertEqual(bridge.episodes[0]['name'], 'פרק 40')
        bridge.backToSubscriptions()
        self.assertEqual(bridge.episodeFeed, '')
        self.assertEqual(bridge.episodes, [])

    def test_pending_episode_survives_browser_navigation(self):
        bridge = self.open_episode()
        episode = bridge.episodes[0]
        bridge.play('radio')
        self.until(lambda: bridge.state == 'playing')
        bridge.play(episode['id'])
        bridge.backToSubscriptions()
        bridge.setSource('internet')
        self.until(lambda: bridge.broadcastText == episode['id'] and bridge.state == 'playing')
        self.assertEqual(bridge.station, episode['name'])
        self.assertEqual(bridge.activeSource, 'podcast')

    def test_pause_resume_waits_for_reported_state(self):
        bridge = self.open_episode()
        bridge.play(bridge.episodes[0]['id'])
        self.until(lambda: bridge.canPause)
        bridge.togglePause()
        self.assertTrue(bridge.pausePending)
        self.until(lambda: bridge.state == 'paused' and not bridge.pausePending)
        bridge.togglePause()
        self.until(lambda: bridge.state == 'playing' and not bridge.pausePending)
        self.assertTrue(bridge.volumeControl)

    def test_rapid_seeks_keep_latest_target_and_do_not_reset_browser(self):
        bridge = self.open_episode()
        bridge.play(bridge.episodes[0]['id'])
        self.until(lambda: bridge.position == 30)
        catalogue_events=[]
        episode_events=[]
        observations=[]
        bridge.changed.connect(lambda: observations.append((bridge.position, bridge.seekTarget)))
        bridge.catalogueChanged.connect(lambda: catalogue_events.append(True))
        bridge.episodesChanged.connect(lambda: episode_events.append(True))
        bridge.seekBy(15); bridge.seekBy(15)
        self.assertEqual(bridge.seekTarget, 60)
        self.until(lambda: bridge.position == 60 and bridge.seekTarget < 0)
        # Qt may consume 45, then the next request's stale 20, in one callback.
        # Observe every notification instead of waiting on a transient value.
        self.assertIn((45.0, 60.0), observations)
        self.assertIn((20.0, 60.0), observations)
        self.assertEqual(catalogue_events, [])
        self.assertEqual(episode_events, [])
        bridge.seekBy(-1000)
        self.assertEqual(bridge.seekTarget, 0)

    def test_live_radio_does_not_send_podcast_controls(self):
        bridge = self.podcast_peer()
        self.until(lambda: bridge.state == 'idle')
        bridge.play('radio')
        self.until(lambda: bridge.broadcastText == 'radio')
        sent=[]
        original=bridge._send
        bridge._send=sent.append
        bridge.togglePause(); bridge.seekBy(15)
        self.assertEqual(sent, [])
        self.assertFalse(bridge.canPause)
        self.assertFalse(bridge.canSeek)
        bridge._send=original

    def test_page_error_keeps_playback_and_allows_retry(self):
        bridge = self.launch('''
print(json.dumps({'type':'ready','protocol':1,'stations':[{'id':'radio','name':'Radio'}],'subscriptions':[{'id':'a','name':'Saved'}],'volume':.1}),flush=True)
for line in sys.stdin:
    r=json.loads(line)
    if r['command']=='quit': break
    if r['command']=='play': print(json.dumps({'type':'state','state':'playing','volume_control':True}),flush=True)
    if r['command']=='episodes': print(json.dumps({'type':'request_error','command':'episodes','request_id':r['request_id'],'message':'No such page'}),flush=True)
''')
        self.until(lambda: bridge.state == 'idle')
        bridge.play('radio')
        self.until(lambda: bridge.state == 'playing')
        bridge.openPodcast('a')
        self.until(lambda: not bridge.episodesLoading)
        self.assertEqual(bridge.episodeError, 'No such page')
        self.assertEqual(bridge.state, 'playing')
        self.assertEqual(bridge.error, '')


if __name__ == '__main__':
    unittest.main()
