# Implementation Plan: Star Wars Backgrounds Downloader

**Branch**: `001-download-starwars-backgrounds` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-download-starwars-backgrounds/spec.md`

## Summary

A single cross-platform Python CLI script that fetches the StarWars.com article "Star Wars Backgrounds for Video Calls & Meetings" (https://www.starwars.com/news/star-wars-backgrounds), extracts every background image in the article's gallery (99 unique full-resolution images at time of writing; the article advertises "more than 50"), and saves each to `StarWarsBackground` inside the user's platform-standard Pictures directory. Downloads are atomic, idempotent on re-run (no overwrite unless `--overwrite`), retried with bounded attempts, and reported per-item on stdout with errors on stderr; exit status is non-zero on any failure. Tech stack (owner-specified): Python with Selenium 4.50.0 for rendered page acquisition, BeautifulSoup4 4.15.0 for gallery parsing, Requests 2.34.2 for image downloads, plus stdlib `argparse`/`pathlib`.

## Technical Context

**Language/Version**: Python 3.9+ (developed and tested locally on Python 3.11.9)

**Primary Dependencies** (owner-specified stack): `selenium==4.50.0` (rendered page acquisition via headless browser), `beautifulsoup4==4.15.0` (gallery HTML parsing), `requests==2.34.2` (image downloads with retries/timeouts), `platformdirs` (cross-platform Pictures directory resolution). Standard library: `argparse`, `pathlib`, `tempfile`, `os`, `sys`. Each third-party dependency is justified in research.md per Constitution Principle I; runtime also requires a supported browser + driver (Selenium Manager-managed) — see Constraints.

**Storage**: Filesystem only — output folder plus temporary download files in the same directory (atomic rename). No database, no state files.

**Testing**: `unittest` (standard library — keeps the test stack dependency-free) with recorded rendered-HTML fixtures for parser tests and a local HTTP stub server (`http.server`) for download behavior; page acquisition is isolated behind an injectable provider so unit tests never launch a browser or touch live endpoints (Constitution Principle IV).

**Target Platform**: Windows, macOS, Linux (cross-platform CLI; clarified in spec).

**Project Type**: CLI tool — single command-line script, no configuration files.

**Performance Goals**: One complete collection download (~99 images) finishes without hanging; every network request has a bounded timeout so a failed run terminates in well under 10 minutes even with retries. No artificial rate limiting beyond retry backoff.

**Constraints**: Owner-specified dependency set only — `selenium`, `beautifulsoup4`, `requests` plus stdlib; no further third-party packages without justification (Constitution I); atomic writes or cleanup on failure (FR-005/II); no overwrite of existing files without explicit option (FR-007/III); deterministic, documented output paths; exit 0 only on full success (FR-010); tool-initiated network requests limited to the article page and its linked image assets (FR-009) — browser rendering sub-resources are part of page acquisition, see research.md R2.

**Scale/Scope**: One source article; ~99 background images per run (~1–5 MB each); single user, local machine.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle / Constraint | Gate Result | Notes |
|---|------------------------|-------------|-------|
| I | Simplicity (stdlib preferred; each new dependency justified) | PASS with justification | Owner-specified stack: three runtime dependencies (`selenium`, `beautifulsoup4`, `requests`) each justified in the Complexity Tracking table and research.md; test stack remains stdlib-only (`unittest`); single script, no framework. |
| II | Reliable Downloads | PASS by design | Bounded retries (3 attempts, backoff), per-request timeouts, atomic temp-file-then-rename writes, magic-byte format validation (CDN provides no checksums), non-zero exit when source unreachable after retries. |
| III | Safe Filesystem Writes | PASS by design | Default never overwrites; deterministic documented output path (`<Pictures>/StarWarsBackground/<NN>-<title>.<ext>`); idempotent re-runs skip existing files; `--overwrite` is the only overwrite path. |
| IV | Test-First | PASS (process gate) | Tests written before implementation for parser, downloader, filesystem behavior, and CLI exit codes; network code tested against recorded fixtures / local stub server only. |
| V | Observability | PASS by design | Per-item stdout progress (index/count, title, bytes, destination path); stderr errors include URL, attempt number, error type; plain-text output, no log infrastructure. |
| C1 | Sole source = the article URL | PASS | Article URL is hardcoded; no user-supplied URLs or catalogs accepted (no `--url` flag exists). |
| C2 | No other network requests / no telemetry | PASS with note | Tool-initiated HTTP (requests) targets only the article URL and image URLs linked from it; Selenium's rendered-page fetch may load the page's own sub-resources (CSS/JS/fonts on starwars.com domains), which is inherent to fetching that page in a browser — see research.md R2. No telemetry, analytics, or phone-home behavior. |
| C3 | Common image formats only | PASS by design | JPEG/PNG accepted (validated via magic bytes); anything else rejected with a clear error naming the item, not written to disk. |

**Gate status**: PASS — the owner-specified third-party stack is justified per Principle I in the Complexity Tracking table below and research.md; no other violations. Re-checked after Phase 1: still PASS (contracts and data model introduce no new dependencies or network paths).

## Project Structure

### Documentation (this feature)

```text
specs/001-download-starwars-backgrounds/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── cli.md           # CLI contract: invocation, flags, exit codes, stdout/stderr format
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
starwars_backgrounds.py      # Single CLI script: page acquisition, parsing, downloading, filesystem writes, reporting
requirements.txt             # Pinned runtime dependencies (selenium, beautifulsoup4, requests)

tests/
├── fixtures/
│   └── article.html         # Recorded rendered HTML of the source article (gallery markup preserved)
└── unit/
    ├── test_article_parser.py   # Gallery extraction from recorded HTML via bs4
    ├── test_downloader.py       # Retry, timeout, atomic write, format validation (stub server)
    ├── test_output_paths.py     # Pictures-dir resolution, filename derivation, idempotency
    └── test_cli.py              # Exit codes and stdout/stderr contract
```

**Structure Decision**: Single-project CLI layout. The constitution mandates a small surface area and the spec assumes "a single command-line script with no configuration files", so the implementation is one importable module at the repository root (`starwars_backgrounds.py`) plus a `tests/` tree and a pinned `requirements.txt`. No `src/` package, no services/models split — that structure would add indirection without benefit at this scale.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Constitution Principle I requires justification for every dependency beyond the standard library. The owner-specified stack introduces three runtime dependencies:

| Dependency | Why Needed | Simpler Alternative Rejected Because |
|------------|------------|---------------------------------------|
| `selenium==4.50.0` | Acquires the article as a rendered page in a real headless browser, so gallery extraction reflects exactly what users see and remains robust to client-side rendering changes or bot mitigation on starwars.com. | Stdlib/requests-only HTML fetch rejected because the owner mandated Selenium; raw-HTML fetching also couples the tool to today's server-rendered markup rather than the rendered DOM. |
| `beautifulsoup4==4.15.0` | Parses the rendered article HTML to extract `<figure><img>` gallery items (URL + title) with tolerant, readable selectors. | Stdlib `html.parser` rejected because the owner mandated BeautifulSoup4; bs4's selector API is materially simpler and more robust for this extraction than hand-rolling an `HTMLParser` state machine. |
| `requests==2.34.2` | Downloads each image with explicit connect/read timeouts, bounded retries, and streamed-to-temp-file writes that support atomic rename (Constitution II). | Stdlib `urllib.request` rejected because the owner mandated Requests; urllib offers no built-in retry/backoff semantics and weaker timeout control for a bulk downloader. |
| `platformdirs` | Resolves the user's platform-standard Pictures directory across Windows, macOS, and Linux via `user_pictures_dir()`. Owner-directed adoption (2026-10-02) replacing manual path resolution; provides correct XDG/Known-Folders semantics without hand-rolling OS-specific logic. | Stdlib-only resolution rejected after owner directive to use platformdirs for correctness across all three platforms with a single call. |

Test stack remains standard-library-only (`unittest`, `http.server`) — no test-framework dependency is introduced.
