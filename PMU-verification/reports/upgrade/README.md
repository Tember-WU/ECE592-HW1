# Upgrade — Section 8.3 PMU verification

已在 `upgrade.ece.ncsu.edu` 上依次完成 capacity、line_size、associativity：共 44 个配置，每个配置 100 万次 timed batches。原始数据、计数器值、图表、运行日志和失败记录均已保存。L1/L2 容量和 L1 8 路阈值得到支持；原始 L2 自动标签不能直接作为物理路数；LLC 有效转折和 64 B line-size 候选的限制见下表。

| Experiment | Completed run and notes | Points | Timed batches | Collection time |
|---|---|---:|---:|---:|
| Capacity | [capacity02](../../capacity/results/upgrade/capacity02/RUN_NOTES.md) | 14 | 14,000,000 | 26.88 s |
| Line/stride | [line_size01](../../line_size/results/upgrade/line_size01/RUN_NOTES.md) | 12 | 12,000,000 | 51.05 s |
| Associativity | [associativity01](../../associativity/results/upgrade/associativity01/RUN_NOTES.md) | 18 | 18,000,000 | 21.21 s |

Successful collection and analysis ran sequentially from **2026-09-14 15:42:16 to 15:44:05 UTC** (11:42–11:44 EDT). The [execution ledger](execution.json) records each interval. There were 18,355,000,000 known chain loads inside the PMU counting windows, including associativity's untimed preparation loads. Each point has one aggregate four-event counter read and one million raw timing intervals, not one million separate counter reads.

## Phase-I freeze and preserved workload

Upgrade's associativity baseline was missing when this work started. The original timing-only flow was therefore completed first: four candidate sweeps for K=1…16 and two three-point boundary repeats, totaling 70 million batches, with no PMU workload counters. The unchanged timing-only source was compiled locally and pinned to CPU 2/node 0. Its [setup manifest](../../../timing-only/associativity/data/upgrade/setup/manifest.json), [raw data](../../../timing-only/associativity/data/upgrade/raw_data/), and [plots](../../../timing-only/associativity/results/upgrade/plots/) are preserved. These prerequisite samples are separate from the 44 million PMU samples above.

At **15:35:57–15:35:58 UTC**, before formal PMU collection and system/vendor cache-geometry lookup, the [freeze manifest](../../phase1_freeze/upgrade/freeze01/manifest.json) recorded 740 Phase-I files (765,410,922 bytes), with hashes for all selected raw data and copies of small results, source and metadata. The [frozen inference](../../phase1_freeze/upgrade/freeze01/inference.json) explicitly retained the ambiguous L2 candidate labels rather than claiming a unique physical L2 associativity. Earlier event-list and short scheduling probes tested access, not cache behavior. The [final verification](verification.json) confirms that all frozen originals and snapshots remain unchanged.

The existing Artemisia C/C++ PMU kernels were reused without changes. Capacity points were chosen around Upgrade's frozen boundaries. Line-size parameters and CPU 4/node 0 placement match its existing baseline. Associativity uses CPU 2/node 0; its eighteen points comprise the original twelve-point design adapted to the local candidates plus six controls at already measured candidate spacings. The controls were selected before formal PMU measurements; K=17/18 are explicitly new extensions with no Phase-I counterpart. No experiments ran concurrently with one another.

The inherited PMU implementation buffers line-size output after measurement instead of formatting CSV inside each sample loop. Associativity retains the original timed dependency loop and now also preserves acquisition-order ticks. These disclosed differences can affect absolute timing. Associativity times **129**, not 128, loads: displayed old medians are multiplied by 128/129, while original files and legacy values are preserved. Capacity divides ticks by 256 and line_size by 1,024. All primary timing units are **TSC ticks per timed load**, with overhead retained, not calibrated core cycles.

## Local event discovery

[Discovery01](../../events/results/upgrade/discovery01/EVENTS.md) retains the full local `perf list` and `perf list --details`, 270 parsed cache/virtual-memory entries, sixteen individual event probes and a four-event group probe. **17/17 probes counted successfully**. Unprobed listed events are not claimed usable. The selected events were checked again against local encodings before each formal run.

| Event | Raw event + umask | Counting role |
|---|---|---|
| `mem_load_retired.l1_miss` | `0x08d1` | Retired loads missing L1 |
| `mem_load_retired.l2_miss` | `0x10d1` | Retired loads missing L2 |
| `mem_load_retired.l3_miss` | `0x20d1` | Retired loads missing LLC |
| `mem_inst_retired.all_loads` | `0x81d0` | Retired loads, including helper/stack overhead |

This host's detailed listing uses the `default_core/` alias. Discovery and runners now accept the exposed core-PMU aliases and reject missing or ambiguous raw encodings. The encodings happen to equal Artemisia's selected values; that equality was checked locally rather than assumed.

Four per-thread user-mode events were grouped and pinned around each complete sample loop; initialization, warm-up and output were excluded. **All 44 groups reported equal enabled/running times**, with no multiplex scaling. This reproduces the four-event Section 8.3 workflow; Section 8.4's eight-event study is separate. Counters include helper loads, so normalized misses are per known chain load, not exact per-address probabilities. Retired loads per 1,000 chain loads were 1,061.11–1,062.39 for capacity, 5,024.96–5,027.25 for line_size and 5,390.31–5,417.89 for associativity. An L3 miss alone does not establish local-DRAM service.

## Timing, PMU and system/vendor comparison

System geometry was read **after the freeze**. [Local sysfs records](system/cache_sysfs.json) and [raw/decoded CPUID leaf 4](system/cpuid_leaf4.csv) agree on the cache sizes, ways, sets and lines. Intel identifies this processor as Coffee Lake and specifies 12 MB Smart Cache. [Intel i7-8700 specifications](https://www.intel.com/content/www/us/en/products/sku/126686/intel-core-i78700-processor-12m-cache-up-to-4-60-ghz/specifications.html).

Agner Fog covers Coffee Lake in §11.15 and gives the related Lake-family cache table in §11.12, Table 11.2, printed p. 160. That table reports a 32 KiB eight-way L1D, a model-dependent L2 range (256 KiB–1 MiB, 4–16 ways), 64 B lines and shared L3. Its family ranges are not treated as an exact i7-8700 specification. [Agner Fog, The microarchitecture of Intel, AMD, and VIA CPUs, pp. 160–161](https://www.agner.org/optimize/microarchitecture.pdf#page=160).

All miss figures below mean misses per 1,000 known chain loads. Sampling brackets are empirical intervals, not confidence intervals.

| Property | Timing Inference | PMU Evidence | Published/System Value | Source/Page | Error/Agreement |
|---|---|---|---|---|---|
| Data-cache levels | Three latency regions | Separate L1/L2/LLC miss behavior | Three data/unified cache levels; separate L1I also exists | [Sysfs](system/cache_sysfs.json), [CPUID](system/cpuid_leaf4.csv) | Agrees on data hierarchy; L1I was not measured |
| L1D capacity | Approximately 32 KiB; edge 32–36 KiB | L1 misses 38.91→994.21; median 3.17→8.45 ticks/load | 32 KiB | [Sysfs](system/cache_sysfs.json); [Agner Table 11.2, p. 160](https://www.agner.org/optimize/microarchitecture.pdf#page=160) | Nominal estimate agrees (0% difference); finite sampling resolution remains |
| L2 capacity | Approximately 256 KiB; edge 256–288 KiB | L2 misses 7.18→286.81; median 8.65→13.93 | 256 KiB | [Sysfs](system/cache_sysfs.json), [CPUID](system/cpuid_leaf4.csv) | Nominal estimate agrees (0% difference) |
| LLC capacity | Effective transition 7–8 MiB; physical size deliberately unresolved | L3 misses 0.59 at 6 MiB, 51.92 at 7 MiB, 51.42 at 8 MiB; smaller latency rise than Phase I | 12 MiB shared LLC | [Sysfs](system/cache_sysfs.json); [Intel SKU, CPU Specifications](https://www.intel.com/content/www/us/en/products/sku/126686/intel-core-i78700-processor-12m-cache-up-to-4-60-ghz/specifications.html) | Physical capacity not verified. Frozen effective threshold is 4–5 MiB below physical size; these are different quantities |
| L1-visible line size | 64 B candidate, noisy dense sweep | Random-window L1 misses 240.85→324.57→338.85 at 56→64→72 B; offset control similar | 64 B L1D line | [Sysfs](system/cache_sysfs.json); [Agner p. 160](https://www.agner.org/optimize/microarchitecture.pdf#page=160) | Candidate agrees numerically; PMU gives qualified support, not a clean plateau |
| L2/LLC line size | No independent per-level inference | This fixed-footprint stride experiment does not isolate their line sizes | 64 B at both levels | [Sysfs](system/cache_sysfs.json), [CPUID](system/cpuid_leaf4.csv) | System value only |
| L1D ways | Eight-address threshold at 4 KiB spacing | K=8→9: L1 misses 0.53→984.54; L2 misses remain below 0.001 | 8 ways | [Sysfs](system/cache_sysfs.json); [Agner p. 160](https://www.agner.org/optimize/microarchitecture.pdf#page=160) | Eight-way candidate supported for this layout |
| L2 ways | Auto-label 8 at 16 KiB spacing, 9 at 32/64 KiB; physical ways withheld | At 16 KiB, K=8→9 is L1; K=16→17 increases L2 misses 0.13→182.64 | 4 ways | [Sysfs](system/cache_sysfs.json), [CPUID](system/cpuid_leaf4.csv) | Auto-label 8 would be +100% if misread as physical ways; reject that interpretation. Later threshold is compatible with four sets × four ways |
| L1D derived sets | 32 KiB / (64 B × 8) = 64 | Capacity, line and L1 conflict evidence mutually consistent | 64 sets | [Sysfs](system/cache_sysfs.json) | Agrees; derived, not a separate set-mapping measurement |
| L2 derived sets | Auto candidate 256 is inconsistent: 256 × 64 B × 8 = 128 KiB, not measured 256 KiB | Additional 32/64 KiB controls show increasing L2 misses, but L1 can mask the smaller L2-way threshold | 1,024 sets; 256 KiB / (64 B × 4) | [Sysfs](system/cache_sysfs.json), [CPUID](system/cpuid_leaf4.csv) | Timing candidate is not validated; 1,024 uses system-reported four ways |
| LLC ways/sets | Not inferred | No LLC conflict experiment | 16 ways; 12,288 reported sets; complex indexing flag set | [CPUID](system/cpuid_leaf4.csv) | System values only; not proof of slice mapping |
| Hit latency | Existing frozen latency medians: L1 3.031–3.035, L2 8.848–8.855, LLC 26.109–27.441 TSC ticks/load | Capacity counters support the ordering of cache-residency regions; no separate latency PMU rerun | Agner table lists 4, 14, 34–85 core cycles for L1/L2/L3 family entries | [Prior latency summary](../../../timing-only/latency/results/upgrade/latency01/summary.csv); [Agner p. 160](https://www.agner.org/optimize/microarchitecture.pdf#page=160) | Units and scope differ; no numeric percentage-error claim or TSC-to-core-cycle conversion |
| Sharing scope | Single-thread tests; no independent sharing inference | Affinity verified; SMT activity recorded | L1D/L2 shared by CPU 2,8 or CPU 4,10; LLC by CPUs 0–11 | [Sysfs](system/cache_sysfs.json), [topology](system/cpu-topology.txt) | System topology documented, not experimentally proven sharing scope |
| Inclusion/exclusion | Not inferred in these three workloads | No dedicated eviction/inclusion experiment | CPUID L3 EDX=0x6: inclusive-lower-levels=1; L2 flag=0 | [CPUID](system/cpuid_leaf4.csv); [Intel Table 1-3, p. 1-5 / PDF p. 23](https://cdrdv2-public.intel.com/774990/architecture-instruction-set-extensions-programming-reference.pdf#page=23) | L3 inclusion is system-reported only. L2 non-inclusion does not establish exclusivity |

## Disagreements and limits

**LLC:** The PMU run shows the first measured LLC-miss increase at 6→7 MiB, whereas the older timing-only run showed a much larger 7→8 MiB jump (8 MiB median about 114 ticks/load, now 35.22). The new points have mixed residency, not almost-every-load LLC misses. This partly corroborates sensitivity in the same neighborhood but does not reproduce the earlier curve or measure the 12 MiB physical capacity. Shared-machine occupancy, streaming timing-result stores, replacement, and mapping are possible contributors; their individual causes were not isolated. Neither the freeze nor these runs establishes a physical upper bound of 8 MiB.

**L2 associativity:** The original automatic selector labels the first strong latency edge, which can be caused by L1. At 16 KiB address spacing the PMU explicitly identifies the eight-address edge as L1. Under a simple index model, this spacing visits four of the 1,024 L2 sets, so sixteen resident lines can be consistent with four ways in each set. The 32/64 KiB controls help distinguish later L2 behavior, but L1 can still serve accesses even when they have been displaced from L2. This is an explanation conditioned on system geometry, not an independent derivation of four ways or a proof of the index/replacement function.

**Line/stride:** At 64 B, sequential/random-window/fully-random traversal produces 37.25/324.57/998.78 L1 misses and medians 9.80/12.01/17.75. Traversal order is therefore a major variable. Random-window misses continue rising at 96 B (479.89), contradicting a strict plateau above 64 B. Spatial reuse and prefetching are plausible contributors; prefetchers were not disabled. The footprint also approaches L2 capacity, and its L2 miss counts depend on order. Report the 64 B result as a compatible candidate with these qualifications.

**Timing and interference:** Core frequency was not fixed or inferred from TSC ticks, and -O0 helper/loop costs are retained. Capacity/line_size/associativity logged 153/308/64 involuntary switches, zero measurement page faults, and maximum measured SMT-sibling activity of 1.37%/1.00%/0.76%. Largest temporal-block median max/min ratios were 1.1042/1.0631/1.0706. These checks bound observed variation; they do not establish an uncontended LLC or memory controller. All distributions and outliers remain in the data.

## Reproducibility and checks

The three data directories retain effective configs, commands, environment, raw compressed timing arrays, raw PMU JSON, source snapshots, locally built binaries, disassembly and functional-check logs. Analyses reopen all raw arrays, verify lengths/hashes, recompute statistics, check actual load denominators and reject multiplexed groups. The final [verification record](verification.json) reports all 44 million samples validated and all archived source/binary hashes matched. Six capacity checks and five shared line_size/associativity checks passed, including live short PMU tests on Upgrade. The complete successful sequence is preserved in [run_sequence.py](run_sequence.py); it refuses existing run IDs, so edit the IDs before another collection.

Example commands from `PMU-verification/` (choose new IDs before collection):

```bash
export PATH="/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:/home/swu35/ECE592-HW1/timing-only/capacity/.venv/native/root/usr/bin:$PATH"
MACHINE=upgrade make -C capacity check
python3 capacity/scripts/run_capacity.py --machine upgrade --run-id capacity03
python3 capacity/scripts/analyze_capacity.py --machine upgrade --run-id capacity03
python3 line_size/scripts/run_line_size.py --machine upgrade --run-id line_size02
python3 line_size/scripts/analyze_line_size.py --machine upgrade --run-id line_size02
python3 associativity/scripts/run_associativity.py --machine upgrade --run-id associativity02
python3 associativity/scripts/analyze_associativity.py --machine upgrade --run-id associativity02
```

The first capacity attempt (`capacity01`) failed before measurement with `MADV_COLLAPSE: Cannot allocate memory`. Its [manifest](../../capacity/data/upgrade/capacity01/manifest.json) and logs remain intact. A bounded process-private 1 GiB allocation was touched and freed before retrying; [memory-preparation.json](memory-preparation.json) records this action. `capacity02` then completed with the same workload and full verified THP backing. No PMU permissions, kernel parameters, governor, or other host-wide setting was changed. The local `perf` warnings about unavailable tracing-event files did not prevent the selected hardware counters from being probed and counted.
