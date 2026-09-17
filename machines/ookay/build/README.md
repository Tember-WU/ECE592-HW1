# Build and execution provenance

`recorded_commands.jsonl` is an index of exact command/compiler values already present in the source evidence. It is not a script to execute. Each entry records the original file, packaged file and JSON pointer. This folder also preserves existing build logs and binary/disassembly snapshots under their original paths. Shared Makefiles and source files are under `../main_code/`; restore the original layout to build them. No compiler version or historical command has been invented when the source did not record one.
