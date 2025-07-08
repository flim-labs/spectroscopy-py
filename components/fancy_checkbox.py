from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QMouseEvent,
    QIcon,
)
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

SELECTED_COLOR = "#8d4ef2"
SELECTED_HOVER_COLOR = "#0053a4"
DISABLED_SELECTED_COLOR = "#2E2E2E"
UNSELECTED_COLOR = "transparent"
DISABLED_COLOR = "#3c3c3c"
TEXT_COLOR = "#FFFFFF"


CHECKED_COLOR = "#FF4242"
UNCHECKED_COLOR = "lightgrey"

SELECTED_COLOR_BUTTON = "#11468F"


class FancyCheckbox(QWidget):
    """
    A composite widget that combines a custom Checkbox with a QLabel.
    
    Provides a more visually appealing checkbox with an associated text label.
    The state of the checkbox can be toggled by clicking either the checkbox
    or the label.

    Signals:
        toggled (pyqtSignal): Emitted when the checkbox state changes.
    """
    toggled = pyqtSignal(bool)  # Signal to emit when the checkbox state changes

    def __init__(self, text="", parent=None):
        """
        Initializes the FancyCheckbox widget.

        Args:
            text (str, optional): The text for the label. Defaults to "".
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(
            0, 0, 0, 0
        )  # Remove margins around the checkbox and label
        self.layout.setSpacing(5)  # Set spacing between checkbox and label

        self.checkbox = Checkbox(self)
        self.label = QLabel(text, self)

        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)

        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.label)

        self.label.mousePressEvent = (
            self.checkbox.mousePressEvent
        )  # Forward mousePressEvent from label to checkbox
        self.checkbox.toggled.connect(self.emit_toggled_signal)

    def emit_toggled_signal(self, checked):
        """
        Emits the toggled signal with the new checked state.

        Args:
            checked (bool): The new state of the checkbox.
        """
        self.toggled.emit(
            checked
        )

    def is_checked(self):
        """
        Returns the current checked state of the checkbox.

        Returns:
            bool: True if checked, False otherwise.
        """
        return self.checkbox.is_checked()

    def set_checked(self, checked):
        """
        Sets the checked state of the checkbox.

        Args:
            checked (bool): The desired checked state.
        """
        self.checkbox.set_checked(checked)

    def set_text(self, text):
        """
        Sets the text of the label.

        Args:
            text (str): The new text for the label.
        """
        self.label.setText(text)

    def setEnabled(self, enabled):
        """
        Enables or disables the checkbox and its label.

        Args:
            enabled (bool): True to enable, False to disable.
        """
        self.checkbox.setEnabled(enabled)
        self.label.setEnabled(enabled)


class Checkbox(QWidget):
    """
    A custom-drawn, circular checkbox widget.

    This widget provides a visually distinct checkbox that can be toggled
    on and off. It supports enabled and disabled states.

    Signals:
        toggled (pyqtSignal): Emitted when the checkbox state changes.
    """
    toggled = pyqtSignal(bool)  # Signal to emit when the checkbox state changes

    def __init__(self, parent=None):
        """
        Initializes the Checkbox widget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setFixedSize(20, 20)  # Set the size of the checkbox
        self.checked = False
        self.enabled = True

    def paintEvent(self, event):
        """
        Paints the checkbox.

        Draws a circle, which is filled when the checkbox is checked.
        The color changes based on the enabled/disabled state.

        Args:
            event: The paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.checked:
            outer_color = QColor(CHECKED_COLOR if self.enabled else DISABLED_COLOR)
        else:
            outer_color = QColor(CHECKED_COLOR if self.enabled else DISABLED_COLOR)
        painter.setPen(QPen(outer_color, 1))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawEllipse(1, 1, 18, 18)
        if self.checked:
            inner_color = QColor(CHECKED_COLOR if self.enabled else DISABLED_COLOR)
            painter.setBrush(QBrush(inner_color))
            painter.drawEllipse(4, 4, 12, 12)

    def mousePressEvent(self, event: QMouseEvent):
        """
        Handles mouse press events to toggle the checkbox state.

        Args:
            event (QMouseEvent): The mouse press event.
        """
        if event.button() == Qt.MouseButton.LeftButton and self.enabled:
            self.checked = not self.checked
            self.update()  # Trigger a repaint
            self.toggled.emit(self.checked)  # Emit the toggled signal

    def is_checked(self):
        """
        Returns the current checked state.

        Returns:
            bool: True if checked, False otherwise.
        """
        return self.checked

    def set_checked(self, checked):
        """
        Sets the checked state of the checkbox.

        Args:
            checked (bool): The desired checked state.
        """
        if self.checked != checked:
            self.checked = checked
            self.update()  # Trigger a repaint

    def setEnabled(self, enabled):
        """
        Enables or disables the checkbox.

        Args:
            enabled (bool): True to enable, False to disable.
        """
        if self.enabled != enabled:
            self.enabled = enabled
            self.update()  # Trigger a repaint


class FancyButton(QPushButton):
    """
    A custom QPushButton that can be toggled between a selected and unselected state.

    This button changes its background color to indicate whether it is selected.
    It supports custom colors for selected, unselected, hover, and pressed states.
    """
    def __init__(
        self,
        text="",
        icon_path=None,
        parent=None,
        selected_color=SELECTED_COLOR_BUTTON,
        unselected_color=UNSELECTED_COLOR,
        hover_color=SELECTED_HOVER_COLOR,
        pressed_color="#003d7a",
    ):
        """
        Initializes the FancyButton.

        Args:
            text (str, optional): The button text. Defaults to "".
            icon_path (str, optional): Path to an icon for the button. Defaults to None.
            parent (QWidget, optional): The parent widget. Defaults to None.
            selected_color (str, optional): Background color when selected. Defaults to SELECTED_COLOR_BUTTON.
            unselected_color (str, optional): Background color when not selected. Defaults to UNSELECTED_COLOR.
            hover_color (str, optional): Background color on hover. Defaults to SELECTED_HOVER_COLOR.
            pressed_color (str, optional): Background color when pressed. Defaults to "#003d7a".
        """
        super().__init__(text, parent)
        self.selected = False  # Track the selected state
        self.selected_color = selected_color
        self.unselected_color = unselected_color
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.initUI(icon_path)

    def initUI(self, icon_path):
        """
        Initializes the UI of the button.

        Args:
            icon_path (str): Path to the icon, if any.
        """
        if icon_path:
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(24, 24))  # Adjust icon size as needed
        self.setFlat(True)  # Set the button to flat style
        self.updateStyleSheet()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, selected):
        """
        Sets the selected state of the button and updates its style.

        Args:
            selected (bool): True to select the button, False to deselect.
        """
        self.selected = selected
        self.updateStyleSheet()

    def setEnabled(self, enabled):
        """
        Enables or disables the button and updates its style.

        Args:
            enabled (bool): True to enable, False to disable.
        """
        super().setEnabled(enabled)
        self.updateStyleSheet()

    def updateStyleSheet(self):
        """
        Updates the button's stylesheet based on its current state (selected, enabled).
        """
        bg_color = self.selected_color if self.selected else self.unselected_color
        color = "#3b3b3b" if not self.selected else "transparent"
        if not self.isEnabled():
            bg_color = "#3c3c3c" if self.selected else "transparent"
            color = "#3b3b3b"
        hover_color = self.hover_color
        pressed_color = self.pressed_color

        self.setStyleSheet(
            f"""
            QPushButton {{
                font-family: "Montserrat";
                font-size: 12px;
                font-weight: thin;
                border: 1px solid {color};
                border-radius: 0px;
                height: 20px;
                color: white;
                padding: 5px;
                background-color: {bg_color};
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
        """
        )
