"""Reception config changes in disposable directories, without receiver or audio."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class ReceptionLocationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.config = self.directory / 'config.json'
        self.config.write_text('{"tools":{},"playback":{"target":"radio_mono"},"dab":{"gain":22,"locations":{"Hannover":["7A"]}}}\n')
        self.original = self.config.read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, action, **values):
        result = subprocess.run(
            ['php', str(ROOT / 'backend/locations.php'), str(self.directory)],
            input=json.dumps(dict(action=action, **values)), text=True,
            capture_output=True, timeout=5)
        response = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if response['type'] == 'locations' else 1, result.stderr)
        return response

    def change(self, action, **values):
        return self.request(action, revision=self.request('list')['revision'], **values)

    def test_list_creates_nothing(self):
        result = self.request('list')
        self.assertEqual(result['items'][0]['channels'], ['7A'])
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ['config.json'])

    def test_save_unicode_and_edit_preserve_unrelated_fields(self):
        result = self.change('save', name='Κρήτη עברית', channels=[' 7a ', '7A', '13F'])
        self.assertEqual(result['selected'], 'Κρήτη עברית')
        data = json.loads(self.config.read_text())
        self.assertEqual(data['tools'], {})
        self.assertEqual(data['dab']['gain'], 22)
        self.assertEqual(data['playback']['target'], 'radio_mono')
        self.assertEqual(data['dab']['locations']['Κρήτη עברית'], ['7A', '13F'])
        self.assertEqual((self.directory / 'config.json.before-locations').read_bytes(), self.original)
        result = self.change('save', name='Κρήτη עברית', original='Κρήτη עברית', channels=['8D'])
        self.assertEqual(result['items'][1]['channels'], ['8D'])

    def test_duplicate_and_invalid_blocks_preserve_config(self):
        for name, channels in [('hannover', ['7A']), ('Other', []), ('Other', ['99Z']), ('__full_band__', ['7A'])]:
            with self.subTest(name=name, channels=channels):
                self.assertEqual(self.change('save', name=name, channels=channels)['type'], 'error')
                self.assertEqual(self.config.read_bytes(), self.original)

    def test_stale_revision_does_not_replace_external_edit(self):
        revision = self.request('list')['revision']
        self.config.write_text('{"external":true}')
        result = self.request('save', revision=revision, name='New', channels=['7A'])
        self.assertEqual(result['type'], 'error')
        self.assertEqual(self.config.read_text(), '{"external":true}')

    def test_delete_active_plan_keeps_presets_and_selects_full_band(self):
        sentinel = self.directory / 'dab-stations.json'
        sentinel.write_bytes(b'presets must remain untouched')
        self.change('select', name='Hannover')
        result = self.change('delete', name='Hannover')
        self.assertEqual(result['selected'], '__full_band__')
        self.assertEqual(result['items'], [])
        self.assertEqual(json.loads(self.config.read_text())['dab']['locations'], {})
        self.assertEqual(sentinel.read_bytes(), b'presets must remain untouched')
        self.assertEqual(self.change('delete', name='__full_band__')['type'], 'error')

    def test_select_does_not_reformat_config(self):
        self.change('select', name='Hannover')
        self.change('select', name='__full_band__')
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.directory / 'config.json.before-locations').exists())

    def test_corrupt_settings_are_preserved(self):
        self.config.write_text('broken')
        self.assertEqual(self.request('list')['type'], 'error')
        self.assertEqual(self.config.read_text(), 'broken')

    def test_selection_change_invalidates_editor_revision(self):
        revision = self.request('list')['revision']
        self.change('select', name='Hannover')
        self.assertEqual(self.request('delete', revision=revision, name='Hannover')['type'], 'error')
        self.assertEqual(self.config.read_bytes(), self.original)
