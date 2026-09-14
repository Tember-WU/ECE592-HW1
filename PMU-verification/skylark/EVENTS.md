# Skylark event groups

Definitions and raw encodings were checked against local perf before every run. Group A and B use identical workload parameters and binaries, with one million samples per point in each group. They are separate runs, not simultaneous per-load classifications.

| Group | Local perf event | Raw config | Meaning |
|---|---|---|---|
| A | `ls_mab_alloc.loads` | `0x0141` | Load miss-address-buffer allocations; request/allocation evidence, not retired-load misses. |
| A | `l2_cache_req_stat.ls_rd_blk_c` | `0x0864` | Core-to-L2 data-cache request misses, all types, excluding L2 prefetch. Includes more than retired demand loads. |
| A | `ls_refills_from_sys.ls_mabresp_lcl_dram` | `0x0843` | Demand data-cache fills from DRAM or IO on this thread die. Indirect beyond-cache evidence, not a direct L3 miss count. |
| A | `ls_dispatch.ld_dispatch` | `0x0129` | Dispatched load operations including helper/stack work and speculative activity; not retired loads. |
| B | `ls_refills_from_sys.ls_mabresp_lcl_l2` | `0x0143` | Demand data-cache fills satisfied by local L2; L1 refill evidence rather than a retired L1 miss count. |
| B | `ls_refills_from_sys.ls_mabresp_lcl_cache` | `0x0243` | Demand fills from a local CCX cache excluding local L2, or remote CCX with address home on this die; not a pure L3-hit count. |
| B | `l2_request_g1.rd_blk_l` | `0x8060` | Data cache reads received by L2, including hardware and software prefetch; not a retired-load miss event. |
| B | `ls_l1_d_tlb_miss.all` | `0xff45` | All L1 data-TLB misses or reloads; translation-control evidence, not necessarily page walks. |

Group A MAB allocations did not follow the L1 timing transition. Preserve that disagreement; use the supplemental refill evidence to assess the L1 boundary. No undocumented erratum or precise cause is asserted.

The `amd_l3` per-thread and system probes returned `<not supported>` under this kernel/perf/account configuration. The local DRAM/IO event is an indirect beyond-cache measure, not direct L3 misses. Group A and B totals must not be subtracted or summed into exact hit/miss probabilities.

Discovery02 contains the corrected raw event modifier syntax. Discovery01 is retained as an earlier availability attempt and contains invalid syntax in its two raw system-L3 probes. Hardware listing stderr warns about inaccessible tracefs; those tracepoint warnings do not invalidate the independently successful core hardware groups.

See [local inventory](../events/results/skylark/discovery02/EVENTS.md), [all relevant local events](../events/results/skylark/discovery02/events.csv), [supplemental group probe](refills-group-probe.txt), and each formal run's `selected-events.txt`.
