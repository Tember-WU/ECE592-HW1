# Machine-organized submission material: Sections 8.2–8.5

This directory follows the assignment's machine-first layout. It is an independent
copy of existing evidence from `timing-only`, `PMU-verification`,
`PMU_Counter_Analysis`, and `software-hit-rate`. The source directories are retained.
No measurement, inference, event mapping or historical command is changed by
this organization step.

This export contains **16,108 archived files**, about **3.10 GiB** after lossless
compression (5.65 GiB before export compression, including shared code copies).
[Full verification](verification.json) checked every archived file and confirmed
that all 15,156 distinct source files remained unchanged. A separate
[restoration check](restore_verification.json) restored Artemisia using only this
package, compiled its estimator, reproduced a one-million-sample CSV statistic,
and revalidated all 54 million Section 8.5 timing samples without new collection.

```text
machines/
  sunbird/                    # same structure for all eight ECE hosts
    README.md
    manifest.jsonl            # original path, archived path, SHA-256, compression
    main_code/
      x86_64/
      aarch64/
      common/                 # portable code, scripts, configs and source snapshots
    build/                    # compiler/build logs, binary/assembly snapshots
    capacity/{raw,processed}/
    line_size/{raw,processed}/
    associativity/{raw,processed}/
    inclusion_policy/{raw,processed}/
    latency/{raw,processed}/
    pmu/
      raw/{verification,counter_analysis}/
      processed/{verification,counter_analysis}/
    software_hit_rate/{raw,processed}/
  artemisia/
  charnwood/
  ookay/
  upgrade/
  crux/
  skylark/
  thunderbird/
  hazel_haswell/              # empty example template; includes slurm/
  hazel_genoa/                # empty example template; includes slurm/
  cross_machine/             # Section 8.4 rankings/comparison figures and history
  tools/
  export_summary.json
  verification.json
  excluded.json
```

## What is included

- Existing source, scripts, machine configurations, exact per-run snapshots,
  compiler/build records, environment/pinning records and recorded commands.
- Complete available raw timing/counter outputs, including preserved failed,
  retry, smoke and diagnostic runs. Their original statuses remain attached.
- Processed statistics, inference/validation JSON, PNG/PDF/SVG figures, reports,
  reference/event evidence, and all existing multi-machine comparisons.
- Empty placeholders when no corresponding machine results exist. Currently
  Section 8.5 data exist only for Artemisia and Sunbird. The other six ECE hosts
  have estimator source but no substituted calibration/measurement results.

The native architecture directories classify source instruction paths, not
claims that every archived source variant ran on every machine. Portable C/C++
and headers live in `common` alongside the workflow files. Original path prefixes
and per-run source snapshots distinguish versions. Rebuild native binaries on
their intended host; old binaries are provenance, not universal executables.

Raw CSV arrays larger than 1 MiB are compressed with deterministic gzip.
Decompression reproduces the original bytes and hash. Existing compressed
arrays are copied unchanged. Small original summary CSVs under legacy
`raw_data/` names are placed in **processed**, since they cannot reconstruct
individual samples. Virtual environments, Python caches, agent instructions,
and unowned live binaries alongside shared source are excluded. Per-run
executable snapshots and working machine-specific build records are retained.

## Traceability and reproduction

Each host's `manifest.jsonl` is authoritative for original-to-archive mapping.
`source_sha256` always hashes the original source file bytes; for a newly gzipped
CSV this is the hash after decompression. Every processed plot retains its
original source/input provenance and can be traced through this mapping.
`build/recorded_commands.jsonl` indexes existing exact command/compiler values
with their original JSON locations. Unrecorded history is not invented.

Splitting files changes their relative locations, so the old scripts and Markdown
links should be used after restoring their original layout. Restoration uses only
the files under `machines/` and verifies every restored hash:

```bash
# From the repository root; output must not already exist.
python3 machines/tools/restore_layout.py --machine artemisia --output /tmp/ece592-artemisia-restored

# All eight machines, shared code, and cross-machine comparisons:
python3 machines/tools/restore_layout.py --machine all --output /tmp/ece592-all-restored
```

The tools do not start experiments, submit Slurm jobs or initialize/commit Git
repositories. Existing scripts retain their original host checks and working
directory requirements. For new collection outside the repository, initialize
a Git checkout if the original collector requires one. Each machine README
provides workflow entry points and points to the exact historical commands.
Archived absolute paths are provenance, not automatically portable shell commands.

Run `python3 machines/tools/organize.py verify` while the source directories are
available to verify the entire export against its originals. The restore tool
validates the package independently without consulting those directories.
The organizer refuses to overwrite an existing export. Review a new export
when additional machine results are pulled; this is a snapshot, not a live view.

## Existing result limits remain visible

This organization does not repair missing associativity raw distributions,
inclusion sample-count/method problems, or ambiguous machine labels. In
particular, Thunderbird's inclusion evidence has an inner Artemisia name;
its original bytes and outer ownership are preserved and flagged in its README.
Sunbird's Section 8.5 notes document a large estimation error even though the
collection completed. Read the original run notes before choosing final values.

`export_summary.json` describes coverage and size; `verification.json` records
packaging integrity, not a scientific grading verdict. The Hazel directories
are empty examples, not evidence that those generations have been allocated or
measured. Final report/slides, contributor material and Git submission remain
separate deliverables.
