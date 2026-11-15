"""Rendered toolbar checks, using synthetic backdrops; no physical key claim."""
import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import QComboBox, QWidget

from PySide6.QtTest import QSignalSpy, QTest

from test_phase01 import app
from ui.overlay import CaptureAction, Overlay, SnipMode, SnipToolbar


def pixel(image, x, y):
    ratio = image.devicePixelRatio()
    return image.pixelColor(round(x * ratio), round(y * ratio))


class ToolbarReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.host = QWidget()
        self.host.resize(900, 150)
        self.host.setAutoFillBackground(True)
        self.toolbar = SnipToolbar(self.host)
        self.toolbar.move(40, 30)
        self.toolbar.adjustSize()
        self.host.show()
        app.processEvents()

    def tearDown(self):
        self.host.close()
        self.host.deleteLater()
        app.processEvents()

    def test_opaque_charcoal_on_bright_and_dark_backdrops(self):
        for background in ('#FFFFFF', '#050505'):
            palette = self.host.palette()
            palette.setColor(QPalette.Window, QColor(background))
            self.host.setPalette(palette)
            app.processEvents()
            image = self.host.grab().toImage()
            # Left inset away from border, child controls and rounded corners.
            color = pixel(image, self.toolbar.x() + 4,
                          self.toolbar.y() + self.toolbar.height() // 2)
            self.assertEqual(color.name(), '#181b20')
            self.assertEqual(color.alpha(), 255)
        self.assertFalse(self.toolbar.testAttribute(Qt.WA_TranslucentBackground))
        self.assertTrue(self.toolbar.testAttribute(Qt.WA_StyledBackground))

    def test_controls_and_compact_dimensions_preserved(self):
        self.assertEqual(self.toolbar.height(), 66)
        self.assertLessEqual(self.toolbar.width(), 640)
        self.assertEqual([b._name_lbl.text() for b in self.toolbar._buttons.values()],
                         ['Rectangle', 'Window', 'Full Screen'])
        for mode, button in self.toolbar._buttons.items():
            self.assertTrue(button.isEnabled())
            self.assertEqual((button.width(), button.height()), (78, 52))
            self.assertTrue(button._icon._color.isValid())
        self.assertNotIn(SnipMode.FREEFORM, self.toolbar._buttons)
        self.assertEqual(self.toolbar.findChildren(QComboBox), [])
        self.assertEqual(list(self.toolbar.action_buttons), ['screenshot', 'extract_text'])
        self.assertEqual(self.toolbar.current_action, 'screenshot')
        self.assertTrue(self.toolbar.action_buttons['screenshot'].isChecked())
        self.toolbar.set_action(CaptureAction.EXTRACT_TEXT.value)
        self.assertEqual(self.toolbar.current_action, 'extract_text')

    def test_action_segments_are_exclusive_and_emit_only_on_change(self):
        changed = QSignalSpy(self.toolbar.action_changed)
        mode = QSignalSpy(self.toolbar.mode_changed)
        screenshot = self.toolbar.action_buttons['screenshot']
        text = self.toolbar.action_buttons['extract_text']
        for button in (text, screenshot, text):
            QTest.mouseClick(button, Qt.LeftButton)
            self.assertTrue(button.isChecked())
            self.assertEqual(sum(b.isChecked() for b in self.toolbar.action_buttons.values()), 1)
        self.assertEqual(changed.count(), 3)
        self.assertEqual(changed.at(0), ['extract_text'])
        self.assertEqual(changed.at(1), ['screenshot'])
        text.click()  # Clicking the selected segment does not clear selection.
        self.toolbar.set_action('extract_text')
        self.toolbar.set_action('invalid')
        self.assertEqual(changed.count(), 3)
        self.assertEqual(mode.count(), 0)
        self.assertEqual(self.toolbar.current_mode, SnipMode.RECTANGULAR)

    def test_segments_have_readable_labels_icons_focus_and_selected_surface(self):
        text = self.toolbar.action_buttons['extract_text']
        text.setFocus()
        QTest.keyClick(text, Qt.Key_Space)
        self.assertEqual(self.toolbar.current_action, 'extract_text')
        self.assertEqual(text.focusPolicy(), Qt.StrongFocus)
        app.processEvents()
        image = self.host.grab().toImage()
        for action, button in self.toolbar.action_buttons.items():
            self.assertTrue(self.toolbar.rect().contains(button.mapTo(self.toolbar, QPoint())))
            self.assertTrue(self.toolbar.rect().contains(button.mapTo(self.toolbar, button.rect().bottomRight())))
            self.assertTrue(button.rect().contains(button._name_lbl.geometry()))
            self.assertTrue(button.rect().contains(button._icon.geometry()))
            self.assertGreaterEqual(button._name_lbl.width(), button._name_lbl.sizeHint().width())
            self.assertEqual(button.accessibleName(), button._name_lbl.text())
            self.assertEqual(button._icon.icon_name, action)
            self.assertIn('QToolButton:focus', button.styleSheet())
            point = button.mapTo(self.host, QPoint(4, button.height() // 2))
            expected = '#303653' if action == 'extract_text' else '#242a33'
            self.assertEqual(pixel(image, point.x(), point.y()).name(), expected)

    def test_action_switch_never_emits_capture_even_with_selection(self):
        overlay = Overlay()
        try:
            overlay.start_point, overlay.end_point = QPoint(10, 180), QPoint(110, 240)
            signals = [QSignalSpy(signal) for signal in (overlay.area_selected,
                overlay.fullscreen_capture_requested, overlay.window_capture_requested, overlay.cancelled)]
            for action in ('extract_text', 'screenshot', 'extract_text'):
                overlay._toolbar.action_buttons[action].click()
                self.assertEqual(overlay.capture_action, action)
            self.assertTrue(all(spy.count() == 0 for spy in signals))
            overlay.set_processing(True)
            overlay._toolbar.action_buttons['screenshot'].click()
            self.assertEqual(overlay.capture_action, 'extract_text')
            self.assertTrue(all(not b.isEnabled() for b in overlay._toolbar.action_buttons.values()))
            self.assertTrue(all(b._icon._color.name() == '#929aa8'
                                for b in overlay._toolbar.action_buttons.values()))
            overlay.set_processing(False)
            self.assertTrue(all(b.isEnabled() for b in overlay._toolbar.action_buttons.values()))
        finally:
            overlay.close()
            overlay.deleteLater()

    def test_selected_mode_has_opaque_indigo_and_visible_border(self):
        window = self.toolbar._buttons[SnipMode.WINDOW]
        window.click()  # Programmatic Qt action only, not physical acceptance.
        self.assertEqual(self.toolbar.current_mode, SnipMode.WINDOW)
        self.assertTrue(window.isChecked())
        image = self.host.grab().toImage()
        point = window.mapTo(self.host, QPoint(5, window.height() // 2))
        self.assertEqual(pixel(image, point.x(), point.y()).name(), '#303653')
        self.assertIn('#8994EC', window.styleSheet())
        self.assertFalse(self.toolbar._buttons[SnipMode.RECTANGULAR].isChecked())

    def test_disabled_icons_refresh_when_parent_disabled_and_restored(self):
        normal = self.toolbar._buttons[SnipMode.WINDOW]
        self.toolbar.setEnabled(False)
        self.assertEqual(normal._icon._color.name(), '#929aa8')
        self.toolbar.setEnabled(True)
        self.assertEqual(normal._icon._color.name(), '#ffffff')
        self.assertNotIn(SnipMode.FREEFORM, self.toolbar._buttons)

    def test_overlay_dimming_and_clear_selection_are_unchanged(self):
        bg = QPixmap(900, 500)
        bg.fill(QColor('white'))
        overlay = Overlay(bg)
        try:
            self.assertTrue(overlay.testAttribute(Qt.WA_TranslucentBackground))
            overlay.show()
            overlay.resize(900, 500)
            overlay.start_point = QPoint(100, 180)
            overlay.end_point = QPoint(220, 280)
            app.processEvents()
            image = overlay.grab().toImage()
            self.assertEqual(pixel(image, 150, 220).name(), '#ffffff')
            self.assertEqual(pixel(image, 10, 400).name(), '#787878')
            self.assertEqual(overlay._toolbar.y(), 20)
            self.assertLessEqual(abs(overlay._toolbar.geometry().center().x()
                                     - overlay.rect().center().x()), 1)
        finally:
            overlay.close()
            overlay.deleteLater()
