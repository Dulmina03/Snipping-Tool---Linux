"""One Wayland fullscreen surface per output, sharing a frozen selection canvas."""
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QWidget

from capture.display_mapping import DisplayMappingError, Rect
from ui.overlay import Overlay, SnipMode


def screen_fingerprint(screens):
    return tuple(sorted((s.name(), s.geometry().getRect(), s.devicePixelRatio()) for s in screens))


class DisplayOverlay(QObject):
    area_selected = Signal(QRectF)
    fullscreen_capture_requested = Signal()
    window_capture_requested = Signal()
    cancelled = Signal()
    delivery_requested = Signal()
    mapping_failed = Signal(str)

    def __init__(self, pixmap, mapping, screens=None, screen_provider=None):
        super().__init__()
        self.capture_mapping = mapping
        self._screen_provider = screen_provider or QGuiApplication.screens
        screens = list(screens if screens is not None else self._screen_provider())
        self._fingerprint = screen_fingerprint(screens)
        monitors = {m.name: m for m in mapping.layout.monitors}
        if len(screens) != len(monitors) or {s.name() for s in screens} != set(monitors):
            raise DisplayMappingError('Qt outputs do not match GNOME displays. Use Window or Full Screen.')
        for screen in screens:
            rect = screen.geometry()
            logical = monitors[screen.name()].logical
            if (rect.width() <= 0 or rect.height() <= 0 or
                    abs(logical.width * rect.height() - logical.height * rect.width())
                    > 2 * max(logical.width, logical.height)):
                raise DisplayMappingError('Qt output proportions do not match GNOME. Use Window or Full Screen.')
        self.surfaces = []
        self.start = None
        self.end = None
        self._processing = False
        self._syncing = False
        self._connections = []
        for screen in screens:
            surface = MonitorOverlay(self, screen, monitors[screen.name()], pixmap)
            self.surfaces.append(surface)
            surface._toolbar.mode_changed.connect(lambda mode, view=surface: self._mode(mode, view))
            surface._toolbar.action_changed.connect(self._action)
            surface.fullscreen_capture_requested.connect(self.fullscreen_capture_requested)
            surface.window_capture_requested.connect(self.window_capture_requested)
            for signal_name in ('geometryChanged', 'logicalDotsPerInchChanged', 'physicalDotsPerInchChanged', 'orientationChanged'):
                signal = getattr(screen, signal_name, None)
                if signal is not None:
                    signal.connect(self._display_changed)
                    self._connections.append(signal)
        self.primary = next((s for s in self.surfaces if s.monitor.primary), self.surfaces[0])
        self._toolbar = self.primary._toolbar
        app = QGuiApplication.instance()
        for signal in (app.screenAdded, app.screenRemoved):
            signal.connect(self._display_changed)
            self._connections.append(signal)

    @property
    def capture_action(self):
        return self._toolbar.current_action

    def _mode(self, mode, origin):
        for surface in self.surfaces:
            surface._mode = mode
            surface._toolbar.select_mode(mode)
            surface._update_cursor()

    def _action(self, action):
        if self._syncing:
            return
        self._syncing = True
        try:
            for surface in self.surfaces:
                surface._toolbar.set_action(action)
        finally:
            self._syncing = False

    def showFullScreenOverlay(self):
        for surface in [s for s in self.surfaces if s is not self.primary] + [self.primary]:
            surface.showFullScreenOverlay()

    def isVisible(self):
        return any(s.isVisible() for s in self.surfaces)

    def isActiveWindow(self):
        return any(s.isActiveWindow() for s in self.surfaces)

    def set_processing(self, processing=True):
        self._processing = processing
        for surface in self.surfaces:
            surface.set_processing(processing)

    def setCursor(self, cursor):
        for surface in self.surfaces:
            surface.setCursor(cursor)

    def hide(self):
        for surface in self.surfaces:
            surface.hide()

    def close(self):
        for signal in self._connections:
            try:
                signal.disconnect(self._display_changed)
            except (RuntimeError, TypeError):
                pass
        self._connections.clear()
        for surface in self.surfaces:
            surface.close()

    def deleteLater(self):
        for surface in self.surfaces:
            surface.deleteLater()
        super().deleteLater()

    def _display_changed(self, *args):
        self.close()
        self.mapping_failed.emit('Display configuration changed. Capture again before selecting an area.')

    def begin(self, view, point):
        self.start = view.canvas_point(point)
        self.end = self.start
        self._unit = (view.monitor.logical.width / view.width(),
                      view.monitor.logical.height / view.height())
        self.update_selection()

    def move(self, view, point):
        if self.start is not None:
            self.end = view.canvas_point(point)
            self.update_selection()

    def selection(self):
        if self.start is None or self.end is None or self.start == self.end:
            return QRectF()
        return QRectF(min(self.start.x(), self.end.x()), min(self.start.y(), self.end.y()),
                      abs(self.start.x() - self.end.x()) + self._unit[0],
                      abs(self.start.y() - self.end.y()) + self._unit[1])

    def update_selection(self):
        for surface in self.surfaces:
            surface.update()

    def confirm(self):
        rect = self.selection()
        if rect.isEmpty() or rect.width() <= 2 * self._unit[0] or rect.height() <= 2 * self._unit[1]:
            self.cancel()
            return
        try:
            if screen_fingerprint(self._screen_provider()) != self._fingerprint:
                raise DisplayMappingError('Display geometry changed. Capture again.')
            for surface in self.surfaces:
                if isinstance(surface.target_screen, QScreen):
                    handle = surface.windowHandle()
                    if handle is None or handle.screen().name() != surface.monitor.name:
                        raise DisplayMappingError('The compositor did not place an overlay on its requested output. Capture again.')
            self.capture_mapping.crop_box(Rect(rect.x(), rect.y(), rect.width(), rect.height()))
        except DisplayMappingError as error:
            self.close()
            self.mapping_failed.emit(str(error))
            return
        self.area_selected.emit(rect)
        if not self._processing:
            self.close()

    def cancel(self):
        self.start = self.end = None
        self.close()
        self.cancelled.emit()


class MonitorOverlay(Overlay):
    def __init__(self, session, screen, monitor, pixmap):
        super().__init__(bg_pixmap=pixmap)
        self.session, self.target_screen, self.monitor = session, screen, monitor
        source = session.capture_mapping.source_rect(monitor)
        self.bg_source_rect = QRectF(source.x, source.y, source.width, source.height)

    def showFullScreenOverlay(self):
        self.winId()  # Create a native surface before choosing its output.
        if isinstance(self.target_screen, QScreen):
            self.windowHandle().setScreen(self.target_screen)
        self.resize(self.target_screen.geometry().size())
        self.showFullScreen()
        self._position_toolbar()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event):
        # No global move/virtual-size request: Wayland fullscreen is per output.
        QWidget.showEvent(self, event)
        self._position_toolbar()

    def canvas_point(self, point):
        desktop = self.session.capture_mapping.layout.desktop
        logical = self.monitor.logical
        return QPointF(logical.x - desktop.x + point.x() * logical.width / self.width(),
                       logical.y - desktop.y + point.y() * logical.height / self.height())

    def get_selection_rect(self):
        rect = self.session.selection()
        if rect.isEmpty():
            return QRectF()
        logical = self.monitor.logical
        desktop = self.session.capture_mapping.layout.desktop
        return QRectF((rect.x() - logical.x + desktop.x) * self.width() / logical.width,
                      (rect.y() - logical.y + desktop.y) * self.height() / logical.height,
                      rect.width() * self.width() / logical.width,
                      rect.height() * self.height() / logical.height)

    def selection_pixel_size(self):
        rect = self.session.selection()
        try:
            left, top, right, bottom = self.session.capture_mapping.crop_box(
                Rect(rect.x(), rect.y(), rect.width(), rect.height()))
            return right - left, bottom - top
        except DisplayMappingError:
            return None

    def mousePressEvent(self, event):
        if self._processing or self._mode != SnipMode.RECTANGULAR:
            return
        if event.button() == Qt.LeftButton and not self._toolbar.geometry().contains(event.position().toPoint()):
            self.selecting = True
            self.session.begin(self, event.position())

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.session.move(self, event.position())

    def mouseReleaseEvent(self, event):
        if self._processing:
            if event.button() == Qt.LeftButton:
                self.session.delivery_requested.emit()
        elif event.button() == Qt.LeftButton and self.selecting:
            self.session.move(self, event.position())
            self.selecting = False
            self.session.confirm()

    def confirm_selection(self):
        self.session.confirm()

    def cancel_selection(self):
        self.session.cancel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.session.cancel()
        elif self._processing and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.session.delivery_requested.emit()
        elif not self._processing and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.session.confirm()
