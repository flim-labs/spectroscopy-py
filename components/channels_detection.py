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


from components.fancy_checkbox import FancyButton
from utils.gui_styles import GUIStyles
from utils.helpers import extract_channel_from_label
from utils.layout_utilities import clear_layout_widgets, draw_layout_separator
from utils.resource_path import resource_path
from core.acquisition_controller import AcquisitionController
import settings.settings as s


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ChannelsDetectionWorker(QThread):
    """
    A worker thread to run the channel detection process without blocking the GUI.
    
    Signals:
        finished (pyqtSignal): Emitted when the detection is complete, carrying the result object.
        error (pyqtSignal): Emitted when an error occurs, carrying the error message string.
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        """
        Executes the channel detection function from flim_labs and emits the result.
        """
        try:
            result = flim_labs.detect_channels_connections()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DetectChannelsDialog(QDialog):
    """
    A dialog window for detecting hardware channel connections.
    
    It manages the detection process, displays the results, and allows the user
    to apply the detected settings to the main application.
    """
    def __init__(self, app):
        """
        Initializes the DetectChannelsDialog.

        Args:
            app: The main application instance.
        """
        super().__init__()
        self.app = app
        self.setWindowTitle("Detect Channels")
        self.setWindowIcon(QIcon(resource_path("assets/channel-icon-blue.png")))
        self.setMinimumWidth(450)
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
        self.layout.addSpacing(10)

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
        self.connection_type = None
        self.sync_in_detected = False

    def flip_loader(self):
        """Animates the loader icon by flipping it horizontally."""
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
        """Starts the channel detection process when the 'DO IT' or 'RETRY' button is clicked."""
        self.error_icon.setVisible(False)
        self.success_icon.setVisible(False)
        self.connection_type = None
        self.sync_in_detected = False
        if hasattr(self, 'connection_type_choose_container'):
            self.choose_connection_container.setVisible(False)
        if hasattr(self, 'sync_in_warning_container'):
                self.sync_in_warning_container.setVisible(False)             
        clear_layout_widgets(self.result_layout)
        self.label.setVisible(True)
        self.label.setText(
            "Detecting channels connections... The process can take a few seconds. Please wait and don't close the window. After 60 seconds, the process "
            "will be interrupted automatically."
        )
        self.loader_label.setVisible(True)
        self.flip_timer.start(400)

        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)
        
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait() 

        self.worker = ChannelsDetectionWorker()
        self.worker.finished.connect(self.on_detection_complete)
        self.worker.error.connect(self.on_detection_error)
        self.worker.start()


    def on_detection_complete(self, result):
        """
        Handles the successful completion of the channel detection.

        Args:
            result: The result object from the detection worker.
        """
        AcquisitionController.check_card_connection(self.app)
        self.connections_obj = result
        self.flip_timer.stop()
        self.loader_label.setVisible(False)

        if self.connections_obj is None:
            self.error_icon.setVisible(True)
            self.success_icon.setVisible(False)
            if hasattr(self, 'connection_type_choose_container'):
                        self.choose_connection_container.setVisible(False)   
            if hasattr(self, 'sync_in_warning_container'):
                    self.sync_in_warning_container.setVisible(False)                                  
            self.label.setText(
                "Channels connections not detected. Please check the connection and try again."
            )
            self.yes_button.setEnabled(True)
            self.yes_button.setText(" RETRY")
            self.yes_button.setIcon((QIcon(resource_path("assets/refresh-icon.png"))))
        else:
            self.error_icon.setVisible(False)
            self.success_icon.setVisible(True)
            detection_result = self.process_detection_result(self.connections_obj)
            self.label.setVisible(False)
            channels_sma = []
            channels_usb = []
            channels_usb_sma = False
            # Check Sync In
            self.sync_in_detected = detection_result[4][0][1] == "Detected"
            # Check channels
            if len(detection_result[0]) > 1:
                channels_sma = detection_result[0][0][1]
                channels_usb = detection_result[0][1][1]
                channels_usb_sma = (channels_sma and channels_sma != "[]") and (channels_usb and channels_usb != "[]")
            for result_group in detection_result:
                for key, status, connection_type in result_group:
                    if status != "[]":
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
            if channels_usb_sma:
                connection_type_choose_container = self.choose_connection_layout()
                self.result_layout.addWidget(connection_type_choose_container) 
                self.no_button.setEnabled(self.connection_type is  not None)
            else:
                if channels_usb != "[]" or channels_sma != "[]":
                    self.connection_type = "USB" if channels_usb != "[]" else "SMA"
                self.no_button.setEnabled(len(detection_result[0]) > 1 or self.sync_in_detected)  
            if self.sync_in_detected:
                sync_in_warning_container = self.sync_in_warning_layout()   
                self.result_layout.addWidget(sync_in_warning_container)             
            self.yes_button.setEnabled(True)
            self.yes_button.setVisible(True)
            self.yes_button.setText(" RETRY")
            self.yes_button.setIcon((QIcon(resource_path("assets/refresh-icon.png"))))
            GUIStyles.set_stop_btn_style(self.yes_button)
        GUIStyles.set_start_btn_style(self.no_button)
        self.no_button.setText("UPDATE SETTINGS")
        self.no_button.clicked.connect(
            partial(self.update_settings, detection_result)
        )

    def choose_connection_layout(self):
        """
        Creates and returns a widget for choosing between USB and SMA connections.
        
        Returns:
            QWidget: The container widget with the connection type choice.
        """
        self.choose_connection_container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(draw_layout_separator())
        layout.addSpacing(5)
        label = QLabel("USB and SMA connections detected. Choose one:")
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)
        buttons_row = QHBoxLayout()
        connections = ["USB", "SMA"]
        self.connection_type_buttons = []
        for c in connections:
            button = FancyButton(c)
            buttons_row.addWidget(button)
            self.connection_type_buttons.append((button, c))
        for button, name in self.connection_type_buttons:
            def on_toggle(toggled_name):
                for b, n in self.connection_type_buttons:
                    b.set_selected(n == toggled_name)
                self.connection_type = toggled_name
                self.no_button.setEnabled(True)
            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(self.connection_type == name)     
        layout.addLayout(buttons_row)
        layout.addSpacing(5) 
        layout.addWidget(draw_layout_separator()) 
        self.choose_connection_container.setLayout(layout)                    
        return self.choose_connection_container
    
    
    def sync_in_warning_layout(self):
        """
        Creates and returns a widget to warn the user about Sync In detection.
        
        Returns:
            QWidget: The container widget with the warning message.
        """
        self.sync_in_warning_container = QWidget()
        layout = QVBoxLayout()
        layout.addSpacing(5)
        label = QLabel("Sync In detected.\nBy clicking 'UPDATE SETTINGS' the frequency measurement\nwill automatically start.")
        label.setStyleSheet("color: #eed202; font-weight: bold; text-align: center")
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(5) 
        self.sync_in_warning_container.setLayout(layout)                    
        return self.sync_in_warning_container
    
    def update_settings(self, detection_result):
        """
        Applies the detected settings to the main application.

        Args:
            detection_result: The processed detection result.
        """
        if detection_result[0][0][1] is not None:
            channel_sma_str = detection_result[0][0][1]
            channels_usb_str = detection_result[0][1][1]
            if self.connection_type == None:
                channels_str = channel_sma_str if channel_sma_str != "[]" else channels_usb_str
            else:
                channels_str = channel_sma_str if self.connection_type == "SMA"   else channels_usb_str   
            self.update_selected_channels(channels_str)
            self.update_channel_connection_type(self.connection_type)
        if self.sync_in_detected:
            self.update_sync_in()           
        self.close()
        
    def update_sync_in(self):
        """Updates the sync setting to 'Sync In' in the main application."""
        from core.controls_controller import ControlsController
        for button, name in self.app.sync_buttons:
            button.set_selected(name == "sync_in") 
        ControlsController.on_sync_selected(self.app, "sync_in", start_sync_in_dialog=False) 
        ControlsController.start_sync_in_dialog(self.app)

    def update_selected_channels(self, channels_str):
        """
        Updates the selected channels in the main application based on detection results.

        Args:
            channels_str (str): A string representation of the detected channel list (e.g., "[1, 2, 3]").
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController
        channels_str_clean = channels_str.replace("[", "").replace("]", "").strip()
        channels = [int(num) - 1 for num in channels_str_clean.split(",")]
        channels.sort()
        for ch_checkbox in self.app.channel_checkboxes:
            label_text = ch_checkbox.label.text()
            ch_index = extract_channel_from_label(label_text)
            ch_checkbox.set_checked(ch_index in channels)
        self.app.selected_channels = channels
        ControlsController.set_selected_channels_to_settings(self.app)
        self.app.plots_to_show = channels[:4]
        self.app.settings.setValue(
            s.SETTINGS_PLOTS_TO_SHOW, json.dumps(self.app.plots_to_show)
        )
        PlotsController.clear_plots(self.app)
        PlotsController.generate_plots(self.app)

    def update_channel_connection_type(self, connection_type):
        """
        Updates the channel connection type (USB/SMA) in the main application.

        Args:
            connection_type (str): The selected connection type ("USB" or "SMA").
        """
        index = 0 if connection_type == "USB" else 1
        self.app.control_inputs["channel_type"].setCurrentIndex(index)
        self.app.settings.setValue(s.SETTINGS_CONNECTION_TYPE, index)

    def process_detection_result(self, result):
        """
        Processes the raw detection result into a structured format.

        Args:
            result: The raw result object from flim_labs.

        Returns:
            list: A list of parsed detection data.
        """
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
        """
        Handles errors that occur during the detection process.

        Args:
            error_msg (str): The error message from the worker.
        """
        AcquisitionController.check_card_connection(self.app)
        self.flip_timer.stop()
        if hasattr(self, 'connection_type_choose_container'):
            self.choose_connection_container.setVisible(False) 
        if hasattr(self, 'sync_in_warning_container'):
            self.sync_in_warning_container.setVisible(False)          
        self.loader_label.setVisible(False)
        self.error_icon.setVisible(True)
        self.success_icon.setVisible(False)
        self.label.setText(f"Error: {error_msg}")
        self.yes_button.setEnabled(True)
        self.yes_button.setText(" RETRY")
        self.yes_button.setIcon((QIcon(resource_path("assets/refresh-icon.png"))))
        self.no_button.setEnabled(True)
        self.no_button.setText("CANCEL")

    def on_no_button_click(self):
        """Closes the dialog when the 'NO' or 'CANCEL' button is clicked."""
        self.close()

    def closeEvent(self, event):
        """
        Handles the close event of the dialog.

        Ensures the worker thread is terminated before closing.

        Args:
            event: The close event.
        """
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        super().closeEvent(event)


class DetectChannelsButton(QWidget):
    """A button widget that opens the channel detection dialog."""
    def __init__(self, app, parent=None):
        """
        Initializes the DetectChannelsButton.

        Args:
            app: The main application instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
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
        self.app.widgets[s.CHANNELS_DETECTION_BUTTON] = self.detect_button
        container.addWidget(self.detect_button, alignment=Qt.AlignmentFlag.AlignBottom)
        self.setLayout(container)

    def open_channels_detection_dialog(self):
        """Creates and shows the channel detection dialog."""
        dialog = DetectChannelsDialog(self.app)
        dialog.exec()


class ChannelsDetection:
    """A data class to hold and parse raw channel detection results."""
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
        """
        Initializes the ChannelsDetection data object.

        Args:
            sma_channels: List of detected SMA channels.
            usb_channels: List of detected USB channels.
            sma_frame: Boolean indicating SMA frame detection.
            usb_frame: Boolean indicating USB frame detection.
            sma_line: Boolean indicating SMA line detection.
            usb_line: Boolean indicating USB line detection.
            sma_pixel: Boolean indicating SMA pixel detection.
            usb_pixel: Boolean indicating USB pixel detection.
            sma_laser_sync_in: Boolean indicating SMA Sync In detection.
            usb_laser_sync_in: Boolean indicating USB Sync In detection.
            usb_laser_sync_out: Boolean indicating USB Sync Out detection.
        """
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
        """
        Parses all raw detection data into a structured list.

        Returns:
            list: A list containing parsed data for each connection type.
        """
        # Channels
        channels_data = self.get_channels_connection()
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

    def get_channels_connection(self):
        """
        Parses the channel connection data.

        Returns:
            list: A list of tuples with channel info (name, status, type).
        """
        results = []
        if (len(self.sma_channels) == 0 and len(self.usb_channels) == 0):
            results.append(("Channels:", None, "Not Detected"))
        else:
            results.append(
                ("Channels:", str([ch + 1 for ch in self.sma_channels]), "SMA")
            )
            results.append(
                ("Channels:", str([ch + 1 for ch in self.usb_channels]), "USB")
            )        
        return results

    def get_frame_connection(self):
        """
        Parses the frame (REF 1) connection data.

        Returns:
            list: A list of tuples with frame info.
        """
        results = []
        if self.sma_frame:
            results.append(("REF 1 (Frame):", "Detected", "SMA"))
        if self.usb_frame:
            results.append(("REF 1 (Frame):", "Detected", "USB"))
        if not results:
            results.append(("REF 1 (Frame):", None, "Not Detected"))
        return results

    def get_line_connection(self):
        """
        Parses the line (REF 2) connection data.

        Returns:
            list: A list of tuples with line info.
        """
        results = []
        if self.sma_line:
            results.append(("REF 2 (Line):", "Detected", "SMA"))
        if self.usb_line:
            results.append(("REF 2 (Line):", "Detected", "USB"))
        if not results:
            results.append(("REF 2 (Line):", None, "Not Detected"))
        return results

    def get_pixel_connection(self):
        """
        Parses the pixel (REF 3) connection data.

        Returns:
            list: A list of tuples with pixel info.
        """
        results = []
        if self.sma_pixel:
            results.append(("REF 3 (Pixel):", "Detected", "SMA"))
        if self.usb_pixel:
            results.append(("REF 3 (Pixel):", "Detected", "USB"))
        if not results:
            results.append(("REF 3 (Pixel):", None, "Not Detected"))
        return results

    def get_sync_in_connection(self):
        """
        Parses the Sync In connection data.

        Returns:
            list: A list of tuples with Sync In info.
        """
        results = []
        if self.sma_laser_sync_in:
            results.append(("Sync In:", "Detected", "SMA"))
        if self.usb_laser_sync_in:
            results.append(("Sync In:", "Detected", "USB"))
        if not results:
            results.append(("Sync In:", None, "Not Detected"))
        return results

    def get_sync_out_connection(self):
        """
        Parses the Sync Out connection data.

        Returns:
            list: A list of tuples with Sync Out info.
        """
        results = []
        if self.usb_laser_sync_out:
            results.append(("Sync Out:", "Detected", "USB"))
        if not results:
            results.append(("Sync Out:", None, "Not Detected"))
        return results