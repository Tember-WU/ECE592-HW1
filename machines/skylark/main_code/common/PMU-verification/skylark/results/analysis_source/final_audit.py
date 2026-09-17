"""Audit preserved originals and the completed six-run evidence package."""
import datetime as dt
import json
from pathlib import Path
import re
import shutil
from support import PMU, frozen_check, sha


def main():
    frozen = frozen_check()
    original = json.loads((PMU / 'skylark/original_pmu_sha256.json').read_text())
    changed = [p for p, checksum in original.items() if sha(PMU.parent / p) != checksum]
    if changed: raise ValueError('Original PMU files changed: ' + str(changed))
    out = PMU / 'skylark/results'
    combined = json.loads((out / 'combined_validation.json').read_text())
    if combined['status'] != 'passed': raise ValueError('Combined validation failed')
    totals = dict(samples=0, minor_faults=0, major_faults=0, involuntary_switches=0, raw_files=0)
    runs = []
    for experiment in ('capacity', 'line_size', 'associativity'):
        for run in (experiment + '01', experiment + '02_refills'):
            data = PMU / experiment / 'data/skylark' / run
            result = PMU / experiment / 'results/skylark' / run
            m = json.loads((data / 'manifest.json').read_text())
            c = json.loads((data / 'config.json').read_text())
            provenance = json.loads((result / 'provenance.json').read_text())
            if m['status'] != 'complete' or sha(data / 'manifest.json') != provenance['manifest_sha256']:
                raise ValueError('Run changed after analysis')
            pages = []
            for job in m['jobs']:
                if job['status'] != 'complete': raise ValueError('Incomplete point')
                for key in ('raw', 'counts'):
                    if sha(data / job[key + '_file']) != job[key + '_sha256']:
                        raise ValueError('Evidence changed after validation')
                counts = json.loads((data / job['counts_file']).read_text())
                if counts['time_enabled_ns'] != counts['time_running_ns'] or counts['time_running_ns'] <= 0:
                    raise ValueError('Unscheduled counter group')
                log = (data / job['log_file']).read_text()
                huge = list(map(int, re.findall(r'AnonHugePages:\s+(\d+)', log)))
                if len(huge) != 2 or huge[0] != huge[1]: raise ValueError('Page backing changed')
                if experiment == 'capacity':
                    mapped = int(re.search(r'mapped_bytes=(\d+)', log)[1])
                    if huge[0] * 1024 != mapped: raise ValueError('Incomplete capacity THP backing')
                elif experiment == 'associativity' and huge != [2048, 2048]:
                    raise ValueError('Unexpected associativity mapping')
                elif experiment == 'line_size' and huge != [0, 0]:
                    raise ValueError('Unexpected line-size mapping')
                pages.append(huge[0])
                totals['samples'] += job['statistics']['n']; totals['raw_files'] += 1
                events = job['measurement_events']
                totals['minor_faults'] += events.get('minor_faults', events.get('measurement_minor_faults', 0))
                for key in ('major_faults', 'involuntary_switches'): totals[key] += events[key]
            runs.append(dict(experiment=experiment, run_id=run, points=len(m['jobs']), cpu=c['cpu'],
                             numa_node=c['numa_node'], started_utc=m['started_utc'], finished_utc=m['finished_utc'],
                             elapsed_seconds=m['elapsed_seconds'], all_raw_and_count_hashes_match=True,
                             all_groups_without_multiplexing=True, stable_huge_kib=sorted(set(pages))))
    if totals['samples'] != 76000000 or totals['raw_files'] != 76:
        raise ValueError('Formal sample total mismatch')
    target = out / 'analysis_source'; target.mkdir(exist_ok=True)
    for p in (PMU / 'skylark').glob('*.py'): shutil.copyfile(p, target / p.name)
    audit = dict(status='passed', completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 original_pmu_files_preserved=len(original), frozen_phase1_files_unchanged=len(frozen['sha256']),
                 totals=totals, runs=runs, combined_validation_sha256=sha(out / 'combined_validation.json'),
                 implementation_and_analysis_hashes={p.name: sha(p) for p in target.glob('*.py')},
                 result_artifact_hashes={p.name: sha(p) for p in out.iterdir()
                                        if p.is_file() and p.name != 'final_audit.json'},
                 report_sha256=sha(PMU / 'SKYLARK.md'))
    (out / 'final_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    for p in [PMU / 'SKYLARK.md', PMU / 'skylark/EVENTS.md']:
        for link in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if '://' in link or link.startswith('#'): continue
            if not (p.parent / link.split('#')[0]).exists(): raise ValueError('Broken report link: ' + link)
    print(f"Preserved {len(original)} original PMU files and {len(frozen['sha256'])} frozen Phase-I files; verified {totals['samples']:,} samples across 76 raw files.")


if __name__ == '__main__':
    main()
