## 1. Decode by static analysis

- [ ] 1.1 Extract the vendor enum constants for targets 162–183 and name each one. Record the table in research/README.md. Verified by the recorded constant table and its source type. (research/README.md, Advanced mappings)
- [ ] 1.2 Trace `BasicJPAdvanceUIData.setMapping` for a mouse target and record the value it stores in the mapping field for each of the ten mouse actions. Verified by the recorded method names, IL offsets and values. (PROTOCOL.md, Key records; keycodes.json, targets)
- [ ] 1.3 Trace the same for consumer targets and confirm or correct the numbers in `keycodes.json`. Record what enum 179 is. Verified by the research log entry. (research/README.md, Advanced mappings)
- [ ] 1.4 Trace how the vendor UI builds a modifier combination and how it is stored: the mapping type and the packing of modifiers and key. Check the two-byte pattern seen in `keycodes.json` (for example `wave` = `0x35e1`) against the code. Verified by the research log entry with two worked examples. (keycodes.json, targets; GUI_IMPLEMENTATION.md, Keys row)
- [ ] 1.5 Record the limits of combinations: how many modifiers, which keys, and any excluded pairs. Verified by the research log entry. (GUI_IMPLEMENTATION.md, Keys row)
- [ ] 1.6 Trace the model conditions that enable each category for `PID_XBOXJP`. Record which categories this model offers. Verified by the research log entry. (GUI_IMPLEMENTATION.md, Reference inventory and evidence boundaries)
- [ ] 1.7 Confirm that `writeXboxJPKey` (`0x1043df10`) is the writer for all these record types. Verified by the recorded call sites. (PROTOCOL.md, Useful native functions)
- [ ] 1.8 Write the decoded encodings into PROTOCOL.md as "vendor code only" and list what remains unknown. Verified by owner review. (PROTOCOL.md, Evidence levels)

## 2. Tables and codec

- [ ] 2.1 Add the confirmed mouse and consumer values to `keycodes.json`. Verified by a unit test that every listed target has a numeric value and a type. (keycodes.json, targets)
- [ ] 2.2 Extend the mapping plan in `retro87_core.py` to build type 2 and type 3 records. Verified by unit tests on the exact 12 bytes, one per category. (PROTOCOL.md, Key records)
- [ ] 2.3 Add the combination record to the mapping plan, as decoded in 1.4. Verified by unit tests on the two worked examples. (PROTOCOL.md, Key records)
- [ ] 2.4 Refuse targets without a recorded value and combinations outside the decoded limits. Verified by unit tests. (research/README.md, Advanced mappings)
- [ ] 2.5 Keep the plan changing exactly one record. Verified by extending the existing "mapping changes only one record" test. (PROTOCOL.md, Key records)
- [ ] 2.6 Decode type 2, type 3 and combination records to names in `retro87_model.py`; keep unknown records as "Preserved assignment". Verified by unit tests, including an unknown type. (GUI_IMPLEMENTATION.md, Implementation safety invariants)

## 3. CLI and desktop app

- [ ] 3.1 Extend `retro87.py map` to accept the new targets and add them to `list-keys`. Verified by unit tests that the default is a preview. (README.md, CLI)
- [ ] 3.2 Stage the new assignments in `Draft`. Verified by a unit test that staging touches no hardware and Review lists the record. (GUI_IMPLEMENTATION.md, Implementation safety invariants)
- [ ] 3.3 Add category controls to the Keys page for mouse, media and combinations. Verified by headless GUI tests with real clicks: stage, review, discard. (GUI_IMPLEMENTATION.md, Keys row)
- [ ] 3.4 Test a simulated apply and a simulated partial failure for one extended assignment. Verified by unit tests with `SimulatedKeyboard`. (GUI_IMPLEMENTATION.md, Implementation safety invariants)

## 4. Hardware checks

- [ ] 4.1 Save a backup with `retro87.py backup`. Verified by the file existing. (hardware, owner) (README.md, CLI)
- [ ] 4.2 Assign left click to a spare key, apply, and check that pressing it clicks. Then check one scroll action. Verified by the owner's observation, recorded in research/README.md. (hardware, owner) (README.md, Not yet available)
- [ ] 4.3 Assign volume up and play/pause to spare keys, apply, and check the host reacts. Verified by the owner's observation. (hardware, owner) (README.md, Not yet available)
- [ ] 4.4 Assign one two-key combination (for example Ctrl+C) and one with two modifiers, apply, and check the host receives them. Verified by the owner's observation, for example with a key-event viewer. (hardware, owner) (README.md, Not yet available)
- [ ] 4.5 Check one assignment with the profile inactive and after a power cycle. Record both results. Verified by the recorded observations. (hardware, owner) (PROTOCOL.md, Activation)
- [ ] 4.6 Reset the test keys to default and confirm the profile equals the backup. Verified by a byte comparison. (hardware, owner) (README.md, Backups and limits)

## 5. Documents

- [ ] 5.1 Update README.md, PROTOCOL.md, GUI_IMPLEMENTATION.md and research/README.md with the verified categories. Leave any unchecked category marked as not hardware-verified. Verified by review against the research log. (PROTOCOL.md, Evidence levels)
