from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QComboBox


class SelectControl:
    @staticmethod
    def setup(label, selectedValue, container, options, event_callback, spacing=20, control_layout="vertical", width= None):
        q_label = QLabel(label)
        control = QVBoxLayout() if control_layout == 'vertical' else QHBoxLayout()
        input = QComboBox()
        if width is not None:
            input.setFixedWidth(width)
        for value in options:
            input.addItem(value)
        input.setCurrentIndex(selectedValue)
        input.currentIndexChanged.connect(event_callback)
        control.addWidget(q_label)
        control.addWidget(input)
        container.addLayout(control)
        if spacing:
            container.addSpacing(spacing)
        return control, input, q_label, container
