# Research: Custom Image Output Directory

**Feature**: `002-custom-image-directory` | **Date**: 2026-10-02

All technical-context unknowns were resolvable from the existing codebase and feature 001's decisions; no NEEDS CLARIFICATION items remained. The research below records the design decisions this feature makes, with rationale and rejected alternatives.

## R1: Option syntax — `--output-dir <path>` flag

**Decision**: Add a single optional flag `--output-dir <path>` (argparse, one value) to `starwars_backgrounds.py`. No positional arguments are introduced; the existing "no positional arguments" contract is preserved.

**Rationale**: The tool already follows the additive-flag convention (`--overwrite`). A named flag is self-documenting in `--help`, composes cleanly with `--overwrite` (both can be given in any order), and keeps invocation backward compatible — every existing command line remains valid with identical behavior (FR-003).

**Alternatives considered**:
- *Positional argument (`python starwars_backgrounds.py [dir]`)*: rejected — breaks the documented "no positional arguments" contract, is less discoverable than a named flag for an optional feature, and complicates adding further options later.
- *Environment variable (e.g., `OUTPUT_DIR`)*: rejected — hidden configuration conflicts with Constitution V (console output/debuggability) and the spec's assumption that the chosen directory is not remembered across runs; a flag is visible in every invocation.

## R2: Path resolution semantics

**Decision**: The provided value is interpreted as follows, in order:
1. Blank/empty values are rejected at parse time (see R3).
2. `~` and environment-variable references are expanded (`Path.expanduser()`), matching standard CLI conventions so quoted `"~/backgrounds"` works.
3. Relative paths resolve against the current working directory of the invocation; absolute paths are used as given (FR-007).
4. The effective output directory is normalized to an absolute path for existence checks and for all progress/summary reporting, so reported destination paths are unambiguous regardless of how the user typed the option.

**Rationale**: pathlib already provides `expanduser()`; resolving relative paths against CWD is the least-surprising behavior for a CLI tool and matches FR-007 verbatim. Normalizing to an absolute path makes FR-007's "resolved destination path" reporting deterministic and keeps skip-existing checks (which compare file names) consistent with what users see on screen.

**Alternatives considered**:
- *Require absolute paths*: rejected — forces users to type full paths for the common `./backgrounds` case; adds friction without safety benefit.
- *Resolve symlinks (`Path.resolve(strict=False)`)*: not required; plain normalization (absolute + expanduser) is sufficient and avoids surprising behavior on symlinked folders.

## R3: Validation and error taxonomy

**Decision**: Three distinct failure classes, mapped to the existing exit-code contract:

| Condition | Detection point | Behavior | Exit code |
|-----------|-----------------|----------|-----------|
| Empty/blank value (e.g., `--output-dir ""` or whitespace-only) | Parse time, via a custom argparse type that raises `ArgumentTypeError` | argparse prints usage error to stderr and exits | 2 (usage error, per existing contract) |
| Path exists but is not a directory (file, or symlink resolving to non-directory) | Before any download, after parsing | `ERROR <path>: not a directory — cannot use as output location` on stderr; nothing written or modified | 1 |
| Directory (or missing parents) cannot be created (`OSError`: permissions, read-only volume, invalid characters, path too long) | Creation step, before any download | `ERROR <path>: <reason>` naming the offending path and reason on stderr | 1 |

A directory that is created successfully but later proves unwritable surfaces through the existing per-item failure reporting (each item fails with its error context; summary shows failures; exit status 1), satisfying FR-009 without a separate pre-flight writability probe.

**Rationale**: Blank values are a usage mistake, so they follow the `argparse` convention already in the contract (exit 2). "Exists but is not a directory" and creation failures are runtime environment failures, matching the existing exit-1 semantics for "output directory not writable". Failing before any download means an unusable target never produces partial output or modified state.

**Alternatives considered**:
- *Treat blank value as "use default"*: rejected — FR-008 explicitly forbids silent fallback to the default folder; a user who typed `--output-dir ""` must be told their input was invalid, not silently redirected.
- *Pre-flight writability probe (test-write a temp file)*: rejected as over-engineering — per-item error reporting already names each failure with full context and yields exit 1; the probe would add platform-dependent false positives for little user-visible gain.

## R4: Interaction with `--overwrite` and idempotency

**Decision**: The existing skip/overwrite logic is unchanged in behavior; it operates on the *effective* output directory (custom when provided, default otherwise). Re-running against the same custom directory skips existing files exactly as today (FR-006), and `--output-dir <dir> --overwrite` re-downloads into `<dir>` only.

**Rationale**: The skip check derives destination file names from gallery position/title and tests existence inside the output root; it is already parameterized by that root, so no logic change is needed — only the root's source changes. This guarantees FR-006 (identical safe-write semantics) with minimal diff.

**Alternatives considered**:
- *Per-directory override state or per-run bookkeeping*: rejected — nothing in the spec requires remembering which directory was used; idempotency is defined purely by file presence at destination, as today.

## R5: Governance bookkeeping for a protected CLI surface

**Decision**: The constitution's Development Workflow section makes public CLI options a governance-protected contract requiring "a spec amendment and a version bump". Feature 002's specification *is* the amendment (it amends feature 001's FR-003 default-output rule by adding an override). Because no version mechanism exists in the codebase yet, this feature introduces a minimal module-level `__version__ = "1.1.0"` constant in `starwars_backgrounds.py` (bump from implicit 1.0.0), documented as the contract version. No user-facing `--version` flag is added — exposing it is out of scope for this feature and would expand the CLI surface beyond what the spec requires (Constitution I).

**Rationale**: A single constant satisfies the "version bump" requirement with zero runtime behavior change, keeps the surface minimal, and gives future contract changes a concrete baseline to bump.

**Alternatives considered**:
- *Add `--version` flag*: rejected — not required by the spec; adds CLI surface area beyond the feature's scope (Constitution I).
- *Skip versioning until a second contract change occurs*: rejected — Governance requires the bump at the time of the change, and deferring leaves this amendment untracked.
