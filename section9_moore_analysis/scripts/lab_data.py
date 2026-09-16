#!/usr/bin/env python3
"""Extract selected lab summaries and render historical evidence; no benchmarks run."""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

HOSTS = ['sunbird', 'charnwood', 'ookay', 'upgrade', 'crux', 'skylark', 'thunderbird', 'artemisia']
GROUP = {h: ('AMD x86' if h == 'skylark' else 'Arm / Ampere' if h == 'thunderbird' else 'Intel x86') for h in HOSTS}
MARKERS = {'Intel x86': 'o', 'AMD x86': 's', 'Arm / Ampere': '^'}
DESKTOP = ['charnwood', 'ookay', 'upgrade', 'crux']
COMP = 'PMU_Counter_Analysis/results/comparison_artemisia_skylark_sunbird_thunderbird_charnwood_crux_ookay_upgrade01'
PHASE2 = {
    'sunbird': (8, 8, 'PMU-verification/common/results/sunbird/RUN_NOTES.md', 'PMU supports L1 onset at 8; original 9 overestimates. L2 threshold 8 agrees.'),
    'charnwood': (8, 4, 'PMU-verification/results/charnwood/REPORT.md', 'L1 8 supported. Original L2 edge is L1; system L2 is 4 ways. No independent physical indexing proof.'),
    'ookay': (8, 4, 'PMU-verification/results/ookay/SECTION_8_3_REPORT.md', 'L1 8 supported. Original L2 edge is L1; system L2 is 4 ways. No independent physical indexing proof.'),
    'upgrade': (8, 4, 'PMU-verification/reports/upgrade/README.md', 'L1 8 supported. Original L2 edge is L1; system L2 is 4 ways. No independent physical indexing proof.'),
    'crux': (8, 4, 'PMU-verification/results/crux/verification01/comparison.md', 'PMU supports L1 8. Original L2 effective 8 can span two sets; system L2 is 4 ways.'),
    'skylark': (8, 8, 'PMU-verification/skylark/results/system_comparison.csv', 'L1 8 supported. L2 PMU onset at 8; largest-jump selector overestimated as 11.'),
    'thunderbird': (4, 8, 'PMU-verification/results/thunderbird/REPORT.md', 'PMU supports selected L1 4 and L2 8; earlier L2-candidate jump at K5 is L1.'),
    'artemisia': (12, 16, 'PMU-verification/associativity/results/artemisia/associativity02/RUN_NOTES.md', 'PMU supports L1 12; extended L2 test supports effective threshold near 16, not original 12.')
}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.labelsize': 12,
                     'axes.titlesize': 12, 'legend.fontsize': 9, 'axes.grid': False,
                     'lines.linewidth': 1.6, 'lines.markersize': 6,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.facecolor': 'white'})


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def csvwrite(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (HERE / 'tables' / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


class Sources:
    def __init__(self, refresh=False):
        self.refresh = refresh
        self.manifest = {}

    def read(self, rel):
        data = (ROOT / rel).read_bytes()
        self.manifest[rel] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        return data.decode('utf-8')

    def json(self, rel):
        return json.loads(self.read(rel))

    def csv(self, rel):
        return list(csv.DictReader(io.StringIO(self.read(rel))))


def read_taxonomy(src):
    rel = 'PMU_Counter_Analysis/docs/Table1_CPU_Architecture_Research.md'
    text = src.read(rel)
    result = {}
    for line in text.splitlines():
        if not re.match(r'\| 20\d\d \|', line):
            continue
        v = [x.strip() for x in line.strip('|').split('|')]
        year, host, cpu, vendor, isa, gen, arch, process, refs = v
        h = host.lower()
        result[h] = dict(host=h, year=int(year), vendor=vendor, isa=isa, generation=gen,
                         microarchitecture=arch, cpu=cpu, process_node=process,
                         taxonomy_source=rel, taxonomy_references=refs)
    assert set(result) == set(HOSTS)
    assert [result[h]['year'] for h in HOSTS] == sorted(result[h]['year'] for h in HOSTS)
    return result


def cpulist(s):
    result = []
    for part in s.split(','):
        a, _, b = part.partition('-')
        result.extend(range(int(a), int(b or a) + 1))
    return result


def bytesize(s):
    return int(s[:-1]) * {'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3}[s[-1]]


def extract(src, cfg):
    machines = read_taxonomy(src)
    capacity, latencies, assoc, inclusion, line, line_stats, software, metadata = [], [], [], [], [], [], [], {}
    checks = []
    phase2 = []
    for h in HOSTS:
        m = machines[h]
        common = {'host': h, 'year': m['year'], 'group': GROUP[h]}
        p1, p2, psource, pnote = PHASE2[h]
        src.read(psource)
        phase2.append({**common, 'l1_phase2_ways': p1, 'l2_phase2_ways': p2,
                       'scope': 'Separate existing PMU/system interpretation; not new timing inference',
                       'interpretation': pnote, 'source': psource})
        m['l1_phase2_ways'] = p1
        m['l2_phase2_ways'] = p2
        m['phase2_interpretation'] = pnote
        m['phase2_source'] = psource
        cpath = f'timing-only/capacity/results/{h}/combined12/inference.json'
        c = src.json(cpath)
        cv = src.json(f'timing-only/capacity/results/{h}/combined12/validation.json')
        m['capacity_source'] = cpath
        m['capacity_cpu'] = c['cpu']
        m['capacity_numa_node'] = c['numa_node']
        m['capacity_scope'] = c['scope']
        m['data_cache_regions'] = c.get('measurable_data_cache_levels', c.get('measurable_data_cache_residency_regions'))
        for i, level in enumerate(['L1D', 'L2', 'LLC']):
            entry = c['capacity_estimates'][i]
            if i == 2:
                bounds = entry['observed_effective_transition_region_bytes']
            else:
                bounds = next(v for k, v in entry.items() if isinstance(v, list) and len(v) == 2 and 'bytes' in k)
            capacity.append({**common, 'level': level, 'estimate_bytes': entry['approximate_bytes'],
                             'lower_bytes': bounds[0], 'upper_bytes': bounds[1],
                             'interval_type': 'effective transition region, NOT physical-capacity bounds' if i == 2 else 'empirical sampling bracket, NOT confidence interval',
                             'source': cpath})
            m[f'{level.lower()}_inferred_bytes'] = entry['approximate_bytes']
            m[f'{level.lower()}_transition_low_bytes'] = bounds[0]
            m[f'{level.lower()}_transition_high_bytes'] = bounds[1]
        run = cfg['latency_runs'][h]
        lp = f'timing-only/latency/results/{h}/{run}/latency_estimates.json'
        a = src.json(lp)
        env = src.json(f'timing-only/latency/data/{h}/{run}/environment.json')
        src.json(f'timing-only/latency/results/{h}/{run}/validation.json')
        src.json(f'timing-only/latency/results/{h}/{run}/quality.json')
        m['latency_source'] = lp
        m['timer_unit'] = a['units']
        m['timer_frequency_hz'] = env.get('timer_frequency_hz')
        m['ns_available'] = bool(env.get('timer_frequency_hz'))
        for g in ['l1_hit', 'l2_hit', 'llc_hit']:
            primary = a['resident_candidates'][g][g + '__primary']
            values = a['resident_candidates'][g]
            for name, stats in values.items():
                logpath = f'timing-only/latency/data/{h}/{run}/logs/{name}.json'
                log = src.json(logpath)
                assert log['stats']['first']['median'] == stats['median']
                assert stats['n'] == 1_000_000
                latencies.append({**common, 'metric': g, 'point': name, 'units': a['units'],
                                  **{k: v for k, v in stats.items() if not isinstance(v, list)},
                                  'footprint_bytes': log['parameters']['bytes'], 'batch': log['parameters']['batch'],
                                  'source': lp, 'raw_log': logpath, 'raw_file': log['raw_file'], 'raw_sha256': log['raw_sha256']})
            m[g] = primary['median']
            m[g + '_low'] = min(v['p05'] for v in values.values())
            m[g + '_high'] = max(v['p95'] for v in values.values())
            m[g + '_ns'] = primary['median'] * 1e9 / env['timer_frequency_hz'] if env.get('timer_frequency_hz') else None
        for g in ['l1_miss', 'l2_miss', 'llc_miss']:
            vals = [v for v in a['contrasts'] if v['name'].startswith(g + '__')]
            primary = next(v for v in vals if v['name'] == g + '__primary')
            m[g] = primary['difference_of_medians']
            # A descriptive envelope across separate-process median contrasts; not a CI.
            m[g + '_low'] = min(v['difference_of_medians'] for v in vals)
            m[g + '_high'] = max(v['difference_of_medians'] for v in vals)
            m[g + '_next_level'] = primary['first_median']
            for v in vals:
                latencies.append({**common, 'metric': g, 'point': v['name'], 'units': a['units'],
                                  'median': v['difference_of_medians'], 'next_level_median': v['first_median'],
                                  'reference_median': v['reference_median'], 'source': lp})
        m['l2_l1_ratio'] = m['l2_hit'] / m['l1_hit']
        m['l2_l1_ratio_low'] = m['l2_hit_low'] / m['l1_hit_high']
        m['l2_l1_ratio_high'] = m['l2_hit_high'] / m['l1_hit_low']
        for level in ['l1', 'l2']:
            p = f'timing-only/associativity/data/{h}/raw_data/{level}_associativity.csv'
            rows = sorted(src.csv(p), key=lambda r: int(r['K']))
            k = np.array([int(r['K']) for r in rows])
            probs = np.array([float(r['eviction_probability']) for r in rows])
            idx = int(np.argmax(np.diff(probs)))
            edge = bool(probs[0] < .2 and probs[-1] > .8 and np.diff(probs)[idx] >= .5)
            inferred = int(k[idx])
            candidates = []
            sp = f'timing-only/associativity/data/{h}/raw_data/associativity_candidate_selection.txt'
            if (ROOT / sp).exists() or (HERE / 'inputs/sources' / sp).exists():
                selection = src.read(sp)
                sec = selection.split('=== ' + level.upper() + ' candidate sweep')[1].split('SELECTED')[0]
                candidates = [int(v) for v in re.findall(r'has_edge=True inferred_ways=(\d+)', sec)]
            status = 'effective conflict threshold; candidate-stride sensitive' if len(set(candidates)) > 1 else 'effective conflict threshold; physical ways not proven'
            assoc.append({**common, 'level': level.upper(), 'selected_effective_ways': inferred,
                          'candidate_min': min(candidates or [inferred]), 'candidate_max': max(candidates or [inferred]),
                          'clean_edge': edge, 'largest_probability_jump': float(np.diff(probs)[idx]),
                          'status': status, 'source': p, 'sha256': src.manifest[p]['sha256']})
        sp = f'timing-only/line_size/data/{h}/stats/all_stats.csv'
        stats = src.csv(sp)
        for row in stats:
            line_stats.append({**common, **row, 'source': sp})
        # No new numerical line-size inference: the existing plotting script marks 64 B
        # as a candidate regardless of data. Retain candidate and validation separately.
        line.append({**common, 'timing_inferred_line_bytes': None, 'existing_candidate_bytes': 64,
                     'status': '64 B candidate; exact line size not established by saved inference', 'source': sp})
        ip = f'timing-only/inclusion/data/{h}/raw_data_inclusion/{h}/inclusion_report.json'
        ir = src.json(ip)
        conflict = src.csv(f'timing-only/inclusion/data/{h}/raw_data_inclusion/{h}/find_conflict_summary.csv')
        max_p = max(float(r['eviction_probability']) for r in conflict)
        inclusion.append({**common, **ir, 'max_search_eviction_probability': max_p,
                          'section9_policy': 'uncertain', 'source': ip,
                          'reason': 'LLC eviction not demonstrated; potential L2 contamination; 40000 trials below required million'})
        m['inclusion_inferred'] = 'uncertain'
        m['inclusion_original_verdict'] = ir['verdict']
        m['inclusion_n_trials'] = ir['n_trials']
        m['llc_effective_associativity'] = None
        mp = f'PMU_Counter_Analysis/results/{h}/counters01/metadata.json'
        md = metadata[h] = src.json(mp)
        assert md['config']['year'] == m['year']
        assert md['smoke'] is False
        m['identification_source'] = mp
        match = re.search(r'^model name\s*:\s*(.+)$', md['cpuinfo'], re.MULTILINE)
        m['observed_model'] = match.group(1) if match else 'Arm implementer/part recorded; Q80-30 mapping inherited from course Table 1'
        ll = next((e for e in md['cache_inventory'] if e['level'] == '3'), None)
        m['llc_system_bytes'] = bytesize(ll['size']) if ll else None
        m['llc_sharing_logical_cpus'] = ll['shared_cpu_list'] if ll else None
        nthreads = len(cpulist(md['topology']['thread_siblings_list']))
        ncores = len(cpulist(ll['shared_cpu_list'])) // nthreads if ll else None
        m['llc_system_domain_cores'] = ncores
        m['llc_system_bytes_per_core'] = m['llc_system_bytes'] / ncores if ll else None
        m['llc_system_scope'] = 'OS-reported sharing domain at Section 8.4 pinned core; topology from a different phase/run'
        m['line_system_bytes'] = int(md['cache_inventory'][0]['coherency_line_size'])
        m['line_timing_inferred_bytes'] = None
        m['line_candidate_bytes'] = 64
        checks.append(f'{h}: capacity and latency source selected; 9 resident summaries match saved per-point logs; 1e6 samples each; taxonomy year matches 8.4')
    # Preserve BOTH ambiguous host assignments; do not decide which file was copied.
    for r in assoc:
        peers = [x['host'] for x in assoc if x['level'] == r['level'] and x['sha256'] == r['sha256'] and x['host'] != r['host']]
        r['identical_other_host_files'] = ','.join(peers)
        if peers:
            r['status'] = 'duplicate across hosts; independent machine provenance unresolved'
        m = machines[r['host']]
        m[r['level'].lower() + '_effective_ways_recorded'] = r['selected_effective_ways']
        m[r['level'].lower() + '_associativity_status'] = r['status']
        m[r['level'].lower() + '_derived_sets'] = None
    for h in ['sunbird', 'artemisia']:
        p = f'software-hit-rate/results/{h}/hitrate01/comparison.csv'
        rows = src.csv(p)
        src.json(f'software-hit-rate/results/{h}/hitrate01/validation.json')
        src.json(f'software-hit-rate/data/{h}/hitrate01/model.json')
        config = src.json(f'software-hit-rate/configs/{h}.json')
        for r in rows:
            software.append({'host': h, 'year': machines[h]['year'], **r, 'source': p})
        for case in sorted(set(r['case'] for r in rows)):
            selected = [r for r in rows if r['case'] == case]
            machines[h]['software_' + case] = float(np.median([float(r['software_standalone']) for r in selected]))
    pmu = src.csv(COMP + '/normalized_summary.csv')
    semantics = src.csv(COMP + '/event_semantics.csv')
    src.read('PMU_Counter_Analysis/docs/generic_mapping_review.md')
    src.read('timing-only/line_size/scripts/run_line_size_experiment.py')
    src.read('timing-only/associativity/scripts/run_associativity.py')
    src.read('timing-only/inclusion/scripts/run_inclusion_experiment.py')
    for r in pmu:
        r['year'] = machines[r['host']]['year']
        r['footprint_bytes'] = metadata[r['host']]['workloads'][r['workload']]
        r['source'] = COMP + '/normalized_summary.csv'
    csvwrite('chronological_master.csv', [machines[h] for h in HOSTS])
    for name, rows in [('capacity', capacity), ('latency', latencies), ('associativity', assoc),
                       ('inclusion', inclusion), ('line_size_candidates', line), ('line_size_evidence', line_stats),
                       ('software_metric', software), ('pmu_normalized', pmu), ('pmu_semantics', semantics),
                       ('phase2_verification', phase2)]:
        csvwrite(name + '.csv', rows)
    return machines, capacity, latencies, assoc, inclusion, line_stats, software, pmu, checks


def axes_year(ax, end=2023):
    ax.set_xlim(2013.4, end + .6)
    ax.set_xticks([2014, 2016, 2018, 2020, 2023] + ([end] if end > 2023 else []))
    ax.set_xlabel('Processor-generation launch year')
    ax.spines[['top', 'right']].set_visible(False)


def points(ax, machines, vals, lows=None, highs=None, labels=False, connect=True):
    # Only the four related desktop generations are joined as an observed lineage.
    if connect:
        hs = [h for h in DESKTOP if h in vals and vals[h] is not None]
        if len(hs) > 1:
            ax.plot([machines[h]['year'] for h in hs], [vals[h] for h in hs], color='.45', zorder=1)
    for group, marker in MARKERS.items():
        hs = [h for h in HOSTS if GROUP[h] == group and h in vals and vals[h] is not None]
        if not hs:
            continue
        xx = [machines[h]['year'] for h in hs]
        yy = [vals[h] for h in hs]
        err = None
        if lows is not None:
            err = np.array([[max(0, vals[h] - lows[h]) for h in hs], [max(0, highs[h] - vals[h]) for h in hs]])
        ax.errorbar(xx, yy, yerr=err, fmt=marker, color='black', markerfacecolor='black',
                    label=group, capsize=3, linestyle='none', zorder=3)
        if labels:
            for h, x, y in zip(hs, xx, yy):
                dy = 22 if h in ['charnwood', 'upgrade', 'thunderbird'] else 8
                ax.annotate(h.title(), (x, y), xytext=(0, dy), textcoords='offset points', ha='center', fontsize=8)


FIGS = []


def save(fig, name, caption):
    fig.savefig(HERE / 'figures' / (name + '.pdf'), bbox_inches='tight', metadata={'CreationDate': None, 'ModDate': None})
    fig.savefig(HERE / 'figures' / (name + '.png'), dpi=155, bbox_inches='tight')
    plt.close(fig)
    FIGS.append({'file': name, 'caption': caption})


def make_plots(machines, capacity, assoc, inclusion, line_stats, software, pmu):
    for level, index in [('L1D', '01'), ('L2', '05')]:
        rows = [r for r in capacity if r['level'] == level]
        fig, ax = plt.subplots(figsize=(8.5, 4.2), layout='constrained')
        points(ax, machines, {r['host']: r['estimate_bytes']/1024 for r in rows},
               {r['host']: r['lower_bytes']/1024 for r in rows}, {r['host']: r['upper_bytes']/1024 for r in rows}, labels=True)
        ax.set_yscale('log', base=2)
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.set_ylabel(f'{level} capacity (KiB/core)')
        axes_year(ax)
        ax.legend(loc='upper left')
        ax.margins(y=.35)
        save(fig, f'{index}_{level.lower()}_capacity', f'{level} timing-derived capacity; bars show sampled transition neighborhoods, not statistical confidence intervals. Solid links join only related Intel desktop observations; server and other-vendor points remain separate.')
    for level, index in [('L1','02'), ('L2','06')]:
        rows = [r for r in assoc if r['level'] == level]
        fig, aa = plt.subplots(1,2,figsize=(12,4.3), layout='constrained')
        ax = aa[0]
        usable = [r for r in rows if not r['identical_other_host_files']]
        points(ax, machines, {r['host']:r['selected_effective_ways'] for r in usable},
               {r['host']:r['candidate_min'] for r in usable}, {r['host']:r['candidate_max'] for r in usable}, labels=True, connect=False)
        for r in rows:
            if r['identical_other_host_files']:
                ax.scatter(r['year'], r['selected_effective_ways'], marker='x', s=65, color='black')
                ax.annotate(r['host'].title()+'*', (r['year'],r['selected_effective_ways']), xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
        ax.set_ylim(2,15); axes_year(ax)
        ax.set_ylabel(f'Recorded {level} candidate threshold (lines)')
        ax.set_title('Original timing inference / candidate')
        ax.legend(loc='lower right')
        points(aa[1],machines,{h:m[level.lower()+'_phase2_ways'] for h,m in machines.items()},labels=True,connect=False)
        axes_year(aa[1]);aa[1].set_ylim(2,19)
        aa[1].set_ylabel('Ways / supported threshold in Section 8.3')
        aa[1].set_title('Separate PMU / system interpretation')
        save(fig, f'{index}_{level.lower()}_associativity', 'Left: selected candidate thresholds, not proven physical ways; bars span clean-edge stride outcomes. Crosses mark byte-identical Sunbird/Crux summaries with unresolved independent provenance. Right: separate Section 8.3 interpretations (see phase2_verification.csv), including system-based physical ways and the supported 16-line Artemisia L2 threshold. Several original purported L2 edges were identified as L1 conflicts. No associativity trend is fitted.')
    for metric, index, title in [('l1_hit','03','L1D resident latency'),('l1_miss','04','L1-to-L2 incremental cost'),
                                  ('l2_hit','07','L2 resident latency'),('l2_miss','08','L2-to-LLC incremental cost'),
                                  ('llc_hit','11a','LLC-region resident latency'),('llc_miss','11b','LLC-to-memory incremental cost')]:
        fig, aa = plt.subplots(1,3,figsize=(13,3.9),layout='constrained')
        for ax, group in zip(aa, MARKERS):
            hs=[h for h in HOSTS if GROUP[h]==group]
            factor=40 if group=='Arm / Ampere' else 1
            points(ax,machines,{h:machines[h][metric]*factor for h in hs},
                   {h:machines[h][metric+'_low']*factor for h in hs}, {h:machines[h][metric+'_high']*factor for h in hs})
            axes_year(ax);ax.set_title(group)
            ax.set_ylabel('ns / dependent load' if group=='Arm / Ampere' else 'Local TSC ticks / dependent load')
            ax.margins(y=.25)
        fig.suptitle(title)
        save(fig,index+'_'+metric, title+'. Separate native-timer panels prevent a false common cycle scale. x86 TSC frequency was not saved; no ns or core-cycle conversion is made. Arm uses documented 25 MHz CNTVCT. Hit bars span P05-P95 across primary/alternate/repeat points; miss bars span differences of medians across those configurations, not a penalty confidence interval.')
    fig, aa = plt.subplots(1,2,figsize=(11,4.1),layout='constrained')
    for r in capacity:
        if r['level']!='LLC': continue
        x=r['year']; lo=r['lower_bytes']/1024**2;hi=r['upper_bytes']/1024**2
        aa[0].vlines(x,lo,hi,color='black',lw=2)
        aa[0].plot([x,x],[lo,hi],marker=MARKERS[GROUP[r['host']]],color='black',linestyle='none')
    aa[0].set_ylabel('Effective transition region (MiB)');aa[0].set_title('Timing evidence: no exact LLC capacity')
    aa[0].set_yscale('log',base=2);aa[0].yaxis.set_major_formatter(ScalarFormatter());axes_year(aa[0])
    vals={h:m['llc_system_bytes_per_core']/1024**2 for h,m in machines.items() if m['llc_system_bytes_per_core'] is not None}
    points(aa[1],machines,vals,labels=False,connect=False);aa[1].set_title('Separate OS validation: sharing domain / core')
    for h,y in vals.items():
        aa[1].annotate(h.title(),(machines[h]['year'],y),xytext=(0,-22 if h in ['charnwood','upgrade'] else 8),textcoords='offset points',ha='center',fontsize=8)
    aa[1].set_ylabel('OS-reported LLC (MiB / physical core)');axes_year(aa[1]);aa[1].set_ylim(1,16)
    aa[1].set_yscale('log',base=2);aa[1].yaxis.set_major_formatter(ScalarFormatter())
    save(fig,'09_llc_capacity','Left: timing-observed LLC transition spans; endpoints do not bound physical capacity and no midpoint is inferred. Right: separate post-Phase-I sysfs sharing-domain capacity divided by domain physical-core count, using saved thread topology; no socket aggregation. Thunderbird has no sysfs LLC entry and is omitted only from the validation panel.')
    fig,ax=plt.subplots(figsize=(8.5,3.5),layout='constrained')
    points(ax,machines,{h:0 for h in HOSTS},connect=False)
    ax.set_yticks([0],['Unresolved']);ax.set_ylim(-.5,.5);axes_year(ax)
    ax.set_title('LLC effective associativity: no defensible numerical estimate')
    save(fig,'10_llc_associativity','All hosts are explicitly unresolved. The saved LLC conflict search did not establish reliable eviction; inclusion pressure K is not an associativity measurement.')
    fig,aa=plt.subplots(1,2,figsize=(11,3.9),layout='constrained')
    points(aa[0],machines,{h:64 for h in HOSTS},connect=False);axes_year(aa[0]);aa[0].set_ylim(48,80)
    aa[0].set_ylabel('Existing candidate (bytes)');aa[0].set_title('64 B candidate; timing estimate unresolved')
    points(aa[1],machines,{h:machines[h]['line_system_bytes'] for h in HOSTS});axes_year(aa[1]);aa[1].set_ylim(48,80)
    aa[1].set_ylabel('OS coherency line size (bytes)');aa[1].set_title('Separate post-Phase-I validation')
    save(fig,'12_line_size','The original stride script hardcodes a 64 B candidate marker. It does not compute a unique line-size inference. Candidate and system-reported values are shown separately; neither is promoted to a measured timing law.')
    fig,aa=plt.subplots(1,2,figsize=(11,3.9),layout='constrained')
    points(aa[0],machines,{h:0 for h in HOSTS},connect=False);aa[0].set_yticks([0],['Uncertain']);aa[0].set_ylim(-.5,.5);axes_year(aa[0])
    aa[0].set_title('Policy classification supported by current evidence')
    points(aa[1],machines,{r['host']:100*r['fraction_L2_hit'] for r in inclusion},connect=False);axes_year(aa[1]);aa[1].set_ylim(90,101)
    aa[1].set_ylabel('Reloads classified as L2-resident (%)');aa[1].set_title('Observed behavior under attempted LLC pressure')
    save(fig,'13_inclusion','High inner-resident reload fractions do not prove non-inclusion when LLC eviction itself was not established. Every run has only 40000 trials and flags potential L2 contamination in every recorded trial. Original verdicts are retained in the CSV, but the supported policy is uncertain.')
    fig,aa=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,case in zip(aa,['reuse2_256k','nonresident_128k']):
        for h in ['sunbird','artemisia']:
            rows=[r for r in software if r['host']==h and r['case']==case]
            vals=np.array([float(r['software_standalone']) for r in rows])*100
            yy=float(np.median(vals));x=machines[h]['year']
            ax.errorbar(x,yy,yerr=[[yy-min(vals)],[max(vals)-yy]],fmt='o',color='black',capsize=3,label='Timing-only estimate' if h=='sunbird' else None)
            pp=np.array([float(r['pmu_hit_rate']) for r in rows])*100
            ax.scatter(x,float(np.median(pp)),marker='x',color='black',s=70,label='Separate PMU reference' if h=='sunbird' else None)
        axes_year(ax);ax.set_ylim(-5,105);ax.set_ylabel('L1D hit-rate estimate (%)');ax.set_title(case)
    aa[0].legend()
    save(fig,'14_software_hit_rate','Identical named workloads on the only two available Section 8.5 hosts. Primary markers use standalone, PMU-free estimator executions; bars are min/max of three repeats. Crosses show separate PMU validation. Six hosts are missing, so no chronological fit or projection is made. The 128 KiB case exposes estimator failure on Sunbird.')
    # Comparability subset: same-generation-lineage Intel desktop read-load accounting
    # and demand-load page walks; other PMU scopes are retained in the full CSV.
    for slot,index,title in [('l1_loads','15a','Intel desktop retired-load mapping'),('dtlb_misses','15b','Intel desktop completed demand-load page walks')]:
        fig,aa=plt.subplots(1,3,figsize=(12.5,3.8),layout='constrained')
        for ax,work in zip(aa,['l1_resident','llc_sized','beyond_llc']):
            rows=[r for r in pmu if r['host'] in DESKTOP and r['slot']==slot and r['workload']==work]
            points(ax,machines,{r['host']:float(r['median']) for r in rows},
                   {r['host']:float(r['minimum']) for r in rows},{r['host']:float(r['maximum']) for r in rows})
            axes_year(ax);ax.set_xlim(2014.6,2018.4);ax.set_xticks([2015,2016,2017,2018]);ax.set_title(work)
            ax.set_ylabel('Events / 1,000 pointer loads')
        fig.suptitle(title)
        save(fig,index+'_'+slot, title+'. Only the four related Intel desktops are compared under the saved mapping review; vendor-kernel mapping caveat remains. Error bars are min/max of three counter passes. Workloads are capacity-relative (different byte sizes), not controlled year-only experiments. All other host/event results remain in pmu_normalized.csv.')
    fig,aa=plt.subplots(1,2,figsize=(11,4.1),layout='constrained')
    for ax,metric,title in [(aa[0],'l2_l1_ratio','Cross-architecture relative latency'),(aa[1],'llc_l1_ratio','LLC-region / L1 relative latency')]:
        vals={h:(m['l2_l1_ratio'] if metric=='l2_l1_ratio' else m['llc_hit']/m['l1_hit']) for h,m in machines.items()}
        numerator='l2_hit' if metric=='l2_l1_ratio' else 'llc_hit'
        lows={h:m[numerator+'_low']/m['l1_hit_high'] for h,m in machines.items()}
        highs={h:m[numerator+'_high']/m['l1_hit_low'] for h,m in machines.items()}
        points(ax,machines,vals,lows,highs,labels=False)
        for h,y in vals.items():
            ax.annotate(h.title(),(machines[h]['year'],y),xytext=(0,-24 if h in ['charnwood','upgrade','skylark'] else 12),textcoords='offset points',ha='center',fontsize=8)
        axes_year(ax);ax.set_ylabel('Ratio of resident medians');ax.set_title(title);ax.margins(y=.35)
    aa[0].legend()
    save(fig,'17_latency_ratios','Dimensionless within-host latency ratios permit a common cross-architecture axis without assuming TSC ticks equal core cycles. They still include run/frequency, candidate-residency and shared-machine effects; the ratios are benchmark observations, not pure hardware latency ratios.')
    dump(HERE/'tables/figure_manifest.json',FIGS)
