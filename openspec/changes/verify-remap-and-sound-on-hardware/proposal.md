## Why

Key remapping and the device sound level are decoded from the vendor app and covered by unit tests, but nobody has checked them on the keyboard. README.md and PROTOCOL.md say so, and GUI_IMPLEMENTATION.md has the open milestone "Validate key remapping and sound level on hardware". Lighting taught us that a correct readback does not prove a visible effect.

## What Changes

- The owner checks single-key remapping on the physical keyboard, through the CLI and the desktop app.
- The owner checks the device sound level (1–5) on the physical keyboard.
- The results go into the research log. The documents are updated to "hardware-verified" only for what passed.
- No new feature. If a check fails, the finding is recorded and a fix is proposed separately.
- This change also writes down the existing behaviour as specs, so later changes have a baseline.

What the record says today (vendor code and tests only):

- Remapping writes one 12-byte key record at `0x28 + slot*12` with mapping type 1. Example: Caps Lock → Esc is `39 00 00 00 29 00 00 00 01 00 00 00` at `0x334`. (PROTOCOL.md, Key records)
- The sound level is one byte at `0x5c9`, values 1–5, written with command 1 by `writeXboxJPVolume` (`0x1043ea60`). It is device sound, not host volume. The vendor default is 2. (PROTOCOL.md, Profile region; research/README.md, Volume)

What is unknown:

- Whether a remap takes effect at once, and whether it needs the profile to be active.
- Whether a remap survives a power cycle.
- Whether the Super Buttons A and B can be remapped as the code assumes.
- What the device sound is on this model, whether the five levels are audibly different, and whether the level applies while the profile is inactive.
- Whether both connections (dongle and cable) behave the same.

## Capabilities

### New Capabilities
- `key-remapping`: remapping one key to another single key.
- `device-sound-level`: setting the keyboard's own sound level.

### Modified Capabilities

None.

## Impact

- No code changes are planned. Tests change only if a check finds a defect, and that fix is a separate proposal.
- `README.md` (hardware-verified list and the "Not yet available" paragraph), `PROTOCOL.md` (evidence table, Key records), `GUI_IMPLEMENTATION.md` (milestone and Volume row), `research/README.md` (test log).
- Storage: about ten small profile writes in total, each approved by the owner.
- Should be done before `add-extended-key-assignments`, which builds on the same key records.
