# Tasks: Star Wars Backgrounds Downloader

**Input**: Design documents from `/specs/001-download-starwars-backgrounds/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Required — Constitution Principle IV mandates test-first; `unittest` (stdlib) with recorded HTML fixtures and local HTTP stub server.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `starwars_backgrounds.py`, `requirements.txt`, `tests/` at repository root
- All implementation lives in one importable module: `starwars_backgrounds.py`
- Tests: `tests/unit/test_*.py`, fixtures: `tests/fixtures/article.html`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project structure per implementation plan — create `starwars_backgrounds.py` at repo root, `requirements.txt`, `tests/` directory tree with `tests/fixtures/` and `tests/unit/` subdirectories
- [X] T002 [P] Pin runtime dependencies in requirements.txt (selenium==4.50.0, beautifulsoup4==4.15.0, requests==2.34.2)
- [X] T003 [P] Record rendered HTML fixture of the article at tests/fixtures/article.html (capture full rendered DOM from https://www.starwars.com/news/star-wars-backgrounds preserving all `<figure><img>` gallery markup)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement BackgroundImage and DownloadRun dataclasses with validation rules in starwars_backgrounds.py (BackgroundImage: position int 1-based, title str non-empty or fallback `background-<position>`, source_url absolute HTTPS lumiere CDN URL, format enum jpeg|png, destination_path Path; duplicate detection by distinct source_url; DownloadRun: total_found int, items list[ItemResult], bytes_downloaded int, exit_status 0|1|2)
- [X] T005 [P] Implement cross-platform Pictures directory resolution as pure function in starwars_backgrounds.py (Windows: `%USERPROFILE%\Pictures`, macOS: `~/Pictures`, Linux: `$XDG_PICTURES_DIR` → `~/.local/share/Pictures` → `~/Pictures`; create `<resolved>/StarWarsBackground` with `pathlib.Path.mkdir(parents=True)`; function takes home directory as input for testability — research.md R4)
- [X] T006 [P] Implement deterministic filename derivation rule in starwars_backgrounds.py (3-digit zero-padded position prefix, title lowercased with every run of non-alphanumerics collapsed to single hyphen, leading/trailing hyphens removed, truncated to 60 chars at last safe boundary, extension `.jpg`/`.png` from validated format — data-model.md naming rule)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Download the full background collection (Priority: P1) 🎯 MVP

**Goal**: A single run fetches the article, extracts every gallery background, downloads each at full resolution to `<Pictures>/StarWarsBackground`, and reports progress per item.

**Independent Test**: Run the tool from an empty output location; verify that every background in the article's collection exists on disk as a valid, complete image file and that progress was reported during the run.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [P] [US1] Write parser tests for gallery extraction from recorded HTML fixture in tests/unit/test_article_parser.py (extract BackgroundImage items from `<figure><img>` where src is lumiere CDN URL `https://lumiere-a.akamaihd.net/v1/images/...jpeg`; verify count ≥ 50, unique source URLs, correct titles and positions; use tests/fixtures/article.html)
- [X] T008 [P] [US1] Write downloader tests using local HTTP stub server in tests/unit/test_downloader.py (download full-resolution URL with query stripped via requests, stream to temp file then os.replace for atomic write, verify progress reporting format `[i/N] <title> -> <path> (<bytes>)` on stdout)

### Implementation for User Story 1

- [X] T009 [US1] Implement Selenium page acquisition function in starwars_backgrounds.py (headless browser via Selenium 4.50.0, navigate to article URL https://www.starwars.com/news/star-wars-backgrounds, wait for document readiness, return driver.page_source as string; injectable provider so unit tests never launch a browser — research.md R2)
- [X] T010 [US1] Implement gallery parsing with BeautifulSoup4 in starwars_backgrounds.py (select `<figure><img>` where src matches lumiere CDN pattern `https://lumiere-a.akamaihd.net/v1/images/...jpeg`, strip query string from src for canonical full-resolution URL, extract position/title/source_url per data-model.md validation rules — research.md R1)
- [X] T011 [US1] Implement image download function in starwars_backgrounds.py using requests (download full-resolution URL with query stripped, 30s connect/read timeout, stream response to temp file in destination directory then os.replace for atomic write; determine format via magic bytes for extension — research.md R3/R5/R6)
- [X] T012 [US1] Implement main CLI entry point and progress reporting in starwars_backgrounds.py (argparse setup with `--overwrite` flag stub, per-item stdout line `[i/N] <title> -> <path> (<bytes>)`, summary line `Summary: X downloaded, Y skipped, Z failed. Output folder: <path>` — contracts/cli.md)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Safe re-runs without clobbering existing files (Priority: P2)

**Goal**: Re-running the tool leaves existing files untouched unless `--overwrite` is given; no duplicates are ever created.

**Independent Test**: Run the tool once, then run it again immediately; verify no existing files were modified or overwritten and no duplicate files appeared.

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Write idempotency tests in tests/unit/test_output_paths.py (existing file skipped when no `--overwrite`, file replaced with `--overwrite`, no duplicates created, unrelated user files left untouched; use temp output directories)

### Implementation for User Story 2

- [X] T014 [US2] Implement skip/overwrite logic and `--overwrite` flag behavior in starwars_backgrounds.py (if destination path exists and `--overwrite` not given → skip item, report as skipped with no byte count; if `--overwrite` given → re-download and replace; skipped items count as success for exit status — FR-007, contracts/cli.md)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Loud, clear failures (Priority: P3)

**Goal**: Every failure is visible on stderr with URL/attempt/error context; exit status reflects any failure; no partial files remain.

**Independent Test**: Run the tool against an unreachable source (or a failing image URL); verify the exit status is non-zero, stderr names the failed URL with attempt context, and no partial file remains in the output folder.

### Tests for User Story 3 ⚠️

- [X] T015 [P] [US3] Write failure behavior tests in tests/unit/test_downloader.py (retry exhaustion with exponential backoff 1s/2s over 3 attempts, format rejection via magic bytes for non-JPEG/PNG content served by stub server, no partial files remain after failed download, error messages include URL + attempt number + error type)
- [X] T016 [P] [US3] Write CLI exit code and stderr format tests in tests/unit/test_cli.py (exit 0 on all success/skip, exit 1 on any runtime failure including zero backgrounds found, exit 2 on usage error; stderr ERROR lines with URL/attempt/error type; final non-zero exit always preceded by at least one ERROR line)

### Implementation for User Story 3

- [X] T017 [US3] Implement retry policy with bounded attempts and exponential backoff in starwars_backgrounds.py (up to 3 attempts per image download, backoff 1s then 2s, connect/read timeout 30s; article page failure after retries aborts run immediately — research.md R5)
- [X] T018 [US3] Implement format validation and rejection in starwars_backgrounds.py (validate magic bytes: JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`; reject non-image content with clear error naming item title + URL; extension derived from validated format, never from URL — research.md R7)
- [X] T019 [US3] Implement error reporting, exit code logic, and zero-backgrounds-found handling in starwars_backgrounds.py (stderr ERROR lines per failure with URL/attempt/error type; exit 1 on any runtime failure or zero backgrounds found; exit 2 for argparse usage errors; final non-zero exit always preceded by at least one ERROR line — FR-006/FR-010, contracts/cli.md)

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T020 [P] Run quickstart.md validation scenarios end-to-end (live run + idempotent re-run + failure simulation via network blocking; verify file count matches `Found <N>` number, no `.tmp` or partial files remain)
- [X] T021 Verify all tests pass with `python -m unittest discover -s tests -v` and confirm no live network access or browser launch in automated tests (parser tests use fixture, downloader/CLI tests use stub server + temp dirs, page acquisition injected as fixture)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 skip/overwrite logic but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Adds retry/validation/error handling on top of US1 download path; should be independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution IV)
- Data model before services
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T002 and T003 can run in parallel (different files: requirements.txt vs tests/fixtures/article.html)
- T005 and T006 can run in parallel (independent functions added to starwars_backgrounds.py)
- T007 and T008 can run in parallel (different test files: test_article_parser.py vs test_downloader.py)
- T015 and T016 can run in parallel (different test files: test_downloader.py additions vs test_cli.py)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Write parser tests for gallery extraction from recorded HTML fixture in tests/unit/test_article_parser.py"
Task: "Write downloader tests using local HTTP stub server in tests/unit/test_downloader.py"

# Then implement sequentially (same file):
Task: "Implement Selenium page acquisition function in starwars_backgrounds.py"
Task: "Implement gallery parsing with BeautifulSoup4 in starwars_backgrounds.py"
Task: "Implement image download function in starwars_backgrounds.py using requests"
Task: "Implement main CLI entry point and progress reporting in starwars_backgrounds.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently — run tool from empty output location, verify all backgrounds downloaded with progress reporting

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (parser, downloader, CLI)
   - Developer B: User Story 2 (skip/overwrite logic) — can start after US1 core download exists
   - Developer C: User Story 3 (retry, validation, error reporting) — can start after US1 core download exists
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution IV)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All implementation lives in `starwars_backgrounds.py` — single-file CLI per plan.md structure decision
- Test stack is stdlib-only (`unittest`, `http.server`) — no pytest, no mock library beyond stdlib

## Phase 7: Convergence

- [X] T022 Update plan.md Complexity Tracking table and research.md R4 to document and justify the `platformdirs` dependency per Constitution I (contradicts)
- [X] T023 Add bounded retry loop with backoff to `fetch_article_html()` so page fetch failures are retried up to 3 attempts before aborting, matching FR-006 and contracts/cli.md error format (partial)
- [X] T024 Fix `process_item()` skip check to account for both `.jpg` and `.png` extensions so idempotency holds regardless of detected image format per FR-007/SC-002 (partial)
- [X] T025 Wrap `resolve_output_root()` call in `main()` with try/except; on failure print ERROR to stderr naming the path and reason, return exit code 1 per contracts/cli.md "output directory not writable" (partial)
