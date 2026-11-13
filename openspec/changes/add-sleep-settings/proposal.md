## Why

The keyboard has sleep settings, but the tools only show one of them, read-only. The owner already had to change the LED sleep timeout by hand to stop the lights switching off after a minute (research/README.md, "LED idle timeout experiment"). README.md lists sleep settings under "Not yet available".

## What Changes

- Decode the vendor's sleep controls first. The record does not yet say which values are valid.
- Add a way to read and set the LED sleep timeout from the CLI and the desktop app, with the usual preview, backup and readback.
- Add the keyboard sleep time only if the decoding work shows that this model uses it.
- Record the hardware results and update the evidence tables.

What the record says today:

- `0x5cc`, 4 bytes, uint32 little-endian: LED sleep. The vendor default is 300. The native writer `writeXboxJPSleep` (`0x1043e890`) writes exactly these four bytes with command 1. (PROTOCOL.md, Profile region; research/README.md, LED idle timeout experiment)
- `0x26`, 1 byte: "Sleep time". `0x27`, 1 byte: "LED sleep time". The vendor's new-profile image leaves both at 0. (PROTOCOL.md, Profile region and Creating a profile)
- The desktop app decodes `0x5cc` as `sleepSeconds` and shows it read-only. (GUI_IMPLEMENTATION.md, Reference inventory, Settings row)

What is unknown:

- The unit of `0x5cc`. The owner saw lights go off after about a minute with the value 60, which suggests seconds. This is not proven.
- The valid values. No vendor UI control for sleep has been traced. No "never sleep" value was found in V1.35.
- What zero does. Zero was written on 2026-09-28. Two days later the value read 60. The firmware seems to reject or reset zero. This is inferred, not proven.
- Whether 65535 (written on 2026-09-30) keeps the lights on. The idle observation is still pending.
- The meaning, unit and valid values of `0x26` and `0x27`, whether this model uses them, and which vendor function writes them.
- Whether the settings apply when the profile is inactive.

## Capabilities

### New Capabilities
- `sleep-settings`: reading and changing the keyboard's sleep timeouts.

### Modified Capabilities

None.

## Impact

- `retro87_core.py`: a write plan for the sleep fields.
- `retro87.py`: a new command and a line in `status`.
- `retro87_model.py`, `retro87_gui.py`, `qml/Main.qml`: a staged edit and a control.
- `test_retro87.py`, `test_model.py`, `test_gui.py`: new tests.
- `PROTOCOL.md`, `README.md`, `GUI_IMPLEMENTATION.md`, `research/README.md`: updated after the hardware checks.
- Storage: one small profile write per user change. No repeated writes.
- Non-goals: firmware updates; host-side idle handling; Bluetooth.
