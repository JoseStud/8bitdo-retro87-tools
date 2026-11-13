# Handoff: OpenSpec bootstrap

Branch `openspec-bootstrap`. Proposals only. No feature was implemented. No existing code, test or document was changed.

## What was done

- Installed `@fission-ai/openspec@1.13.0` and ran `openspec init --tools claude,codex --no-animation`. This added `openspec/`, `.claude/` (skills and commands) and `.agents/` (skills for Codex).
- Filled `openspec/config.yaml` with a `context` block and per-artifact `rules`. The rules include: "hardware-verified" needs the owner's check on the physical keyboard; keyboard tasks are marked "(hardware, owner)"; storage writes respect `research/storage-wear.md`; firmware updates are a non-goal.
- Wrote five changes under `openspec/changes/`:

| Change | Artifacts | Tasks | New capability |
| --- | --- | --- | --- |
| `add-sleep-settings` | proposal, design, spec, tasks | 21 | `sleep-settings` |
| `add-hardware-macros` | proposal, design, spec, tasks | 42 | `hardware-macros` |
| `add-extended-key-assignments` | proposal, spec, tasks | 25 | `extended-key-assignments` |
| `upstream-openrgb-support` | proposal, design, spec, tasks | 28 | `openrgb-support` |
| `verify-remap-and-sound-on-hardware` | proposal, spec, tasks | 22 | `key-remapping`, `device-sound-level` |

Every task ends with its source in the repository record.

## Validation

`openspec validate --all --strict --no-interactive`: 5 passed, 0 failed.

The hardware-free unit tests still pass (`test_retro87 test_model test_service test_macro_backup test_buttons test_chord`: 66 tests, OK). The GUI tests were not run here; PySide6 is not installed in this container. Nothing they cover was changed.

## Decisions I made without asking

- **Suggested order:** `verify-remap-and-sound-on-hardware` first (no code, unblocks the key-record work), then `add-sleep-settings`, `add-extended-key-assignments`, `add-hardware-macros`. `upstream-openrgb-support` is independent.
- **Sleep settings:** the tools accept only values that are vendor UI choices or owner-checked. Zero is refused until its effect is known. `0x26`/`0x27` get a setter only if decoding shows this model uses them.
- **Macros:** three gates in order: static decoding, an owner-run erase-extent experiment with a script limited to two blocks, then the feature. Product code keeps rejecting commands 5 and 6 until then.
- **Extended assignments:** the Win/Tab/F4 fast-settings switches are left out (see "Not covered").
- **Hardware verification change:** it also writes the existing remap and sound-level behaviour as specs, so there is a baseline. A failed check leads to a separate fix proposal.
- **OpenRGB upstreaming:** the rework and submission are human work. Agents do not author or push upstream commits. I propose two merge requests (generic LampArray transport first, then the 8BitDo controller). The spec capability describes delivery rules, not new lighting behaviour.
- **Test command in the config:** it lists all twelve test modules. The README command lists only eight (see below).

## Unknown, or needs the owner

Decisions:

- Approve, change or reject each of the five proposals.
- OpenRGB: whether to submit upstream at all given its AI-contribution policy, who the human submitter is, and one merge request or two. Upstream's current CONTRIBUTING.md was not re-read; the record is from 2026-09-28.
- Sleep: whether to allow hand-picked timeout values if the vendor UI offers none for this model, and whether to test zero again.
- Macros: approve the erase-extent experiment plan before any macro write.

Protocol facts the record does not have (the first tasks of each change are this decoding work):

- Sleep: the unit and valid values of `0x5cc`; what zero does; the meaning of `0x26` and `0x27`; any "never sleep" value.
- Macros: what command 5 erases; metadata byte offsets; timer placement; repeat fields; the metadata flag; block allocation; the type-4 mapping value; how a macro is removed; playback behaviour.
- Extended assignments: native values for the ten mouse targets; whether the consumer numbers in `keycodes.json` are the stored values; what enum 179 is; how a modifier combination is stored; which categories this model enables.
- Remap and sound: whether they need an active profile; persistence; what the "device sound" is on this model.

Hardware checks waiting for the owner (all marked "(hardware, owner)" in the tasks):

- Remap and sound level on the keyboard, on both connections.
- The idle observation with LED sleep 65535, pending since 2026-09-30.
- Macro erase-extent experiment and playback checks.
- Each OpenRGB effect mode on hardware, the dongle path with the patched build, and that leaving Direct saves nothing.
- Mouse, media and combination assignments once decoded.

## Remaining work found that is not covered by the five changes

- **Fast settings (Win/Tab/F4 at `0x5c8`) and Fn lock (`0x25`).** Semantics and model availability are not traced. PROTOCOL.md says bits 0/1/2; research/README.md says "bits 1/2/4". This should be reconciled. (research/README.md, Advanced mappings; GUI_IMPLEMENTATION.md, Keys row)
- **Per-preset hardware checks beyond breathing.** Other presets' parameters share the encoding but were not individually tested. (PROTOCOL.md, Evidence levels; GUI_IMPLEMENTATION.md, Lighting row)
- **Full-display mirror is a draft.** Native monitor capture and sustained hardware output still need an interactive validation run. (README.md, Full-display mirror)
- **Stale milestone.** GUI_IMPLEMENTATION.md still lists "Live wallpaper mirroring: blocked on the storage-persistence test (issue #1)". Live animation now exists over USB LampArray. The owner should close or reword the milestone and the issue.
- **LampArray power-cycle check.** research/storage-wear.md refers to a "power-cycle check below" for LampArray updates, but no result is recorded.
- **Manual keyboard and accessibility review of the desktop app.** Open milestone. (GUI_IMPLEMENTATION.md, Milestones)
- **Macro recording and local playback in the editor.** Listed as unavailable; `add-hardware-macros` does not include them. (README.md, Desktop app)
- **Snapshots and restore gaps.** `restore-profile` writes only the profile region; per-key colours are restored by hand. The OpenRGB path makes no backups. (README.md, Backups and limits; OPENRGB.md, Limitations)
- **AUR packaging.** Planned, not published; needs an AUR account and an explicit decision to publish. (OPENRGB.md, AUR packaging)
- **OpenRGB limits.** No Direct mode on Windows or macOS; with two wired keyboards the first LampArray is used. The upstream change states these but does not fix them. (OPENRGB.md, Limitations)
- **README test command is incomplete.** It omits `test_macros`, `test_macro_backup`, `test_buttons` and `test_chord`. The "68 automated tests" figure in GUI_IMPLEMENTATION.md is also old.
- **Bluetooth and other models** are unsupported. The config treats them as out of scope; say so if that should change.

No pull request was opened.
