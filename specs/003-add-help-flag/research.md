# Research: Help Flag

**Feature**: `003-add-help-flag` | **Date**: 2026-10-02

All technical-context unknowns were resolvable from the existing codebase and features 001–002's decisions; no NEEDS CLARIFICATION items remained. The research below records the design decisions this feature makes, with rationale and rejected alternatives.

## R1: Flag mechanism — explicit `-h/--help` on a parser built with `add_help=False`

**Decision**: Build the argparse parser with `add_help=False` and register an explicit `-h/--help` flag (`action="store_true"`). After `parse_args()` succeeds, if the help flag was requested, print the curated help text to stdout and return exit code 0 *before* any directory resolution or fetch setup.

**Rationale**: argparse's implicit default `-h/--help` (a) auto-generates minimal text that cannot satisfy FR-002's required content (defaults in human-readable form plus one example per supported behavior), and (b) is order-dependent: its `HelpAction` fires at the point `-h`/`--help` is encountered during sequential parsing, so `--help --output-dir ""` would print help while `--output-dir "" --help` would raise a usage error. The clarification requires that an invalid value produces a usage error naming the offending option *even if* `--help` is also present (FR-004). With an explicit store_true flag, parsing completes and validates every value first; any invalid value or unrecognized option aborts with argparse's standard usage error (exit 2) regardless of where `--help` appears, while valid combinations always reach the post-parse help check. Both flag forms set the same attribute, so `-h` and `--help` are trivially identical (FR-003, SC-004).

**Alternatives considered**:
- *Keep argparse's implicit `-h/--help` and only enrich its description/epilog*: rejected — auto-generated option text cannot express the human-readable defaults required by FR-005 ("the platform Pictures folder"), examples are not part of `format_help()` output, and the HelpAction's order-dependent firing violates the clarification's precedence rule.
- *Pre-scan `sys.argv` for `-h`/`--help` before parsing*: rejected — duplicates argparse's validation logic (would need to re-validate values separately to honor "invalid value takes precedence"), adding a second source of truth for option definitions; the post-parse check achieves identical semantics with zero extra machinery.

## R2: Help text content and single source of truth

**Decision**: One module-level constant `HELP_TEXT` holding curated, ASCII-only plain text with three parts: (a) a one-line description of what the tool does; (b) every public option (`--help`, `-h`, `--overwrite`, `--output-dir`) with its purpose and default value stated in human-readable terms; (c) at least one example invocation for each supported behavior — default run, custom output directory, forced re-download. FR-005 drift protection is enforced by unit tests asserting that every public option name appears in the text and that the documented defaults match the runtime defaults (default folder `<Pictures>/StarWarsBackground`, no-overwrite-by-default).

**Rationale**: A curated constant is the simplest construct that satisfies FR-002/FR-005 while remaining readable to users (Constitution V: console output is the primary UX). The option set is small and stable; tests, not code generation, guard against drift between documented defaults and runtime behavior.

**Alternatives considered**:
- *Generate help from parser metadata (`parser.format_help()`)*: rejected — auto-generated text omits human-readable default phrasing and examples entirely, forcing awkward workarounds (custom `metavar`/help strings per option) that still cannot produce the examples section required by FR-002(c).
- *Load help text from a file on disk*: rejected — adds a filesystem dependency to every invocation and violates Constitution I; a constant is sufficient for this content size.

## R3: Exit codes and stream contract

**Decision**: No new exit codes are introduced. Help output goes to stdout with exit code 0 (FR-001, FR-006). Usage errors — unrecognized options/arguments and blank `--output-dir` values — keep argparse's standard behavior: usage error on stderr naming the offending input, exit code 2 (existing contract from features 001–002). Runtime failures keep exit code 1.

**Rationale**: The spec's Assumptions state that existing exit-status conventions apply; FR-006 already assigns stdout to help and stderr + non-zero exit to usage errors. Reusing argparse's built-in error path means the "usage error naming the offending option" requirement (FR-004, edge cases) is satisfied by the library rather than hand-rolled message formatting.

**Alternatives considered**:
- *Custom usage-error handling for help-related failures*: rejected — no new failure class exists; argparse's messages already name the offending option and match the contract table.

## R4: Governance bookkeeping for a protected CLI surface

**Decision**: The constitution's Development Workflow section makes public CLI options a governance-protected contract requiring "a spec amendment and a version bump". This feature's specification *is* the amendment (it adds `--help`/`-h` as explicit public options and replaces the pre-feature minimal auto-generated help text with comprehensive curated text). The module-level `__version__` constant introduced in feature 002 is bumped from **1.1.0** to **1.2.0** (MINOR: new public CLI option; per Governance semantic versioning).

**Rationale**: A MINOR bump records the contract change with zero runtime behavior change beyond the feature itself. Note that pre-feature, argparse already exposed a minimal `-h/--help`; post-feature the same flags produce comprehensive curated text — that replacement *is* this feature (SC-005 protects only command lines that do not include a help option).

**Alternatives considered**:
- *PATCH bump*: rejected — adding public CLI options is materially expanding, not clarifying; Governance reserves PATCH for wording fixes.
- *No bump because the flags "already existed" via argparse defaults*: rejected — the contract surface (documented flag semantics + comprehensive output) changes, and feature 002's R5 established that each such change gets a tracked version increment.

## R5: ASCII-only enforcement (clarification Q1)

**Decision**: `HELP_TEXT` is strictly ASCII; a unit test asserts every character in the constant has code point < 128 and that captured help output contains no non-ASCII characters. No runtime stdout reconfiguration is added.

**Rationale**: On Windows, console output encoding follows the active code page (cp1252, GBK, etc.); printing a non-ASCII character can raise `UnicodeEncodeError`, which would make `--help` crash on legacy consoles and violate SC-003 ("exits with status 0 in 100% of invocations"). ASCII-only text renders identically on every terminal (edge case: non-UTF-8 terminals) at zero runtime cost.

**Alternatives considered**:
- *Reconfigure stdout to UTF-8 / `errors="replace"`*: rejected — masks the problem, adds runtime behavior and platform-specific code paths; the help content has no need for non-ASCII characters (Constitution I).

## R6: Test strategy (Constitution IV)

**Decision**: Tests are written before implementation in `tests/unit/test_cli.py`, following its existing convention (`_run_main` helper patching `sys.argv`, capturing stdout/stderr via `io.StringIO`). Coverage per requirement:
- FR-001/SC-003: help exits 0, performs no network call (patched fetch raises if invoked), writes no files (default folder absent before and after; temp CWD unchanged).
- FR-002/SC-001/SC-002: output contains the description line, every public option name, both documented defaults, and at least one example per supported behavior.
- FR-003/SC-004: `-h` and `--help` produce byte-identical stdout and exit status; combined with valid options (`--overwrite --output-dir <tmp>`) still yields help + exit 0.
- FR-004 (clarification Q2): `--output-dir "" --help` and `--help --output-dir ""` both yield a usage error naming the option with exit 2; unrecognized option with and without `--help` yields exit 2.
- FR-005: documented defaults in help text match runtime defaults (asserted against constants/behavior).
- FR-006 + clarification Q1: help on stdout, ASCII-only assertion; usage errors on stderr.
- FR-007/SC-005: existing non-help invocations unchanged — covered by the pre-existing suite passing unmodified.

No live network or browser is used (Constitution IV); no new fixtures are required beyond what `test_cli.py` already defines.

**Alternatives considered**:
- *Separate `tests/unit/test_help.py` module*: rejected in favor of extending `test_cli.py` — help invocations are CLI exit-code/usage behavior, and the existing `_run_main` helper is exactly the needed harness; a new file would duplicate that setup.
