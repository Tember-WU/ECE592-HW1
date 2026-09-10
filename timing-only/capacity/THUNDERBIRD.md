# Thunderbird: AArch64 capacity experiments

The original `src/cache_bench.c`, Artemisia configs, raw data, and results are preserved. Before this port, 386 original files were hashed in `data/thunderbird/preflight/artemisia_sha256_before.json`. The pre-edit shared scripts, Makefile, README, and x86 source were also copied to `data/thunderbird/preflight/source_before/`.

## Architecture changes

- Host: thunderbird.ece.ncsu.edu; Linux AArch64, little endian, ARM Neoverse-N1. CPU 32, NUMA node 0, one hardware thread per core. The initial `lscpu` compatibility check also displayed kernel-reported cache totals; those totals are not used to select intervals or substitute for timing evidence.
- `src/cache_bench_aarch64.c` retains the pointer cycle, random seeds, warm-up, sample storage, and page validation from the x86 source. The compiler remains GCC with the same `-O0` flags. Make selects the source from the compiler target and omits x86-only objdump options on ARM.
- The timed assembly uses `DSB ISH; ISB; MRS CNTVCT_EL0; ISB`, 16 mutually dependent `LDR` instructions per loop group, then `DSB ISHLD; ISB; MRS CNTVCT_EL0; ISB`. No PMU is used. Register constraints preserve the start timestamp throughout the loop, and the timed interval contains no stack access or calls.
- `CNTFRQ_EL0` is 25,000,000 Hz on this host: one raw tick is 40 ns, **not one core cycle**. At 256 loads/batch, one raw tick corresponds to 0.15625 ns/load; the 1024-load controls reduce that increment to 0.0390625 ns/load. Timing/barrier overhead remains included; the empty control is reported separately without subtraction. A zero-tick empty control is valid at finite timer resolution; nonempty intervals must be positive.
- The base page is 4 KiB and the PMD huge page is 2 MiB, obtained from the running kernel. Full THP backing is verified before and after timing. Already-complete first-touch THP does not require `MADV_COLLAPSE`; incomplete backing requires successful collapse and subsequent validation. No silent switch to base pages is allowed.
- ARM `/proc/cpuinfo` has no x86-style `model name`; the runner records implementer, architecture, variant, part, and revision instead. Timer frequency, governor, and CPU frequency snapshots are recorded. The existing `schedutil` governor is retained.

The timer ordering/frequency choices follow [Arm's Generic Timer guide](https://documentation-service.arm.com/static/66c4754f32f35b31ceb317ff) and [Arm's system-counter example](https://learn.arm.com/learning-paths/servers-and-cloud-computing/arm_pmu/assembly/). The preflight directory contains native smoke checks, timer calibration, inspected disassembly, unit-check logs, and an environment record. These short smoke checks are excluded from the two formal rounds.

## Local dependencies and commands

Python dependencies use the original pinned requirements in `.venv/`. The missing `numactl` executable was extracted locally from [Rocky Linux's AArch64 numactl 2.0.19-3.el9 package](https://download.rockylinux.org/pub/rocky/9/BaseOS/aarch64/os/Packages/n/numactl-2.0.19-3.el9.aarch64.rpm); it uses the host's installed `numactl-libs` of the same version. The executable is also archived as `data/thunderbird/preflight/numactl.bin`, with package/executable SHA256 hashes. No system packages or kernel settings were changed.

```bash
cd /home/swu35/ECE592-HW1/timing-only/capacity
export PATH="$PWD/.venv/bin:$PWD/build/thunderbird/deps/usr/bin:$PATH"
make MACHINE=thunderbird capacity assembly
make check
python3 scripts/run_capacity.py --machine thunderbird --run-id round1
python3 scripts/analyze_capacity.py --machine thunderbird --run-id round1
# The completed first round selected the following measured endpoints:
python3 scripts/plan_capacity.py --machine thunderbird --from-runs round1 --round 2 \
    --l1 64KiB:128KiB --l2 1MiB:2MiB --llc 32MiB:64MiB \
    --output configs/thunderbird-round2.json
python3 scripts/run_capacity.py --machine thunderbird --config configs/thunderbird-round2.json --sweep all --run-id round2
python3 scripts/analyze_capacity.py --machine thunderbird --run-id round2
python3 scripts/analyze_capacity.py --machine thunderbird --run-id round1 round2 --output-id combined12 \
    --boundaries results/thunderbird/combined12/boundaries.json
python3 scripts/validate_capacity.py --machine thunderbird --run-id round1 round2 --output-id combined12
```

Every collection requires a new run ID. The two rounds run serially, with the same kernel and CPU/NUMA binding. Round 1 uses the unchanged shared protocol: 39 configurations spanning 2 KiB–512 MiB, with 1,000,000 timed batches per configuration. Round 2 follows the original bounded adaptive planner, using only endpoints measured in the new first round. Raw arrays stay in counter ticks; multiply the ARM ticks/load by 40 to obtain ns/load. Different ISAs' raw tick values cannot be directly compared.

Both rounds are complete: 96 configurations and 96,000,000 timed batches. See the [combined results and interpretation](results/thunderbird/combined12/RUN_NOTES.md) and [validation record](results/thunderbird/combined12/validation.json). The measured estimates are approximately 64 KiB for L1D and 1 MiB for L2; the LLC/system-cache result is an effective transition region of 32–64 MiB, not a unique physical capacity.

The commands above document the completed sequence. Collection and planning refuse to overwrite existing run IDs/config files; a new experiment requires new names and intervals selected from its own first-round measurements. Analysis and validation can be rerun directly for the existing data.
