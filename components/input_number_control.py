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
    def wheelEvent(self, event):
        event.ignore()


class CustomDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class InputNumberControl:
    @staticmethod
    def setup(
        label,
        min,
        max,
        value,
        row,
        event_callback,
        spacing=20,
        control_layout="vertical",
    ):
        q_label = QLabel(label)
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input = CustomSpinBox()
        if min is not None:
            input.setMinimum(min)
        if max is not None:
            input.setMaximum(max)
        if value is not None:
            input.setValue(value)
        input.valueChanged.connect(event_callback)
        control.addWidget(q_label)
        control.addWidget(input)
        row.addLayout(control)
        if spacing:
            row.addSpacing(20)
        return q_label, input


class InputFloatControl:
    @staticmethod
    def setup(
        label,
        min,
        max,
        value,
        row,
        event_callback,
        spacing=20,
        control_layout="vertical",
        action_widget=None,
    ):
        h_box = QHBoxLayout()
        q_label = QLabel(label)
        q_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input = CustomDoubleSpinBox()
        if min is not None:
            input.setMinimum(min)
        if max is not None:
            input.setMaximum(max)
        if value is not None:
            input.setValue(value)
        input.valueChanged.connect(event_callback)
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
        control.addWidget(input)
        row.addLayout(control)
        if spacing:
            row.addSpacing(spacing)
        return q_label, input
