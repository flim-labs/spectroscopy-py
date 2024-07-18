from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QPlainTextEdit

class InputTextControl:
    @staticmethod
    def setup(
        label,
        placeholder,
        event_callback,
        control_layout="vertical",
        text="",
    ):
        q_label = QLabel(label)
        q_label.setStyleSheet("font-size: 14px")
        control = QVBoxLayout() if control_layout == "vertical" else QHBoxLayout()
        input_text = QLineEdit()
        input_text.setPlaceholderText(placeholder)
        input_text.setText(text)
        input_text.textChanged.connect(event_callback)
        control.addWidget(q_label)
        control.addWidget(input_text)
        return q_label, input_text
    

class InputTextareaControl:
    @staticmethod
    def setup(
        label,
        placeholder,
        event_callback,
        control_layout="vertical",
        text="",
    ):
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
    