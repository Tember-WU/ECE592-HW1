# Generic names: architecture-specific mapping review

A generic name is an API request, not a portable physical event. The following **upstream Linux v5.14 reference mappings** explain the expected differences; the installed vendor kernel may contain backports. Preserve its version and verify against corresponding vendor sources before claiming exact equivalence. Raw fallback names/encodings instead come from the supplied host inventories.

| Generic name | Intel Haswell / Skylake family reference | AMD family 17h reference | Arm PMUv3 base mapping |
|---|---|---|---|
| cache-references | Architectural LLC references | L2 requests, `0xff60` | L1D accesses |
| cache-misses | Architectural LLC misses | L2 misses, `0x0964` | L1D refills |
| L1-dcache-loads | Retired load uops (Haswell) or instructions (Skylake), `0x81d0` | Data-cache accesses, `0x0040`, includes writes | L1D accesses, may include writes |
| L1-dcache-load-misses | L1D replacements, `0x0151`; NOT retired-load misses | L2 accesses from DC misses, `0xc860` | L1D refills |
| L1-dcache-stores | Retired stores, `0x82d0` | Unsupported; use documented refill proxy | Base mapping unsupported; use write-event fallback |
| LLC-loads | Filtered offcore responses | Unsupported; use local-cache-fill proxy | LL_CACHE_RD, firmware dependent |
| LLC-load-misses | Filtered offcore responses | Unsupported; use local-DRAM/IO-fill proxy | LL_CACHE_MISS_RD, firmware dependent |
| dTLB-load-misses | Completed demand load page walks | L2 TLB misses / walks, `0xf045` | L1D TLB refills |

Arm CPU-specific overrides can select read-only variants, so a successful generic probe does not resolve that distinction. N1's archived local definitions and the existing SLC diagnostic remain necessary. Sapphire Rapids requires its vendor-kernel mapping review rather than assuming the older Intel table applies unchanged. Generic cache references and misses may overlap other slots; exactly eight configured events does not mean eight disjoint populations.

Primary code sources:

- [Intel driver and mapping tables](https://raw.githubusercontent.com/torvalds/linux/v5.14/arch/x86/events/intel/core.c), `hsw_hw_cache_event_ids`, `skl_hw_cache_event_ids` and extra-response filters.
- [AMD driver and mapping tables](https://raw.githubusercontent.com/torvalds/linux/v5.14/arch/x86/events/amd/core.c), `amd_hw_cache_event_ids_f17h`, `amd_f17h_perfmon_event_map`.
- [Arm64 PMUv3 driver](https://raw.githubusercontent.com/torvalds/linux/v5.14/arch/arm64/kernel/perf_event.c), `armv8_pmuv3_perf_map` and `armv8_pmuv3_perf_cache_map`.

Consulted 2026-09-14. This reference table does not claim that remote runtime mappings have been independently checked in the current session. In the final paper, describe unsupported proxies under their actual meaning, and qualify comparisons whose vendor-kernel mappings remain unresolved.
