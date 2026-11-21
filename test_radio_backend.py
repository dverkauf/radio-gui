"""Read-only saved-station checks and a hardware-free FM failure recovery."""
import json
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(shutil.which('php') and Path('vendor/autoload.php').is_file(), 'Install PHP and Composer dependencies first')
class RadioBackendTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.write('config.json', {})

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, data):
        (self.directory / name).write_text(json.dumps(data))

    def fm(self):
        self.write('stations.json', {'schema_version': 1, 'stations': {
            str(hz): {'frequency_hz': hz, 'pi': '0XD382', 'name': 'Same name', 'verified_at': '2026-11-21T08:00:00Z'}
            for hz in (96200000, 100000000)}})

    def dab(self):
        self.write('dab-stations.json', {'schema_version': 1, 'blocks': {
            channel: {'ensemble': {'ensemble_name': 'Test', 'services': [
                {'name': 'Same name', 'channel': channel, 'service_id': '0xD382',
                 'station_id': 'dab-' + channel.lower() + '-e1-100-d382',
                 'audio_components': [{'audio_type': 'DAB+'}]},
                {'name': 'Data only', 'channel': channel, 'service_id': '0xE001',
                 'station_id': 'data-' + channel, 'audio_components': []}]}}
            for channel in ('7A', '5C')}})

    def snapshot(self):
        result = subprocess.run(['php', 'backend/radio.php', str(self.directory)],
            input='{"command":"quit"}\n', text=True, capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_fm_names_on_different_frequencies_have_distinct_ids(self):
        self.fm()
        rows = self.snapshot()['stations']
        self.assertEqual([s['id'] for s in rows], ['fm/96200000', 'fm/100000000'])
        self.assertEqual({s['source'] for s in rows}, {'fm'})
        # Check the exact library selection used by the bridge, without tuning.
        code = "require 'vendor/autoload.php'; require 'backend/SavedRadioStations.php'; echo json_encode(SavedRadioStations::load($argv[1]));"
        result = subprocess.run(['php', '-r', code, str(self.directory)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['stations'][0]['selection'], '96.200000')

    def test_dab_duplicate_names_use_service_ids_and_exclude_data(self):
        self.dab()
        rows = self.snapshot()['stations']
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({s['id'] for s in rows}), 2)
        self.assertTrue(all(s['source'] == 'dab' and s['name'] == 'Same name' for s in rows))

    def test_broken_fm_does_not_hide_valid_dab(self):
        self.dab()
        (self.directory / 'stations.json').write_text('invalid JSON')
        ready = self.snapshot()
        self.assertIn('fm', ready['catalogue_errors'])
        self.assertEqual(len(ready['stations']), 2)

    def test_catalogue_bound_and_startup_does_not_modify_saved_data(self):
        self.dab()
        (self.directory / 'stations.json').write_text('x' * (2097152 + 1))
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        ready = self.snapshot()
        self.assertIn('2 MiB', ready['catalogue_errors']['fm'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_invalid_fm_options_recover_without_receiver_or_audio(self):
        self.fm()
        self.write('config.json', {'playback': {'gain_db': 99}})
        peer = subprocess.Popen(['php', 'backend/radio.php', str(self.directory)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        buffered = b''
        selector = selectors.DefaultSelector()
        selector.register(peer.stdout, selectors.EVENT_READ)
        def receive():
            nonlocal buffered
            deadline = time.monotonic() + 5
            while b'\n' not in buffered:
                self.assertTrue(selector.select(max(0, deadline - time.monotonic())), 'Timed out waiting for backend')
                import os
                data = os.read(peer.stdout.fileno(), 65536)
                self.assertTrue(data, 'Backend exited unexpectedly')
                buffered += data
            line, buffered = buffered.split(b'\n', 1)
            return json.loads(line)
        def send(command):
            peer.stdin.write((json.dumps(command) + '\n').encode()); peer.stdin.flush()
        try:
            self.assertEqual(receive()['type'], 'ready')
            send({'command': 'play', 'id': 'fm/96200000'})
            messages = [receive(), receive()]
            self.assertEqual(messages[0]['type'], 'session_error')
            self.assertEqual(messages[1]['state'], 'stopped')
            # Process remains usable; repeat the request instead of a dead connection.
            send({'command': 'play', 'id': 'fm/100000000'})
            self.assertEqual(receive()['type'], 'session_error')
            self.assertEqual(receive()['state'], 'stopped')
            send({'command': 'quit'})
            _, error = peer.communicate(timeout=8)
            self.assertEqual(peer.returncode, 0, error.decode())
            self.assertFalse((self.directory / 'receiver.lock').exists())
            self.assertFalse((self.directory / 'playback').exists())
        finally:
            selector.close()
            if peer.poll() is None:
                peer.kill(); peer.communicate()


if __name__ == '__main__':
    unittest.main()
