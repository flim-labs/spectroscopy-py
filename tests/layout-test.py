import sys
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QFont, QPen, QTextOption


class GradientText(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Gradient Text")
        self.setFont(QFont("Arial", 20))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Define the gradient for the text
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("red"))  # Start color
        gradient.setColorAt(1.0, QColor("blue"))  # End color

        # Set the painter to use the gradient for drawing text
        painter.setPen(QPen(gradient, 0))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw the text
        painter.drawText(QRectF(0, 0, self.width(), self.height()), self.text(),
                         QTextOption(Qt.AlignmentFlag.AlignCenter))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setGeometry(300, 300, 280, 170)
        self.setWindowTitle('Gradient Text Example')

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Add the gradient text label to the window
        gradient_text_label = GradientText()
        layout.addWidget(gradient_text_label)

        self.show()


def main():
    app = QApplication(sys.argv)
    ex = MainWindow()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
