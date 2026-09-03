"""Selection overlay widget for rectangular screen capture."""

import logging

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget


logger = logging.getLogger(__name__)


class Overlay(QWidget):
    """Frameless translucent overlay covering all monitors for area selection."""

    area_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, bg_pixmap: QPixmap | None = None, parent: QWidget | None = None):
        super().__init__(parent)

        self.bg_pixmap = bg_pixmap
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selecting = False
        self.selected_rect: QRect | None = None

        # Standard top-level window flags for Wayland and X11 toplevel fullscreen surfaces
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    def _get_virtual_geometry(self) -> QRect:
        """Calculate the united virtual desktop geometry across all screens."""
        total_rect = QRect()
        for screen in QGuiApplication.screens():
            total_rect = total_rect.united(screen.geometry())

        if total_rect.isEmpty():
            primary = QGuiApplication.primaryScreen()
            total_rect = primary.geometry() if primary else QRect(0, 0, 1920, 1080)

        return total_rect

    def showFullScreenOverlay(self) -> None:
        """Position overlay to cover the virtual geometry of all connected screens."""
        virtual_rect = self._get_virtual_geometry()
        logger.debug("Configuring overlay with virtual geometry: %s", virtual_rect)

        # Set geometry before showing
        self.setGeometry(virtual_rect)
        self.resize(virtual_rect.size())
        self.move(virtual_rect.topLeft())

        self.showFullScreen()

        # Re-assert geometry and bring to front
        self.setGeometry(virtual_rect)
        self.raise_()
        self.activateWindow()

        logger.debug("Overlay displayed with active geometry: %s", self.geometry())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        virtual_rect = self._get_virtual_geometry()
        if not virtual_rect.isEmpty() and self.geometry() != virtual_rect:
            self.setGeometry(virtual_rect)
            self.resize(virtual_rect.size())

    def get_selection_rect(self) -> QRect:
        """Return the current normalized selection rectangle."""
        if self.start_point.isNull() or self.end_point.isNull():
            return QRect()
        return QRect(self.start_point, self.end_point).normalized()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.selecting = True
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

    def confirm_selection(self) -> None:
        """Confirm the selected region if it has valid area, otherwise cancel."""
        rect = self.get_selection_rect()
        if rect.width() > 2 and rect.height() > 2:
            self.selected_rect = rect
            self.area_selected.emit(rect)
        else:
            self.selected_rect = None
            self.cancelled.emit()
        self.close()

    def cancel_selection(self) -> None:
        """Cancel selection and close overlay."""
        self.selected_rect = None
        self.cancelled.emit()
        self.close()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.get_selection_rect()
        has_selection = not rect.isEmpty() and rect.width() > 1 and rect.height() > 1

        if self.bg_pixmap and not self.bg_pixmap.isNull():
            # Draw background screen snapshot
            painter.drawPixmap(self.rect(), self.bg_pixmap)

            # Dim everything outside the selection
            dim_path = QPainterPath()
            dim_path.addRect(self.rect())
            if has_selection:
                dim_path.addRect(rect)

            painter.fillPath(dim_path, QColor(0, 0, 0, 120))
        else:
            # Translucent dark overlay with cut-out
            if has_selection:
                painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                painter.fillRect(rect, Qt.transparent)
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            else:
                painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if has_selection:
            # Draw crisp border around the cut-out selection
            border_pen = QPen(QColor(255, 255, 255, 240), 1.5, Qt.SolidLine)
            painter.setPen(border_pen)
            painter.drawRect(rect)

            # Draw dimensions label near the cursor / selection corner
            dim_text = f"{rect.width()} × {rect.height()}"
            font = QFont("Sans-Serif", 9, QFont.Bold)
            painter.setFont(font)

            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(dim_text)
            text_height = metrics.height()

            badge_padding_x = 8
            badge_padding_y = 4
            badge_w = text_width + (badge_padding_x * 2)
            badge_h = text_height + (badge_padding_y * 2)

            # Position badge below bottom-right or above if near screen edge
            badge_x = rect.right() - badge_w if (rect.right() + badge_w > self.width()) else rect.right() + 4
            badge_y = rect.bottom() + 6 if (rect.bottom() + badge_h + 10 < self.height()) else rect.bottom() - badge_h - 4

            if badge_x < 4:
                badge_x = 4

            badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)

            # Draw rounded badge background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 25, 210))
            painter.drawRoundedRect(badge_rect, 4, 4)

            # Draw text inside badge
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_rect, Qt.AlignCenter, dim_text)

        painter.end()


# Maintain backwards compatibility with SelectionOverlay alias
SelectionOverlay = Overlay
