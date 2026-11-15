"""Full-screen snipping overlay with a compact, opaque vector toolbar."""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────────────────────────────────────

class SnipMode(str, enum.Enum):
    RECTANGULAR = "rectangular"
    FREEFORM    = "freeform"
    WINDOW      = "window"
    FULLSCREEN  = "fullscreen"


class CaptureAction(str, enum.Enum):
    SCREENSHOT   = "screenshot"
    EXTRACT_TEXT = "extract_text"


# ─────────────────────────────────────────────────────────────────────────────
#  Vector Icon Widget — Crisp, resolution-independent line-art icons
# ─────────────────────────────────────────────────────────────────────────────

class VectorIconWidget(QWidget):
    """
    Renders resolution-independent vector icons with QPainter.
    Thin, crisp lines (1.5px stroke) with consistent optical weight.
    """

    def __init__(
        self,
        icon_name: str,
        parent: QWidget | None = None,
        size: int = 20,
        color: QColor | str = "#FFFFFF",
    ):
        super().__init__(parent)
        self.icon_name = icon_name
        self._color = QColor(color) if isinstance(color, str) else color
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_color(self, color: QColor | str) -> None:
        c = QColor(color) if isinstance(color, str) else color
        if c != self._color:
            self._color = c
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Scale coordinate space to 20x20
        scale = self.width() / 20.0
        painter.scale(scale, scale)

        pen = QPen(self._color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        name = self.icon_name
        if name == "rectangular":
            # Dashed selection box with corner crosshair anchor
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([3, 2])
            painter.setPen(pen)
            painter.drawRoundedRect(QRectF(2.5, 3.5, 15, 13), 2, 2)
            # Corner crosshair anchor
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(1.5, 3.5), QPointF(4.5, 3.5))
            painter.drawLine(QPointF(2.5, 2.5), QPointF(2.5, 5.5))

        elif name == "freeform":
            # Smooth lasso loop with knot
            path = QPainterPath()
            path.moveTo(5.5, 13.5)
            path.cubicTo(2.5, 8.5, 6.5, 3.5, 11.5, 4.0)
            path.cubicTo(16.5, 4.5, 17.5, 10.5, 14.0, 14.5)
            path.cubicTo(11.5, 17.0, 7.5, 17.0, 6.0, 14.5)
            path.lineTo(4.0, 16.5)
            painter.drawPath(path)

        elif name == "window":
            # Modern application window with titlebar line & 3 window dots
            painter.drawRoundedRect(QRectF(2, 2.5, 16, 15), 2.5, 2.5)
            painter.drawLine(QPointF(2, 6.5), QPointF(18, 6.5))
            painter.setBrush(self._color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(4.2, 4.2, 1.8, 1.8))
            painter.drawEllipse(QRectF(7.2, 4.2, 1.8, 1.8))
            painter.drawEllipse(QRectF(10.2, 4.2, 1.8, 1.8))

        elif name == "fullscreen":
            # 4 expand corner brackets
            painter.drawLine(QPointF(3, 7), QPointF(3, 3))
            painter.drawLine(QPointF(3, 3), QPointF(7, 3))
            painter.drawLine(QPointF(13, 3), QPointF(17, 3))
            painter.drawLine(QPointF(17, 3), QPointF(17, 7))
            painter.drawLine(QPointF(3, 13), QPointF(3, 17))
            painter.drawLine(QPointF(3, 17), QPointF(7, 17))
            painter.drawLine(QPointF(13, 17), QPointF(17, 17))
            painter.drawLine(QPointF(17, 17), QPointF(17, 13))

        elif name == "screenshot":
            painter.drawRoundedRect(QRectF(2, 5, 16, 12), 2, 2)
            painter.drawEllipse(QRectF(7, 8, 6, 6))
            painter.drawLine(QPointF(6, 5), QPointF(7, 2.5))
            painter.drawLine(QPointF(7, 2.5), QPointF(13, 2.5))
            painter.drawLine(QPointF(13, 2.5), QPointF(14, 5))

        elif name == "extract_text":
            for x, direction in ((2, 1), (18, -1)):
                for y, vertical in ((3, 1), (17, -1)):
                    painter.drawLine(QPointF(x, y), QPointF(x + 3 * direction, y))
                    painter.drawLine(QPointF(x, y), QPointF(x, y + 3 * vertical))
            painter.drawLine(QPointF(6, 7), QPointF(14, 7))
            painter.drawLine(QPointF(10, 7), QPointF(10, 14))
            painter.drawLine(QPointF(8, 14), QPointF(12, 14))

        elif name == "close":
            # Clean diagonal cross
            painter.drawLine(QPointF(5, 5), QPointF(15, 15))
            painter.drawLine(QPointF(15, 5), QPointF(5, 15))

        elif name == "brand":
            # Minimal viewfinder / aperture symbol
            painter.drawRoundedRect(QRectF(3.5, 3.5, 13, 13), 3, 3)
            painter.drawLine(QPointF(10, 1.5), QPointF(10, 4.5))
            painter.drawLine(QPointF(10, 15.5), QPointF(10, 18.5))
            painter.drawLine(QPointF(1.5, 10), QPointF(4.5, 10))
            painter.drawLine(QPointF(15.5, 10), QPointF(18.5, 10))
            painter.setBrush(self._color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(8.5, 8.5, 3, 3))

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
#  Mode Button — Refined Linear/Raycast aesthetic
# ─────────────────────────────────────────────────────────────────────────────

class _ModeButton(QToolButton):
    """
    Mode selector button with a resolution-independent vector icon and
    refined typography.
    """

    # Normal: transparent with subtle border on hover
    _STYLE_NORMAL = """
        QToolButton {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 3px;
        }
        QToolButton:hover {
            background: #2D3440;
            border: 1px solid #454D5B;
        }
        QToolButton:pressed {
            background: #364155;
            border: 1px solid #596477;
        }
    """

    # Checked: opaque muted indigo with a visible border
    _STYLE_CHECKED = """
        QToolButton {
            background: #303653;
            border: 1px solid #8994EC;
            border-radius: 8px;
            padding: 3px;
        }
        QToolButton:hover {
            background: #3C4567;
            border: 1px solid #B0B9FF;
        }
    """

    # Disabled: muted but legible, with a distinct solid surface
    _STYLE_DISABLED = """
        QToolButton {
            background: #1D2128;
            border: 1px solid #343B47;
            border-radius: 8px;
            padding: 3px;
        }
    """

    # Colors applied to vector icon and label text
    _COLOR_NORMAL   = "#FFFFFF"
    _COLOR_CHECKED  = "#FFFFFF"
    _COLOR_DISABLED = "#929AA8"

    def __init__(self, mode: SnipMode, label: str, enabled: bool = True):
        super().__init__()
        self.mode = mode
        self.setCheckable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 5, 4, 5)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignCenter)

        # 1. Vector Icon (QPainter line art) — Pure white
        self._icon = VectorIconWidget(mode.value, self, size=20, color="#FFFFFF")
        self._glyph_lbl = self._icon  # backward-compatible attribute
        layout.addWidget(self._icon, 0, Qt.AlignCenter)

        # 2. Refined label with purposeful typography (regular 500 weight)
        self._name_lbl = QLabel(label)
        self._name_lbl.setAlignment(Qt.AlignCenter)
        self._name_lbl.setStyleSheet(
            "font-size: 11px; background: transparent; font-weight: 500; "
            "letter-spacing: 0.2px; font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;"
        )
        self._name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_lbl, 0, Qt.AlignCenter)

        self.setFixedSize(QSize(78, 52))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.setEnabled(enabled)

        self._refresh_style()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.EnabledChange and hasattr(self, '_name_lbl'):
            self._refresh_style()

    def _refresh_style(self) -> None:
        if not self.isEnabled():
            self.setStyleSheet(self._STYLE_DISABLED)
            self._set_label_color(self._COLOR_DISABLED, is_bold=False)
        elif self.isChecked():
            self.setStyleSheet(self._STYLE_CHECKED)
            self._set_label_color(self._COLOR_CHECKED, is_bold=True)
        else:
            self.setStyleSheet(self._STYLE_NORMAL)
            self._set_label_color(self._COLOR_NORMAL, is_bold=False)

    def _set_label_color(self, color: str, is_bold: bool = False) -> None:
        """Apply color and purposeful font weight to vector icon and label."""
        if hasattr(self, "_icon"):
            self._icon.set_color(color)
        if hasattr(self, "_name_lbl"):
            weight = "600" if is_bold else "500"
            self._name_lbl.setStyleSheet(
                f"font-size: 11px; background: transparent; font-weight: {weight}; "
                f"letter-spacing: 0.2px; color: {color}; "
                f"font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;"
            )

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._refresh_style()


# ─────────────────────────────────────────────────────────────────────────────
#  Pill Toolbar — Docked at top-center
# ─────────────────────────────────────────────────────────────────────────────

class _ActionButton(QToolButton):
    """One segment of the exclusive action selector, in Qt logical pixels."""
    def __init__(self, action: CaptureAction, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 0, 7, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)
        self._icon = VectorIconWidget(action.value, self, size=16)
        self._name_lbl = QLabel(label, self)
        self._name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._name_lbl.setStyleSheet(
            "QLabel { background: transparent; color: #FFFFFF; font-size: 11px; font-weight: 500; }"
            "QLabel:disabled { color: #929AA8; }")
        layout.addWidget(self._icon)
        layout.addWidget(self._name_lbl)
        # Respect actual font metrics without multiplying by the screen DPR.
        self.setMinimumWidth(max(103, self._name_lbl.sizeHint().width() + 35))
        self.setStyleSheet("""
            QToolButton {
                background: #242A33; border: 1px solid transparent;
                border-radius: 6px;
            }
            QToolButton:hover { background: #2D3440; border-color: #596477; }
            QToolButton:pressed { background: #364155; border-color: #8994EC; }
            QToolButton:checked { background: #303653; border-color: #8994EC; }
            QToolButton:checked:hover { background: #3C4567; border-color: #B0B9FF; }
            QToolButton:focus { border: 2px solid #B0B9FF; }
            QToolButton:disabled { background: #1D2128; border-color: #343B47; }
        """)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.EnabledChange and hasattr(self, '_icon'):
            self._icon.set_color('#FFFFFF' if self.isEnabled() else '#929AA8')


class SnipToolbar(QFrame):
    """
    Precision pill-shaped toolbar docked at the top of the overlay.
    Design language inspired by Linear, Raycast, and Arc:
      - Clean vector brand badge
      - Exclusive action segments (Screenshot vs Extract Text)
      - Vector line-art mode buttons (Rectangle, Window, Full Screen)
      - Integrated dismiss button (✕)
    """

    mode_changed     = Signal(SnipMode)
    action_changed   = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_mode = SnipMode.RECTANGULAR
        self._buttons: dict[SnipMode, _ModeButton] = {}
        self._build()

    def _build(self) -> None:
        self.setObjectName("snip_toolbar")
        # Paint an opaque styled interior into the translucent overlay. Do not
        # mark this rounded child as opaque (its corners still reveal the parent).
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame#snip_toolbar {
                background: #181B20;
                border: 1px solid #454D5B;
                border-radius: 14px;
            }
        """)

        # Subtle separation without a translucent/glass surface
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(6)
        outer.setAlignment(Qt.AlignCenter)

        # ── 1. Sleek Brand Badge ──────────────────────────────────────────────
        brand_box = QWidget()
        brand_box.setStyleSheet("background: transparent;")
        bl = QHBoxLayout(brand_box)
        bl.setContentsMargins(4, 0, 4, 0)
        bl.setSpacing(6)
        bl.setAlignment(Qt.AlignCenter)

        brand_icon = VectorIconWidget("brand", brand_box, size=16, color="#FFFFFF")
        bl.addWidget(brand_icon)

        brand_text = QLabel("Snip")
        brand_text.setStyleSheet("""
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.4px;
            font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
            background: transparent;
        """)
        bl.addWidget(brand_text)
        outer.addWidget(brand_box)

        # ── Divider 1 ────────────────────────────────────────────────────────
        outer.addWidget(self._create_divider())

        # Two adjacent exclusive segments; changing action never captures.
        self.action_toggle = QFrame(self)
        self.action_toggle.setObjectName('action_toggle')
        self.action_toggle.setStyleSheet("""
            QFrame#action_toggle {
                background: #242A33; border: 1px solid #454D5B; border-radius: 9px;
            }
        """)
        action_layout = QHBoxLayout(self.action_toggle)
        action_layout.setContentsMargins(3, 3, 3, 3)
        action_layout.setSpacing(2)
        self._action_group = QButtonGroup(self)
        self._action_group.setExclusive(True)
        self.action_buttons = {}
        for action, label in ((CaptureAction.SCREENSHOT, 'Screenshot'),
                              (CaptureAction.EXTRACT_TEXT, 'Extract Text')):
            button = _ActionButton(action, label, self.action_toggle)
            self._action_group.addButton(button)
            self.action_buttons[action.value] = button
            action_layout.addWidget(button)
            button.toggled.connect(
                lambda checked, value=action.value: self.action_changed.emit(value) if checked else None)
        self.action_buttons[CaptureAction.SCREENSHOT.value].setChecked(True)
        outer.addWidget(self.action_toggle)

        # ── Divider 2 ────────────────────────────────────────────────────────
        outer.addWidget(self._create_divider())

        # ── 3. Mode Buttons ───────────────────────────────────────────────────
        modes = [
            (SnipMode.RECTANGULAR, "Rectangle",  True),
            (SnipMode.WINDOW,      "Window",     True),
            (SnipMode.FULLSCREEN,  "Full Screen", True),
        ]

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for mode, label, enabled in modes:
            btn = _ModeButton(mode, label, enabled=enabled)
            btn.setToolTip(label)
            btn.clicked.connect(lambda checked, m=mode, b=btn: self._on_btn_clicked(m, b))
            self._buttons[mode] = btn
            self._btn_group.addButton(btn)
            outer.addWidget(btn)

        # Pre-select RECTANGULAR by default
        self._buttons[SnipMode.RECTANGULAR].setChecked(True)

        # ── Divider 3 ────────────────────────────────────────────────────────
        outer.addWidget(self._create_divider())

        # ── 4. Cancel Button ──────────────────────────────────────────────────
        close_btn = QPushButton()
        close_btn.setFixedSize(QSize(32, 32))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Cancel (Esc)")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 7px;
            }
            QPushButton:hover {
                background: #48282E;
                border: 1px solid #BF707B;
            }
            QPushButton:pressed {
                background: #65313B;
            }
        """)

        # Clean vector close icon inside close button
        cl = QHBoxLayout(close_btn)
        cl.setContentsMargins(0, 0, 0, 0)
        self._close_icon = VectorIconWidget("close", close_btn, size=14, color="#FFFFFF")
        cl.addWidget(self._close_icon, 0, Qt.AlignCenter)

        close_btn.clicked.connect(self.cancel_requested)
        outer.addWidget(close_btn)

        self.adjustSize()

    @staticmethod
    def _create_divider() -> QFrame:
        div = QFrame()
        div.setFixedSize(1, 24)
        div.setStyleSheet("""
            background: #454D5B;
            border: none;
        """)
        return div

    def _on_btn_clicked(self, mode: SnipMode, btn: _ModeButton) -> None:
        for m, b in self._buttons.items():
            b.setChecked(m == mode)
        self._current_mode = mode
        self.mode_changed.emit(mode)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def current_mode(self) -> SnipMode:
        return self._current_mode

    @property
    def current_action(self) -> str:
        return next(action for action, button in self.action_buttons.items() if button.isChecked())

    def set_action(self, action: str) -> None:
        button = self.action_buttons.get(action)
        if button is not None:
            button.setChecked(True)

    def select_mode(self, mode: SnipMode) -> None:
        if mode in self._buttons and self._buttons[mode].isEnabled():
            self._buttons[mode].setChecked(True)
            self._current_mode = mode


# ─────────────────────────────────────────────────────────────────────────────
#  Main Overlay Widget
# ─────────────────────────────────────────────────────────────────────────────

class Overlay(QWidget):
    """
    Frameless fullscreen overlay covering all monitors.

    Signals
    -------
    area_selected(QRect)
        Emitted when the user completes a rectangular drag selection.
    fullscreen_capture_requested()
        Emitted when the user clicks "Full Screen" in the toolbar.
    window_capture_requested()
        Emitted when the user clicks "Window" in the toolbar.
    cancelled()
        Emitted when the user presses Esc or clicks ×.
    """

    area_selected                = Signal(QRect)
    fullscreen_capture_requested = Signal()
    window_capture_requested     = Signal()
    cancelled                    = Signal()

    delivery_requested = Signal()

    def __init__(
        self,
        bg_pixmap: QPixmap | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.bg_pixmap   = bg_pixmap
        self.start_point = QPoint()
        self.end_point   = QPoint()
        self.selecting   = False
        self.selected_rect: QRect | None = None
        self._mode       = SnipMode.RECTANGULAR
        self._processing = False

        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Build the embedded toolbar
        self._toolbar = SnipToolbar(self)
        self._toolbar.mode_changed.connect(self._on_mode_changed)
        self._toolbar.cancel_requested.connect(self.cancel_selection)

        self._update_cursor()

    @property
    def capture_action(self) -> str:
        """Current capture action selected in toolbar: 'screenshot' or 'extract_text'."""
        return self._toolbar.current_action

    # ── Show helpers ──────────────────────────────────────────────────────────

    def _get_virtual_geometry(self) -> QRect:
        if hasattr(self, '_display_geometry'):
            return QRect(self._display_geometry)
        total = QRect()
        for screen in QGuiApplication.screens():
            total = total.united(screen.geometry())
        if total.isEmpty():
            primary = QGuiApplication.primaryScreen()
            total = primary.geometry() if primary else QRect(0, 0, 1920, 1080)
        return total

    def showFullScreenOverlay(self) -> None:
        """Position overlay to cover all connected screens and show."""
        vg = self._get_virtual_geometry()
        logger.debug("Overlay virtual geometry: %s", vg)
        self.setGeometry(vg)
        self.resize(vg.size())
        self.move(vg.topLeft())
        self.showFullScreen()
        self.setGeometry(vg)
        self.raise_()
        self.activateWindow()
        self._position_toolbar()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        vg = self._get_virtual_geometry()
        if not vg.isEmpty() and self.geometry() != vg:
            self.setGeometry(vg)
            self.resize(vg.size())
        self._position_toolbar()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_toolbar()

    def _position_toolbar(self) -> None:
        self._toolbar.adjustSize()
        tw = self._toolbar.width()
        # Centre horizontally, 20 px from top for modern sleek look
        x = max(0, (self.width() - tw) // 2)
        y = 20
        self._toolbar.move(x, y)
        self._toolbar.raise_()

    # ── Mode handling ─────────────────────────────────────────────────────────

    @Slot(SnipMode)
    def _on_mode_changed(self, mode: SnipMode) -> None:
        self._mode = mode
        self._update_cursor()

        if mode == SnipMode.FULLSCREEN:
            self.fullscreen_capture_requested.emit()
        elif mode == SnipMode.WINDOW:
            self.hide()
            self.window_capture_requested.emit()

    def _update_cursor(self) -> None:
        if self._mode == SnipMode.RECTANGULAR:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    # ── Mouse events (rectangular selection) ─────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if self._processing:
            return
        if self._mode != SnipMode.RECTANGULAR:
            return
        if event.button() == Qt.LeftButton:
            # Ignore clicks inside the toolbar area
            if self._toolbar.geometry().contains(event.position().toPoint()):
                return
            self.start_point = event.position().toPoint()
            self.end_point   = self.start_point
            self.selecting   = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self.selecting:
            self.end_point = event.position().toPoint()
            self.update()

    def set_processing(self, processing=True):
        self._processing = processing
        for mode, button in self._toolbar._buttons.items():
            button.setEnabled(not processing and mode != SnipMode.FREEFORM)
        self._toolbar.action_toggle.setEnabled(not processing)
        self.setCursor(Qt.BusyCursor if processing else Qt.CrossCursor)

    def mouseReleaseEvent(self, event) -> None:
        if self._processing:
            if event.button() == Qt.LeftButton:
                self.delivery_requested.emit()
            return
        if event.button() == Qt.LeftButton and self.selecting:
            self.end_point = event.position().toPoint()
            self.selecting = False
            self.confirm_selection()

    def keyPressEvent(self, event) -> None:
        if self._processing:
            if event.key() == Qt.Key_Escape:
                self.cancel_selection()
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.delivery_requested.emit()
            return
        if event.key() == Qt.Key_Escape:
            self.cancel_selection()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self.selecting or not self.get_selection_rect().isEmpty():
                self.selecting = False
                self.confirm_selection()

    # ── Selection logic ───────────────────────────────────────────────────────

    def get_selection_rect(self) -> QRect:
        if self.start_point == self.end_point:
            return QRect()
        return QRect(min(self.start_point.x(), self.end_point.x()),
                     min(self.start_point.y(), self.end_point.y()),
                     abs(self.start_point.x() - self.end_point.x()) + 1,
                     abs(self.start_point.y() - self.end_point.y()) + 1)

    def confirm_selection(self) -> None:
        rect = self.get_selection_rect()
        if rect.width() > 2 and rect.height() > 2:
            self.selected_rect = rect
            self.area_selected.emit(rect)
            if not self._processing:
                self.close()
        else:
            self.selected_rect = None
            self.close()
            self.cancelled.emit()

    def cancel_selection(self) -> None:
        self.selected_rect = None
        self.close()
        self.cancelled.emit()

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.get_selection_rect()
        has_sel = not rect.isEmpty() and rect.width() > 1 and rect.height() > 1

        if self.bg_pixmap and not self.bg_pixmap.isNull():
            # 1. Draw desktop screenshot at full clarity
            source_rect = getattr(self, 'bg_source_rect', QRectF(self.bg_pixmap.rect()))
            painter.drawPixmap(QRectF(self.rect()), self.bg_pixmap, source_rect)

            # 2. Dim everything EXCEPT the live selection (OddEven rule)
            dim_path = QPainterPath()
            dim_path.setFillRule(Qt.OddEvenFill)
            dim_path.addRect(self.rect())
            if has_sel:
                dim_path.addRect(rect)
            painter.fillPath(dim_path, QColor(0, 0, 0, 135))
        else:
            # Fallback: solid dim
            dim_path = QPainterPath()
            dim_path.setFillRule(Qt.OddEvenFill)
            dim_path.addRect(self.rect())
            if has_sel:
                dim_path.addRect(rect)
            painter.fillPath(dim_path, QColor(0, 0, 0, 135))

        if has_sel:
            # 3. Selection border — crisp white with subtle blue-indigo highlight
            painter.setPen(QPen(QColor(255, 255, 255, 240), 1.5, Qt.SolidLine))
            painter.drawRect(rect)

            # 4. Dimensions badge (Linear style)
            pixel_size = getattr(self, 'selection_pixel_size', None)
            size = pixel_size() if pixel_size is not None else (rect.width(), rect.height())
            dim_text = f"{size[0]:g} × {size[1]:g}" if size else 'Invalid area'
            font = QFont("Inter", 9, QFont.Medium)
            font.setStyleHint(QFont.SansSerif)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(dim_text)
            th = metrics.height()
            px, py = 7, 3
            bw, bh = tw + px * 2, th + py * 2

            bx = rect.right() - bw if rect.right() + bw > self.width() else rect.right() + 4
            by = rect.bottom() + 6 if rect.bottom() + bh + 10 < self.height() else rect.bottom() - bh - 4
            bx = max(4, bx)

            badge = QRect(round(bx), round(by), bw, bh)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.setBrush(QColor(17, 19, 26, 220))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(241, 245, 249, 230))
            painter.drawText(badge, Qt.AlignCenter, dim_text)

        painter.end()


# Backwards-compatible alias
SelectionOverlay = Overlay
