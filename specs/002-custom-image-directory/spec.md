# Feature Specification: Custom Image Output Directory

**Feature Branch**: `002-custom-image-directory`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "The user should be able to provide a directory to store the images in"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Direct downloads to a chosen folder (Priority: P1)

A user runs the downloader and provides a directory of their choosing. Every background image is saved into that directory instead of the standard Pictures-based output folder, so the collection lands exactly where the user wants it — for example, a project folder, an external drive, or a folder organized by theme.

**Why this priority**: This is the core value of the feature. Without honoring a user-provided directory, users must move files after every run, defeating the purpose of the option.

**Independent Test**: Run the tool with a user-provided directory and verify that 100% of downloaded images appear in that directory (and none in the default folder), with progress output naming each destination path.

**Acceptance Scenarios**:

1. **Given** an existing writable directory on the machine, **When** the user runs the downloader specifying that directory as the image location, **Then** every background is saved inside that directory and no images are written to the default Pictures-based folder.
2. **Given** a successful run with a specified directory, **When** the user reviews the console output, **Then** each item's reported destination path points into the specified directory.

---

### User Story 2 - Default behavior is unchanged (Priority: P2)

A user who runs the downloader without specifying any directory gets exactly the same behavior as before this feature: images are saved to the standard "StarWarsBackground" folder inside the platform Pictures directory. Existing workflows, scripts, and expectations keep working with zero changes.

**Why this priority**: The tool's existing contract (default output location, idempotent re-runs) is trusted by current users; any change to default behavior would break that trust. Backward compatibility is a hard requirement for an additive option.

**Independent Test**: Run the tool with no directory specified and verify the images land in the standard Pictures-based folder exactly as before this feature existed.

**Acceptance Scenarios**:

1. **Given** a machine where the default output folder does not yet exist, **When** the user runs the downloader without specifying a directory, **Then** the standard "StarWarsBackground" Pictures folder is created and used, identical to pre-feature behavior.
2. **Given** a completed download in the default folder, **When** the user re-runs the tool without options, **Then** existing files are not overwritten and no duplicates appear (idempotent).

---

### User Story 3 - Safe handling of new or invalid target locations (Priority: P3)

A user specifies a directory that does not exist yet — perhaps nested several levels deep — and it is created automatically. If the specified location cannot be used as an image folder (for example, a path that exists but is a file, or a location where creation fails), the tool reports a clear error naming the problem and exits with a failure status instead of writing images somewhere unexpected.

**Why this priority**: Users will naturally point the tool at fresh paths; auto-creation makes the option convenient, while loud failures on unusable targets protect user data and keep runs reproducible from console output alone.

**Independent Test**: Run the tool pointing at (a) a nonexistent nested path — verify it is created and populated — and (b) a path that collides with an existing file — verify a clear error, non-zero exit, and no stray writes.

**Acceptance Scenarios**:

1. **Given** a specified directory path that does not exist (including missing parent folders), **When** the user runs the downloader, **Then** the full folder structure is created and all images are saved there successfully.
2. **Given** a specified path that exists but is a file rather than a folder, **When** the user runs the downloader, **Then** the tool reports an error naming the offending path, exits with a non-zero status, and does not modify or delete the existing file.

---

### Edge Cases

- What happens when the specified directory already contains unrelated files? They MUST be left untouched; safe-write rules (no overwrite by default, idempotent re-runs) apply identically to custom directories as to the default folder.
- How does the system handle a relative path (e.g., `./backgrounds`)? It is interpreted relative to the directory from which the tool was invoked and reported in output as the resolved location.
- What happens when the specified directory cannot be created or written to (permissions, read-only volume, invalid characters)? The tool MUST report a clear error naming the path and reason, exit with a non-zero status, and leave no partial files behind.
- How does an explicitly provided but empty directory value behave? It is treated as an invalid usage: the tool reports a clear usage error and exits non-zero rather than silently falling back to the default folder.
- What happens when two backgrounds would produce the same file name inside the custom directory? Names MUST be made unique deterministically, exactly as in the default folder (no silent overwrites within one run).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST accept a user-provided directory that designates where downloaded images are saved.
- **FR-002**: When a directory is provided, every downloaded image MUST be saved inside that directory; no images MAY be written to the default Pictures-based folder during that run.
- **FR-003**: When no directory is provided, behavior MUST remain exactly as specified for the standard output folder ("StarWarsBackground" inside the platform Pictures directory), created if it does not exist.
- **FR-004**: If the provided directory (or any of its missing parent folders) does not exist, the tool MUST create them before saving images; creation failures MUST produce a clear error naming the path and reason with a non-zero exit status.
- **FR-005**: If the provided path exists but is not a directory, the tool MUST report an error naming the path, exit with a non-zero status, and leave the existing file untouched.
- **FR-006**: Safe-write rules MUST apply identically to custom directories: existing files are never overwritten unless explicitly instructed by the overwrite option, re-runs against the same directory are idempotent, and unrelated pre-existing files in the directory are left untouched.
- **FR-007**: A relative provided path MUST be interpreted relative to the current working directory; an absolute path MUST be used as given. Progress output for each item MUST report the resolved destination path.
- **FR-008**: An explicitly provided but empty or blank directory value MUST be rejected with a clear usage error and non-zero exit status; it MUST NOT silently fall back to the default folder.
- **FR-009**: The tool MUST exit with a non-zero status whenever the specified directory cannot be created, is not usable as an image folder, or any download fails; success (status 0) requires every requested background saved into the effective output directory.

### Key Entities *(include if feature involves data)*

- **Output Directory**: The location where images are saved for a run. Attributes: user-provided path (or default when unspecified), resolved absolute location, whether it was created by this run.
- **Download Run**: A single invocation of the tool. Attributes: effective output directory, total items found, items downloaded successfully, items failed (with reasons), bytes transferred, final exit status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can direct a full download run to any writable location with a single option; 100% of saved images appear in the specified directory and 0 appear in the default folder when the option is used.
- **SC-002**: Running without the option produces behavior identical to before this feature: 100% of images land in the standard Pictures-based folder, with zero changes observable by existing users.
- **SC-003**: A specified directory that does not exist yet (including nested paths) is created automatically and populated successfully on the first run, with no manual pre-creation step required.
- **SC-004**: In 100% of cases where the target location is unusable (path is a file, cannot be created, or unwritable), the user sees an error naming the offending path and receives a non-zero exit status, with no partial files left behind as if complete.
- **SC-005**: Re-running against the same custom directory produces 0 overwritten or duplicated files and 0 errors (idempotent).

## Assumptions

- The option is additive: it changes only where images are saved; source page, image selection, file naming rules, retry behavior, and overwrite semantics from the base downloader feature are unchanged.
- A missing specified directory (including missing parents) is created automatically rather than rejected; this matches common download-tool conventions and keeps first use frictionless.
- Relative paths resolve against the current working directory of the invocation; no additional path interpretation rules (e.g., environment variable expansion beyond what the operating system shell already performs) are assumed.
- The chosen directory is not remembered across runs: each invocation uses either its provided directory or the default, with no configuration file or persistent preference store.
- Safe-write and idempotency guarantees from the base feature apply unchanged to custom directories; the overwrite option, when used, applies within whatever directory is effective for that run.
