# Sunbird experiment preparation

Host: `sunbird.ece.ncsu.edu`. Both formal rounds use CPU 32 / NUMA node 0, with SMT sibling CPU 8. The original C kernel, collector, planner, analyzer, common round-1 configuration, and compiler flags are unchanged.

The machine had no `numactl` executable. The Rocky Linux 9 `numactl-2.0.19-3.el9.x86_64.rpm` was extracted into `build/sunbird/deps/`, using the existing system `libnuma.so.1`. The RPM and executable are preserved here; their source URL and SHA-256 hashes are in `dependencies.json`. No system package installation was performed. A local `.venv` supplies the NumPy and Matplotlib versions from `requirements.txt`; `python-freeze.txt` records the complete Python environment.

Use this environment from the capacity directory:

```bash
export PATH="$PWD/.venv/bin:$PWD/build/sunbird/deps/usr/bin:$PATH"
```

To restore the local NUMA tool after cleaning `build/`:

```bash
mkdir -p build/sunbird/deps/usr/bin
cp data/sunbird/setup/numactl build/sunbird/deps/usr/bin/numactl
chmod u+x build/sunbird/deps/usr/bin/numactl
```

`make MACHINE=sunbird capacity assembly` succeeded. All 10 existing `make check` tests passed in the local Python environment. The inherited affinity mask was narrower than the CPUs available for explicit binding; binding to CPU 32 was checked successfully. `preflight.json` records a 3-second all-CPU observation: CPU 32 and CPU 8 were both at 0% busy time. This short observation does not reserve a CPU or prove the absence of later interference.

## Initial allocation failure and preparation

The first attempt, `../round1/`, stopped at its fourth configuration (`1 MiB`, sequential) because `MADV_COLLAPSE` returned `ENOMEM`. Three completed configurations and all failure records are retained. This incomplete attempt is excluded from the formal first-round and combined analyses.

Untimed allocation diagnostics are saved in `allocation-diagnostic.json`. A 512 MiB allocation initially failed its collapse request and then succeeded on the next trial. A subsequent process-local 2 GiB allocation also returned `ENOMEM` for complete collapse, with partial huge-page backing. It was released. All five subsequent 512 MiB allocations succeeded and were verified as fully backed by huge pages; see `allocation-preparation.json`. These allocations generated no capacity timing samples. No THP policy, global cache-dropping, or system VM settings were changed. The sequence is consistent with transient allocation availability; it does not prove a unique cause for the earlier failure.

The collector then restarted the entire coarse scan under the new ID `round1_retry1`, retaining the original strict huge-page checks. Every actual measurement verifies page backing before and after timing.

Host inspection with `lscpu` included cache specifications. Follow-up intervals and reported capacity evidence are selected from the new timing measurements, but this execution should not be described as blind to hardware specifications. No PMU measurements are used.

## Validation

After each completed run has been analyzed, the supplementary audit can be repeated:

```bash
python3 data/sunbird/setup/audit_runs.py round1_retry1 round2
```

It verifies manifest completion, raw sample counts and hashes, positive timing intervals, source/executable hashes, analysis input provenance, CPU binding, local NUMA placement, and actual huge/base-page backing. It also summarizes measurement faults, context switches, and SMT sibling activity. Per-run validation records are written under `results/sunbird/<run-id>/validation.json`.
