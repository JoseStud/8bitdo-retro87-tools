## Purpose

Lets the user read and change the keyboard's sleep timeouts, such as how long the key lights stay on while idle, with the same safety steps as every other write.

## ADDED Requirements

### Requirement: Show the LED sleep timeout
The tools SHALL show the stored LED sleep timeout when they show the keyboard status. They SHALL show the raw stored value when its meaning is not confirmed.

#### Scenario: Status with an initialized profile
- **WHEN** the user asks for the status of a keyboard with an initialized profile
- **THEN** the output includes the LED sleep timeout read from the keyboard

#### Scenario: Status without a profile
- **WHEN** the profile is not initialized
- **THEN** the tools show the timeout as unknown and do not present the erased value as a setting

### Requirement: Change the LED sleep timeout safely
The tools SHALL let the user set the LED sleep timeout to a confirmed value. The change SHALL be a preview until the user approves it. On approval the tools SHALL save a backup, write only the timeout field, and verify it by readback.

#### Scenario: Preview by default
- **WHEN** the user requests a new timeout without approving the write
- **THEN** the tools show the old and new value and write nothing

#### Scenario: Approved change
- **WHEN** the user approves a change to a confirmed value
- **THEN** the tools save a backup, write the timeout field, read it back, and report success only if the readback matches

#### Scenario: Unchanged value
- **WHEN** the requested value equals the stored value
- **THEN** the tools write nothing

#### Scenario: No profile
- **WHEN** the profile is not initialized
- **THEN** the tools refuse the change and tell the user to create a profile first

### Requirement: Refuse unconfirmed values
The tools SHALL refuse any timeout value that is neither a vendor choice recorded in the research log nor a value the owner has checked on hardware. They SHALL NOT describe any value as "always on" unless that behaviour is hardware-verified.

#### Scenario: Zero before it is understood
- **WHEN** the user requests zero and zero is not a confirmed value
- **THEN** the tools refuse and explain that the effect of zero is not known

#### Scenario: Out-of-range value
- **WHEN** the user requests a value outside the confirmed set
- **THEN** the tools refuse before any device access

### Requirement: Preserve undecoded sleep bytes
The tools SHALL NOT change sleep-related bytes whose meaning is not decoded. They SHALL preserve them in every write and restore.

#### Scenario: Other edits leave them alone
- **WHEN** the user applies any other change
- **THEN** the undecoded sleep bytes are identical before and after
