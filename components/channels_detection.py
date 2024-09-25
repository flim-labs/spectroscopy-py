from functools import partial
import json
import os
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QDialog,
)
from PyQt6.QtGui import QIcon, QPixmap, QTransform
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import flim_labs


from components.gui_styles import GUIStyles
from components.helpers import extract_channel_from_label
from components.resource_path import resource_path
from settings import *


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ChannelsDetectionWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            result = flim_labs.detect_channels_connections()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DetectChannelsDialog(QDialog):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("Detect Channels")
        self.setWindowIcon(QIcon(resource_path("assets/channel-icon-blue.png")))
        self.setMinimumSize(300, 250)
        self.setMaximumSize(400, 350)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Loader
        self.loader_label = QLabel(self)
        self.loader_pixmap = QPixmap(resource_path("assets/channel-icon-blue.png"))
        self.loader_pixmap = self.loader_pixmap.scaled(
            40, 40, Qt.AspectRatioMode.KeepAspectRatio
        )
        self.loader_label.setPixmap(self.loader_pixmap)
        self.loader_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.loader_label.setVisible(False)

        # Success/Error Icon
        self.success_icon_layout = QHBoxLayout()
        self.success_icon_layout.setContentsMargins(0, 0, 0, 0)
        self.success_icon_layout.setSpacing(0)
        self.success_icon = QLabel()
        self.success_icon_pixmap = QPixmap(resource_path("assets/success-lens.png"))
        self.success_icon_pixmap = self.success_icon_pixmap.scaled(
            45, 45, Qt.AspectRatioMode.KeepAspectRatio
        )
        self.success_icon.setPixmap(self.success_icon_pixmap)
        self.success_icon.setVisible(False)
        self.success_icon_layout.addWidget(
            self.success_icon, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        self.error_icon_layout = QHBoxLayout()
        self.error_icon_layout.setContentsMargins(0, 0, 0, 0)
        self.error_icon_layout.setSpacing(0)
        self.error_icon = QLabel()
        self.error_icon_pixmap = QPixmap(resource_path("assets/error-lens.png"))
        self.error_icon_pixmap = self.error_icon_pixmap.scaled(
            45, 45, Qt.AspectRatioMode.KeepAspectRatio
        )
        self.error_icon.setPixmap(self.error_icon_pixmap)
        self.error_icon.setVisible(False)
        self.error_icon_layout.addWidget(
            self.error_icon, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        # Label
        label_container = QHBoxLayout()
        self.label = QLabel("Do you want to detect channels connections?")
        self.label.setStyleSheet("font-family: Montserrat; font-size: 14px;")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label_container.addWidget(self.label)

        self.layout.addWidget(self.loader_label)
        self.layout.addLayout(self.success_icon_layout)
        self.layout.addLayout(self.error_icon_layout)
        self.layout.addLayout(label_container)
        self.layout.addSpacing(20)

        # Connections result layout
        self.result_layout = QVBoxLayout()
        self.result_layout.setSpacing(5)
        self.layout.addLayout(self.result_layout)
        self.layout.addSpacing(20)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.no_button = QPushButton("NO")
        self.no_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.no_button.setObjectName("btn")
        GUIStyles.set_stop_btn_style(self.no_button)
        self.no_button.clicked.connect(self.on_no_button_click)
        self.button_layout.addWidget(self.no_button)

        self.yes_button = QPushButton("DO IT")
        self.yes_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yes_button.setObjectName("btn")
        GUIStyles.set_start_btn_style(self.yes_button)
        self.yes_button.clicked.connect(self.on_yes_button_click)
        self.button_layout.addWidget(self.yes_button)

        self.connections_obj = None
        GUIStyles.customize_theme(self)
        GUIStyles.set_fonts()

        self.worker = None
        self.flip_timer = QTimer(self)
        self.flip_timer.timeout.connect(self.flip_loader)

        self.flipped = False

    def flip_loader(self):
        transform = QTransform()
        if self.flipped:
            transform.scale(1, 1)
        else:
            transform.scale(-1, 1)

        self.loader_label.setPixmap(
            self.loader_pixmap.transformed(
                transform, mode=Qt.TransformationMode.SmoothTransformation
            )
        )
        self.flipped = not self.flipped

    def on_yes_button_click(self):
        self.error_icon.setVisible(False)
        self.success_icon.setVisible(False)
        self.label.setText(
            "Detecting channels connections... The process can take a few seconds. Please wait and don't close the window. After 60 seconds, the process "
            "will be interrupted automatically."
        )
        self.loader_label.setVisible(True)
        self.flip_timer.start(400)

        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)

        self.worker = ChannelsDetectionWorker()
        self.worker.finished.connect(self.on_detection_complete)
        self.worker.error.connect(self.on_detection_error)
        self.worker.start()

    def on_detection_complete(self, result):
        self.connections_obj = result
        self.flip_timer.stop()
        self.loader_label.setVisible(False)

        if self.connections_obj is None:
            self.error_icon.setVisible(True)
            self.success_icon.setVisible(False)
            self.label.setText(
                "Channels connections not detected. Please check the connection and try again."
            )
            self.yes_button.setEnabled(True)
            self.yes_button.setText("RETRY")
        else:
            self.error_icon.setVisible(False)
            self.success_icon.setVisible(True)
            detection_result = self.process_detection_result(self.connections_obj)
            self.label.setVisible(False)
            for key, status, connection_type in detection_result:
                result_text = f"{key} {status if status else ''} {'(' + connection_type + ')' if connection_type != 'Not Detected' else connection_type}"
                result_label = QLabel(result_text)
                if connection_type != "Not Detected":
                    result_label.setStyleSheet(
                        "font-family: Montserrat; font-size: 14px; font-weight: bold; color: #0096FF;"
                    )
                else:
                    result_label.setStyleSheet(
                        "font-family: Montserrat; font-size: 14px; color: #cecece;"
                    )

                self.result_layout.addWidget(
                    result_label, alignment=Qt.AlignmentFlag.AlignHCenter
                )
            self.yes_button.setEnabled(False)
            self.yes_button.setVisible(False)
        self.no_button.setEnabled(True)
        GUIStyles.set_start_btn_style(self.no_button)
        self.no_button.setText("UPDATE SETTINGS")
        channels_str = detection_result[0][1]
        connection = detection_result[0][2]
        self.no_button.clicked.connect(
            partial(self.update_settings, channels_str, connection)
        )

    def update_settings(self, channels_str, connection_type):
        self.update_selected_channels(channels_str)
        self.update_channel_connection_type(connection_type)
        self.close()

    def update_selected_channels(self, channels_str):
        channels_str_clean = channels_str.replace('[', '').replace(']', '').strip()
        channels = [int(num) - 1 for num in channels_str_clean.split(",")]
        channels.sort()
        for ch_checkbox in self.app.channel_checkboxes:
            label_text = ch_checkbox.label.text()
            ch_index = extract_channel_from_label(label_text)
            ch_checkbox.set_checked(ch_index in channels)
        self.app.selected_channels = channels
        self.app.set_selected_channels_to_settings()
        self.app.plots_to_show = channels[:4]
        self.app.settings.setValue(
            SETTINGS_PLOTS_TO_SHOW, json.dumps(self.app.plots_to_show)
        )
        self.app.clear_plots()
        self.app.generate_plots()

    def update_channel_connection_type(self, connection_type):
        index = 0 if connection_type == "USB" else 1
        self.app.control_inputs["channel_type"].setCurrentIndex(index)
        self.app.settings.setValue(SETTINGS_CONNECTION_TYPE, index)

    def process_detection_result(self, result):
        detection = ChannelsDetection(
            result.sma_channels,
            result.usb_channels,
            result.sma_frame,
            result.usb_frame,
            result.sma_line,
            result.usb_line,
            result.sma_pixel,
            result.usb_pixel,
            result.sma_laser_sync_in,
            result.usb_laser_sync_in,
            result.usb_laser_sync_out,
        )
        parsed_detection = detection.parse_data()
        return parsed_detection

    def on_detection_error(self, error_msg):
        self.flip_timer.stop()
        self.loader_label.setVisible(False)
        self.error_icon.setVisible(True)
        self.success_icon.setVisible(False)
        self.label.setText(f"Error: {error_msg}")
        self.yes_button.setEnabled(True)
        self.yes_button.setText("RETRY")
        self.no_button.setEnabled(True)
        self.no_button.setText("CANCEL")

    def on_no_button_click(self):
        self.error_icon.setVisible(False)
        self.success_icon.setVisible(False)
        self.loader_label.setVisible(False)
        self.close()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        super().closeEvent(event)


class DetectChannelsButton(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        container = QVBoxLayout()
        container.setSpacing(0)
        container.setContentsMargins(0, 0, 0, 0)
        self.detect_button = QPushButton(" DETECT CHANNELS")
        self.detect_button.setIcon(QIcon(resource_path("assets/channel-icon.png")))
        self.detect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        GUIStyles.set_stop_btn_style(self.detect_button)
        self.detect_button.setFixedHeight(40)
        self.detect_button.clicked.connect(self.open_channels_detection_dialog)
        self.app.widgets[CHANNELS_DETECTION_BUTTON] = self.detect_button
        container.addWidget(self.detect_button, alignment=Qt.AlignmentFlag.AlignBottom)
        self.setLayout(container)

    def open_channels_detection_dialog(self):
        dialog = DetectChannelsDialog(self.app)
        dialog.exec()


class ChannelsDetection:
    def __init__(
        self,
        sma_channels,
        usb_channels,
        sma_frame,
        usb_frame,
        sma_line,
        usb_line,
        sma_pixel,
        usb_pixel,
        sma_laser_sync_in,
        usb_laser_sync_in,
        usb_laser_sync_out,
    ):
        self.sma_channels = sma_channels
        self.usb_channels = usb_channels
        self.sma_frame = sma_frame
        self.usb_frame = usb_frame
        self.sma_line = sma_line
        self.usb_line = usb_line
        self.sma_pixel = sma_pixel
        self.usb_pixel = usb_pixel
        self.sma_laser_sync_in = sma_laser_sync_in
        self.usb_laser_sync_in = usb_laser_sync_in
        self.usb_laser_sync_out = usb_laser_sync_out

    def parse_data(self):
        # Channels
        channels_data = self.get_first_non_empty_channel()
        # Frame
        frame_data = self.get_frame_connection()
        # Line
        line_data = self.get_line_connection()
        # Pixel
        pixel_data = self.get_pixel_connection()
        # Sync In
        sync_in_data = self.get_sync_in_connection()
        # Sync Out
        sync_out_data = self.get_sync_out_connection()
        return [
            channels_data,
            frame_data,
            line_data,
            pixel_data,
            sync_in_data,
            sync_out_data,
        ]

    def get_frame_connection(self):
        if self.sma_frame == True:
            return ("REF 1 (Frame):", "Detected", "SMA")
        elif self.usb_frame == True:
            return ("REF 1 (Frame):", "Detected", "USB")
        else:
            return ("REF 1 (Frame):", None, "Not Detected")

    def get_line_connection(self):
        if self.sma_line == True:
            return ("REF 2 (Line):", "Detected", "SMA")
        elif self.usb_line == True:
            return ("REF 2 (Line):", "Detected", "USB")
        else:
            return ("REF 2 (Line):", None, "Not Detected")

    def get_pixel_connection(self):
        if self.sma_pixel == True:
            return ("REF 3 (Pixel):", "Detected", "SMA")
        elif self.usb_pixel == True:
            return ("REF 3 (Pixel):", "Detected", "USB")
        else:
            return ("REF 3 (Pixel):", None, "Not Detected")

    def get_first_non_empty_channel(self):
        if len(self.sma_channels) > 0:
            return ("Channels:", str([ch + 1 for ch in self.sma_channels]), "SMA")
        elif len(self.usb_channels) > 0:
            return ("Channels:", str([ch + 1 for ch in self.usb_channels]), "USB")
        else:
            return ("Channels:", None, "Not Detected")

    def get_sync_in_connection(self):
        if self.sma_laser_sync_in == True:
            return ("Sync In:", "Detected", "SMA")
        elif self.usb_laser_sync_in == True:
            return ("Sync In:", "Detected", "USB")
        else:
            return ("Sync In:", None, "Not Detected")

    def get_sync_out_connection(self):
        if self.usb_laser_sync_out == True:
            return ("Sync Out:", "Detected", "USB")
        else:
            return ("Sync Out:", None, "Not Detected")
