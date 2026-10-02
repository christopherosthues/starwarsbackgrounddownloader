# Contract: Command-Line Interface (Amended)

**Feature**: `002-custom-image-directory` | **Date**: 2026-10-02

This contract amends [feature 001's CLI contract](../001-download-starwars-backgrounds/contracts/cli.md). Per the constitution's Development Workflow section, public CLI options are a governance-protected surface; this feature's specification is the amendment and the module-level `__version__` constant is bumped to **1.1.0** (research.md R5). Everything not restated here remains in force from feature 001.

## Invocation

```text
python starwars_backgrounds.py [--overwrite] [--output-dir <path>]
```

| Element | Contract |
|---------|----------|
| Entry point | `starwars_backgrounds.py` at the repository root, runnable via `python <script>` on Windows/macOS/Linux with Python 3.9+. |
| Positional arguments | None (unchanged). The source article URL is fixed; no user-supplied URLs are accepted. |
| `--overwrite` | Unchanged from feature 001: re-download and replace files that already exist at their destination path. Applies within the effective output directory. |
| `--output-dir <path>` (new) | Sets the directory where images are saved for this run, replacing the default `<Pictures>/StarWarsBackground`. Relative paths resolve against the current working directory; `~` is expanded; blank values are rejected as a usage error. A missing directory (including missing parents) is created automatically. See "Output locations" and "Exit codes". |

## Output locations

| Case | Effective output directory |
|------|----------------------------|
| No `--output-dir` given | Default standard folder, unchanged: `<Pictures>/StarWarsBackground` (platform table in feature 001's contract). Created if absent. |
| `--output-dir <existing directory>` | That directory, as-is. Never created; never modified except for image writes. |
| `--output-dir <missing path>` | The full path is created (including missing parents) before any download starts. |

File naming inside the effective output directory follows feature 001's rule: `<NNN>-<sanitized-title>.<ext>`. Every per-item progress line and the summary line report destination paths as absolute paths derived from the effective output directory, regardless of how `--output-dir` was typed (FR-007).

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Every background was downloaded successfully or skipped as already present **inside the effective output directory** (FR-009). |
| 1 | Runtime failure: article unreachable after bounded retries; one or more image items failed; zero backgrounds found; `--output-dir` path exists but is not a directory; specified directory could not be created. Each such failure prints an `ERROR` line naming the offending URL or path. |
| 2 | Usage error (unrecognized flag/argument, or blank `--output-dir` value), per `argparse` convention. |

## stdout format (progress — FR-007, FR-008)

Unchanged from feature 001: one line per item plus a final summary; every item line contains index/total count, title, absolute destination path, and byte count (`skipped` items show no byte count); the summary reports counts per outcome and the effective output folder path. With `--output-dir`, all reported paths point into the specified directory (SC-001).

## stderr format (errors — FR-005, FR-008, FR-009)

Unchanged conventions, with two new error shapes:

```text
ERROR <path>: not a directory — cannot use as output location
ERROR <path>: <reason>   # e.g., permission denied while creating the directory
```

Rules (additions only):
- Directory resolution/creation failures name the offending path and reason, appear before any download starts, and are always followed by exit status 1.
- Blank `--output-dir` values produce argparse's standard usage error on stderr with exit status 2; no fallback to the default folder occurs (FR-008).

## Guarantees (from spec)

- No network requests other than the article page fetch and image downloads linked from it; no telemetry of any kind (unchanged, FR-009 of feature 001).
- Atomic writes: a destination file appears only when complete and validated; failed items leave no partial files — identical guarantees inside custom directories.
- Re-runs against the same effective output directory are idempotent without `--overwrite` (FR-006, SC-005); existing unrelated files in a custom directory are left untouched.
- When `--output-dir` is used, zero images are written to the default Pictures-based folder during that run (FR-002).
