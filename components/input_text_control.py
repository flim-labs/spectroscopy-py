from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QPlainTextEdit

class InputTextControl:
    """A utility class to create a single-line text input control (QLineEdit) with a label."""
    @staticmethod
    def setup(
        label,
        placeholder,
        event_callback,
        control_layout="vertical",
        text="",
        validator=None,
    ):
        """
        Creates and configures a QLabel and a QLineEdit.

        Args:
            label (str): The text for the label.
            placeholder (str): The placeholder text for the input field.
            event_callback (callable): The function to call when the text changes.
            control_layout (str, optional): The layout orientation ('vertical' or 'horizontal'). Defaults to "vertical".
            text (str, optional): The initial text for the input field. Defaults to "".
            validator (QValidator, optional): A validator to apply to the input field. Defaults to None.

        Returns:
            tuple: A tuple containing the created QLabel and QLineEdit widgets.
        """
        q_label = QLabel(label)
        q_label.setStyleSheet("font-size: 14px")
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input_text = QLineEdit()
        input_text.setPlaceholderText(placeholder)
        input_text.setText(text)
        if validator is not None:
            input_text.setValidator(validator)
        input_text.textChanged.connect(event_callback)
        control.addWidget(q_label)
        control.addWidget(input_text)
        return q_label, input_text
    

class InputTextareaControl:
    """A utility class to create a multi-line text input control (QPlainTextEdit) with a label."""
    @staticmethod
    def setup(
        label,
        placeholder,
        event_callback,
        control_layout="vertical",
        text="",
    ):
        """
        Creates and configures a QLabel and a QPlainTextEdit.

        Args:
            label (str): The text for the label.
            placeholder (str): The placeholder text for the textarea.
            event_callback (callable): The function to call when the text changes.
            control_layout (str, optional): The layout orientation ('vertical' or 'horizontal'). Defaults to "vertical".
            text (str, optional): The initial text for the textarea. Defaults to "".

        Returns:
            tuple: A tuple containing the created QLabel and QPlainTextEdit widgets.
        """
        q_label = QLabel(label)
        q_label.setStyleSheet("font-size: 14px")
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input_textarea = QPlainTextEdit()
        input_textarea.setPlaceholderText(placeholder)
        input_textarea.setPlainText(text)
        input_textarea.textChanged.connect(event_callback)
        
        control.addWidget(q_label)
        control.addWidget(input_textarea)
      
        return q_label, input_textarea
