# Contract: Command-Line Interface (Amended)

**Feature**: `003-add-help-flag` | **Date**: 2026-10-02

This contract amends [feature 002's CLI contract](../002-custom-image-directory/contracts/cli.md). Per the constitution's Development Workflow section, public CLI options are a governance-protected surface; this feature's specification is the amendment and the module-level `__version__` constant is bumped to **1.2.0** (research.md R4). Everything not restated here remains in force from features 001–002.

## Invocation

```text
python starwars_backgrounds.py [--overwrite] [--output-dir <path>] [-h | --help]
```

| Element | Contract |
|---------|----------|
| Entry point | `starwars_backgrounds.py` at the repository root, runnable via `python <script>` on Windows/macOS/Linux (unchanged). |
| Positional arguments | None (unchanged). The source article URL is fixed; no user-supplied URLs are accepted. |
| `--overwrite` | Unchanged from feature 001: re-download and replace files that already exist at their destination path. Applies within the effective output directory. |
| `--output-dir <path>` | Unchanged from feature 002: sets the directory where images are saved for this run; relative paths resolve against the current working directory; `~` is expanded; blank values rejected as a usage error; missing directories (including parents) created automatically. |
| `-h` / `--help` (new) | Displays comprehensive usage information on stdout and exits with status 0 without performing any download, network request, or filesystem write — including not creating the default output folder. Both forms are registered explicitly and behave identically (FR-003). See "Help output format" and "Precedence rules". |

## Help output format (new)

The help text is plain, **ASCII-only** text on stdout (clarification Q1; FR-006). It MUST contain:

1. A one-line description of what the tool does (FR-002a).
2. Every public option — `--help`/`-h`, `--overwrite`, `--output-dir <path>` — with its purpose and default value stated in human-readable terms; documented defaults MUST match runtime defaults (`<Pictures>/StarWarsBackground`, overwrite off) (FR-002b, FR-005).
3. At least one example invocation for each supported behavior: default run, custom output directory, forced re-download (FR-002c).

The text is stable and does not depend on terminal size or interactive state; it is safe to pipe or redirect (edge case). Help invocations complete in under 2 seconds with zero network requests and zero files written (SC-003) and work fully offline.

## Precedence rules (new — FR-004, clarification Q2)

| Command line | Behavior | Exit code |
|--------------|----------|-----------|
| `--help` or `-h` alone | Help text on stdout; nothing else happens. | 0 |
| `--help`/`-h` + any combination of valid options (e.g., `--overwrite --output-dir <dir>`) | Help text on stdout; no download, no directory creation, no image writes — regardless of option order. | 0 |
| Any invalid value or unrecognized option, with or without `--help`/`-h` (e.g., `--output-dir "" --help`, `--bogus`) | Usage error on stderr naming the offending input; help is NOT displayed. | 2 |

## Exit codes

Unchanged from feature 002:

| Code | Meaning |
|------|---------|
| 0 | Every background was downloaded successfully or skipped as already present inside the effective output directory — **or** a help invocation completed (new). |
| 1 | Runtime failure: article unreachable after bounded retries; one or more image items failed; zero backgrounds found; `--output-dir` path exists but is not a directory; specified directory could not be created. Each such failure prints an `ERROR` line naming the offending URL or path. |
| 2 | Usage error (unrecognized flag/argument, or blank `--output-dir` value), per `argparse` convention — including when `--help` is also present on the command line. |

## stdout format (progress) and stderr format (errors)

Unchanged from feature 002 for non-help invocations. Help invocations write nothing to stderr; usage errors keep argparse's standard shape (usage line plus an error naming the offending option).

## Guarantees (from spec)

- No network requests other than the article page fetch and image downloads linked from it; no telemetry of any kind — help invocations make **zero** network requests (unchanged guarantee, now explicitly covering the help path).
- Atomic writes: a destination file appears only when complete and validated; failed items leave no partial files (unchanged).
- Re-runs against the same effective output directory are idempotent without `--overwrite` (unchanged).
- Backward compatibility: every command line that does not include a help option produces identical results to pre-feature behavior — same options, defaults, download behavior, and exit statuses (FR-007, SC-005).
