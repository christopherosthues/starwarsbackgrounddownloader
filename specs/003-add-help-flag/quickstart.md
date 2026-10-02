# Quickstart: Help Flag

**Feature**: `003-add-help-flag` | **Date**: 2026-10-02

Runnable validation scenarios that prove the feature works end-to-end. See [contracts/cli.md](./contracts/cli.md) for the amended CLI contract, [data-model.md](./data-model.md) for entity rules and option definitions, and [research.md](./research.md) for design decisions. Features 001–002 quickstarts remain valid for non-help invocations; the scenarios below focus on the new flag.

## Prerequisites

- Same as feature 001: Python (3.10+), `pip install -r requirements.txt`. No browser or internet access is needed for any scenario in this file — help invocations are fully offline.
- A scratch working directory you can delete afterwards, to verify no files are created by help invocations.

## Scenario 1: Comprehensive help (SC-001/SC-002, FR-001/FR-002)

```bash
cd /tmp && mkdir help-check && cd help-check
python <repo>/starwars_backgrounds.py --help; echo "exit=$?"
ls -A
```

**Expected**: exit code 0; stdout contains (a) a one-line description of the tool, (b) every public option (`--help`, `-h`, `--overwrite`, `--output-dir`) with its purpose and default value — including `<Pictures>/StarWarsBackground` as the default directory and overwrite-off as the default behavior, and (c) at least one example invocation for each supported behavior (default run, custom output directory, forced re-download). The scratch directory is still empty: no files created, no default folder created.

## Scenario 2: Short form identical to long form (SC-004, FR-003)

```bash
python <repo>/starwars_backgrounds.py --help > help_long.txt 2>&1; echo "exit=$?"
python <repo>/starwars_backgrounds.py -h > help_short.txt 2>&1; echo "exit=$?"
diff help_long.txt help_short.txt && echo IDENTICAL
```

**Expected**: both exit codes are 0 and `diff` reports the files identical.

## Scenario 3: Help wins over valid options (SC-004, FR-004)

```bash
python <repo>/starwars_backgrounds.py --help --overwrite --output-dir /tmp/help-check/dir; echo "exit=$?"
ls -A /tmp/help-check
```

**Expected**: exit code 0; only help text is displayed (no progress lines, no summary); `/tmp/help-check` contains nothing — the directory was not created and no download started. Re-run with `--help` placed after the other options: identical result.

## Scenario 4: Invalid value takes precedence over help (FR-004, clarification Q2)

```bash
python <repo>/starwars_backgrounds.py --output-dir "" --help; echo "exit=$?"
python <repo>/starwars_backgrounds.py --help --output-dir ""; echo "exit=$?"
python <repo>/starwars_backgrounds.py --bogus --help; echo "exit=$?"
```

**Expected**: all three exit with code 2; stderr contains a usage error naming the offending option (`--output-dir` for the blank value, `--bogus` for the unrecognized flag); no help text is displayed in any of the three runs.

## Scenario 5: ASCII-only output (clarification Q1, FR-006)

```bash
python <repo>/starwars_backgrounds.py --help | python -c "import sys; data = sys.stdin.buffer.read(); assert all(b < 128 for b in data), 'non-ASCII found'; print('ascii-ok')"
```

**Expected**: prints `ascii-ok` — the help text contains no non-ASCII characters and renders identically on any terminal, including legacy Windows console code pages.

## Scenario 6: Offline help (SC-003)

Run Scenario 1 with network access disabled (airplane mode / disconnected interface).

**Expected**: identical output to Scenario 1 — exit code 0 in well under 2 seconds; no network activity, no connection errors.

## Scenario 7: Non-help invocations unchanged (SC-005, FR-007)

```bash
python <repo>/starwars_backgrounds.py --output-dir /tmp/help-check/dir; echo "exit=$?"
```

**Expected**: identical to feature 002's behavior — progress lines and summary on stdout, images saved into the specified directory, exit code 0 (or 1 only on genuine runtime failure). No help text appears unless requested.

## Run the automated test suite (Constitution IV)

```bash
python -m unittest discover -s tests -v
```

**Expected**: all tests pass with no live network or browser launch. New coverage in `tests/unit/test_cli.py` includes: help content requirements (FR-002), ASCII-only assertion, `-h`/`--help` byte-identical output and exit status, precedence over valid options, invalid-value and unrecognized-option precedence (exit 2 with the offending option named), no network/filesystem side effects on help invocations, and unchanged behavior for non-help invocations.
