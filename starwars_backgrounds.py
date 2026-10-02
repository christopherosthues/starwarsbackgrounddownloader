"""Star Wars Backgrounds Downloader.

Downloads all Star Wars background images from the StarWars.com article
gallery into <Pictures>/StarWarsBackground.
"""

import argparse
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import platformdirs
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver as Chrome

__version__ = "1.1.0"

ARTICLE_URL = "https://www.starwars.com/news/star-wars-backgrounds"
LUMIERE_CDN_PREFIX = "https://lumiere-a.akamaihd.net/v1/images/"
CONNECT_TIMEOUT = 30
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1


def _sleep(seconds: float) -> None:
    """Sleep wrapper (mockable in tests)."""
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# T004: Data model entities (data-model.md)
# ---------------------------------------------------------------------------

class Format(Enum):
    """Supported image formats."""

    JPEG = "jpeg"
    PNG = "png"

    @property
    def extension(self) -> str:
        """File extension for this format (".jpg" or ".png")."""
        return ".jpg" if self is Format.JPEG else ".png"


class ItemStatus(Enum):
    """Outcome status of a processed item."""

    PENDING = "pending"
    SAVED = "saved"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class BackgroundImage:
    """One downloadable image from the article's gallery."""

    position: int  # 1-based gallery order
    title: str  # figure alt text, verbatim
    source_url: str  # lumiere CDN URL with query string stripped
    format: Format | None = None  # determined by magic bytes after download
    destination_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            self.title = f"background-{self.position}"


@dataclass
class ItemResult:
    """Outcome of processing one BackgroundImage in a run."""

    image: BackgroundImage
    status: ItemStatus = ItemStatus.PENDING
    bytes_downloaded: int = 0
    error: str | None = None


@dataclass
class DownloadRun:
    """One invocation of the tool; summarized to stdout at exit."""

    total_found: int = 0
    items: list[ItemResult] = field(default_factory=list)
    bytes_downloaded: int = 0
    exit_status: int = 0


# ---------------------------------------------------------------------------
# T005: Cross-platform Pictures directory resolution (research.md R4)
# ---------------------------------------------------------------------------

def resolve_output_root() -> Path:
    """Resolve <Pictures>/StarWarsBackground and create it if needed.

    Uses platformdirs to determine the user's Pictures directory across
    Windows, macOS, and Linux (research.md R4).

    Returns:
        Path to <Pictures>/StarWarsBackground (created if absent).
    """
    pictures = Path(platformdirs.user_pictures_dir())
    output_root = pictures / "StarWarsBackground"
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


class OutputDirectoryError(Exception):
    """Raised when a user-provided output directory is unusable."""


def resolve_output_dir(cli_value: str | None = None) -> Path:
    """Resolve and validate the effective output directory.

    When cli_value is None (no --output-dir given), falls back to the
    default <Pictures>/StarWarsBackground folder unchanged. Otherwise:
      - expand ~, resolve relative values against the current working
        directory, normalize to an absolute path;
      - create missing directories including parents;
      - raise OutputDirectoryError if the value names an existing file
        or the directory cannot be created.

    Args:
        cli_value: Raw --output-dir value, or None when absent.

    Returns:
        Absolute Path to the effective output directory (created).

    Raises:
        OutputDirectoryError: If the target is unusable; message names
            the offending path and reason per contracts/cli.md.
    """
    if cli_value is None:
        return resolve_output_root()

    target = Path(os.path.expanduser(cli_value))
    if not target.is_absolute():
        target = Path.cwd() / target

    if target.exists() and not target.is_dir():
        raise OutputDirectoryError(
            f"{target}: not a directory — cannot use as output location"
        )

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OutputDirectoryError(f"{target}: {e}") from e

    return target


def _output_dir_arg(value: str) -> str:
    """argparse type for --output-dir; rejects blank values (exit 2)."""
    if not value.strip():
        raise argparse.ArgumentTypeError("must be a non-empty directory path")
    return value


# ---------------------------------------------------------------------------
# T006: Deterministic filename derivation (data-model.md naming rule)
# ---------------------------------------------------------------------------

def derive_filename(position: int, title: str, fmt: Format) -> str:
    """Derive the deterministic file name for a background image.

    Rule (data-model.md):
      1. Prefix: NNN = zero-padded 3-digit gallery position (e.g., "007").
      2. Stem: title lowercased; every run of characters outside [a-z0-9]
         collapsed to a single "-"; leading/trailing "-" removed;
         truncated to 60 chars at the last safe boundary.
      3. Extension: ".jpg" for JPEG, ".png" for PNG (from validated format).

    The position prefix guarantees global uniqueness within a run.

    Args:
        position: 1-based gallery position.
        title: Raw title text from the article.
        fmt: Validated image format.

    Returns:
        File name string, e.g., "007-tatooine.jpg".
    """
    prefix = f"{position:03d}"

    # Sanitize: lowercase, collapse non-alphanumerics to single hyphen
    stem = title.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem)
    stem = stem.strip("-")

    # Truncate to 60 chars at last safe boundary (don't cut mid-hyphen-group)
    if len(stem) > 60:
        truncated = stem[:60]
        # Ensure we don't end with a dangling hyphen from truncation
        truncated = truncated.rstrip("-")
        stem = truncated

    return f"{prefix}-{stem}{fmt.extension}"


# ---------------------------------------------------------------------------
# T009: Selenium page acquisition (research.md R2)
# ---------------------------------------------------------------------------

def fetch_article_html() -> str:
    """Fetch the article as rendered HTML using a headless browser.

    Launches a headless Chrome instance via Selenium 4, navigates to the
    article URL with bounded retries and backoff, waits for document
    readiness, and returns driver.page_source.

    Returns:
        The full rendered HTML source of the article page.

    Raises:
        Exception: If the page cannot be reached after bounded retries.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        driver = None
        try:
            driver = Chrome(options=options)
            driver.get(ARTICLE_URL)
            html = driver.page_source
            return html
        except Exception as e:  # pylint: disable=broad-exception-caught
            last_error = e
        finally:
            if driver is not None:
                driver.quit()
        if attempt < MAX_ATTEMPTS:
            backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            _sleep(backoff)

    raise RuntimeError(
        f"attempt {MAX_ATTEMPTS}/{MAX_ATTEMPTS} {ARTICLE_URL}: "
        f"{type(last_error).__name__} after retries: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# T010: Gallery parsing with BeautifulSoup4 (research.md R1)
# ---------------------------------------------------------------------------

def parse_gallery(html: str) -> list[BackgroundImage]:
    """Extract all background images from the rendered article HTML.

    Selects <figure><img> elements where src is a lumiere CDN JPEG URL,
    strips query strings for canonical full-resolution URLs, and returns
    BackgroundImage items in gallery order.

    Args:
        html: Rendered HTML string of the article page.

    Returns:
        List of BackgroundImage items (position 1-based, unique source_urls).
    """
    soup = BeautifulSoup(html, "html.parser")
    figures = soup.select("figure img[src]")

    items: list[BackgroundImage] = []
    position = 0

    for img in figures:
        src = img.get("src", "")
        # Strip query string first, then validate
        clean_src = src.split("?")[0]
        if not clean_src.startswith(LUMIERE_CDN_PREFIX):
            continue
        if not clean_src.endswith(".jpeg"):
            continue

        position += 1
        source_url = clean_src
        title = img.get("alt", "").strip()

        items.append(BackgroundImage(
            position=position,
            title=title,
            source_url=source_url,
        ))

    return items


# ---------------------------------------------------------------------------
# T011: Image download with requests (research.md R3/R5/R6)
# ---------------------------------------------------------------------------

def _detect_format(data: bytes) -> Format | None:
    """Detect image format from magic bytes. Returns None if unrecognized."""
    if data[:3] == b"\xff\xd8\xff":
        return Format.JPEG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return Format.PNG
    return None


def _download_single(
    clean_url: str,
    dest_dir: Path,
    position: int,
    total: int,
    title: str,
) -> tuple[Format, int]:
    """Perform a single download attempt (no retry).

    Downloads the image, validates magic bytes, writes atomically.
    Raises requests exceptions on network failure, ValueError on format rejection.
    """
    tmp_path: Path | None = None
    try:
        response = requests.get(clean_url, timeout=CONNECT_TIMEOUT)
        response.raise_for_status()
        data = response.content

        # Detect format from magic bytes (no retry on format error)
        fmt = _detect_format(data)
        if fmt is None:
            raise ValueError(
                f"rejected format — not a recognized JPEG/PNG image "
                f"(item {position}: {title}, URL: {clean_url})"
            )

        # Write to temp file in destination directory (same filesystem for atomic rename)
        fd, tmp_name = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
        os.close(fd)
        tmp_path = Path(tmp_name)

        with open(tmp_path, "wb") as f:
            f.write(data)

        # Atomically replace temp file with final name
        filename = derive_filename(position, title, fmt)
        final_path = dest_dir / filename
        os.replace(tmp_path, final_path)
        tmp_path = None  # Success — no cleanup needed

        # Progress reporting (FR-008, SC-005)
        print(f"[{position}/{total}] {title} -> {final_path} ({len(data)} bytes)")

        return fmt, len(data)

    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def download_image(
    url: str,
    dest_dir: Path,
    position: int = 0,
    total: int = 0,
    title: str = "",
) -> tuple[Format, int]:
    """Download an image from URL with retry logic and atomic write.

    Retries up to MAX_ATTEMPTS times on network errors with exponential
    backoff (1s, 2s). Format rejections are not retried.

    Args:
        url: Full image URL (may include query string; it will be stripped).
        dest_dir: Directory where the final file will be written.
        position: 1-based gallery position (for progress reporting).
        total: Total item count (for progress reporting).
        title: Item title (for progress reporting and filename derivation).

    Returns:
        Tuple of (detected Format, bytes_written).

    Raises:
        Exception: If download fails after all retries or format is not recognized.
    """
    clean_url = url.split("?")[0]

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _download_single(clean_url, dest_dir, position, total, title)
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < MAX_ATTEMPTS:
                backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                _sleep(backoff)

    # All attempts exhausted — raise with full context
    error_type = type(last_error).__name__ if last_error else "UnknownError"
    raise RuntimeError(
        f"attempt {MAX_ATTEMPTS}/{MAX_ATTEMPTS} {clean_url}: "
        f"{error_type} after retries: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# T014: Skip/overwrite logic (FR-007, US2)
# ---------------------------------------------------------------------------

def process_item(
    item: BackgroundImage,
    output_root: Path,
    total: int,
    overwrite: bool = False,
) -> ItemResult:
    """Process a single background image item.

    If the destination file already exists and overwrite is False, skip.
    Otherwise download and atomically write. Returns an ItemResult.

    Args:
        item: The BackgroundImage to process.
        output_root: Directory where files are written.
        total: Total item count (for progress reporting).
        overwrite: If True, re-download even if file exists.

    Returns:
        ItemResult with status SAVED, SKIPPED, or FAILED.
    """
    # Check both possible extensions for idempotency (FR-007)
    dest_jpg = output_root / derive_filename(item.position, item.title, Format.JPEG)
    dest_png = output_root / derive_filename(item.position, item.title, Format.PNG)

    existing_path: Path | None = None
    if dest_jpg.exists():
        existing_path = dest_jpg
    elif dest_png.exists():
        existing_path = dest_png

    # Skip existing files unless --overwrite (FR-007)
    if existing_path is not None and not overwrite:
        print(f"[{item.position}/{total}] {item.title} -> {existing_path} (skipped)")
        return ItemResult(image=item, status=ItemStatus.SKIPPED)

    try:
        _, bytes_written = download_image(
            item.source_url,
            output_root,
            position=item.position,
            total=total,
            title=item.title,
        )
        return ItemResult(
            image=item,
            status=ItemStatus.SAVED,
            bytes_downloaded=bytes_written,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Format stderr ERROR line per contracts/cli.md
        msg = str(e)
        if "attempt" in msg and "/3/" in msg:
            # Network failure after retries
            print(f"ERROR {msg}", file=sys.stderr)
        else:
            # Format rejection or other item-level error
            print(
                f'ERROR item "{item.title}" ({item.source_url}): {msg}',
                file=sys.stderr,
            )
        return ItemResult(image=item, status=ItemStatus.FAILED, error=msg)


# ---------------------------------------------------------------------------
# T012: Main CLI entry point and progress reporting (contracts/cli.md)
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point. Returns exit code (0=success, 1=failure)."""
    parser = argparse.ArgumentParser(
        description="Download all Star Wars backgrounds from the StarWars.com article."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download and replace files that already exist.",
    )
    parser.add_argument(
        "--output-dir",
        type=_output_dir_arg,
        default=None,
        metavar="DIR",
        help=(
            "Directory where images are saved (created if missing; "
            "default: <Pictures>/StarWarsBackground)."
        ),
    )
    args = parser.parse_args()

    # Resolve output directory
    try:
        output_root = resolve_output_dir(args.output_dir)
    except OutputDirectoryError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"ERROR: Cannot create output directory: {e}", file=sys.stderr)
        return 1

    # Fetch article HTML (injectable for tests via module-level override)
    try:
        html = fetch_article_html()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"ERROR [attempt 3/3] {ARTICLE_URL}: {e}", file=sys.stderr)
        return 1

    # Parse gallery
    items = parse_gallery(html)
    if not items:
        print("ERROR: No backgrounds found in the article.", file=sys.stderr)
        return 1

    total = len(items)
    print(f"Found {total} backgrounds in the article.")

    run = DownloadRun(total_found=total)
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for item in items:
        result = process_item(item, output_root, total, overwrite=args.overwrite)
        if result.status == ItemStatus.SAVED:
            downloaded_count += 1
            run.bytes_downloaded += result.bytes_downloaded
        elif result.status == ItemStatus.SKIPPED:
            skipped_count += 1
        else:
            failed_count += 1

    # Summary (contracts/cli.md)
    summary = (
        f"Summary: {downloaded_count} downloaded, "
        f"{skipped_count} skipped, {failed_count} failed. "
        f"Output folder: {output_root}"
    )
    print(summary)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
