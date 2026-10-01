<!-- SYNC IMPACT REPORT (temporary scratch — remove before commit)
Version change: 1.0.0 → 1.1.0 (MINOR: single-source restriction + hard-fail contract added)
Modified principles:
  - II. Reliable Downloads — added requirement to exit with a non-zero error code when the source site is unreachable
Added sections: none
Removed sections: none
Deferred TODOs: none
-->

# Star Wars Background Downloader Constitution

## Core Principles

### I. Simplicity (NON-NEGOTIABLE)
The tool MUST remain a small, focused downloader for Star Wars backgrounds. Every feature MUST trace to an explicit spec; capabilities that do not serve downloading and saving backgrounds MUST NOT be added. Dependencies MUST be minimal: prefer the language standard library over third-party packages, and each new dependency MUST be justified in its plan document. Rationale: a small surface area keeps the tool easy to audit, test, and maintain.

### II. Reliable Downloads
Every download path MUST handle network failures gracefully with bounded retries and clear error reporting. Partial or corrupt files MUST NOT be left behind as if they were complete; writes MUST be atomic (temp file then rename) or cleaned up on failure. Where a source provides a checksum, integrity MUST be verified before the artifact is accepted. If the authorized source site is unreachable after bounded retries, the tool MUST exit with a non-zero error code and MUST NOT report success. Rationale: users trust the tool to deliver complete, valid image files without manual cleanup, and failures must be loud rather than silent.

### III. Safe Filesystem Writes
The tool MUST NOT overwrite existing files unless explicitly instructed by an option or flag; default output paths MUST be deterministic and documented in the spec. Re-running a completed download set MUST be idempotent (no duplicates, no errors). Rationale: re-runs are safe and user data is never silently destroyed.

### IV. Test-First (NON-NEGOTIABLE)
Tests MUST be written before implementation for every new behavior; the red-green-refactor cycle MUST be followed, with tests failing first and passing only after implementation. Network-dependent code MUST be tested against recorded fixtures or a local stub server rather than live endpoints in unit tests. Rationale: deterministic tests keep CI fast and independent of external availability.

### V. Observability
Every run MUST produce structured, human-readable progress output (item count, bytes downloaded, destination path) on stdout; errors MUST go to stderr with enough context to reproduce the failure (URL, attempt number, error type). Plain text I/O MUST remain debuggable without log infrastructure. Rationale: a downloader's primary user experience is its console output.

## Additional Constraints
- All background images MUST be sourced exclusively from https://www.starwars.com/news/star-wars-backgrounds; no other URLs or catalogs are permitted, whether configured or user-supplied.
- The tool MUST NOT perform network requests other than to fetch that page and the image assets linked from it; no telemetry, analytics, or phone-home behavior of any kind.
- Output files MUST use common image formats (e.g., JPEG/PNG); unsupported or unrecognized formats MUST be rejected with a clear error rather than silently written.

## Development Workflow & Quality Gates
- Every change MUST pass the full test suite before merge; CI MUST run tests on every commit and pull request.
- Public CLI options and output file naming rules are contracts: changes to them require a spec amendment and a version bump per Governance.
- Code review MUST verify compliance with this constitution; any violation MUST be documented as an explicit exception in the change description.

## Governance
This constitution supersedes all other project practices; where project documents conflict, this document wins. Amendments MUST edit this file directly, increment `CONSTITUTION_VERSION` per semantic versioning (MAJOR: principle removal or redefinition; MINOR: new principle/section added or materially expanded; PATCH: clarifications and wording fixes), and update the Last Amended date. Compliance review is expected on every change set; complexity beyond these principles MUST be justified in writing.

**Version**: 1.1.0 | **Ratified**: 2026-10-01 | **Last Amended**: 2026-10-01
