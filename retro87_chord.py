"""Change the waywallen wallpaper when both Super Buttons are held together.

Uses the temporary report mode of retro87_buttons.py: no profile writes and no
keyboard logging. The device lock is held while running, so stop this (or its
unit, retro87-chord) before using the GUI or the identification window.
Default buttons K7+K8, the pair of the first accessory jack (see research/README.md).
"""
import argparse
import signal
import subprocess
import sys
import time

import retro87_buttons as buttons

WAYWALLEN = ("org.waywallen.waywallen.Daemon", "/org/waywallen/waywallen/Daemon",
             "org.waywallen.waywallen.Daemon1")


def next_wallpaper(method="Next"):
    subprocess.run(["busctl", "--user", "call", *WAYWALLEN, method], check=True,
                   stdout=subprocess.DEVNULL, timeout=5)


class Chord:
    """Fires once per press of all wanted buttons; re-arms after they are all released."""

    def __init__(self, wanted, action):
        self.wanted = frozenset(wanted)
        self.action = action
        self.armed = True

    def update(self, held):
        held = set(held)
        if self.wanted <= held:
            if self.armed:
                self.armed = False
                self.action()
        elif not held & self.wanted:
            self.armed = True


def run(wanted, action, monitor_factory=buttons.ButtonMonitor, sleep=time.sleep, retry=5):
    chord = Chord(wanted, action)
    stopping = []
    signal.signal(signal.SIGTERM, lambda *_: stopping.append(1))
    while not stopping:
        monitor = monitor_factory()
        try:
            monitor.start()
            print("Watching for", "+".join(sorted(wanted)).upper(), flush=True)
            while not stopping:
                for held in monitor.poll():
                    chord.update(held)
                sleep(0.02)
        except KeyboardInterrupt:
            break
        except (OSError, RuntimeError) as exc:
            print("Waiting for keyboard:", exc, file=sys.stderr, flush=True)
        finally:
            try:
                monitor.stop()
            except OSError as exc:
                print("Could not restore report mode:", exc, file=sys.stderr, flush=True)
        for _ in range(retry * 10):
            if stopping:
                break
            sleep(0.1)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--keys", default="k7,k8", help="buttons to hold together (default k7,k8)")
    parser.add_argument("--previous", action="store_true", help="go to the previous wallpaper instead")
    args = parser.parse_args()
    wanted = [key.strip().lower() for key in args.keys.split(",")]
    if len(wanted) < 2 or any(key not in buttons.BUTTON_BITS for key in wanted):
        parser.error("--keys takes two or more of k1..k8")

    def action():
        try:
            next_wallpaper("Previous" if args.previous else "Next")
        except (OSError, subprocess.SubprocessError) as exc:
            print("Wallpaper change failed:", exc, file=sys.stderr, flush=True)

    return run(wanted, action)


if __name__ == "__main__":
    sys.exit(main())
