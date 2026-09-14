# Section 8.4 generated analysis

Primary contributor: Preet Patel

Mode: SMOKE TEST; not submission data
Missing ECE hosts: artemisia, crux, ookay, skylark, sunbird, thunderbird, upgrade

Counts are divided by the exact number of dependent pointer loads, then multiplied by 1,000. Timing samples are batches divided by batch length; they are not individually timed loads. Counter passes omit timers and sample-buffer writes. Initialization and two full warm-up traversals are excluded. Remaining user-space call/loop overhead is included; no baseline subtraction or multiplex scaling is applied.

See docs/generic_mapping_review.md for upstream mappings (including cache-level differences under identical generic names). Ranks compare the configured event slots numerically, NOT necessarily identical physical phenomena. Read event_semantics.csv before interpreting any ordering. Same generic event spelling does not establish equivalent PMU semantics. Error bars are min/max across repeated counter passes, not confidence intervals. No ratio is called a hit/miss probability because numerator/denominator semantics may differ.

Intel retired-load proxies differ from AMD dispatch/MAB/refill proxies and Arm speculative/refill events. AMD local-DRAM fills exclude remote service. Thunderbird 0x36/0x37 have not been validated as SLC accesses/misses by section 8.3. LLC-sized means capacity-relative working set, not proof of LLC residency. Base-page TLB pressure, shared cache contention, prefetching, NUMA, and cache organization can change results.

## Compact ranked tables

### l1_resident

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | charnwood: 3.023 |
| cache_misses | charnwood: 0 |
| l1_loads | charnwood: 1000 |
| l1_misses | charnwood: 1.859 |
| stores_or_replacements | charnwood: 0.1094 |
| llc_loads | charnwood: 0.5078 |
| llc_misses | charnwood: 0 |
| dtlb_misses | charnwood: 0 |

### llc_sized

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | charnwood: 3041 |
| cache_misses | charnwood: 1136 |
| l1_loads | charnwood: 990.2 |
| l1_misses | charnwood: 1177 |
| stores_or_replacements | charnwood: 0.1094 |
| llc_loads | charnwood: 1018 |
| llc_misses | charnwood: 361.7 |
| dtlb_misses | charnwood: 259.3 |

### beyond_llc

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | charnwood: 3351 |
| cache_misses | charnwood: 2680 |
| l1_loads | charnwood: 996.7 |
| l1_misses | charnwood: 1664 |
| stores_or_replacements | charnwood: 0.1094 |
| llc_loads | charnwood: 1221 |
| llc_misses | charnwood: 958.8 |
| dtlb_misses | charnwood: 816.1 |

## Interpretation to finish after collecting all hosts

- Describe whether each workload produced the intended L1/deeper-cache/above-LLC behavior using normalized counters and timing distributions.
- For each architecture-specific proxy, cite the copied event inventory and explain exactly which rankings permit a comparison and which are only descriptive.
- Compare older/newer Intel systems within semantically matched event definitions, then discuss AMD and Arm separately. Launch year alone does not control server/desktop class, cache domain, memory or process differences.
- Inspect raw_counts.csv faults/switches and activity logs. Record actual SMT sibling activity/reservation and reasons for noisy reruns; never discard inconvenient observations silently.
- Fill actual contributor identity, repository/Overleaf links and AI disclosure in the overall submission. Include final source listings and docs/methodology.md diagram.
