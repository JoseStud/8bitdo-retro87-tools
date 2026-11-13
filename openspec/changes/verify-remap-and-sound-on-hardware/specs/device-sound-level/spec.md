## Purpose

Lets the user set the keyboard's own sound level, safely, and states when that behaviour counts as hardware-verified.

## ADDED Requirements

### Requirement: Set the device sound level
The tools SHALL let the user set the device sound level to a value from 1 to 5. The change SHALL be staged and written only after the user approves it, with a backup before the write and a readback after it.

#### Scenario: Approved change
- **WHEN** the user stages level 4 and approves
- **THEN** only the sound-level byte changes, the readback matches, and the keyboard's sound follows the new level

#### Scenario: Out-of-range level
- **WHEN** the user requests a level outside 1 to 5
- **THEN** the tools refuse and change nothing

#### Scenario: Stored value outside the range
- **WHEN** the stored byte is not a level from 1 to 5
- **THEN** the tools show the level as unknown and preserve the byte until the user sets a level

### Requirement: Sound level is hardware-verified only after the owner's check
The documents SHALL list the sound level as hardware-verified only after the owner has heard the change on the physical keyboard, and the result is in the research log.

#### Scenario: Before the check
- **WHEN** no owner check is recorded
- **THEN** the documents describe the sound level as decoded and tested, not hardware-verified

#### Scenario: After a passed check
- **WHEN** the research log records a passed check with its date and connection
- **THEN** the documents list the sound level as hardware-verified
