# Section 8.4 generated analysis

Primary contributor: Preet Patel

Mode: full collection
Missing ECE hosts: artemisia, charnwood, crux, ookay, sunbird, thunderbird, upgrade

Counts are divided by the exact number of dependent pointer loads, then multiplied by 1,000. Timing samples are batches divided by batch length; they are not individually timed loads. Counter passes omit timers and sample-buffer writes. Initialization and two full warm-up traversals are excluded. Remaining user-space call/loop overhead is included; no baseline subtraction or multiplex scaling is applied.

See docs/generic_mapping_review.md for upstream mappings (including cache-level differences under identical generic names). Ranks compare the configured event slots numerically, NOT necessarily identical physical phenomena. Read event_semantics.csv before interpreting any ordering. Same generic event spelling does not establish equivalent PMU semantics. Error bars are min/max across repeated counter passes, not confidence intervals. No ratio is called a hit/miss probability because numerator/denominator semantics may differ.

Intel retired-load proxies differ from AMD dispatch/MAB/refill proxies and Arm speculative/refill events. AMD local-DRAM fills exclude remote service. Thunderbird 0x36/0x37 have not been validated as SLC accesses/misses by section 8.3. LLC-sized means capacity-relative working set, not proof of LLC residency. Base-page TLB pressure, shared cache contention, prefetching, NUMA, and cache organization can change results.

## Compact ranked tables

### l1_resident

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | skylark: 0.03317 |
| cache_misses | skylark: 0.0007187 |
| l1_loads | skylark: 1000 |
| l1_misses | skylark: 0.03042 |
| stores_or_replacements | skylark: 0.02522 |
| llc_loads | skylark: 0.0002656 |
| llc_misses | skylark: 0 |
| dtlb_misses | skylark: 6.25e-05 |

### llc_sized

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | skylark: 2384 |
| cache_misses | skylark: 1026 |
| l1_loads | skylark: 1508 |
| l1_misses | skylark: 1034 |
| stores_or_replacements | skylark: 14.44 |
| llc_loads | skylark: 775.5 |
| llc_misses | skylark: 270.6 |
| dtlb_misses | skylark: 508.6 |

### beyond_llc

| Event slot | Ascending machines: median events / 1,000 accesses |
|---|---|
| cache_references | skylark: 2955 |
| cache_misses | skylark: 1180 |
| l1_loads | skylark: 1881 |
| l1_misses | skylark: 1008 |
| stores_or_replacements | skylark: 3.023 |
| llc_loads | skylark: 123 |
| llc_misses | skylark: 873.2 |
| dtlb_misses | skylark: 879.5 |

## Interpretation to finish after collecting all hosts

- Describe whether each workload produced the intended L1/deeper-cache/above-LLC behavior using normalized counters and timing distributions.
- For each architecture-specific proxy, cite the copied event inventory and explain exactly which rankings permit a comparison and which are only descriptive.
- Compare older/newer Intel systems within semantically matched event definitions, then discuss AMD and Arm separately. Launch year alone does not control server/desktop class, cache domain, memory or process differences.
- Inspect raw_counts.csv faults/switches and activity logs. Record actual SMT sibling activity/reservation and reasons for noisy reruns; never discard inconvenient observations silently.
- Fill actual contributor identity, repository/Overleaf links and AI disclosure in the overall submission. Include final source listings and docs/methodology.md diagram.
