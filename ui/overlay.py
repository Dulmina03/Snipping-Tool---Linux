"""Full-screen snipping overlay with Windows-style top-center mode toolbar."""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal, Slot
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
#  Mode button (a QToolButton styled as a toggle)
# ─────────────────────────────────────────────────────────────────────────────

class _ModeButton(QToolButton):
    """Pill-toolbar icon button with icon glyph and bold label text."""

    # Normal: crisp white text on near-transparent dark pill button
    _STYLE_NORMAL = """
        QToolButton {
            background: rgba(255,255,255,0.07);
            color: rgba(255,255,255,0.90);
            border: none;
            border-radius: 10px;
            padding: 6px 10px;
            font-size: 13px;
            font-weight: 700;
        }
        QToolButton:hover {
            background: rgba(255,255,255,0.18);
            color: #FFFFFF;
        }
    """
    # Checked: vivid violet with white border — unmistakably active
    _STYLE_CHECKED = """
        QToolButton {
            background: rgba(108,99,255,1.0);
            color: #FFFFFF;
            border: 2px solid rgba(255,255,255,0.60);
            border-radius: 10px;
            padding: 4px 8px;
            font-size: 13px;
            font-weight: 700;
        }
        QToolButton:hover {
            background: rgba(130,120,255,1.0);
            color: #FFFFFF;
        }
    """
    # Disabled: dimmed but readable — 42% white
    _STYLE_DISABLED = """
        QToolButton {
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.42);
            border: none;
            border-radius: 10px;
            padding: 6px 10px;
            font-size: 13px;
            font-weight: 700;
        }
    """

    # Per-state text colors applied directly to child QLabels
    # (Qt does not propagate `color` from QToolButton stylesheet to child widgets)
    _COLOR_NORMAL   = "rgba(255,255,255,0.90)"
    _COLOR_CHECKED  = "#FFFFFF"
    _COLOR_DISABLED = "rgba(255,255,255,0.42)"

    def __init__(self, icon_glyph: str, label: str, mode: SnipMode, enabled: bool = True):
        super().__init__()
        self.mode = mode
        self.setCheckable(True)
        # NOTE: do NOT call setChecked here — _glyph_lbl/_name_lbl don't exist yet.
        # _refresh_style() is called at the end of __init__ instead.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        self._glyph_lbl = QLabel(icon_glyph)
        self._glyph_lbl.setAlignment(Qt.AlignCenter)
        self._glyph_lbl.setStyleSheet("font-size: 22px; background: transparent;")
        self._glyph_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self._glyph_lbl)

        # Bold and slightly larger font size (bumped up by 2px to 13px)
        self._name_lbl = QLabel(label)
        self._name_lbl.setAlignment(Qt.AlignCenter)
        self._name_lbl.setStyleSheet(
            "font-size: 13px; background: transparent; font-weight: 700; letter-spacing: 0.2px;"
        )
        self._name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_lbl)

        self.setMinimumSize(QSize(90, 64))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.setEnabled(enabled)

        # Apply initial style now that labels exist
        self._refresh_style()

    def _refresh_style(self) -> None:
        if not self.isEnabled():
            self.setStyleSheet(self._STYLE_DISABLED)
            self._set_label_color(self._COLOR_DISABLED)
        elif self.isChecked():
            self.setStyleSheet(self._STYLE_CHECKED)
            self._set_label_color(self._COLOR_CHECKED)
        else:
            self.setStyleSheet(self._STYLE_NORMAL)
            self._set_label_color(self._COLOR_NORMAL)

    def _set_label_color(self, color: str) -> None:
        """Push an explicit color onto child labels (Qt doesn't inherit from button stylesheet)."""
        if not hasattr(self, "_glyph_lbl"):
            return  # called before labels exist (during super().__init__)
        self._glyph_lbl.setStyleSheet(
            f"font-size: 22px; background: transparent; color: {color};"
        )
        self._name_lbl.setStyleSheet(
            f"font-size: 13px; background: transparent; font-weight: 700; "
            f"letter-spacing: 0.2px; color: {color};"
        )

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._refresh_style()


# ─────────────────────────────────────────────────────────────────────────────
#  Pill toolbar – docked at top-center of the screen
# ─────────────────────────────────────────────────────────────────────────────

class SnipToolbar(QFrame):
    """
    Semi-transparent pill-shaped toolbar docked at the top of the overlay.
    Contains:
      - Mode dropdown: "Screenshot" vs "Extract Text"
      - Mode buttons: Rectangular, Freeform (disabled), Window, Full Screen
      - Cancel button: ✕
    """

    mode_changed    = Signal(SnipMode)
    action_changed  = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_mode = SnipMode.RECTANGULAR
        self._buttons: dict[SnipMode, _ModeButton] = {}
        self._build()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setObjectName("snip_toolbar")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QFrame#snip_toolbar {
                background: rgba(12, 12, 20, 0.96);
                border: 1.5px solid rgba(255,255,255,0.18);
                border-radius: 20px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 220))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(18, 12, 18, 12)
        outer.setSpacing(8)

        # ── Snip tool branding ────────────────────────────────────────────────
        brand = QLabel("✂  Snip")
        brand.setStyleSheet("""
            color: rgba(255,255,255,0.85);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.6px;
            padding-right: 4px;
        """)
        outer.addWidget(brand)

        # ── Mode dropdown (Screenshot vs Extract Text) at the LEFT ─────────────
        self.action_combo = QComboBox()
        self.action_combo.setObjectName("action_combo")
        self.action_combo.addItem("Screenshot", CaptureAction.SCREENSHOT.value)
        self.action_combo.addItem("Extract Text", CaptureAction.EXTRACT_TEXT.value)
        self.action_combo.setCurrentIndex(0)
        self.action_combo.setCursor(Qt.PointingHandCursor)
        self.action_combo.setStyleSheet("""
            QComboBox#action_combo {
                background: rgba(255, 255, 255, 0.09);
                color: #FFFFFF;
                border: 1.5px solid rgba(255, 255, 255, 0.22);
                border-radius: 10px;
                padding: 6px 28px 6px 14px;
                font-size: 13px;
                font-weight: 700;
                min-width: 125px;
                min-height: 38px;
            }
            QComboBox#action_combo:hover {
                background: rgba(255, 255, 255, 0.18);
                border-color: rgba(255, 255, 255, 0.45);
            }
            QComboBox#action_combo:on {
                border-color: #6C63FF;
            }
            QComboBox#action_combo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border: none;
                background: transparent;
            }
            QComboBox#action_combo::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #FFFFFF;
                margin-right: 10px;
            }
            QComboBox#action_combo QAbstractItemView {
                background-color: #181824;
                color: #FFFFFF;
                selection-background-color: #6C63FF;
                selection-color: #FFFFFF;
                border: 1.5px solid rgba(255, 255, 255, 0.25);
                border-radius: 10px;
                padding: 6px;
                outline: none;
                font-size: 13px;
                font-weight: 700;
            }
            QComboBox#action_combo QAbstractItemView::item {
                min-height: 34px;
                padding: 6px 12px;
                border-radius: 6px;
                color: #FFFFFF;
            }
            QComboBox#action_combo QAbstractItemView::item:selected {
                background-color: #6C63FF;
                color: #FFFFFF;
            }
        """)
        self.action_combo.currentIndexChanged.connect(
            lambda: self.action_changed.emit(self.current_action)
        )
        outer.addWidget(self.action_combo)

        # ── Vertical divider ─────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("background: rgba(255,255,255,0.20); min-width:1px; max-width:1px; margin: 6px 8px; border: none;")
        outer.addWidget(div)

        # ── Mode buttons ──────────────────────────────────────────────────────
        modes = [
            ("▭",   "Rectangular", SnipMode.RECTANGULAR, True),
            ("✏",   "Freeform",    SnipMode.FREEFORM,    False),  # disabled – coming soon
            ("⬜",  "Window",      SnipMode.WINDOW,      True),
            ("⛶",   "Full Screen", SnipMode.FULLSCREEN,  True),
        ]

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for glyph, label, mode, enabled in modes:
            btn = _ModeButton(glyph, label, mode, enabled=enabled)
            if not enabled:
                btn.setToolTip(f"{label} — coming soon")
            else:
                btn.setToolTip(label)
                btn.clicked.connect(lambda checked, m=mode, b=btn: self._on_btn_clicked(m, b))
            self._buttons[mode] = btn
            self._btn_group.addButton(btn)
            outer.addWidget(btn)

        # Pre-select RECTANGULAR
        self._buttons[SnipMode.RECTANGULAR].setChecked(True)

        # ── Divider + Cancel ─────────────────────────────────────────────────
        div2 = QFrame()
        div2.setFrameShape(QFrame.VLine)
        div2.setStyleSheet("background: rgba(255,255,255,0.20); min-width:1px; max-width:1px; margin: 6px 8px; border: none;")
        outer.addWidget(div2)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(QSize(38, 38))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Cancel (Esc)")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255,255,255,0.85);
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(224, 108, 117, 0.80);
                color: #FFFFFF;
            }
        """)
        close_btn.clicked.connect(self.cancel_requested)
        outer.addWidget(close_btn)

        self.adjustSize()

    def _on_btn_clicked(self, mode: SnipMode, btn: _ModeButton) -> None:
        # Update visual state
        for m, b in self._buttons.items():
            b.setChecked(m == mode)
        self._current_mode = mode
        self.mode_changed.emit(mode)

    # ── Public API ─────────────────────────────────────────────────────────────

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
#  Main overlay widget
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

    area_selected               = Signal(QRect)
    fullscreen_capture_requested = Signal()
    window_capture_requested    = Signal()
    cancelled                   = Signal()

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

        # Build the embedded toolbar (child widget)
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
        # Centre horizontally, 24 px from top
        x = max(0, (self.width() - tw) // 2)
        y = 24
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
        # RECTANGULAR: wait for mouse drag
        # FREEFORM: disabled, never fires

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
            painter.fillPath(dim_path, QColor(0, 0, 0, 130))
        else:
            # Fallback: solid dim
            dim_path = QPainterPath()
            dim_path.setFillRule(Qt.OddEvenFill)
            dim_path.addRect(self.rect())
            if has_sel:
                dim_path.addRect(rect)
            painter.fillPath(dim_path, QColor(0, 0, 0, 130))

        if has_sel:
            # 3. Selection border
            painter.setPen(QPen(QColor(255, 255, 255, 240), 1.5, Qt.SolidLine))
            painter.drawRect(rect)

            # 4. Dimensions badge
            dim_text = f"{rect.width()} × {rect.height()}"
            font = QFont("Sans-Serif", 10, QFont.Bold)
            painter.setFont(font)
            metrics  = painter.fontMetrics()
            tw = metrics.horizontalAdvance(dim_text)
            th = metrics.height()
            px, py = 8, 4
            bw, bh = tw + px * 2, th + py * 2

            bx = rect.right() - bw if rect.right() + bw > self.width() else rect.right() + 4
            by = rect.bottom() + 6 if rect.bottom() + bh + 10 < self.height() else rect.bottom() - bh - 4
            bx = max(4, bx)

            badge = QRect(bx, by, bw, bh)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 25, 210))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge, Qt.AlignCenter, dim_text)

        painter.end()


# Backwards-compatible alias
SelectionOverlay = Overlay
