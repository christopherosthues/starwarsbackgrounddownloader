# Implementation Plan: Temp-Staged Downloads with Hash Deduplication

**Branch**: `005-temp-staged-downloads` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-temp-staged-downloads/spec.md`

## Summary

Rework the single-script downloader's pipeline into a two-phase, temp-staged flow: every run first downloads all gallery images into `<Temp>/swbdl/<datetime>`, then moves them to the effective target directory. Saved file names are derived from the base name embedded in the source URL (with deterministic position/title fallback), duplicates across runs are detected by comparing SHA-256 content hashes against existing target files hashed at run start — no persistent state, every run re-fetches everything and discards hash matches — name collisions with existing target files are resolved via sequential postfix (`name.jpg`, `name-1.jpg`, ...), a new configurable `--delay` option (default 0.2s) throttles requests to the source CDN, moves are best-effort (failed items reported individually; non-zero exit on any failure), and `<Temp>/swbdl` is deleted after every run regardless of outcome. Implementation stays inside `starwars_backgrounds.py` plus unit tests; stdlib only (`hashlib`, `tempfile`, `shutil`) — no new third-party dependencies (Constitution I).

## Technical Context

**Language/Version**: Python 3.10+ (existing codebase uses PEP 604 unions at runtime; developed/tested locally on Python 3.14)

**Primary Dependencies**: None added — stdlib `hashlib`, `tempfile`, and `shutil` only. Existing stack (`selenium`, `beautifulsoup4`, `requests`, `platformdirs`) unchanged (Constitution I).

**Storage**: Filesystem only — the per-run temp staging folder `<Temp>/swbdl/<datetime>` plus the effective target directory. No persistent state, manifest, or configuration files between runs (spec clarification: stateless dedup via content hashes computed at run start).

**Testing**: `unittest` (stdlib) with the existing local HTTP stub server and recorded HTML fixtures; new unit tests for URL-derived naming, temp staging lifecycle, hash deduplication, postfix collisions, throttling option, and best-effort moves. No live network or browser in unit tests (Constitution IV).

**Target Platform**: Windows, macOS, Linux (unchanged — cross-platform CLI).

**Project Type**: CLI tool — single command-line script at the repository root.

**Performance Goals**: A ~100-image run completes in under 2 minutes including default throttling (0.2s × ~100 requests ≈ 20s of delay plus transfer time); content hashes are computed with streaming chunked reads so memory stays bounded regardless of image size; one full pass over existing target files per run for baseline hashing.

**Constraints**: No persistent state between runs (spec clarification Q4); temp staging folder deleted after every run, successful or failed (FR-005); best-effort moves with non-zero exit on any item failure (clarification Q5); bounded retries unchanged; CLI options and output file naming rules are governance-protected surfaces — this feature's spec is the amendment and requires a version bump per Governance.

**Scale/Scope**: ~100 images per run, single-user local machine; one new CLI option (`--delay`); pipeline rework inside the existing module (staging, naming, deduplication, move phase).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle / Constraint | Gate Result | Notes |
|---|------------------------|-------------|-------|
| I | Simplicity (stdlib preferred; each new dependency justified) | PASS | No new dependencies — `hashlib`, `tempfile`, and `shutil` are stdlib. Single script remains the only implementation surface. |
| II | Reliable Downloads | PASS by design | Bounded retries with backoff unchanged; files written fully to staging before any move (no partial target writes); `<Temp>/swbdl` deleted after every run including failures; non-zero exit when the source is unreachable after retries or any item fails. |
| III | Safe Filesystem Writes | PASS by design | Existing target files are never overwritten without `--overwrite`; name collisions resolve via sequential postfix instead of replacement; re-runs against a completed set leave the target byte-for-byte identical (hash dedup, FR-007); default output path unchanged and documented. |
| IV | Test-First | PASS (process gate) | Tests written before implementation for URL-derived naming, staging lifecycle/cleanup, hash deduplication, postfix resolution, `--delay` parsing/throttling, best-effort moves, and summary format; stub server and fixtures only — no live network or browser in unit tests. |
| V | Observability | PASS by design | Per-item progress for both phases (staged download path + bytes; moved/discarded destination); ERROR lines on stderr with URL, attempt number, and error type; summary reports moved/discarded/failed counts and the effective output folder. |
| C1 | Sole source = the article URL | PASS | Staging is local filesystem work; no new URLs or catalogs introduced. |
| C2 | No other network requests / no telemetry | PASS | Fetch surface unchanged: article page plus image assets linked from it only. |
| C3 | Common image formats only | PASS | Magic-byte validation (JPEG/PNG) applied to staged content before any move; unrecognized formats rejected with a clear error, extension corrected to the detected format. |

**Gate status**: PASS — no violations; nothing to justify in Complexity Tracking. Re-checked after Phase 1: still PASS (contracts, data model, and quickstart introduce no new dependencies, network paths, or write behavior).

## Project Structure

### Documentation (this feature)

```text
specs/004-temp-staged-downloads/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
    └── cli.md           # Amended CLI contract: URL-derived naming, --delay option, two-phase progress, exit codes
```

### Source Code (repository root)

```text
starwars_backgrounds.py      # Reworked pipeline: temp staging, URL-derived naming, hash dedup, postfix resolution, --delay, best-effort moves
tests/
├── fixtures/
│   └── article.html         # Unchanged (shared fixture from feature 001)
└── unit/
    ├── test_article_parser.py   # Extended: base-name extraction from source URLs + fallback
    ├── test_downloader.py       # Extended: staging writes, --delay between requests
    ├── test_output_paths.py     # Extended: temp staging resolution, stale cleanup, post-run deletion
    ├── test_cli.py              # Extended: --delay parsing/validation, two-phase summary format
    └── test_temp_staging.py     # New: hash deduplication, postfix collisions, best-effort moves, idempotent re-runs
```

**Structure Decision**: Single-project CLI layout inherited from features 001–003 — one importable module at the repository root plus a `tests/` tree. This feature adds no modules; it reworks the download/move pipeline inside `starwars_backgrounds.py`, extends four existing test files, and adds one new test file for the cohesive staging/dedup behavior. The README's Options table is updated as part of implementation to keep documented usage in sync with the protected CLI contract.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — this feature adds no dependencies, projects, or abstractions beyond the existing single-script design; all new behavior uses stdlib modules already permitted by Constitution I.
