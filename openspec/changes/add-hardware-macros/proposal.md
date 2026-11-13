## Why

The desktop app can edit macros and save them to files, and it can save a Super Button target (K1–K8). It cannot put a macro on the keyboard. README.md lists hardware macros under "Not yet available". The write commands are disabled on purpose, because the record does not yet prove what they erase.

## What Changes

- Finish the decoding work first. Hardware macro writes stay disabled until it is done.
- Then add: compile a local macro to the keyboard's format, write it to a macro block, assign it to a key or Super Button, read macros back, remove them, and restore macro storage from a backup.
- Keep every step behind preview, backup, explicit approval and readback.

What the record says today (vendor code only, unless noted):

- Macro storage is ten 4096-byte blocks, addresses `0x0000`–`0x9fff`. Command 7 reads them. All ten were read twice over USB and every byte was `ff` (hardware). (research/README.md, Super Buttons and macro reads)
- `writeXboxJPMacro` (`0x1043e340`): command 5 at the macro address with no payload, an acknowledgment and a 100 ms delay; command 6 writes 48 bytes of metadata at the address; command 6 writes four-byte event records at address + `0x40` in chunks of at most 53 bytes. At most 1008 events. (research/README.md, Macros)
- Metadata fields in declaration order: uint32 flag; byte source key; 32-byte UTF-16BE name; uint16 step count; uint16 interval; byte repeat; byte repeat type; uint16 unify time; uint16 reserved. (research/README.md, Macros)
- Event fields: byte key state, byte key code, uint16 timer. Key state: press = 1, release = 2, interval = 3. (research/README.md, Macros)
- A key record with mapping type 4 holds a macro address. Super Buttons K1–K8 use profile slots 108–115, and their metadata source-key values are 108–115. (PROTOCOL.md, Key records; research/README.md, Super Buttons and macro reads)

What is unknown:

- What command 5 erases. It is "likely erase/preparation". Its extent is not established: one block, more, or something else.
- The padding and alignment of the metadata structure. The field order is known; the byte offsets are not proven.
- Where the timer applies (before or after the event) and how the "interval" key state is used.
- The full repeat behaviour: the repeat count, the repeat type values, the interval and the unify time.
- The value of the metadata flag.
- How the vendor picks a block for a new macro, and the allocation limits.
- Exactly what the mapping field of a type-4 record holds for each block.
- Whether a write can restore the unused bytes of a block to their earlier state.
- How playback behaves on the keyboard. No macro has ever been written to this keyboard.
- Whether macros work while the profile is inactive.

## Capabilities

### New Capabilities
- `hardware-macros`: storing macros on the keyboard, assigning them to keys, and backing up and restoring macro storage.

### Modified Capabilities

None.

## Impact

- `retro87_core.py`: commands 5 and 6, now rejected, become available behind a guard.
- `retro87_macros.py`: a compiler from local macro documents to the stored format, and a decoder.
- `retro87_macro_backup.py`: a restore path next to the read-only backup.
- `retro87_model.py`, `retro87_gui.py`, `qml/Main.qml`: staged macro assignment in Review and Apply.
- `retro87.py`: CLI commands for the same operations.
- `test_macros.py`, `test_macro_backup.py`, `test_model.py`, `test_gui.py`: new tests; the simulator gains macro storage.
- `PROTOCOL.md`, `README.md`, `GUI_IMPLEMENTATION.md`, `research/README.md`: updated after hardware checks.
- Storage: each macro write probably erases flash. Writes happen only on explicit Apply.
- Non-goals: macro recording from live typing; host-side playback; firmware updates; a global key logger.
