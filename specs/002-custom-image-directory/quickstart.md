# Quickstart: Custom Image Output Directory

**Feature**: `002-custom-image-directory` | **Date**: 2026-10-02

Runnable validation scenarios that prove the feature works end-to-end. See [contracts/cli.md](./contracts/cli.md) for the amended CLI contract, [data-model.md](./data-model.md) for entity rules, and [research.md](./research.md) for design decisions. Feature 001's quickstart remains valid for default behavior; the scenarios below focus on the new option.

## Prerequisites

- Same as feature 001: Python 3.9+, `pip install -r requirements.txt`, a supported browser, and (for live scenarios) internet access to `www.starwars.com` and its image CDN.
- A scratch location for test directories, e.g., an empty folder you can delete afterwards.

## Scenario 1: Direct downloads to an existing directory (SC-001, FR-002)

```bash
mkdir custom-bg
python starwars_backgrounds.py --output-dir custom-bg; echo "exit=$?"
```

**Expected**: exit code 0; every progress line's destination path is inside `custom-bg` (absolute); the summary reports `Output folder: <abs-path>/custom-bg`; all images are in `custom-bg`, and zero new files appear in `<Pictures>/StarWarsBackground`.

## Scenario 2: Auto-creation of a missing nested directory (SC-003, FR-004)

```bash
python starwars_backgrounds.py --output-dir deep/nested/dir; echo "exit=$?"
```

**Expected**: exit code 0; `deep/nested/dir` is created along with its parents before any download starts; all images land there. Re-run the same command: every item is reported as `skipped`, exit code 0 (SC-005, FR-006).

## Scenario 3: Default behavior unchanged (SC-002, FR-003)

```bash
python starwars_backgrounds.py; echo "exit=$?"
```

**Expected**: identical to feature 001 — images go to `<Pictures>/StarWarsBackground`, exit code 0. No `--output-dir` anywhere in the invocation means no observable change from pre-feature behavior.

## Scenario 4: Unusable targets fail loudly (SC-004, FR-005/FR-009)

```bash
# Path exists but is a file
touch not-a-dir.txt
python starwars_backgrounds.py --output-dir not-a-dir.txt; echo "exit=$?"

# Blank value
python starwars_backgrounds.py --output-dir ""; echo "exit=$?"
```

**Expected**:
- File target: stderr contains `ERROR <path>: not a directory — cannot use as output location`; exit code 1; `not-a-dir.txt` is untouched and no downloads started.
- Blank value: argparse usage error on stderr; exit code 2; the default folder is NOT used (no fallback).

## Scenario 5: Relative path resolution (FR-007)

```bash
cd /tmp && python <repo>/starwars_backgrounds.py --output-dir ./bg-test
```

**Expected**: images are saved in `/tmp/bg-test` (resolved against the invocation's working directory), and every reported destination path is absolute.

## Scenario 6: Overwrite inside a custom directory (FR-006)

```bash
python starwars_backgrounds.py --output-dir custom-bg --overwrite; echo "exit=$?"
```

**Expected**: all items re-downloaded into `custom-bg` (`saved`, not `skipped`), same file names, exit code 0.

## Run the automated test suite (Constitution IV)

```bash
python -m unittest discover -s tests -v
```

**Expected**: all tests pass with no live network or browser launch. New coverage includes: `--output-dir` parsing and blank-value rejection (exit 2), missing-directory creation (including nested parents), exists-but-is-a-file error (exit 1, file untouched), relative-path resolution against CWD, absolute paths reported in progress output, idempotent re-runs against a custom directory, skip/overwrite semantics inside a custom directory, and default behavior with the option absent.

## Manual edge-case checks

| Scenario | How to check | Expected |
|----------|--------------|----------|
| Custom directory pre-populated with unrelated files | Drop `notes.txt` into the target dir, run with `--output-dir` | File untouched; run succeeds (edge case: unrelated files) |
| Duplicate titles in article | Run against fixture-based tests targeting a custom dir | Distinct `<NNN>-` prefixes; no overwrites within one run |
| Unwritable location | Point `--output-dir` at a read-only volume/path where creation fails | `ERROR <path>: <reason>` on stderr, exit code 1, no partial files |
