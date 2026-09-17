# Section 8.4 generated analysis

Primary contributor: Preet Patel, UNASSIGNED

Mode: full collection
Missing ECE hosts: charnwood, crux, ookay, thunderbird, upgrade

Counts are divided by the exact number of dependent pointer loads, then multiplied by 1,000. Timing samples are batches divided by batch length; they are not individually timed loads. Counter passes omit timers and sample-buffer writes. Initialization and two full warm-up traversals are excluded. Remaining user-space call/loop overhead is included; no baseline subtraction or multiplex scaling is applied.

See docs/generic_mapping_review.md for upstream mappings (including cache-level differences under identical generic names). Ranks compare the configured event slots numerically, NOT necessarily identical physical phenomena. Read event_semantics.csv before interpreting any ordering. Same generic event spelling does not establish equivalent PMU semantics. Error bars are min/max across repeated counter passes, not confidence intervals. No ratio is called a hit/miss probability because numerator/denominator semantics may differ.

Intel retired-load proxies differ from AMD dispatch/MAB/refill proxies and Arm speculative/refill events. AMD local-DRAM fills exclude remote service. Thunderbird 0x36/0x37 have not been validated as SLC accesses/misses by section 8.3. LLC-sized means capacity-relative working set, not proof of LLC residency. Base-page TLB pressure, shared cache contention, prefetching, NUMA, and cache organization can change results.

## Compact ranked tables

### l1_resident

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | artemisia: 0.0008281 → skylark: 0.03317 → sunbird: 0.08166 |
| cache_misses | sunbird: 0 → artemisia: 0.0005469 → skylark: 0.0007187 |
| l1_loads | sunbird: 999.9 → artemisia: 1000 → skylark: 1000 |
| l1_misses | skylark: 0.03042 → artemisia: 0.1638 → sunbird: 0.8366 |
| stores_or_replacements | artemisia: 0.000125 → sunbird: 0.000125 → skylark: 0.02522 |
| llc_loads | artemisia: 0.0002656 → skylark: 0.0002656 → sunbird: 0.1211 |
| llc_misses | skylark: 0 → sunbird: 0 → artemisia: 0.00025 |
| dtlb_misses | skylark: 6.25e-05 → artemisia: 7.813e-05 → sunbird: 0.001406 |

### llc_sized

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | artemisia: 1000 → sunbird: 1110 → skylark: 2384 |
| cache_misses | sunbird: 439.3 → artemisia: 999.9 → skylark: 1026 |
| l1_loads | sunbird: 919.1 → artemisia: 1000 → skylark: 1508 |
| l1_misses | skylark: 1034 → sunbird: 1707 → artemisia: 1730 |
| stores_or_replacements | artemisia: 0.000125 → sunbird: 0.000125 → skylark: 14.44 |
| llc_loads | skylark: 775.5 → artemisia: 1000 → sunbird: 1104 |
| llc_misses | skylark: 270.6 → sunbird: 404.7 → artemisia: 1000 |
| dtlb_misses | skylark: 508.6 → artemisia: 870.7 → sunbird: 871.7 |

### beyond_llc

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | artemisia: 1022 → sunbird: 1597 → skylark: 2955 |
| cache_misses | artemisia: 1000 → sunbird: 1000 → skylark: 1180 |
| l1_loads | sunbird: 933.3 → artemisia: 1000 → skylark: 1881 |
| l1_misses | skylark: 1008 → sunbird: 1923 → artemisia: 1925 |
| stores_or_replacements | artemisia: 0.000125 → sunbird: 0.000125 → skylark: 3.023 |
| llc_loads | skylark: 123 → artemisia: 1020 → sunbird: 1609 |
| llc_misses | skylark: 873.2 → artemisia: 1000 → sunbird: 1000 |
| dtlb_misses | skylark: 879.5 → artemisia: 968.2 → sunbird: 971.1 |

## Interpretation to finish after collecting all hosts

- Describe whether each workload produced the intended L1/deeper-cache/above-LLC behavior using normalized counters and timing distributions.
- For each architecture-specific proxy, cite the copied event inventory and explain exactly which rankings permit a comparison and which are only descriptive.
- Compare older/newer Intel systems within semantically matched event definitions, then discuss AMD and Arm separately. Launch year alone does not control server/desktop class, cache domain, memory or process differences.
- Inspect raw_counts.csv faults/switches and activity logs. Record actual SMT sibling activity/reservation and reasons for noisy reruns; never discard inconvenient observations silently.
- Fill actual contributor identity, repository/Overleaf links and AI disclosure in the overall submission. Include final source listings and docs/methodology.md diagram.
