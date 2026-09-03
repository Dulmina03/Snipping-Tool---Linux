"""Full-screen snipping overlay with Raycast/Linear-style vector toolbar."""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal, Slot
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
    QComboBox,
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
        color: QColor | str = QColor(226, 232, 240, 190),
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
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        QToolButton:pressed {
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.12);
        }
    """

    # Checked: desaturated indigo glass with luminous border (Linear style)
    _STYLE_CHECKED = """
        QToolButton {
            background: rgba(79, 70, 229, 0.28);
            border: 1px solid rgba(129, 140, 248, 0.65);
            border-radius: 8px;
            padding: 3px;
        }
        QToolButton:hover {
            background: rgba(79, 70, 229, 0.38);
            border: 1px solid rgba(165, 180, 252, 0.85);
        }
    """

    # Disabled: subtle muted ghost
    _STYLE_DISABLED = """
        QToolButton {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 3px;
        }
    """

    # Colors applied to vector icon and label text
    _COLOR_NORMAL   = "rgba(226, 232, 240, 0.75)"
    _COLOR_CHECKED  = "#FFFFFF"
    _COLOR_DISABLED = "rgba(255, 255, 255, 0.25)"

    def __init__(self, mode: SnipMode, label: str, enabled: bool = True):
        super().__init__()
        self.mode = mode
        self.setCheckable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 5, 4, 5)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignCenter)

        # 1. Vector Icon (QPainter line art)
        self._icon = VectorIconWidget(mode.value, self, size=20, color=self._COLOR_NORMAL)
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

class SnipToolbar(QFrame):
    """
    Precision pill-shaped toolbar docked at the top of the overlay.
    Design language inspired by Linear, Raycast, and Arc:
      - Clean vector brand badge
      - Muted dropdown for capture action (Screenshot vs Extract Text)
      - Vector line-art mode buttons (Rectangular, Freeform, Window, Full Screen)
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
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QFrame#snip_toolbar {
                background: rgba(17, 19, 26, 0.94);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
        """)

        # Soft atmospheric drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 190))
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

        brand_icon = VectorIconWidget("brand", brand_box, size=16, color="rgba(255, 255, 255, 0.75)")
        bl.addWidget(brand_icon)

        brand_text = QLabel("Snip")
        brand_text.setStyleSheet("""
            color: rgba(255, 255, 255, 0.85);
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

        # ── 2. Action Dropdown (Screenshot vs Extract Text) ───────────────────
        self.action_combo = QComboBox()
        self.action_combo.setObjectName("action_combo")
        self.action_combo.addItem("Screenshot", CaptureAction.SCREENSHOT.value)
        self.action_combo.addItem("Extract Text", CaptureAction.EXTRACT_TEXT.value)
        self.action_combo.setCurrentIndex(0)
        self.action_combo.setCursor(Qt.PointingHandCursor)
        self.action_combo.setFixedSize(QSize(118, 34))
        self.action_combo.setStyleSheet("""
            QComboBox#action_combo {
                background: rgba(255, 255, 255, 0.05);
                color: rgba(241, 245, 249, 0.90);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 7px;
                padding: 3px 24px 3px 10px;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
            }
            QComboBox#action_combo:hover {
                background: rgba(255, 255, 255, 0.09);
                border-color: rgba(255, 255, 255, 0.20);
                color: #FFFFFF;
            }
            QComboBox#action_combo:on {
                border-color: rgba(129, 140, 248, 0.65);
            }
            QComboBox#action_combo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
                background: transparent;
            }
            QComboBox#action_combo::down-arrow {
                image: none;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-top: 4.5px solid rgba(255, 255, 255, 0.65);
                margin-right: 8px;
            }
            QComboBox#action_combo QAbstractItemView {
                background-color: #151722;
                color: rgba(241, 245, 249, 0.90);
                selection-background-color: rgba(79, 70, 229, 0.35);
                selection-color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 4px;
                outline: none;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
            }
            QComboBox#action_combo QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 10px;
                border-radius: 5px;
                color: rgba(241, 245, 249, 0.90);
            }
            QComboBox#action_combo QAbstractItemView::item:selected {
                background-color: rgba(79, 70, 229, 0.35);
                color: #FFFFFF;
            }
        """)
        self.action_combo.currentIndexChanged.connect(
            lambda: self.action_changed.emit(self.current_action)
        )
        outer.addWidget(self.action_combo)

        # ── Divider 2 ────────────────────────────────────────────────────────
        outer.addWidget(self._create_divider())

        # ── 3. Mode Buttons ───────────────────────────────────────────────────
        modes = [
            (SnipMode.RECTANGULAR, "Rectangle",  True),
            (SnipMode.FREEFORM,    "Freeform",   False),  # disabled — coming soon
            (SnipMode.WINDOW,      "Window",     True),
            (SnipMode.FULLSCREEN,  "Full Screen", True),
        ]

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for mode, label, enabled in modes:
            btn = _ModeButton(mode, label, enabled=enabled)
            if not enabled:
                btn.setToolTip(f"{label} — coming soon")
            else:
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
                background: rgba(239, 68, 68, 0.16);
                border: 1px solid rgba(248, 113, 113, 0.30);
            }
            QPushButton:pressed {
                background: rgba(239, 68, 68, 0.26);
            }
        """)

        # Clean vector close icon inside close button
        cl = QHBoxLayout(close_btn)
        cl.setContentsMargins(0, 0, 0, 0)
        self._close_icon = VectorIconWidget("close", close_btn, size=14, color="rgba(255, 255, 255, 0.65)")
        cl.addWidget(self._close_icon, 0, Qt.AlignCenter)

        close_btn.clicked.connect(self.cancel_requested)
        outer.addWidget(close_btn)

        self.adjustSize()

    @staticmethod
    def _create_divider() -> QFrame:
        div = QFrame()
        div.setFixedSize(1, 24)
        div.setStyleSheet("""
            background: rgba(255, 255, 255, 0.08);
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
        data = self.action_combo.currentData()
        if data:
            return str(data)
        if "Extract Text" in self.action_combo.currentText():
            return CaptureAction.EXTRACT_TEXT.value
        return CaptureAction.SCREENSHOT.value

    def set_action(self, action: str) -> None:
        idx = self.action_combo.findData(action)
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)

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
            self.hide()
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

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.selecting:
            self.end_point = event.position().toPoint()
            self.selecting = False
            self.confirm_selection()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel_selection()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self.selecting or not self.get_selection_rect().isEmpty():
                self.selecting = False
                self.confirm_selection()

    # ── Selection logic ───────────────────────────────────────────────────────

    def get_selection_rect(self) -> QRect:
        if self.start_point.isNull() or self.end_point.isNull():
            return QRect()
        return QRect(self.start_point, self.end_point).normalized()

    def confirm_selection(self) -> None:
        rect = self.get_selection_rect()
        if rect.width() > 2 and rect.height() > 2:
            self.selected_rect = rect
            self.close()
            self.area_selected.emit(rect)
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
            painter.drawPixmap(self.rect(), self.bg_pixmap)

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
            dim_text = f"{rect.width()} × {rect.height()}"
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

            badge = QRect(bx, by, bw, bh)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.setBrush(QColor(17, 19, 26, 220))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(241, 245, 249, 230))
            painter.drawText(badge, Qt.AlignCenter, dim_text)

        painter.end()


# Backwards-compatible alias
SelectionOverlay = Overlay
