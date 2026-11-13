## 1. Prepare

- [ ] 1.1 Run the unit tests and confirm they pass before touching the keyboard. Verified by the test command in README.md ending with "OK". (README.md, Tests)
- [ ] 1.2 Stop the tray service and OpenRGB server, or avoid changing settings in them during the checks. Verified by `systemctl --user status retro87 retro87-openrgb`. (hardware, owner) (README.md, KDE Plasma integration)
- [ ] 1.3 Save a backup with `retro87.py backup` and note its path. Verified by the file existing and `retro87.py --snapshot <file> status` reading it. (hardware, owner) (README.md, CLI)
- [ ] 1.4 Note the connection in use (dongle or cable), whether the profile is active, and the current sound level from `retro87.py status`. Verified by the notes in research/README.md. (hardware, owner) (PROTOCOL.md, Activation)

## 2. Key remapping

- [ ] 2.1 Run `retro87.py map capslock esc` without `--apply` and confirm the preview shows the record `39 00 00 00 29 00 00 00 01 00 00 00` at `0x334`. Verified by the preview output. (hardware, owner) (PROTOCOL.md, Key records)
- [ ] 2.2 Run it with `--apply`. Press Caps Lock and note what the host receives. Verified by the owner's observation, for example with a key-event viewer. (hardware, owner) (README.md, CLI)
- [ ] 2.3 Press the Profile button to change the active state and press Caps Lock again. Record whether the remap depends on the profile being active. Verified by the recorded observation. (hardware, owner) (PROTOCOL.md, Activation)
- [ ] 2.4 Switch the keyboard off and on with the dongle unplugged at startup, then test Caps Lock again. Record whether the remap persisted. Verified by the recorded observation. (hardware, owner) (research/README.md, Per-key write timing and dongle reads)
- [ ] 2.5 Repeat 2.2 on the other connection (cable or dongle). Verified by the recorded observation. (hardware, owner) (README.md, introduction)
- [ ] 2.6 Run `retro87.py map capslock capslock --apply` and confirm Caps Lock works normally again. Verified by the owner's observation and by the record returning to type 0 in the readback. (hardware, owner) (PROTOCOL.md, Key records)
- [ ] 2.7 Remap one modifier (for example Right Ctrl) to a letter and back. This checks a record in the modifier slots. Verified by the owner's observation. (hardware, owner) (keycodes.json, initial)
- [ ] 2.8 Remap the A Super Button (`ka`) to a letter, test it, and set it back to `none`. Verified by the owner's observation. (hardware, owner) (retro87_core.py, mapping_plan)
- [ ] 2.9 Do one remap through the desktop app: Keys page, Review, Apply. Check the key, then revert it the same way. Verified by the owner's observation and the backup file the app writes. (hardware, owner) (README.md, Desktop app)

## 3. Device sound level

- [ ] 3.1 In the desktop app, stage sound level 5 on the Volume page, Review, and Apply. Note what sound the keyboard makes and how loud it is. Verified by the owner's observation. (hardware, owner) (research/README.md, Volume)
- [ ] 3.2 Apply level 1 and compare. Then step through 2, 3 and 4 if the difference is not clear. Record whether five distinct levels exist. Verified by the recorded observation. (hardware, owner) (PROTOCOL.md, Profile region)
- [ ] 3.3 Repeat one level change with the profile inactive. Record whether it applies. Verified by the recorded observation. (hardware, owner) (PROTOCOL.md, Activation)
- [ ] 3.4 Power-cycle the keyboard and check that the level persisted. Verified by the recorded observation. (hardware, owner) (research/README.md, Per-key write timing and dongle reads)
- [ ] 3.5 Restore the level noted in 1.4 and confirm with `retro87.py status`. Verified by the status output. (hardware, owner) (README.md, CLI)

## 4. Finish

- [ ] 4.1 Compare a fresh snapshot with the backup from 1.3 and confirm the profile is byte-for-byte equal. Verified by the comparison output. (hardware, owner) (README.md, Backups and limits)
- [ ] 4.2 Write the results into research/README.md with date, connection and profile state. Include failures and surprises as observed. Verified by owner review. (research/README.md, introduction)
- [ ] 4.3 For each feature that passed: update the evidence table and the Key records text in PROTOCOL.md, the hardware-verified list and the "Not yet available" paragraph in README.md, and the milestone and Volume row in GUI_IMPLEMENTATION.md. Verified by review against the research log. (PROTOCOL.md, Evidence levels)
- [ ] 4.4 For each check that failed: record the bytes written and the behaviour seen, leave the documents saying "not hardware-verified", and open a follow-up proposal for the fix. Verified by the research log entry and the new proposal. (GUI_IMPLEMENTATION.md, Milestones)
