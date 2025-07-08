from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSpinBox,
    QDoubleSpinBox,
    QSpacerItem,
    QSizePolicy,
)
from PyQt6.QtCore import Qt


class CustomSpinBox(QSpinBox):
    """A QSpinBox subclass that ignores mouse wheel events to prevent accidental value changes."""

    def wheelEvent(self, event):
        """
        Ignores mouse wheel events.

        Args:
            event (QWheelEvent): The wheel event.
        """
        event.ignore()


class CustomDoubleSpinBox(QDoubleSpinBox):
    """A QDoubleSpinBox subclass that ignores mouse wheel events to prevent accidental value changes."""

    def wheelEvent(self, event):
        """
        Ignores mouse wheel events.

        Args:
            event (QWheelEvent): The wheel event.
        """
        event.ignore()


class InputNumberControl:
    """A utility class to create an integer input control (spin box) with a label."""

    @staticmethod
    def setup(
        label,
        min_val,
        max_val,
        value,
        row,
        event_callback,
        spacing=20,
        control_layout="vertical",
    ):
        """
        Creates and configures a QLabel and a QSpinBox, adding them to a given layout.

        Args:
            label (str): The text for the label.
            min_val (int or None): The minimum value for the spin box.
            max_val (int or None): The maximum value for the spin box.
            value (int or None): The initial value for the spin box.
            row (QLayout): The layout to which the control will be added.
            event_callback (callable): The function to call when the spin box value changes.
            spacing (int, optional): The spacing to add after the control. Defaults to 20.
            control_layout (str, optional): The layout orientation ('vertical' or 'horizontal'). Defaults to "vertical".

        Returns:
            tuple: A tuple containing the created QLabel and QSpinBox widgets.
        """
        q_label = QLabel(label)
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input_widget = CustomSpinBox()
        if min_val is not None:
            input_widget.setMinimum(min_val)
        if max_val is not None:
            input_widget.setMaximum(max_val)
        if value is not None:
            input_widget.setValue(value)
        input_widget.valueChanged.connect(event_callback)
        control.addWidget(q_label)
        control.addWidget(input_widget)
        row.addLayout(control)
        if spacing:
            row.addSpacing(spacing)
        return q_label, input_widget


class InputFloatControl:
    """A utility class to create a float input control (double spin box) with a label."""

    @staticmethod
    def setup(
        label,
        min_val,
        max_val,
        value,
        row,
        event_callback,
        spacing=20,
        control_layout="vertical",
        action_widget=None,
    ):
        """
        Creates and configures a QLabel and a QDoubleSpinBox, adding them to a given layout.

        Args:
            label (str): The text for the label.
            min_val (float or None): The minimum value for the spin box.
            max_val (float or None): The maximum value for the spin box.
            value (float or None): The initial value for the spin box.
            row (QLayout): The layout to which the control will be added.
            event_callback (callable): The function to call when the spin box value changes.
            spacing (int, optional): The spacing to add after the control. Defaults to 20.
            control_layout (str, optional): The layout orientation ('vertical' or 'horizontal'). Defaults to "vertical".
            action_widget (QWidget, optional): An optional widget to place next to the label. Defaults to None.

        Returns:
            tuple: A tuple containing the created QLabel and QDoubleSpinBox widgets.
        """
        h_box = QHBoxLayout()
        q_label = QLabel(label)
        q_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input_widget = CustomDoubleSpinBox()
        if min_val is not None:
            input_widget.setMinimum(min_val)
        if max_val is not None:
            input_widget.setMaximum(max_val)
        if value is not None:
            input_widget.setValue(value)
        input_widget.valueChanged.connect(event_callback)
        h_box.addWidget(q_label)
        spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        h_box.addItem(spacer)
        if action_widget is not None:
            action_widget.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred
            )
            h_box.addWidget(action_widget, alignment=Qt.AlignmentFlag.AlignRight)
        control.addLayout(h_box)
        control.addWidget(input_widget)
        row.addLayout(control)
        if spacing:
            row.addSpacing(spacing)
        return q_label, input_widget
