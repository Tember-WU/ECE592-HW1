# Ookay system and reference evidence

These values were read after the [Phase-I freeze](../phase1-freeze01/manifest.json).
`sysfs-cache-organization.json` records the acquisition timestamp, CPU identity, exact sysfs
paths and values for experiment CPUs 2 and 4. Sizes, ways, sets and sharing in the comparison
table come from this local evidence; they were not used to rewrite the frozen inferences.

`read_cpuid.c` queries deterministic cache leaf 4 with each subleaf until cache type is zero.
The preserved output is `cpuid-leaf4.json`; the helper was compiled locally and executed
with `taskset -c 3`. To reproduce after the timing-only phase:

```bash
gcc -O2 -std=c11 read_cpuid.c -o /tmp/ookay-read-cpuid
taskset -c 3 /tmp/ookay-read-cpuid
```

The raw registers are retained. L3 EDX is 6: bit 1 indicates inclusiveness and bit 2 reports
complex cache indexing. Decode definitions: Intel, *Architecture Instruction Set Extensions
and Future Features Programming Reference*, December 2022, ref. 319433-047,
[Table 1-3, printed p.1-5 (PDF page 23)](https://cdrdv2-public.intel.com/671368/architecture-instruction-set-extensions-programming-reference.pdf).

External references accessed on 2026-09-14:

- [Intel i7-7700 specifications](https://www.intel.com/content/www/us/en/products/sku/97128/intel-core-i77700-processor-8m-cache-up-to-4-20-ghz/specifications.html), product identification and Cache fields.
- [Agner Fog, The microarchitecture of Intel, AMD, and VIA CPUs](https://www.agner.org/optimize/microarchitecture.pdf), 2026-05-23 revision; p.152 establishes chapter coverage and p.160 §11.12 Table 11.2 supplies the family reference used in the report. Its table was visually checked. Family ranges are not substituted for the exact local SKU geometry.

The external PDFs are not copied into this repository. Source/page citations and the independent
local CPUID/sysfs capture make clear which evidence supports each comparison.
