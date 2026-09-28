# OpenRGB integration

OpenRGB is the only program that opens the keyboard. It runs as a local SDK
server; the Plasma tray service and the OpenRGB GUI are both clients of it.
This needs an OpenRGB build with the Retro 87 support: the fork
[JoseStud/OpenRGB-8BitDo-Retro87](https://github.com/JoseStud/OpenRGB-8BitDo-Retro87)
publishes one automatically, or build it from
[openrgb/retro87-openrgb.patch](openrgb/retro87-openrgb.patch).

```text
 Plasma tray widget ──D-Bus──▶ retro87_service.py ──┐
 Plasma brightness keys ─UPower─▶ (retro87 unit)    │  OpenRGB SDK, protocol 4
 Wallpaper / display capture ──────────▶            │  127.0.0.1:6742
                                                    ▼
 OpenRGB GUI ─────────────────────────────▶ openrgb --server (retro87-openrgb unit)
                                                    │
                        ┌───────────────────────────┴──────────────────────────┐
                        ▼                                                      ▼
      configuration interface 2 (hidraw)                     HID LampArray interface 3
      2.4 GHz dongle 2dc8:202e or cable 2dc8:2028            cable 2dc8:2028 only (libusb)
      stored effects and per-key picture, saved              Direct: runtime colours, never saved
```

With `./install-kde.sh --direct` the service instead opens the keyboard itself,
without OpenRGB (the behaviour of earlier versions, including per-session
backups). The desktop app (`run-gui`) and the CLI always open it directly.

## Setup

### Option 1: the fork's release

[OpenRGB-8BitDo-Retro87](https://github.com/JoseStud/OpenRGB-8BitDo-Retro87)
follows upstream OpenRGB. A daily GitHub Actions workflow applies the patch to
upstream `master`, builds a Linux AppImage in upstream's own CI container, and
publishes it as a release when upstream or the patch changed; if the patch
stops applying or the build fails it opens an issue instead. Its `retro87`
branch holds the patched source. Download the latest
`OpenRGB-8BitDo-Retro87-x86_64.AppImage`, check it against its `.sha256`, make
it executable and install with it:

```sh
chmod +x ~/Applications/OpenRGB-8BitDo-Retro87-x86_64.AppImage
OPENRGB=~/Applications/OpenRGB-8BitDo-Retro87-x86_64.AppImage ./install-kde.sh
```

The fork's `patches/` is the maintained copy of the patch; when it changes,
update [openrgb/retro87-openrgb.patch](openrgb/retro87-openrgb.patch) here too.

### Option 2: build it yourself

Build OpenRGB with the patch. It was made against OpenRGB commit `d008deb`
and also applies to `c1784ca` (upstream `master` on 2026-09-28):

```sh
git clone https://gitlab.com/CalcProgrammer1/OpenRGB.git ~/OpenRGB
cd ~/OpenRGB
git checkout d008deb
git apply /path/to/8bitdo-retro87-tools/openrgb/retro87-openrgb.patch
mkdir -p build && cd build
qmake6 ../OpenRGB.pro
make -j"$(nproc)"
```

Then install the Plasma integration, pointing it at that binary (or put
`openrgb` on `PATH`). Either way:

```sh
OPENRGB=~/OpenRGB/build/openrgb ./install-kde.sh
```

The installer adds two user units that start with each Plasma login:

| Unit | Runs | Log |
| --- | --- | --- |
| `retro87-openrgb` | `openrgb --server --server-host 127.0.0.1 --noautoconnect` | `journalctl --user -u retro87-openrgb` |
| `retro87` | `retro87_service.py` (tray, backlight, wallpaper sync), ordered after it | `journalctl --user -u retro87` |

The udev rule from `install-kde.sh` (`/etc/udev/rules.d/70-retro87-backlight.rules`)
gives the logged-in user access to the wired keyboard's hidraw and USB nodes,
which OpenRGB needs for the cable. The server uses the normal OpenRGB
configuration directory, so profiles and settings are shared with the GUI.

Check it:

```sh
systemctl --user status retro87-openrgb retro87
~/OpenRGB/build/openrgb -ld   # connects to the running server; lists the keyboard
```

Started while the server runs, the OpenRGB GUI (`~/OpenRGB/build/openrgb`)
connects to it instead of detecting devices, so it can be used alongside the
tray.

## The keyboard in OpenRGB

One device, **8BitDo Retro 87 Mecha BREAK** (description
`8BitDo Retro 87 Keyboard Device (USB cable)` or `(2.4 GHz dongle)`), with an
87-key ANSI TKL layout. The A and B keys to the right of Right Alt are
`Key: A (Super button)` and `Key: B (Super button)`. The space bar is one key
in OpenRGB and lights all five of its LEDs.

| Mode | Available | Parameters | Saved on the keyboard |
| --- | --- | --- | --- |
| Direct | USB cable only | Per-key colours | Never |
| Custom | Always | Per-key colours, brightness | Yes: every update erases and rewrites flash |
| Static | Always | Colour, brightness | Yes |
| Breathing | Always | Colour, brightness, speed | Yes |
| Spectrum Cycle | Always | Brightness, speed | Yes |
| Rainbow Wave | Always | Brightness, speed | Yes |
| Ripple | Always | Colour, brightness, speed | Yes |
| Resonance | Always | Background and highlight colours, brightness, speed | Yes |
| Starlight | Always | Background and star colours, brightness, speed | Yes |
| Off | Always | | Yes |

- **Direct** takes the lighting over through the keyboard's HID LampArray
  interface (Windows Dynamic Lighting) and is the only mode meant for
  per-frame updates. The 2.4 GHz dongle has no LampArray
  ([research/storage-wear.md](research/storage-wear.md)).
- **Leaving Direct** gives the lighting back to the keyboard. Returning to the
  mode that was active before Direct, with unchanged settings, saves nothing;
  any other choice is stored as usual.
- **Custom and the effects** use the configuration interface. Each Custom
  write runs the keyboard's `0x0d` prepare step, which was shown on hardware
  to erase flash. Use Custom for occasional pictures, never for animation;
  see [Flash-wear protection](#flash-wear-protection).
- Stored brightness, speed and colours apply only while the keyboard's
  profile is active (Profile button); see the main README.

When the cable is plugged in, the dongle can no longer reach the keyboard.
OpenRGB then uses the cable's configuration interface and skips the dongle
(logged as `Keyboard not reachable through the dongle ... not added`). After
plugging or unplugging the cable, have OpenRGB re-detect (*Rescan devices* in
the GUI, or `systemctl --user restart retro87-openrgb`); the tray follows the
new device list on its own.

## Flash-wear protection

Everything except Direct is saved on the keyboard, and every per-key (Custom)
save erases flash ([research/storage-wear.md](research/storage-wear.md)). The
OpenRGB device protects the keyboard from any client, including OpenRGB's own
GUI, whose brightness and speed sliders send a mode update for every step
while dragged:

- **Coalesced saves.** Saved writes go through one background writer: the
  first change is written at once, later ones at most once per second, and
  only the latest pending request is kept. Checked on hardware: 61 brightness
  updates in 1.2 s in Custom mode produced 3 saves (first, one intermediate,
  final value), instead of 61 per-key rewrites.
- **Unchanged writes are skipped.** Effect settings are compared with the
  cached profile bytes (the existing `WriteProfile` check, updated after each
  verified write). The per-key block is compared with the last block read
  from or written to the keyboard; identical Custom saves are not rewritten
  (checked on hardware: repeating the stored Custom settings and colours
  logged `Per-key block unchanged; not rewritten`).
- **Direct is never saved**, and leaving it for the unchanged previous effect
  saves nothing.
- A change still pending when OpenRGB exits is written before it closes.

OpenRGB's GUI already requires *Apply colors* for per-key colours in modes
that save, so colour-wheel drags do not stream to Custom.

On the tray side, *Picture on keys* writes at most once per wallpaper change
and every 10 seconds, and a re-apply after reconnecting to OpenRGB is skipped
by the device when the picture is unchanged. Live animation uses Direct. The
flash-wearing fallback of streaming live frames into Custom over the dongle
exists only with `--experimental-live`, which the installer does not set; the
per-second coalescing would still let it save about 3,600 times an hour.

Saves are logged at debug level (`--loglevel debug`, in OpenRGB's log files):
`Saving mode ...`, `Writing per-key block`, `Per-key block unchanged; not rewritten`.

### How long the flash lasts

Only per-key (Custom) saves are proven to erase flash; unchanged pictures are
now skipped. The keyboard's flash endurance and wear levelling are unknown.
The estimate below assumes about 100,000 erase cycles per sector, typical for
the NOR flash in Telink microcontrollers, and no wear levelling (every save
erases the same sector):

| Use | Erases per day | Time to 100,000 |
| --- | --- | --- |
| Wallpaper changed about 5 times a day (*Picture on keys*) | 5 | about 55 years |
| Busiest logged day (27 writes, many from service restarts that are now skipped) | 27 | about 10 years |
| Wallpaper slideshow every 30 minutes | 48 | about 5.7 years |
| Wallpaper slideshow every 10 minutes | 144 | about 1.9 years |
| Wallpaper changing every 10 seconds (the tray's limit) | 8,640 | about 12 days |
| A client streaming into Custom (OpenRGB's one save per second) | 86,400 | about 28 hours |
| The old configuration-path live mode over the dongle (2 frames per second) | 172,800 | about 14 hours |

If the real endurance is 10,000 cycles, divide the times by 10; wear
levelling would extend them. Normal wallpaper matching is not a concern, a
fast slideshow is, and streaming into Custom never is acceptable: animations
must use Direct.

### Automatic profiles

No OpenRGB profile loads automatically on this setup (startup, resume,
suspend and exit profiles are disabled, and there are no saved profiles or
plugins). If you enable one, loading an unchanged profile costs nothing, but
a profile that changes the keyboard's effect saves on every load.

## The tray service over OpenRGB

`retro87_openrgb.py` is a standard-library SDK client. It requests protocol
version 4, where devices are addressed by index and the server sends no
acknowledgements, and uses only these packets:

| Packet | ID | Use |
| --- | --- | --- |
| `SET_CLIENT_NAME` | 50 | "Retro 87 tools" |
| `REQUEST_PROTOCOL_VERSION` | 40 | Negotiate version 4 |
| `REQUEST_CONTROLLER_COUNT` / `_DATA` | 0 / 1 | Device list, modes, LED names, colours |
| `RGBCONTROLLER_UPDATEMODE` | 1101 | Presets, brightness, speed, colours, Direct in and out |
| `RGBCONTROLLER_UPDATELEDS` | 1050 | Per-key picture (Custom) and live frames (Direct) |
| `DEVICE_LIST_UPDATED` | 100 | Received: re-read devices (cable plugged in, detection finished) |

Tray settings map onto the OpenRGB device's modes:

| Tray | OpenRGB |
| --- | --- |
| Preset `solid`, `breathing`, `cycle`, `color-ripple`, `ripple`, `resonance`, `starlight`, `off` | Static, Breathing, Spectrum Cycle, Rainbow Wave, Ripple, Resonance, Starlight, Off |
| Per-key on / off | Custom / the last preset shown |
| Brightness 0–100 | Mode brightness 0–255 |
| Speed 1 (slow) – 10 (fast) | Mode speed `11 − speed` (keyboard value 10 slowest, 1 fastest) |
| Colour / highlight | Mode colour 1 / 2 |
| *Picture on keys* | Custom colours, then Custom mode (one saved write per wallpaper change, at most every 10 s) |
| *Live animation (USB)* / full-display mirror | Direct, up to 10 frames per second |

During live animation the tray keeps showing the stored effect Direct will
return to. Brightness changes (tray slider, Plasma keyboard-brightness keys)
then only dim the streamed colours and are not saved; other manual changes
stop live mode first. Stopping live mode returns to that stored effect.

Every 5 seconds the service reads pending notifications from the server. When
the device list changed it re-reads it, logs the connection, and once the
keyboard appears re-applies the wallpaper colours. This covers OpenRGB still
detecting when the service starts.

## Writing your own modes

Any OpenRGB SDK client can drive the keyboard: the OpenRGB GUI and CLI
(`openrgb --client 127.0.0.1:6742 ...`), libraries such as `openrgb-python`,
effect plugins, or your own code. They all see the same device and modes as
the tray. The server listens on `127.0.0.1` only; the SDK has no
authentication, so keep it local.

From Python, `retro87_openrgb.py` offers three layers:

| Layer | Use it for |
| --- | --- |
| `Client` | Raw SDK access: `devices()`, `update_mode(device, index, mode)`, `update_leds(device, colors)` |
| `Controller` | Tray-style settings: `set("preset", "breathing")`, `set("brightness", "40")`, `set("color", "#ff8000")`, and `set_leds({...})`, which **saves** a per-key picture to Custom |
| `LampSink(controller)` | Streaming: `set_leds({"esc": "#ff0000", ...})` selects Direct and maps Retro 87 key names (`retro87_core.LED_KEYS`) to OpenRGB LEDs; `close()` returns to the stored effect without saving |

[examples/direct_wave.py](examples/direct_wave.py) is a complete mode: a
rainbow wave across the keys at 20 frames per second. Replace its
`frame(t, keys)` function, which receives the time and every key's layout
position from `retro87_layout.keyboard_layout()` and returns
`{key name: "#rrggbb"}`:

```sh
.venv/bin/python examples/direct_wave.py 10   # seconds
```

Checked on hardware: it streamed through the running server and afterwards
the device was back on Custom with nothing saved.

Rules for new modes:

- **Animate with Direct** (`LampSink`, or select the *Direct* mode in another
  client). Never stream into Custom or change stored effects per frame;
  see [Flash-wear protection](#flash-wear-protection).
- **One animator at a time.** Clients share the device; see
  [Sharing Direct with the tray](#sharing-direct-with-the-tray).
- **Hand the lighting back.** Call `close()` (or select a stored effect in
  other clients) when done; otherwise the keys keep the last Direct frame
  until OpenRGB exits or the keyboard is power-cycled.
- Direct needs the USB cable. A full frame takes about 50 ms over USB, so
  about 19 frames per second is the ceiling.

To make a mode part of the tray instead, feed its colours to the service's
`LampSink` the way `retro87_live.LiveMirror` does for wallpaper frames.

### Sharing Direct with the tray

Two clients streaming Direct at once overwrite each other's frames. Three
rules prevent that:

1. **Ask the tray to pause.** The tray service's D-Bus method
   `PauseLive(s seconds)` (at most 300) stops its live animation and hands the
   lighting back to the keyboard before it returns. The pause is a lease:
   renew it while your mode runs, and the tray resumes by itself when it runs
   out, so a program that crashes cannot block live mode for longer than one
   lease. `ResumeLive()` ends it early. The status field
   `wallpaperLivePaused` shows the seconds left.

   ```sh
   busctl --user call io.github.JoseStud.Retro87 /io/github/JoseStud/Retro87 \
       io.github.JoseStud.Retro87 PauseLive s 15
   ```

2. **Do not take Direct from someone else.** Before `LampSink` switches to
   Direct it checks the device: if the keyboard is already in Direct and it
   was not this sink that selected it, it raises `Direct mode is in use by
   another OpenRGB client` instead of drawing. The tray obeys the same rule, so
   an app streaming Direct is not fought over; live animation then stops with
   that message. A sink that loses and re-finds the device (for example after a
   device-list refresh) keeps its own Direct.
3. **An explicit choice takes over.** Selecting *Live animation* in the tray
   takes Direct once even if another client left it selected (for example
   after crashing without handing back). Scripts can do the same deliberately
   with `LampSink.takeover = True` (`--takeover` in the example).

`examples/direct_wave.py` follows all three: it pauses the tray, re-reads the
devices (the pause freed Direct), renews the pause every 5 seconds, and calls
`ResumeLive` when done. Checked on hardware with the tray's live animation
running: the tray paused (lease shown counting down), the example streamed for
its full run, and afterwards the tray resumed and took Direct back without an
error.

Clients other than the tray cannot see who holds Direct: the SDK has no
ownership or locking. Third-party apps that stream Direct without pausing the
tray will still conflict with its live animation; turn one of them off.

## Changes in the OpenRGB patch

**HID LampArray controller** (`Controllers/HIDLampArrayController`):

- Linux: LampArray interfaces without an interrupt-IN endpoint are not bound
  by `usbhid`, so they have no hidraw node and hidapi cannot see them. A
  libusb detector (`DetectHIDLampArrayUSBControllers`) finds unbound HID
  interfaces with only OUT endpoints, claims them and checks the report
  descriptor for a LampArray application collection (usage page `0x59`,
  usage `0x01`). Interfaces with a kernel driver are left to the hidapi path.
  An interface already claimed elsewhere is logged
  (`... is in use by another program; not added`).
- The controller talks to either hidapi or a libusb handle: GET/SET_REPORT
  feature control transfers and the HID report descriptor request, with the
  report ID in the first byte as with hidapi.
- The report-ID table is zeroed before the descriptor is parsed; previously
  the "report missing" check could read uninitialised memory.
- `OpenHIDLampArrayUSBControllers(vid, pid, exclude)` is shared with the 8BitDo
  controller; the generic detector excludes `2dc8:2028`.
- Retro 87 lamp fix-ups (`2dc8:2028`, 91 lamps), for the generic path: the
  firmware reports X positions 10× or 100× too large (lamps 22–32, 84–89),
  the right arrow at (0, 0), backspace with the backslash usage, and no usage
  for pause, four of the five space-bar lamps and the A/B keys.

**8BitDo Retro 87 controller** (`Controllers/8BitDoController`):

- Detects the configuration interface over the cable (`2dc8:2028`,
  interface 2) as well as the dongle (`2dc8:202e`); the description names the
  connection.
- A dongle whose keyboard does not answer (switched off, or on the cable) is
  not added, instead of appearing as a device whose writes all fail.
- Direct mode over the cable: the detector opens the keyboard's LampArray
  interface and hands it to the device. `retro87_lamp_ids` maps each
  configuration LED index to its lamp ID (91 entries, generated from the
  verified key tables in `retro87_core.py` and `retro87_lamparray.py`); the
  space-bar LED fans out to lamps 79–83. A frame is 12 multi-update reports
  of up to 8 lamps, the last marked complete. Entering Direct turns the
  LampArray's autonomous mode off and remembers the previous mode, its
  settings and colours; leaving it turns autonomous mode back on, and skips
  the save when returning to that mode unchanged. The destructor also hands
  the lighting back.
- Flash-wear protection (above): saved writes run on a background thread
  that coalesces them to at most one per second; the controller caches the
  per-key block (`ReadCustom`/`SetCustom`) and skips identical writes; saves
  are logged at debug level.

## Limitations

- Direct and the merged device use the Linux libusb path. On Windows or macOS
  the LampArray would still appear as a separate generic device, and the
  8BitDo device would have no Direct mode.
- With two wired Retro 87 keyboards connected, the device takes the first
  LampArray found, which may belong to the other keyboard.
- The OpenRGB path makes no configuration backups; `--direct` does.
- OpenRGB's Custom mode has no speed, so the tray hides the speed slider in
  per-key mode.
- The tray shows OpenRGB-side changes when its popup opens (it refreshes
  then), not instantly.
- The desktop app and CLI open the keyboard directly. They work while OpenRGB
  runs, but avoid changing settings in both at the same moment.

## Troubleshooting

| Message or symptom | Cause and fix |
| --- | --- |
| `OpenRGB is not running` | Start it: `systemctl --user start retro87-openrgb`. |
| `OpenRGB does not see the Retro 87` | Switch the keyboard on (dongle) or connect the cable; rescan in the OpenRGB GUI if needed. |
| No *Live animation (USB)* option, or `Live colours need the keyboard's USB cable` | Direct exists only over the cable. |
| `... interface 3 is in use by another program; not added` (OpenRGB log) | Another program holds the LampArray, e.g. a service installed with `--direct` streaming live mode. |
| Keyboard missing and permission errors in the OpenRGB log | Re-run `./install-kde.sh` (with sudo) to install the udev rule, then replug. |
| Keys stay on live colours after OpenRGB was killed | Select any mode in OpenRGB, or power-cycle the keyboard. |

## Tests

`test_openrgb.py` runs the client and service backend against a fake OpenRGB
server that encodes devices in the protocol-4 layout and records mode and LED
updates: status mapping, presets, speed and colour, per-key on/off, brightness
scaling, the Custom picture, Direct live frames with dimming and return to the
stored effect, the dongle without Direct, device-list changes, and an
unreachable server.

Hardware checks (2026-09-28, wired, Linux): one OpenRGB device with Direct and
all effects; live animation through the running service at about 8 frames per
second; tray brightness during live mode dimmed only the stream; after
stopping, the device was back on Custom at the stored brightness; a second
OpenRGB instance connected to the server and listed the keyboard without
detecting. That leaving Direct writes nothing to the keyboard follows from the
code and was not measured on hardware.

## Upstream status

The patch is published in the unofficial fork above and is not part of
OpenRGB. OpenRGB's
CONTRIBUTING.md does not permit AI-generated submissions as a general rule
and forbids AI authorship credits in commits. This code was written with an
AI assistant, so it should not be submitted upstream as-is; a submitter would
need to rework and fully vet it. Notes for that are in
[research/openrgb-merge-request.md](research/openrgb-merge-request.md).
