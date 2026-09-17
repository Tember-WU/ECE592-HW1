# Charnwood latency01: incomplete attempt

Status: **failed**, with 11/30 configurations completed. Collection started at 2026-09-10T20:53:15.927934+00:00 and stopped at 2026-09-10T20:53:55.863472+00:00.

The run stopped at `llc_miss__alternate`, the 512 MiB paired configuration, before its formal sampling loop. The benchmark reported `MADV_COLLAPSE: full THP backing unavailable: Cannot allocate memory`. The first 11 completed configurations and all their compressed samples, as well as the failed configuration's log, remain in [the raw run](../../../data/charnwood/latency01/).

This attempt is not a complete seven-group result and has not been passed to the formal analyzer. It is not pooled into subsequent attempts. The collector's stop preserves the original requirement for complete huge-page backing.

A subsequent [allocation diagnostic](../preparation/thp-probe.json), using the same 512 MiB footprint and binary with only 16 paired samples, successfully verified full huge-page backing before and after timing. It is a diagnostic, not a formal latency measurement. No kernel setting, page policy, or timing source was changed. The precise cause of the transient allocation failure was not established.

A fresh full seven-group run was launched as `latency02` with the same configuration and shuffled order. That retry also stopped at allocation; see [the latency02 record](../latency02/RUN_NOTES.md) and [preparation records](../preparation/README.md).

[Manifest](../../../data/charnwood/latency01/manifest.json) · [Collector output](../../../data/charnwood/latency01/collector.log) · [Failure log](../../../data/charnwood/latency01/logs/llc_miss__alternate.txt)
