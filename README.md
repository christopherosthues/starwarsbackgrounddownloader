# Star Wars Backgrounds Downloader

**Version 1.3.0**

Downloads all background images from the [StarWars.com backgrounds article](https://www.starwars.com/news/star-wars-backgrounds) into `<Pictures>/StarWarsBackground` (or any directory of your choice with `--output-dir`). Images are first staged in a per-run temp folder (`<Temp>/swbdl/<datetime>`) and then moved to the output folder, so re-runs never accumulate duplicates.

## Prerequisites

- Python 3.9+
- A supported web browser (e.g., Chrome); Selenium Manager fetches the matching driver on first run
- Internet access to `www.starwars.com` and its image CDN

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python starwars_backgrounds.py
```

The tool:

1. Renders the article in a headless browser (Selenium) and extracts every gallery image from the lumiere CDN.
2. Downloads each full-resolution image into the per-run temp staging folder with retries (3 attempts, exponential backoff) and an inter-request delay (`--delay`, default 0.2s).
3. Validates each file by magic bytes (JPEG/PNG only), discards content-hash duplicates of files already in the output directory, and moves every new image atomically into `<Pictures>/StarWarsBackground`.

Progress is printed per item in two phases: `[i/N] <title> -> <staged-path> (<bytes>)` during download, then one line per moved or discarded file, followed by a summary: `Summary: X moved, Y duplicates discarded, Z failed. Output folder: <dir>`.

### Options

| Flag | Description |
|------|-------------|
| `-h`, `--help` | Display comprehensive usage information on stdout and exit 0 without downloading anything, creating directories, or making network requests. Invalid values or unrecognized options still produce a usage error (exit code 2). |
| `--output-dir <path>` | Directory where images are saved. Relative paths resolve against the current working directory; missing directories (including parents) are created automatically. Blank values are rejected with a usage error. Default: `<Pictures>/StarWarsBackground`. |
| `--overwrite` | Re-download and replace files that already exist: a staged image whose name matches an existing output file replaces it instead of receiving a postfix. Content-hash duplicates are still discarded (default: off). |
| `--delay <seconds>` | Pause between successive image download requests (float, default 0.2, minimum 0). Blank or negative values are rejected with a usage error (exit code 2). Retry backoff is unchanged and additive to this delay. |

### Output naming

File names are derived from the base name embedded in each source URL (e.g., `tatooine_abc.jpg`), sanitized for Windows file systems. URLs without a recognizable file name fall back to `<NNN>-<sanitized-title>.jpg`, where `<NNN>` is the zero-padded 3-digit gallery position and titles are lowercased with non-alphanumerics collapsed to single hyphens (truncated to 60 characters). The extension always matches the validated format (`.jpg`/`.png`). If the destination already exists and `--overwrite` is not set, `-1`, `-2`, ... are appended before the extension until the name is unique.

### Behavior

- **Idempotent**: every run re-downloads everything to temp staging; images whose content hash matches an existing output file are discarded as duplicates, so a re-run leaves the output folder byte-for-byte identical. Use `--overwrite` to replace files by name.
- **Temp-staged**: all downloads land in `<Temp>/swbdl/<datetime>` first and are moved into place; the run's staging folder (and `<Temp>/swbdl` once empty) is deleted after every run, including failed runs. Stale subfolders from crashed runs are cleaned up at start, so overlapping instances never delete each other's staged files.
- **Atomic writes**: downloads go to a temp file first and are renamed into place, so partial/corrupt files never remain.
- **Exit codes**: `0` if every item was moved or discarded as a duplicate, `1` on any failure (no backgrounds found, fetch failure after retries, or item-level failures). Errors are printed to stderr as `ERROR ...`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite runs fully offline: the parser uses an HTML fixture, downloads use a local stub server and temp directories, and page acquisition is injected. It covers gallery extraction, retry exhaustion, atomic-write cleanup, format rejection, filename derivation, Pictures-folder resolution per platform, skip/overwrite behavior, and exit codes.

## Project layout

```
starwars_backgrounds.py   # CLI tool (single module)
tests/                    # unittest suite (offline)
specs/001-download-starwars-backgrounds/  # spec, plan, contracts, quickstart
requirements.txt          # selenium, beautifulsoup4, requests, platformdirs
```

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
