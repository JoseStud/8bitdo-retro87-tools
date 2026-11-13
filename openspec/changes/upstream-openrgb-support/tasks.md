## 1. Decide

- [ ] 1.1 Read upstream OpenRGB's current CONTRIBUTING.md and note its rules on AI-assisted code, commit style and new-device requirements in research/openrgb-merge-request.md. Verified by the dated note. (owner) (OPENRGB.md, Upstream status)
- [ ] 1.2 Decide whether to submit, and name the human submitter. Record the decision in OPENRGB.md. Stop this change after section 2 if the answer is no. Verified by the recorded decision. (owner) (research/openrgb-merge-request.md, introduction)
- [ ] 1.3 If the policy is unclear for a human-reworked patch, ask the upstream maintainers before reworking, and record their answer. Also ask whether they prefer one merge request or two. Verified by the recorded answer or link. (owner) (OPENRGB.md, Upstream status)

## 2. Keep the local patch current

- [ ] 2.1 Run `./update-openrgb.sh --force` and confirm the patch applies to today's upstream `master` and builds. Verified by the log line naming the upstream commit and a successful start check. (OPENRGB.md, Option 1)
- [ ] 2.2 If it does not apply, repair the patch in a development checkout and export it as OPENRGB.md describes. Verified by 2.1 passing afterwards. (OPENRGB.md, Maintaining the fork)
- [ ] 2.3 Record the upstream commit the patch was last checked against in OPENRGB.md. Verified by review. (OPENRGB.md, Option 3)
- [ ] 2.4 Compare `sha256sum openrgb/retro87-openrgb.patch` with the fork's `patches/0001-8bitdo-retro87.patch` and the latest release tag. Sync the fork if they differ. Verified by equal hashes. (owner) (OPENRGB.md, Maintaining the fork)
- [ ] 2.5 Confirm the daily timer `retro87-openrgb-update` is enabled and its last run succeeded. Verified by `journalctl --user -u retro87-openrgb-update`. (hardware, owner) (OPENRGB.md, Option 1)

## 3. Close the testing gaps

- [ ] 3.1 With the patched build over the USB cable, select each effect mode in OpenRGB (Static, Breathing, Spectrum Cycle, Rainbow Wave, Ripple, Resonance, Starlight, Off) and note what the keyboard shows. Verified by the owner's observations in research/README.md. (hardware, owner) (research/openrgb-merge-request.md, Testing so far)
- [ ] 3.2 Repeat detection and two effect modes over the 2.4 GHz dongle with the patched build, and confirm there is no Direct mode. Verified by the owner's observations. (hardware, owner) (research/openrgb-merge-request.md, Testing so far)
- [ ] 3.3 Save one Custom picture and change its brightness once. Keep to a handful of Custom saves in total. Verified by the owner's observation and the debug log lines `Writing per-key block`. (hardware, owner) (OPENRGB.md, Flash-wear protection)
- [ ] 3.4 Check that leaving Direct for the unchanged previous mode writes nothing: enter Direct, leave it, power-cycle with the cable and dongle unplugged, and compare the stored lighting with before. Also check the debug log shows no save. Verified by the recorded observation. (hardware, owner) (OPENRGB.md, Tests)
- [ ] 3.5 Check that a dongle whose keyboard is off is not added as a device. Verified by the log line `Keyboard not reachable through the dongle ... not added`. (hardware, owner) (OPENRGB.md, The keyboard in OpenRGB)
- [ ] 3.6 Build the patched OpenRGB for Windows and macOS, or record that this could not be done. No hardware test is expected. Verified by build logs or the recorded gap. (owner) (OPENRGB.md, Limitations)
- [ ] 3.7 Update the "Testing so far" list in research/openrgb-merge-request.md with dates and results. Verified by review against research/README.md. (research/openrgb-merge-request.md, Testing so far)

## 4. Human rework

- [ ] 4.1 Read the whole patch and list every part the submitter cannot yet explain. Verified by the list being empty at the end of this section. (owner) (OPENRGB.md, Upstream status)
- [ ] 4.2 Rework the HID LampArray changes (libusb transport, detector for interfaces without an IN endpoint, report-ID table fix) to upstream's code style. Verified by a clean build and the keyboard still appearing with Direct. (owner) (OPENRGB.md, Changes in the OpenRGB patch)
- [ ] 4.3 Rework the 8BitDo Retro 87 controller, including the coalesced writer and the identical-write skip. Verified by a clean build and by repeating tasks 3.1 and 3.3 on the reworked code. (hardware, owner) (OPENRGB.md, Changes in the OpenRGB patch)
- [ ] 4.4 Decide how to handle the known limits in the submission: Linux-only Direct, and two wired keyboards taking the first LampArray. Fix them or state them. Verified by the merge request text. (owner) (OPENRGB.md, Limitations)
- [ ] 4.5 Write commits without AI authorship credits, in upstream's commit style. Verified by `git log` on the submission branch. (owner) (OPENRGB.md, Upstream status)
- [ ] 4.6 Export the reworked code back to `openrgb/retro87-openrgb.patch`, commit it here, and sync the fork copy. Verified by task 2.1 passing and equal hashes. (owner) (OPENRGB.md, Maintaining the fork)

## 5. Submit and follow up

- [ ] 5.1 Write the merge request description from research/openrgb-merge-request.md in the submitter's own words: summary, modes, protocol, notes for users, tested and untested claims. Verified by owner review. (owner) (research/openrgb-merge-request.md, Summary)
- [ ] 5.2 Open the merge request (or the first of two) on GitLab. Record its link and date in OPENRGB.md. Verified by the link. (owner) (research/openrgb-merge-request.md, introduction)
- [ ] 5.3 Answer review comments. Bring every accepted change back into the local patch and the fork copy. Verified by equal hashes and task 2.1 passing after each update. (owner) (OPENRGB.md, Maintaining the fork)
- [ ] 5.4 If the first merge request is merged, drop its hunks from the local patch and confirm the remaining patch applies and builds. Verified by task 2.1. (OPENRGB.md, Maintaining the fork)
- [ ] 5.5 If upstream declines, record the reason in OPENRGB.md and keep the patch queue as the supported path. Verified by review. (owner) (OPENRGB.md, Upstream status)

## 6. After a full merge

- [ ] 6.1 Update the "Upstream status" and setup sections of OPENRGB.md and the README.md paragraph on OpenRGB to name the upstream version that has the support. Verified by review. (OPENRGB.md, Upstream status)
- [ ] 6.2 Write a follow-up proposal to retire `update-openrgb.sh`, the update timer, the local patch and the fork's release workflow, and to make `install-kde.sh` use upstream OpenRGB. Verified by the new proposal passing `openspec validate`. (OPENRGB.md, Option 1 and Option 2)
