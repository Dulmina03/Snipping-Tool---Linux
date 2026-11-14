"""Rendered toolbar checks, using synthetic backdrops; no physical key claim."""
import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette, QPixmap
from PySide6.QtWidgets import QWidget

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
        self.assertLess(self.toolbar.width(), 660)
        self.assertEqual([b._name_lbl.text() for b in self.toolbar._buttons.values()],
                         ['Rectangle', 'Freeform', 'Window', 'Full Screen'])
        for mode, button in self.toolbar._buttons.items():
            self.assertEqual(button.isEnabled(), mode != SnipMode.FREEFORM)
            self.assertEqual((button.width(), button.height()), (78, 52))
            self.assertTrue(button._icon._color.isValid())
        combo = self.toolbar.action_combo
        self.assertEqual([combo.itemText(i) for i in range(combo.count())],
                         ['Screenshot', 'Extract Text'])
        self.assertEqual((combo.width(), combo.height()), (118, 34))
        self.toolbar.set_action(CaptureAction.EXTRACT_TEXT.value)
        self.assertEqual(self.toolbar.current_action, 'extract_text')

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
        self.assertFalse(self.toolbar._buttons[SnipMode.FREEFORM].isEnabled())

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
