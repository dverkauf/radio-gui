"""Offline PHP composition checks using Symfony's mock HTTP transport."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class DiscoveryBackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        (self.directory / 'config.json').write_text(json.dumps({'internet': {'directory_servers': ['https://directory.example.org']}}))

    def tearDown(self):
        self.tmp.cleanup()

    def job(self, request, body, headers=None):
        script = r'''
require $argv[1] . '/vendor/autoload.php';
require $argv[1] . '/backend/DiscoveryOperations.php';
$data = json_decode(stream_get_contents(STDIN), true, 32, JSON_THROW_ON_ERROR);
$http = new Symfony\Component\HttpClient\MockHttpClient(
    new Symfony\Component\HttpClient\Response\MockResponse($data['body'], ['http_code'=>200,
        'response_headers'=>$data['headers']])
);
try { echo json_encode(runDiscoveryJob($argv[2], $data['request'], $http), JSON_THROW_ON_ERROR); }
catch (Throwable $e) { echo json_encode(['type'=>'error','message'=>$e->getMessage()]); }
'''
        p = subprocess.run(['php', '-r', script, str(ROOT), str(self.directory)],
                           input=json.dumps({'request': request, 'body': body, 'headers': headers or ['content-type: application/json']}),
                           text=True, capture_output=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_internet_search_preserves_unicode_and_does_not_save(self):
        result = self.job({'source': 'internet', 'action': 'search', 'query': 'Ελληνικά'}, json.dumps([{
            'stationuuid': '12345678-1234-1234-1234-123456789abc', 'name': 'עברית Ελληνικά',
            'url_resolved': 'https://example.org/live', 'countrycode': 'GR', 'codec': 'MP3', 'language': 'greek'}]))
        self.assertEqual(result['type'], 'results', result)
        self.assertEqual(result['items'][0]['name'], 'עברית Ελληνικά')
        self.assertEqual(list(self.directory.iterdir()), [self.directory / 'config.json'])

    def test_podcast_search_does_not_subscribe(self):
        result = self.job({'source': 'podcast', 'action': 'search', 'query': 'radio'}, json.dumps({'resultCount': 1, 'results': [{
            'collectionName': 'עברית Ελληνικά', 'artistName': 'Publisher', 'feedUrl': 'https://example.org/feed'}]}))
        self.assertEqual(result['type'], 'results', result)
        self.assertEqual(result['items'][0]['key'], 'https://example.org/feed')
        self.assertFalse((self.directory / 'podcasts.json').exists())

    def test_explicit_internet_save_uses_library_store(self):
        uuid = '12345678-1234-1234-1234-123456789abc'
        result = self.job({'source': 'internet', 'action': 'save', 'key': uuid}, json.dumps([{
            'stationuuid': uuid, 'name': 'Test Radio', 'url_resolved': 'https://example.org/live'}]))
        self.assertEqual(result['type'], 'saved', result)
        stores = [p for p in self.directory.glob('*.json') if p.name != 'config.json']
        self.assertEqual(len(stores), 1)
        self.assertIn('Test Radio', stores[0].read_text())

    def test_explicit_subscription_fetches_and_saves_feed(self):
        rss = '<rss version="2.0"><channel><title>Greek Radio</title><link>https://example.org/</link><description>Test</description><item><title>Episode</title><guid>one</guid><enclosure url="https://example.org/one.mp3" type="audio/mpeg" length="123"/></item></channel></rss>'
        result = self.job({'source': 'podcast', 'action': 'save', 'key': 'https://example.org/feed'},
                          rss, ['content-type: application/rss+xml'])
        self.assertEqual(result['type'], 'saved', result)
        self.assertIn('Greek Radio', (self.directory / 'podcasts.json').read_text())

    def test_invalid_query_and_source_do_not_create_data(self):
        for request in ({'source': 'fm', 'action': 'search', 'query': 'test'},
                        {'source': 'internet', 'action': 'search', 'query': ''}):
            self.assertEqual(self.job(request, '[]')['type'], 'error')
        self.assertEqual(len(list(self.directory.iterdir())), 1)

    def test_corrupt_store_is_preserved(self):
        # Obtain the store path from the same library used in production.
        result = self.job({'source': 'internet', 'action': 'save', 'key': '12345678-1234-1234-1234-123456789abc'},
                         '[{"stationuuid":"12345678-1234-1234-1234-123456789abc","name":"Test","url":"https://example.org/live"}]')
        self.assertEqual(result['type'], 'saved', result)
        store = next(p for p in self.directory.glob('*.json') if p.name != 'config.json')
        store.write_text('broken')
        result = self.job({'source': 'internet', 'action': 'save', 'key': '12345678-1234-1234-1234-123456789abc'},
                         '[{"stationuuid":"12345678-1234-1234-1234-123456789abc","name":"Test","url":"https://example.org/live"}]')
        self.assertEqual(result['type'], 'error')
        self.assertEqual(store.read_text(), 'broken')
