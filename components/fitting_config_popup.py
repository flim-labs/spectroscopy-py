import os
from io import BytesIO

import matplotlib.pyplot as plt
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication, QPixmap, QIcon
from PyQt6.QtWidgets import QWidget, QPushButton, QCheckBox, QComboBox, QHBoxLayout, QVBoxLayout, QLabel, \
    QApplication, QSpacerItem, QSizePolicy, QScrollArea

from components.logo_utilities import TitlebarIcon
from components.resource_path import resource_path
from fit_decay_curve import fit_decay_curve

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

# Define style constants
DARK_THEME_BG_COLOR = "#141414"
DARK_THEME_TEXT_COLOR = "#cecece"
DARK_THEME_TEXT_FONT_SIZE = "20px"
DARK_THEME_HEADER_FONT_SIZE = "25px"
DARK_THEME_FONT_FAMILY = "Montserrat"
DARK_THEME_BTN_HEIGHT = 40
DARK_THEME_RADIO_BTN_STYLE = f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
DARK_THEME_LABEL_STYLE = f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
DARK_THEME_BTN_STYLE = f"background-color: red; color: white; border: none; padding: 5px 10px; text-transform: uppercase; font-size: {DARK_THEME_TEXT_FONT_SIZE}; font-weight: bold; font-family: {DARK_THEME_FONT_FAMILY};"
DARK_THEME_BTN_CANCEL_STYLE = f"background-color: grey; color: white; border: none; padding: 5px 10px; text-transform: uppercase; font-size: {DARK_THEME_TEXT_FONT_SIZE}; font-weight: bold; font-family: {DARK_THEME_FONT_FAMILY};"


class FittingDecayConfigPopup(QWidget):
    def __init__(self, window, data):
        super().__init__()
        self.app = window
        self.data = data
        self.setWindowTitle("Spectroscopy - Fitting Decay Config")
        self.setWindowIcon(QIcon(resource_path("assets/spectroscopy-logo.png")))
        self.setStyleSheet(f"background-color: {DARK_THEME_BG_COLOR};")
        self.setWindowState(Qt.WindowState.WindowMaximized)

        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        desc = QLabel("Select the number of components for the fitting model and whether to include a B component.")
        desc.setWordWrap(True)
        desc.setStyleSheet(DARK_THEME_LABEL_STYLE)
        self.main_layout.addWidget(desc)
        self.main_layout.addSpacing(20)

        components_layout = QVBoxLayout()
        components_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.components_combo = QComboBox()
        self.components_combo.setFixedWidth(200)
        self.components_combo.setStyleSheet(DARK_THEME_RADIO_BTN_STYLE)
        self.components_combo.addItems([f"{i} Component(s)" for i in range(1, 5)])
        self.components_combo.currentIndexChanged.connect(self.update_model_text)
        components_layout.addWidget(self.components_combo)
        self.main_layout.addLayout(components_layout)

        self.b_component_checkbox = QCheckBox("Include B Component")
        self.b_component_checkbox.setStyleSheet(DARK_THEME_RADIO_BTN_STYLE)
        self.b_component_checkbox.stateChanged.connect(self.update_model_text)
        self.main_layout.addWidget(self.b_component_checkbox)

        self.model_text = QLabel("")
        self.model_text.setWordWrap(True)
        self.model_text.setStyleSheet(
            f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}; font-family: {DARK_THEME_FONT_FAMILY};")
        self.main_layout.addWidget(self.model_text)

        self.main_layout.addSpacing(20)


        # Create a scroll area for the plots
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #141414; border: none;")
        self.scroll_area.setWidgetResizable(True)
        # set scroll_area stretch factor to 1
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.scroll_widget = QWidget()
        self.plot_layout = QHBoxLayout(self.scroll_widget)
        self.plot_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.scroll_widget.setLayout(self.plot_layout)

        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.fitting_message = QLabel("Fitting in progress, please wait...")
        self.fitting_message.setStyleSheet(f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: yellow;")
        self.fitting_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fitting_message.setVisible(False)
        self.main_layout.addWidget(self.fitting_message)

        self.main_layout.addSpacing(20)

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

        self.main_layout.addLayout(btn_layout)

        self.setLayout(self.main_layout)

        self.update_model_text()

    def update_model_text(self):
        num_components = self.components_combo.currentIndex() + 1
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
        num_components = self.components_combo.currentIndex() + 1
        include_b = self.b_component_checkbox.isChecked()

        if num_components == -1:
            print("Please select the number of components.")
            return

        self.clear_plots()
        self.fitting_message.setVisible(True)
        QTimer.singleShot(100, self.perform_fitting)

    def perform_fitting(self):
        num_components = self.components_combo.currentIndex() + 1
        include_b = self.b_component_checkbox.isChecked()

        for data_point in self.data:
            result = self.get_plotted_data(data_point['x'], data_point['y'], data_point['title'], num_components, include_b)
            if 'error' in result:
                self.display_error(result['error'], data_point['title'])
            else:
                self.display_plot(result['buffer'], data_point['title'])

        self.fitting_message.setVisible(False)

    def clear_plots(self):
        for i in reversed(range(self.plot_layout.count())):
            widget_to_remove = self.plot_layout.itemAt(i).widget()
            self.plot_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

    def get_plotted_data(self, x_values, y_values, plot_title, num_components, B_component):
        result = fit_decay_curve(x_values, y_values, plot_title, num_components, B_component)
        if 'error' in result:
            return {'error': result['error']}
        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return {'buffer': buf}

    def display_plot(self, plot_data, title):
        plot_label = QLabel(self)
        pixmap = QPixmap()
        pixmap.loadFromData(plot_data.getvalue())
        plot_label.setPixmap(pixmap)
        plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plot_label.setStyleSheet(f"background-color: {DARK_THEME_BG_COLOR}; border: 1px solid {DARK_THEME_BG_COLOR};")
        self.plot_layout.addWidget(plot_label)
        plot_data.close()

    def display_error(self, error_message, title):
        error_label = QLabel(f"Error in {title}: {error_message}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: red; background-color: {DARK_THEME_BG_COLOR};")
        self.plot_layout.addWidget(error_label)

    def center_window(self):
        screen_number = self.get_current_screen()
        if screen_number == -1:
            screen = QGuiApplication.primaryScreen()
        else:
            screen = QGuiApplication.screens()[screen_number]

        screen_geometry = screen.geometry()
        frame_gm = self.frameGeometry()
        screen_center = screen_geometry.center()
        frame_gm.moveCenter(screen_center)
        self.move(frame_gm.topLeft())

    @staticmethod
    def get_current_screen():
        cursor_pos = QCursor.pos()
        screens = QGuiApplication.screens()
        for screen_number, screen in enumerate(screens):
            if screen.geometry().contains(cursor_pos):
                return screen_number
        return -1


if __name__ == '__main__':
    def generate_fake_decay_data(num_bins=256, x_max=12.5):
        import numpy as np

        x_values = np.linspace(0, x_max, num_bins)

        # Create an initial rapid increase using a sigmoid function
        increase_length = num_bins // 10
        decay_length = num_bins - increase_length

        sigmoid = 1 / (1 + np.exp(-10 * (x_values[:increase_length] - 0.5 * x_values[increase_length])))
        sigmoid = sigmoid / sigmoid[-1] * 1000  # Normalize to a range of counts

        # Create a smooth exponential decay that starts from the last point of increase
        decay = np.exp(-0.3 * (x_values[increase_length:] - x_values[increase_length]))
        decay = decay * sigmoid[-1]  # Ensure continuity

        # Concatenate the increase and decay parts
        y_values = np.concatenate([sigmoid, decay])
        y_values = y_values[:num_bins]  # Ensure y_values has the same length as x_values

        # Add random noise with lower amplitude
        noise = np.random.normal(0, 0.02 * np.max(y_values), num_bins)
        y_values = y_values + noise
        y_values = np.maximum(y_values, 0)  # Ensure no negative counts

        return x_values, y_values


    def main():
        sample_data = [{'x': channel_data[0], 'y': channel_data[1], 'title': f'Channel {i + 1}'} for i, channel_data in
                       enumerate([generate_fake_decay_data() for _ in range(3)])]
        app = QApplication([])
        window = FittingDecayConfigPopup(None, sample_data)
        window.show()
        app.exec()


    main()
