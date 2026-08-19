from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget


class SelectionOverlay(QWidget):

    def __init__(self):
        super().__init__()

        # Make the window cover the screen
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        # Make the background transparent
        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        # Allow mouse interaction
        self.setMouseTracking(True)

        self.start_point = QPoint()
        self.end_point = QPoint()

        self.selecting = False

    def showFullScreenOverlay(self):

        screen = (
            self.screen()
            or self.windowHandle().screen()
        )

        if screen:
            self.setGeometry(
                screen.geometry()
            )

        self.showFullScreen()

        self.raise_()

        self.activateWindow()

    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:

            self.start_point = (
                event.position().toPoint()
            )

            self.end_point = (
                event.position().toPoint()
            )

            self.selecting = True

            self.update()

    def mouseMoveEvent(self, event):

        if self.selecting:

            self.end_point = (
                event.position().toPoint()
            )

            self.update()

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.LeftButton:

            self.end_point = (
                event.position().toPoint()
            )

            self.selecting = False

            self.update()

            rectangle = QRect(
                self.start_point,
                self.end_point,
            ).normalized()

            print(
                "Selected area:",
                rectangle.x(),
                rectangle.y(),
                rectangle.width(),
                rectangle.height(),
            )

    def paintEvent(self, event):

        painter = QPainter(self)

        # Dark transparent overlay
        painter.fillRect(
            self.rect(),
            QColor(
                0,
                0,
                0,
                80,
            ),
        )

        # Draw selection rectangle
        if (
            not self.start_point.isNull()
            and not self.end_point.isNull()
        ):

            rectangle = QRect(
                self.start_point,
                self.end_point,
            ).normalized()

            # Clear the selected area
            painter.setCompositionMode(
                QPainter.CompositionMode_Clear
            )

            painter.fillRect(
                rectangle,
                Qt.transparent,
            )

            # Draw border
            painter.setCompositionMode(
                QPainter.CompositionMode_SourceOver
            )

            painter.setPen(
                QPen(
                    QColor(255, 255, 255),
                    2,
                )
            )

            painter.drawRect(
                rectangle
            )

        painter.end()

    def keyPressEvent(self, event):

        # Escape cancels selection
        if event.key() == Qt.Key_Escape:

            self.close()