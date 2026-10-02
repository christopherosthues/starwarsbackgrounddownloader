# Quickstart: Star Wars Backgrounds Downloader

**Feature**: `001-download-starwars-backgrounds` | **Date**: 2026-10-01

Runnable validation scenarios that prove the feature works end-to-end. See [contracts/cli.md](./contracts/cli.md) for the full CLI contract and [data-model.md](./data-model.md) for entity/naming rules.

## Prerequisites

- Python 3.9+.
- Dependencies: `pip install -r requirements.txt` (`selenium==4.50.0`, `beautifulsoup4==4.15.0`, `requests==2.34.2`).
- A supported web browser (e.g., Chrome) installed on the host; Selenium Manager fetches the matching driver on first run.
- Internet access to `www.starwars.com` and its image CDN (for live scenarios only; automated tests use fixtures/stubs).

## Run the tool

```bash
python starwars_backgrounds.py
```

**Expected outcome**:
1. stdout reports `Found <N> backgrounds in the article.` with N ≥ 50 (99 at time of writing), then one progress line per item (`[i/N] <title> -> <path> (<bytes>)`).
2. The folder `<Pictures>/StarWarsBackground` exists and contains one file per background, named `<NNN>-<sanitized-title>.jpg`.
3. Exit code 0; a summary line reports `0 failed`.

## Validate the download (SC-001, SC-004)

```bash
# Windows
dir "%USERPROFILE%\Pictures\StarWarsBackground" | find /c ".jpg"
# macOS / Linux
ls ~/Pictures/StarWarsBackground | wc -l
```

**Expected**: file count equals the `Found <N>` number from stdout; every file opens as a 1920×1080 JPEG in any standard image viewer. No `.tmp` or partial files remain.

## Validate idempotent re-run (SC-002, FR-007)

```bash
python starwars_backgrounds.py
```

**Expected**: exit code 0; every item reported as `skipped`; existing files' contents and timestamps unchanged; no duplicate files created. Then:

```bash
python starwars_backgrounds.py --overwrite
```

**Expected**: all items re-downloaded (`saved`), same file names, exit code 0.

## Validate failure behavior (SC-003, FR-006/FR-010)

Simulate an unreachable source by blocking the network or pointing the system at a dead host for `www.starwars.com`, then run:

```bash
python starwars_backgrounds.py; echo "exit=$?"
```

**Expected**: stderr contains `ERROR [attempt 3/3] https://www.starwars.com/news/star-wars-backgrounds: ...`; exit code 1; no success summary on stdout.

## Run the automated test suite (Constitution IV)

```bash
python -m unittest discover -s tests -v
```

**Expected**: all tests pass with no network access to live endpoints and no browser launch — parser tests use `tests/fixtures/article.html` through the bs4 extraction function, downloader/CLI tests use a local stub server and temp output directories, and page acquisition is injected as a fixture. Coverage includes: gallery extraction count/uniqueness, retry exhaustion, atomic-write cleanup on failure, format rejection, filename derivation (including duplicate titles), Pictures-folder resolution per platform, skip/overwrite behavior, and exit codes 0/1/2.

## Manual edge-case checks

| Scenario | How to check | Expected |
|----------|--------------|----------|
| Output folder pre-populated with unrelated files | Drop a `notes.txt` into `<Pictures>/StarWarsBackground`, re-run | File untouched; run succeeds |
| Corrupt/unsupported asset | Stub server test serves non-image bytes for one item | Item reported as rejected on stderr, nothing written for it, exit code 1 |
| Duplicate titles in article | Inspect fixture (e.g., multiple "Tatooine" entries) | Distinct `<NNN>-` prefixes; no file overwrites within a run |
