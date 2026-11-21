"""Order preference integrity plus catalogue/reload integration; no audio or receiver."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class PresetOrderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.rows = [dict(id='a', name='Same'), dict(id='b', name='Same'), dict(id='c', name='עברית Ελληνικά')]

    def tearDown(self):
        self.tmp.cleanup()

    def php(self, code):
        result = subprocess.run(['php', '-r', "require $argv[1].'/backend/PresetOrder.php'; " + code,
                                 str(ROOT), str(self.directory)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def apply(self, source='fm'):
        return self.php(
            '$rows=json_decode(\'' + json.dumps(self.rows) + '\',true);echo json_encode((new PresetOrder($argv[2]))->apply(\'' + source + '\',$rows));')

    def test_no_preference_is_readonly(self):
        self.assertEqual(self.apply(), self.rows)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_move_uses_identity_and_preserves_other_source_order(self):
        path = self.directory / 'gui-preset-order.json'
        path.write_text('{"internet":["c","a"]}')
        result = self.php('''$o=new PresetOrder($argv[2]);$r=[['id'=>'a'],['id'=>'b'],['id'=>'c']];
$r=$o->move('fm',$r,'b',-1,PresetOrder::revision($r));echo json_encode($r);''')
        self.assertEqual([i['id'] for i in result], ['b','a','c'])
        self.assertEqual(json.loads(path.read_text())['internet'], ['c','a'])
        self.assertEqual([i['id'] for i in self.apply()], ['b','a','c'])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_new_entries_append_and_deleted_entries_are_ignored(self):
        (self.directory / 'gui-preset-order.json').write_text('{"fm":["c","deleted","a"]}')
        self.assertEqual([i['id'] for i in self.apply()], ['c','a','b'])

    def test_each_source_has_an_independent_order(self):
        path = self.directory / 'gui-preset-order.json'
        path.write_text(json.dumps({'fm':['b'], 'dab':['c'], 'internet':['c','b'], 'podcast':['b','c']}))
        expected = {'fm':['b','a','c'], 'dab':['c','a','b'], 'internet':['c','b','a'], 'podcast':['b','c','a']}
        for source, ids in expected.items():
            self.assertEqual([i['id'] for i in self.apply(source)], ids)

    def test_stale_and_invalid_moves_do_not_replace_file(self):
        path = self.directory / 'gui-preset-order.json'
        original = '{"fm":["b","a"]}'
        path.write_text(original)
        for key, direction, revision in [('a', -1, 'stale'), ('missing', 1, None), ('b', -1, None), ('a', 2, None)]:
            result = self.php('''$o=new PresetOrder($argv[2]);$r=[['id'=>'a'],['id'=>'b']];$r=$o->apply('fm',$r);
try {$o->move('fm',$r,''' + json.dumps(key) + ',' + str(direction) + ',' + (json.dumps(revision) if revision else 'PresetOrder::revision($r)') + ''');echo json_encode(false);}
catch(Throwable $e){echo json_encode(true);}''')
            self.assertTrue(result)
            self.assertEqual(path.read_text(), original)

    def test_corrupt_order_falls_back_but_cannot_be_overwritten(self):
        path = self.directory / 'gui-preset-order.json'
        for original in ('broken', '[]', '{"fm":["a","a"]}'):
            path.write_text(original)
            self.assertEqual(self.apply(), self.rows)
            result = self.php('''try {(new PresetOrder($argv[2]))->move('fm',[['id'=>'a'],['id'=>'b']],'b',-1,'x');echo 'false';}
catch(Throwable $e){echo 'true';}''')
            self.assertTrue(result)
            self.assertEqual(path.read_text(), original)

    def test_reordering_leaves_catalogues_and_progress_untouched(self):
        names = ['stations.json','dab-stations.json','internet-stations.json','podcasts.json','config.json']
        for name in names: (self.directory / name).write_bytes(b'unchanged')
        self.php('''$r=[['id'=>'a'],['id'=>'b']];(new PresetOrder($argv[2]))->move('fm',$r,'b',-1,PresetOrder::revision($r));echo 'true';''')
        for name in names: self.assertEqual((self.directory / name).read_bytes(), b'unchanged')

    def test_worker_and_radio_reload_use_same_order_without_session(self):
        seed = subprocess.run(['php','-r',"require $argv[1].'/vendor/autoload.php';$c=new Radio\\Fm\\StationCache($argv[2]);$c->remember(96200000,'0xD382','One');$c->remember(90900000,'0xD381','Two');",str(ROOT),str(self.directory)],capture_output=True,text=True,timeout=5)
        self.assertEqual(seed.returncode,0,seed.stderr)
        (self.directory / 'config.json').write_text('{}')
        def request(data):
            p = subprocess.run(['php',str(ROOT/'backend/presets.php'),str(self.directory)],input=json.dumps(data),capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            return json.loads(p.stdout)
        before = request(dict(source='fm',action='list'))
        key = before['items'][1]['key']
        moved = request(dict(source='fm',action='move',key=key,direction=-1,revision=before['revision']))
        self.assertEqual(moved['type'],'ordered')
        self.assertEqual(request(dict(source='fm',action='list'))['items'][0]['key'],key)
        p = subprocess.run(['php',str(ROOT/'backend/radio.php'),str(self.directory)],input='{"command":"reload"}\n{"command":"quit"}\n',text=True,capture_output=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        messages = [json.loads(line) for line in p.stdout.splitlines()]
        for kind in ('ready','catalogue'):
            msg = next(m for m in messages if m['type']==kind)
            self.assertEqual(msg['stations'][0]['id'],key)
