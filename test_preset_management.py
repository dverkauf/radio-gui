"""Storage-worker deletion tests in disposable directories; no hardware/network."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent


class PresetManagementTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.directory=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def request(self,request):
        p=subprocess.run(['php',str(ROOT/'backend/presets.php'),str(self.directory)],
                         input=json.dumps(request),capture_output=True,text=True,timeout=5)
        return p,json.loads(p.stdout)
    def seed(self,code):
        p=subprocess.run(['php','-r',"require $argv[1].'/vendor/autoload.php'; "+code,str(ROOT),str(self.directory)],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
    def test_list_is_readonly_and_delete_unknown_is_rejected(self):
        p,result=self.request({'source':'internet','action':'list'})
        self.assertEqual(p.returncode,0,result);self.assertEqual(result['items'],[])
        self.assertEqual(list(self.directory.iterdir()),[])
        p,result=self.request({'source':'internet','action':'delete','key':'wrong'})
        self.assertNotEqual(p.returncode,0);self.assertEqual(list(self.directory.iterdir()),[])
    def test_fm_delete_removes_only_selected_preset(self):
        self.seed("$s=new Radio\\Fm\\StationCache($argv[2]);$s->remember(96200000,'0xD382','One');$s->remember(90900000,'0xD381','Two');")
        p,result=self.request({'source':'fm','action':'delete','key':'fm/96200000'})
        self.assertEqual(p.returncode,0,result)
        _,result=self.request({'source':'fm','action':'list'})
        self.assertEqual([i['name'] for i in result['items']],['Two'])
    def test_internet_delete_uses_shared_library_api(self):
        key='12345678-1234-1234-1234-123456789abc'
        self.seed("(new Radio\\Internet\\StationCatalogue($argv[2]))->remember(['station_uuid'=>'"+key+"','name'=>'Greek Radio','url'=>'https://example.org/live']);")
        p,result=self.request({'source':'internet','action':'delete','key':key})
        self.assertEqual(p.returncode,0,result)
        _,result=self.request({'source':'internet','action':'list'})
        self.assertEqual(result['items'],[])
    def test_corrupt_store_is_not_replaced(self):
        path=self.directory/'internet-stations.json';path.write_text('broken')
        p,result=self.request({'source':'internet','action':'list'})
        self.assertNotEqual(p.returncode,0);self.assertEqual(path.read_text(),'broken')

    def test_unsubscribe_keeps_progress_unless_explicitly_selected(self):
        for remove in (False,True):
            self.seed("$feed=(new Radio\\Podcast\\FeedParser())->parse('<rss version=\"2.0\"><channel><title>Test Podcast</title></channel></rss>','https://example.org/feed');(new Radio\\Podcast\\JsonSubscriptionRepository($argv[2]))->subscribe($feed);")
            _,result=self.request({'source':'podcast','action':'list'})
            key=result['items'][0]['key']
            progress=self.directory/'podcast-progress'/key
            progress.mkdir(parents=True,exist_ok=True)
            checkpoint=progress/('a'*64+'.json');checkpoint.write_text('explicitly removable test record')
            p,result=self.request({'source':'podcast','action':'delete','key':key,'remove_progress':remove})
            self.assertEqual(p.returncode,0,result)
            self.assertEqual(checkpoint.exists(),not remove)
            _,result=self.request({'source':'podcast','action':'list'})
            self.assertEqual(result['items'],[])
