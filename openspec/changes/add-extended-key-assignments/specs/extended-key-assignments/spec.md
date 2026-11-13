## Purpose

Lets the user assign mouse actions, media keys and modifier combinations to keys, in addition to single-key remapping, with the same safety steps as every other write.

## ADDED Requirements

### Requirement: Assign a mouse action to a key
The tools SHALL let the user assign a decoded mouse action (a click or a scroll step) to a key. They SHALL offer only actions whose stored value is recorded in the protocol document.

#### Scenario: Preview by default
- **WHEN** the user assigns a mouse action without approving the write
- **THEN** the tools show the key record that would change and write nothing

#### Scenario: Approved assignment
- **WHEN** the user approves the assignment
- **THEN** the tools save a backup, write only that key's record, and verify it by readback

#### Scenario: Undecoded action
- **WHEN** the user asks for a mouse action whose stored value is not recorded
- **THEN** the tools refuse before any device access

### Requirement: Assign a media key to a key
The tools SHALL let the user assign a decoded media (consumer) function to a key, with preview, backup and readback.

#### Scenario: Approved assignment
- **WHEN** the user approves assigning a media function to a key
- **THEN** only that key's record changes and the readback matches

#### Scenario: Unknown media name
- **WHEN** the user names a media function the tools do not list
- **THEN** the tools refuse and point to the list of supported names

### Requirement: Assign a modifier combination to a key
The tools SHALL let the user assign a combination of modifiers and one key to a key, limited to the combinations the decoded format can store.

#### Scenario: Approved combination
- **WHEN** the user approves assigning a supported combination
- **THEN** only that key's record changes and the readback matches

#### Scenario: Unsupported combination
- **WHEN** the combination cannot be stored in the decoded format
- **THEN** the tools refuse and say why

### Requirement: Show existing extended assignments
The tools SHALL show a stored mouse, media or combination assignment by its name. They SHALL show a record they cannot decode as a preserved assignment with its raw type and value.

#### Scenario: Decoded record
- **WHEN** the keyboard holds a decoded media assignment
- **THEN** the key shows the media function's name

#### Scenario: Unknown record
- **WHEN** the keyboard holds a record with an unknown type or value
- **THEN** the key shows it as preserved, with its raw type and value, and other edits leave it unchanged

### Requirement: Return a key to its default
The tools SHALL let the user return a key with an extended assignment to its default record.

#### Scenario: Reset a key
- **WHEN** the user resets a key that has a mouse assignment and approves
- **THEN** the key's record returns to the default type and the readback matches

### Requirement: Hardware status is stated honestly
The documents SHALL describe each category as hardware-verified only after the owner has checked it on the physical keyboard.

#### Scenario: Category not yet checked
- **WHEN** a category has unit tests but no owner check
- **THEN** the documents list it as decoded and tested, not hardware-verified
