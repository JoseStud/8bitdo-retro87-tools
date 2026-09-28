#!/usr/bin/env python3
"""Example: your own lighting mode, streamed through OpenRGB's Direct mode.

A rainbow wave across the keys, using the same pieces as the tray's live
animation: retro87_openrgb talks to the OpenRGB SDK server, LampSink selects
Direct, maps Retro 87 key names to OpenRGB LEDs, and on close returns to the
stored effect that was showing (without saving anything).

    .venv/bin/python examples/direct_wave.py [seconds] [--takeover]

Needs the keyboard on its USB cable (Direct exists only there) and the OpenRGB
server (the retro87-openrgb unit). Direct never writes the keyboard's flash;
do not stream into Custom instead.

Sharing Direct: while it runs, the example asks the Retro 87 tray service to
pause its live animation (D-Bus PauseLive, renewed every few seconds; the tray
resumes by itself if this program dies). If some other client already has the
keyboard in Direct, it stops with an error; --takeover draws anyway.
"""
import colorsys
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import retro87_openrgb as openrgb
from retro87_layout import keyboard_layout

FPS = 20        # a full frame takes about 50 ms over USB
PAUSE, RENEW = 15, 5    # seconds: tray pause lease and how often to renew it


def tray(method, *args):
    """Call the Retro 87 tray service; silently does nothing if it is not running."""
    subprocess.run(["busctl", "--user", "call", "io.github.JoseStud.Retro87", "/io/github/JoseStud/Retro87",
                    "io.github.JoseStud.Retro87", method] + (["s" * len(args), *args] if args else []),
                   capture_output=True, timeout=5)


def frame(t, keys):
    """{key name: '#rrggbb'} for time t. Replace this with your own mode."""
    width = max(k["x"] + k["units"] for k in keys)
    colors = {}
    for key in keys:
        hue = ((key["x"] + key["units"] / 2) / width + t / 4) % 1
        r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
        colors[key["key"]] = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
    return colors


def main(seconds, takeover=False):
    controller = openrgb.Controller(openrgb.Client(name="Retro 87 example"))
    state = controller.refresh()
    if not state["connected"]:
        sys.exit(state["error"])
    lamps = openrgb.LampSink(controller)
    lamps.takeover = takeover
    if not lamps.available():
        sys.exit("Direct mode needs the keyboard's USB cable.")
    keys = keyboard_layout()
    tray("PauseLive", str(PAUSE))   # the tray hands the lighting back before this returns
    controller.refresh()            # so re-read the devices: Direct is free now
    renewed = start = time.monotonic()
    try:
        while (now := time.monotonic() - start) < seconds:
            lamps.set_leds(frame(now, keys))
            if time.monotonic() - renewed > RENEW:
                tray("PauseLive", str(PAUSE))
                renewed = time.monotonic()
            time.sleep(max(0, 1 / FPS - (time.monotonic() - start - now)))
    except RuntimeError as exc:
        sys.exit(str(exc))
    finally:
        lamps.close()   # back to the stored effect
        controller.client.close()
        tray("ResumeLive")


if __name__ == "__main__":
    numbers = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(float(numbers[0]) if numbers else 10, takeover="--takeover" in sys.argv)
