# Incomplete first-round attempt: round1

This attempt completed 4/39 configurations and stopped at the 512 MiB random point because `MADV_COLLAPSE` returned `Cannot allocate memory`. The manifest, completed raw samples and failure log are preserved unchanged. This attempt is excluded from the completed two-round analysis.

A fresh full sweep, `round1-retry2`, was started after a bounded allocation diagnostic and a temporary 1 GiB anonymous allocation/touch/release. No benchmark code, sample count, page policy or system settings were changed. See the preparation records in `../round1-retry2/`.
