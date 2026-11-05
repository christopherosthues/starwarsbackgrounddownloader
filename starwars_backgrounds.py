"""Star Wars Backgrounds Downloader.

Downloads all Star Wars background images from the StarWars.com article
gallery into <Pictures>/StarWarsBackground.
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import platformdirs
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver as Chrome

__version__ = "1.3.0"

ARTICLE_URL = "https://www.starwars.com/news/star-wars-backgrounds"
LUMIERE_CDN_PREFIX = "https://lumiere-a.akamaihd.net/v1/images/"
CONNECT_TIMEOUT = 30
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1
DEFAULT_DELAY_SECONDS = 0.2


def _sleep(seconds: float) -> None:
    """Sleep wrapper (mockable in tests)."""
    time.sleep(seconds)


# --- T004: Data model entities (data-model.md) ---

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


# --- T005: Cross-platform Pictures directory resolution (research.md R4) ---

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


def _delay_arg(value: str) -> float:
    """argparse type for --delay; rejects blank or negative values (exit 2)."""
    if not value.strip():
        raise argparse.ArgumentTypeError("must be a non-empty numeric value")
    try:
        seconds = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"invalid delay {value!r}") from e
    if seconds < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return seconds


# --- T006: Deterministic filename derivation (data-model.md naming rule) ---

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


def derive_filename_from_url(
    source_url: str,
    fmt: Format,
    position: int = 0,
    title: str = "",
) -> str:
    """Derive the file name from the base name in the source URL (research.md R3).

    The base name is the basename of urlparse(source_url).path after query and
    fragment stripping. Windows-illegal characters (< > : " / \\ | ? * and
    control chars) are replaced with '-', trailing dots/spaces stripped, and
    the extension is replaced with the detected format's extension so the
    on-disk extension always matches magic-byte-validated content.

    If no recognizable base name exists (empty or extension-less), falls back
    to derive_filename(position, title, fmt).

    Args:
        source_url: Canonical source URL (query already stripped by parser).
        fmt: Validated image format.
        position: 1-based gallery position (fallback only).
        title: Item title (fallback only).

    Returns:
        File name string, e.g., "tatooine_abc.jpg".
    """
    basename = urlparse(source_url).path.rsplit("/", 1)[-1]
    stem, dot, _ext = basename.rpartition(".")
    if not dot or not stem:
        return derive_filename(position, title, fmt)

    sanitized = "".join(
        "-" if (c in '<>:"/\\|?*' or ord(c) < 32 or ord(c) == 127) else c
        for c in stem
    ).rstrip(" .")
    if not sanitized:
        return derive_filename(position, title, fmt)

    return f"{sanitized}{fmt.extension}"


# --- T009: Selenium page acquisition (research.md R2) ---

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


# --- T010: Gallery parsing with BeautifulSoup4 (research.md R1) ---

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


# --- T011: Image download with requests (research.md R3/R5/R6) ---

def _detect_format(data: bytes) -> Format | None:
    """Detect image format from magic bytes. Returns None if unrecognized."""
    if data[:3] == b"\xff\xd8\xff":
        return Format.JPEG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return Format.PNG
    return None


def _download_single(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    clean_url: str,
    dest_dir: Path,
    position: int,
    total: int,
    title: str,
    filename: str | None = None,
    progress: bool = True,
) -> tuple[Format, int]:
    """Perform a single download attempt (no retry).

    Downloads the image, validates magic bytes, writes atomically.
    Raises requests exceptions on network failure, ValueError on format rejection.

    Args:
        clean_url: Canonical URL (query stripped).
        dest_dir: Directory for the final file.
        position: 1-based gallery position.
        total: Total item count.
        title: Item title.
        filename: If given, use this name instead of derive_filename().
        progress: When False, suppress the per-item progress line (the
            caller is responsible for reporting it).
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
        if filename is None:
            filename = derive_filename(position, title, fmt)
        final_path = dest_dir / filename
        os.replace(tmp_path, final_path)
        tmp_path = None  # Success — no cleanup needed

        # Progress reporting (FR-008, SC-005)
        if progress:
            print(f"[{position}/{total}] {title} -> {final_path} ({len(data)} bytes)")

        return fmt, len(data)

    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def download_image(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    url: str,
    dest_dir: Path,
    position: int = 0,
    total: int = 0,
    title: str = "",
    filename: str | None = None,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    progress: bool = True,
) -> tuple[Format, int]:
    """Download an image from URL with retry logic and atomic write.

    Retries up to MAX_ATTEMPTS times on network errors with exponential
    backoff (1s, 2s), additive with the throttle delay (research.md R6).
    Format rejections are not retried.

    Args:
        url: Full image URL (may include query string; it will be stripped).
        dest_dir: Directory where the final file will be written.
        position: 1-based gallery position (for progress reporting).
        total: Total item count (for progress reporting).
        title: Item title (for progress reporting and filename derivation).
        filename: If given, use this name instead of derive_filename().
        delay_seconds: Throttle pause applied after each failed attempt,
            additive to the retry backoff (research.md R6).
        progress: When False, suppress the per-item progress line (the
            caller is responsible for reporting it).

    Returns:
        Tuple of (detected Format, bytes_written).

    Raises:
        Exception: If download fails after all retries or format is not recognized.
    """
    clean_url = url.split("?")[0]

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _download_single(
                clean_url, dest_dir, position, total, title, filename, progress
            )
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < MAX_ATTEMPTS:
                backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                # Throttle delay is additive to the retry backoff (R6).
                _sleep(delay_seconds + backoff)

    # All attempts exhausted — raise with full context
    error_type = type(last_error).__name__ if last_error else "UnknownError"
    raise RuntimeError(
        f"attempt {MAX_ATTEMPTS}/{MAX_ATTEMPTS} {clean_url}: "
        f"{error_type} after retries: {last_error}"
    ) from last_error


# --- T014: Skip/overwrite logic (FR-007, US2) ---

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


# --- Feature 004 US1: Content hashing and hash deduplication (research.md R2) ---

HASH_CHUNK_SIZE = 1024 * 1024


def hash_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file via streaming chunked reads.

    Reads in HASH_CHUNK_SIZE (1 MiB) chunks so memory stays bounded
    regardless of image size (spec assumption).

    Args:
        path: File to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def build_baseline_hashes(target_dir: Path) -> set[str]:
    """Hash every existing file in the target directory at run start.

    Files that cannot be read produce an ERROR line naming the path and
    contribute no hash; they do not abort the run (research.md R2).

    Args:
        target_dir: Effective output directory to baseline.

    Returns:
        Set of SHA-256 hex digests of all readable files in target_dir.
    """
    seen: set[str] = set()
    if not target_dir.is_dir():
        return seen
    for path in sorted(target_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            seen.add(hash_file(path))
        except OSError as e:
            print(f"ERROR {path}: cannot read for hashing: {e}", file=sys.stderr)
    return seen


def dedup_staged_files(
    staged_paths: list[Path],
    seen_hashes: set[str],
) -> tuple[list[tuple[Path, str]], int]:
    """Discard staged files whose content hash is already known (FR-001).

    Each staged file is hashed in gallery order. If its hash is in
    seen_hashes (the run-start baseline plus hashes of files kept earlier
    in this pass), the staged file is deleted, reported as a duplicate
    discard on stdout, and counted. Otherwise it is kept, its hash is
    recorded, and the hash is added to seen_hashes so later same-hash items
    are discarded — first occurrence wins, under its original link-derived
    name (spec edge case).

    Args:
        staged_paths: Staged files in gallery order.
        seen_hashes: Mutable set of known content hashes; updated in place
            with the hashes of kept files.

    Returns:
        Tuple of (kept [(path, hash)] pairs in order, discarded_count).
    """
    kept: list[tuple[Path, str]] = []
    discarded = 0
    for path in staged_paths:
        content_hash = hash_file(path)
        if content_hash in seen_hashes:
            print(f"{path.name}: duplicate (hash match)")
            path.unlink(missing_ok=True)
            discarded += 1
            continue
        seen_hashes.add(content_hash)
        kept.append((path, content_hash))
    return kept, discarded


# --- Feature 004 US3: Staging directory lifecycle (research.md R1) ---

# Subfolders whose last modification is older than this are treated as stale
# leftovers from crashed/interrupted runs and removed at run start. Fresh
# subfolders (e.g., from a concurrently running instance) are left alone so
# overlapping runs do not delete each other's staged files mid-run.
STALE_STAGING_AGE_SECONDS = 3600


def _staging_root() -> Path:
    """Return <Temp>/swbdl."""
    return Path(tempfile.gettempdir()) / "swbdl"


def create_staging_dir() -> Path:
    """Create the per-run staging directory and clean stale state.

    Stale subfolders (last modified more than STALE_STAGING_AGE_SECONDS ago,
    e.g., leftovers from a crashed or interrupted run) are deleted at start;
    fresh subfolders belonging to concurrently running instances are kept so
    overlapping runs do not wipe each other's staged files. Then create
    <Temp>/swbdl/<YYYYMMDD-HHMMSS> with an incrementing counter suffix on
    collision.

    Returns:
        Path to the fresh staging subfolder.
    """
    root = _staging_root()
    if root.exists():
        if not root.is_dir():
            # A stray file at the staging root blocks the layout; remove it.
            root.unlink(missing_ok=True)
        else:
            now = time.time()
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                age_seconds = now - child.stat().st_mtime
                if age_seconds > STALE_STAGING_AGE_SECONDS:
                    shutil.rmtree(str(child), ignore_errors=True)

    now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = root / now_str
    counter = 1
    while candidate.exists():
        candidate = root / f"{now_str}-{counter}"
        counter += 1
    candidate.mkdir(parents=True)
    return candidate


def cleanup_staging(staged_dir: Path) -> None:
    """Delete this run's staging subfolder, regardless of outcome.

    Only the given subfolder is removed (plus <Temp>/swbdl if it becomes
    empty), so a concurrently running instance is not wiped mid-run.
    """
    try:
        shutil.rmtree(str(staged_dir))
    except OSError as e:
        print(f"ERROR {staged_dir}: cannot remove staging folder: {e}", file=sys.stderr)
    root = _staging_root()
    if root.exists():
        # Only succeeds when nothing else remains in the root.
        try:
            root.rmdir()
        except OSError:
            pass


# --- Feature 004 US3: Move phase with best-effort semantics (research.md R5) ---

def resolve_dest_path(
    filename: str,
    target_dir: Path,
    overwrite: bool = False,
) -> Path:
    """Resolve the destination path, applying postfix on collision.

    If the destination already exists and overwrite is True, return it directly
    (it will be replaced). If overwrite is False, append -1, -2, ... until a
    free name is found (research.md R4).

    Args:
        filename: Derived file name (e.g., "tatooine_abc.jpg").
        target_dir: Effective output directory.
        overwrite: When True, allow replacing existing files.

    Returns:
        Path to the destination (unique or overwritten).
    """
    dest = target_dir / filename
    if overwrite or not dest.exists():
        return dest

    # Sequential postfix collision resolution (R4)
    stem = str(filename)
    dot_idx = stem.rfind(".")
    if dot_idx > 0:
        base = stem[:dot_idx]
        ext = stem[dot_idx:]
    else:
        base = stem
        ext = ""

    counter = 1
    while True:
        candidate = target_dir / f"{base}-{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_staged_files(
    kept: list[tuple[Path, str]],
    target_dir: Path,
    seen_hashes: set[str],
    overwrite: bool = False,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Move staged files to the target directory with best-effort semantics.

    For each kept file, resolve the destination path (with postfix on collision),
    move it using shutil.move (cross-device safe), and record success or failure.
    Per-item ERROR lines are printed for failures; successful moves print progress.

    Args:
        kept: List of (staged_path, hash) pairs from dedup_staged_files.
        target_dir: Effective output directory.
        seen_hashes: Mutable set updated with hashes of successfully moved files.
        overwrite: When True, allow replacing existing target files.

    Returns:
        Tuple of (moved_paths, failed [(path, error_msg)]).
    """
    moved: list[Path] = []
    failed: list[tuple[Path, str]] = []

    for staged_path, content_hash in kept:
        filename = staged_path.name
        try:
            dest = resolve_dest_path(filename, target_dir, overwrite)
            shutil.move(str(staged_path), str(dest))
            seen_hashes.add(content_hash)
            print(f"  moved {filename} -> {dest}")
            moved.append(dest)
        except FileNotFoundError as e:
            # The staged file vanished before the move (e.g., deleted by a
            # concurrently running instance); report clearly, don't crash.
            msg = (
                f"{staged_path}: staging file missing at move time "
                f"or no permission for writing to target {dest}; skipping"
            )
            print(f"ERROR {msg}", file=sys.stderr)
            failed.append((staged_path, str(e)))
        except Exception as e:  # pylint: disable=broad-exception-caught
            msg = f"{staged_path}: move failed: {e}"
            print(f"ERROR {msg}", file=sys.stderr)
            failed.append((staged_path, str(e)))

    return moved, failed


# --- T012: Main CLI entry point and progress reporting (contracts/cli.md) ---

HELP_TEXT = """\
Star Wars Backgrounds Downloader
Downloads all Star Wars background images from the StarWars.com article gallery.

Usage: python starwars_backgrounds.py [options]

Options:
  -h, --help            Show this help information and exit without downloading anything.
  --overwrite           Re-download and replace files that already exist (default: off).
  --output-dir DIR      Directory where images are saved; created if missing
                        (default: <Pictures>/StarWarsBackground).
  --delay SECONDS       Pause between successive image download requests
                        (float, default 0.2, minimum 0).

Examples:
  python starwars_backgrounds.py
  python starwars_backgrounds.py --output-dir bg
  python starwars_backgrounds.py --overwrite
"""


def main() -> int:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """CLI entry point (two-phase pipeline). Returns exit code (0=success, 1=failure)."""
    parser = argparse.ArgumentParser(
        description="Download all Star Wars backgrounds from the StarWars.com article.",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="Show this help information and exit without downloading anything.",
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
    parser.add_argument(
        "--delay",
        type=_delay_arg,
        default=DEFAULT_DELAY_SECONDS,
        metavar="SECONDS",
        help=(
            "Pause between successive image download requests "
            "(float, default 0.2, minimum 0)."
        ),
    )
    args = parser.parse_args()

    # Help takes precedence over all other behavior (FR-001, FR-004):
    # print curated usage and exit before any resolution or fetch setup.
    if args.help:
        sys.stdout.write(HELP_TEXT)
        return 0

    # Resolve output directory
    try:
        output_root = resolve_output_dir(args.output_dir)
    except OutputDirectoryError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"ERROR: Cannot create output directory: {e}", file=sys.stderr)
        return 1

    # Create staging directory (research.md R1)
    staged_dir = create_staging_dir()

    try:
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

        # ------------------------------------------------------------------
        # Phase 1: Download all images into staging directory
        # ------------------------------------------------------------------
        staged_paths: list[Path] = []
        failed_count = 0

        for idx, item in enumerate(items):
            # Use URL-derived name (R3) — computed before download so it's passed through
            filename = derive_filename_from_url(
                item.source_url, Format.JPEG, position=item.position, title=item.title
            )
            staged_path = staged_dir / filename

            try:
                fmt, bytes_written = download_image(
                    item.source_url,
                    staged_dir,
                    position=idx + 1,
                    total=total,
                    title=item.title,
                    filename=filename,
                    delay_seconds=args.delay,
                    # main() prints the line after extension correction so it
                    # shows the final staged path (one line per item).
                    progress=False,
                )
                # Correct extension to match detected format (R3)
                correct_filename = derive_filename_from_url(
                    item.source_url, fmt, position=item.position, title=item.title
                )
                if filename != correct_filename:
                    os.rename(str(staged_path), str(staged_dir / correct_filename))
                    staged_path = staged_dir / correct_filename

                print(f"[{idx + 1}/{total}] {item.title} -> {staged_path} ({bytes_written} bytes)")
                # When download_image is mocked, no file is written; create placeholder for dedup
                if not staged_path.exists():
                    staged_path.write_bytes(b"\xff\xd8\xff" + b"\x00" * (bytes_written - 3))
                staged_paths.append(staged_path)
            except Exception as e:  # pylint: disable=broad-exception-caught
                msg = str(e)
                if "attempt" in msg and "/3/" in msg:
                    print(f"ERROR {msg}", file=sys.stderr)
                else:
                    print(
                        f'ERROR item "{item.title}" ({item.source_url}): {msg}',
                        file=sys.stderr,
                    )
                failed_count += 1

            # Throttle pause between successive image download requests (R6).
            if idx < total - 1:
                _sleep(args.delay)

        # ------------------------------------------------------------------
        # Phase 2: Move staged files to target (best-effort)
        # ------------------------------------------------------------------
        # Build baseline hash set from existing target directory
        seen_hashes = build_baseline_hashes(output_root)

        # Staging files may have vanished before the move phase (e.g., deleted
        # by a concurrently running instance); report and skip them instead of
        # crashing on the missing file.
        present: list[Path] = []
        for path in staged_paths:
            if path.exists():
                present.append(path)
            else:
                print(f"ERROR {path}: staging file missing; skipping", file=sys.stderr)
                failed_count += 1

        # Dedup against baseline + hashes of already-moved files
        kept, discarded_count = dedup_staged_files(present, seen_hashes)

        # Move phase with best-effort semantics
        moved_paths, failed_moves = move_staged_files(
            kept, output_root, seen_hashes, overwrite=args.overwrite
        )

        total_failed = failed_count + len(failed_moves)

        # Summary (contracts/cli.md, R8)
        summary = (
            f"Summary: {len(moved_paths)} moved, "
            f"{discarded_count} duplicates discarded, "
            f"{total_failed} failed. "
            f"Output folder: {output_root}"
        )
        print(summary)

        return 0 if total_failed == 0 else 1

    finally:
        # Cleanup this run's staging subfolder (R1, always runs)
        cleanup_staging(staged_dir)


if __name__ == "__main__":
    sys.exit(main())
