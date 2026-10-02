# Research: Star Wars Backgrounds Downloader

**Feature**: `001-download-starwars-backgrounds` | **Date**: 2026-10-01

All NEEDS CLARIFICATION items from the plan's Technical Context were resolved during research; none remain. Findings below are grounded in live inspection of https://www.starwars.com/news/star-wars-backgrounds on 2026-10-01 and reflect the owner-specified tech stack: Python + `selenium==4.50.0`, `beautifulsoup4==4.15.0`, `requests==2.34.2`, stdlib `argparse`/`pathlib`.

## R1. Source page structure and background-image discovery

**Decision**: Parse the rendered article HTML with BeautifulSoup4 (`figure img` selector) and select `<img>` elements that are children of `<figure>` tags whose `src` is a lumiere CDN image URL (`https://lumiere-a.akamaihd.net/v1/images/...jpeg`) — these are exactly the gallery backgrounds. Each figure yields one background: source URL = `src` with any query string stripped; title = `alt` attribute.

**Rationale**: Live inspection (2026-10-01) shows the article contains 99 `<figure><img src="https://lumiere-a.akamaihd.net/v1/images/...jpeg[?region=0,0,1920,1080]" alt="<title>">` blocks — all of them backgrounds (alt texts confirm: "Star Wars virtual background: …" / location names). The page has 107 `<img>` tags total; the remaining 8 are SVG logos/nav icons outside gallery figures. There is no separate full-resolution URL, lightbox data attribute, or anchor wrapping in the markup — the figure `src` is the only image reference (a second copy of each figure exists inside an escaped JSON blob for SEO; parsing real DOM tags avoids double-counting). bs4's selector API makes this extraction a few readable lines and tolerant to attribute reordering.

**Alternatives considered**:
- Regex-only extraction: rejected — fragile against attribute reordering and quote escaping in the page's embedded JSON, and bs4 is mandated by the stack.
- Selecting by URL name pattern (`virtual-background`/`backgrounds-`): rejected as primary rule — 5 of 99 images use other naming (`image_*.jpeg`, `zbg-*.jpeg`) and would be missed; figure + CDN-hosted raster image is the stable, complete selector.
- Stdlib `html.parser`: rejected in favor of mandated BeautifulSoup4 (see plan Complexity Tracking).

## R2. Page acquisition via Selenium (rendered DOM)

**Decision**: A thin page-acquisition layer launches a headless browser with Selenium 4.50.0, navigates to the article URL, waits for document readiness, and returns `driver.page_source` as a string. The parser (R1) consumes that string; nothing else in the tool depends on the driver. Driver binaries are managed by Selenium Manager (built into Selenium 4); a supported browser must be present on the host machine.

**Rationale**: Acquiring the page as rendered guarantees gallery extraction reflects exactly what users see, and stays robust if starwars.com changes server-rendering or adds bot mitigation — the failure mode that would silently break a raw-HTML scraper. Isolating acquisition behind one function keeps the rest of the tool (parser, downloader, filesystem) browser-free and unit-testable with fixtures (Constitution IV).

**Alternatives considered**:
- `requests`-only HTML fetch: rejected because the owner mandated Selenium; it also couples the tool to today's server-rendered markup.
- Driving the browser per-image for downloads: rejected — slow, non-atomic, and no retry/streaming control; image downloading is delegated to Requests (R5).

**Network note (FR-009)**: Tool-initiated HTTP via `requests` targets only the article URL and image URLs linked from it. The Selenium page fetch may additionally load the page's own sub-resources (CSS/JS/fonts on starwars.com domains) — inherent to fetching that page in a browser, not telemetry or phone-home behavior.

## R3. Full-resolution asset URL

**Decision**: Download the lumiere URL with its query string stripped (e.g., `.../star-wars-virtual-background-2026-07_ba76c3f3.jpeg`), i.e., the canonical CDN object without the `?region=0,0,1920,1080` crop parameter.

**Rationale**: Verified via HEAD requests: with and without `?region=` both return HTTP 200 `image/jpeg`, and downloaded samples are identical dimensions (1920×1080). Stripping the query yields the untransformed original asset, matching the article's "open it at full resolution" instruction.

**Alternatives considered**: Downloading the exact `src` including `?region=`: rejected only on cleanliness grounds — both variants are 1920×1080, but the query-less URL is the stable canonical object and avoids coupling to a display crop parameter that could change without notice.

## R4. Cross-platform Pictures directory resolution (platformdirs)

**Decision**: Use `platformdirs.user_pictures_dir()` to resolve the user's platform-standard Pictures directory, then create `<resolved>/StarWarsBackground` with `pathlib.Path.mkdir(parents=True)` as needed. The resolution function is a single call that works identically on Windows, macOS, and Linux.

**Rationale**: Owner-directed adoption (2026-10-02) of `platformdirs` for correct cross-platform Pictures directory resolution. Provides proper XDG/Known-Folders semantics without hand-rolling OS-specific logic; a single call replaces the manual three-branch resolution chain while remaining testable via module-level patching.

**Alternatives considered**:
- Stdlib-only manual resolution (`os.path.expanduser("~") / "Pictures"`, `$XDG_PICTURES_DIR` fallback): initially chosen but replaced per owner directive to use `platformdirs` for correctness and simplicity.
- Windows Known Folders via registry/COM: rejected — overkill; `platformdirs` handles this internally.

## R5. Retry policy, timeouts, bounded runtime (Requests)

**Decision**: Every image download via `requests` gets a connect/read timeout of 30 s and up to 3 attempts with exponential backoff (1 s, then 2 s). A request that still fails after its final attempt is recorded as a failed item; the article page failing all acquisition attempts aborts the run immediately. Worst-case wall time for a fully unreachable host is bounded, and no single request can hang indefinitely.

**Rationale**: Satisfies FR-006/SC-003 ("bounded retries", "no indefinite hang") with concrete numbers; 3 attempts matches common downloader practice and keeps worst-case runtime predictable for tests (tests use short timeouts). `requests` provides clean timeout semantics and per-attempt exception handling that stdlib `urllib` lacks.

**Alternatives considered**:
- Unbounded retries: rejected — violates SC-003.
- Retry only on connection errors, not HTTP 5xx/429: rejected — CDN transient failures surface as 5xx; retrying any non-success status (except client-side 404) is the safer default for a one-shot downloader.

## R6. Atomic writes and no-partial-file guarantee

**Decision**: Each image downloads to a temporary file in the destination directory (`tempfile.NamedTemporaryFile` with `dir=<output folder>`, delete-on-failure), then `os.replace()` moves it to its final name. Any exception during download or validation deletes the temp file. Final names are unique per item, so concurrent runs of this tool cannot clobber each other's in-progress files either.

**Rationale**: Satisfies FR-005/SC-004 and Constitution II with stdlib primitives; same-directory temp avoids cross-device rename failures on Windows. Streaming `requests` responses into the temp file bounds memory use regardless of image size.

**Alternatives considered**: Write directly then delete on failure: rejected — leaves partial files if the process is killed (SIGKILL/power loss) mid-write.

## R7. Format validation ("common image formats only")

**Decision**: Accept JPEG and PNG, validated by magic bytes (`FF D8 FF` for JPEG; `89 50 4E 47 0D 0A 1A 0A` for PNG) after download completes. Any other content is rejected with a clear error naming the item (title + URL); nothing is written to its final name. Extension comes from the validated format, not blindly from the URL.

**Rationale**: FR-004 requires rejecting unsupported formats rather than silently writing them; the live collection is 100% JPEG, and PNG covers the spec's "e.g., JPEG/PNG" allowance. Magic-byte checks are stdlib-only and catch mislabeled assets without a full image decoder (decoding every file would need third-party libraries outside the specified stack).

**Alternatives considered**:
- Full decode with Pillow: rejected — dependency not justified; magic bytes plus complete-download size sanity is sufficient for this feature.
- Trust the URL extension: rejected — violates FR-004's "rejected rather than silently written" guarantee.

## R8. Deterministic, unique file names

**Decision**: `<NNN>-<sanitized-title>.<ext>` where `NNN` is the 3-digit zero-padded gallery position (1-based), title = figure `alt` text sanitized to lowercase ASCII alphanumerics/hyphens (runs of non-alphanumerics collapsed to one hyphen, leading/trailing hyphens removed, max 60 chars), and `<ext>` is `.jpg`/`.png` from R7. The index prefix guarantees uniqueness even when titles repeat (the live collection has repeated titles such as "Tatooine" ×4).

**Rationale**: FR-003 requires deterministic names derived from listing order and titles; the edge-case rule requires no two backgrounds ever map to one file. Index-first ordering also makes the folder readable in article order.

**Alternatives considered**:
- Title-only names: rejected — live data has duplicate titles, which would force overwrite or collision handling (violates FR-007/edge cases).
- Hash-based names: rejected — opaque and not derived from titles as the spec requires.

## R9. Testing strategy without live network

**Decision**: `unittest` (stdlib) with three mechanisms: (1) a recorded rendered-HTML fixture of the article (`tests/fixtures/article.html`) for bs4 parser tests; (2) a local HTTP stub server built on `http.server` serving small generated JPEG/PNG payloads and configurable failure modes (500s, timeouts, truncated bodies) for downloader/CLI tests; (3) page acquisition isolated behind an injectable provider so unit tests never launch a browser. Output paths are redirected into per-test temp directories via the pure path-resolution function and an injectable output root — no test touches the real user Pictures folder or live endpoints.

**Rationale**: Constitution IV requires network-dependent code to be tested against recorded fixtures or a local stub server; stdlib `unittest` keeps the test stack dependency-free (Constitution I). The provider seam makes the Selenium layer the only component that needs a browser, exercised solely by optional live validation in quickstart.md.

**Alternatives considered**:
- pytest: rejected as default — adds a dependency outside the specified stack for no capability this project needs (`unittest` covers parameterization, subTest, and temp dirs); revisit only if the suite outgrows it.
- Live-endpoint integration tests in CI: rejected by Constitution IV (CI must not depend on external availability).

## R10. CLI surface

**Decision**: `python starwars_backgrounds.py [--overwrite]`. No other flags — no custom URL (FR-001 forbids user-supplied sources), no custom output directory (the standard Pictures folder is the documented contract; tests inject paths internally rather than exposing a flag). Exit codes: 0 = all backgrounds downloaded successfully; 2 = usage error (argparse default); 1 = any runtime failure (source unreachable after retries, one or more image failures, zero backgrounds found, output directory not writable).

**Rationale**: Minimal surface per Constitution I and the spec's "single command-line script" assumption; FR-007's explicit overwrite option is the only behavior change worth a flag. `argparse` (stdlib) provides this with no extra dependencies.

**Alternatives considered**: `--output-dir`, `--url`, `--verbose`: rejected — none are required by the spec, and each widens the contract surface that Constitution governance protects.
