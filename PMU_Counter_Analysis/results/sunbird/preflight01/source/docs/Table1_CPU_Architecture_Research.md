# Table 1 — Architecture and Microarchitecture of the Eight ECE Lab Systems

**Project:** *Predicting Cache Evolution: The Growing Capacity and Latency Cost of CPU Caching*  
**Research date:** September 5, 2026  
**Scope:** Processor identification, vendor, ISA, processor generation, microarchitecture/codename, generation launch year, and fabrication process. No cache specifications or inferred cache results are included.

> **Provenance.** The host-to-CPU assignments and the explicitly listed dual-processor configurations come from Table 1 on page 3 of the supplied `PROJECT 1.pdf`. The processor taxonomy and historical information below come from the cited manufacturer sources. This document does not independently verify the hardware currently installed on the remote hosts; compare the listed models with the team's saved machine-identification logs before final submission.[^HW]

## 1. Report-ready introduction and year convention

Table 1 summarizes the eight ECE/Ajorpaz lab systems used for the observation phase. Processor vendor, instruction-set architecture, processor generation, and microarchitecture/codename are recorded separately so that an ISA family is not confused with a processor manufacturer or a particular implementation. The table follows the machine assignments in the course handout.[^HW]

**Year convention.** The chronological coordinate is the **first formal public launch year of the processor generation represented by the CPU**, rather than the release date of the individual SKU, the installation year of the machine, or the first announcement of an underlying core IP. Within a named processor generation, the first products establish that generation's year, even when a particular desktop or server SKU arrives later. Preliminary roadmap disclosures and pre-launch demonstrations are not treated as product-generation launches. This convention must also be used for the later Hazel entries and all chronological plots.[^HW]

This choice matters especially for the Core i7-7700 and Core i7-9700: their generation years differ from their individual SKU launch years. The distinction is documented in Section 3 below; the year column does **not** assert that every listed SKU was already available in that year.

## 2. Table 1: ECE lab machines, sorted by generation launch year

**Table 1.** Processor taxonomy of the eight ECE lab systems. Rows are ordered by the processor-generation launch year defined above. The `2 ×` notation is retained only where the assignment explicitly lists two processors. Fabrication entries preserve the manufacturer's terminology; they are not a normalized physical-feature-size scale.

| Generation launch year | Lab host | CPU configuration in the handout | Processor vendor | ISA / architecture | Processor generation / family | Microarchitecture / codename | Fabrication process | Sources |
|---:|---|---|---|---|---|---|---|---|
| 2014 | Sunbird | 2 × Intel Xeon E5-2680 v3 | Intel | x86-64 / Intel 64 | Xeon E5-2600 v3 | Haswell, server implementation | Intel 22 nm | [^I1] [^I2] |
| 2015 | Charnwood | Intel Core i7-6700 | Intel | x86-64 / Intel 64 | 6th Generation Core | Skylake | Intel 14 nm | [^I3] [^I4] |
| 2016 | Ookay | Intel Core i7-7700 | Intel | x86-64 / Intel 64 | 7th Generation Core | Kaby Lake | Intel 14 nm | [^I5] [^I6] |
| 2017 | Upgrade | Intel Core i7-8700 | Intel | x86-64 / Intel 64 | 8th Generation Core, Coffee Lake desktop family | Coffee Lake | Intel 14 nm | [^I7] [^I8] |
| 2018 | Crux | Intel Core i7-9700 | Intel | x86-64 / Intel 64 | 9th Generation Core | Coffee Lake, 9th-generation refresh | Intel 14 nm | [^I9] [^I10] |
| 2019 | Skylark | 2 × AMD EPYC 7532 | AMD | x86-64 / AMD64 | 2nd Generation EPYC, 7002 series | Zen 2 cores; Rome processor codename | 7 nm CPU chiplets; 14 nm I/O die | [^A1] [^A2] [^A3] |
| 2020 | Thunderbird | Ampere Altra Q80-30 | Ampere Computing | AArch64 / 64-bit Arm; Armv8.2+ compatibility | Ampere Altra | Arm Neoverse N1-based | TSMC 7 nm FinFET | [^P1] [^P2] |
| 2023 | Artemisia | 2 × Intel Xeon Gold 5420+ | Intel | x86-64 / Intel 64 | 4th Generation Xeon Scalable | Sapphire Rapids | Intel 7 | [^I11] [^I12] |

**Primary contributor:** [Insert the actual team member's full name and GitHub username.]  
**Checked by:** [Insert the teammate who checked the table and references.]

### Table notes

**Vendor versus ISA.** Thunderbird belongs to the Arm/AArch64 comparison group, but the processor vendor is **Ampere Computing**, not Arm. Ampere identifies Altra as a 64-bit Arm processor based on the Neoverse N1 platform and documents Armv8.2+ compatibility.[^P1] Intel and AMD remain separate vendors even though their listed CPUs belong to the x86-64 ISA family.

**Microarchitecture versus product codename.** For AMD, `Zen 2` identifies the CPU-core architecture and `Rome` identifies the EPYC processor generation. For Ampere, `Altra` is the processor family and `Neoverse N1` identifies the underlying Arm platform/core lineage.[^A3][^P1] The Intel names in the table follow the manufacturers' product-codename fields. In particular, Intel lists both the i7-8700 and i7-9700 under Coffee Lake; “9th-generation refresh” distinguishes Crux's product generation without claiming an entirely unrelated core architecture.[^I7][^I9]

**Process labels.** The Intel entries retain the official `22 nm`, `14 nm`, and `Intel 7` labels. No `14+` or `14++` subdivision is inferred from an ARK entry that says only `14 nm`.[^I1][^I3][^I5][^I7][^I9][^I11] Rome is recorded as a mixed-process design rather than describing every die in the package as 7 nm.[^A3] The process column should not be used by itself to infer a numerical density or performance ratio between vendors.

**Phase-I separation.** Table 1 is an identification and historical-ordering table, not a cache-results table. Cache capacity, ways, sets, line size, hit/miss latency, sharing scope, and inclusion behavior belong to the later experimental sections.[^HW]

## 3. Evidence and chronology notes for each machine

### 3.1 Sunbird — Xeon E5-2680 v3

Intel's product entry identifies the E5-2680 v3 as an E5 v3-family server processor, with Haswell as its codename, 22 nm fabrication, Intel 64 support, and an individual SKU launch in Q3 2014.[^I1] Intel's dated announcement places the E5-2600 v3 product-family launch on September 8, 2014.[^I2] Therefore, the table uses **2014** for this server generation, rather than substituting the earlier history of the broader Haswell core family.

### 3.2 Charnwood — Core i7-6700

Intel identifies the i7-6700 as a 6th Generation Core desktop processor, using Skylake, 14 nm fabrication, and Intel 64; its SKU launch is Q3 2015.[^I3] Intel's 2015 generation announcement independently identifies the 6th Generation Core family with Skylake and 14 nm technology.[^I4] The chronology therefore uses **2015**.

The hostname **Charnwood** refers to this Intel Skylake system. The similarly spelled hostname **Skylark** in the assignment refers to an AMD EPYC system, not to Intel Skylake.[^HW]

### 3.3 Ookay — Core i7-7700

Intel identifies the i7-7700 as a 7th Generation Core desktop processor using Kaby Lake, 14 nm fabrication, and Intel 64. The individual SKU's launch date is **Q1 2017**.[^I5] However, Intel publicly launched the 7th Generation Core family on **August 30, 2016**.[^I6]

Consequently, the table uses **2016**, consistently with the generation-level convention. This is not a claim that the i7-7700 itself launched in 2016. A desktop-subfamily-only convention would instead need to be defined and applied consistently; it should not be mixed silently with the convention used here.

### 3.4 Upgrade — Core i7-8700

Intel's product entry places the i7-8700 in the 8th Generation Core family and identifies Coffee Lake, 14 nm fabrication, Intel 64 support, and a Q4 2017 SKU launch.[^I7] Intel announced the 8th Generation Core desktop family on September 24, 2017, with availability beginning October 5, 2017.[^I8] The year used here is **2017**.

### 3.5 Crux — Core i7-9700

Intel identifies the i7-9700 as a **9th Generation Core** processor, while retaining **Coffee Lake** as the codename. Its fabrication process is 14 nm and its individual SKU launch is **Q2 2019**.[^I9] Intel's archived launch-event announcement documents the introduction of 9th Generation Core processors on **October 8, 2018**.[^I10]

The table therefore uses **2018**, not 2019. The difference between the i7-8700 and i7-9700 rows is explicitly a product-generation distinction; it does not imply that their official codename fields differ.

### 3.6 Skylark — AMD EPYC 7532

AMD places the EPYC 7532 in the EPYC 7002 series; the series uses Zen 2 cores.[^A1] AMD's formal 2nd Generation EPYC launch was on August 7, 2019, so the table uses **2019**.[^A2]

AMD's earlier architecture disclosure identifies the upcoming processor as **Rome**, with 7 nm Zen 2 CPU chiplets and a separate 14 nm I/O portion.[^A3] That November 2018 disclosure was a pre-launch demonstration, not the formal generation launch used for this table. No exact EPYC 7532 SKU launch date is asserted here: the year records the 7002-series generation, not the introduction date of that particular model.

### 3.7 Thunderbird — Ampere Altra Q80-30

Ampere's March 3, 2020 announcement identifies **Altra** as a 64-bit Arm server processor based on the **Arm Neoverse N1** platform and documents 7 nm technology and Armv8.2+ compatibility.[^P1] Ampere's product brief explicitly lists **Q80-30** and specifies TSMC 7 nm FinFET fabrication.[^P2]

The table therefore records **Ampere Computing** as the vendor, **AArch64** as the 64-bit Arm execution/ISA category, **Neoverse N1-based** as the implementation lineage, and **2020** as the Altra processor-generation year. The date of the underlying Arm IP's announcement is not substituted for the Altra generation's launch year.

### 3.8 Artemisia — Xeon Gold 5420+

Intel identifies the **5420+** as a 4th Generation Xeon Scalable server processor, with **Sapphire Rapids** as its codename, **Intel 7** as its fabrication label, Intel 64 support, and a Q1 2023 SKU launch.[^I11] Intel's formal 4th Generation Xeon Scalable launch took place on January 10, 2023.[^I12] The chronological entry is therefore **2023**.

The `+` suffix is part of the processor model and is retained in the report. The fabrication entry is written as **Intel 7**, not silently rewritten as a generic “7 nm.”

## 4. Using this material in the report

The report can use Section 1's year-convention paragraph, the table and its essential notes from Section 2, and the references below. Section 3 provides the supporting research record and explains choices that a reader or grader might otherwise question.

Before finalizing the report, compare the handout's model names with the team's saved identification logs. If a host now contains a different processor, update that row and research the actually measured CPU; do not silently retain an obsolete handout model. Record the true primary contributor beneath the table and retain the same year convention in the later chronological master table.[^HW]

This file does **not** replace the separately required two pre-experiment hypotheses, timing-only measurements, or Phase-I freeze. Those are distinct assignment components.[^HW]

## 5. References and source-access notes

All external references below are manufacturer publications. Product-database references identify the exact SKU entry, while dated launch announcements establish generation-level chronology.

> **Source-safety note for Phase I.** Some manufacturer product pages and their search previews also display cache information. Only non-cache identification, chronology, and process facts are reproduced in this document. The Intel ARK entries are identified below by exact product name and product ID rather than by their full canonical URLs, because those URLs themselves embed cache-capacity information. Product briefs and broader family pages may also contain cache fields; do not use those fields to choose or adjust a Phase-I inference. This research note is not a certification that no search preview or underlying source ever displayed a cache field. Describe any actual prior exposure accurately in the team's methodology record.

[^HW]: Course handout, *Homework I: Cache Reverse Engineering Across Architectures and CPU Generations*, Fall 2026, uploaded as `PROJECT 1.pdf`. Page 3, Table 1 and “Machine research requirement” / “Year convention”; page 13, Section 8.1; pages 11–12, phase-separation rules; page 2, figure/table contributor attribution. The handout supplies the host/CPU mapping and assignment requirements, not the researched taxonomy answers.

[^I1]: Intel, *Intel Xeon Processor E5-2680 v3*, Intel Product Specifications / ARK, **product ID 81908**. Relevant metadata: product family, codename, market segment, processor number, fabrication, SKU launch, and Intel 64 support. Retrieved September 5, 2026. Full cache-bearing product URL intentionally not reproduced.

[^I2]: Intel, *Latest Intel Xeon Processors Accelerate Data Center Transformation for the Digital Services Era*, September 8, 2014. Establishes the E5-2600 v3 generation launch. [Official Intel announcement](https://www.intc.com/news-events/press-releases/detail/401/latest-intel-xeon-processors-accelerate-data-center). Retrieved September 5, 2026.

[^I3]: Intel, *Intel Core i7-6700 Processor*, Intel Product Specifications / ARK, **product ID 88196**. Relevant metadata: 6th Generation Core, Skylake, desktop classification, 14 nm fabrication, Q3 2015 SKU launch, and Intel 64 support. Retrieved September 5, 2026. Full cache-bearing product URL intentionally not reproduced.

[^I4]: Intel, *Introducing 6th Generation Intel Core, Intel's Best Processor Ever*, September 1, 2015. Corroborates the generation year, Skylake architecture, and 14 nm process; this dated family announcement is not used to assert an exact first-sale date for every SKU. [Official Intel announcement](https://www.intc.com/news-events/press-releases/detail/1193/introducing-6th-generation-intel-core-intels-best). Retrieved September 5, 2026.

[^I5]: Intel, *Intel Core i7-7700 Processor*, Intel Product Specifications / ARK, **product ID 97128**. Relevant metadata: 7th Generation Core, Kaby Lake, desktop classification, 14 nm fabrication, Q1 2017 SKU launch, and Intel 64 support. Retrieved September 5, 2026. Full cache-bearing product URL intentionally not reproduced.

[^I6]: Intel, *New 7th Gen Intel Core Processor: Built for the Immersive Internet*, August 30, 2016. The opening passage on PDF page 1 introduces the new 7th Generation Core processors. [Official Intel archived announcement (PDF)](https://download.intel.com/newsroom/2021/archive/2016-08-30-editorials-new-7th-gen-intel-core-processor-built-immersive-internet.pdf). Retrieved September 5, 2026.

[^I7]: Intel, *Intel Core i7-8700 Processor*, Intel Product Specifications / ARK, **product ID 126686**. Relevant metadata: 8th Generation Core, Coffee Lake, desktop classification, 14 nm fabrication, Q4 2017 SKU launch, and Intel 64 support. Retrieved September 5, 2026. Full cache-bearing product URL intentionally not reproduced.

[^I8]: Intel, *Intel Unveils the 8th Gen Intel Core Processor Family for Desktop, Featuring Intel's Best Gaming Processor Ever*, September 24, 2017. Documents the desktop-family announcement and October 5, 2017 availability. [Official Intel announcement](https://www.intc.com/news-events/press-releases/detail/203/intel-unveils-the-8th-gen-intel-core-processor-family). Retrieved September 5, 2026.

[^I9]: Intel, *Intel Core i7-9700 Processor*, Intel Product Specifications / ARK, **product ID 191792**. Relevant metadata: 9th Generation Core, Coffee Lake, desktop classification, 14 nm fabrication, Q2 2019 SKU launch, and Intel 64 support. Retrieved September 5, 2026. Full cache-bearing product URL intentionally not reproduced.

[^I10]: Intel, *Intel's Fall Desktop Launch Event (Replay)*, October 8, 2018. PDF page 1 identifies the event and the introduction of 9th Generation Core processors. [Official Intel archived launch notice (PDF)](https://download.intel.com/newsroom/2021/archive/2018-10-08-news-intels-fall-desktop-launch-event-livestream.pdf). Retrieved September 5, 2026.

[^A1]: AMD, *AMD EPYC 7002 Series Processors*. The series description identifies Zen 2; the manufacturer's indexed SKU information places EPYC 7532 in this series. The live SKU listing is dynamically rendered and may not be present in a text-only page export. [Official AMD family page](https://www.amd.com/en/products/processors/server/epyc/7002-series.html). Retrieved September 5, 2026. Only product-family membership and core architecture are used here.

[^A2]: AMD, *2nd Gen AMD EPYC Processors Set New Standard for the Modern Datacenter with Record-Breaking Performance and Significant TCO Savings*, August 7, 2019. Establishes the formal EPYC 7002 / 2nd Generation EPYC launch. [Official AMD Investor Relations release](https://ir.amd.com/news-events/press-releases/detail/904/2nd-gen-amd-epyc-processors-set-new-standard-for-the-modern-datacenter-with-record-breaking-performance-and-significant-tco-savings). Retrieved September 5, 2026.

[^A3]: AMD, *AMD Takes High-Performance Datacenter Computing to the Next Horizon*, November 6, 2018. The Rome/Zen 2 architecture discussion identifies the x86 processor design and separates the 7 nm CPU-chiplet process from the 14 nm I/O process. This is a pre-launch architecture disclosure, not the date used for the generation launch. [Official AMD Investor Relations release](https://ir.amd.com/news-events/press-releases/detail/860/amd-takes-high-performance-datacenter-computing-to-the-next-horizon). Retrieved September 5, 2026.

[^P1]: Ampere Computing, *Ampere Altra — Industry's First 80-Core Server Processor Unveiled*, March 3, 2020. Identifies the Altra generation, 64-bit Arm architecture, Neoverse N1 platform, 7 nm technology, and Armv8.2+ compatibility. [Official Ampere announcement](https://amperecomputing.com/press/ampere-altra-industrys-first-80-core-server-processor-unveiled). Retrieved September 5, 2026.

[^P2]: Ampere Computing, *Ampere Altra Family 64-Bit Multi-Core Processors*, product brief, May 11, 2023. The product list explicitly includes Q80-30; the technical metadata specifies Armv8.2+ compatibility and TSMC 7 nm FinFET. The brief's publication date is not the Altra generation's launch year. [Official Ampere product brief](https://amperecomputing.com/briefs/ampere-altra-family-product-brief). Retrieved September 5, 2026. Only the non-cache fields identified above are used.

[^I11]: Intel, *Intel Xeon Gold 5420+ Processor*, Intel Product Specifications / ARK, **product ID 232381**. Relevant metadata: 4th Generation Xeon Scalable, Sapphire Rapids, server classification, Intel 7 fabrication, Q1 2023 SKU launch, and Intel 64 support. Retrieved September 5, 2026. Full cache-bearing product URL intentionally not reproduced.

[^I12]: Intel, *Intel Launches 4th Gen Xeon Scalable Processors, Max Series CPUs and GPUs*, January 10, 2023. The dated opening announcement on PDF page 2 identifies the 4th Generation Xeon Scalable launch and Sapphire Rapids codename. [Official Intel archived launch release (PDF)](https://download.intel.com/newsroom/archive/2025/en-us-2023-01-10-intel-launches-4th-gen-xeon-scalable-processors-max-series-cpus.pdf). Retrieved September 5, 2026. The archive-path year is not the processor-generation launch year.
