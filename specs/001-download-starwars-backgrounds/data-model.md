# Data Model: Star Wars Backgrounds Downloader

**Feature**: `001-download-starwars-backgrounds` | **Date**: 2026-10-01

This tool is stateless between runs; the "data model" describes the in-memory entities built from the article page and the rules that govern their persistence. There are no databases or persistent state files (Constitution I).

## Entity: BackgroundImage

One downloadable image from the article's gallery, extracted from a `<figure><img>` block.

| Field | Type | Source / Rule |
|-------|------|---------------|
| `position` | int (1-based) | Order of appearance in the article body; drives filename prefix and progress reporting. |
| `title` | str | The figure's `alt` attribute, verbatim from the page. |
| `source_url` | str | The figure's `src`, with any query string stripped (canonical full-resolution CDN object — see research.md R3). |
| `format` | enum: `jpeg` \| `png` | Determined by magic bytes after download (research.md R7); not trusted from the URL. |
| `destination_path` | Path | `<output_root>/<NNN>-<sanitized-title>.<ext>` per naming rule below. |

**Validation rules**:
- `source_url` MUST be an absolute HTTPS URL on the lumiere CDN host referenced by the article (any other asset is not a background and is excluded at parse time).
- `title` MUST be non-empty after trimming; if empty, fall back to `background-<position>`.
- Duplicate detection: two items with different `source_url`s are always distinct items even when titles match.

**File naming rule (FR-003, edge cases)**:
1. Prefix: `NNN` = zero-padded 3-digit gallery position (e.g., `007`).
2. Stem: title lowercased; every run of characters outside `[a-z0-9]` collapsed to a single `-`; leading/trailing `-` removed; truncated to 60 chars at the last safe boundary.
3. Extension: `.jpg` for JPEG, `.png` for PNG (from validated format, never from the URL).
4. The position prefix guarantees global uniqueness within a run — no two items can produce one file name.

## Entity: DownloadRun

One invocation of the tool; exists only in memory and is summarized to stdout at exit.

| Field | Type | Rule |
|-------|------|------|
| `total_found` | int | Count of BackgroundImage items extracted from the article (0 ⇒ run fails with "no backgrounds found"). |
| `items` | list[ItemResult] | One result per item, in gallery order. |
| `bytes_downloaded` | int | Sum of bytes written for successful items this run. |
| `exit_status` | 0 \| 1 \| 2 | 0 only when every item succeeded (or was skipped as already present); see contracts/cli.md. |

### ItemResult state transitions

```text
pending ──► downloading ──► saved          (new file written atomically)
                  │
                  ├──► skipped              (final path exists and --overwrite not given; FR-007)
                  │
                  └──► failed               (all retries exhausted, or format rejected after download)
```

- `saved`: temp file renamed to final name; magic bytes validated.
- `skipped`: existing file left untouched; counts as success for exit status.
- `failed`: reason recorded (URL + attempt count + error type); temp file deleted if any; item reported on stderr; contributes to non-zero exit status.

**Invariants**:
- A run never writes two items to the same destination path.
- After a run ends (success or failure), no temporary files remain in the output directory and every final-path file is either pre-existing user content, a complete validated image written by this tool, or absent.
- Re-running with identical input produces zero new writes when all items are `skipped` (idempotency — FR-007/SC-002).
