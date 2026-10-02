# Data Model: Custom Image Output Directory

**Feature**: `002-custom-image-directory` | **Date**: 2026-10-02

This feature is additive to the data model defined in [feature 001](../001-download-starwars-backgrounds/data-model.md). It introduces one new entity and extends one existing entity. All other entities (`BackgroundImage`, `ItemResult`) are unchanged; their validation rules, naming rule, and state transitions apply identically inside custom directories.

## Entity: OutputDirectory (new)

The location where images are saved for a run — either the user-provided directory or the default standard folder.

| Field | Type | Source / Rule |
|-------|------|---------------|
| `provided_value` | str \| None | Raw value of `--output-dir`; `None` when the option is absent (FR-003). Blank values never reach this entity — they are rejected at parse time (research.md R3). |
| `resolved_path` | Path (absolute) | Normalized effective directory: expanduser applied; relative values resolved against the current working directory; absolute values used as given (FR-007, research.md R2). |
| `created_by_run` | bool | True when this run created the directory or any missing parents (FR-004); False when it already existed. |

**Validation rules**:
- `resolved_path` MUST exist and be a directory before any download starts; if the value names an existing file, resolution fails with an error naming that path (FR-005).
- Creation of missing directories (including parents) MUST succeed or fail loudly: creation failures produce an error naming the offending path and reason, with non-zero exit status (FR-004, FR-009).
- `resolved_path` is used for all existence checks, writes, and progress/summary reporting — reported destination paths are always absolute and unambiguous (FR-007).

## Entity: DownloadRun (extended)

One invocation of the tool. Feature 001 fields (`total_found`, `items`, `bytes_downloaded`, `exit_status`) are unchanged; this feature adds:

| Field | Type | Rule |
|-------|------|------|
| `effective_output_dir` | Path (absolute) | The OutputDirectory's `resolved_path` for this run — default standard folder when no option was given, custom directory otherwise. All item destination paths derive from it. |

**Invariants (unchanged, now scoped to the effective output directory)**:
- A run never writes outside its effective output directory; when a custom directory is used, zero images are written to the default Pictures-based folder (FR-002).
- Safe-write rules apply identically inside custom directories: existing files are skipped unless `--overwrite` is given; re-runs against the same directory are idempotent (FR-006).
- Exit status 0 requires every item saved or skipped *inside the effective output directory* (FR-009); any resolution, creation, or download failure yields non-zero exit.
