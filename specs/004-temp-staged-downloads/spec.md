# Feature Specification: Temp-Staged Downloads with Hash Deduplication

**Feature Branch**: `005-temp-staged-downloads`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "The user should be able to execute the script multiple times and only new images should be downloaded. The naming of the files should changes from the existing one to the name of the file in the link. Download the images first to a subfolder of the temp directory (e.g. Windows AppData/Temp/swbdl/<datetime> -> swbdl for starwarsbackgrounddownloader). Detection of duplicates across multiple runs should be done via hash comparison, content can be large so we don't do it for 100 pictures. If two different images have the same name (downloaded <-> target directory, downloaded <-> downloaded should not happen) use sequential numbers as postfix. The downloaded images should then be moved to the target directory. As cleanup step the temp directory swbdl should be deleted."

## Clarifications

### Session 2026-11-05

- Q: When all downloads complete successfully in the temp staging folder but the target directory becomes unwritable during the move phase, should the tool preserve files for recovery or delete them? → A: Delete temp folder entirely; user must re-run to redownload everything.
- Q: Should the tool enforce delays between individual image requests when downloading ~100 images in a single run? → A: Configurable delay via CLI option (e.g., `--delay`); default 0.2 seconds to keep total run time under 2 minutes for ~100 images.
- Q: Within a single run, can two different images from the source article have identical base file names in their download URLs? → A: Trust source URLs produce unique base names; only handle new-vs-existing target directory conflicts with sequential postfix.
- Q: How should the tool know on a second run which images it has already obtained so that only new images are fetched from the network? → A: No persistent state — every run re-downloads all images to temp staging, then hashes them against existing target files and moves only new ones (full network cost per run).
- Q: If one image fails after all retries while other images succeed in the same run, should the successful images still be moved to the target directory? → A: Best-effort — successful images are moved; failing items are reported individually with URL and reason; exit status is non-zero.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Only new images persist on re-runs (Priority: P1)

A user runs the downloader multiple times — for example, after a partial failure or when new backgrounds have been added to the article — and only genuinely new images end up in the target directory. Every run fetches each image into temp staging; the tool then compares content hashes of fetched images against existing files in the target directory, so an image with identical content is never saved again as a duplicate copy.

**Why this priority**: This is the core value of the feature — without hash-based deduplication, repeated runs would accumulate duplicate copies in the target directory; with it, any number of re-runs leaves exactly one copy per unique image and existing files are never touched.

**Independent Test**: Run the tool once to download all available backgrounds; run it again immediately and verify that the target directory is unchanged — no new, modified, or duplicate files — with console output reporting each fetched image as a hash-match duplicate.

**Acceptance Scenarios**:

1. **Given** a completed first run with all backgrounds saved, **When** the user runs the downloader again without extra options, **Then** every fetched image whose content-hash matches an existing file is discarded after download (no new or modified files in the target directory), and the console reports each discard with its hash-match reason.
2. **Given** a target directory containing some previously downloaded backgrounds, **When** the source article has added new backgrounds since the last run, **Then** only the genuinely new images are saved into the target directory; existing images remain untouched.
3. **Given** a successful re-run where all images already exist in the target directory, **When** the user reviews console output, **Then** every item is reported as a duplicate with hash-match confirmation, and no files were added, modified, or overwritten.

---

### User Story 2 - File names derived from source link (Priority: P1)

A user runs the downloader and saved images use the actual file name embedded in the download URL rather than a position-based generated name. For example, if the article links to `https://lumiere-a.akamaihd.net/v1/images/starwars-background-001.jpg`, the saved file is named `starwars-background-001.jpg` (or whatever the link specifies), preserving the source's original naming convention.

**Why this priority**: Users expect downloaded files to retain their original names from the source; position-based names obscure which image came from which URL and make manual management harder. Link-derived names improve traceability and user confidence that they have the correct file.

**Independent Test**: Run the tool against a known article with identifiable URLs; verify every saved file name matches the base name extracted from its source URL (not a position-based generated name).

**Acceptance Scenarios**:

1. **Given** an image linked as `https://lumiere-a.akamaihd.net/v1/images/some-name.jpg`, **When** the user runs the downloader, **Then** the saved file is named `some-name.jpg` (the base name from the URL), not a position-based generated name like `001-some-title.jpg`.
2. **Given** a successful run, **When** the user reviews the target directory, **Then** every saved file name corresponds to the base name extracted from its source download link.

---

### User Story 3 - Temp-staged downloads with atomic move (Priority: P2)

A user runs the downloader and all images are first downloaded into a temporary staging folder under the system temp directory (e.g., `%AppData%\Temp\swbdl\<datetime>` on Windows). Once downloads complete, successfully downloaded images are moved to the final target directory — even if other images in the same run fail after retries; failed items are reported individually with their URL and reason and the run exits with a non-zero status. After moving, the temp staging folder is cleaned up and removed.

**Why this priority**: Staging downloads in a temp folder protects the user's target directory from partial or corrupt writes — each file reaches the target only after its download completes fully. Best-effort moves preserve progress when individual images fail, and cleanup prevents disk clutter across runs.

**Independent Test**: Run the tool with one failing image among many; verify that successful images are moved to the target directory, the failed item is reported individually with its URL and reason, the exit status is non-zero, and the temp staging folder is removed after completion regardless of outcome.

**Acceptance Scenarios**:

1. **Given** a fresh run, **When** the user observes the file system during execution, **Then** downloaded images first appear only in the temp staging folder (`<Temp>/swbdl/<datetime>`), not yet in the target directory.
2. **Given** all downloads complete successfully, **When** the run finishes, **Then** every non-duplicate image is moved from the temp folder to the target directory, duplicate images are discarded, and the temp folder is deleted.
3. **Given** one or more images fail after exhausting retries while other images succeed, **When** the run completes with a non-zero exit status, **Then** successfully downloaded images have been moved to the target directory, each failed item is reported individually with its URL and reason, and no partial files remain in either the temp staging folder or the target directory.

---

### User Story 4 - Sequential postfix for name conflicts (Priority: P3)

A user runs the downloader and encounters a newly downloaded image whose base file name from its source link matches an existing file in the target directory. The tool resolves the conflict by appending a sequential number to the new name (e.g., `name.jpg` becomes `name-1.jpg`) so both files are saved without overwriting each other. Within a single run, source URLs are assumed to produce unique base names, so only new-vs-existing conflicts require resolution.

**Why this priority**: Name collisions can occur when source links use generic names; sequential postfix ensures no data is lost due to silent overwrites while keeping file names recognizable.

**Independent Test**: Run the tool with a source containing two different images that share the same base name in their URLs; verify both are saved with unique names using sequential postfix, and neither was overwritten by the other.

**Acceptance Scenarios**:

1. **Given** a target directory already containing `name.jpg`, **When** a newly downloaded image also resolves to `name.jpg`, **Then** the new file is saved as `name-1.jpg` (or the next available sequential number) without overwriting the existing file.
2. **Given** multiple existing files in the target directory (`name.jpg`, `name-1.jpg`, `name-2.jpg`), **When** a newly downloaded image also resolves to `name.jpg`, **Then** the new file is saved as `name-3.jpg` (the next available sequential number) without overwriting any existing file.

---

### Edge Cases

- What happens when the temp staging folder already exists from a previous interrupted run? It MUST be detected and reused or cleaned before starting; stale files are removed to avoid confusion with fresh downloads.
- How does the system handle an image whose source link has no recognizable base name (e.g., a URL ending in `/` or query string only)? A deterministic fallback name is generated from position and title, sanitized for safe filesystem use.
- What happens when two images have the same hash but different names? They are treated as duplicates; only one copy is kept in the target directory under its original link-derived name.
- How does the system handle a temp directory that cannot be created (permissions, full disk)? The tool MUST report an error naming the path and reason, exit with a non-zero status, and leave no partial files behind.
- What happens when the sequential postfix reaches a very high number due to many collisions? Numbers continue incrementing until a unique name is found; there is no hard upper limit within reasonable bounds (e.g., up to 999).
- What happens when all downloads succeed but the target directory becomes unwritable during the move phase? The tool MUST report an error naming the path and reason, exit with a non-zero status, and delete the entire temp staging folder so the user can re-run cleanly without stale files.
- What happens when one image fails after exhausting retries while other images succeed? Successful images are still moved to the target directory; the failed item is reported individually with its URL and reason; the run exits with a non-zero status and the temp staging folder is cleaned up.
- What happens when the user manually deletes a file from the target directory and re-runs? Because no persistent state tracks prior downloads, the image is re-downloaded and restored; the target directory converges back to the complete collection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST compute a content hash for each downloaded image and compare it against the content of existing files in the target directory (hashed at run start) before moving it into place; images whose hash matches an existing file are discarded from temp staging rather than saved, so no duplicate copies accumulate across runs.
- **FR-002**: Saved file names MUST be derived from the base name embedded in the source download URL (the filename portion of the link), not from position-based generation or title sanitization.
- **FR-003**: All images for a run MUST first be downloaded into a temporary staging folder under the system temp directory, structured as `<Temp>/swbdl/<datetime>` where `swbdl` stands for "Star Wars Background Downloader" and `<datetime>` is a unique timestamp identifying this run.
- **FR-004**: Images that downloaded successfully MUST be moved from the temp staging folder to the effective target directory (default or user-specified via `--output-dir`), even if other items in the same run fail after retries; each failed item is reported individually with its URL and reason, and the tool exits with a non-zero status.
- **FR-005**: The temp staging folder (`<Temp>/swbdl`) MUST be deleted after a run completes — whether successful or failed — as a cleanup step.
- **FR-006**: When a newly downloaded image resolves to the same file name as an existing file in the target directory, sequential numbers MUST be appended as postfix (e.g., `name.jpg`, `name-1.jpg`, `name-2.jpg`) until all names are unique; within a single run, source URLs are assumed to produce unique base names so intra-run collisions need not be handled.
- **FR-007**: Re-running the tool against a completed download set MUST leave the target directory unchanged: every image is re-fetched to temp staging, and any whose content-hash matches an existing file is discarded; no files are added, modified, or overwritten (idempotent end state).
- **FR-008**: Network failures during temp-staged downloads MUST be retried with bounded attempts and clear error reporting; failed items are reported individually while successfully downloaded images are still moved to the target directory, and the tool exits with a non-zero status after cleaning up the temp folder.
- **FR-009**: The tool MUST enforce a configurable delay between individual image download requests to avoid overwhelming the source CDN; the default delay is 0.2 seconds per request, adjustable via a CLI option (e.g., `--delay`); this keeps total run time under 2 minutes for ~100 images.
- **FR-010**: Every run MUST print human-readable progress to stdout (item count, bytes downloaded per item, destination path); errors MUST go to stderr with enough context to reproduce the failure (URL, attempt number, error type).
- **FR-011**: The tool MUST make no network requests other than fetching the article page and downloading image assets linked from it; no telemetry, analytics, or phone-home behavior of any kind.

### Key Entities *(include if feature involves data)*

- **Background Image**: One downloadable image from the article's gallery. Attributes: source URL (with embedded file name), resolved base file name, content hash computed after download, format detected from magic bytes, and local destination path in both temp staging folder and final target directory.
- **Temp Staging Folder**: A per-run temporary directory under `<Temp>/swbdl/<datetime>` where images are downloaded before being moved to the target. Attributes: run timestamp, list of downloaded files, cleanup status.
- **Download Run**: A single invocation of the tool. Attributes: effective output directory, temp staging path, total items fetched, items moved to target, items discarded as duplicates (hash match), items failed (with reasons), bytes transferred, final exit status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a re-run against an unchanged target directory, 100% of fetched images whose content matches an existing file are identified via hash comparison and discarded; the target directory is left byte-for-byte identical with 0 new or modified files.
- **SC-002**: Every saved file name matches the base name extracted from its source download URL; 0 files use position-based generated names.
- **SC-003**: On a successful run, 100% of downloaded images appear first in the temp staging folder before being moved to the target directory; after completion, the temp staging folder is deleted with no residual files.
- **SC-004**: When a newly downloaded image shares the same base file name as an existing file in the target directory, it is saved with a unique name using sequential postfix; 0 silent overwrites occur across runs (intra-run collisions are assumed impossible per source URL uniqueness).
- **SC-005**: After any failed or interrupted run, 0 partial files remain in either the temp staging folder or the target directory; cleanup is complete and exit status is non-zero.

## Assumptions

- Content hash comparison uses a standard cryptographic hash function (e.g., SHA-256) computed over the full file content after download; this provides reliable deduplication regardless of file name differences.
- The "name in the link" refers to the base filename extracted from the URL path portion (e.g., `file.jpg` from `https://example.com/path/file.jpg`); query strings and fragments are stripped before extraction.
- Temp staging folders use the platform-standard temp directory resolved via cross-platform means (Windows `%AppData%\Temp`, macOS/Linux `/tmp` or equivalent), with a subfolder named `swbdl` for "Star Wars Background Downloader".
- The datetime suffix in the temp path uses ISO 8601 format (`YYYYMMDD-HHMMSS`) to ensure uniqueness across runs; collisions are resolved by appending an incrementing counter if needed.
- Sequential postfix numbering starts at `-1` for the first collision (e.g., `name.jpg`, then `name-1.jpg`, `name-2.jpg`); this convention keeps the original name intact when possible.
- Source URLs from the article gallery produce unique base file names within a single run; sequential postfix is only needed to resolve conflicts between newly downloaded images and existing files in the target directory.
- No persistent state or manifest is kept between runs: every run re-downloads all images to temp staging, and duplicate detection compares each downloaded image's content hash against the content hashes of existing files in the target directory (computed at run start); this trades network bandwidth for simplicity — a full collection costs one download per run.
- The temp staging workflow applies to both the default output folder (`<Pictures>/StarWarsBackground`) and any user-specified `--output-dir`; behavior is consistent regardless of target location.
