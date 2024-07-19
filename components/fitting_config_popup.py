import os

from PyQt6.QtWidgets import QWidget, QPushButton, QCheckBox, QRadioButton, QHBoxLayout, QVBoxLayout, QLabel, QApplication, QButtonGroup
from PyQt6.QtCore import Qt
from components.logo_utilities import TitlebarIcon

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

# Define style constants
DARK_THEME_BG_COLOR = "#141414"
DARK_THEME_TEXT_COLOR = "#cecece"
DARK_THEME_TEXT_FONT_SIZE = "14px"
DARK_THEME_HEADER_FONT_SIZE = "18px"
DARK_THEME_FONT_FAMILY = "Consolas, monospace"
DARK_THEME_BTN_HEIGHT = 40
DARK_THEME_RADIO_BTN_STYLE = f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
DARK_THEME_LABEL_STYLE = f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
DARK_THEME_BTN_STYLE = f"background-color: #333; color: white; border: 1px solid #444; border-radius: 5px; padding: 5px 10px;"
DARK_THEME_BTN_CANCEL_STYLE = f"background-color: #555; color: white; border: 1px solid #666; border-radius: 5px; padding: 5px 10px;"

class FittingDecayConfigPopup(QWidget):
    def __init__(self, window):
        super().__init__()
        self.app = window
        self.setWindowTitle("Spectroscopy - Fitting Decay Config")
        TitlebarIcon.setup(self)
        self.setStyleSheet(f"background-color: {DARK_THEME_BG_COLOR};")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        desc = QLabel("Select the number of components for the fitting model and whether to include a B component.")
        desc.setWordWrap(True)
        desc.setStyleSheet(DARK_THEME_LABEL_STYLE)
        layout.addWidget(desc)
        layout.addSpacing(20)

        self.components_group = QButtonGroup(self)
        self.components_group.buttonClicked.connect(self.update_model_text)
        components_layout = QVBoxLayout()
        components_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for i in range(1, 5):
            radio_btn = QRadioButton(f"{i} Component(s)")
            radio_btn.setStyleSheet(DARK_THEME_RADIO_BTN_STYLE)
            self.components_group.addButton(radio_btn, i)
            components_layout.addWidget(radio_btn)
        layout.addLayout(components_layout)

        self.b_component_checkbox = QCheckBox("Include B Component")
        self.b_component_checkbox.setStyleSheet(DARK_THEME_RADIO_BTN_STYLE)
        self.b_component_checkbox.stateChanged.connect(self.update_model_text)
        layout.addWidget(self.b_component_checkbox)

        self.model_text = QLabel("")
        self.model_text.setWordWrap(True)
        self.model_text.setStyleSheet(f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}; font-family: {DARK_THEME_FONT_FAMILY};")
        layout.addWidget(self.model_text)

        layout.addSpacing(20)

        btn_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(DARK_THEME_BTN_CANCEL_STYLE)
        self.cancel_btn.setFixedHeight(DARK_THEME_BTN_HEIGHT)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancel)
        btn_layout.addWidget(self.cancel_btn)

        self.start_fitting_btn = QPushButton("Start Fitting")
        self.start_fitting_btn.setStyleSheet(DARK_THEME_BTN_STYLE)
        self.start_fitting_btn.setFixedHeight(DARK_THEME_BTN_HEIGHT)
        self.start_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_fitting_btn.clicked.connect(self.start_fitting)
        btn_layout.addWidget(self.start_fitting_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self.center_window()

        # Initialize model text
        self.update_model_text()

    def update_model_text(self):
        num_components = self.components_group.checkedId()
        include_b = self.b_component_checkbox.isChecked()

        if num_components == -1:
            self.model_text.setText("")
            return

        model_text = "Model: "
        terms = [f"A{i} * exp(-t / tau{i})" for i in range(1, num_components + 1)]

        if include_b:
            terms.append("B")

        model_text += " + ".join(terms)
        self.model_text.setText(model_text)

    def cancel(self):
        self.close()

    def start_fitting(self):
        # Logic to start the fitting process based on selected options
        pass

    def center_window(self):
        frameGm = self.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry().center()
        frameGm.moveCenter(screen)
        self.move(frameGm.topLeft())


def main():
    app = QApplication([])
    window = FittingDecayConfigPopup(None)
    window.show()
    app.exec()


if __name__ == '__main__':
    main()