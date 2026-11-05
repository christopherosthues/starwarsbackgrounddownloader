# Data Model: Temp-Staged Downloads with Hash Deduplication

**Feature**: `004-temp-staged-downloads` | **Date**: 2026-11-05

Entities from the feature spec's Key Entities section, extended with the validation rules and state transitions required by requirements FR-001…FR-011. No persistent storage exists — all entities are in-memory per run plus their filesystem artifacts (research.md R2).

## Background Image

One downloadable image from the article's gallery.

| Field | Type | Source / Rule |
|-------|------|---------------|
| `position` | int, 1-based | Gallery order from the parsed article (unchanged from feature 001). |
| `title` | str | Figure alt text verbatim; falls back to `background-<position>` when blank (unchanged). |
| `source_url` | str | Lumiere CDN URL with query string stripped (canonical form, unchanged). |
| `resolved_base_name` | str | **New.** Base name extracted from the URL path (`urlparse(source_url).path` basename) after query/fragment stripping. If empty or extension-less → fallback to position/title derivation (`NNN-title`). Windows-illegal characters replaced with `-`; trailing dots/spaces stripped (research.md R3). |
| `format` | JPEG \| PNG \| None | Detected from magic bytes of the staged content **after download**; unrecognized content is rejected with a clear error before any move (Constitution C3, FR-011 unchanged). The on-disk extension always equals the detected format's extension. |
| `content_hash` | str (SHA-256 hex) | **New.** Computed over the full staged file via streaming chunked reads after download; used for duplicate detection (FR-001). |
| `destination_path` | Path \| None | Final target path inside the effective output directory, including any sequential postfix applied at move time. |

**Validation rules**:
- `resolved_base_name` must be non-empty after sanitization or the fallback applies; it is never silently dropped.
- Extension mismatch between URL text and detected format resolves in favor of the detected format (research.md R3).
- Same content hash, different names: first occurrence wins — later same-hash items are discarded as duplicates (spec edge case).

## Temp Staging Folder

A per-run temporary directory under `<Temp>/swbdl/<datetime>` where images are downloaded before being moved to the target.

| Field | Type | Source / Rule |
|-------|------|---------------|
| `path` | Path | `<tempfile.gettempdir()>/swbdl/<YYYYMMDD-HHMMSS>`; counter suffix appended if the subfolder already exists (research.md R1). |
| `run_timestamp` | str | ISO 8601 `YYYYMMDD-HHMMSS`, unique per run. |
| `staged_files` | list[Path] | Files downloaded this run, keyed by item position. |
| `cleanup_status` | enum: pending \| cleaned | Set to `cleaned` when `<Temp>/swbdl` is deleted at run end — on success **and** failure (FR-005). |

**Lifecycle rules**:
- If `<Temp>/swbdl` exists at start (interrupted prior run), it is deleted before the fresh subfolder is created; stale files never mix with fresh downloads (spec edge case).
- The folder is deleted entirely after every run, including failed runs and move-phase failures (FR-005, clarification Q1).

## Download Run

A single invocation of the tool. Attributes: effective output directory, temp staging path, total items fetched, items moved to target, items discarded as duplicates (hash match), items failed (with reasons), bytes transferred, final exit status.

| Field | Type | Rule |
|-------|------|------|
| `effective_output_dir` | Path | Default `<Pictures>/StarWarsBackground` or user-specified `--output-dir` (feature 002 contract unchanged). |
| `staging_path` | Path | Temp Staging Folder path for this run. |
| `total_fetched` | int | Items found in the gallery and attempted. |
| `items_moved` | int | Staged files moved into the target directory (including postfix-renamed ones). |
| `items_discarded` | int | Staged files deleted as hash-match duplicates. |
| `items_failed` | list[(item, reason)] | Items that failed after bounded retries or failed to move; each reported individually with URL and reason (FR-004, FR-008). |
| `bytes_transferred` | int | Sum of bytes downloaded this run. |
| `exit_status` | 0 \| 1 | 0 iff `items_failed` is empty; otherwise 1 (clarification Q5). Usage errors exit 2 per the CLI contract. |

## Item State Transitions

Per-item outcome tracking (extends feature 001's `ItemStatus`; vocabulary aligned with the spec's Key Entities):

```text
PENDING ──download ok──▶ STAGED ──hash match────▶ DISCARDED   (staged file deleted)
                  │                        └──unique hash────▶ MOVED       (in target, possibly postfix-renamed)
                  └──retries exhausted──▶ FAILED               (ERROR line; run continues)
```

- `PENDING`: item parsed from the gallery, not yet downloaded.
- `STAGED`: file fully written and format-validated inside `<Temp>/swbdl/<datetime>`.
- `MOVED`: moved into the effective target directory (destination path recorded).
- `DISCARDED`: content hash matched an existing or already-moved file; staged file deleted, no target write.
- `FAILED`: download failed after bounded retries, format rejected, or move failed — reported individually with URL/path and reason; does not stop the run (clarification Q5).

**Invariants**:
- A file appears in the target directory only after its full content is staged and validated (no partial target writes; Constitution II/III).
- `MOVED + DISCARDED + FAILED = total_fetched` at run end.
- Re-running against an unchanged target yields `MOVED = 0`, all items `DISCARDED`, and a byte-for-byte identical target directory (FR-007, SC-001).
