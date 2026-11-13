## 1. Decode by static analysis

- [ ] 1.1 Recover the byte offsets of the 48-byte metadata structure from the native code that reads and writes it (`readXboxJPMacroInfo` `0x1042cfd0`, `writeXboxJPMacro` `0x1043e340`) and from the managed marshalling attributes. Record the layout with offsets in research/README.md. Verified by the offsets summing to 48 and matching both functions. (research/README.md, Macros)
- [ ] 1.2 Trace how the managed code fills the event timer and when it emits key state 3 (interval). Record whether the timer is the delay before or after the event. Verified by the recorded method names and IL offsets. (research/README.md, Macros)
- [ ] 1.3 Trace the repeat count, repeat type values, interval and unify time from `MacroSettingXbox` and `BasicJPAdvanceUIData.setMacro`. Record each field's values and meaning. Verified by the research log entry. (research/README.md, Macros; GUI_IMPLEMENTATION.md, Macros row)
- [ ] 1.4 Trace the value the vendor writes to the metadata flag. Verified by the research log entry. (research/README.md, Macros)
- [ ] 1.5 Trace `BasicJPAdvanceUIData.getMacroAddress`: how a block is chosen for a new macro and what happens when all ten are used. Verified by the research log entry. (research/README.md, Macros)
- [ ] 1.6 Trace what the type-4 key record's mapping field holds for a given block, and the order in which the vendor writes the macro and the key record. Verified by the research log entry. (PROTOCOL.md, Key records)
- [ ] 1.7 Trace how the vendor removes a macro: which commands it sends and what it writes to the key record. Verified by the research log entry. (research/README.md, Macros)
- [ ] 1.8 Disassemble the command-5 call in `writeXboxJPMacro` and record its exact packet (offset, length, header bytes). Note that static analysis cannot show the erase extent. Verified by the recorded packet bytes. (research/README.md, Macros)
- [ ] 1.9 Write the decoded format into PROTOCOL.md as "vendor code only", and list what is still unknown. Verified by owner review. (PROTOCOL.md, Evidence levels)

## 2. Codec, offline only

- [ ] 2.1 Add an encoder from a local macro document to block bytes (metadata and events) in `retro87_macros.py`. Verified by unit tests on exact bytes for a two-key chord. (research/README.md, Macros)
- [ ] 2.2 Add a decoder from block bytes to a macro document. Verified by a round-trip unit test and a test that an all-`ff` block decodes as "empty". (research/README.md, Super Buttons and macro reads)
- [ ] 2.3 Make the encoder refuse more than 1008 events and anything the stored format cannot express. Verified by unit tests. (README.md, Desktop app, Macros)
- [ ] 2.4 Add macro storage to `SimulatedKeyboard`, with commands 5, 6 and 7 and a configurable erase extent. Verified by unit tests of the simulator itself. (GUI_IMPLEMENTATION.md, Implementation safety invariants)
- [ ] 2.5 Confirm that the product `Keyboard` class still rejects commands 5 and 6. Verified by the existing boundary test in `test_macro_backup.py`. (PROTOCOL.md, Super Button identification and macro backups)

## 3. Erase-extent experiment

- [ ] 3.1 Write the experiment plan in research/README.md: the two blocks used, the exact packets, the number of writes, the stop conditions and the recovery steps. Verified by owner approval of the plan. (research/README.md, Macros, "Before hardware writing")
- [ ] 3.2 Add an experiment script that can write only the two planned blocks, previews by default, and refuses any other address. Verified by unit tests against the simulator. (PROTOCOL.md, Super Button identification and macro backups)
- [ ] 3.3 Take a full macro backup with `retro87_macro_backup.py` over the USB cable. Verified by the file and its block hashes. (hardware, owner) (README.md, Desktop app)
- [ ] 3.4 Write the short test macro to the first planned block, then read all ten blocks, the profile and the LED region. Record which bytes changed. Verified by the recorded diff. (hardware, owner) (research/README.md, Macros)
- [ ] 3.5 Write the test macro to the second planned block and take a new full backup. Verified by the backup file. (hardware, owner) (research/README.md, Macros)
- [ ] 3.6 Send the write sequence again to the first block only. Compare all ten blocks, the profile and the LED region with the backup. Record the erase extent. Verified by the recorded diff. (hardware, owner) (research/README.md, Macros)
- [ ] 3.7 Send command 5 alone to the first block and read all blocks. Record whether command 5 by itself erases, and how much. Verified by the recorded diff. (hardware, owner) (research/storage-wear.md, Prepare-only erase test)
- [ ] 3.8 Power-cycle the keyboard with cable and dongle unplugged, then read the blocks again. Record whether the data persisted. Verified by the recorded read. (hardware, owner) (research/storage-wear.md, Evidence and limits)
- [ ] 3.9 Record the results in research/README.md and PROTOCOL.md. State the measured erase extent or that it is still unknown. Verified by owner review. (PROTOCOL.md, Evidence levels)

## 4. Playback and timing checks

- [ ] 4.1 Assign the test macro to one Super Button by a hand-approved key-record write, press the button, and note what is typed. Verified by the owner's observation. (hardware, owner) (PROTOCOL.md, Key records)
- [ ] 4.2 Write a test macro with a long, visible delay and note where the delay falls. This confirms the timer placement. Verified by the recorded observation. (hardware, owner) (research/README.md, Macros)
- [ ] 4.3 Write test macros for each repeat setting decoded in 1.3 and note the behaviour. Verified by the recorded observations. (hardware, owner) (research/README.md, Macros)
- [ ] 4.4 Check whether the macro plays while the profile is inactive. Verified by the recorded observation. (hardware, owner) (PROTOCOL.md, Activation)
- [ ] 4.5 Remove the test macros and the test assignment, and confirm the blocks and the profile match the backup from 3.3. Verified by a byte comparison. (hardware, owner) (research/README.md, Macros)

## 5. Write path in the tools

- [ ] 5.1 Enable commands 5 and 6 in `retro87_core.py` only for aligned addresses in the ten blocks, behind the writable guard. Verified by unit tests for refused addresses. (PROTOCOL.md, Super Button identification and macro backups)
- [ ] 5.2 Implement the macro block write with the vendor sequence and readback. Verified by a unit test of the packet sequence against the simulator. (research/README.md, Macros)
- [ ] 5.3 Back up every block inside the measured erase extent before a write, and rewrite or refuse as the design says. Verified by a unit test with a simulator erase extent larger than one block. (research/README.md, Macros)
- [ ] 5.4 Skip the write when the compiled block equals the stored block. Verified by a unit test that no write command is sent. (research/storage-wear.md, Conclusion)
- [ ] 5.5 Stop without retry on a failed write or readback, and report the backup path. Verified by a simulated partial-failure test. (GUI_IMPLEMENTATION.md, Implementation safety invariants)
- [ ] 5.6 Add restore from a `retro87-macro-backup` file, writing only blocks that differ. Verified by unit tests, including a refused out-of-range address. (README.md, Desktop app)

## 6. Assignment and user interface

- [ ] 6.1 Add a type-4 key-record plan to `retro87_core.py`. Verified by a unit test on the exact record bytes. (PROTOCOL.md, Key records)
- [ ] 6.2 Stage macro store and assignment in `Draft`, with the macro block written and verified before the key record. Verified by a unit test of the write order. (GUI_IMPLEMENTATION.md, Implementation safety invariants)
- [ ] 6.3 Show stored macros and assignments when the keyboard is read. Verified by a unit test with a simulator that holds one macro. (GUI_IMPLEMENTATION.md, Macros row)
- [ ] 6.4 Add "store on keyboard" and "remove from keyboard" to the Macros page, through Review and Apply. Verified by headless GUI tests with real clicks. (README.md, Desktop app, Macros)
- [ ] 6.5 Add CLI commands for store, assign, remove, list and restore, each previewing by default. Verified by unit tests that the default path never writes. (README.md, CLI)

## 7. Final hardware check and documents

- [ ] 7.1 Store a macro from the desktop app, assign it to a Super Button, press it, and check the output. Verified by the owner's observation. (hardware, owner) (README.md, Not yet available)
- [ ] 7.2 Remove it and restore the earlier macro backup; confirm by a byte comparison. Verified by the comparison output. (hardware, owner) (README.md, Desktop app)
- [ ] 7.3 Update README.md, PROTOCOL.md, GUI_IMPLEMENTATION.md and research/README.md with the verified results. Verified by review against the research log. (PROTOCOL.md, Evidence levels)
