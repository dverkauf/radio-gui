"""Native library composition with fake tools, temporary storage and no SDR."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent


class ScanBackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = {'dab': {'locations': {'Hannover': ['7A','7A','5C'], 'Palekastro': ['12B']}},
                       'scan': {'integration_seconds': 1}}
        self.write_config()

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self):
        (self.root / 'config.json').write_text(json.dumps(self.config))

    def job(self, request):
        p = subprocess.run(['php', str(ROOT / 'backend/scan.php'), str(self.root)],
                           input=json.dumps(request), text=True, capture_output=True, timeout=10)
        messages = [json.loads(line) for line in p.stdout.splitlines()]
        self.assertTrue(messages, p.stderr)
        return p, messages[-1]

    def helper(self, code):
        script = "require $argv[1].'/vendor/autoload.php'; require $argv[1].'/backend/ScanOperations.php'; " + code
        p = subprocess.run(['php', '-r', script, str(ROOT), str(self.root)], capture_output=True, text=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_locations_use_configured_blocks_and_unknown_full_plan(self):
        p, result = self.job({'source':'dab','action':'settings'})
        self.assertEqual(p.returncode, 0, result)
        self.assertEqual(result['location'], '__full_band__')
        self.assertEqual(result['locations'][0]['channels'], ['7A','5C'])
        self.assertEqual(len(result['locations'][-1]['channels']), 38)
        self.assertEqual(sorted(x.name for x in self.root.iterdir()), ['config.json'])

    def test_invalid_location_does_not_access_receiver_or_save(self):
        p, result = self.job({'source':'dab','action':'scan','location':'Nowhere'})
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(result['type'], 'error')
        self.assertEqual(sorted(x.name for x in self.root.iterdir()), ['config.json'])

    def test_invalid_preview_key_cannot_read_arbitrary_file(self):
        p, result = self.job({'source':'dab','action':'save','key':'../../config.json'})
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(result['type'], 'error')
        self.assertFalse((self.root / 'dab-stations.json').exists())

    def test_fm_spectrum_preview_never_creates_presets(self):
        tool = self.root / 'fake-rtl-power'
        tool.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_text("2026-11-20,12:00:00,96000000,96200000,100000,2,-10,-20\\n")\n')
        tool.chmod(0o700)
        self.config['tools'] = {'rtl_power':str(tool)}
        self.write_config()
        p, result = self.job({'source':'fm','action':'scan'})
        self.assertEqual(p.returncode, 0, result)
        self.assertEqual(result['type'], 'results')
        self.assertTrue(result['items'])
        self.assertIn('MHz', result['items'][0]['name'])
        self.assertFalse((self.root / 'stations.json').exists())

    def test_dab_preview_requires_explicit_block_save(self):
        items = self.helper("$e=(new Radio\\Dab\\EnsembleParser())->parse($argv[1].'/tests/fixtures/gui-welle-7A.json','7A'); echo json_encode(ScanOperations::preview($argv[2], 'dab', [$e]));")
        self.assertFalse((self.root / 'dab-stations.json').exists())
        p, result = self.job({'source':'dab','action':'save','key':items[0]['key']})
        self.assertEqual(p.returncode, 0, result)
        document = json.loads((self.root / 'dab-stations.json').read_text())
        self.assertEqual(len(document['blocks']['7A']['ensemble']['services']), 8)

    def test_remembered_location_survives_failed_block_and_settings_reload(self):
        tool = self.root / 'fake-welle'
        tool.write_text('#!/bin/sh\nexit 7\n')
        tool.chmod(0o700)
        self.config['tools'] = {'welle_cli':str(tool)}
        self.write_config()
        p, result = self.job({'source':'dab','action':'scan','location':'Palekastro'})
        self.assertEqual(p.returncode, 0, result)
        self.assertEqual(result['items'], [])
        self.assertTrue(result['warning'])
        _, settings = self.job({'source':'dab','action':'settings'})
        self.assertEqual(settings['location'], 'Palekastro')
        self.assertFalse((self.root / 'dab-stations.json').exists())

    def test_fm_save_requires_prior_identification(self):
        items = self.helper("echo json_encode(ScanOperations::preview($argv[2], 'fm', [['tune_hz'=>96200000,'power'=>-20]]));")
        self.assertFalse(items[0]['can_save'])
        p, result = self.job({'source':'fm','action':'save','key':items[0]['key']})
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.root / 'stations.json').exists())

    def test_identification_is_preview_only_until_explicit_save(self):
        items = self.helper("$i=ScanOperations::preview($argv[2], 'fm', [['tune_hz'=>96200000,'power'=>-20]]); echo json_encode([ScanOperations::recordIdentification($argv[2],$i[0]['key'],['station_identity'=>['pi'=>'0xD382','name'=>'Test Radio'],'radiotext_counts'=>['Example text'=>2]])]);")
        self.assertTrue(items[0]['can_save'])
        self.assertIn('Test Radio',items[0]['name'])
        self.assertIn('Example text',items[0]['detail'])
        self.assertFalse((self.root / 'stations.json').exists())
        p, result = self.job({'source':'fm','action':'save','key':items[0]['key']})
        self.assertEqual(p.returncode,0,result)
        self.assertTrue((self.root / 'stations.json').exists())

    def test_fm_cancellation_reaps_tool_and_releases_receiver(self):
        tool = self.root / 'fake-rtl-power'
        pidfile = self.root / 'tool.pid'
        tool.write_text('#!' + sys.executable + '\nimport os,signal,time\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nPath(' + repr(str(pidfile)) + ').write_text(str(os.getpid()))\nwhile True: time.sleep(.01)\n')
        tool.chmod(0o700)
        self.config['tools'] = {'rtl_power':str(tool)}
        self.write_config()
        p = subprocess.Popen(['php', str(ROOT / 'backend/scan.php'), str(self.root)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        pid = None
        try:
            p.stdin.write(json.dumps({'source':'fm','action':'scan'})); p.stdin.close(); p.stdin = None
            deadline = time.monotonic() + 4
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(pidfile.exists())
            pid = int(pidfile.read_text())
            p.terminate()
            stdout, stderr = p.communicate(timeout=8)
            self.assertNotEqual(p.returncode, 0, stdout + stderr)
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)
            with (self.root / 'receiver.lock').open('r+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertFalse((self.root / 'stations.json').exists())
        finally:
            if p.poll() is None:
                p.kill(); p.wait()
            if pid:
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
