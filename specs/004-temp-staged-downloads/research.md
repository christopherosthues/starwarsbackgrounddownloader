# Research: Temp-Staged Downloads with Hash Deduplication

**Feature**: `004-temp-staged-downloads` | **Date**: 2026-11-05

All technical-context unknowns were resolvable from the existing codebase, features 001–003 decisions, and the clarified spec; no NEEDS CLARIFICATION items remained. The research below records the design decisions this feature makes, with rationale and rejected alternatives.

## R1: Temp staging directory resolution and lifecycle

**Decision**: Use stdlib `tempfile.gettempdir()` as the platform-standard temp root (Windows `%TEMP%` = `%AppData%\Local\Temp`, macOS/Linux `$TMPDIR` or `/tmp`). Per-run layout is `<Temp>/swbdl/<datetime>` where `<datetime>` is ISO 8601 `YYYYMMDD-HHMMSS`, with an incrementing counter suffix appended if the subfolder already exists. Lifecycle:

1. **Start**: Delete stale subfolders of `<Temp>/swbdl` — those whose last modification is older than `STALE_STAGING_AGE_SECONDS` (1 hour), i.e., leftovers from crashed/interrupted runs — then create a fresh `<datetime>` subfolder. Fresh subfolders (e.g., from a concurrently running instance) are left alone so overlapping runs do not wipe each other's staged files mid-run.
2. **During**: All image downloads write into the per-run subfolder only.
3. **End** (success, failure, or exception): Delete this run's `<datetime>` subfolder — including any staged files for failed items — and delete `<Temp>/swbdl` itself once it becomes empty.

**Rationale**: `tempfile.gettempdir()` is stdlib and matches the spec assumption of "the platform-standard temp directory resolved via cross-platform means" without adding a dependency. Stale-only cleanup at start satisfies the edge case "detected and reused or cleaned before starting; stale files are removed". Deleting this run's subfolder after every run implements FR-005 and clarification Q1 (move-phase failure deletes everything) with one code path: successful images have already been moved to the target, so nothing user-visible is lost. Scoping cleanup to the per-run subfolder (instead of wiping `<Temp>/swbdl` wholesale) makes overlapping instances safe: a second instance starting or finishing while another is mid-run can no longer delete its staged files before the move phase (observed failure mode: `WinError 2` on every move).

**Alternatives considered**:
- *`platformdirs.temp_dir()`*: rejected — `tempfile.gettempdir()` is the direct stdlib equivalent, already in the language standard library, and avoids a second source of truth for platform paths (the existing `platformdirs` dependency is used only for the Pictures default).
- *Wipe `<Temp>/swbdl` entirely at start and end (original design)*: replaced — a second instance starting or finishing while another was mid-run deleted its staged files, producing `WinError 2` on every move; per-run subfolder cleanup plus empty-root deletion preserves FR-005 for single runs while making overlapping instances safe.

## R2: Content hashing and duplicate detection (stateless)

**Decision**: SHA-256 via stdlib `hashlib`, computed by streaming reads in 1 MiB chunks so memory stays bounded regardless of image size. Duplicate detection is stateless per clarification Q4:

1. **Run start**: Walk the effective target directory and compute the SHA-256 of every existing file → baseline hash set. Files that cannot be read produce an `ERROR` line naming the path but do not abort the run; they simply contribute no hash.
2. **Per staged image**: Hash the staged file after download. If its hash is in the seen set (baseline ∪ hashes of files already moved this run), delete the staged file and report it as a duplicate discard. Otherwise move it to the target and add its hash to the seen set.

**Rationale**: FR-001 mandates "hashed at run start" comparison against existing target content; streaming chunked reads honor the spec's note that "content can be large"; first-seen-wins for same-hash-different-name images implements the edge case ("only one copy is kept ... under its original link-derived name"); no manifest or state file keeps the tool stateless and makes manual deletion of a target file self-healing on re-run (edge case).

**Alternatives considered**:
- *Persistent hash manifest between runs*: rejected — clarification Q4 explicitly chose stateless re-download-and-compare over persistent state.
- *Name-based deduplication instead of content hashing*: rejected — FR-001 mandates hash comparison; names change with this feature and are not a reliable identity.
- *Load whole files into memory for hashing*: rejected — images can be large; chunked streaming is strictly safer at zero cost.

## R3: URL-derived file naming and fallback

**Decision**: The saved base name is the basename of `urlparse(source_url).path` after query/fragment stripping (the existing canonical-URL step already strips queries). Refinements, in order:

1. If the extracted base name is empty or has no extension → fall back to the existing position/title derivation (`NNN-title.ext`) so degenerate URLs still produce deterministic names (spec edge case).
2. The file extension is replaced with the detected format's extension (`.jpg`/`.png`) so the on-disk extension always matches the magic-byte-validated content (Constitution C3; existing behavior already ties extension to detected format).
3. Windows-illegal characters (`<>:"/\|?*` and control characters) are replaced with `-`, and trailing dots/spaces stripped — filesystem safety without altering normal CDN names.

**Rationale**: FR-002 requires "the base name embedded in the source download URL". The fallback preserves feature 001's deterministic naming for URLs with no recognizable file name, and extension correction keeps format validation authoritative rather than trusting URL text.

**Alternatives considered**:
- *Keep the URL's extension verbatim even when content differs*: rejected — Constitution C3 requires common image formats and existing behavior rejects unrecognized content; a `.jpeg` URL serving PNG must land as `.png`.
- *Apply full title-style sanitization (lowercase, hyphen-collapse) to URL names*: rejected — that would alter "the name of the file in the link" for ordinary CDN names, violating FR-002's intent.

## R4: Sequential postfix collision resolution

**Decision**: At move time, if the destination path already exists, append `-1`, `-2`, ... before the extension until a free name is found (spec assumption: numbering starts at `-1`). The existence check runs against the live target directory state, so both pre-existing files and files moved earlier in the same run are handled uniformly.

**Rationale**: FR-006 and SC-004 mandate postfix resolution for new-vs-existing conflicts. Checking live directory state (rather than a precomputed name set) naturally covers intra-run collisions even though clarification Q3 assumes source URLs produce unique base names — defensive at zero extra state cost.

**Alternatives considered**:
- *Precompute the occupied-name set from the run-start listing only*: rejected — misses files moved earlier in the same run; live checks are simpler and correct by construction.
- *Fail on collision*: rejected — FR-006 mandates automatic postfix resolution, not an error.

## R5: Two-phase pipeline and best-effort semantics

**Decision**: The run executes as two phases plus cleanup:

1. **Download phase**: Fetch article HTML (existing Selenium path), parse the gallery (existing parser), then download every item into the staging subfolder with existing bounded retries and backoff. A per-item failure is recorded (`ItemResult` FAILED, `ERROR` line) and the loop continues to the next item; a configurable delay (R6) applies between requests.
2. **Move phase**: For each successfully staged file: hash it, discard hash matches (delete staged file), otherwise move it to the target with postfix resolution (R4). Moves use `shutil.move` so cross-device moves (e.g., temp on one volume, Pictures on another) work; a failed move is reported per item.
3. **Cleanup**: Delete this run's staging subfolder (and `<Temp>/swbdl` if it becomes empty) regardless of outcome.

Exit status: 0 only if zero items failed; otherwise 1 with per-item `ERROR` lines naming URL and reason (clarification Q5).

**Rationale**: SC-003 requires "100% of downloaded images appear first in the temp staging folder before being moved"; FR-004/FR-008 and clarification Q5 require best-effort moves with individual failure reporting; uniform cleanup covers both normal completion and move-phase failure (clarification Q1) without separate code paths.

**Alternatives considered**:
- *Interleaved per-item download→move*: rejected — SC-003 mandates staging-first, and two phases make the run-start baseline hash set valid for the whole move phase.
- *All-or-nothing moves (any failure blocks all)*: rejected — clarification Q5 chose best-effort; it also aligns with feature 001's contract that successful downloads are kept when others fail.

## R6: `--delay` throttling option

**Decision**: New optional flag `--delay <seconds>` (float, default **0.2**, minimum 0) that sleeps between successive image download requests — i.e., after each completed HTTP request attempt (success or failure), before the next request is issued; retry backoff remains unchanged and additive. Blank or negative values are rejected as a usage error (exit 2).

**Rationale**: FR-009 mandates configurable throttling with a 0.2s default to keep ~100-image runs comfortably under 2 minutes (clarification Q2: "1 second delay would lead to a 2 minute run → too long"). Applying the delay per request (not per item) also spaces out retry bursts, giving the CDN the most even request stream for the same option surface.

**Alternatives considered**:
- *Fixed non-configurable delay*: rejected — clarification Q2 chose configurable via CLI option.
- *Per-item delay only (skip during retries)*: weaker protection with more complex logic; per-request is a superset and simpler to state.

## R7: `--overwrite` interaction with hash deduplication

**Decision**: `--overwrite` keeps its purpose — "re-download and replace files that already exist" — under the new scheme: when set, a staged file whose derived name matches an existing target file **replaces** it (atomic move) instead of receiving a sequential postfix. Hash-match discards still apply either way (identical content is a no-op). Without `--overwrite`, existing target files are never replaced.

**Rationale**: Constitution III forbids overwriting "unless explicitly instructed by an option or flag"; the flag is a governance-protected contract that this spec does not remove, so it must retain meaningful semantics. This interpretation preserves both contracts with the minimal semantic shift: replacement happens at the name level, deduplication stays content-based.

**Alternatives considered**:
- *Remove `--overwrite`*: rejected — breaking CLI contract change not sanctioned by this feature's spec; would require a MAJOR version bump and user-visible loss of capability.
- *Treat `--overwrite` as "disable hash dedup entirely"*: rejected — under clarification Q4 every run re-downloads everything anyway, so disabling dedup has no observable effect beyond replacement at the name level.

## R8: Progress output and summary format

**Decision**: Two-phase stdout progress (Constitution V, FR-010):

- Download phase: `[i/N] <title> -> <staged-path> (<bytes>)` per item.
- Move phase: one line per staged file — moved items show the final target path; duplicate discards report `<name>: duplicate (hash match)`; postfix-resolved names show the renamed destination.
- Summary: `Summary: X moved, Y duplicates discarded, Z failed. Output folder: <effective-output-dir>`.

`ERROR` lines on stderr keep the existing convention (URL, attempt number, error type); move-phase failures additionally name the target path and reason.

**Rationale**: FR-010 requires human-readable progress with item count, bytes per item, and destination path; the two phases are distinct enough that labeling them keeps console output debuggable without log infrastructure (Constitution V). The summary's outcome vocabulary matches the spec's Key Entities ("items moved to target", "items discarded as duplicates").

**Alternatives considered**:
- *Single unified per-item line across both phases*: rejected — an item is reported twice by design in a two-phase pipeline; separate phase lines make the staging→move transition visible, which SC-003 validation depends on.

## R9: Governance bookkeeping for protected CLI surfaces

**Decision**: The constitution's Development Workflow section makes public CLI options and output file naming rules governance-protected contracts requiring "a spec amendment and a version bump". This feature's specification *is* the amendment (it changes the naming rule from position-based to URL-derived and adds `--delay`). Because the module-level `__version__` constant exists since feature 002, it is bumped **1.2.0 → 1.3.0** (MINOR: additive option + amended naming contract).

**Rationale**: A MINOR bump matches semantic versioning for an expanded-but-not-breaking contract change; the spec amendment requirement is satisfied by this feature's specification and clarification record.

**Alternatives considered**:
- *MAJOR bump*: rejected — no CLI option is removed or redefined incompatibly (`--overwrite` retains its purpose per R7).
- *No bump*: rejected — Governance requires a bump whenever protected surfaces change, and both the naming rule and the option set change here.
