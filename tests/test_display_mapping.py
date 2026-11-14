"""Controlled display/image fixtures, not physical multi-monitor acceptance."""
import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from dbus_next import MessageType, Variant
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QCoreApplication, QEvent, Qt
from PySide6.QtGui import QPixmap

from test_phase01 import app, spin_until
from capture.display_mapping import (CaptureMapping, DisplayMappingError, Layout,
    Monitor, Rect, compatibility_mapping, parse_layout, read_gnome_layout)
from ui.display_overlay import DisplayOverlay
from ui.overlay import Overlay, SnipMode
import ui.capture_menu as controller


def fixture(width, height):
    image = Image.new('RGB', (width, height))
    image.putdata([((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
                   for y in range(height) for x in range(width)])
    return image


def state(monitors, serial=8, mode=1):
    physical, logical = [], []
    for name, x, y, width, height, scale, transform in monitors:
        spec = [name, 'vendor', 'product', 'serial']
        physical.append([spec, [['mode', width, height, 60., scale, [scale],
                                {'is-current': Variant('b', True)}]], {}])
        logical.append([x, y, scale, transform, not logical, [spec], {}])
    return [serial, physical, logical, {'layout-mode': Variant('u', mode)}]


def screen(name, rect, dpr=1):
    return NS(name=lambda: name, geometry=lambda: QRect(*rect), devicePixelRatio=lambda: dpr)


class MappingTests(unittest.TestCase):
    def test_single_screen_100_125_150_175_200(self):
        for scale in (1., 1.25, 1.5, 1.75, 2.):
            with self.subTest(scale=scale):
                layout = Layout(1, (Monitor('one', Rect(0, 0, 80, 60), scale, True),))
                mapping = layout.mapping((round(80 * scale), round(60 * scale)))
                # Outward coverage of half-open selection, not banker's rounding.
                import math
                self.assertEqual(mapping.crop_box(Rect(3, 5, 13, 11)),
                    (math.floor(3 * scale), math.floor(5 * scale),
                     math.ceil(16 * scale), math.ceil(16 * scale)))
                self.assertEqual(mapping.crop_box(Rect(0, 0, 80, 60)), (0, 0, *mapping.image_size))

    def test_fractional_gnome_ceil_render_buffer_is_not_scaled_twice(self):
        layout = Layout(1, (Monitor('one', Rect(0, 0, 80, 60), 1.25, True),))
        mapping = layout.mapping((160, 120))
        self.assertEqual(mapping.scale, 2.)
        self.assertEqual(mapping.crop_box(Rect(10, 10, 20, 15)), (20, 20, 60, 50))

    def test_two_different_resolutions_and_boundary_crossing(self):
        layout = Layout(1, (Monitor('primary', Rect(0, 0, 80, 60), 1, True),
                            Monitor('right', Rect(80, 0, 120, 80), 1)))
        mapping = layout.mapping((200, 80))
        self.assertEqual(mapping.crop_box(Rect(70, 10, 30, 20)), (70, 10, 100, 30))
        self.assertEqual(mapping.source_rect(layout.monitors[1]), Rect(80, 0, 120, 80))
        with self.assertRaisesRegex(DisplayMappingError, 'outside'):
            mapping.crop_box(Rect(30, 50, 80, 25))  # Includes space below shorter monitor.
        large = Layout(1, (Monitor('one', Rect(0, 0, 10000, 10000), 1),
                            Monitor('two', Rect(10000, 0, 10000, 9999), 1))).mapping((20000, 10000))
        with self.assertRaises(DisplayMappingError):
            large.crop_box(Rect(0, 0, 10000.003, 10000))  # Relative area tolerance must not admit a gap.

    def test_mixed_scale_stage_mapping_uses_compositor_scale_not_output_dpr(self):
        layout = parse_layout(state([('left', 0, 0, 160, 120, 2., 0),
                                     ('right', 80, 0, 120, 80, 1., 0)]))
        mapping = layout.mapping((400, 160))
        self.assertEqual(mapping.crop_box(Rect(70, 10, 30, 20)), (140, 20, 200, 60))
        # Right monitor's pixels in the GNOME composed PNG are also 2x.
        self.assertEqual(mapping.source_rect(layout.monitors[1]), Rect(160, 0, 240, 160))

    def test_left_above_below_negative_origins_normalize_canvas_once(self):
        cases = [((-80, 0, 80, 60), (0, 0, 80, 60), (160, 60)),
                 ((0, -60, 80, 60), (0, 0, 80, 60), (80, 120)),
                 ((0, 0, 80, 60), (0, 60, 80, 60), (80, 120))]
        for first, second, size in cases:
            layout = Layout(1, (Monitor('one', Rect(*first), 1), Monitor('two', Rect(*second), 1, True)))
            mapping = layout.mapping(size)
            self.assertEqual(mapping.crop_box(Rect(3, 5, 10, 12)), (3, 5, 13, 17))
            self.assertEqual(mapping.source_rect(layout.monitors[0]), Rect(0, 0, 80, 60))

    def test_edges_clipped_to_image_and_outside_or_invalid_selections_rejected(self):
        mapping = Layout(1, (Monitor('one', Rect(0, 0, 80, 60), 1.5),)).mapping((120, 90))
        self.assertEqual(mapping.crop_box(Rect(78, 58, 9, 9)), (117, 87, 120, 90))
        self.assertEqual(mapping.crop_box(Rect(-2, -2, 5, 5)), (0, 0, 5, 5))
        for rect in (Rect(90, 0, 5, 5), Rect(1, 1, 0, 5), Rect(1, 1, -5, 5), Rect(float('nan'), 0, 5, 5)):
            with self.assertRaises(DisplayMappingError):
                mapping.crop_box(rect)

    def test_unknown_backend_nonuniform_dimensions_and_layout_mode_rejected(self):
        layout = Layout(1, (Monitor('one', Rect(0, 0, 80, 60), 1),))
        for size, software in (((80, 61), 'gnome-screenshot'), ((80, 60), 'other')):
            with self.assertRaises(DisplayMappingError):
                layout.mapping(size, software)
        with self.assertRaises(DisplayMappingError):
            replace(layout, mode=2).mapping((80, 60))
        with self.assertRaises(DisplayMappingError):
            compatibility_mapping((80, 60), (80, 61))

    def test_parser_fractional_rotation_and_geometry(self):
        layout = parse_layout(state([('rotated', 0, 0, 120, 160, 2., 1)]))
        self.assertEqual(layout.monitors[0].logical, Rect(0, 0, 80, 60))
        self.assertEqual(layout.serial, 8)
        self.assertEqual(layout.mapping((160, 120)).scale, 2)

    def test_parser_rejects_overlap_clone_and_missing_mode(self):
        for body in [state([('one', 0, 0, 80, 60, 1., 0), ('two', 20, 0, 80, 60, 1., 0)]),
                     state([('one', 0, 0, 80, 60, 1., 0)])]:
            if len(body[1]) == 1:
                body[1][0][1][0][6] = {}
            with self.assertRaises(DisplayMappingError):
                parse_layout(body)
        body = state([('one', 0, 0, 80, 60, 1., 0)])
        body[2][0][5].append(['clone', 'v', 'p', 's'])
        with self.assertRaises(DisplayMappingError):
            parse_layout(body)

    def test_saved_and_copied_pixels_match_original_source_slice(self):
        layout = Layout(1, (Monitor('left', Rect(-80, 0, 80, 60), 2),
                            Monitor('right', Rect(0, 0, 120, 80), 1, True)))
        mapping = layout.mapping((400, 160))
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.png'
            original = fixture(400, 160)
            original.save(source)
            with patch.object(controller, 'SCREENSHOTS_DIR', Path(folder) / 'saved'):
                output = controller._crop_and_save(source, 70, 10, 30, 20, mapping=mapping)
            with Image.open(output) as saved:
                self.assertEqual(saved.size, (60, 40))
                self.assertEqual(saved.tobytes(), original.crop((140, 20, 200, 60)).tobytes())
            from utils.clipboard import copy_image_to_clipboard
            from PySide6.QtGui import QImage
            copy_image_to_clipboard(output)
            png = bytes(app.clipboard().mimeData().data('image/png'))
            image = QImage.fromData(png, 'PNG')
            self.assertEqual((image.width(), image.height()), (60, 40))
            color = image.pixelColor(2, 3)
            self.assertEqual((color.red(), color.green(), color.blue()), original.getpixel((142, 23)))
            app.clipboard().clear()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.screens = [screen('left', (-80, 0, 80, 60), 2), screen('right', (0, 0, 120, 80), 1)]
        layout = Layout(1, (Monitor('left', Rect(0, 0, 80, 60), 2), Monitor('right', Rect(80, 0, 120, 80), 1, True)))
        self.mapping = layout.mapping((400, 160))
        pixmap = QPixmap(400, 160)
        pixmap.fill(Qt.white)
        self.session = DisplayOverlay(pixmap, self.mapping, self.screens, screen_provider=lambda: self.screens)
        for surface in self.session.surfaces:
            surface.resize(surface.target_screen.geometry().size())

    def tearDown(self):
        self.session.close()
        self.session.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        app.clipboard().clear()

    def test_each_monitor_displays_its_source_region_without_global_stretch(self):
        left, right = self.session.surfaces
        self.assertEqual(left.bg_source_rect.getRect(), (0., 0., 160., 120.))
        self.assertEqual(right.bg_source_rect.getRect(), (160., 0., 240., 160.))
        self.assertEqual(right.canvas_point(QPointF(10, 10)), QPoint(90, 10))
        self.assertEqual(left.canvas_point(QPointF(10, 10)), QPoint(10, 10))

    def test_per_output_painting_uses_correct_pixels_not_whole_desktop(self):
        from PySide6.QtGui import QImage
        image = QImage(400, 160, QImage.Format_RGB32)
        image.fill(Qt.blue)
        from PySide6.QtGui import QPainter
        painter = QPainter(image)
        painter.fillRect(0, 0, 160, 160, Qt.red)
        painter.end()
        pixmap = QPixmap.fromImage(image)
        self.session.start, self.session.end = QPointF(0, 0), QPointF(199, 79)
        self.session._unit = (1., 1.)
        for surface, expected in zip(self.session.surfaces, ('#ff0000', '#0000ff')):
            surface.bg_pixmap = pixmap
            surface._toolbar.hide()
            rendered = surface.grab().toImage()
            ratio = rendered.devicePixelRatio()
            self.assertEqual(rendered.pixelColor(round(10 * ratio), round(10 * ratio)).name(), expected)

    def test_cross_monitor_implicit_grab_coordinates_and_shared_selection(self):
        left, right = self.session.surfaces
        # Wayland pointer-grab events remain relative to the originating surface.
        self.session.begin(left, QPointF(70, 10))
        self.session.move(left, QPointF(99, 29))
        observed = []
        self.session.area_selected.connect(observed.append)
        self.session.confirm()
        self.assertEqual(observed, [QRectF(70, 10, 30, 20)])
        self.session.begin(right, QPointF(19, 29))
        self.session.move(right, QPointF(-10, 10))
        self.assertEqual(self.session.selection(), QRectF(70, 10, 30, 20))
        self.assertEqual(right.get_selection_rect().getRect(), (-10., 10., 30., 20.))
        self.assertEqual(self.mapping.crop_box(Rect(70, 10, 30, 20)), (140, 20, 200, 60))

    def test_qt_scaled_surface_coordinates_not_multiplied_by_dpr_again(self):
        surface = self.session.surfaces[0]
        surface.resize(40, 30)  # e.g. QT_SCALE_FACTOR=2 logical widget units.
        self.assertEqual(surface.canvas_point(QPointF(5, 5)), QPoint(10, 10))
        self.session.begin(surface, QPointF(5, 5))
        self.session.move(surface, QPointF(14.5, 9.5))
        rect = self.session.selection()
        self.assertEqual(self.mapping.crop_box(Rect(rect.x(), rect.y(), rect.width(), rect.height())), (20, 20, 62, 42))

    def test_fractional_viewport_edges_keep_subpixel_precision(self):
        view = self.session.surfaces[0]
        view.resize(64, 48)  # 1.25 GNOME logical units per Qt widget unit.
        self.session.begin(view, QPointF(10, 10))
        self.session.move(view, QPointF(19, 19))
        rect = self.session.selection()
        self.assertEqual(rect, QRectF(12.5, 12.5, 12.5, 12.5))
        self.assertEqual(self.mapping.crop_box(Rect(rect.x(), rect.y(), rect.width(), rect.height())),
                         (25, 25, 50, 50))
        self.assertEqual(view.get_selection_rect(), QRectF(10, 10, 10, 10))
        self.assertEqual(view.selection_pixel_size(), (25, 25))

    def test_changed_geometry_and_gap_abort_without_output(self):
        failures, areas = [], []
        self.session.mapping_failed.connect(failures.append)
        self.session.area_selected.connect(areas.append)
        self.session.begin(self.session.surfaces[0], QPointF(10, 10))
        self.session.move(self.session.surfaces[0], QPointF(30, 30))
        self.screens[0] = screen('left', (-80, 0, 70, 60), 2)
        self.session.confirm()
        self.assertTrue(failures)
        self.assertFalse(areas)

    def test_corner_selection_cancel_and_synchronized_controls(self):
        left, right = self.session.surfaces
        self.session.begin(left, QPointF(0, 0))
        self.session.move(left, QPointF(9, 9))
        self.assertEqual(self.session.selection(), QRectF(0, 0, 10, 10))
        left._toolbar.set_action('extract_text')
        self.assertEqual(right.capture_action, 'extract_text')
        self.session.set_processing()
        self.assertTrue(all(s._processing for s in self.session.surfaces))
        observed = []
        self.session.cancelled.connect(lambda: observed.append(True))
        self.session.cancel()
        self.assertEqual(observed, [True])
        self.assertFalse(self.session.isVisible())

    def test_window_fullscreen_and_cancel_signals_route_once_from_any_output(self):
        full, windows, cancelled = [], [], []
        self.session.fullscreen_capture_requested.connect(lambda: full.append(True))
        self.session.window_capture_requested.connect(lambda: windows.append(True))
        self.session.cancelled.connect(lambda: cancelled.append(True))
        self.session.surfaces[0]._toolbar._buttons[SnipMode.FULLSCREEN].click()
        self.assertEqual(full, [True])
        self.assertTrue(all(s._mode == SnipMode.FULLSCREEN for s in self.session.surfaces))
        self.session.surfaces[1]._toolbar._buttons[SnipMode.WINDOW].click()
        self.assertEqual(windows, [True])
        self.session.surfaces[0].cancel_selection()
        self.assertEqual(cancelled, [True])

    def test_generic_overlay_accepts_origin_and_reverse_drag_to_origin(self):
        overlay = Overlay()
        try:
            overlay.start_point, overlay.end_point = QPoint(0, 0), QPoint(10, 10)
            self.assertEqual(overlay.get_selection_rect(), QRect(0, 0, 11, 11))
            overlay.start_point, overlay.end_point = overlay.end_point, overlay.start_point
            self.assertEqual(overlay.get_selection_rect(), QRect(0, 0, 11, 11))
        finally:
            overlay.close()
            overlay.deleteLater()


class ProviderTests(unittest.TestCase):
    def test_unverified_shell_version_and_gnome_negative_origin_refused(self):
        for version, body in [('51.0', state([('one', 0, 0, 80, 60, 1., 0)])),
                              ('50.1', state([('one', -80, 0, 80, 60, 1., 0)]))]:
            closed = []
            bus = NS(connect=AsyncMock(), disconnect=lambda: closed.append(True))
            bus.connect.return_value = bus
            bus.call = AsyncMock(side_effect=[NS(message_type=MessageType.METHOD_RETURN, body=[Variant('s', version)]),
                NS(message_type=MessageType.METHOD_RETURN, body=body)])
            with patch('capture.display_mapping.MessageBus', return_value=bus):
                with self.assertRaises(DisplayMappingError):
                    asyncio.run(read_gnome_layout())
            self.assertEqual(closed, [True])
            if version == '51.0':
                self.assertEqual(bus.call.await_count, 1)
        with patch('capture.display_mapping.MessageBus', side_effect=RuntimeError('no session bus')):
            with self.assertRaises(DisplayMappingError):
                asyncio.run(read_gnome_layout())

    def test_read_only_query_and_disconnect_on_success_error_and_cancel(self):
        for outcome in ('success', 'error', 'cancel'):
            bus = NS(connect=AsyncMock(), disconnect=lambda: disconnected.append(True))
            bus.connect.return_value = bus
            disconnected = []
            if outcome == 'cancel':
                bus.call = AsyncMock(side_effect=asyncio.CancelledError)
            else:
                bus.call = AsyncMock(side_effect=[
                    NS(message_type=MessageType.METHOD_RETURN, body=[Variant('s', '50.1')]),
                    NS(message_type=MessageType.METHOD_RETURN if outcome == 'success' else MessageType.ERROR,
                       body=state([('one', 0, 0, 80, 60, 1., 0)]))])
            with patch('capture.display_mapping.MessageBus', return_value=bus):
                if outcome == 'success':
                    self.assertEqual(asyncio.run(read_gnome_layout()).serial, 8)
                else:
                    with self.assertRaises(asyncio.CancelledError if outcome == 'cancel' else DisplayMappingError):
                        asyncio.run(read_gnome_layout())
            self.assertEqual(disconnected, [True])
            self.assertEqual(bus.call.call_args.args[0].member,
                             'Get' if outcome == 'cancel' else 'GetCurrentState')


class ControllerMappingTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        self.source = self.root / 'portal.png'
        from PIL.PngImagePlugin import PngInfo
        metadata = PngInfo()
        metadata.add_text('Software', 'gnome-screenshot')
        self.qt = app.primaryScreen()
        size = self.qt.geometry().size()
        Image.new('RGB', (size.width(), size.height()), 'blue').save(self.source, pnginfo=metadata)
        rect = self.qt.geometry()
        self.layout = Layout(1, (Monitor(self.qt.name(), Rect(0, 0, rect.width(), rect.height()), 1., True),))
        self.menu = controller.CaptureMenu()
        self.messages = []
        self.menu._show_toast = self.messages.append
        self.patches = [patch.object(controller.QGuiApplication, 'platformName', return_value='wayland'),
            patch.object(controller, '_portal_screenshot', new=AsyncMock(return_value=self.source)),
            patch.object(controller, 'SCREENSHOTS_DIR', self.root / 'saved')]
        for item in self.patches:
            item.start()

    def tearDown(self):
        self.menu.shutdown()
        self.menu.jobs.close()
        self.menu.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.clipboard().clear()
        for item in reversed(self.patches):
            item.stop()
        self.scratch.cleanup()
        app.processEvents()

    def test_verified_native_branch_delivers_exact_crop_through_existing_handler(self):
        with patch.object(controller, 'read_gnome_layout', new=AsyncMock(return_value=self.layout)):
            self.menu.launch_overlay()
            spin_until(lambda: self.menu._overlay is not None and not self.menu.busy)
        session = self.menu._overlay
        self.assertIsInstance(session, DisplayOverlay)
        with patch.object(session, 'isActiveWindow', return_value=True):
            session.begin(session.primary, QPointF(20, 100))
            session.move(session.primary, QPointF(39, 119))
            session.confirm()
            spin_until(lambda: not self.menu.busy)
        self.assertIsNone(self.menu._overlay)
        with Image.open(self.menu.last_capture_path) as result:
            self.assertEqual(result.size, (20, 20))
            self.assertEqual(result.getpixel((3, 4)), (0, 0, 255))
        self.assertFalse(self.source.exists())

    def test_missing_layout_disables_rectangle_but_preserves_fullscreen_save(self):
        with patch.object(controller, 'read_gnome_layout', new=AsyncMock(side_effect=DisplayMappingError('mapping unavailable'))):
            self.menu.launch_overlay()
            spin_until(lambda: self.menu._overlay is not None and not self.menu.busy)
        overlay = self.menu._overlay
        self.assertFalse(overlay._toolbar._buttons[SnipMode.RECTANGULAR].isEnabled())
        self.assertTrue(overlay._toolbar._buttons[SnipMode.WINDOW].isEnabled())
        self.assertTrue(overlay._toolbar._buttons[SnipMode.FULLSCREEN].isEnabled())
        self.assertIsNone(overlay.bg_pixmap)  # No misleading stretched preview.
        self.assertIn('mapping unavailable', self.messages[-1])
        expected = self.source.read_bytes()
        with patch.object(overlay, 'isActiveWindow', return_value=True):
            self.menu._on_fullscreen(self.source, 'screenshot')
            spin_until(lambda: not self.menu.busy)
        self.assertEqual(self.menu.last_capture_path.read_bytes(), expected)
        self.assertIsNone(self.menu._overlay)

    def test_changed_layout_during_capture_refuses_rectangle_without_file(self):
        with patch.object(controller, 'read_gnome_layout', new=AsyncMock(side_effect=[self.layout, replace(self.layout, serial=2)])):
            self.menu.launch_overlay()
            spin_until(lambda: self.menu._overlay is not None and not self.menu.busy)
        self.assertIn('changed during capture', self.messages[-1])
        self.menu._on_area_selected(QRect(0, 0, 20, 20), self.source, 'screenshot')
        self.assertIsNone(self.menu.last_capture_path)
        self.assertIsNone(self.menu._overlay)
        self.assertFalse((self.root / 'saved').exists())

    def test_layout_change_while_selecting_cancels_all_surfaces_and_source(self):
        with patch.object(controller, 'read_gnome_layout', new=AsyncMock(return_value=self.layout)):
            self.menu.launch_overlay()
            spin_until(lambda: self.menu._overlay is not None and not self.menu.busy)
        session = self.menu._overlay
        session._display_changed()
        self.assertFalse(session.isVisible())
        self.assertIsNone(self.menu._overlay)
        self.assertFalse(self.source.exists())
        self.assertIn('configuration changed', self.messages[-1])
        self.assertIsNone(self.menu.last_capture_path)
