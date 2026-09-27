# Retro 87 controls for Linux

Native Linux desktop app and dependency-free Python CLI for the
**8BitDo Retro 87 Mechanical Keyboard – Mecha BREAK: Panther**, over its 2.4 GHz
dongle (`2dc8:202e`, USB name `8BitDo Retro 87 Adapter X`). The protocol was
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

Not yet available: hardware macros, mouse/media/modifier-combination
assignments, sleep settings and firmware updates. Key remapping and sound-level
writes are decoded from the vendor app and covered by tests, but have not been
checked on hardware. Only the wireless dongle is supported (no Bluetooth or
wired USB), and only this model.

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

Requires Linux, Python 3.9+, and read/write access to the dongle's
`/dev/hidraw*` node for your user. Never run the tools as root.

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
./install-kde.sh                  # asks for sudo once, for the keyboard backlight
./install-kde.sh --no-backlight   # tray widget only, no root
./install-kde.sh --uninstall
```

- **Tray widget "Retro 87 Lighting"**: effect, brightness, speed, colours and a
  per-key on/off switch. Enable it under Configure System Tray → Entries. Its
  settings button opens the full app.
- **Keyboard backlight**: the keyboard appears in Plasma's Brightness applet
  and responds to the keyboard-brightness keys (5 steps). The slider sets the
  current preset's brightness, or the per-key brightness in per-key mode.

Both use a user service, `retro87_service.py` (`systemctl --user status retro87`,
log in `journalctl --user -u retro87`). It opens the dongle only for each
change, reads it first, writes the changed bytes, verifies them, and saves one
backup per session before its first write. The D-Bus API
(`io.github.JoseStud.Retro87`) is described at the top of the file.

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
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest test_retro87 test_model test_gui test_service   # 63 tests, no hardware
```

The tests cover packet encoding, acknowledgment/readback handling, every
codec, the LED layout and write sequence, stale baselines, partial-write
failures, and headless GUI flows with real clicks. All of them run against
mocks or an in-memory simulator.

## Documentation

- [PROTOCOL.md](PROTOCOL.md): the complete protocol and hardware findings.
- [research/README.md](research/README.md): reproducible vendor analysis and the
  hardware test log.
- [GUI_IMPLEMENTATION.md](GUI_IMPLEMENTATION.md): GUI status and remaining work.

The tools contain independently written code and numeric protocol tables. They
do not include or redistribute any vendor binaries or artwork.

## License

MIT; see [LICENSE](LICENSE).
