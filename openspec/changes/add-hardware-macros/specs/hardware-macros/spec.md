## Purpose

Lets the user store macros on the keyboard, assign them to keys or Super Buttons, and back up and restore the keyboard's macro storage, without risking data the tools cannot put back.

## ADDED Requirements

### Requirement: Writes stay disabled until the format is proven
The tools SHALL reject every macro write until the research log records the erase extent of the write sequence, the metadata layout, and the timer and repeat semantics, each with its evidence.

#### Scenario: Write attempted before the proof
- **WHEN** a macro write is requested and the proofs are not recorded
- **THEN** the tools refuse before sending any command to the keyboard

### Requirement: Store a macro on the keyboard
The tools SHALL write a local macro to one macro block on the keyboard after explicit approval. Before the write they SHALL back up every block the write can affect. After the write they SHALL verify the block by readback.

#### Scenario: Preview by default
- **WHEN** the user asks to store a macro without approving the write
- **THEN** the tools show which block and bytes would change and write nothing

#### Scenario: Approved write
- **WHEN** the user approves storing a valid macro
- **THEN** the tools save a macro backup, write the block, read it back, and report success only if the readback matches

#### Scenario: Identical macro
- **WHEN** the compiled macro equals the stored block
- **THEN** the tools write nothing

#### Scenario: Macro the keyboard cannot hold
- **WHEN** the macro has more than 1008 events or uses a feature the stored format cannot express
- **THEN** the tools refuse and name the problem before any device access

#### Scenario: Failure during the write
- **WHEN** a write or readback fails
- **THEN** the tools stop, do not retry, and report the backup path

### Requirement: Assign a macro to a key
The tools SHALL assign a stored macro to a key or a Super Button (K1–K8) as a staged profile change. They SHALL write the key assignment only after the macro block has been verified.

#### Scenario: Assign to a Super Button
- **WHEN** the user assigns a verified stored macro to K7 and approves
- **THEN** the K7 key record points at that macro and the change is verified by readback

#### Scenario: Remove an assignment
- **WHEN** the user removes a macro from a key and approves
- **THEN** the key record returns to its default before any macro block is changed

### Requirement: Read macros back
The tools SHALL read stored macros and show their name, trigger, events, delays and repeat settings. They SHALL show a block they cannot decode as raw, preserved data.

#### Scenario: Empty storage
- **WHEN** every block is erased
- **THEN** the tools report that no macros are stored

#### Scenario: Undecodable block
- **WHEN** a block holds data the decoder does not understand
- **THEN** the tools show it as unknown and do not offer to overwrite it without a backup

### Requirement: Restore macro storage
The tools SHALL restore macro blocks from a macro backup file after explicit approval, and verify each block by readback.

#### Scenario: Restore a backup
- **WHEN** the user approves restoring a valid macro backup
- **THEN** each block that differs is rewritten and verified, and unchanged blocks are not written

#### Scenario: Backup of another layout
- **WHEN** the backup refers to an address outside the ten known blocks
- **THEN** the tools refuse the restore

### Requirement: Macro writes respect storage wear limits
The tools SHALL write macro storage only on an explicit user action. They SHALL NOT write it repeatedly, on a timer, or per frame.

#### Scenario: No background writes
- **WHEN** no user has approved a macro change
- **THEN** no macro write command is sent to the keyboard
