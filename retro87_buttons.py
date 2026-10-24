"""Focused Super Button identification. No profile writes or keyboard logging.

Run with .venv/bin/python retro87_buttons.py. Report mode is temporary and
restored on Stop, timeout, focus loss, failure, and normal window close.
"""
import os
import select
import sys
import time

import retro87_core as protocol

# XboxMacroView.InitMapping, Button_Down and readKey in vendor V1.35.
PORTS = {"A": ("k1", "k2"), "B": ("k4", "k3"),
         "X": ("k5", "k6"), "Y": ("k8", "k7")}
BUTTON_BITS = {f"k{i + 1}": (26 + (i + 2) // 8, 1 << ((i + 2) % 8)) for i in range(8)}


def extension_buttons(report):
    """Ignore all ordinary-key data and all non-input reports."""
    if len(report) != 64 or report[:4] != b"\x02\x04\x03\x09":
        return None
    return tuple(key for key, (offset, mask) in BUTTON_BITS.items() if report[offset] & mask)


def report_mode_packet(enabled):
    if type(enabled) is not bool:
        raise ValueError("Expected a boolean report mode")
    result = bytearray(protocol.packet(8))
    result[3] = int(enabled)  # Vendor ReportXbox argument is header byte 3.
    return bytes(result)


class ButtonMonitor:
    def __init__(self, device_factory=protocol.Keyboard):
        self.device_factory = device_factory
        self.device = None

    def start(self):
        if self.device is not None:
            raise RuntimeError("Identification is already running")
        device = self.device_factory(writable=False)
        device.__enter__()  # Existing device lock excludes other tools.
        self.device = device
        try:
            if os.write(device.fd, report_mode_packet(True)) != 64:
                raise OSError("Short report-mode request")
        except BaseException:
            self.stop()
            raise

    def poll(self):
        if self.device is None:
            return []
        states = []
        # Bound each UI tick even if reports are arriving continuously.
        for _ in range(64):
            if not select.select([self.device.fd], [], [], 0)[0]:
                break
            raw = os.read(self.device.fd, 64)
            if not raw:
                raise OSError("Keyboard disconnected")
            buttons = extension_buttons(raw)
            if buttons is not None:
                states.append(buttons)
        return states

    def stop(self):
        device, self.device = self.device, None
        if device is None:
            return
        try:
            if os.write(device.fd, report_mode_packet(False)) != 64:
                raise OSError("Could not restore normal report mode; reconnect the keyboard")
        finally:
            device.__exit__(None, None, None)


def main():
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

    app = QApplication(sys.argv)
    monitor = ButtonMonitor()

    class Window(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Identify Super Buttons · Retro 87 Tools")
            self.resize(560, 300)
            self.deadline = 0
            self.previous = ()
            layout = QVBoxLayout(self)
            intro = QLabel("Keep this window focused. Click Start, then press each external button.\n"
                           "Only extension buttons are shown; no keys are recorded.\n"
                           "Stops after 30 seconds or when this window loses focus.")
            intro.setWordWrap(True)
            layout.addWidget(intro)
            layout.addWidget(QLabel("Vendor port order: A: K1/K2 · B: K4/K3 · X: K5/K6 · Y: K8/K7"))
            self.status = QLabel("Ready. No keyboard settings will be changed.")
            self.status.setWordWrap(True)
            self.last = QLabel("Last detected: —")
            layout.addWidget(self.status)
            layout.addWidget(self.last)
            self.start_button = QPushButton("Start identification")
            self.start_button.clicked.connect(self.start)
            layout.addWidget(self.start_button)
            self.stop_button = QPushButton("Stop")
            self.stop_button.clicked.connect(self.stop)
            self.stop_button.setEnabled(False)
            layout.addWidget(self.stop_button)
            self.timer = QTimer(self)
            self.timer.setInterval(20)
            self.timer.timeout.connect(self.poll)
            app.applicationStateChanged.connect(self.focus_changed)

        def start(self):
            try:
                monitor.start()
            except (OSError, RuntimeError) as exc:
                self.status.setText(str(exc))
                return
            self.deadline = time.monotonic() + 30
            self.last.setText("Last detected: —")
            self.previous = ()
            self.status.setText("Listening for Super Buttons…")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.timer.start()

        def stop(self, message="Stopped. Normal report mode restored."):
            self.timer.stop()
            try:
                monitor.stop()
            except OSError as exc:
                message = f"Stopped, but restoring report mode failed: {exc}. Reconnect the keyboard."
            self.status.setText(message if isinstance(message, str) else "Stopped. Normal report mode restored.")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

        def poll(self):
            if time.monotonic() >= self.deadline:
                self.stop("Identification finished. Normal report mode restored.")
                return
            try:
                for keys in monitor.poll():
                    self.status.setText("Held: " + (", ".join(k.upper() for k in keys) or "none"))
                    if keys and keys != self.previous:
                        print("Super Buttons:", ", ".join(k.upper() for k in keys), flush=True)
                    self.previous = keys
                    if keys:
                        labels = [f"{key.upper()} (port {next(p for p, pair in PORTS.items() if key in pair)})" for key in keys]
                        self.last.setText("Last detected: " + ", ".join(labels))
            except (OSError, RuntimeError) as exc:
                self.stop(f"Identification stopped: {exc}")

        def focus_changed(self, state):
            if state != Qt.ApplicationActive and monitor.device is not None:
                self.stop("Stopped on focus loss. Normal report mode restored.")

        def closeEvent(self, event):
            self.stop()
            event.accept()

    window = Window()
    window.show()
    try:
        return app.exec()
    finally:
        monitor.stop()


if __name__ == "__main__":
    sys.exit(main())
