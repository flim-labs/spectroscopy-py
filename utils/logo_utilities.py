import os
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap, QIcon, QPainter
from PyQt6.QtCore import Qt
from utils.resource_path import resource_path

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path, '..'))


class OverlayWidget(QWidget):
    """A transparent widget that overlays a logo on its parent widget."""
    def __init__(self, parent=None):
        """Initializes the OverlayWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.imagePath = "assets/flimlabs-logo.png"  
        self.pixmap = QPixmap(self.imagePath).scaledToWidth(100)
        self.opacity = 0.3
        self.adjustSize()

    def paintEvent(self, event):
        """Paints the semi-transparent logo in the bottom-right corner.

        Args:
            event (QPaintEvent): The paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self.opacity)  # Set the painter opacity for translucent drawing
        x = self.width() - self.pixmap.width() - 10  # 10 pixels padding from the right edge
        y = self.height() - self.pixmap.height() - 20  # 20 pixels padding from the bottom edge
        painter.drawPixmap(x, y, self.pixmap)
        

class TitlebarIcon():
    """A utility class for setting the application's title bar icon."""
    @staticmethod
    def setup(window):
        """Sets the window icon for the given window.

        Args:
            window (QWidget): The window to which the icon will be applied.
        """
        icon_path = resource_path("assets/spectroscopy-logo.png")
        window.setWindowIcon(QIcon(icon_path))
