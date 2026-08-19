import sys

from PySide6.QtWidgets import QApplication

from ui.selection_overlay import SelectionOverlay


app = QApplication(sys.argv)

overlay = SelectionOverlay()

overlay.showFullScreenOverlay()

sys.exit(app.exec())