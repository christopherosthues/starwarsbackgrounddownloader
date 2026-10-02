# Feature Specification: Help Flag

**Feature Branch**: `003-add-help-flag`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Add a help flag"

## Clarifications

### Session 2026-10-02

- Q: Should the help text be restricted to ASCII characters so it renders correctly on any terminal, including legacy Windows consoles? → A: Yes — help output MUST be plain ASCII; no non-ASCII characters anywhere in the help text.
- Q: When `--help` appears alongside a recognized flag with an invalid value (e.g., a blank `--output-dir`), should the tool still display help? → A: No — an invalid value still produces a usage error naming the offending option, even if `--help` is also present.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learn what the tool does and how to use it (Priority: P1)

A user who has never run the downloader invokes it with `--help` and immediately sees complete usage information: what the tool does, every public option with its purpose and default value, and examples of common invocations. The invocation ends right away — no downloading begins, nothing is written to disk, and no network connection is attempted.

**Why this priority**: This is the core value of the feature. A help flag that exists but leaves users guessing at options or defaults fails its purpose; complete, self-contained usage information is what makes first-time use frictionless.

**Independent Test**: Run the tool with `--help` on a machine with no network access and an empty output folder; verify the full usage text appears (covering every public option and its default), the exit status is 0, no files were created or modified outside normal process behavior, and no network activity occurred.

**Acceptance Scenarios**:

1. **Given** any installation of the tool, **When** the user runs it with `--help`, **Then** usage information appears describing the tool's purpose, every public option (including its default value), and at least one example invocation for each supported behavior, and the tool exits with status 0 without starting a download.
2. **Given** the help output from a single run, **When** a new user reads it, **Then** they can determine how to change where images are saved and how to force re-downloading of existing files without trial and error or consulting any other documentation.

---

### User Story 2 - Short-form alias behaves identically (Priority: P2)

A user who prefers short flags invokes the tool with `-h` and gets exactly the same result as `--help`: identical usage information, immediate exit, status 0, no download activity.

**Why this priority**: The short form is a universal CLI convention; users muscle-memory `-h`. Supporting it identically keeps the flag predictable without adding any new behavior surface.

**Independent Test**: Run the tool with `-h` and verify the output text and exit status are identical to those produced by `--help`, with no download or network activity.

**Acceptance Scenarios**:

1. **Given** any invocation context, **When** the user runs the tool with `-h`, **Then** the same usage information as `--help` is displayed and the tool exits with status 0 without starting a download.
2. **Given** both forms of the flag, **When** each is run separately, **Then** their outputs are identical in content (modulo nothing — same text) and exit status.

---

### User Story 3 - Help takes precedence over other options (Priority: P3)

A user who includes `--help` alongside any combination of the tool's other options gets help output and a clean exit, regardless of what else was on the command line. The flag is safe to use for experimentation without side effects.

**Why this priority**: Users commonly type `tool --help <other flags>` or discover the flag while composing a longer command; help must win so that asking for help never triggers a download run or an error about unrelated options.

**Independent Test**: Run the tool with `--help` combined with other valid options (e.g., an output directory and overwrite) and verify only help is displayed, exit status is 0, and no download occurred.

**Acceptance Scenarios**:

1. **Given** a command line that includes `--help` together with any combination of the tool's other public options, **When** the user runs it, **Then** usage information is displayed and the tool exits with status 0 without starting a download or writing image files.
2. **Given** a command line containing an unrecognized option (with or without `--help`), **When** the user runs it, **Then** the tool reports a clear usage error naming the offending option and exits with a non-zero status rather than silently ignoring it.

---

### Edge Cases

- What happens when `--help` is combined with other options? Help output is displayed and the tool exits with status 0; no download, network request, or image file write occurs for any combination of valid options alongside the flag.
- How does help behave offline (no network available)? Identically to online: usage information is displayed from local knowledge only, with exit status 0.
- What happens when the default output folder does not exist and `--help` is run? The tool MUST NOT create it; help performs no filesystem writes at all.
- How does the tool handle an unrecognized option or misspelled flag? It reports a usage error naming the offending input and exits with a non-zero status (existing behavior preserved).
- What happens when `--help` is combined with a recognized flag that has an invalid value (e.g., a blank output directory)? The usage error naming the offending option takes precedence over help; the tool exits with a non-zero status without displaying help.
- What happens when help output is piped to another program or redirected? The text is plain, stable, human-readable output on stdout suitable for capture; its content does not depend on terminal size or interactive state.
- What happens when help is displayed on a terminal that does not support UTF-8 (e.g., legacy Windows console code pages)? The help text contains no non-ASCII characters, so it renders correctly regardless of the terminal's character encoding; no garbled output or crashes occur.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST provide a `--help` option that displays complete usage information and exits without performing any download, network request, or filesystem write.
- **FR-002**: The help output MUST include: (a) a one-line description of what the tool does; (b) every public option with its name, purpose, and default value; (c) at least one example invocation for each supported behavior (default run, custom output directory, forced re-download).
- **FR-003**: The `-h` short form MUST behave identically to `--help`: same usage information, same exit status, no download activity.
- **FR-004**: When the help option is present on the command line alongside any combination of other valid options, the tool MUST display help and exit with status 0 without starting a download or writing image files. If another option's value is invalid, the usage error naming that option takes precedence over help.
- **FR-005**: The default values documented in the help output MUST match the tool's actual runtime defaults (default output location, no-overwrite-by-default).
- **FR-006**: Help output MUST be written to stdout as plain, ASCII-only text (no non-ASCII characters); errors for unrecognized options MUST go to stderr with a non-zero exit status.
- **FR-007**: Invocations that do not include the help option MUST behave exactly as before this feature: same options, same defaults, same download behavior, and same exit statuses (backward compatible).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the tool's public options appear in `--help` output with their correct default values; a reviewer comparing help text against actual runtime defaults finds zero discrepancies.
- **SC-002**: A user who has never used the tool can determine, from `--help` output alone, how to perform each supported behavior (default download, custom directory, forced re-download) — verified by successfully executing all three behaviors using only information present in the help text.
- **SC-003**: Running `--help` or `-h` completes in under 2 seconds on any machine, works with no network connectivity, performs zero network requests, writes zero files, and exits with status 0 in 100% of invocations.
- **SC-004**: Both flag forms produce identical usage information and exit status; combining the flag with other valid options still yields help output and status 0 with no download started.
- **SC-005**: Existing users experience zero behavioral change: every command line that did not include a help option before this feature produces identical results after it (same files, same output, same exit statuses).

## Assumptions

- The tool's existing public options (`--overwrite`, `--output-dir`) and their semantics are unchanged; the help flag is purely additive.
- A single level of help is sufficient for v1: no extended/verbose help levels, subcommand-style help topics, or interactive prompts are required.
- Help output documents defaults in human-readable terms (e.g., "the platform Pictures folder") rather than embedding machine-specific paths that vary per user.
- The tool's existing exit-status conventions apply: successful invocations (including help) exit 0; usage errors and failures exit non-zero.
- No localization, formatting, or display-styling requirements beyond plain-text readability are assumed for v1.
