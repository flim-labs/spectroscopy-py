from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QComboBox

class CustomSelect(QComboBox):
    """A custom QComboBox that ignores wheel events to prevent accidental scrolling."""
    def wheelEvent(self, event):
        """Ignores mouse wheel events to prevent changing the selection.

        Args:
            event (QWheelEvent): The wheel event.
        """
        event.ignore()
            
class SelectControl:
    """A factory class for creating a labeled QComboBox (select) control."""
    @staticmethod
    def setup(
        label,
        selectedValue,
        container,
        options,
        event_callback,
        spacing=20,
        control_layout="vertical",
        width=None,
        prevent_default_value = False
    ):
        """Creates and configures a labeled combo box and adds it to a container layout.

        Args:
            label (str): The text for the label associated with the combo box.
            selectedValue (int): The index of the initially selected item.
            container (QLayout): The layout to which the control will be added.
            options (list): A list of strings to populate the combo box options.
            event_callback (function): The function to call when the selection changes.
            spacing (int, optional): The space to add after the control. Defaults to 20.
            control_layout (str, optional): The layout orientation ('vertical' or 'horizontal'). Defaults to "vertical".
            width (int, optional): The fixed width for the combo box. Defaults to None.
            prevent_default_value (bool, optional): If True, makes the first item unselectable. Defaults to False.

        Returns:
            tuple: A tuple containing the control layout, the QComboBox instance,
                   the QLabel instance, and the container layout.
        """
        q_label = QLabel(label)
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input = CustomSelect()
        if width is not None:
            input.setFixedWidth(width)
        for value in options:
            input.addItem(value)
        if prevent_default_value:
            input.setItemData(0, None)            
        if selectedValue is not None:
            input.setCurrentIndex(selectedValue)
        input.currentIndexChanged.connect(event_callback)
        control.addWidget(q_label)
        control.addWidget(input)
        container.addLayout(control)
        if spacing:
            container.addSpacing(spacing)
        return control, input, q_label, container
