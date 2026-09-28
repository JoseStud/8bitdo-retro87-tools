# Retro 87 (Mecha BREAK: Panther) configuration protocol

Recovered from Ultimate Software V2 for Windows v1.35 by static analysis (the
vendor code was never executed), then verified on a Retro 87 Mecha BREAK:
Panther through its 2.4 GHz dongle on 2026-09-27. The vendor app identifies the
dongle `2dc8:202e` as `PID_XBOXJPUSB` (8238) and drives it through the
`PID_XBOXJP` code paths (`SelectPlatform.Update_Click` sets
`PID_Current = PID_XBOXJP`).

Native DLL `8BitDoAdvance.dll` SHA-256
`d80a5362df432e43be657ba32051d1cae0d029afcd7edc16b458de11bc131166`.
Addresses below assume image base `0x10000000`. See
[research/README.md](research/README.md) for how to reproduce the analysis and
for the full hardware test log.

## Evidence levels

| Area | Status |
| --- | --- |
| Transport, reads, write framing and acknowledgments | Hardware-verified |
| Preset selection (`0x5ca`), profile activation (`0x24`) | Hardware-verified |
| Breathing colour, brightness and speed encodings | Hardware-verified (profile active) |
| Other presets' parameters | Same encoding as breathing (vendor code); not individually tested |
| Vendor default profile image | Written and verified by readback; the profile then activates |
| Per-key LED block, layout, write sequence and all effects | Hardware-verified |
| Key remapping records, sound level | Vendor code and tests only |
| Macros, sleep settings, mouse/media assignments | Not implemented |

## Sources

- [Ultimate Software V2](https://app.8bitdo.com/Ultimate-Software-V2/),
  archive `8BitDo_Ultimate_Software_V2_Windows_V1.35.zip`.
- [Mecha BREAK FAQ](https://support.8bitdo.com/faq/retro-87-mechanical-keyboard-mechabreak.html)
  and the [Retro 87 manual](https://download.8bitdo.com/Manual/PC-Peripherals/Retro-87-Mechanical-Keyboard.pdf)
  (Profile button, factory reset combination, Fn lighting keys).
- [.NET bundle manifest](https://github.com/dotnet/runtime/blob/main/src/installer/managed/Microsoft.NET.HostModel/Bundle/Manifest.cs)
  format, used to extract the managed assembly without running it.
- [goncalor/8bitdo-kbd-mapper](https://github.com/goncalor/8bitdo-kbd-mapper/blob/main/protocol.txt):
  a different, earlier 8BitDo keyboard protocol; its `0x52`/`0x54` reports do not
  apply here.

## Transport

- Interface 2, vendor usage page `0xffa0`; OUT endpoint `0x05`, IN `0x84`.
  The tools find the hidraw node by VID/PID and its exact report descriptor.
- OUT report ID `0x81`, IN report ID `0x02`, 64 bytes each.
- The dongle exposes no HID LampArray (Dynamic Lighting) interface.

Request (zero-padded to 64 bytes):

| Offset | Meaning |
| --- | --- |
| 0 | `81` |
| 1 | `04` |
| 2 | Command |
| 3 | `00` |
| 4 | Length (≤ 53) |
| 5 | Sum of payload bytes mod 256 (0 for reads) |
| 6–9 | Offset, little-endian uint32 |
| 10… | Payload |

Response: `02 04 03 CMD LEN … OFFSET_LE32 DATA…` (data from byte 10). For
writes, `LEN` is the number of bytes the keyboard accepted.

| Command | Use |
| --- | --- |
| `01` | Write profile region |
| `02` | Read profile region (1532 bytes) |
| `08` | `ReportXbox(0)`: enter configuration mode. The vendor sends it once per session (`reportID` caches it) and never exits |
| `0d` | Prepare the per-key LED write (no payload; wait for its reply) |
| `0e` | Write the per-key LED region |
| `0f` | Read the per-key LED region (283 bytes) |
| `10` | `ReadLightingState`; unused by the `XboxJP` code path |

The vendor sleeps 10 ms after command 8 and before each write call. The tools
do the same and verify each write range by reading it back.

## Profile region (`0x5fc` bytes)

| Offset | Size | Field |
| --- | --- | --- |
| `0000` | 4 | Marker `02 09 20 20` (`0x20200902`); `ff` when uninitialized |
| `0004` | 32 | Profile name, UTF-16BE, zero-padded |
| `0024` | 1 | **Profile active**: 1 = active, 0 = inactive, toggled by the keyboard's Profile button |
| `0025` | 1 | Fn lock |
| `0026` | 1 | Sleep time |
| `0027` | 1 | LED sleep time |
| `0028` | 1440 | 120 key records × 12 bytes |
| `05c8` | 1 | Fast settings (bit 0 Win, bit 1 Tab, bit 2 F4) |
| `05c9` | 1 | Device sound level 1–5 |
| `05ca` | 1 | Current preset |
| `05cc` | 4 | LED sleep, uint32 LE (default 300) |
| `05d0` | 5 | Solid: brightness, colour flag, R, G, B |
| `05d5` | 2 | Cycle: brightness, speed |
| `05d7` | 3 | Colour ripple: brightness, speed, direction 0–5 |
| `05da` | 6 | Breathing: brightness, speed, flag, R, G, B |
| `05e0` | 6 | Ripple: brightness, speed, flag, R, G, B |
| `05e6` | 9 | Resonance: brightness, speed, flag, background RGB, echo RGB |
| `05ef` | 10 | Starlight: brightness, speed, count, flag, background RGB, echo RGB |
| `05f9` | 1 | Per-key (custom) lighting enable |
| `05fa` | 1 | Lighting engine: 0 vendor RGB, 1 Windows Dynamic Lighting |

Encodings (verified on breathing): brightness is `percent * 255 // 100`; speed is
stored as `11 - UI speed` (stored 1 is fastest); colours are R, G, B; flag 1
means "use this colour".

Preset IDs: 0 off, 1 resonance, 2 starlight, 3 solid, 4 cycle, 5 colour ripple,
6 breathing, 7 ripple. The keyboard's own lighting key steps through 0 → 7 in
order and updates `0x5ca`.

### Activation: why lighting writes seemed to do nothing

- The firmware uses the stored preset **parameters** only while `0x24 == 1`.
  While it is inactive, it uses onboard settings controlled by the Fn
  brightness/colour keys. These settings are not stored in either readable
  region. On the test keyboard, onboard solid brightness was zero, so solid
  looked dark whatever we wrote.
- The preset **selection** (`0x5ca`) takes effect in both states.
- The Profile button toggles `0x24` only once the marker is valid. With an
  all-`ff` factory profile, it lit its indicator but changed no readable byte.
- With the profile active, parameter writes show immediately, without
  reselecting the preset.
- The vendor's `Readflag` (`ReadXboxJPflag`, `0x1041b470`) reads `0x24`. When it
  is not 1, the app shows its "press the Profile button" tip, but writes anyway.

### Preset selection sequence

`XboxLedView.*_ModeDown` (`PID_XBOXJP` branch): if `0x5f9` is nonzero, write
`0x5f9 = 0` (`writeColorFlag`), then call `Readflag` and write `0x5ca`
(`writeCurrentColor`). The vendor does not write `0x5fa` here (only
`DynamicSetting_Down` does) and does not rewrite theme parameters. Editing a
theme sends the complete theme record (`writeXboxJPColor`).

### Creating a profile

`JPPlatFormView.RenameResult` → `XboxJPAdvanceUI.clearConfig` (zeroes the
struct) → `XboxJPAdvance.temp_new` (defaults) → `copyFile` → `writeAdvance`
(the whole profile via `writeXboxJP`, then the LED region via
`writeXboxJPLed`). The default image (`default_profile()` in `retro87_core.py`):

- marker and name;
- `0x24`–`0x27` = 0;
- identity key records (type 0), with unused slots zeroed;
- fast settings 0, sound 2, preset 1 (resonance), LED sleep 300;
- every theme at brightness `ff` and stored speed 3, colour flag 1, colour
  `ff a5 00` (orange), black backgrounds; starlight count 5;
- `0x5f9` = `0x5fa` = 0.

The tools write this image with the marker last. They keep the current preset
rather than resonance, and do not write the vendor's default LED block.

### Key records

Each record is `uint8 keyCode`, 3 padding bytes, `uint32 mapping`,
`uint32 mappingType` (little-endian) at `0x28 + slot*12`. Type 0 is the
default, type 1 a keyboard key, type 2 consumer (target enum 172–183, except
179), type 3 mouse (162–171), and type 4 a macro. `keycodes.json` holds the
slot, source-code and target tables recovered from `setInitXboxKeyMappings` and
`BasicJPAdvanceUIData.setMapping`. Example: Caps Lock → Esc is
`39 00 00 00 29 00 00 00 01 00 00 00` at `0x334`. Remapping has not been
tested on hardware.

## Per-key LED region (`0x11b` = 283 bytes)

`LED_CUSTOM_THEME`, built by `BasicJPAdvanceUIData.getTotalColor`:

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 1 | Brightness (`percent * 255 // 100`) |
| 1 | 1 | Colour flag, 1 |
| 2 | 1 | Type: 0 freeze (vendor "close"), 1 static, 2 breathing, 3 starlight |
| 3 | 1 | Speed, `11 - UI speed` |
| 4 | 1 | Starlight count 5–100 |
| 5 | 4 | Reserved, 0 |
| 9 | 273 | 91 × R, G, B |
| 282 | 1 | `is_done`, 1 |

Hardware results: all types display as described, with brightness and speed
effective and a higher starlight count lighting more keys. Type 0 **freezes the
current frame** rather than turning off. Static at brightness 0 is dark, and
the tools use that for "off".

Write sequence, native `writeXboxJPLed` (`0x1043e0f0`):

1. Sleep 10 ms, send command `0d` (length 0, offset 0), and wait for
   `02 04 03 0d`.
2. For offset 0 up to 283: sleep (vendor 100 ms; the tools use 20 ms), then send command `0e` with up to
   53 bytes at that offset. Wait for `02 04 03 0e LEN` and advance the offset
   by `LEN`.
3. (Tools) Read the region back with command `0f` and compare.

Enable per-key mode with `0x5f9 = 1` (`Custom_MouseLeftButtonDown` →
`writeColorFlag`). Selecting a preset clears it.

LED order (`XboxLedView.initMappings` + `ColorPoint.getXboxJP`): 87 on-screen
buttons, bottom row first, each row left to right. Button `i` drives LED `i` for
`i < 3`, otherwise LED `i + 4`. The space bar (button 3) drives LEDs 3–7
(`writecolor`). Button order:

```text
 0-10  lctrl lwin lalt space ralt A B rctrl left down right
11-23  lshift z x c v b n m , . / rshift up
24-36  caps a s d f g h j k l ; ' enter
37-53  tab q w e r t y u i o p [ ] \ delete end pgdn
54-70  ` 1 2 3 4 5 6 7 8 9 0 - = backspace insert home pgup
71-86  esc f1–f12 prtsc scrlk pause
```

The A and B keys (`ka`, `kb`) were identified on hardware. `LED_KEYS` in
`retro87_core.py` is the authoritative list.

## Useful native functions

| Function | Address | Notes |
| --- | --- | --- |
| Packet builder | `1040a8b0` | 53-byte chunks, additive checksum |
| `readXboxJP` | `1042c280` | Command 2, 1532 bytes |
| `readXboxJPLed` | `1042cb60` | Command 15, 283 bytes |
| `writeXboxJPKey` | `1043df10` | 12 bytes at `0x28 + slot*12` |
| `writeXboxJPColor` | `1043d600` | Theme records |
| `writeXboxJPCurrentColor` | `1043dcb0` | 1 byte at `0x5ca` |
| `writeXboxJPColorFlag` | `1043dae0` | 1 byte at `0x5f9` |
| `writeDynamic` | `10430d10` | 1 byte at `0x5fa` |
| `writeXboxJPVolume` | `1043ea60` | 1 byte at `0x5c9` |
| `writeXboxJPLed` | `1043e0f0` | Commands `0d`/`0e` |
| `ReadXboxJPflag` | `1041b470` | Reads `0x24`; active iff 1 |
| `ReportXbox` | `1041b6e0` | Command 8 |
| `ReadLightingState` | `104196d0` | Command `10`; returns byte == 1 |
