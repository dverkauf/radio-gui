"""Native saved-podcast browsing/selection checks; no network or audio launched."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('php') and Path('vendor/autoload.php').is_file(), 'Install PHP and Composer dependencies first')
class PodcastBackendTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        (self.directory / 'config.json').write_text('{}')
        self.feed = hashlib.sha256(b'https://example.invalid/podcast.xml').hexdigest()

    def tearDown(self):
        self.temporary.cleanup()

    def populate(self):
        code = r'''
require 'vendor/autoload.php';
$episodes = [];
for ($i = 0; $i < 41; ++$i) {
    $episodes[] = new Radio\Podcast\Episode('guid-' . $i, 'עברית Ελληνικά ' . $i,
        'https://example.invalid/audio-' . $i . '.mp3');
}
$feed = new Radio\Podcast\Feed('https://example.invalid/podcast.xml', 'Test', $episodes);
(new Radio\Podcast\JsonSubscriptionRepository($argv[1]))->subscribe($feed, 'עושים תוכנה');
'''
        result = subprocess.run(['php', '-r', code, str(self.directory)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def exchange(self, requests):
        payload = ''.join(json.dumps(r) + '\n' for r in requests + [{'command': 'quit'}])
        result = subprocess.run(['php', 'backend/radio.php', str(self.directory)],
            input=payload, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def page_request(self, page=0, request=1):
        return {'command': 'episodes', 'feed': self.feed, 'page': page, 'request_id': request}

    def test_subscription_and_episode_pages_preserve_logical_unicode(self):
        self.populate()
        messages = self.exchange([self.page_request(), self.page_request(1, 2)])
        self.assertEqual(messages[0]['subscriptions'][0]['name'], 'עושים תוכנה')
        first, second = messages[1:]
        self.assertEqual(first['total'], 41)
        self.assertEqual(len(first['items']), 40)
        self.assertEqual(len(second['items']), 1)
        self.assertEqual(second['request_id'], 2)
        self.assertEqual(first['items'][0]['name'], 'עברית Ελληνικά 0')

    def test_full_episode_key_is_used_for_library_selection(self):
        self.populate()
        code = r'''
require 'vendor/autoload.php'; require 'backend/SavedPodcasts.php';
$saved = new SavedPodcasts($argv[1]);
$page = $saved->page($argv[2], 0);
echo json_encode($saved->selection($page['items'][0]['id']));
'''
        result = subprocess.run(['php', '-r', code, str(self.directory), self.feed], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        key = hashlib.sha256((self.feed + '\0guid-0').encode()).hexdigest()
        self.assertEqual(json.loads(result.stdout), {'source': 'podcast', 'selection': self.feed + '/' + key})

    def test_invalid_page_and_unknown_episode_are_rejected(self):
        self.populate()
        messages = self.exchange([self.page_request(-1), self.page_request(99, 2),
            {'command': 'play', 'id': 'podcast/' + self.feed + '/' + '0' * 64}])
        self.assertEqual([m['type'] for m in messages[1:]], ['request_error'] * 3)
        self.assertEqual(messages[1]['command'], 'episodes')
        self.assertEqual(messages[1]['request_id'], 1)
        self.assertFalse((self.directory / 'playback').exists())

    def test_corrupt_podcast_store_is_reported_without_replacing_it(self):
        path = self.directory / 'podcasts.json'
        path.write_text('broken snapshot')
        messages = self.exchange([])
        self.assertEqual(messages[0]['subscriptions'], [])
        self.assertIn('podcast', messages[0]['catalogue_errors'])
        self.assertEqual(path.read_text(), 'broken snapshot')

    def test_browsing_does_not_modify_snapshots_or_listening_progress(self):
        self.populate()
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        self.exchange([self.page_request()])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})
        self.assertFalse((self.directory / 'podcast-progress').exists())

    def test_transport_requests_without_session_are_rejected(self):
        messages = self.exchange([{'command': 'pause'}, {'command': 'resume'},
            {'command': 'seek', 'seconds': 15, 'request_id': 1}])
        self.assertEqual([m['type'] for m in messages[1:]], ['request_error'] * 3)
        self.assertFalse((self.directory / 'podcast-progress').exists())


if __name__ == '__main__':
    unittest.main()
