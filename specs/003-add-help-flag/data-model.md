# Data Model: Help Flag

**Feature**: `003-add-help-flag` | **Date**: 2026-10-02

This feature introduces one new in-memory entity and no persistent state. All existing entities (`BackgroundImage`, `ItemResult`, `DownloadRun`) are unchanged; help invocations return before a `DownloadRun` is constructed, so they never touch the download data model (FR-001).

## Entity: HelpText (new)

The rendered usage information displayed by `--help`/`-h`. Exists only as in-memory text for the duration of the invocation; it is never persisted.

| Field | Type | Source / Rule |
|-------|------|---------------|
| `description_line` | str | One-line statement of what the tool does (FR-002a). |
| `options` | list of option entries | Every public option: name, short form (if any), purpose, default value stated in human-readable terms (FR-002b, FR-005). |
| `examples` | list of invocations | At least one example per supported behavior: default run, custom output directory, forced re-download (FR-002c). |

**Validation rules**:
- The full rendered text MUST be plain ASCII — every character has code point < 128 (clarification Q1; enforced by unit test).
- Rendered text MUST appear on stdout only; help invocations write nothing to stderr and perform no filesystem writes or network requests (FR-001, FR-006).
- Documented default values MUST match runtime defaults: output directory `<Pictures>/StarWarsBackground`, overwrite off by default (FR-005); drift is caught by unit tests comparing help text against the option definitions.

## Option Definitions (contract source of truth)

The complete set of public CLI options after this feature; both parser registration and `HelpText` derive from this table, so FR-001/SC-001 coverage is verifiable against a single list:

| Option | Short form | Purpose | Default |
|--------|-----------|---------|---------|
| `--help` | `-h` (new) | Display comprehensive usage information and exit with status 0; no download, network request, or filesystem write. | Absent — normal run proceeds when not given. |
| `--overwrite` | — | Re-download and replace files that already exist at their destination path. | Off. |
| `--output-dir <path>` | — | Set the directory where images are saved for this run (created if missing; blank values rejected as a usage error). | `<Pictures>/StarWarsBackground`. |

**Precedence rules (FR-004, clarification Q2)**:
- Help flag + any combination of *valid* options → help text on stdout, exit 0, no side effects.
- Any invalid value or unrecognized option → usage error naming the offending input on stderr, exit 2 — even when `--help` is also present.

## Invariants (unchanged from features 001–002)

- Safe-write rules: existing files are never overwritten without `--overwrite`; re-runs are idempotent; default output path deterministic and documented.
- Exit statuses: 0 success, 1 runtime failure, 2 usage error — help adds no new codes (research.md R3).
- Atomic writes, retry/backoff, format validation, and progress/summary reporting apply only to non-help invocations and are untouched by this feature (FR-007).
