# Charnwood latency02: incomplete retry

Status: **failed**, with 11/30 configurations completed. This retry ran from 2026-09-10T20:55:23.046528+00:00 to 2026-09-10T20:56:03.503232+00:00.

The original configuration and timing code were reused after a separate 512 MiB allocation diagnostic succeeded. The full run nevertheless stopped at `llc_miss__alternate` before measurement with `MADV_COLLAPSE: full THP backing unavailable: Cannot allocate memory`.

All completed samples and failure evidence are retained in [the raw run](../../../data/charnwood/latency02/). This incomplete attempt is excluded from formal analysis and has not been combined with other runs. The exact allocation-failure cause was not established.

A new full retry was launched as `latency03`, with glibc allocator thresholds set to release large temporary allocations more readily. No C source, timing operation, measurement configuration, or global kernel setting was changed. Details are in [the launch context](../preparation/launch-context-latency03.json).

[Manifest](../../../data/charnwood/latency02/manifest.json) · [Collector output](../../../data/charnwood/latency02/collector.log) · [Failure log](../../../data/charnwood/latency02/logs/llc_miss__alternate.txt)
