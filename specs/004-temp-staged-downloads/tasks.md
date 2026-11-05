# Tasks: Temp-Staged Downloads with Hash Deduplication

**Input**: Design documents from `/specs/004-temp-staged-downloads/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: REQUIRED - Constitution Principle IV (Test-First) mandates tests written before implementation for every new behavior; network-dependent code is tested against recorded fixtures and the local stub server only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `starwars_backgrounds.py` at repository root; `tests/unit/`, `tests/fixtures/` per plan.md structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish a green baseline before any change

- [X] T001 Run the existing test suite (`python -m unittest discover -s tests`) from repository root and confirm all feature-001/002/003 tests pass with no live network or browser launch; record the result as the pre-change baseline. Note that `tests/fixtures/article.html` CDN URLs carry recognizable base names usable for URL-naming tests (research.md R3).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [X] T002 Bump the module-level `__version__` constant in starwars_backgrounds.py from "1.2.0" to "1.3.0" per research.md R9 (governance: public CLI options and output file naming rules are protected contracts; this feature's spec is the amendment). No user-facing flag is added here.

**Checkpoint**: Foundation ready - all users can begin story implementation

---

## Phase 3: User Story 1 - Only new images persist on re-runs (P1)

**Goal**: Every run re-fetches all images to temp staging; each staged image's SHA-256 content hash is compared against existing target files hashed at run start, and hash matches are discarded so no duplicate copies accumulate across runs. No persistent state or manifest exists between runs.

**Independent Test**: Run the tool once into a scratch directory; run it again immediately and verify the target directory is byte-for-byte unchanged with every item reported as a hash-match duplicate (SC-001, FR-001, FR-007).

### Tests for User Story 1

- [X] T003 [P] [US1] Create tests/unit/test_temp_staging.py with unit tests: streaming SHA-256 computation via chunked reads (hash of known content matches hashlib reference; large multi-chunk content handled without loading the file into memory); baseline hash set built from an existing target directory at run start, including unreadable files producing an ERROR line but not aborting.
- [X] T004 [P] [US1] Extend tests/unit/test_temp_staging.py: idempotent re-run test - a second simulated run against an unchanged target discards every staged file as `duplicate (hash match)`, leaves the target byte-for-byte identical, and reports 0 moved / N discarded / 0 failed; same-hash-different-name items keep only the first occurrence under its original link-derived name.

### Implementation for User Story 1

- [X] T005 [US1] Implement in starwars_backgrounds.py: a chunked SHA-256 helper (read files in 1 MiB chunks, return hex digest) and run-start baseline hashing of the effective target directory producing a seen-hash set; unreadable files log an ERROR line naming the path and contribute no hash.
- [X] T006 [US1] Implement move-phase deduplication in starwars_backgrounds.py: after each staged file is hashed, if its hash is in the seen set (baseline plus hashes of files already moved this run) delete the staged file and report `<name>: duplicate (hash match)`; otherwise add its hash to the seen set before moving. No manifest or state file is written anywhere (spec assumption).

**Checkpoint**: Story 1 independently testable - re-runs discard duplicates, target unchanged (SC-001)

---

## Phase 4: User Story 2 - File names derived from source link (P1)

**Goal**: Saved file names use the base name embedded in the source download URL instead of position-based generation, with a deterministic fallback for degenerate URLs.

**Independent Test**: Run against the fixture article; verify every saved file name equals the base name extracted from its source URL and 0 files use position-based generated names (SC-002, FR-002).

### Tests for User Story 2

- [X] T007 [P] [US2] Extend tests/unit/test_article_parser.py: unit tests for base-name extraction - basename of `urlparse(source_url).path` after query/fragment stripping; empty or extension-less URL paths fall back to the existing `<NNN>-<sanitized-title>` derivation; Windows-illegal characters (`<>:"/\|?*` and control chars) replaced with `-`; trailing dots/spaces stripped.

### Implementation for User Story 2

- [X] T008 [US2] Implement in starwars_backgrounds.py: URL-derived naming replacing the position-based `derive_filename(position, title, fmt)` as the primary rule - extract base name from the canonical source URL (query already stripped), apply sanitization per research.md R3, and replace the extension with the detected format's extension (`.jpg`/`.png`) so on-disk extension always matches magic-byte-validated content.

**Checkpoint**: Story 2 independently testable - link-derived names everywhere except degenerate URLs (SC-002)

---

## Phase 5: User Story 3 - Temp-staged downloads with atomic move (P2)

**Goal**: All images download first into `<Temp>/swbdl/<datetime>`; after the download phase, successful items are moved to the target directory best-effort even when other items fail; failed items are reported individually with URL and reason; exit status is non-zero on any failure; `<Temp>/swbdl` is deleted after every run regardless of outcome.

**Independent Test**: Run with one failing image among many (stub server returns HTTP 500 for that URL); verify successful images are moved, the failed item prints an ERROR line with its URL and reason, exit status is non-zero, and `<Temp>/swbdl` no longer exists (SC-003, SC-005, FR-004, FR-005, FR-008).

### Tests for User Story 3

- [X] T009 [P] [US3] Extend tests/unit/test_output_paths.py: staging lifecycle tests - per-run path is `<tempfile.gettempdir()>/swbdl/<YYYYMMDD-HHMMSS>` with a counter suffix on collision; a pre-existing stale `<Temp>/swbdl` (simulating an interrupted run) is deleted before the fresh subfolder is created; `<Temp>/swbdl` is deleted entirely after the run including staged files for failed items, on success and failure paths.
- [X] T010 [P] [US3] Extend tests/unit/test_temp_staging.py: best-effort move test against the stub server - one image URL fails after bounded retries while others succeed; successful images are moved to the target; the failing item produces an ERROR line with URL, attempt count, and error type on stderr; exit status is 1.
- [X] T011 [P] [US3] Extend tests/unit/test_cli.py: two-phase stdout progress (download phase lines show staged path + bytes; move phase lines show final target path or duplicate discard) and summary format `Summary: X moved, Y duplicates discarded, Z failed. Output folder: <dir>` per contracts/cli.md; exit codes 0/1 verified for success/partial-failure runs.

### Implementation for User Story 3

- [X] T012 [US3] Implement in starwars_backgrounds.py: the two-phase pipeline - (1) download every gallery item into the staging subfolder with existing bounded retries/backoff, recording per-item failures without stopping; (2) move phase over staged files using `shutil.move` so cross-device moves work. Delete `<Temp>/swbdl` entirely at run end via a finally-style cleanup path covering success, failure, and exceptions (research.md R1, R5).
- [X] T013 [US3] Implement in starwars_backgrounds.py: best-effort semantics and reporting - per-item ERROR lines naming URL/path and reason; exit status 0 only when zero items failed, otherwise 1; `--overwrite` reinterpreted per research.md R7 (a staged file whose derived name matches an existing target file replaces it instead of receiving a postfix; hash-match discards still apply).

**Checkpoint**: Story 3 independently testable - staging-first flow with best-effort moves and guaranteed cleanup (SC-003, SC-005)

---

## Phase 6: User Story 4 - Sequential postfix for name conflicts (P3)

**Goal**: A newly downloaded image whose derived name matches an existing target file is saved as `name-1.jpg`, `name-2.jpg`, ... until unique; no silent overwrites. Intra-run collisions are assumed impossible per source URL uniqueness but live checks cover them defensively.

**Independent Test**: Pre-create `name.jpg` and `name-1.jpg` in the target with unrelated content, run the tool, verify the new image lands as `name-2.jpg` and existing files are untouched (SC-004, FR-006).

### Tests for User Story 4

- [X] T014 [P] [US4] Extend tests/unit/test_temp_staging.py: postfix collision tests - pre-existing `name.jpg` yields `name-1.jpg`; pre-existing `name.jpg`, `name-1.jpg`, `name-2.jpg` yields `name-3.jpg`; numbering continues to the next free slot against live target directory state including files moved earlier in the same run; existing colliding files are never overwritten.

### Implementation for User Story 4

- [X] T015 [US4] Implement in starwars_backgrounds.py: at move time, if the destination path exists and `--overwrite` is not set, append `-1`, `-2`, ... before the extension until a free name is found (numbering starts at `-1` per spec assumption); existence checks run against live target directory state.

**Checkpoint**: Story 4 independently testable - zero silent overwrites across runs (SC-004)

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T016 [P] Extend tests/unit/test_downloader.py and tests/unit/test_cli.py: `--delay <seconds>` option - float parsing with default 0.2, minimum 0; blank or negative values rejected as a usage error (exit 2) before any download starts; the delay sleeps between successive image download requests (per-request, additive to retry backoff per research.md R6); `--help` lists the new option.
- [X] T017 Implement in starwars_backgrounds.py: the `--delay <seconds>` argparse option (float, default 0.2) applied between successive image download requests; blank/negative values produce an argparse usage error with exit code 2 per contracts/cli.md.
- [X] T018 Update README.md Options table and version note to document `--delay`, the URL-derived naming rule, temp-staging behavior, and version 1.3.0 (governance: keep documented CLI in sync with the protected contract).
- [X] T019 Run the full test suite (`python -m unittest discover -s tests`) and walk through quickstart.md scenarios 1-5 and 7 against a scratch directory; confirm exit codes, summary format, `<Temp>/swbdl` deletion, and idempotent re-run behavior all match contracts/cli.md.

---

## Phase 8: Bug Fix - Concurrency-Safe Staging Lifecycle

**Goal**: Overlapping instances must not delete each other's staged files mid-run (observed failure: `WinError 2` on every move after a second instance wiped `<Temp>/swbdl`).

- [X] T020 Scope the staging lifecycle to per-run subfolders in starwars_backgrounds.py: at start, delete only stale subfolders (mtime older than STALE_STAGING_AGE_SECONDS); `cleanup_staging(staged_dir)` deletes this run's subfolder and `<Temp>/swbdl` once empty; `move_staged_files` reports vanished staged files with a clear diagnostic instead of raw WinError 2; `main()` skips missing staged files before dedup. Add regression tests in tests/unit/test_output_paths.py (stale deletion, fresh-folder survival, scoped cleanup) and tests/unit/test_temp_staging.py (missing-file move); sync research.md R1/R5, contracts/cli.md, and README.md.

---

## Dependencies & Execution Order

**Global dependencies**:
- Phase 1 (baseline) blocks everything.
- Phase 2 (version bump) is trivial but must land before story work to keep the module consistent.

**Story-level dependencies**:
- US1, US2, and US4 are independent at test level: T003/T004, T007, and T014 can all be written in parallel (different files or disjoint sections of test_temp_staging.py).
- US3's pipeline implementation (T012) integrates US1 deduplication (T006) and US2 naming (T008); implement stories in phase order so each checkpoint is independently testable.
- Polish tasks T016-T017 depend on the download loop existing from Phase 5; T018/T019 depend on all implementation being complete.

**Parallel execution examples**:
- US1: T003 + T004 in parallel (disjoint test sections), then T005, then T006.
- US2: T007 and T008 can run alongside US1 tasks - different files.
- US3: T009, T010, T011 all in parallel (three different test files), then T012, then T013.
- US4: T014 and T015 sequential; T014 can start as soon as Phase 5 tests exist.

**Parallel opportunities**:
- Maximum parallelism: T003/T004/T007 (three test files) after Phase 2; then T009/T010/T011 in parallel during US3.

---

## Implementation Strategy

**MVP scope**: Phases 1-5 - temp-staged pipeline with hash deduplication, URL-derived naming, and best-effort moves gives the core value (idempotent re-runs + link names) before postfix edge cases and throttling polish.

**Incremental delivery**:
1. Baseline green (Phase 1), version bump (Phase 2).
2. US1: deduplication logic testable in isolation against a scratch target directory.
3. US2: naming rule - pure function, immediately verifiable via fixture tests.
4. US3: wire the two-phase pipeline; this is where SC-003 becomes observable end-to-end.
5. US4: collision edge case on top of the move path.
6. Polish: `--delay`, README sync, full quickstart validation (Phase 7).

**Constitution IV compliance**: every behavior change has its test task before its implementation task within the same phase; no live network or browser in unit tests - stub server and recorded fixtures only.
