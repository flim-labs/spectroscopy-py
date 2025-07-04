from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QPen, QTextOption
from PyQt6.QtWidgets import QLabel


class GradientText(QLabel):
    """
    A QLabel subclass that renders its text with a linear gradient.

    It also provides a simple shadow effect when the label is clicked.
    """
    def __init__(self, parent=None, text="", colors: list[(float, str)] = None, stylesheet=""):
        """
        Initializes the GradientText widget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            text (str, optional): The text to display. Defaults to "".
            colors (list[(float, str)], optional): A list of tuples defining the gradient.
                                                   Each tuple contains a position (0.0 to 1.0) and a color string.
                                                   Defaults to a red-to-blue gradient.
            stylesheet (str, optional): A CSS stylesheet to apply to the label. Defaults to "".
        """
        super().__init__(parent)
        self.setText(text)
        self.setStyleSheet(stylesheet)
        self.colors = colors if colors else [(0.0, "red"), (1.0, "blue")]
        self.draw_shadow = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """
        Handles the mouse press event to enable the shadow effect.

        Args:
            event: The mouse press event.
        """
        self.draw_shadow = True
        self.update()

    def mouseReleaseEvent(self, event):
        """
        Handles the mouse release event to disable the shadow effect.

        Args:
            event: The mouse release event.
        """
        self.draw_shadow = False
        self.update()

    def paintEvent(self, event):
        """
        Paints the label's text with a gradient and an optional shadow.

        Args:
            event: The paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setWindow(0, 0, self.width() + 6, self.height() + 3)

        if self.draw_shadow:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("white"), 0))
            painter.drawText(QRectF(3, -2, self.width(), self.height()), self.text(),
                             QTextOption(Qt.AlignmentFlag.AlignLeft))

        gradient = QLinearGradient(0, 0, self.width(), self.height())
        for position, color in self.colors:
            gradient.setColorAt(position, QColor(color))
        painter.setPen(QPen(gradient, 0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(QRectF(0, 0, self.width(), self.height()), self.text(),
                         QTextOption(Qt.AlignmentFlag.AlignLeft))
