## Purpose

Describes how the keyboard's OpenRGB support is delivered: a local patch that stays current with upstream OpenRGB, and the rules for moving that support upstream.

## ADDED Requirements

### Requirement: The local patch applies to current upstream
The repository's OpenRGB patch SHALL apply cleanly to upstream OpenRGB `master` and build. When it stops applying, the failure SHALL be reported and the previously built OpenRGB SHALL stay in use.

#### Scenario: Upstream unchanged
- **WHEN** neither upstream nor the patch changed since the last build
- **THEN** the updater does nothing

#### Scenario: Patch no longer applies
- **WHEN** an upstream change makes the patch fail to apply
- **THEN** the updater keeps the previous binary, logs the reason, and notifies the user

#### Scenario: Patch repaired
- **WHEN** the patch is updated to apply again
- **THEN** the next updater run builds it and replaces the binary only after a successful build and start check

### Requirement: The two patch copies are identical
The patch in this repository and the patch in the fork SHALL be byte-identical after every patch change.

#### Scenario: After a patch change
- **WHEN** the patch is changed in this repository
- **THEN** the same file is pushed to the fork and both have the same SHA-256

### Requirement: Upstream submissions follow upstream's contribution rules
A submission to upstream OpenRGB SHALL be made by a human who has reworked and fully reviewed the code and written the description. It SHALL NOT contain AI authorship credits. It SHALL NOT be made before the owner has decided to submit.

#### Scenario: Unreworked patch
- **WHEN** the patch has not been reworked and reviewed by its human submitter
- **THEN** it is not submitted upstream

#### Scenario: Agent asked to submit
- **WHEN** an automated agent is asked to open or push the upstream merge request
- **THEN** it declines and leaves the submission to the human submitter

### Requirement: Flash-wear protection is kept
The OpenRGB device for this keyboard SHALL coalesce saved writes to at most one per second, SHALL skip per-key writes identical to the stored block, and SHALL never save Direct-mode colours. This holds for the local patch and for any version submitted upstream.

#### Scenario: Slider drag in Custom mode
- **WHEN** a client sends many Custom-mode updates within one second
- **THEN** the first is written at once and the rest are reduced to at most one saved write per second, keeping only the latest

#### Scenario: Unchanged picture
- **WHEN** a client saves a Custom picture identical to the stored one
- **THEN** nothing is written to the keyboard

#### Scenario: Animation
- **WHEN** a client streams frames in Direct mode
- **THEN** no frame is saved on the keyboard

### Requirement: Tested claims only
The merge request description and this repository's documents SHALL claim a mode, connection or platform as tested only when a recorded hardware check exists for it.

#### Scenario: Untested platform
- **WHEN** Windows or macOS has not been tested on hardware
- **THEN** the description says so

### Requirement: The local patch shrinks after a merge
After upstream merges part or all of the support, the repository's patch SHALL drop the merged parts, and the documents SHALL say which OpenRGB version users need.

#### Scenario: Full merge
- **WHEN** upstream contains all of the support
- **THEN** the documents point users to upstream OpenRGB and the local patch is retired in a follow-up change
