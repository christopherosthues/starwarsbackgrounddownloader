# Quickstart: Temp-Staged Downloads with Hash Deduplication

**Feature**: `004-temp-staged-downloads` | **Date**: 2026-11-05

Runnable validation scenarios that prove the feature works end-to-end. See [contracts/cli.md](./contracts/cli.md) for the amended CLI contract, [data-model.md](./data-model.md) for entity rules and state transitions, and [research.md](./research.md) for design decisions. Feature 001's quickstart scenarios remain valid where they do not conflict with this feature (naming rule and summary vocabulary are amended).

## Prerequisites

- Same as feature 001: Python 3.10+, `pip install -r requirements.txt`, a supported browser for the Selenium article fetch, and (for live scenarios) internet access to `www.starwars.com` and its image CDN.
- A scratch location for test directories, e.g., an empty folder you can delete afterwards.
- Access to the system temp directory (`<Temp>/swbdl/...`) — no special setup needed; it is created and deleted by the tool itself.

## Scenario 1: Fresh run into a scratch directory (FR-002, FR-003, SC-002)

```bash
python starwars_backgrounds.py --output-dir bg-test; echo "exit=$?"
```

**Expected**: exit code 0; during the download phase every progress line shows a destination inside `<Temp>/swbdl/<datetime>` with byte counts; after the move phase every saved file name is the base name from its source URL (not `NNN-title`); the summary reports moved/duplicates-discarded/failed counts and the scratch directory as output folder. Afterwards `<Temp>/swbdl` no longer exists (FR-005).

## Scenario 2: Idempotent re-run — target unchanged, all duplicates discarded (FR-001, FR-007, SC-001)

```bash
# Record state before the second run
find bg-test -type f | sort > before.txt   # Windows: dir /b bg-test > before.txt
python starwars_backgrounds.py --output-dir bg-test; echo "exit=$?"
find bg-test -type f | sort > after.txt    # Windows: dir /b bg-test > after.txt
```

**Expected**: exit code 0; every item is reported as `duplicate (hash match)` in the move phase; summary reports `0 moved, N duplicates discarded, 0 failed`; `before.txt` and `after.txt` are identical — no new, modified, or overwritten files. `<Temp>/swbdl` deleted again.

## Scenario 3: Deleted file is restored on re-run (stateless dedup)

```bash
rm bg-test/<some-name>.jpg        # Windows: del bg-test\<some-name>.jpg
python starwars_backgrounds.py --output-dir bg-test; echo "exit=$?"
```

**Expected**: exit code 0; exactly one item is moved (the deleted file, restored under its URL-derived name); all others discarded as duplicates. Because no persistent state exists, the tool converges back to the complete collection.

## Scenario 4: Name collision resolves via sequential postfix (FR-006, SC-004)

```bash
# Pre-create a colliding file with unrelated content
echo "not an image" > bg-test/<some-name>.jpg
python starwars_backgrounds.py --output-dir bg-test; echo "exit=$?"
```

**Expected**: exit code 0; the pre-existing `<some-name>.jpg` is untouched (its content differs, so no hash match); the downloaded image is saved as `<some-name>-1.jpg`. With `name-1.jpg` also pre-created, the next run saves `<some-name>-2.jpg` — numbering continues to the next free slot.

## Scenario 5: Throttling option (FR-009)

```bash
python starwars_backgrounds.py --help
python starwars_backgrounds.py --output-dir bg-test --delay 0; echo "exit=$?"
python starwars_backgrounds.py --delay -1; echo "exit=$?"
```

**Expected**: `--help` lists `--delay <seconds>` with the 0.2 default; `--delay 0` runs without inter-request pauses and exits 0; a negative value produces an argparse usage error on stderr with exit code 2 and no downloads started. A timed run at the default delay completes in under 2 minutes for ~100 images.

## Scenario 6: Best-effort moves on partial failure (FR-004, FR-008)

Covered by unit tests against the stub server (no live network needed): one image URL returns HTTP 500 after retries while others succeed.

**Expected**: successful images are moved to the target directory; the failing item prints an `ERROR` line with its URL, attempt count, and error type on stderr; exit code is 1; `<Temp>/swbdl` is deleted including the staged file for the failed item. Re-running restores the missing image (Scenario 3 behavior).

## Scenario 7: Stale temp folder from an interrupted run (edge case)

```bash
mkdir -p <Temp>/swbdl/20260101-000000 && touch <Temp>/swbdl/stale.jpg
python starwars_backgrounds.py --output-dir bg-test; echo "exit=$?"
```

**Expected**: exit code 0; the stale `stale.jpg` is gone — `<Temp>/swbdl` was cleaned before the fresh run started and deleted again after it finished.

## Run the automated test suite (Constitution IV)

```bash
python -m unittest discover -s tests -v
```

**Expected**: all tests pass with no live network or browser launch. New coverage includes: URL base-name extraction and fallback naming, sequential postfix resolution against pre-existing and same-run files, hash deduplication discards (including same-hash-different-name), streaming hash computation on large content, temp staging creation/stale-cleanup/post-run deletion, `--delay` parsing/validation/throttling, best-effort moves with per-item error reporting, exit codes 0/1/2, and the two-phase summary format.

## Manual edge-case checks

| Scenario | How to check | Expected |
|----------|--------------|----------|
| Unwritable target during move phase | Point `--output-dir` at a path that becomes read-only after creation (or run as non-privileged user against a protected folder) | `ERROR` naming the path and reason on stderr; exit code 1; `<Temp>/swbdl` deleted entirely — re-run redownloads everything cleanly (clarification Q1) |
| Same content, different names in one article | Covered by fixture-based unit tests | One copy kept under its original link-derived name; later same-hash items discarded as duplicates |
| URL with no recognizable file name | Fixture with a query-only or extension-less CDN URL | Fallback `<NNN>-<sanitized-title>.<ext>` naming, run succeeds |
| Unrelated files in target directory | Drop `notes.txt` into the scratch dir before running | File untouched; not hashed as an image candidate beyond its content hash; run succeeds |
