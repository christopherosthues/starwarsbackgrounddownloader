# Contract: Command-Line Interface (Amended)

**Feature**: `004-temp-staged-downloads` | **Date**: 2026-11-05

This contract amends [feature 003's CLI contract](../003-add-help-flag/contracts/cli.md). Per the constitution's Development Workflow section, public CLI options and output file naming rules are governance-protected surfaces; this feature's specification is the amendment and the module-level `__version__` constant is bumped **1.2.0 → 1.3.0** (research.md R9). Everything not restated here remains in force from features 001–003.

## Invocation

```text
python starwars_backgrounds.py [--overwrite] [--output-dir <path>] [--delay <seconds>]
```

| Element | Contract |
|---------|----------|
| Entry point | `starwars_backgrounds.py` at the repository root, runnable via `python <script>` on Windows/macOS/Linux with Python 3.10+. |
| Positional arguments | None (unchanged). The source article URL is fixed; no user-supplied URLs are accepted. |
| `-h`, `--help` | Unchanged from feature 003: prints curated usage and exits 0 before any resolution, fetch, or download. Help text gains the `--delay` line. |
| `--overwrite` | Amended semantics (research.md R7): re-download and replace files that already exist — under this feature's scheme, a staged file whose derived name matches an existing target file **replaces** it instead of receiving a sequential postfix. Hash-match discards still apply either way. Without the flag, existing target files are never replaced. |
| `--output-dir <path>` | Unchanged from feature 002 (resolution, creation, error taxonomy). |
| `--delay <seconds>` (**new**) | Float pause between successive image download requests; default **0.2**, minimum 0. Blank or negative values are rejected as a usage error (exit 2). Retry backoff is unchanged and additive to this delay (research.md R6). |

## File naming rule (amended)

Saved file names are derived from the base name embedded in the source download URL — not from position-based generation:

1. Base name = basename of the URL path after query/fragment stripping; Windows-illegal characters replaced with `-`, trailing dots/spaces stripped.
2. If no recognizable base name exists (empty or extension-less), fall back to feature 001's rule: `<NNN>-<sanitized-title>.<ext>`.
3. Extension always equals the detected format's extension (`.jpg`/`.png`) from magic-byte validation — never the URL's text.
4. If the destination already exists and `--overwrite` is not set, append `-1`, `-2`, ... before the extension until unique (`name.jpg` → `name-1.jpg`). With `--overwrite`, the existing file of the same name is replaced instead.

Every per-item progress line and the summary report absolute destination paths inside the effective output directory (feature 002 contract unchanged).

## Temp staging guarantee (new)

All images for a run appear first in `<Temp>/swbdl/<datetime>` before any file appears in the target directory; this run's staging subfolder is deleted after every run — successful, failed, or interrupted — and `<Temp>/swbdl` itself is removed once empty, leaving no residual files (FR-003, FR-005, SC-003).

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Every item was moved to the target directory or discarded as a hash-match duplicate; zero failures. |
| 1 | Runtime failure: article unreachable after bounded retries; one or more image items failed (download, format rejection, or move) — each reported individually with URL/path and reason; zero backgrounds found; `--output-dir` path exists but is not a directory; specified directory could not be created. |
| 2 | Usage error (unrecognized flag/argument, blank `--output-dir` value, blank/negative `--delay` value), per `argparse` convention. |

## stdout format (progress — FR-010)

Two-phase progress, one line per item per phase:

```text
Found N backgrounds in the article.
[1/N] <title> -> <abs-staged-path> (<bytes>)          # download phase
...
<name>.jpg -> <abs-target-path>                        # move phase (postfix-renamed names show final name)
<name>.jpg: duplicate (hash match)                     # move phase, discarded
Summary: X moved, Y duplicates discarded, Z failed. Output folder: <effective-output-dir>
```

The summary's outcome vocabulary replaces feature 001's "downloaded/skipped" counts with the spec's moved/discarded/failed vocabulary; byte totals and per-item context remain (Constitution V).

## stderr format (errors — FR-004, FR-008, FR-010)

Unchanged conventions: `ERROR` lines carry enough context to reproduce the failure (URL, attempt number, error type); move-phase failures additionally name the target path and reason. Failed items do not stop the run; each is reported individually and the exit status becomes 1 (clarification Q5).

## Guarantees (from spec)

- No network requests other than the article page fetch and image downloads linked from it; no telemetry of any kind (unchanged, FR-011).
- Stateless deduplication: every run re-fetches all images to temp staging; duplicates are detected by content hash against existing target files hashed at run start — no manifest or state file is created anywhere (FR-001, FR-007).
- Re-runs against an unchanged target directory leave it byte-for-byte identical: 0 new, modified, or overwritten files (SC-001).
- Best-effort moves: successful images are moved even when other items fail; failing items are reported individually with URL and reason (FR-004).
- Atomic per-file writes: a target file appears only after its full content is staged, validated, and moved; failed runs leave no partial files in the temp folder or the target directory (SC-005).
- Configurable throttling keeps ~100-image runs under 2 minutes at the default delay (FR-009).
