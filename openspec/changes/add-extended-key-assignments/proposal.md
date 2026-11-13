## Why

A key can only be remapped to another single key today. The vendor app can also assign mouse actions, media keys and modifier combinations. README.md lists these under "Not yet available", and GUI_IMPLEMENTATION.md has the open milestone "Decode advanced mappings (mouse, media, combinations)".

## What Changes

- Decode the target values for mouse, media and combination assignments first. The record has the record types but not the proven values.
- Add these assignments to the CLI and the Keys page of the desktop app, with preview, backup and readback.
- Show existing extended assignments by name instead of "Preserved assignment".

What the record says today (vendor code only):

- A key record is 12 bytes: key code, 3 padding bytes, uint32 mapping, uint32 mapping type. Type 1 is a keyboard key, type 2 consumer (media), type 3 mouse, type 4 macro. (PROTOCOL.md, Key records)
- `XboxKeyBoardTools.getMode` picks type 3 for target enum 162–171 and type 2 for 172–183 except 179. (research/README.md, Advanced mappings)
- `keycodes.json` lists ten mouse targets by name only (`LEFT_CLICK` … `SCROLL_RIGHT`), with no numeric value. It lists consumer targets with numbers (for example `voiceup` 233, `play` 205). It also lists shifted-symbol targets such as `wave` 13793 (`0x35e1`), which look like a key code and a modifier code in two bytes. (keycodes.json)
- The tools preserve records of type 2 and above and show them as "Preserved assignment". (retro87_model.py, decode)

What is unknown:

- The native mapping value for each mouse target. The record says to "confirm enum constants and the actual native target values" before enabling these.
- Whether the consumer numbers in `keycodes.json` are the values stored in the record.
- What enum 179 is and why it is excluded.
- How a modifier combination is stored: which mapping type, and how the modifiers and the key are packed. The two-byte pattern in `keycodes.json` is a lead, not a decoded format.
- Which combinations the vendor UI allows (how many modifiers, which keys).
- Whether these categories are enabled for this model. Field presence alone does not prove it.
- An unreachable branch (`enum > 183 && enum < 184`) exists in `getMode`. No category may be inferred from it.
- Whether any of this works on the keyboard. Even plain remapping is not yet hardware-verified.

## Capabilities

### New Capabilities
- `extended-key-assignments`: assigning mouse actions, media keys and modifier combinations to keys.

### Modified Capabilities

None.

## Impact

- `keycodes.json`: confirmed target values for the new categories.
- `retro87_core.py`: mapping plans for the new record types.
- `retro87_model.py`: decoding and staging.
- `retro87.py`, `retro87_gui.py`, `qml/Main.qml`: CLI syntax and Keys page controls.
- `test_retro87.py`, `test_model.py`, `test_gui.py`: new tests.
- `PROTOCOL.md`, `README.md`, `GUI_IMPLEMENTATION.md`, `research/README.md`: updated after hardware checks.
- Depends on `verify-remap-and-sound-on-hardware`: plain remapping should be checked on hardware first, because this change uses the same key records.
- Storage: one 12-byte profile write per changed key, on explicit Apply only.
- Non-goals: macros (see `add-hardware-macros`); the Win/Tab/F4 fast-settings switches; firmware updates.
