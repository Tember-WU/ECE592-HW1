# Artemisia section 8.4 run notes

Collection completed with the default full protocol: three repetitions, one million timed batches of 64 dependent loads per workload/repetition; 9,000,000 timing samples and 72 separate event passes. Every PMU pass had positive, equal enabled/running time; no multiplex scaling. No measured interval recorded a major page fault.

CPU 0 / physical core 0 / socket 0; SMT sibling 56. First-touch allocation after pinning; base pages. This session could not use CPU 32 because it was outside the allowed affinity. No exclusive reservation or idle-sibling claim is made. Activity and context-switch records are retained.

| Workload | Footprint | Median of three timing medians (TSC ticks/access) | Generic LLC misses / 1,000 chain loads |
|---|---:|---:|---:|
| l1_resident | 0.0234375 MiB | 6.0000 | 0.0003 |
| llc_sized | 52.5 MiB | 283.5938 | 999.9783 |
| beyond_llc | 210 MiB | 293.1875 | 999.9898 |

The 52.5 MiB LLC-sized working set generated approximately one generic LLC miss per chain access, and its timing was close to the 210 MiB workload. It is therefore **not evidence of an isolated LLC-hit latency**. This run uses the documented sharing-domain capacity as the workload size, not a tuned residency footprint. Base-page translation traffic, effective cache availability/organization and contention may contribute; these data alone do not identify the cause. The 8.4 workload definition remains explicit and unchanged.

Timing means and standard deviations show large upper tails relative to the medians. All samples and Tukey outliers are preserved. Use the distributions and context-switch/activity records in the discussion; do not label the run uncontended or discard large delays without a documented rule.

The other seven ECE hosts are still missing. The single-host rank plots are local pipeline checks; run the same protocol there and generate the combined ranked panels/tables before claiming completion of the cross-generation comparison.

The saved benchmark source matches the final src/bench.cpp. Collection used the runner archived at start; subsequent runner changes enforce a fresh -O0 build and execute the snapshotted binary, and fix Thunderbird SLC/alias handling. Those changes do not alter this Intel workload. The exact final analyzer is saved with hashes under analysis/.

Primary contributor: Preet Patel — fill actual name/account before submission. AI assistance: Codex generated/modified the suite, tests, plotting, and documentation; the team must review and understand the code and disclose this assistance in the project appendix.
