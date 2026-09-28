# Draft: 8BitDo Retro 87 (Mecha BREAK) keyboard and HID LampArray without IN endpoint

Notes toward an upstream OpenRGB merge request
(https://gitlab.com/CalcProgrammer1/OpenRGB). The code in
[../openrgb/retro87-openrgb.patch](../openrgb/retro87-openrgb.patch) was
written with an AI assistant. OpenRGB's CONTRIBUTING.md does not permit
AI-generated submissions as a general rule and forbids AI authorship credits,
so neither the patch nor this text should be submitted as-is: a human
submitter needs to rework and fully vet the code first. Current behaviour and
design are described in [../OPENRGB.md](../OPENRGB.md).

---

## Summary

1. **8BitDo Retro 87 controller.** The keyboard's configuration interface
   (interface 2, usage page `0xFFA0`, usage `0x01`) over its 2.4 GHz dongle
   (`2dc8:202e`, "8BitDo Retro 87 Adapter X") or its USB cable (`2dc8:2028`,
   "8BitDo Retro 87 Keyboard X"). A dongle whose keyboard does not answer is
   not added.
2. **Direct mode over the cable** through the keyboard's HID LampArray
   interface, merged into the same device.
3. **HID LampArray on Linux without an interrupt-IN endpoint.** `usbhid` does
   not bind such interfaces, so hidapi (hidraw) cannot see them; a libusb
   transport and detector handle them. Includes a fix for the uninitialised
   report-ID table.

## Modes

| OpenRGB mode | Keyboard effect | Parameters | Saved |
| --- | --- | --- | --- |
| Direct (cable only) | Host-controlled, HID LampArray | Per-LED colour | No |
| Custom | Per-key static | Per-LED colour, brightness | Yes |
| Static | Solid | Colour, brightness | Yes |
| Breathing | Breathing | Colour, brightness, speed | Yes |
| Spectrum Cycle | Cycle | Brightness, speed | Yes |
| Rainbow Wave | Colour ripple | Brightness, speed | Yes |
| Ripple | Ripple | Colour, brightness, speed | Yes |
| Resonance | Resonance | Background and highlight colours, brightness, speed | Yes |
| Starlight | Starlight | Background and star colours, brightness, speed | Yes |
| Off | Off | | Yes |

Saved modes carry `MODE_FLAG_AUTOMATIC_SAVE`. Writing the per-key block starts
with a prepare command (`0x0D`) that was shown on hardware to erase the
keyboard's flash, so saved writes are coalesced to at most one per second and
identical per-key writes are skipped. Direct is the only mode for per-frame
updates; leaving it for the unchanged previous mode only re-enables the
LampArray's autonomous mode.

The layout is ANSI TKL. The right Fn and Menu positions hold the Retro 87's A
and B buttons. The space bar has five LEDs, set together from the space key.

## Protocol

Configuration interface: 64-byte reports, OUT ID `0x81`, IN ID `0x02`.
Request `81 04 CMD 00 LEN SUM OFFSET(LE32) DATA`, response
`02 04 03 CMD LEN xx OFFSET(LE32) DATA`. Commands: `01` write and `02` read
the 1532-byte profile, `08` enter configuration mode, `0D`/`0E`/`0F`
prepare/write/read the 283-byte per-key block. Each profile write is
acknowledged and verified by readback.

LampArray (interface 3, cable only): 91 lamps, minimum update interval 30 ms,
feature reports `0x11`–`0x16`, lamp IDs auto-increment after one attributes
request. Firmware (bcdDevice 1.14) lamp attributes contain wrong X positions,
a (0, 0) position and wrong or missing key usages; the patch corrects them for
`2dc8:2028`.

Full notes: https://github.com/JoseStud/8bitdo-retro87-tools/blob/main/PROTOCOL.md

## Notes for users

- The keyboard applies stored brightness, speed and colours only while its
  profile is active (Profile button indicator lit). Otherwise it uses its
  onboard Fn-key settings, and only the effect selection changes.
- A factory-fresh keyboard has no stored profile. One must be created once
  with the vendor software (or the linked Linux tools) before the Profile
  button activates.
- Direct needs the USB cable; the dongle has no LampArray.
- Linux: the wired keyboard's hidraw (interface 2) and USB device node
  (LampArray, via libusb) need user access; the generated udev rules cover
  `2dc8:2028`.

## Testing so far

Linux (Arch), OpenRGB `d008deb`, keyboard on the USB cable, 2026-09-27/28:
detection of one device with Direct and all effects; Direct colours and hand
back via the tray service at about 8 frames per second; Custom brightness
drag coalesced to 3 saves for 61 updates; identical Custom writes skipped;
unreachable dongle skipped. Not yet tested: every effect mode over OpenRGB on
hardware, the dongle path with this build, Windows and macOS.
