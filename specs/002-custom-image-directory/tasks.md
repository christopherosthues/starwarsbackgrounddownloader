# Tasks: Custom Image Output Directory

**Input**: Design documents from `/specs/002-custom-image-directory/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: REQUIRED — Constitution Principle IV (Test-First) mandates tests written before implementation for every new behavior; network-dependent code is tested against recorded fixtures and the local stub server only.

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

- [x] T001 Run the existing test suite (`python -m unittest discover -s tests`) from repository root and confirm all feature-001 tests pass with no live network or browser launch; record the result as the pre-change baseline.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Add module-level `__version__ = "1.1.0"` constant to starwars_backgrounds.py per research.md R5 (governance: public CLI options are a protected contract; this feature's spec is the amendment and requires a version bump). No user-facing flag is added.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Direct downloads to a chosen folder (Priority: P1) 🎯 MVP

**Goal**: `--output-dir <path>` directs every downloaded image into the specified existing directory; progress and summary report paths inside it; zero images written to the default Pictures-based folder during that run (FR-001, FR-002, FR-007).

**Independent Test**: Run the tool with `--output-dir` pointing at an existing writable directory (via injected fetch + stub server in tests); verify 100% of images land in that directory and none in the default folder, with every reported destination path inside it.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T003 [P] [US1] Write failing unit tests in tests/unit/test_output_paths.py for the new directory-resolution behavior: `--output-dir` value with an existing directory becomes the effective output directory; relative values resolve against the current working directory; absolute values are used as given; `~` is expanded; the effective path is normalized to an absolute path (research.md R2, FR-007).
- [x] T004 [P] [US1] Write failing unit tests in tests/unit/test_cli.py for a full run with `--output-dir <existing dir>` using injected article fetch and the local stub server: every item is saved inside `<dir>`, zero files are written to the default Pictures-based folder, and each progress line plus the summary line report absolute destination paths inside `<dir>` (FR-002, FR-007, SC-001).

### Implementation for User Story 1

- [x] T005 [US1] Implement `--output-dir <path>` in starwars_backgrounds.py: add the argparse option; resolve the value per research.md R2 (expanduser, relative→CWD, absolute as-is, normalized to an absolute path); wire the effective output directory through main() so all item writes and progress/summary reporting use it. Make T003/T004 pass without altering default-path behavior when the option is absent.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently — `python starwars_backgrounds.py --output-dir <dir>` saves everything into `<dir>`.

---

## Phase 4: User Story 2 - Default behavior is unchanged (Priority: P2)

**Goal**: Invocations without `--output-dir` behave exactly as before this feature (default `<Pictures>/StarWarsBackground`, idempotent re-runs), and safe-write rules apply identically inside custom directories (FR-003, FR-006).

**Independent Test**: Run the tool with no options and verify images land in the standard Pictures-based folder exactly as before; re-run without options and confirm skips/idempotency; separately confirm skip/overwrite semantics operate on a custom directory.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL (or are absent) before implementation**

- [x] T006 [P] [US2] Write failing unit tests in tests/unit/test_cli.py: an invocation with no `--output-dir` uses the default Pictures-based folder resolution unchanged from feature 001; a second run without options reports existing files as skipped and exits 0 (idempotent, FR-003).
- [x] T007 [P] [US2] Write failing unit tests in tests/unit/test_output_paths.py: skip/overwrite semantics operate on the effective directory — re-running against a custom directory skips existing files and leaves unrelated pre-existing files untouched; `--output-dir <dir> --overwrite` re-downloads into `<dir>` only (FR-006, SC-005).

### Implementation for User Story 2

- [x] T008 [US2] In starwars_backgrounds.py, verify and preserve default-path behavior: confirm the no-option invocation delegates to the existing default resolution unchanged and that skip/overwrite logic operates on the effective output directory (adjust only if drift is found). Make T006/T007 pass.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently — new option works, old behavior is byte-for-byte intact.

---

## Phase 5: User Story 3 - Safe handling of new or invalid target locations (Priority: P3)

**Goal**: Missing specified directories (including nested parents) are created automatically before any download; unusable targets fail loudly with clear errors naming the offending path and non-zero exit status, leaving no stray writes (FR-004, FR-005, FR-008, FR-009).

**Independent Test**: Run the tool pointing at (a) a nonexistent nested path — verify it is created and populated; (b) a path that collides with an existing file — verify `ERROR <path>: not a directory — cannot use as output location`, exit 1, file untouched, no downloads started; (c) a blank value — verify argparse usage error, exit 2.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T009 [P] [US3] Write failing unit tests in tests/unit/test_output_paths.py: a missing specified directory (including missing parents) is created before any download starts; a value naming an existing file is detected as "exists but not a directory" and resolution fails with an error naming that path (FR-004, FR-005).
- [x] T010 [P] [US3] Write failing unit tests in tests/unit/test_cli.py: blank/whitespace-only `--output-dir` value produces an argparse usage error on stderr with exit code 2 and does NOT fall back to the default folder (FR-008); a path-is-file target prints `ERROR <path>: not a directory — cannot use as output location` on stderr, exits 1, leaves the file untouched, and starts no downloads; a creation failure (`OSError`) prints an error naming the offending path and reason and exits 1 (FR-005, FR-009, contracts/cli.md).

### Implementation for User Story 3

- [x] T011 [US3] Implement validation/error taxonomy in starwars_backgrounds.py: custom argparse type rejecting blank values via `ArgumentTypeError` (exit 2 per contract); pre-download checks — exists-but-not-a-directory error and directory creation with missing parents (`mkdir(parents=True)`) handling `OSError`; emit the exact stderr formats from contracts/cli.md. Make T009/T010 pass.

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T012 [P] Update README.md Options table to document `--output-dir <path>` (including relative-path resolution and auto-creation of missing directories) and note that default behavior is unchanged when the option is absent.
- [x] T013 Run quickstart.md validation end-to-end: execute all six scenarios plus manual edge-case checks, confirming exit codes 0/1/2, stderr formats, and reported paths match contracts/cli.md; then run `python -m unittest discover -s tests` and confirm the full suite passes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-5)**: All depend on Foundational phase completion
  - US1, US2, and US3 each build on the previous phase's state of starwars_backgrounds.py; execute sequentially in priority order (P1 → P2 → P3) because they share one module
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Builds on US1's option plumbing; independently testable via no-option invocations
- **User Story 3 (P3)**: Builds on US1/US2; adds validation/error taxonomy around the same code path

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution IV)
- Core resolution/plumbing before validation/error handling
- Story complete before moving to next priority

### Parallel Opportunities

- T003/T004 can run in parallel within Phase 3 (different test files)
- T006/T007 can run in parallel within Phase 4 (different test files)
- T009/T010 can run in parallel within Phase 5 (different test files)
- T012 is independent of T013 within Phase 6

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Write failing unit tests in tests/unit/test_output_paths.py for directory-resolution behavior" (T003)
Task: "Write failing unit tests in tests/unit/test_cli.py for a full run with --output-dir <existing dir>" (T004)

# Then implement sequentially (single shared module):
Task: "Implement --output-dir option and effective-directory wiring in starwars_backgrounds.py" (T005)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (green baseline)
2. Complete Phase 2: Foundational (`__version__` constant)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `python starwars_backgrounds.py --output-dir <dir>` saves everything into `<dir>`; default folder untouched

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP: option works for existing directories
3. Add User Story 2 → Test independently → Default behavior proven unchanged, safe-write rules hold in custom dirs
4. Add User Story 3 → Test independently → Auto-creation and loud failures complete the contract
5. Polish (Phase 6) → README + quickstart validation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done, story phases proceed sequentially (single shared module `starwars_backgrounds.py`), but test-writing tasks within each phase can be parallelized across the two test files

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution IV — NON-NEGOTIABLE)
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- Avoid: vague tasks, same-file conflicts within a parallel batch, cross-story dependencies that break independence
