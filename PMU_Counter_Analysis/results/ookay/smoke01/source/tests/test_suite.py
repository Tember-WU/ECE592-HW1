import importlib.util,json,os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
class Suite(unittest.TestCase):
    def test_distribution_known_values(self):
        s=module('analyze').stats([1.,2.,3.,4.,100.])
        self.assertEqual(s['median'],3.); self.assertEqual(s['outliers'],1); self.assertEqual(s['n'],5)
    def test_timing_cycle_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            prefix=pathlib.Path(d)/'probe'
            # Exactly one cycle returns to the starting node, proving closure for this permutation.
            cmd=[str(ROOT/'build/bench'),str(min(os.sched_getaffinity(0))),'4096','64','64','1','59284','0','0',str(prefix),'1']
            subprocess.run(cmd,check=True)
            r=json.loads(prefix.with_suffix('.json').read_text())
            self.assertEqual(r['checksum_offset'],0); self.assertEqual(r['chain_loads'],64)
            self.assertEqual(prefix.with_suffix('.ticks.u64').stat().st_size,64*8)
            cmd[5]='0'
            self.assertNotEqual(subprocess.run(cmd,stderr=subprocess.DEVNULL).returncode,0)
    def test_full_sample_guard(self):
        r=subprocess.run(['python3',str(ROOT/'scripts/run.py'),'--samples','999999'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0); self.assertIn('1,000,000',r.stderr)
    def test_profiles_have_eight_distinct_slots_and_provenance(self):
        for p in (ROOT/'configs').glob('*.json'):
            c=json.loads(p.read_text()); self.assertEqual(len(c['events']),8)
            self.assertEqual(len({e['slot'] for e in c['events']}),8)
            for e in c['events']:
                self.assertTrue(e['candidates'])
                for v in e['candidates']:
                    self.assertIn(v['type'],[0,3,4]); self.assertGreaterEqual(int(v['config'],0),0); self.assertTrue(v['meaning'])
if __name__=='__main__': unittest.main()
