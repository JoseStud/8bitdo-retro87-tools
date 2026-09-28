# Retro 87 controls for Linux

Native Linux desktop app and dependency-free Python CLI for the
**8BitDo Retro 87 Mechanical Keyboard – Mecha BREAK: Panther**, over its 2.4 GHz
dongle (`2dc8:202e`, USB name `8BitDo Retro 87 Adapter X`) or its USB cable
(`2dc8:2028`, `8BitDo Retro 87 Keyboard X`). The protocol was
recovered by static analysis of the official Ultimate Software V2 (Windows,
v1.35) and verified on hardware. Unofficial; not affiliated with 8BitDo.

What works on the keyboard (hardware-verified, 2026-09-27):

- **Profile setup** with the vendor's default profile image.
- **Built-in lighting presets**: selecting an effect (starlight, solid, cycle
  and breathing tested), and breathing's colour, brightness and speed. The
  other presets use the same encoding.
- **Per-key RGB lighting** for all 87 keys (91 LEDs), with static, breathing,
  starlight, freeze and off effects, brightness, speed and star count.
- Backup before every write, and verification by readback after it.
- **KDE Plasma**: a tray widget, the keyboard in Plasma's Brightness applet and
  brightness keys, and lighting that follows the
  [waywallen](https://github.com/waywallen/waywallen) wallpaper.

Not yet available: hardware macros, mouse/media/modifier-combination
assignments, sleep settings and firmware updates. Key remapping and sound-level
writes are decoded from the vendor app and covered by tests, but have not been
checked on hardware. The dongle and the USB cable are supported (not
Bluetooth), and only this model. Both expose the same configuration interface;
when the cable is plugged in the tools use it, because the dongle then no longer
reaches the keyboard.

## The one thing to know: activate the profile

The keyboard shows the lighting stored in its profile **only while the profile
is active**. When it is inactive, it uses its own onboard settings (the Fn
brightness/colour keys), and anything you write seems to have no effect.
For example, solid looked dark because its onboard brightness was zero.

1. Create a profile once (GUI: Profiles → Create profile, or
   `retro87.py profile-create Linux --apply`). A factory-fresh keyboard has
   none, and until one exists the Profile button changes nothing.
2. Press the keyboard's **Profile button** (the small button beside Pair and
   Fast key mapping) so its indicator lights. The app shows **active** next to
   the profile name. Pressing it again switches back to the onboard lighting.

Do not hold Pair + Fast key mapping + Profile together for 5 seconds: that is
the factory reset.

## Install

Requires Linux, Python 3.9+, and read/write access to the dongle's or wired
keyboard's `/dev/hidraw*` node for your user (`install-kde.sh` adds a udev rule
for the wired keyboard). Never run the tools as root.

```sh
git clone https://github.com/JoseStud/8bitdo-retro87-tools.git
cd 8bitdo-retro87-tools
python3 -m venv .venv
.venv/bin/pip install -r requirements-gui.txt   # PySide6, for the desktop app only
```

Optional desktop launcher:

```sh
sed "s|@DIR@|$PWD|g" retro87-tools.desktop > ~/.local/share/applications/retro87-tools.desktop
```

## Desktop app

```sh
./run-gui                              # reads the keyboard; Apply asks before writing
./run-gui --read-only                  # never writes
./run-gui --snapshot original-config.json   # offline, no device access
```

Pages: Keys (remapping), Macros (status only), Volume (device sound level),
Lighting (presets and the per-key editor) and Profiles (create/rename,
snapshots, restore). Edits are staged in memory. **Review changes** lists
every byte range; **Apply** re-reads the keyboard and refuses if it changed
since loading (the Profile and lighting keys also change it). It then writes a
backup to `~/.local/share/retro87-tools/backups`, writes, and verifies by
readback. After a failure it stops without retrying; restore from the backup.

**Per-key lighting** (Lighting page, lower section): click a key, Ctrl+click
to add more, enter `#RRGGBB`, then **Colour selected**. Choose an effect,
brightness, speed and star count, click **Stage per-key lighting**, then
Review and Apply. Staging switches the keyboard into per-key mode. Selecting a
built-in preset switches back.

## KDE Plasma integration

```sh
OPENRGB=/path/to/openrgb ./install-kde.sh   # asks for sudo once, for udev rules and the backlight
./install-kde.sh --no-backlight             # no root; keeps previously installed udev rules
./install-kde.sh --direct                   # without OpenRGB (see below)
./install-kde.sh --uninstall
```

After installing, everything starts with each Plasma login. Nothing needs to
be run by hand.

**OpenRGB is the only program that opens the keyboard** (details in
[OPENRGB.md](OPENRGB.md)). The installer runs
OpenRGB's SDK server as the user unit `retro87-openrgb` (localhost only), and
the tray service sends every change through it. The OpenRGB GUI can be used at
the same time: started while the server runs, it connects to it instead of
opening devices. This needs an OpenRGB build with the Retro 87 support (the
8BitDo controller, and the HID LampArray changes for the USB cable); the
binary comes from `$OPENRGB` or `PATH`. In OpenRGB the keyboard is one device,
**8BitDo Retro 87 Mecha BREAK**: the stored effects and the stored per-key
picture (*Custom*) work over the dongle or the cable and are saved on the
keyboard; over the cable it also has **Direct**, runtime per-key colours
through the keyboard's HID LampArray interface that are never saved. Selecting
any other mode gives the lighting back to the keyboard; returning to the
unchanged effect that was active before Direct saves nothing. Live animation
uses Direct, and brightness changes while it runs only dim the live colours. `--direct` installs the service without OpenRGB; it
then opens the keyboard itself, as earlier versions did. The desktop app and
CLI below always open the keyboard directly; avoid changing settings in them
and in OpenRGB at the same moment.

- **Tray widget "Retro 87 Lighting"** (keyboard icon): Match wallpaper,
  per-key on/off, effect, brightness, speed and colours. Its refresh button
  re-reads the keyboard; its settings button opens the full app. To show it:
  right-click the system tray arrow → Configure System Tray → Entries →
  Retro 87 Lighting → Always shown. If it is missing after an install or
  update, restart the shell with `systemctl --user restart plasma-plasmashell`.
- **Keyboard backlight**: the keyboard appears in Plasma's Brightness applet
  and responds to the keyboard-brightness keys (5 steps). The slider sets the
  current preset's brightness, or the per-key brightness in per-key mode.
- **Match wallpaper** (tray widget): follows the wallpaper playing in
  [waywallen](https://github.com/waywallen/waywallen) (including Wallpaper
  Engine scenes it plays) and updates whenever the wallpaper changes.
  *Colour* puts the wallpaper's main colour into the current effect (a dim
  background and accent highlight for Resonance/Starlight; effects without a
  colour switch to Solid). *Picture on keys* spreads the wallpaper over the
  keys as per-key colours. Colours come from waywallen's preview image for
  each wallpaper. The choice is remembered in
  `~/.config/retro87-tools/service.json`. Writes are limited to one per
  wallpaper change, at most every 10 seconds; watch them with
  `journalctl --user -u retro87 -f`.

  **Live animation** is available with the optional capture bridge below. It
  follows the rendered wallpaper, including video and scene motion, and needs
  the keyboard's **USB cable**: frames go to its HID LampArray (the Windows
  Dynamic Lighting interface) as runtime colours, up to 10 per second, and the
  keyboard returns to its own lighting when live mode stops. The 2.4 GHz dongle
  has no LampArray; there, each per-key write erases the keyboard's flash
  (hardware-proven, see the [storage wear assessment](research/storage-wear.md)),
  so that fallback needs `--experimental-live` and should not be used for
  continuous streaming.

Both use a user service, `retro87_service.py` (`systemctl --user status retro87`,
log in `journalctl --user -u retro87`). It sends each change to OpenRGB, which
saves effects and the per-key picture on the keyboard; this path makes no
backups. With `--direct` it instead opens the keyboard (cable or dongle) only for
each change, reads it first, writes the changed bytes, verifies them, and saves
one backup per session before its first write. The D-Bus API
(`io.github.JoseStud.Retro87`) is described at the top of the file.

### Live mirroring

Wallpaper capture uses `grabToImage` on Plasma's Waywallen surface. It captures
the animation itself, without application windows, desktop icons or panels.
Install the optional bridge with:

```sh
.venv/bin/python install-live-wallpaper.py
```

This copies the system Waywallen wallpaper to your user wallpaper directory and
adds the capture component. It refuses to overwrite an unmanaged user copy.
Log out and back in to load it. Re-run the installer after updating Waywallen;
the local copy otherwise shadows system updates. Remove it with
`.venv/bin/python install-live-wallpaper.py --uninstall`, then log in again.

Connect the keyboard with its USB cable. `install-kde.sh` (without
`--no-backlight`) installs the udev rule that gives your session access to the
LampArray interface; re-run it once after updating. Then choose **Live
animation (USB)** in Match wallpaper. Unplugging the cable stops live mode with
an error instead of falling back to flash writes.

Only to allow the flash-wearing 2.4 GHz fallback, run `systemctl --user edit retro87`
and add this override (replace the paths with your checkout's absolute paths):

```ini
[Service]
ExecStart=
ExecStart=/absolute/path/.venv/bin/python /absolute/path/retro87_service.py --experimental-live
```

Restart with `systemctl --user restart retro87`. From a terminal:

```sh
busctl --user call io.github.JoseStud.Retro87 /io/github/JoseStud/Retro87 io.github.JoseStud.Retro87 Set ss wallpaper live
```

The first screen requesting capture is selected; add `--wallpaper-screen DP-1`
to the service arguments to select a specific Qt screen name. Captures preserve
the screen aspect ratio and are centre-cropped to the keyboard layout. Frames
are at most 192 pixels on their longest edge, stored temporarily in a private
runtime directory, and removed after consumption. There is one capture in
flight, no frame queue, and identical mapped colours cause no keyboard access.
Locking pauses delivery; an unavailable lock service also pauses it. Any device
failure stops the stream until live mode is reselected. Manual preset/colour
changes stop live mode. Over USB, stopping returns the keyboard to its own
lighting; the 2.4 GHz fallback preserves brightness and leaves the last pattern.

### Full-display mirror (draft)

`retro87_display.py` samples the entire monitor, including applications and
windows. The entire frame maps to the keyboard, including its top and bottom
edges, without a centre crop. On Wayland, Qt's ScreenCast/PipeWire backend opens the desktop portal
screen picker; choose a monitor. This is independent of the Waywallen bridge.
The default only prints per-key colour JSON, with **no keyboard writes**:

```sh
.venv/bin/python retro87_display.py
```

With the keyboard on its USB cable (or the experimental option above), send it to the keyboard:

```sh
.venv/bin/python retro87_display.py --apply
```

Ctrl+C stops capture and disables display mirroring. Selecting a different
lighting mode also stops the runner when its next frame arrives. It shares the
wallpaper mode's frame limit (10/s over USB), lock checks and failure handling.
On X11, `--screen NAME` selects a monitor; Wayland selection is handled by the
portal. Full-display mode is never restored automatically at service startup.
This draft requires Qt Multimedia with the FFmpeg backend and a working
ScreenCast portal/PipeWire on Wayland. Native monitor capture and sustained
hardware output still require an interactive validation run.

How the backlight works: the root step loads the kernel's `uleds` module at
boot and adds a udev rule. The rule lets your session create a userspace LED
named `retro87::kbd_backlight`, which UPower reports as a keyboard backlight.
The service starts before PowerDevil, which only looks for keyboard
backlights at startup; on first install it restarts PowerDevil once.

## CLI

Every write command previews by default and only writes with `--apply`, which
first saves a backup under `backups/`.

```sh
python retro87.py status
python retro87.py list-keys                 # source/target/LED key names
python retro87.py backup my-backup.json

python retro87.py profile-create Linux --apply
python retro87.py rgb --mode breathing --color '#00aaff' --brightness 70 --speed 5 --apply
python retro87.py led --default '#0000ff' --key w=#ff0000 --key a=#ff0000 \
    --key s=#ff0000 --key d=#ff0000 --key space=#00ff00 --apply
python retro87.py led --effect off --apply
python retro87.py map capslock esc --apply
python retro87.py restore-profile original-config.json --apply
```

`led` options: `--effect static|breathing|starlight|freeze|off`,
`--brightness 0–100`, `--speed 1–10`, `--count 5–100` (starlight). `off`
darkens the keys (0% brightness). `freeze` is the vendor's "close" effect,
which holds the current frame.

Offline previews: `python retro87.py --snapshot original-config.json status`.

## Backups and limits

A snapshot holds the 1532-byte profile region and the 283-byte per-key LED
region. It is not a firmware image: macro storage is not captured.
`restore-profile` writes the profile region only. To put back per-key colours,
restore them with `led` or the GUI.

## Tests

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest test_retro87 test_model test_gui test_service test_wallpaper test_live test_lamparray test_openrgb   # no hardware
```

The tests cover packet encoding, acknowledgment/readback handling, every
codec, the LED layout and write sequence, stale baselines, partial-write
failures, and headless GUI flows with real clicks. All of them run against
mocks or an in-memory simulator.

## Documentation

- [PROTOCOL.md](PROTOCOL.md): the complete protocol and hardware findings.
- [OPENRGB.md](OPENRGB.md): OpenRGB as the single program driving the keyboard:
  setup, the OpenRGB device and its modes, flash-wear protection, the tray
  backend, the OpenRGB patch ([openrgb/retro87-openrgb.patch](openrgb/retro87-openrgb.patch)),
  a flash-endurance estimate, and how to write your own lighting modes
  ([examples/direct_wave.py](examples/direct_wave.py)).
- [research/README.md](research/README.md): reproducible vendor analysis and the
  hardware test log.
- [GUI_IMPLEMENTATION.md](GUI_IMPLEMENTATION.md): GUI status and remaining work.

The tools contain independently written code and numeric protocol tables. They
do not include or redistribute any vendor binaries or artwork.

## License

MIT; see [LICENSE](LICENSE).
