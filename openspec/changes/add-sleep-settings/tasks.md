## 1. Decode the vendor's sleep controls

- [ ] 1.1 Find the managed UI code that edits `leds_sleep` with `research/inspect_vendor.py managed`. Record the control, its choices and any conversion in research/README.md. Verified by the recorded method names and IL offsets. (research/README.md, LED idle timeout experiment)
- [ ] 1.2 Trace whether any `PID_XBOXJP` path reads or writes `0x26` (sleep time) and `0x27` (LED sleep time). Record the functions and the unit, or record that none exists. Verified by the research log entry. (PROTOCOL.md, Profile region)
- [ ] 1.3 Re-disassemble `writeXboxJPSleep` at `0x1043e890` and confirm it writes four bytes at `0x5cc` with command 1 and nothing else. Verified by the recorded disassembly notes. (research/README.md, LED idle timeout experiment)
- [ ] 1.4 Check whether the sleep control is enabled for this model, by tracing the model conditions. Verified by the research log entry. (GUI_IMPLEMENTATION.md, Reference inventory and evidence boundaries)
- [ ] 1.5 Write the confirmed value list, or "none found", into research/README.md. Stop here if the vendor offers no control and the owner does not want hand-picked values. Verified by owner review. (GUI_IMPLEMENTATION.md, Settings row)

## 2. Hardware observations

- [ ] 2.1 Save a backup with `retro87.py backup` and note its path. Verified by the file existing. (hardware, owner) (README.md, CLI)
- [ ] 2.2 With the current value 65535, leave the keyboard idle for more than 10 minutes and note whether the lights stay on. Verified by the owner's observation, recorded in research/README.md. (hardware, owner) (research/README.md, Follow-up 2026-09-30)
- [ ] 2.3 Write 60, then 300, and time when the lights go off for each. This confirms the unit. Verified by the timings recorded in research/README.md. (hardware, owner) (research/README.md, LED idle timeout experiment)
- [ ] 2.4 Repeat one timing with the profile inactive. Record whether the setting still applies. Verified by the recorded observation. (hardware, owner) (PROTOCOL.md, Activation)
- [ ] 2.5 Only if the owner agrees: write zero once, read it back at once and again after a power cycle, and record both reads. Verified by the recorded values. (hardware, owner) (research/README.md, Follow-up 2026-09-30)
- [ ] 2.6 Restore the owner's preferred value and confirm by `retro87.py status`. Verified by the status output. (hardware, owner) (README.md, CLI)

## 3. Protocol code

- [ ] 3.1 Add a write plan for the LED sleep timeout in `retro87_core.py` that returns one four-byte write at `0x5cc`. Verified by a unit test on the exact bytes. (PROTOCOL.md, Profile region)
- [ ] 3.2 Make the plan refuse values outside the confirmed set and refuse an uninitialized profile. Verified by unit tests for zero, an out-of-set value and an `ff` profile. (research/README.md, LED idle timeout experiment)
- [ ] 3.3 Add the timeout to `show_status`. Verified by a unit test on the status text for a snapshot. (README.md, CLI)

## 4. CLI

- [ ] 4.1 Add a command to `retro87.py` that previews the change and writes only with `--apply`, after a backup. Verified by a unit test that the default never opens the device for writing. (README.md, CLI)
- [ ] 4.2 Skip the write when the value is unchanged. Verified by a unit test with the simulator. (research/storage-wear.md, Conclusion)

## 5. Desktop app

- [ ] 5.1 Add a staged sleep edit to `Draft` in `retro87_model.py`, like `volume`. Verified by a unit test that staging touches no hardware and that Review lists the byte range. (GUI_IMPLEMENTATION.md, Implementation safety invariants)
- [ ] 5.2 Add the control to the desktop app, offering only confirmed values. Verified by a headless GUI test with real clicks: stage, review, discard. (GUI_IMPLEMENTATION.md, Reference inventory, Settings row)
- [ ] 5.3 Test a simulated apply and a simulated partial failure for the new edit. Verified by unit tests with `SimulatedKeyboard`. (GUI_IMPLEMENTATION.md, Implementation safety invariants)

## 6. Hardware check of the finished feature and documents

- [ ] 6.1 Set a timeout through the CLI and through the desktop app, and confirm the lights follow it. Verified by the owner's observation. (hardware, owner) (README.md, Not yet available)
- [ ] 6.2 Update PROTOCOL.md (evidence table, Profile region), README.md ("Not yet available" and the command list) and GUI_IMPLEMENTATION.md with the verified results. Verified by review against the research log. (PROTOCOL.md, Evidence levels)
