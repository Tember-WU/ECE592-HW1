# crux cache-event inventory

Descriptions and encodings come from this host's archived `perf list --details`.
A listed event is not necessarily usable. Selected probes count a short `/usr/bin/true` process;
they test access/scheduling, not cache behavior. Formal capacity measurements are separate.

| Event | Local meaning | Probe result |
|---|---|---|
| `mem_load_retired.l1_hit` | Retired load instructions with L1 cache hits as data sources Supports address when precise (Precise event) | counted in user mode |
| `mem_load_retired.l1_miss` | Retired load instructions missed L1 cache as data sources Supports address when precise (Precise event) | counted in user mode |
| `mem_load_retired.l2_hit` | Retired load instructions with L2 cache hits as data sources Supports address when precise (Precise event) | counted in user mode |
| `mem_load_retired.l2_miss` | Retired load instructions missed L2 cache as data sources Supports address when precise (Precise event) | counted in user mode |
| `mem_load_retired.l3_hit` | Retired load instructions with L3 cache hits as data sources Supports address when precise (Precise event) | counted in user mode |
| `mem_load_retired.l3_miss` | Retired load instructions missed L3 cache as data sources Supports address when precise (Precise event) | counted in user mode |
| `mem_load_retired.fb_hit` | Retired load instructions which data sources were load missed L1 but hit FB due to preceding miss to the same cache line with data not ready Supports address when precise (Precise event) | counted in user mode |
| `mem_inst_retired.all_loads` | Retired load instructions Supports address when precise (Precise event) | counted in user mode |
| `l1d.replacement` | L1D data line replacements | counted in user mode |
| `l2_rqsts.all_demand_data_rd` | Demand Data Read requests | counted in user mode |
| `l2_rqsts.demand_data_rd_miss` | Demand Data Read miss L2, no rejects | counted in user mode |
| `l2_rqsts.references` | All L2 requests | counted in user mode |
| `l2_rqsts.miss` | All requests that miss L2 cache | counted in user mode |
| `dtlb_load_misses.walk_completed` | Load miss in all TLB levels causes a page walk that completes. (All page sizes) | counted in user mode |
| `cache-references` | Generic Linux hardware alias; do not assume a specific cache level. | counted in user mode |
| `cache-misses` | Generic Linux hardware alias; do not assume a specific cache level. | counted in user mode |

The capacity run groups the three `mem_load_retired.*_miss` events with
`mem_inst_retired.all_loads`, all user mode and per thread. The group probe result is: **counted in user mode**.
Raw encodings are specific to this CPU and must be rediscovered on other machines.

Miss counts are normalized per known pointer-chase load. The counters also see user-space
loop/timer-helper loads within the measured loop. `all_loads` documents that overhead;
it is not identical to the number of pointer-chase loads. Do not interpret an L3 miss as
proof of local DRAM service, or a generic `cache-misses` count as an L1 miss count.

See `events.csv` for all parsed cache/virtual-memory events, including unprobed ones.
The complete unfiltered listings and individual probe commands/output are under the matching `data/` run.
