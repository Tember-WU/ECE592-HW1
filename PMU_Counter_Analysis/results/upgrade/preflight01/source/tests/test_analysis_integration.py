"""Exercise the multi-host analysis with temporary synthetic fixtures, never report data."""
import json,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AnalysisGuards(unittest.TestCase):
    def test_duplicate_hosts_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)
            (p/'metadata.json').write_text(json.dumps({'host':'fixture'}))
            (p/'records.json').write_text('[]')
            r=subprocess.run(['python3',str(ROOT/'scripts/analyze.py'),str(p),str(p)],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0); self.assertIn('one run per host',r.stderr)
    def test_mixed_smoke_and_full_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            paths=[]
            for i in range(2):
                p=pathlib.Path(td)/str(i); p.mkdir(); paths.append(str(p))
                (p/'metadata.json').write_text(json.dumps({'host':str(i),'smoke':bool(i)})); (p/'records.json').write_text('[]')
            r=subprocess.run(['python3',str(ROOT/'scripts/analyze.py')]+paths,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0); self.assertIn('Cannot combine',r.stderr)
