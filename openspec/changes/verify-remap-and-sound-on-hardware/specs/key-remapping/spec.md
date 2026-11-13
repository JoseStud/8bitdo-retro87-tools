## Purpose

Lets the user remap one key to another single key on the keyboard, safely, and states when that behaviour counts as hardware-verified.

## ADDED Requirements

### Requirement: Remap a key to another key
The tools SHALL let the user remap one key to another single key. The change SHALL be a preview until the user approves it. On approval the tools SHALL save a backup, write only that key's record, and verify it by readback.

#### Scenario: Preview by default
- **WHEN** the user requests a remap without approving the write
- **THEN** the tools show the record that would change and write nothing

#### Scenario: Approved remap
- **WHEN** the user approves remapping Caps Lock to Esc
- **THEN** only the Caps Lock record changes, the readback matches, and pressing Caps Lock on the keyboard sends Esc

#### Scenario: Return to default
- **WHEN** the user remaps a key to itself and approves
- **THEN** the key's record returns to the default type and the key sends its own code again

#### Scenario: No profile
- **WHEN** the profile is not initialized
- **THEN** the tools refuse the remap and tell the user to create a profile first

#### Scenario: Unknown key name
- **WHEN** the user names a key the tools do not list
- **THEN** the tools refuse before any device access

### Requirement: Remapping is hardware-verified only after the owner's check
The documents SHALL list key remapping as hardware-verified only after the owner has pressed a remapped key on the physical keyboard and seen the expected result, and the result is in the research log.

#### Scenario: Before the check
- **WHEN** no owner check is recorded
- **THEN** the documents describe remapping as decoded and tested, not hardware-verified

#### Scenario: After a passed check
- **WHEN** the research log records a passed check with its date and connection
- **THEN** the documents list remapping as hardware-verified
