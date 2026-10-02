# Star Wars Backgrounds Downloader

Downloads all background images from the [StarWars.com backgrounds article](https://www.starwars.com/news/star-wars-backgrounds) into `<Pictures>/StarWarsBackground` (or any directory of your choice with `--output-dir`).

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
2. Downloads each full-resolution image with retries (3 attempts, exponential backoff).
3. Validates each file by magic bytes (JPEG/PNG only) and writes it atomically to `<Pictures>/StarWarsBackground`.

Progress is printed per item: `[i/N] <title> -> <path> (<bytes>)`, followed by a summary line with downloaded/skipped/failed counts and the output folder.

### Options

| Flag | Description |
|------|-------------|
| `-h`, `--help` | Display comprehensive usage information on stdout and exit 0 without downloading anything, creating directories, or making network requests. Invalid values or unrecognized options still produce a usage error (exit code 2). |
| `--output-dir <path>` | Directory where images are saved. Relative paths resolve against the current working directory; missing directories (including parents) are created automatically. Blank values are rejected with a usage error. Default: `<Pictures>/StarWarsBackground`. |
| `--overwrite` | Re-download and replace files that already exist (default: skip existing files). |

### Output naming

Files are named `<NNN>-<sanitized-title>.jpg` (or `.png`), where `<NNN>` is the zero-padded 3-digit gallery position. Titles are lowercased, non-alphanumerics collapsed to single hyphens, and truncated to 60 characters. The position prefix guarantees uniqueness even for duplicate titles.

### Behavior

- **Idempotent**: re-running skips files that already exist; use `--overwrite` to force re-download.
- **Atomic writes**: downloads go to a temp file first and are renamed into place, so partial/corrupt files never remain.
- **Exit codes**: `0` if all items succeeded or were skipped, `1` on any failure (no backgrounds found, fetch failure after retries, or item-level failures). Errors are printed to stderr as `ERROR ...`.

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
