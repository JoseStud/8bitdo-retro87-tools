# Reproducible vendor analysis

All findings below are static analysis, not hardware-write validation. Vendor
code is parsed and disassembled, never executed. Do not commit vendor binaries
or extracted artwork. Temporary artifacts can disappear; this document records
the durable evidence and remaining boundaries.

## Source and tooling

Official archive used:
https://support.8bitdo.com/bd-uploads/files/ultimate_soft/8BitDo_Ultimate_Software_V2_Windows_V1.35.zip

Native `8BitDoAdvance.dll` SHA-256:
`d80a5362df432e43be657ba32051d1cae0d029afcd7edc16b458de11bc131166`

Research dependencies: `dnfile`, `dncil`, `pefile`, `capstone` (not needed to run
the desktop app). `inspect_vendor.py` provides three static-only entry points:

```sh
.venv/bin/python research/inspect_vendor.py bundle '/path/8BitDo Ultimate Software V2.exe' /tmp/retro87-managed.dll
.venv/bin/python research/inspect_vendor.py managed /tmp/retro87-managed.dll 'BasicJPAdvanceUIData.get.*Theme$' --output /tmp/themes.txt
.venv/bin/python research/inspect_vendor.py native '/path/8BitDoAdvance.dll' writeXboxJPVolume
```

The bundle parser selects the app's managed DLL from the .NET bundle manifest;
it does not extract arbitrary archive paths. The extracted V1.35 managed assembly
is 99,886,592 bytes. The managed command matches full type/method names with a
regex. Matching a type also emits all its methods, so anchor specific queries.
Native addresses below refer to the V1.35 32-bit image (base `0x10000000`).

## Preset codecs (implemented)

`BasicJPAdvanceUIData.getLoopTheme`, `getColorRippleTheme`, `getRippleTheme`,
`getResonanceTheme`, `getStarlightTheme` construct the native theme structs.
`getSingleTheme`/breathing encoding was recovered in the original CLI research.
Brightness is one byte; speed is `11 - UI speed` with UI speed 1–10. RGB order is
red, green, blue. Explicit color setters write the color flag as 1.
`XboxLedView.up` converts percentage brightness with integer arithmetic:
`percent * 255 / 100`, truncated. Thus 50% is `0x7f`, not rounded `0x80`.

| Mode | Profile offset | Byte sequence |
| --- | --- | --- |
| solid | `0x5d0` | brightness, flag, RGB |
| cycle | `0x5d5` | brightness, speed |
| color-ripple | `0x5d7` | brightness, speed, direction |
| breathing | `0x5da` | brightness, speed, flag, RGB |
| ripple | `0x5e0` | brightness, speed, flag, RGB |
| resonance | `0x5e6` | brightness, speed, flag, background RGB, echo RGB |
| starlight | `0x5ef` | brightness, speed, count, flag, background RGB, echo RGB |

`XboxLedView.Horizontal_ModeDown`, `Horizontalre_ModeDown`, `Vertical_ModeDown`,
`Verticalre_ModeDown`, `Diffuse_ModeDown`, `Shrink_ModeDown` assign direction
0–5 respectively and call `writeColorRipple`.
`NumberProgress.setProgress` clamps star count to 5–100; pointer movement uses
that same range. `getStarlightTheme` stores the number directly as one byte.

Preset activation (`XboxLedView.*_ModeDown`, `PID_XBOXJP` branch; the dongle
`0x202e` is `PID_XBOXJPUSB`, and `SelectPlatform.Update_Click` sets
`PID_Current = PID_XBOXJP`): if the loaded custom flag `0x5f9` is nonzero, set it
to 0 and write it (`writeColorFlag`); call `Readflag`; then write mode
`0x5ca = 0..7` (`writeCurrentColor`). The engine byte `0x5fa` is written only by
`DynamicSetting_Down` (`writeDynamic`), never on preset selection, and theme
parameters are not rewritten on selection. An earlier version of these tools
also wrote `0x5fa = 0`; the 2026-09-27 hardware test that did so went dark.
The tools now match the vendor sequence. The GUI writes theme parameters before
the activation fields, and profile name/flags before publishing the
initialization marker.

`Readflag` → native `ReadXboxJPflag` (`0x1041b470`): command 2 read of one byte
at `0x24`, retried up to 30 times; true only when the byte is 1. When false the
app opens `OpenXboxTispDialog` (the "press the Profile button" tip) but still
performs the mode write. On this keyboard `0x24` reads `ff`, so the vendor app
would show that tip; status output and post-apply messages now report it.

`reportID(0)` caches the last report mode (initialized to -1), so native
`ReportXbox(0)` (command 8) is sent once per session. The app never sends a
different value. Each managed write wrapper then sleeps 10 ms before its native
call; `Keyboard.apply` sends command 8 once and pauses 10 ms before every range.

Physical lighting-key observation (read-only watch, 2026-09-27): the on-keyboard
key steps `0x5ca` through 0→7 in order and leaves every theme record `ff`, so
blank records are normal firmware state.

Solid preset hardware results (2026-09-27, 2.4G dongle, profile header and
`0x24` both `ff`):

- First authorised write (21:15 UTC): solid `#00c8ff` at 50% plus `0x5fa = 0`
  and `0x5f9 = 0`. Readback matched, but the backlight went dark. Restoring the
  previous lighting bytes brought it back. A selector-only write (`0x5ca = 3`)
  and a complete cyan record with the original flags were also dark.

- Writing `0x5ca = 2` (starlight) visibly switched the effect, so mode writes
  take effect.
- Preset 3 (solid) stayed dark in every tested state: vendor-exact write
  (`0x5f9 = 0`, `0x5ca = 3`); full-brightness white record `ff 01 ff ff ff`;
  selecting 3 with the keyboard's own lighting key; and with the physical
  Profile button's indicator lit. The Profile button changed no readable byte.
- The dongle exposes no HID LampArray interface (usage page `0x59`), so a host
  Dynamic Lighting layer is not the cause over 2.4G.
- Vendor new-profile image (`default_profile`, from `RenameResult` →
  `clearConfig`/`temp_new`/`copyFile`/`writeAdvance`) written with mode 3:
  readback exact, header now valid, `0x24` = 0; solid still dark.
- **Cause found:** solid's brightness is held by the firmware and was at zero.
  The owner raised it with the onboard Fn brightness key and solid lit up green.
  Neither that key nor the onboard colour key changes any byte in the profile
  or LED regions.
- The stored solid record is ignored for display: with orange `ff a5 00`, then
  blue `00 00 ff` (also after reselecting cycle → solid by write), the keyboard
  stayed on its onboard colour. Solid colour/brightness are therefore onboard
  controls on this firmware over 2.4G; only the preset selection (`0x5ca`)
  has a verified visible effect while the profile is inactive.
- **Profile activation is the switch.** With a valid header, the physical
  Profile button toggles `0x24` between 0 and 1 (with an `ff` header it changed
  nothing readable). With `0x24 = 1`, breathing showed the stored colour
  (green `00 ff 00`, then blue `00 00 ff`); writes applied immediately without
  reselecting the preset. Channel order is R, G, B. Brightness `0x40` was
  visibly dimmer. Stored speed 10 was slower than 1, confirming
  `stored = 11 - UI speed`. With `0x24 = 0` the keyboard uses onboard lighting
  (Fn brightness/colour keys), which is why solid looked dark.
- Profile creation now writes the full vendor default image
  (`profile_plan` → `default_profile`), keeping the current preset.
All-FF theme records are shown as unknown/default, never fabricated readings.

Native `writeXboxJPColor` sends each complete theme structure even when some
bytes are unchanged. The desktop transaction planner now follows those record
boundaries; a brightness-only edit still emits the full theme. Raw changed-byte
compression previously produced a four-byte solid write when its blue byte
remained `ff`. Regression tests cover unchanged interior/trailing bytes and
every integer percentage. These corrections match vendor behavior but require
physical-effect feedback; storage readback alone is insufficient evidence.

## Volume (implemented)

`XboxVoiceView.voiceProgressDelegate` converts five positions `15 + 45*n`
into level `n+1`, giving 1–5. Native `_writeXboxJPVolume@1532` at `0x1043ea60`
writes one byte at `0x5c9` using command 1. This is device sound, not host volume.

## Advanced mappings (not exposed yet)

`XboxKeyBoardTools.getMode` selects type 3 for target enum 162–171 (mouse),
type 2 for 172–183 except 179 (consumer), and type 1 otherwise. A branch
`enum > 183 && enum < 184` appears unreachable for integer enums; do not infer
a supported category from it. Confirm enum constants and the actual native
target values before enabling mouse/media/chord mapping.

Fast-settings preparation packs Win/Tab/F4 into bits 1/2/4 of `0x5c8`;
the native writer is at `0x1043dd40`. Exact switch semantics and Panther
availability still need tracing. LED sleep writes four bytes at `0x5cc`
(`0x1043e890`); valid UI choices still need confirmation.

## Macros (do not enable hardware writes yet)

`BasicJPAdvanceUIData.getMacroAddress` allocates aligned 4096-byte regions.
Mapping type 4 holds a macro address. Official read code accepts at most 1008
steps. Native read-info at `0x1042cfd0` uses command 7 for 48 bytes.
Native `writeXboxJPMacro` at `0x1043e340` performs:

1. Command 5 at the macro address (low 16 bits), no payload; acknowledgment and
   100 ms delay. Likely erase/preparation; exact erase extent is not established.
2. Command 6 writes a 48-byte metadata structure at the macro address.
3. Command 6 writes four-byte event records at address + `0x40`, in chunks of
   at most 53 bytes. `64 + 1008*4 = 4096`.

Metadata fields in managed declaration order: uint32 flag; byte source key;
32-byte UTF-16BE name; uint16 step count; uint16 interval; byte repeat;
byte repeat type; uint16 unify time; uint16 reserved. Padding/alignment must
still be verified rather than guessed. Event fields: byte key state, byte key
code, uint16 timer; enum state constants remain to be confirmed.

Before implementation: prove read coverage of the entire affected erase unit,
metadata alignment, key-state/repeat enums, allocation limits, and restoration
of unused bytes. Current snapshots omit macro storage. No macro commands are
accepted by the current transport, and none were sent to the keyboard.

## Per-key custom lighting (implemented, hardware-verified 2026-09-27)

Native `writeXboxJPLed` (`0x1043e0f0`): after the command-8 session, send
command `0x0d` with no payload and wait for its `02 04 03 0d` reply; then send
the 283-byte `LED_CUSTOM_THEME` with command `0x0e` (offset little-endian, up to
53 bytes each), sleeping 100 ms before every chunk and advancing by the length
byte of each `02 04 03 0e LEN` acknowledgment. Command `0x0f` reads it back.

`LED_CUSTOM_THEME`: brightness, color_flag (1), type, speed (`11 - UI`), number
(starlight count), four reserved bytes, `color[273]` (91 RGB triples), is_done (1).
`BasicJPAdvanceUIData.getTotalColor` builds it. `type` comes from
`XboxLedView.Total*_ModeDown`: 0 (`TotalClose`), 1 static, 2 breathing, 3 starlight. On hardware, type 0 stops the animation and holds the current frame rather than darkening; the tools call it `freeze` and implement `off` as static at 0% brightness (verified dark).
Custom mode is enabled by writing `0x5f9 = 1` (`Custom_MouseLeftButtonDown` →
`writeColorFlag`); selecting a preset clears it.

LED order: `XboxLedView.initMappings` creates 87 buttons at the
`ColorPoint.getXboxJP` coordinates, bottom row first, left to right. Button
`i` drives LED `i` for `i < 3`, otherwise LED `i + 4`; `writecolor` gives the
space bar LEDs 3–7. `LED_KEYS` in `retro87_core.py` lists the order. The two
bottom-row keys after Right Alt are the A and B keys (`ka`, `kb`), confirmed on
hardware. A test pattern (WASD red, space green, rest blue) displayed exactly,
with the profile active.

Per-key hardware results (2026-09-27, profile active): static, breathing and
starlight all display the stored per-key colours; brightness 30% was visibly
dimmer and speed 10 faster than 5; starlight count 100 lit clearly more keys
than 25; type 0 froze the last starlight frame; static at brightness 0 was dark.

## Per-key write timing and dongle reads (hardware tests, 2026-09-27)

Transfer speed. Per-key blocks were written with 100, 50, 20 and 0 ms before
each `0x0e` chunk (the vendor uses 100 ms). Every chunk was acknowledged in
6–9 ms and every block read back exactly:

| Delay per chunk | Whole write (after command 8) |
| --- | --- |
| 100 ms | 690 ms |
| 50 ms | 388 ms |
| 20 ms | 209 ms |
| 0 ms | 87–95 ms |

The prepare command `0x0d` takes about 45 ms. The tools now use 20 ms
(`LED_CHUNK_DELAY`), so a per-key write takes about 0.2 s.

Display rate. Whole-keyboard red/blue frames were written with no chunk delay
at a fixed rate and observed on the keys:

| Frames per second | Observed |
| --- | --- |
| ~10 (back to back) | Changes skipped |
| 4 | Only the first few changes shown |
| 3 | Every change shown |
| 2 | Every change shown |

The keyboard acknowledges faster updates but needs about 250–330 ms to apply
each one. Whether that time is spent writing to permanent storage is not known.

Reads come from the dongle. With the keyboard switched off (its lights stayed
on), reads of the profile and per-key regions were still answered in about
9 ms with the last written data, while a per-key write failed (no `0x0d`
acknowledgment). The dongle therefore answers reads from its own copy. While
the keyboard is connected that copy tracks it (Profile-button and
lighting-key changes appear in reads), but a readback does not by itself
prove what the keyboard stored.

Persistence: open. The per-key pattern survived switching the keyboard off
and on, but the lights never went dark, so power was probably not removed. A
test with no USB cable and the lights fully dark (or a flat battery) is still
needed. Live wallpaper mirroring waits on this answer; see
[issue #1](https://github.com/JoseStud/8bitdo-retro87-tools/issues/1).
