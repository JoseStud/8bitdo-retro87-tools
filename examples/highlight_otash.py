#!/usr/bin/env python3
"""Example: light only the O, T, A, S, H keys, everything else off.

Uses OpenRGB's Direct mode (retro87_openrgb.LampSink), the same runtime
per-key path as direct_wave.py, so nothing is written to the keyboard's
flash — closing this program (or Ctrl+C) hands the lighting straight back
to whatever stored effect was showing.

    .venv/bin/python examples/highlight_otash.py [seconds] [--color=#rrggbb] [--takeover]

Needs the keyboard on its USB cable (Direct exists only there) and the
OpenRGB server (the retro87-openrgb unit).
"""
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import retro87_openrgb as openrgb
from retro87_core import LED_KEYS

PAUSE, RENEW = 15, 5    # seconds: tray pause lease and how often to renew it
HIGHLIGHT_KEYS = ("o", "t", "a", "s", "h")


def tray(method, *args):
    """Call the Retro 87 tray service; silently does nothing if it is not running."""
    subprocess.run(["busctl", "--user", "call", "io.github.JoseStud.Retro87", "/io/github/JoseStud/Retro87",
                    "io.github.JoseStud.Retro87", method] + (["s" * len(args), *args] if args else []),
                   capture_output=True, timeout=5)


def frame(color):
    """{key name: '#rrggbb'}: O, T, A, S, H lit, every other key off."""
    colors = {key: "#000000" for key in LED_KEYS}
    colors.update({key: color for key in HIGHLIGHT_KEYS})
    return colors


def main(seconds, color="#ff0000", takeover=False):
    controller = openrgb.Controller(openrgb.Client(name="Retro 87 example"))
    state = controller.refresh()
    if not state["connected"]:
        sys.exit(state["error"])
    lamps = openrgb.LampSink(controller)
    lamps.takeover = takeover
    if not lamps.available():
        sys.exit("Direct mode needs the keyboard's USB cable.")
    tray("PauseLive", str(PAUSE))   # the tray hands the lighting back before this returns
    controller.refresh()            # so re-read the devices: Direct is free now
    colors = frame(color)
    renewed = start = time.monotonic()
    try:
        lamps.set_leds(colors)
        while time.monotonic() - start < seconds:
            if time.monotonic() - renewed > RENEW:
                tray("PauseLive", str(PAUSE))
                lamps.set_leds(colors)   # in case Direct had to be re-selected
                renewed = time.monotonic()
            time.sleep(1)
    except RuntimeError as exc:
        sys.exit(str(exc))
    finally:
        lamps.close()   # back to the stored effect
        controller.client.close()
        tray("ResumeLive")


if __name__ == "__main__":
    numbers = [a for a in sys.argv[1:] if not a.startswith("--")]
    color = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--color=")), "#ff0000")
    main(float(numbers[0]) if numbers else 10, color=color, takeover="--takeover" in sys.argv)
