# Crux Phase-I checkpoint before PMU verification

Created: 2026-09-14T15:31:22.812249+00:00. Git commit: `f86eecbb6fce590f3d40b64487620888b33dcd93`.

The timing-only worktree was clean. `manifest.json` records the committed raw/source/result blob IDs and SHA-256 hashes for copied baseline files in `snapshot/`. Existing timing inferences are preserved, including capacity approximately 32 KiB / 256 KiB with uncertain LLC, and the associativity selector's L1 9-way / L2-candidate 8-way labels. These are pre-PMU claims to test, not silently corrected conclusions.

This checkpoint was created before any PMU probes in this session. It cannot remove earlier limitations already disclosed in the source records. No original timing-only result was changed.
