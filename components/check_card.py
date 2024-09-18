import os
from PyQt6.QtCore import  Qt
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel
)
from PyQt6.QtGui import QIcon


from components.gui_styles import GUIStyles
from components.resource_path import resource_path
from settings import CHECK_CARD_BUTTON, CHECK_CARD_MESSAGE


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class CheckCard(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)
        # Check button
        self.check_button = QPushButton(" CHECK DEVICE")
        self.check_button.setIcon(QIcon(resource_path("assets/card-icon.png")))
        self.check_button.setFixedHeight(36)
        self.check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_button.clicked.connect(app.check_card_connection)
        GUIStyles.set_start_btn_style(self.check_button)
        self.app.widgets[CHECK_CARD_BUTTON] = self.check_button
        # Check message
        self.check_message = QLabel("Card ID: 12345")
        self.check_message.setStyleSheet(GUIStyles.check_card_message(color="#285da6"))
        self.app.widgets[CHECK_CARD_MESSAGE] = self.check_message
        self.layout.addWidget(self.check_button)
        self.layout.addSpacing(5)
        self.layout.addWidget(self.check_message)
        self.check_message.hide()
        self.setLayout(self.layout)
        
        
    @staticmethod
    def update_check_message(app, message, error):
        if CHECK_CARD_MESSAGE in app.widgets:
            app.widgets[CHECK_CARD_MESSAGE].setText(message if error else f"Card ID: {message}")
            app.widgets[CHECK_CARD_MESSAGE].setStyleSheet(GUIStyles.check_card_message(color="#285da6" if not error else "#f72828"))
            if not (app.widgets[CHECK_CARD_MESSAGE].isVisible()):
                app.widgets[CHECK_CARD_MESSAGE].setVisible(True)
                
        
        
        
        
    


