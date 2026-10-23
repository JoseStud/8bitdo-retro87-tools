# Native GUI implementation tracker

## Accepted decisions
- Native Linux desktop: Python/PySide6 with Qt Quick/QML; preserve CLI use.
- Reproduce Ultimate Software V2 keyboard workflow; full Panther configuration
  parity is the target. Firmware flashing and Windows integrations excluded.
- Wireless dongle only initially. Stage changes, explicit Apply, backup/readback.
- No settings changes during development. Separate approval for hardware writes.
- Official downloaded binary/public references; no user screenshots required.

## Milestones
- [x] Inspect official public keyboard screen and relevant V1.35 WPF controls.
- [x] Create reference-based visual brief and provisional capability inventory.
- [x] Generate and approve the initial Keys screen design.
- [x] Extract shared backend and preserve CLI/snapshot compatibility.
- [x] Add structured state, staged changes, simulator and serialized worker.
- [x] Implement desktop shell, Keys, preset Lighting, Volume, Profiles and backups.
- [x] Per-key lighting editor (Lighting page) with staged apply, backup and readback.
- [x] Test offline behavior, two window sizes, 2× scaling and simulated failure recovery.
- [x] Package local launcher template and document device-access setup.
- [x] Verify live reads and the GUI connection in the user's desktop session.
- [x] Validate lighting writes and restoration on hardware (2026-09-27; see
      [research/README.md](research/README.md)). Writes are enabled by default;
      `--read-only` disables them.
- [x] KDE Plasma integration: session service, tray widget, keyboard backlight
      in the Brightness applet and brightness keys (2026-09-27).
- [x] Match the waywallen wallpaper (accent colour or per-key picture), updated
      on each wallpaper change (2026-09-27).
- [x] Measure per-key write timing on hardware; chunk delay cut from 100 ms to
      20 ms (2026-09-27; see research/README.md).
- [ ] Live wallpaper mirroring: blocked on the storage-persistence test
      ([issue #1](https://github.com/JoseStud/8bitdo-retro87-tools/issues/1)).
- [ ] Decode advanced mappings (mouse, media, combinations), macros and sleep settings.
- [ ] Validate key remapping and sound level on hardware.
- [ ] Complete manual keyboard/accessibility review.

Hardware validation summary (2026-09-27): preset selection, profile activation
via the Profile button, breathing colour/brightness/speed, the vendor default
profile image and all per-key lighting effects work. The first solid-colour
test looked like a failure. The keyboard was actually showing its onboard
lighting (inactive profile, onboard solid brightness zero), as recorded in
research/README.md and PROTOCOL.md. 68 automated tests pass (as of the
KDE and wallpaper work).

### Review interaction fix and testing (2026-09-27)

- Reproduced an inert Review button with no staged edits: it was disabled.
  The dialog already opened after staging. Review now opens in both states and
  explains how to stage an edit when empty, or how to load a configuration.
- Added mouse/keyboard interaction tests for empty review, populated review,
  Close/Escape, local profile creation and remapping, all eight lighting modes,
  volume changes, and discard cancellation/confirmation.
- Tested Apply cancellation, backup/readback on simulated success, and partial
  failure lockout while keeping review available. No real hardware writes.
- Offscreen suite passes at normal and 2× scaling. Review, volume/discard and
  all-preset staging/review interaction tests also pass on the user's Wayland
  desktop using offline test data. This is not hardware-write validation or
  full feature-parity certification.

## Reference inventory and evidence boundaries

Source assembly: downloaded official Ultimate Software V2 Windows V1.35.
The original temporary research directory disappeared. Vendor V1.35 was recovered;
durable reproduction instructions and findings are now in `research/README.md`
and `research/inspect_vendor.py`. Do not redistribute vendor binaries or artwork.

| Surface | Official evidence | Existing implementation | Remaining work |
| --- | --- | --- | --- |
| Shell | XboxSettingMenuView: Mapping, Macro, Voice, Led, ProfileName | Native QML shell, staged Apply and review | Interactive accessibility review |
| Keys | XboxMappingView: category controls, source/target, Win/Tab/F4 switches | Single key/modifier/none plans | Trace advanced categories, combinations and shortcut switches |
| Macros | XboxMacroView; MacroSettingXbox: event list, delay, repeat, record, save | Local event editor, delays, finite repeats, JSON import/export, K1–K8 target intent and focused identification; full-allocation read-only backup | Decode storage, limits, assignment, backup and safe restoration |
| Lighting | XboxLedView: Preset/Custom, modes, direction, color, brightness, speed, count | All eight preset codecs, per-key editor, LED backup/restore | Per-preset hardware checks beyond breathing |
| Volume | XboxVoiceView: voice, progress, voice button | Staged 1–5 control; native write offset confirmed | Hardware behavior validation |
| Profiles | Profile menu and names | Explicit creation, rename, offline import/export, profile backup/restore | Full macro backup coverage and hardware lifecycle validation |
| Settings | Existing profile includes LED sleep | Read-only value | Trace exact UI controls and valid encodings |

These types are shared across editions. Field presence alone does not prove a
control is enabled for Panther. Trace model conditions before enabling features.

Public screenshot: https://app.8bitdo.com/images/support/new-software/mapping.jpg
shows Fami Keys view: centered tabs, left editor, right keyboard and extension
buttons. It establishes layout, not exact Panther artwork or all current labels.

## Implementation safety invariants
- No automatic initialization or normalization; nothing is written without Apply confirmation.
- Preserve unsupported/unknown bytes; distinguish unknown/default from a value.
- Serialize device I/O; compare fresh affected regions to baseline before Apply.
- Back up every affected region before writes; fail closed without coverage.
- On write failure, report partial state and stop, no automatic retries/rollback.
- Test disconnect, contention, access denial, stale edits and backup failure.
- Capture only focused macro-editor input; never run a global key logger.

### Local macro editor (2026-09-28)

- Added independent local macro documents with key-down/up events, per-event
  delays, ordering, removal and finite repeat counts. New/open/save/discard
  controls use the existing native page styling.
- Versioned JSON files are distinct from device snapshots. Import validation,
  exclusive file creation and unsaved-edit guards protect local documents.
- Sequence diagnostics report duplicate presses and missing releases; incomplete
  drafts remain saveable. No recording, playback, assignment or device codec.
- Hardware macro work still needs the protocol evidence listed in research/README.md.

### Super Button preparation (2026-09-28)

- Traced vendor port pairs and input-report extension bits. Added a focused
  identification window with timeout, focus-loss cleanup and mode restoration.
- Live identification of the user's first accessory jack reported K7 then K8
  (vendor Y pair). Ordinary key data was not recorded.
- Added optional K1–K8 target intent to local macro documents (version 2, with
  version 1 import compatibility). This does not stage a hardware assignment.
- Added bounded command-7 macro reads and a separate ten-allocation raw backup.
  On hardware all ten blocks read as `ff`, with two matching reads per block.
- Hardware macro writes remain unavailable pending erase-extent proof, complete
  metadata/timing semantics and restoration validation.
