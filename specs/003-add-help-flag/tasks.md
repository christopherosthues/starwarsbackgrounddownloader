# Tasks: Help Flag

**Input**: Design documents from `/specs/003-add-help-flag/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: REQUIRED — Constitution Principle IV (Test-First) mandates tests written before implementation for every new behavior; help invocations are tested with no live network or browser launch.

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

- [X] T001 Run the existing test suite (`python -m unittest discover -s tests`) from repository root and confirm all feature-001/002 tests pass with no live network or browser launch; record the result as the pre-change baseline.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Bump the module-level `__version__` constant in starwars_backgrounds.py from `"1.1.0"` to `"1.2.0"` per research.md R4 (governance: public CLI options are a protected contract; this feature's spec is the amendment and requires a MINOR version bump). No user-facing flag is added here.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Learn what the tool does and how to use it (Priority: P1) 🎯 MVP

**Goal**: `--help` displays comprehensive curated usage information on stdout — a one-line description of what the tool does, every public option with its purpose and default value stated in human-readable terms, and at least one example invocation for each supported behavior (default run, custom output directory, forced re-download) — then exits 0 without performing any download, network request, or filesystem write; help text is plain ASCII-only and documented defaults match runtime defaults (FR-001, FR-002, FR-005, FR-006, SC-001, SC-002, SC-003).

**Independent Test**: Run the tool with `--help` in an empty scratch directory; verify exit code 0, full usage text on stdout (all options + defaults + examples), no files created, and no network activity.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T003 [US1] Write failing unit tests in tests/unit/test_cli.py (using the existing `_run_main` harness) for a `--help` invocation: exit code 0; stdout contains (a) a one-line description of what the tool does, (b) every public option name (`--help`, `-h`, `--overwrite`, `--output-dir`) with its purpose and default value — including `<Pictures>/StarWarsBackground` as the default directory and overwrite-off-by-default — and (c) at least one example invocation for each supported behavior (default run, custom output directory, forced re-download); stderr is empty; no network call is attempted (patched fetch raises if invoked) and no files are created in a temp working directory or default folder (FR-001, FR-002, FR-005, SC-003).
- [X] T004 [US1] Write failing unit tests in tests/unit/test_cli.py asserting the help text is ASCII-only: every character of captured `--help` stdout has code point < 128 (clarification Q1; FR-006 edge case — renders identically on any terminal, including legacy Windows console code pages).

### Implementation for User Story 1

- [X] T005 [US1] Implement in starwars_backgrounds.py per research.md R1/R2: build the argparse parser with `add_help=False`; register an explicit `-h`/`--help` flag (`action="store_true"`); add a module-level ASCII-only `HELP_TEXT` constant containing (a) the one-line description, (b) every public option with purpose and human-readable default value, and (c) at least one example invocation per supported behavior; after successful `parse_args()`, if help was requested print `HELP_TEXT` to stdout and return 0 BEFORE directory resolution or fetch setup. Make T003/T004 pass without altering any non-help invocation.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently — `python starwars_backgrounds.py --help` prints comprehensive usage information and exits 0 with zero side effects.

---

## Phase 4: User Story 2 - Short-form alias behaves identically (Priority: P2)

**Goal**: `-h` produces byte-identical usage information and exit status to `--help`, with no download activity for either form (FR-003, SC-004).

**Independent Test**: Run the tool with `-h` and separately with `--help`; verify identical output text and exit status 0 in both runs.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL (or are absent) before implementation**

- [X] T006 [US2] Write failing unit tests in tests/unit/test_cli.py: running `-h` and `--help` separately produce byte-identical stdout and identical exit status 0; neither form starts a download (patched fetch raises if invoked) (FR-003, SC-004).

### Implementation for User Story 2

- [X] T007 [US2] In starwars_backgrounds.py, verify both flag forms register to the same store_true attribute so `-h` and `--help` are handled by a single code path (adjust registration if drift is found); confirm no separate short-form handling exists. Make T006 pass.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently — both flag forms exist and behave identically.

---

## Phase 5: User Story 3 - Help takes precedence over other options (Priority: P3)

**Goal**: `--help`/`-h` combined with any combination of valid options yields help text + exit 0 with no side effects regardless of option order; an invalid value or unrecognized option produces a usage error naming the offending input on stderr with exit code 2 even when `--help` is also present (FR-004, FR-006, clarification Q2).

**Independent Test**: Run the tool with `--help --overwrite --output-dir <tmp>` (and reordered) — verify help only + exit 0; run `--output-dir "" --help` and `--bogus --help` — verify usage error naming the offending option + exit 2, no help displayed.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [US3] Write failing unit tests in tests/unit/test_cli.py: `--help --overwrite --output-dir <tmp>` and the same flags reordered both yield help text + exit 0 with no download started and no directory created; `--output-dir "" --help` and `--help --output-dir ""` both produce a usage error naming `--output-dir` on stderr with exit code 2 and NO help text displayed; `--bogus --help` produces a usage error naming the unrecognized option with exit code 2 (FR-004, FR-006, contracts/cli.md precedence table).

### Implementation for User Story 3

- [X] T009 [US3] In starwars_backgrounds.py, verify/adjust parser semantics per research.md R1: because parsing validates every value before the post-parse help check, invalid values and unrecognized options abort with argparse's standard usage error (exit 2) regardless of where `--help` appears, while valid combinations always reach the help path. Make T008 pass.

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T010 [P] Update README.md Options table to document `-h`/`--help` (comprehensive usage information on stdout, exit 0, no side effects) and note that non-help invocations are unchanged; keep documented defaults in sync with contracts/cli.md.
- [X] T011 Run quickstart.md validation end-to-end: execute all seven scenarios confirming help content requirements, byte-identical `-h`/`--help`, precedence rules (exit 2 naming the offending option), ASCII-only output, offline behavior, and unchanged non-help invocations; then run `python -m unittest discover -s tests` and confirm the full suite passes with no live network or browser launch.

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
- **User Story 2 (P2)**: Builds on US1's flag registration; independently testable via the `-h` invocation
- **User Story 3 (P3)**: Builds on US1/US2; verifies precedence semantics of the same parser/code path

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution IV — NON-NEGOTIABLE)
- Flag registration/help text before precedence verification
- Story complete before moving to next priority

### Parallel Opportunities

- T010 is independent of T011 within Phase 6 (different files, no dependencies)
- All other tasks share `starwars_backgrounds.py` or `tests/unit/test_cli.py`, so they execute sequentially per research.md R6 (single shared module; single test file by design decision)

---

## Parallel Example: User Story 1

```bash
# Write tests first (sequential — same test file):
Task: "Write failing unit tests in tests/unit/test_cli.py for --help content and no side effects" (T003)
Task: "Write failing unit tests in tests/unit/test_cli.py asserting ASCII-only help text" (T004)

# Then implement sequentially (single shared module):
Task: "Implement explicit -h/--help flag + HELP_TEXT constant in starwars_backgrounds.py" (T005)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (green baseline)
2. Complete Phase 2: Foundational (`__version__` bump to 1.2.0)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `python starwars_backgrounds.py --help` prints comprehensive usage information, exits 0, writes nothing, touches no network

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP: comprehensive `--help` works with zero side effects
3. Add User Story 2 → Test independently → `-h` proven byte-identical to `--help`
4. Add User Story 3 → Test independently → Precedence rules complete the contract (invalid values/unrecognized options still error)
5. Polish (Phase 6) → README sync + quickstart validation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done, story phases proceed sequentially (single shared module `starwars_backgrounds.py` and single test file `tests/unit/test_cli.py`); only Phase 6 tasks parallelize

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution IV — NON-NEGOTIABLE)
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- Avoid: vague tasks, same-file conflicts within a parallel batch, cross-story dependencies that break independence
