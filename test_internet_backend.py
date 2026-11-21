"""Real PHP/library protocol checks with temporary data; no playback launched."""
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('php') and Path('vendor/autoload.php').is_file(), 'Install PHP and Composer dependencies first')
class BackendTest(unittest.TestCase):
    def run_peer(self, commands):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'config.json').write_text('{}')
            process = subprocess.run(['php', 'backend/internet.php', directory],
                input=commands, capture_output=True, text=True, timeout=8)
            return process, [json.loads(line) for line in process.stdout.splitlines()]

    def test_ready_and_quit_do_not_create_data(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'config.json').write_text('{}')
            result = subprocess.run(['php', 'backend/internet.php', directory],
                input='{"command":"quit"}\n', capture_output=True, text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['stations'], [])
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ['config.json'])

    def test_eof_exits_cleanly(self):
        result, _ = self.run_peer('')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_station_is_rejected_without_audio(self):
        result, messages = self.run_peer('{"command":"play","id":"missing"}\n{"command":"quit"}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(messages[-1]['type'], 'request_error')

    def test_malformed_protocol_fails(self):
        result, messages = self.run_peer('not json\n')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(messages[-1]['type'], 'error')

    def test_oversized_input_fails(self):
        result, messages = self.run_peer('x' * 70000)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(messages[-1]['type'], 'error')

    def test_sigterm_exits_without_data_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'config.json').write_text('{}')
            peer = subprocess.Popen(['php', 'backend/internet.php', directory],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # A bounded communicate test above covers startup. Read readiness before signal.
                import select
                self.assertTrue(select.select([peer.stdout], [], [], 5)[0])
                self.assertEqual(json.loads(peer.stdout.readline())['type'], 'ready')
                peer.send_signal(signal.SIGTERM)
                _, error = peer.communicate(timeout=8)
                self.assertEqual(peer.returncode, 0, error)
            finally:
                if peer.poll() is None:
                    peer.kill(); peer.communicate()


if __name__ == '__main__':
    unittest.main()
