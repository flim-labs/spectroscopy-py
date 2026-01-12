"""
This module serves as the main entry point for the Spectroscopy application.

It initializes the main window, settings, UI components, and controllers.
It also handles the application's main event loop.
"""

from functools import partial
import json
import os
import queue
import sys
from utils.export_data import ExportData
import settings.settings as s
from utils.settings_utilities import check_and_update_ini
import numpy as np

from PyQt6.QtCore import (
    QTimer,
    QSettings,
    QEvent,
    QThreadPool,
    QtMsgType,
    qInstallMessageHandler,
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
)
from utils.logo_utilities import OverlayWidget
from components.read_data import (
    ReadDataControls,
)
from core.acquisition_controller import AcquisitionController
from core.controls_controller import ControlsController
from core.phasors_controller import PhasorsController
from core.plots_controller import PlotsController
from core.ui_controller import UIController


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class SpectroscopyWindow(QWidget):
    """
    The main window for the Spectroscopy application.

    This class is responsible for initializing the application's state,
    UI, and connecting all the components.
    """

    def __init__(self):
        """
        Initializes the SpectroscopyWindow instance.
        """
        super().__init__()
        self._initialize_settings()
        self._initialize_attributes()
        self._initialize_ui()
        self._initialize_controllers_and_timers()

    def _initialize_settings(self):
        """
        Initializes application settings from the settings file.
        """
        self.settings = QSettings("settings.ini", QSettings.Format.IniFormat)

        # General Application Settings
        default_time_shifts = self.settings.value(
            s.SETTINGS_TIME_SHIFTS, s.DEFAULT_TIME_SHIFTS
        )
        self.time_shifts = (
            {int(k): v for k, v in json.loads(default_time_shifts).items()}
            if default_time_shifts
            else {}
        )

        default_lin_log_mode = self.settings.value(
            s.SETTINGS_LIN_LOG_MODE, s.DEFAULT_LIN_LOG_MODE
        )
        self.lin_log_mode = (
            {int(k): v for k, v in json.loads(default_lin_log_mode).items()}
            if default_lin_log_mode
            else {}
        )

        default_roi = self.settings.value(s.SETTINGS_ROI, s.DEFAULT_ROI)
        self.roi = (
            {int(k): v for k, v in json.loads(default_roi).items()}
            if default_roi
            else {}
        )

        self.harmonic_selector_value = int(
            self.settings.value(s.SETTINGS_HARMONIC, s.SETTINGS_HARMONIC_DEFAULT)
        )

        default_plots_to_show = self.settings.value(
            s.SETTINGS_PLOTS_TO_SHOW, s.DEFAULT_PLOTS_TO_SHOW
        )
        self.plots_to_show = (
            json.loads(default_plots_to_show) if default_plots_to_show else []
        )

        self.selected_sync = self.settings.value(s.SETTINGS_SYNC, s.DEFAULT_SYNC)
        self.sync_in_frequency_mhz = float(
            self.settings.value(
                s.SETTINGS_SYNC_IN_FREQUENCY_MHZ, s.DEFAULT_SYNC_IN_FREQUENCY_MHZ
            )
        )

        write_data_gui = self.settings.value(
            s.SETTINGS_WRITE_DATA, s.DEFAULT_WRITE_DATA
        )
        self.write_data_gui = str(write_data_gui).lower() == "true"

        pico_mode_value = self.settings.value(s.SETTINGS_PICO_MODE, s.DEFAULT_PICO_MODE)
        self.pico_mode = str(pico_mode_value).lower() == "true"

        time_tagger = self.settings.value(s.SETTINGS_TIME_TAGGER, s.DEFAULT_TIME_TAGGER)
        self.time_tagger = str(time_tagger).lower() == "true"

        show_SBR = self.settings.value(s.SETTINGS_SHOW_SBR, s.DEFAULT_SHOW_SBR)
        self.show_SBR = str(show_SBR).lower() == "true"

        self.acquire_read_mode = self.settings.value(
            s.SETTINGS_ACQUIRE_READ_MODE, s.DEFAULT_ACQUIRE_READ_MODE
        )

        quantized_phasors = self.settings.value(
            s.SETTINGS_QUANTIZE_PHASORS, s.DEFAULT_QUANTIZE_PHASORS
        )
        self.quantized_phasors = str(quantized_phasors).lower() == "true"

        self.phasors_resolution = int(
            self.settings.value(
                s.SETTINGS_PHASORS_RESOLUTION, s.DEFAULT_PHASORS_RESOLUTION
            )
        )

        self.fitting_algorithm = int(
            self.settings.value(
                s.SETTINGS_FITTING_ALGORITHM, s.DEFAULT_FITTING_ALGORITHM
            )
        )

    def _initialize_attributes(self):
        """
        Initializes instance attributes and data structures.
        """
        self.threadpool = QThreadPool()
        self.reader_data = s.READER_DATA
        self.update_plots_enabled = False
        self.widgets = {}
        self.channel_checkboxes = []
        self.sync_buttons = []
        self.control_inputs = {}
        self.mode = s.MODE_STOPPED
        self.tab_selected = s.TAB_SPECTROSCOPY
        self.reference_file = None
        self.overlay2 = None
        self.acquisition_stopped = False
        self.intensities_widgets = {}
        self.intensity_lines = s.INTENSITY_LINES
        self.phasors_charts = {}
        self.phasors_widgets = {}
        self.phasors_coords = {}
        self.phasors_lifetime_points = {}
        self.phasors_lifetime_texts = {}
        self.phasors_colorbars = {}
        self.phasors_legends = {}
        self.phasors_legend_labels = {}
        self.phasors_clusters_center = {}
        self.phasors_crosshairs = {}
        self.quantization_images = {}
        self.cps_widgets = {}
        self.cps_widgets_animation = {}
        self.cps_counts = {}
        self.SBR_items = {}
        self.acquisition_time_countdown_widgets = {}
        self.decay_curves = s.DECAY_CURVES
        self.decay_widgets = {}
        self.all_cps_counts = []
        self.all_SBR_counts = []
        self.cached_decay_x_values = np.array([])
        self.cached_decay_values = s.CACHED_DECAY_VALUES
        self.spectroscopy_axis_x = np.arange(1)
        self.lin_log_switches = {}
        self.decay_curves_queue = queue.Queue()
        self.cached_time_span_seconds = 3
        self.selected_channels = []
        self.plots_to_show_already_appear = False
        self.write_data = True
        self.show_bin_file_size_helper = self.write_data_gui
        self.bin_file_size = ""
        self.bin_file_size_label = QLabel("")
        self.saved_spectroscopy_reference = None
        self.harmonic_selector_shown = False
        self.fitting_config_popup = None
        self.phasors_harmonic_selected = 1
        self.refresh_reader_popup_plots = False

    def _initialize_ui(self):
        """
        Initializes the user interface components.
        """
        (self.top_bar, self.grid_layout) = UIController.init_ui(self)
        PlotsController.generate_plots(self)
        self.overlay = OverlayWidget(self)
        self.installEventFilter(self)

    def _initialize_controllers_and_timers(self):
        """
        Initializes controllers, timers, and connects signals.
        """
        ControlsController.get_selected_channels_from_settings(self)
        ControlsController.update_pico_mode_toggle(self)
        ControlsController.on_tab_selected(self, s.TAB_SPECTROSCOPY)
        self.all_phasors_points = PhasorsController.get_empty_phasors_points()

        self.pull_from_queue_timer = QTimer()
        self.pull_from_queue_timer.timeout.connect(
            partial(AcquisitionController.pull_from_queue, self)
        )

        ExportData.calc_exported_file_size(self)
        ReadDataControls.handle_widgets_visibility(
            self, self.acquire_read_mode == "read"
        )
        ControlsController.toggle_intensities_widgets_visibility(self)
        AcquisitionController.check_card_connection(self)

    def closeEvent(self, event):
        """
        Handles the window close event.

        Saves window size and position, and closes any open pop-up windows.

        Args:
            event: The close event.
        """
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())

        popups_to_close = [
            s.PLOTS_CONFIG_POPUP,
            s.READER_POPUP,
            s.READER_METADATA_POPUP,
            s.FITTING_POPUP,
        ]
        for popup_key in popups_to_close:
            if popup_key in self.widgets and self.widgets[popup_key] is not None:
                self.widgets[popup_key].close()

        event.accept()

    def eventFilter(self, source, event):
        """
        Filters events for the main window.

        Used to ensure the overlay widget is always on top after a resize or
        mouse press/release event.

        Args:
            source: The object that generated the event.
            event: The event to be filtered.

        Returns:
            The result of the parent's eventFilter.
        """
        try:
            if event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
            ):
                if self.overlay:
                    self.overlay.raise_()
                    self.overlay.resize(self.size())
            return super().eventFilter(source, event)
        except Exception:
            # Pass silently on any exception during event filtering
            pass
        return False


def main():
    """
    The main function to run the application.
    """
    # Check correct app version in .ini file
    check_and_update_ini()
    # Remove .pid file if it exists
    if os.path.exists(".pid"):
        os.remove(".pid")

    app = QApplication(sys.argv)
    window = SpectroscopyWindow()
    window.showMaximized()
    window.show()

    def custom_message_handler(msg_type, context, message):
        """
        Custom handler for Qt messages to suppress specific warnings.
        """
        if (
            msg_type == QtMsgType.QtWarningMsg
            and "QWindowsWindow::setGeometry" in message
        ):
            return
        print(f"Qt Message: {message} (Type: {msg_type})")

    qInstallMessageHandler(custom_message_handler)

    exit_code = app.exec()

    if window.pull_from_queue_timer.isActive():
        window.pull_from_queue_timer.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
