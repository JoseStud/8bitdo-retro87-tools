# Storage wear assessment — 2026-09-27

Conclusion (updated 2026-09-27, hardware-proven): **every custom-LED write
erases flash.** The prepare command `0x0d` alone erases the nonvolatile area
holding the 283-byte custom LED block; see "Prepare-only erase test" below.
Configuration-based frame streaming therefore spends one flash erase per frame
and must not be used for continuous live mirroring. Erase-unit size, rated
endurance and any wear levelling remain unknown.

## Evidence and limits

- The owner reports that the custom per-key pattern survived switching the
  keyboard off with its USB cable disconnected and all lights out, then on
  with the wireless dongle also unplugged. This excludes a connected dongle
  restoring the pattern at startup and is strong evidence of keyboard-local
  retention. It is not an instrumented electrical power-removal test; the
  internal battery remained connected.
- Re-disassembly of official Ultimate Software V2 1.35 confirms
  `writeXboxJPLed` at `0x1043e0f0` sends prepare command `0x0d`, followed by the
  283-byte block through `0x0e`. There is no separate save command in this
  function. That does not mean the writes are RAM-only: the device firmware
  decides what prepare, chunk completion and payload flags do.
- Managed `BasicJPAdvanceUIData.getTotalColor` sets `is_done = 1` (IL offsets
  `0x55–0x56`). Its name does not establish whether it means transfer complete,
  apply, or persist. Setting it to zero is not a verified no-save workaround.
- The tools use this same configuration path for every changed live frame:
  `LiveMirror.submit` → `Controller.set_leds` → `Keyboard.write_led`. Reusing
  the profile and skipping identical colours does not bypass LED-block writes.
- Previous timing tests and dongle readback cannot identify erase/program
  operations. The local OpenRGB implementation derives from the same reverse
  engineering and is not independent confirmation of persistence or endurance.

Vendor DLL SHA-256:
`d80a5362df432e43be657ba32051d1cae0d029afcd7edc16b458de11bc131166`.
Reproduce the static inspection with `research/inspect_vendor.py` using the
`native ... writeXboxJPLed` and
`managed ... 'BasicJPAdvanceUIData.getTotalColor$'` entry points.

## What remains unknown

The storage technology, erase-block size, rated endurance, wear levelling,
write coalescing, and save policy have not been identified. Retention alone
cannot distinguish saving each update from periodic saving or saving on
shutdown. Even an image disappearing on restart would not prove zero writes
elsewhere. Firmware analysis or vendor confirmation is needed to establish a
no-save transport; another ordinary off/on test cannot establish endurance.

At the implemented upper limit of two changed frames per second, the host can
request 7,200 configuration updates per hour, 57,600 per eight-hour session,
or 172,800 per day. These are **update counts, not measured flash erase cycles**.
Only if each update consumes endurance in the same storage area would those
rates translate directly into wear. The two-FPS limit is a display-throughput
limit, not an endurance safeguard.

## Alternative to investigate

The [Mecha BREAK FAQ](https://support.8bitdo.com/faq/retro-87-mechanical-keyboard-mechabreak.html)
confirms the 8BitDo RGB / Windows Dynamic Lighting control-mode choice.
[Microsoft documents](https://learn.microsoft.com/en-us/windows/apps/develop/devices-sensors/lighting-dynamic-lamparray)
Dynamic Lighting as HID LampArray, an open standard for host-controlled effects.
The [vendor's Xbox Retro 87 firmware notes](https://support.8bitdo.com/)
specifically describe wired-only Dynamic Lighting in firmware 1.05. That is
family-level evidence, not a verified Panther USB descriptor.

The currently attached `2dc8:202e` adapter exposes mouse, keyboard/consumer,
and vendor-page `0xffa0` interfaces in its three HID descriptors. None exposes
the Lighting and Illumination usage page. A direct USB connection and inspection
of the keyboard's descriptors, potentially in Dynamic Lighting mode, is the
next useful check. Do not assume that a standard interface alone proves a
particular firmware never writes storage.

The direct-USB follow-up below found that interface. Runtime output and its
storage behavior remain unvalidated.

Keep configuration-based streaming off for normal use pending that work.
Static wallpaper matching or the keyboard's built-in animations require far
fewer host configuration changes. The capture code and JSON preview can still
be exercised without keyboard writes.

## Direct USB follow-up — 2026-09-27

The owner connected the keyboard by USB. Read-only inspection identified
`2dc8:2028` (product string `8BitDo Retro 87 Keyboard X`, USB `bcdDevice 1.14`)
with four interfaces. `bcdDevice` is recorded as a USB descriptor value, not
independently verified as the installed firmware version.

Interfaces 0–2 expose mouse, keyboard/consumer and the existing vendor
configuration transport. Interface 3 exposes **HID Lighting and Illumination
page `0x59`, application usage LampArray `0x01`**. It has only interrupt-OUT
endpoint `0x06`, 64 bytes, interval 1 ms. Linux `usbhid` logs
`couldn't find an input interrupt endpoint` and leaves this interface unbound;
there is no corresponding hidraw node. Thus enumerating only hidraw devices
misses the lighting interface.

The 327-byte HID report descriptor was fetched with USB GET_DESCRIPTOR:
`bmRequestType=0x81`, `bRequest=6`, `wValue=0x2200`, `wIndex=3`, `wLength=327`.
USB GET_REPORT (`0xa1`, request 1, value `0x0311`, interface 3, length 23)
successfully returned the LampArray attributes:

```text
11 5b00 c0bc0500 10980200 98b70000 01000000 30750000
```

| Field | Value |
| --- | --- |
| Lamp count | 91 |
| Bounding box | 376 × 170 × 47 mm |
| LampArray kind | 1 (keyboard) |
| Minimum update interval | 30,000 microseconds (30 ms) |

The interval advertises a ceiling of approximately 33.3 updates/second; it is
not a measured display frame rate. This is a separate protocol from the
configuration block whose observed display rate was about 3 updates/second.

The descriptor declares these Feature reports (sizes include the report ID):

| Report ID | Purpose | Size |
| --- | --- | --- |
| `0x11` | LampArray attributes | 23 bytes |
| `0x12` | Lamp attributes request (lamp ID) | 3 bytes |
| `0x13` | Lamp attributes response | 29 bytes |
| `0x14` | Multi-lamp update (up to 8 lamp IDs and colours) | 51 bytes |
| `0x15` | Lamp range update | 10 bytes |
| `0x16` | LampArray control / autonomous mode | 2 bytes |

GET_REPORT for control report `0x16` stalled (`EPIPE`); no SET_REPORT was sent.
This does not invalidate the successful attributes query. Reading the vendor
profile directly showed engine byte `0x5fa = 0` (vendor RGB), custom flag 1 and
an active initialized profile. LampArray enumeration/attribute reads therefore
work even in the current vendor RGB setting. Whether host colour updates also
work without changing that selector is not yet established.

Direct usbfs control requests required elevated USB-device access; no udev
rules, drivers, lighting configuration or firmware were changed. No colour
updates or endurance tests were performed.

The next implementation should investigate this direct-USB runtime interface
instead of repeatedly rewriting the persistent custom-lighting block. Query
lamp attributes to verify mapping before assuming the 91 indices match the
configuration layout. Validate host-control entry/exit, visible colour updates,
and stored-profile preservation. These checks still cannot prove absence of
all internal flash writes without firmware or vendor evidence.

### 2.4 GHz dongle re-check

The adapter was re-checked at the USB level rather than through hidraw alone,
since the wired LampArray interface is invisible to hidraw. `2dc8:202e`
(`8BitDo Retro 87 Adapter X`, `bcdDevice 1.14`) has one configuration with
three interfaces, each with a single alternate setting, all bound to `usbhid`:

| Interface | Endpoints | Usage pages | Application collections |
| --- | --- | --- | --- |
| 0 (hidraw) | IN `0x82` | `0x01`, `0x09`, `0x0c` | Generic Desktop (mouse) |
| 1 (hidraw) | IN `0x81` | `0x01`, `0x07`, `0x08`, `0x0c` | Keyboard, Consumer, System |
| 2 (hidraw) | OUT `0x05`, IN `0x84` | `0xffa0` | Vendor |

No interface is unbound, and no descriptor contains usage page `0x59`. The
dongle does not expose HID LampArray. This matches the vendor's wired-only
Dynamic Lighting note. Live mirroring over the standard interface therefore
requires a USB cable; over 2.4 GHz only the vendor `0xffa0` channel exists.
Whether that channel can tunnel runtime (non-persistent) colour updates is
unknown. Read-only; nothing was sent to the device.

## Prepare timing and prepare-only erase test — 2026-09-27

Timing over the dongle (26 writes of the owner's own block, 20 ms chunk delay):

| Run | `0x0d` prepare | `0x0e` chunk acks | Last-chunk ack |
| --- | --- | --- | --- |
| 10 writes, 1.5 s idle apart | 50 ms (49–52) | 6.9 ms (4.9–9.2) | 5.9 ms |
| 10 writes back to back | 50 ms (49–53) | 6.9 ms (4.9–9.9) | 5.9 ms |
| 6 writes, changed vs identical data | 50–51 ms every time | — | 5.9–6.9 ms, no difference |

Prepare costs about 43 ms of keyboard-side work beyond a radio round trip,
on every write, before any colour data arrives, so identical frames cannot
avoid it. No post-write busy period was visible.

Prepare-only test: command 8 then `0x0d` (acknowledged in 51 ms), and **no**
`0x0e` data. The running lights were unchanged (RAM). The owner then switched
the keyboard off with the USB cable and dongle disconnected, and back on:
**all key lights were dark**. After the dongle was reconnected, a `0x0f` read
of the LED block began `ff ff ff ff ff ff ff ff ff` (the first nine bytes
were printed), the erased-flash value; the same read had matched the backup
before the test. The profile was intact (active, custom flag `0x5f9 = 1`,
engine `0x5fa = 0`). The backup block was rewritten and verified by readback.

This proves that `0x0d` erases the nonvolatile storage of the custom LED
block, and that the chunk writes then reprogram it. Each per-key write,
including each changed live frame, is one erase/program cycle of that area.
For scale only: typical NOR flash is rated around 100,000 erase cycles per
sector (this part's rating is unknown). Without wear levelling, the 2 FPS live
limit (7,200 writes/hour) would reach that figure in about 14 hours of
streaming. Occasional writes, such as a per-wallpaper colour match, are not
a concern.

Official firmware metadata (8BitDo API Type 80) lists v1.05 as adding Windows
Dynamic Lighting for wired connections only. The image header carries PID
`0x2028` and a Telink boot header, identifying a Telink TLSR82xx MCU.

## LampArray streaming test — 2026-09-27

Over the USB cable, `retro87_lamparray.py` claimed interface 3 through usbfs
and used feature reports only (the descriptor declares all six reports,
`0x11`–`0x16`, as Feature). Sequence: range update red then green, a
multi-update test pattern, then 10 s of a scrolling rainbow at the advertised
30 ms interval, each frame being 12 multi-update reports (8 lamps each, last
marked complete), then autonomous mode restored.

| Measure | Result |
| --- | --- |
| Frames | 194 in 10.0 s (19.4 FPS) |
| Per frame (12 reports) | median 52.0 ms, max 56.0 ms |
| Per SET_REPORT | median 4.0 ms, max 8.0 ms (≈2,300 reports) |

No report showed the ~40 ms extra latency of the configuration `0x0d` erase;
the frame rate is limited by control-transfer round trips, not by storage.
That is strong evidence, not proof, that LampArray updates are not written to
flash each time; see the power-cycle check below. While the cable is connected
the dongle cannot reach the keyboard, so the stored block cannot be read back
through it during the test.

Lamp attributes contain firmware errors, so `LAMP_KEYS` in
`retro87_lamparray.py` fixes the order from this probe and checks the bindings
the lamps do report: X positions of lamps 22–32 and 84–87 are 10× too large
and those of 88–89 100×, lamp 90 reports (0, 0), lamp 29 (backspace) reports the
backslash usage, and lamps 15 (pause), 79/80/82/83 (space bar) and 85/86
(A/B keys) have no binding.
