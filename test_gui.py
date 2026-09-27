"""Headless GUI tests. All device interactions use an in-memory simulator."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Qt, QUrl, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

import retro87_core as protocol
from retro87_gui import Controller
from retro87_model import Snapshot, SimulatedKeyboard

APP = QGuiApplication.instance() or QGuiApplication([])
QQuickStyle.setStyle("Basic")


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = Snapshot.load(protocol.ROOT / "original-config.json")
        self.factory = Mock(side_effect=AssertionError("No real device in GUI tests"))
        self.controller = Controller(self.snapshot, device_factory=self.factory)

    def tearDown(self):
        self.controller.pool.waitForDone()
        APP.processEvents()

    def wait(self):
        for _ in range(300):
            if not self.controller.busy:
                return
            QTest.qWait(10)
        self.fail("Background operation did not complete")

    @contextmanager
    def rendered(self, width=1200, height=800):
        """Real QML controls with a transport that rejects all hardware access."""
        messages = []
        previous = qInstallMessageHandler(lambda kind, context, message: messages.append(message))
        engine = QQmlApplicationEngine()
        self._qt_refs = []  # Keep Python wrappers for QML-owned popup footers alive.
        try:
            engine.setInitialProperties({"bridge": self.controller})
            engine.load(QUrl.fromLocalFile(str(protocol.ROOT / "qml/Main.qml")))
            self.assertTrue(engine.rootObjects(), messages)
            window = engine.rootObjects()[0]
            window.resize(width, height)
            QTest.qWait(50)
            yield window
            self.factory.assert_not_called()
            self.assertFalse(messages, "\n".join(messages))
        finally:
            self.controller.discard()
            if engine.rootObjects():
                engine.rootObjects()[0].close()
            del engine
            qInstallMessageHandler(previous)

    def item(self, window, name):
        item = window.findChild(QObject, name)
        if item is None:  # Repeater delegates are visual children, not QObject children.
            stack = [window.contentItem()]
            while stack and item is None:
                current = stack.pop()
                if current.objectName() == name:
                    item = current
                stack.extend(current.childItems())
        self.assertIsNotNone(item, name)
        return item

    def reveal(self, window, name):
        """Scroll the Lighting page so a control is inside the window."""
        item = self.item(window, name)
        flickable = self.item(window, "lightingScroll").property("contentItem")
        top = item.mapToItem(flickable.property("contentItem"), 0, 0).y()
        limit = max(0, flickable.property("contentHeight") - flickable.height())
        flickable.setProperty("contentY", min(limit, max(0, top - flickable.height() / 2)))
        QTest.qWait(30)
        return item

    def click(self, window, button):
        if isinstance(button, str):
            button = self.item(window, button)
        self.assertTrue(button.isVisible())
        self.assertTrue(button.isEnabled())
        point = button.mapToScene(button.boundingRect().center()).toPoint()
        self.assertTrue(window.contentItem().boundingRect().contains(point))
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(50)

    def dialog_button(self, window, dialog_name, text):
        footer = self.item(window, dialog_name).property("footer")
        self._qt_refs.append(footer)
        matches = [item for item in footer.findChildren(QQuickItem)
                   if item.property("text") == text and item.property("checkable") is not None]
        self.assertEqual(len(matches), 1, f"Dialog button {text}")
        return matches[0]

    def test_review_empty_state_mouse_and_keyboard(self):
        for width, height in [(1200, 800), (1000, 700)]:
            with self.subTest(size=(width, height)), self.rendered(width, height) as window:
                self.click(window, "reviewButton")
                self.assertTrue(self.item(window, "reviewDialog").property("opened"))
                self.assertIn("No changes have been staged", self.item(window, "reviewText").property("text"))
                self.click(window, self.dialog_button(window, "reviewDialog", "Close"))
                self.assertFalse(self.item(window, "reviewDialog").property("visible"))
                self.item(window, "reviewButton").forceActiveFocus()
                QTest.keyClick(window, Qt.Key_Space)
                QTest.qWait(50)
                self.assertTrue(self.item(window, "reviewDialog").property("opened"))
                QTest.keyClick(window, Qt.Key_Escape)
                QTest.qWait(50)
                self.assertFalse(self.item(window, "reviewDialog").property("visible"))
                self.assertFalse(self.controller.state["dirty"])

    def test_review_without_loaded_configuration(self):
        self.controller.draft = None
        with self.rendered() as window:
            self.click(window, "reviewButton")
            self.assertIn("No configuration is loaded", self.item(window, "reviewText").property("text"))
            self.assertFalse(self.item(window, "applyButton").isEnabled())

    def test_volume_stage_review_and_discard_by_click(self):
        with self.rendered(1000, 700) as window:
            window.setProperty("page", 2)
            self.item(window, "volumeLevel").setProperty("value", 4)
            self.assertFalse(self.controller.state["dirty"])
            self.click(window, "stageVolume")
            self.assertTrue(self.controller.state["dirty"])
            self.click(window, "reviewButton")
            text = self.item(window, "reviewText").property("text")
            self.assertIn("Device sound level: 4", text)
            self.assertIn("0x05c9: 02 → 04", text)
            self.click(window, self.dialog_button(window, "reviewDialog", "Close"))
            self.click(window, "discardButton")
            self.click(window, self.dialog_button(window, "discardDialog", "No"))
            self.assertTrue(self.controller.state["dirty"])
            self.click(window, "discardButton")
            self.click(window, self.dialog_button(window, "discardDialog", "Yes"))
            self.assertFalse(self.controller.state["dirty"])
            self.assertEqual(self.controller.draft.profile, self.snapshot.profile)
            self.click(window, "reviewButton")
            self.assertIn("No changes have been staged", self.item(window, "reviewText").property("text"))

    def test_lighting_stage_and_review_by_click(self):
        with self.rendered(1000, 700) as window:
            window.setProperty("page", 3)
            for index, mode in enumerate(["solid", "breathing", "off", "cycle", "color-ripple", "ripple", "resonance", "starlight"]):
                with self.subTest(mode=mode):
                    self.item(window, "effectPicker").setProperty("currentIndex", index)
                    self.item(window, "rgbColor").setProperty("text", "#123456")
                    QTest.qWait(20)
                    self.click(window, self.reveal(window, "stageRgb"))
                    self.assertFalse(self.controller.error)
                    self.assertEqual(self.controller.state["lighting"]["mode"], mode)
                    self.click(window, "reviewButton")
                    self.assertTrue(self.item(window, "reviewDialog").property("opened"))
                    self.assertIn("Lighting parameters: " + mode, self.item(window, "reviewText").property("text"))
                    self.click(window, self.dialog_button(window, "reviewDialog", "Close"))
                    self.assertFalse(self.item(window, "applyButton").isEnabled())

    def test_profile_creation_and_mapping_by_click_are_local(self):
        with self.rendered() as window:
            create = next(item for item in window.findChildren(QQuickItem)
                          if item.property("text") == "Create Profile…" and item.property("checkable") is not None)
            self.click(window, create)
            self.item(window, "profileName").setProperty("text", "UI test")
            self.click(window, self.dialog_button(window, "profileDialog", "OK"))
            self.assertTrue(self.controller.state["initialized"])
            self.assertEqual(window.property("selectedKey"), "capslock")
            names = [item["name"] for item in self.controller.targets]
            self.item(window, "targetPicker").setProperty("currentIndex", names.index("esc"))
            self.click(window, "stageMap")
            self.assertEqual(self.controller.state["mappings"]["capslock"], "esc")
            self.click(window, "reviewButton")
            text = self.item(window, "reviewText").property("text")
            self.assertIn("Create profile: UI test", text)
            self.assertIn("capslock → esc", text)
            self.assertFalse(self.item(window, "applyButton").isEnabled())
            self.assertEqual(self.controller.draft.baseline, self.snapshot)

    def test_apply_confirmation_cancel_then_simulated_success(self):
        device = SimulatedKeyboard(self.snapshot, writable=True)
        factory = Mock(return_value=device)
        self.controller.device_factory = factory
        self.controller.allow_writes = self.controller.live = True
        with tempfile.TemporaryDirectory() as directory, patch("retro87_model.data_dir", return_value=Path(directory)), self.rendered() as window:
            window.setProperty("page", 2)
            self.item(window, "volumeLevel").setProperty("value", 4)
            self.click(window, "stageVolume")
            self.click(window, "applyButton")
            factory.assert_not_called()
            self.click(window, self.dialog_button(window, "applyDialog", "No"))
            factory.assert_not_called()
            self.assertEqual(device.snapshot, self.snapshot)
            self.assertTrue(self.controller.state["dirty"])
            self.click(window, "applyButton")
            self.click(window, self.dialog_button(window, "applyDialog", "Yes"))
            self.wait()
            self.assertFalse(self.controller.error)
            self.assertFalse(self.controller.state["dirty"])
            self.assertEqual(device.snapshot.profile[0x5c9], 4)
            self.assertEqual(device.snapshot.led, self.snapshot.led)
            backups = list((Path(directory) / "backups").glob("*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(Snapshot.load(backups[0]), self.snapshot)
            factory.assert_called_once_with(writable=True)
            self.assertFalse(self.item(window, "applyButton").isEnabled())

    def test_simulated_partial_failure_disables_apply_and_keeps_review(self):
        device = SimulatedKeyboard(self.snapshot, writable=True, fail_after=1)
        factory = Mock(return_value=device)
        self.controller.device_factory = factory
        self.controller.allow_writes = self.controller.live = True
        with tempfile.TemporaryDirectory() as directory, patch("retro87_model.data_dir", return_value=Path(directory)), self.rendered() as window:
            self.controller.stageVolume(4)
            self.controller.stageRgb("solid", "#123456", 50, 5)
            self.click(window, "applyButton")
            self.click(window, self.dialog_button(window, "applyDialog", "Yes"))
            self.wait()
            self.assertIn("partially changed", self.controller.error)
            self.assertTrue(self.controller.failure)
            self.assertFalse(self.controller.live)
            self.assertFalse(self.item(window, "applyButton").isEnabled())
            self.click(window, "reviewButton")
            self.assertTrue(self.item(window, "reviewDialog").property("opened"))
            self.assertIn("Lighting parameters: solid", self.item(window, "reviewText").property("text"))
            self.assertEqual(sum(call[0] == "write" for call in device.calls), 1)
            factory.assert_called_once_with(writable=True)

    def test_stage_create_map_and_discard(self):
        self.controller.createProfile("Linux")
        self.controller.stageMap("capslock", "esc")
        self.controller.stageRgb("solid", "#8000ff", 50, 5)
        for source in ["ka", "kb"] + [f"k{i}" for i in range(1, 9)]:
            self.controller.stageMap(source, "f13")
            self.controller.stageDefault(source)
            self.assertFalse(self.controller.error)
            self.assertEqual(self.controller.state["mappings"][source], "Default")
        self.assertTrue(self.controller.state["dirty"])
        self.assertFalse(self.controller.state["canApply"])
        self.controller.applyConfirmed()
        self.factory.assert_not_called()
        self.controller.discard()
        self.assertFalse(self.controller.state["dirty"])

    def test_read_only_connect_and_guard_against_dirty_reload(self):
        device = SimulatedKeyboard(self.snapshot)
        self.controller.device_factory = Mock(return_value=device)
        self.controller.connectDevice()
        self.wait()
        self.assertTrue(self.controller.live)
        self.controller.device_factory.assert_called_once_with(writable=False)
        self.controller.stageVolume(4)
        self.controller.connectDevice()
        self.controller.device_factory.assert_called_once()
        self.assertIn("pending", self.controller.error)
        self.assertFalse(self.controller.state["canApply"])

    def test_export_restore_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "snapshot.json")
            self.controller.exportSnapshot(path, False)
            self.wait()
            self.controller.stageVolume(4)
            self.controller.restoreProfile(path)
            self.wait()
            self.assertFalse(self.controller.state["dirty"])
            self.controller.exportSnapshot(path, False)
            self.wait()
            self.assertTrue(self.controller.error)
            self.assertEqual(Snapshot.load(path), self.snapshot)

    def test_read_failure_is_reported(self):
        self.controller.device_factory = Mock(side_effect=PermissionError("HID access denied"))
        self.controller.connectDevice()
        self.wait()
        self.assertIn("HID access denied", self.controller.error)
        self.assertFalse(self.controller.live)

    def test_all_effects_stage_offline(self):
        for mode in protocol.MODES:
            self.controller.stageEffect(mode, "#123456", 50, 4, "#abcdef", 5, 30)
            self.assertFalse(self.controller.error)
            self.assertEqual(self.controller.state["lighting"]["mode"], mode)
        self.factory.assert_not_called()
        self.assertFalse(self.controller.state["canApply"])

    def test_per_key_lighting_click_stage_review_and_simulated_apply(self):
        device = SimulatedKeyboard(self.snapshot, writable=True)
        factory = Mock(return_value=device)
        self.controller.device_factory = factory
        self.controller.allow_writes = self.controller.live = True
        with tempfile.TemporaryDirectory() as directory, patch("retro87_model.data_dir", return_value=Path(directory)), self.rendered() as window:
            window.setProperty("page", 3)
            QTest.qWait(20)
            self.click(window, self.reveal(window, "led_w"))
            self.item(window, "ledKeyColor").setProperty("text", "#ff0000")
            self.click(window, self.reveal(window, "ledPaint"))
            self.click(window, self.reveal(window, "stageLeds"))
            self.assertFalse(self.controller.error)
            self.assertEqual(self.controller.state["leds"]["colors"]["w"], "#ff0000")
            self.assertEqual(self.controller.state["leds"]["colors"]["a"], "#000000")
            self.click(window, "reviewButton")
            text = self.item(window, "reviewText").property("text")
            self.assertIn("Per-key lighting: static", text)
            self.assertIn("custom LED block", text)
            self.click(window, self.dialog_button(window, "reviewDialog", "Close"))
            self.click(window, "applyButton")
            self.click(window, self.dialog_button(window, "applyDialog", "Yes"))
            self.wait()
            self.assertFalse(self.controller.error)
            self.assertEqual([c[0] for c in device.calls][2:4], ["write_led", "write"])
            self.assertEqual(device.snapshot.profile[0x5f9], 1)
            self.assertEqual(protocol.decode_led(device.snapshot.led)["colors"]["w"], "#ff0000")
            self.assertFalse(self.controller.state["dirty"])

    def test_every_page_renders_without_qml_warnings(self):
        messages = []
        previous = qInstallMessageHandler(lambda kind, context, message: messages.append(message))
        engine = QQmlApplicationEngine()
        try:
            engine.setInitialProperties({"bridge": self.controller})
            engine.load(QUrl.fromLocalFile(str(protocol.ROOT / "qml/Main.qml")))
            self.assertTrue(engine.rootObjects(), messages)
            window = engine.rootObjects()[0]
            for width, height in [(1200, 800), (1000, 700)]:
                window.resize(width, height)
                for page in range(5):
                    window.setProperty("page", page)
                    QTest.qWait(20)
                    self.assertFalse(window.grabWindow().isNull())
                    apply = window.findChild(QQuickItem, "applyButton")
                    self.assertLessEqual(apply.mapToScene(apply.boundingRect().bottomRight()).y(), height)
                window.setProperty("page", 3)
                picker = window.findChild(QQuickItem, "effectPicker")
                stage = window.findChild(QQuickItem, "stageRgb")
                for index in range(8):
                    picker.setProperty("currentIndex", index)
                    QTest.qWait(20)
                    point = stage.mapToScene(stage.boundingRect().bottomRight())
                    # The lighting editor scrolls; its permanent footer must not.
                    self.assertLessEqual(point.y(), 800)
                    self.assertLessEqual(point.x(), width)
            self.controller.createProfile("Linux")
            self.controller.stageMap("capslock", "esc")
            QTest.qWait(20)
            self.assertFalse(messages, "\n".join(messages))
            self.factory.assert_not_called()
            self.controller.discard()
            window.close()
        finally:
            del engine
            qInstallMessageHandler(previous)


if __name__ == "__main__":
    unittest.main()
