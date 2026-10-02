# Implementation Plan: Custom Image Output Directory

**Branch**: `002-custom-image-directory` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-custom-image-directory/spec.md`

## Summary

Additive CLI option to the existing single-script downloader: `--output-dir <path>` lets the user direct downloaded images to any directory of their choosing instead of the default `<Pictures>/StarWarsBackground`. When omitted, behavior is byte-for-byte identical to feature 001. A missing specified directory (including missing parents) is created automatically; a path that exists but is not a directory, or a location that cannot be created, produces an `ERROR` line naming the offending path and exit status 1; an empty/blank value is rejected as a usage error (exit 2). Safe-write rules (no overwrite without `--overwrite`, idempotent re-runs) apply unchanged to custom directories. Implementation touches only `starwars_backgrounds.py` (argparse option + directory resolution/validation) and the existing unit tests; no new dependencies, no new network paths.

## Technical Context

**Language/Version**: Python 3.9+ (unchanged from feature 001; developed/tested locally on Python 3.11.9)

**Primary Dependencies**: None added — stdlib `argparse` and `pathlib` only, both already in use. Existing stack (`selenium`, `beautifulsoup4`, `requests`, `platformdirs`) unchanged (Constitution I: no new third-party packages).

**Storage**: Filesystem only — the effective output directory plus temporary download files inside it (atomic rename). No database, no state files, no configuration files persisting the chosen directory.

**Testing**: `unittest` (stdlib) with the existing local HTTP stub server and recorded HTML fixtures; new unit tests for directory resolution/validation live in `tests/unit/test_output_paths.py` and `tests/unit/test_cli.py`. No browser or network access in unit tests (Constitution IV).

**Target Platform**: Windows, macOS, Linux (unchanged — cross-platform CLI).

**Project Type**: CLI tool — single command-line script at the repository root.

**Performance Goals**: Unchanged from feature 001; directory creation/validation is O(1) and adds no measurable overhead to a run of ~99 images.

**Constraints**: Additive option only (FR-003: default behavior unchanged); safe-write rules apply identically to custom directories (FR-006, Constitution III); relative paths resolve against the current working directory (FR-007); loud failures with non-zero exit for unusable targets (FR-009, Constitution II); CLI is a governance-protected surface — this feature's spec is the amendment and requires a version bump per Governance.

**Scale/Scope**: One new option; one new resolution/validation code path; same single-user, local-machine scale as feature 001 (~99 images per run).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle / Constraint | Gate Result | Notes |
|---|------------------------|-------------|-------|
| I | Simplicity (stdlib preferred; each new dependency justified) | PASS | No new dependencies — `argparse`/`pathlib` are stdlib and already used. Single script remains the only implementation surface. |
| II | Reliable Downloads | PASS by design | Unusable-target failures produce clear errors naming the path with non-zero exit (FR-005, FR-009); atomic writes/cleanup unchanged; no partial files left behind as if complete. |
| III | Safe Filesystem Writes | PASS by design | Default output path unchanged and documented; custom directories inherit skip-existing/idempotent semantics (FR-006); existing files in a custom directory are never overwritten without `--overwrite`. |
| IV | Test-First | PASS (process gate) | Tests written before implementation for option parsing, directory creation/validation, error taxonomy, and idempotency against custom directories; no live network or browser in unit tests. |
| V | Observability | PASS by design | Per-item progress already prints the destination path; with a custom directory every reported path reflects the effective (resolved) output directory (FR-007); errors name the offending path. |
| C1 | Sole source = the article URL | PASS | Option affects only where images are saved, not what is fetched; no user-supplied URLs introduced. |
| C2 | No other network requests / no telemetry | PASS | Directory resolution/validation is purely local filesystem work; no new network paths. |
| C3 | Common image formats only | PASS | Format validation unchanged and applies identically inside custom directories. |

**Gate status**: PASS — no violations; nothing to justify in Complexity Tracking. Re-checked after Phase 1: still PASS (contracts, data model, and quickstart introduce no new dependencies, network paths, or write behavior).

## Project Structure

### Documentation (this feature)

```text
specs/002-custom-image-directory/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
    └── cli.md           # Amended CLI contract: --output-dir option, exit codes, guarantees
```

### Source Code (repository root)

```text
starwars_backgrounds.py      # Add --output-dir option; replace resolve_output_root() usage with effective-directory resolution/validation
tests/
├── fixtures/
│   └── article.html         # Unchanged (shared fixture from feature 001)
└── unit/
    ├── test_article_parser.py   # Unchanged
    ├── test_downloader.py       # Unchanged
    ├── test_output_paths.py     # Extended: custom directory resolution, creation, error taxonomy
    └── test_cli.py              # Extended: --output-dir parsing, usage errors, exit codes
```

**Structure Decision**: Single-project CLI layout inherited from feature 001 — one importable module at the repository root plus a `tests/` tree. This feature adds no modules; it extends argument handling and directory resolution inside `starwars_backgrounds.py` and extends two existing test files. The README's Options table is updated as part of implementation to keep documented usage in sync with the protected CLI contract.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — this feature adds no dependencies, projects, or abstractions beyond the existing single-script design.
