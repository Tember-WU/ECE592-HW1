# Skylark AMD PMU discovery

The event definitions below were verified against the saved local `perf list --details`.
All four core events run together per thread in user mode. A short probe establishes access, not cache semantics.

| Event | Raw config | Interpretation |
|---|---|---|
| `ls_mab_alloc.loads` | `0x0141` | Load miss-address-buffer allocations; request/allocation evidence, not retired-load misses. |
| `l2_cache_req_stat.ls_rd_blk_c` | `0x0864` | Core-to-L2 data-cache request misses, all types, excluding L2 prefetch. Includes more than retired demand loads. |
| `ls_refills_from_sys.ls_mabresp_lcl_dram` | `0x0843` | Demand data-cache fills from DRAM or IO on this thread die. Indirect beyond-cache evidence, not a direct L3 miss count. |
| `ls_dispatch.ld_dispatch` | `0x0129` | Dispatched load operations including helper/stack work and speculative activity; not retired loads. |

The third core event is **local DRAM/IO demand fills**, not a direct L3 miss event.
Direct L3 events belong to the shared `amd_l3` PMU. The separate user-only and all-mode probes preserve their errors; they are not silently replaced by Intel events.
Intel `mem_load_retired.l1_miss` was also probed to document nonportability.

| Probe | Usable |
|---|---|
| `ls_mab_alloc.loads` | True |
| `l2_cache_req_stat.ls_rd_blk_c` | True |
| `ls_refills_from_sys.ls_mabresp_lcl_dram` | True |
| `ls_dispatch.ld_dispatch` | True |
| `ls_refills_from_sys.ls_mabresp_lcl_l2` | True |
| `ls_refills_from_sys.ls_mabresp_lcl_cache` | True |
| `ls_refills_from_sys.ls_mabresp_rmt_dram` | True |
| `ls_l1_d_tlb_miss.all` | True |
| `ls_dc_accesses` | True |
| `l3_comb_clstr_state.request_miss` | False |
| `l3_lookup_state.all_l3_req_typs` | False |
| `mem_load_retired.l1_miss` | False |
| `user_core_group` | True |
| `l3_system_user` | False |
| `l3_system_all_modes` | False |

No host settings were changed. Full listings, exact commands, and errors are retained in the matching data directory.
