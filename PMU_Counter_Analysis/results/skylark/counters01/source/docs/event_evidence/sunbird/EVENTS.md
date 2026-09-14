# sunbird cache-event inventory

Descriptions and encodings come from this host's archived `perf list --details`.
A listed event is not necessarily usable. Selected probes count a short `/usr/bin/true` process;
they test access/scheduling, not cache behavior. Formal capacity measurements are separate.

| Event | Local meaning | Probe result |
|---|---|---|
| `mem_load_uops_retired.l1_hit` | Retired load uops with L1 cache hits as data sources Supports address when precise. Spec update: HSD29,HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_load_uops_retired.l1_miss` | Retired load uops misses in L1 cache as data sources Supports address when precise. Spec update: HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_load_uops_retired.l2_hit` | Retired load uops with L2 cache hits as data sources Supports address when precise. Spec update: HSD76,HSD29,HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_load_uops_retired.l2_miss` | Miss in mid-level (L2) cache. Excludes Unknown data-source Supports address when precise. Spec update: HSD29,HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_load_uops_retired.l3_hit` | Retired load uops which data sources were data hits in L3 without snoops required Supports address when precise. Spec update: HSD74, HSD29,HSD25,HSM26,HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_load_uops_retired.l3_miss` | Miss in last-level (L3) cache. Excludes Unknown data-source Supports address when precise. Spec update: HSD74,HSD29,HSD25,HSM26,HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_load_uops_retired.hit_lfb` | Retired load uops which data sources were load uops missed L1 but hit FB due to preceding miss to the same cache line with data not ready Supports address when precise. Spec update: HSM30 (Precise event). Unit: cpu | counted in user mode |
| `mem_uops_retired.all_loads` | Retired load uops Supports address when precise. Spec update: HSD29, HSM30 (Precise event). Unit: cpu | counted in user mode |
| `l1d.replacement` | L1D data line replacements. Unit: cpu | counted in user mode |
| `l2_rqsts.all_demand_data_rd` | Demand Data Read requests Spec update: HSD78,HSM80. Unit: cpu | counted in user mode |
| `l2_rqsts.demand_data_rd_miss` | Demand Data Read miss L2,no rejects Spec update: HSD78,HSM80. Unit: cpu | counted in user mode |
| `l2_rqsts.references` | All L2 requests Spec update: HSD78,HSM80. Unit: cpu | counted in user mode |
| `l2_rqsts.miss` | All requests that miss L2 cache Spec update: HSD78,HSM80. Unit: cpu | counted in user mode |
| `dtlb_load_misses.walk_completed` | Demand load Miss in all translation lookaside buffer (TLB) levels causes a page walk that completes of any page size. Unit: cpu | counted in user mode |
| `cache-references` | Generic Linux hardware alias; do not assume a specific cache level. | counted in user mode |
| `cache-misses` | Generic Linux hardware alias; do not assume a specific cache level. | counted in user mode |

The verification group is `mem_load_uops_retired.l1_miss`, `mem_load_uops_retired.l2_miss`, `mem_load_uops_retired.l3_miss`, `mem_uops_retired.all_loads`.
All events count user mode per thread. The group probe result is: **failed; see raw log**.
Raw encodings are specific to this CPU and must be rediscovered on other machines.

Miss counts are normalized per known pointer-chase load. The counters also see user-space
loop/timer-helper loads within the measured loop. `all_loads` documents that overhead;
it is not identical to the number of pointer-chase loads. Do not interpret an L3 miss as
proof of local DRAM service, or a generic `cache-misses` count as an L1 miss count.

See `events.csv` for all parsed cache/virtual-memory events, including unprobed ones.
The complete unfiltered listings and individual probe commands/output are under the matching `data/` run.

## Scheduling resolution for the formal Sunbird run

The archived discovery result remains a failed **four-event group** probe (16 individual
probes passed, one group failed). Additional [group probes](../../../data/sunbird/group-probes01/probes.json)
found that three miss events also cannot be scheduled together. Two pairs were usable:

| Pass | Local events | Raw configs |
|---|---|---|
| `l1_l2` | `mem_load_uops_retired.l1_miss`, `mem_load_uops_retired.l2_miss` | `0x08d1`, `0x10d1` |
| `l3_loads` | `mem_load_uops_retired.l3_miss`, `mem_uops_retired.all_loads` | `0x20d1`, `0x81d0` |

Both pairs passed short `perf stat` diagnostics at 100% running time and direct pinned
`perf_event_open` smoke tests in all three measurement kernels. The formal collectors
repeat the identical workload once per pair and reject any group with unequal enabled
and running times. Each pass has its own one-million-batch raw timing distribution.
Events from different passes are not simultaneous observations. The scheduling failure's
underlying resource cause was not established.

`perf list` also reports permission denied for the tracing-events directory. It exits
successfully and lists the hardware events; tracepoint access is restricted. User-mode
hardware counter access works at the unchanged `perf_event_paranoid=2` setting.
The local perf descriptions include errata references, retained above; these counts
should be interpreted as transition evidence, not an exact miss probability.
