# Contract: Command-Line Interface

**Feature**: `001-download-starwars-backgrounds` | **Date**: 2026-10-01

The CLI is the tool's only external interface (Constitution I). This contract is a governance-protected surface per the constitution's Development Workflow section; changes require a spec amendment and version bump.

## Invocation

```text
python starwars_backgrounds.py [--overwrite]
```

| Element | Contract |
|---------|----------|
| Entry point | `starwars_backgrounds.py` at the repository root, runnable via `python <script>` on Windows/macOS/Linux with Python 3.9+. |
| Positional arguments | None. The source article URL is fixed (FR-001); no user-supplied URLs are accepted. |
| `--overwrite` | Re-download and replace files that already exist at their destination path. Without this flag, existing files are skipped and left untouched (FR-007). |

No other flags exist by design; output location is always the standard folder `<Pictures>/StarWarsBackground` (research.md R4/R10).

## Output locations

| Platform | Standard output folder |
|----------|------------------------|
| Windows  | `%USERPROFILE%\Pictures\StarWarsBackground` |
| macOS    | `~/Pictures/StarWarsBackground` |
| Linux   | `$XDG_PICTURES_DIR/StarWarsBackground`, else `~/.local/share/Pictures/StarWarsBackground`, falling back to `~/Pictures/StarWarsBackground` |

The folder is created if it does not exist. File names follow the rule in data-model.md: `<NNN>-<sanitized-title>.<ext>`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Every background was downloaded successfully or skipped as already present (FR-010). |
| 1 | Runtime failure: article unreachable after bounded retries; one or more image items failed; zero backgrounds found in the article; output directory not writable. |
| 2 | Usage error (unrecognized flag/argument), per `argparse` convention. |

## stdout format (progress — FR-008, SC-005)

Human-readable plain text, one line per item plus a final summary:

```text
Found 99 backgrounds in the article.
[12/99] At Attin -> C:\Users\chris\Pictures\StarWarsBackground\012-at-attain.jpg (305412 bytes)
...
Summary: 97 downloaded, 2 skipped, 0 failed. Output folder: <path>
```

Rules:
- Every item line contains: zero-padded index/total count, title, destination path, and byte count (`skipped` items show no byte count).
- The summary line reports counts per outcome and the output folder path.
- stdout carries progress only; it never carries error details.

## stderr format (errors — FR-006, FR-008)

One line per failure with enough context to reproduce it:

```text
ERROR [attempt 3/3] https://lumiere-a.akamaihd.net/v1/images/<name>.jpeg: HTTPError 503 after retries
ERROR item "Hoth" (https://...): rejected format — not a recognized JPEG/PNG image
```

Rules:
- Network failures include the URL, attempt number (`attempt n/3`), and error type.
- Format rejections name the item title and URL.
- The final non-zero exit is always preceded by at least one `ERROR` line on stderr.

## Guarantees (from spec)

- No network requests other than the article page fetch and image downloads linked from it; no telemetry of any kind (FR-009).
- Atomic writes: a destination file appears only when complete and validated; failed items leave no partial files (FR-005, SC-004).
- Re-runs are idempotent without `--overwrite` (FR-007, SC-002).
