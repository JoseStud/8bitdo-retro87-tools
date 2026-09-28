# Draft: Add 8BitDo Retro 87 (Mecha BREAK) keyboard

Draft merge request text for upstream OpenRGB
(https://gitlab.com/CalcProgrammer1/OpenRGB). Review it, and the code, before
submitting. OpenRGB's CONTRIBUTING.md asks that submitters fully understand
the code they send and that commits carry no AI authorship.

---

Adds a controller for the 8BitDo Retro 87 Mechanical Keyboard, Mecha BREAK
edition, over its 2.4 GHz dongle (`2dc8:202e`, "8BitDo Retro 87 Adapter X"),
configuration interface 2 (usage page `0xFFA0`, usage `0x01`).

## Modes

| OpenRGB mode | Keyboard effect | Parameters |
| --- | --- | --- |
| Custom | Per-key static | Per-LED colour, brightness |
| Static | Solid | Colour, brightness |
| Breathing | Breathing | Colour, brightness, speed |
| Spectrum Cycle | Cycle | Brightness, speed |
| Rainbow Wave | Colour ripple | Brightness, speed |
| Ripple | Ripple | Colour, brightness, speed |
| Resonance | Resonance | Background and highlight colours, brightness, speed |
| Starlight | Starlight | Background and star colours, brightness, speed |
| Off | Off | |

All modes save to the keyboard. There is no Direct mode: a per-key update is
a prepare command plus six chunks (about 0.2 s with 20 ms between chunks; the
vendor software waits 100 ms), and the keyboard displays at most about three
updates per second. Faster updates are acknowledged but not shown.

The keyboard layout is ANSI TKL. The right Fn and Menu positions hold the
Retro 87's A and B buttons. The space bar has five LEDs, which are all set to
the space key's colour.

## Protocol

64-byte reports: OUT ID `0x81`, IN ID `0x02`.
Request `81 04 CMD 00 LEN SUM OFFSET(LE32) DATA`, response
`02 04 03 CMD LEN xx OFFSET(LE32) DATA`. Commands: `01` write and `02` read
the 1532-byte profile, `08` enter configuration mode, `0D`/`0E`/`0F`
prepare/write/read the 283-byte per-key block. Each profile write is
acknowledged and then verified by readback.

Full notes: https://github.com/JoseStud/8bitdo-retro87-tools/blob/main/PROTOCOL.md

## Notes for users

- The keyboard applies stored brightness, speed and colours only while its
  profile is active (Profile button indicator lit). Otherwise it uses its
  onboard Fn-key settings, and only the effect selection changes.
- A factory-fresh keyboard has no stored profile. One must be created once
  with the vendor software (or the linked Linux tools) before the Profile
  button activates.

## Testing

Tested on Linux (Arch, hidapi 0.15) with the dongle: detection, reading the
current effect, <fill in: which modes were checked on hardware>.
