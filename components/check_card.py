import os
from PyQt6.QtCore import  Qt
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel
)
from PyQt6.QtGui import QIcon


from utils.gui_styles import GUIStyles
from utils.resource_path import resource_path
import settings.settings as s


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class CheckCard(QWidget):
    """
    A widget that provides a button to check for a connected hardware device
    and a label to display the connection status.
    """
    def __init__(self, app, parent=None):
        """
        Initializes the CheckCard widget.

        Args:
            app: The main application instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        from core.acquisition_controller import AcquisitionController
        self.app = app
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)
        # Check button
        self.check_button = QPushButton(" CHECK DEVICE")
        self.check_button.setIcon(QIcon(resource_path("assets/card-icon.png")))
        self.check_button.setFixedHeight(36)
        self.check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_button.clicked.connect(lambda: AcquisitionController.check_card_connection(app))
        GUIStyles.set_start_btn_style(self.check_button)
        self.app.widgets[s.CHECK_CARD_BUTTON] = self.check_button
        # Check message
        self.check_message = QLabel("")
        self.check_message.setStyleSheet(GUIStyles.check_card_message(color="#285da6"))
        self.app.widgets[s.CHECK_CARD_MESSAGE] = self.check_message
        self.layout.addWidget(self.check_button)
        self.layout.addSpacing(5)
        self.layout.addWidget(self.check_message)
        self.check_message.hide()
        self.setLayout(self.layout)
        
        
    @staticmethod
    def update_check_message(app, message, error):
        """
        Updates the message label with the device connection status.

        Args:
            app: The main application instance.
            message (str): The message to display (e.g., card ID or error message).
            error (bool): True if the message is an error, False otherwise.
        """
        if s.CHECK_CARD_MESSAGE in app.widgets:
            app.widgets[s.CHECK_CARD_MESSAGE].setText(message if error else f"Card ID: {message}")
            app.widgets[s.CHECK_CARD_MESSAGE].setStyleSheet(GUIStyles.check_card_message(color="#285da6" if not error else "#f72828"))
            if not (app.widgets[s.CHECK_CARD_MESSAGE].isVisible()):
                app.widgets[s.CHECK_CARD_MESSAGE].setVisible(True)



