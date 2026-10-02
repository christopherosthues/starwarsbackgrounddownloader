# Implementation Plan: Help Flag

**Branch**: `003-add-help-flag` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-add-help-flag/spec.md`

## Summary

Additive CLI feature: the tool gains an explicit `--help` / `-h` flag that displays comprehensive, curated usage information — a one-line description of what the tool does, every public option with its purpose and default value, and at least one example invocation per supported behavior (default run, custom output directory, forced re-download) — then exits with status 0 without performing any download, network request, or filesystem write. Help text is plain ASCII-only stdout; usage errors for unrecognized options or invalid values keep the existing stderr + exit-2 convention and take precedence over help when both are present on the command line. Invocations that do not include the help flag behave exactly as before (FR-007). Implementation touches only `starwars_backgrounds.py` (parser setup, curated help text constant) and the unit tests; no new dependencies, no new network paths. Per Governance, this amends the protected CLI contract: `__version__` bumps 1.1.0 → 1.2.0.

## Technical Context

**Language/Version**: Python (unchanged from feature 001/002; codebase uses PEP 604 unions so effectively requires Python 3.10+, contract entry point per feature 001's CLI contract)

**Primary Dependencies**: None added — stdlib `argparse` only, already in use (Constitution I). Existing stack (`selenium`, `beautifulsoup4`, `requests`, `platformdirs`) unchanged.

**Storage**: N/A for this feature — help invocations perform no filesystem writes and persist no state; existing download-path storage is untouched.

**Testing**: `unittest` (stdlib), run via `python -m unittest discover -s tests`. Help coverage extends the existing convention in `tests/unit/test_cli.py`: patch `sys.argv`, capture stdout/stderr with `io.StringIO`, assert exit codes and output content; help tests additionally assert no network call is attempted and no files are created. No live network or browser (Constitution IV).

**Target Platform**: Windows, macOS, Linux (unchanged — cross-platform CLI). ASCII-only help text guarantees correct rendering on legacy Windows console code pages regardless of terminal encoding (clarification Q1).

**Project Type**: CLI tool — single command-line script at the repository root.

**Performance Goals**: Help invocations complete in under 2 seconds on any machine with zero network requests and zero files written (SC-003); trivially met since help exits before directory resolution or fetch setup.

**Constraints**: Additive flag only; non-help invocations byte-for-byte unchanged (FR-007, SC-005); ASCII-only help text (clarification Q1); existing exit-code conventions preserved — 0 success/help, 1 runtime failure, 2 usage error; CLI is a governance-protected surface — this feature's spec is the amendment and requires a version bump per Governance.

**Scale/Scope**: One new flag pair (`--help`/`-h`) replacing argparse's implicit default help with curated text; one module-level help-text constant; same single-user, local-machine scale as features 001–002.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle / Constraint | Gate Result | Notes |
|---|------------------------|-------------|-------|
| I | Simplicity (stdlib preferred; each new dependency justified) | PASS | No new dependencies — `argparse` is stdlib and already used. Single script remains the only implementation surface; help text is one curated constant, not a framework. |
| II | Reliable Downloads | PASS by design | Help path performs no downloads; existing download/retry/atomic-write paths are untouched (FR-007). |
| III | Safe Filesystem Writes | PASS by design | Help writes nothing — not even the default output folder (edge case: missing default folder is NOT created); non-help invocations unchanged. |
| IV | Test-First | PASS (process gate) | Tests written before implementation for help content (FR-002), ASCII-only text, both flag forms identical (SC-004), precedence over valid options and invalid-value precedence (FR-004), no side effects (SC-003); no live network in unit tests. |
| V | Observability | PASS by design | Help is plain human-readable ASCII text on stdout; usage errors go to stderr naming the offending option with exit 2 — consistent with existing console-output contract. |
| C1 | Sole source = the article URL | PASS | Help path makes no network requests at all; no user-supplied URLs introduced. |
| C2 | No other network requests / no telemetry | PASS | Help works fully offline (edge case); zero new network paths. |
| C3 | Common image formats only | PASS | Format validation untouched; help invocations never reach it. |

**Gate status**: PASS — no violations; nothing to justify in Complexity Tracking. Re-checked after Phase 1: still PASS (contracts, data model, and quickstart introduce no new dependencies, network paths, or write behavior).

## Project Structure

### Documentation (this feature)

```text
specs/003-add-help-flag/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
    └── cli.md           # Amended CLI contract: --help/-h flag, help output format, exit codes
```

### Source Code (repository root)

```text
starwars_backgrounds.py      # Replace implicit argparse -h/--help with explicit flag + curated ASCII-only HELP_TEXT constant; bump __version__ to 1.2.0
tests/
├── fixtures/
│   └── article.html         # Unchanged (shared fixture from feature 001)
└── unit/
    ├── test_article_parser.py   # Unchanged
    ├── test_downloader.py       # Unchanged
    ├── test_output_paths.py     # Unchanged
    └── test_cli.py              # Extended: help flag content, ASCII-only text, both forms identical, precedence rules, no side effects
```

**Structure Decision**: Single-project CLI layout inherited from features 001–002 — one importable module at the repository root plus a `tests/` tree. This feature adds no modules; it changes parser setup and adds one help-text constant inside `starwars_backgrounds.py`, extends `tests/unit/test_cli.py`, and amends `contracts/cli.md`. The README's Options table is updated as part of implementation to keep documented usage in sync with the protected CLI contract.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — this section remains empty per the gate result above.
