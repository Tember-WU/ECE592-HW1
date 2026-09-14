# Thunderbird PMU discovery

Machine: thunderbird.ece.ncsu.edu, AArch64 / Neoverse N1 (Ampere Altra). Discovery followed the Phase-I SHA-256 freeze at `preflight/thunderbird/phase1_freeze.json`.

Full `perf list` / `perf list --details`, stderr, sysfs PMU inventory, raw encoding verification, and successful four-event probes on CPUs 4 and 32 are archived in `events/data/thunderbird/discovery01/`. `events.csv` enumerates core events and distinguishes listed events from the four actually probed/collected. Core PMU `armv8_pmuv3_0` has dynamic type 10; Linux `PERF_TYPE_RAW` also opens this core PMU successfully in the native smoke tests. DSU, CMN and DMC PMUs are separately enumerated; their mere presence does not establish access permission or per-thread attribution.

| Selected core event | Raw config | Meaning and limitation |
|---|---:|---|
| `l1d_cache_refill_rd` | `0x42` | L1D line allocations caused by speculative load misses; not retired-load misses. |
| `l2d_cache_refill_rd` | `0x52` | Cacheable reads that fetch from outside the CPU; includes store-miss read allocation. |
| `ll_cache_miss_rd` | `0x37` | With EXTLLC enabled, reads returned from outside the core/cluster whose source is not CMN SLC; may include other caches and remote sources, not only DRAM. |
| `ld_spec` | `0x70` | Speculatively executed loads, including helper/stack traffic; diagnostic only. |

Semantics: [Arm Neoverse N1 PMU Guide, Issue 2.0, pp. 33, 38, 40–44, 52](https://documentation-service.arm.com/static/66ace6ee0469d5197d40c93e). Nonzero `0x37` counts and workload response are observed; the privileged EXTLLC register was not read or changed. Core `l3d_cache_refill` (`0x2a`) describes a DSU/cluster boundary and must not be substituted for SLC misses.

Other locally listed events include `l1d_cache` (0x04), `l2d_cache` (0x16), `ll_cache_rd` (0x36), `l1d_tlb_refill` (0x05), `dtlb_walk` (0x34), and `inst_retired` (0x08); these are not collected in this four-event run. This follows the original Artemisia representative experiment flow, with four simultaneous platform-appropriate events.

All measured events are grouped, pinned, per-thread, user mode, excluding kernel/hypervisor/guest. Warm-up, allocation and file output lie outside the count interval. The entire sample loop lies inside it, including output-buffer stores and associativity preparation. Normalization uses analytically known chain loads, not `ld_spec` as a denominator. A group is rejected unless `time_running == time_enabled > 0`; no multiplex scaling is used.

`perf_event_paranoid=2` permits these user counters. `perf list` warns about inaccessible tracing events; no tracepoints are needed. The installed perf is 5.14.0-687.17.1.el9_8, while the running kernel is 5.14.0-611.54.1.el9_7. A command with multiple positional event-name filters terminated with SIGSEGV during preflight; the new workflow uses the complete inventory and validates encodings in Python. Explicit core PMU qualifiers in probes avoid regrouping ambiguous core/DSU aliases. No permission or system configuration was changed.

**Observed SLC limitation:** the primary capacity run shows `0x37` closely tracking L2 refills, including at 2 MiB, and remaining flat across 32–64 MiB. The separate `capacity/ll_diagnostic01` run therefore collects `ll_cache_rd` (0x36), `ll_cache_miss_rd` (0x37), `l3d_cache_refill` (0x2a), and `l2d_cache_refill_rd` (0x52), on the same 2 MiB and 64 MiB Phase-I workloads with one million batches each. In this session the first three counts are nearly equal at both sizes. Do not interpret `0x37` as independently verified SLC misses on this host. The cause in firmware/configuration/data-source reporting has not been established.

CMN `hnf_cache_miss` is listed in sysfs (`type=0x5,eventid=0x1`, PMU type 51). Perf probes returned `<not supported>` with user filtering. A direct, disabled `perf_event_open` probe with no user/kernel filtering returned `EACCES` (13), confirming that this account cannot open the required system-wide CMN event. See `cmn-*-probe.json` and `preflight/thunderbird/probe_cmn.c`. No CMN counts were fabricated or substituted.
