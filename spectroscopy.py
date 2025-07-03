
from functools import partial
import json
import os
import queue
from math import floor, log
import sys
from components.settings_utilities import check_and_update_ini
import numpy as np

from PyQt6.QtCore import QTimer, QSettings, QEvent, QThreadPool, QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLayout,
    QLabel,
)
from components.helpers import calc_SBR, format_size
from components.laserblood_metadata_popup import LaserbloodMetadataPopup
from components.logo_utilities import OverlayWidget
from components.read_data import (
    ReadData,
    ReadDataControls,
)
from core.acquisition_controller import AcquisitionController
from core.controls_controller import ControlsController
from core.phasors_controller import PhasorsController
from core.plots_controller import PlotsController
from core.ui_controller import UIController
from settings import *
from laserblood_settings import *

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class SpectroscopyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = self.init_settings()
        ## LASERBLOOD METADATA
        self.laserblood_settings = json.loads(
            self.settings.value(METADATA_LASERBLOOD_KEY, LASERBLOOD_METADATA_JSON)
        )
        self.laserblood_laser_type = self.settings.value(
            SETTINGS_LASER_TYPE, DEFAULT_LASER_TYPE
        )
        self.laserblood_filter_type = self.settings.value(
            SETTINGS_FILTER_TYPE, DEFAULT_FILTER_TYPE
        )
        self.laserblood_new_added_inputs = json.loads(
            self.settings.value(
                NEW_ADDED_LASERBLOOD_INPUTS_KEY, NEW_ADDED_LASERBLOOD_INPUTS_JSON
            )
        )
        self.laserblood_widgets = {}           
        self.threadpool = QThreadPool()
        self.reader_data = READER_DATA
        self.update_plots_enabled = False
        self.widgets = {}
        self.channel_checkboxes = []
        self.sync_buttons = []
        self.control_inputs = {}
        self.mode = MODE_STOPPED
        self.tab_selected = TAB_SPECTROSCOPY
        self.reference_file = None
        self.overlay2 = None
        self.acquisition_stopped = False
        self.intensities_widgets = {}
        self.intensity_lines = INTENSITY_LINES
        self.phasors_charts = {}
        self.phasors_widgets = {}
        self.phasors_coords = {}
        self.phasors_lifetime_points = {}
        self.phasors_lifetime_texts = {}
        self.phasors_colorbars = {}
        self.phasors_legends = {}
        self.phasors_clusters_center = {}
        self.phasors_crosshairs = {}
        self.quantization_images = {}
        self.cps_widgets = {}
        self.cps_widgets_animation = {}
        self.cps_counts = {}
        self.SBR_items = {}
        self.acquisition_time_countdown_widgets = {}
        self.decay_curves = DECAY_CURVES
        self.decay_widgets = {}
        self.all_cps_counts = []
        self.all_SBR_counts = []
        self.cached_decay_x_values = np.array([])
        self.cached_decay_values = CACHED_DECAY_VALUES
        self.spectroscopy_axis_x = np.arange(1)
        self.lin_log_switches = {}
        default_time_shifts = self.settings.value(
            SETTINGS_TIME_SHIFTS, DEFAULT_TIME_SHIFTS
        )
        self.time_shifts = (
            {int(key): value for key, value in json.loads(default_time_shifts).items()}
            if default_time_shifts is not None
            else {}
        )
        default_lin_log_mode = self.settings.value(
            SETTINGS_LIN_LOG_MODE, DEFAULT_LIN_LOG_MODE
        )
        self.lin_log_mode = (
            {int(key): value for key, value in json.loads(default_lin_log_mode).items()}
            if default_lin_log_mode is not None
            else {}
        )
        # ROI
        default_roi = self.settings.value(SETTINGS_ROI, DEFAULT_ROI)
        self.roi = (
            {int(key): value for key, value in json.loads(default_roi).items()}
            if default_roi is not None
            else {}
        )
        self.decay_curves_queue = queue.Queue()
        self.harmonic_selector_value = int(
            self.settings.value(SETTINGS_HARMONIC, SETTINGS_HARMONIC_DEFAULT)
        )
        self.cached_time_span_seconds = 3
        self.selected_channels = []
        default_plots_to_show = self.settings.value(
            SETTINGS_PLOTS_TO_SHOW, DEFAULT_PLOTS_TO_SHOW
        )
        self.plots_to_show = (
            json.loads(default_plots_to_show)
            if default_plots_to_show is not None
            else []
        )
        self.plots_to_show_already_appear = False
        self.selected_sync = self.settings.value(SETTINGS_SYNC, DEFAULT_SYNC)
        self.sync_in_frequency_mhz = float(
            self.settings.value(
                SETTINGS_SYNC_IN_FREQUENCY_MHZ, DEFAULT_SYNC_IN_FREQUENCY_MHZ
            )
        )
        self.write_data = True
        write_data_gui = self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA)
        self.write_data_gui = write_data_gui == "true" or write_data_gui == True
        self.show_bin_file_size_helper = self.write_data_gui
        # Time tagger
        time_tagger = self.settings.value(SETTINGS_TIME_TAGGER, DEFAULT_TIME_TAGGER)
        self.time_tagger = time_tagger == "true" or time_tagger == True
        # SBR
        show_SBR = self.settings.value(SETTINGS_SHOW_SBR, DEFAULT_SHOW_SBR)
        self.show_SBR = show_SBR == "true" or show_SBR == True        

        self.bin_file_size = ""
        self.bin_file_size_label = QLabel("")
        
        self.saved_spectroscopy_reference = None

        self.acquire_read_mode = self.settings.value(
            SETTINGS_ACQUIRE_READ_MODE, DEFAULT_ACQUIRE_READ_MODE
        )
        self.harmonic_selector_shown = False
        quantized_phasors = self.settings.value(
            SETTINGS_QUANTIZE_PHASORS, DEFAULT_QUANTIZE_PHASORS
        )
        self.quantized_phasors = (
            quantized_phasors == "true" or quantized_phasors == True
        )
        self.phasors_resolution = int(
            self.settings.value(SETTINGS_PHASORS_RESOLUTION, DEFAULT_PHASORS_RESOLUTION)
        )
        self.replicates = 1
        self.get_selected_channels_from_settings()
        (self.top_bar, self.grid_layout) = UIController.init_ui(self)
        ControlsController.on_tab_selected(self, TAB_SPECTROSCOPY)
        # self.update_sync_in_button()
        PlotsController.generate_plots(self)
        self.all_phasors_points = PhasorsController.get_empty_phasors_points()
        self.overlay = OverlayWidget(self)
        self.installEventFilter(self)
        self.pull_from_queue_timer = QTimer()
        self.pull_from_queue_timer.timeout.connect(partial(AcquisitionController.pull_from_queue, self))
        self.fitting_config_popup = None
        self.calc_exported_file_size()
        self.phasors_harmonic_selected = 1
        ReadDataControls.handle_widgets_visibility(
            self, self.acquire_read_mode == "read"
        )
        ControlsController.toggle_intensities_widgets_visibility(self)
        self.refresh_reader_popup_plots = False
        frequency_mhz = ControlsController.get_current_frequency_mhz(self)
        LaserbloodMetadataPopup.set_frequency_mhz(frequency_mhz, self)
        LaserbloodMetadataPopup.set_FPGA_firmware(self)
        # Check card connection
        AcquisitionController.check_card_connection(self)        
   

    @staticmethod
    def init_settings():
        settings = QSettings("settings.ini", QSettings.Format.IniFormat)
        return settings

  

    def acquired_spectroscopy_data_to_fit(self, read):
        data = []
        channels_shown = [
            channel
            for channel in self.plots_to_show
            if channel in self.selected_channels
        ]
        for channel, channel_index in enumerate(channels_shown):
            time_shift = (
                0
                if channel_index not in self.time_shifts
                else self.time_shifts[channel_index]
            )
            x, _ = self.decay_curves[self.tab_selected][channel_index].getData()
            y = self.cached_decay_values[self.tab_selected][channel_index]
            data.append(
                {
                    "x": x * 1000 if read else x,
                    "y": y,
                    "title": "Channel " + str(channel_index + 1),
                    "channel_index": channel_index,
                    "time_shift": time_shift,
                }
            )
        return data, time_shift

    def read_spectroscopy_data_to_fit(self):
        data = ReadData.get_spectroscopy_data_to_fit(self)
        return data

    

    def get_selected_channels_from_settings(self):
        self.selected_channels = []
        for i in range(MAX_CHANNELS):
            if self.settings.value(f"channel_{i}", "false") == "true":
                self.selected_channels.append(i)

    def set_selected_channels_to_settings(self):
        for i in range(MAX_CHANNELS):
            self.settings.setValue(f"channel_{i}", "false")
            if i in self.selected_channels:
                self.settings.setValue(f"channel_{i}", "true")

    def clear_layout_tree(self, layout: QLayout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout_tree(item.layout())
            del layout

    def calc_exported_file_size(self):
        free_running = self.settings.value(SETTINGS_FREE_RUNNING, DEFAULT_FREE_RUNNING)
        acquisition_time = self.settings.value(
            SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME
        )
        bin_width = self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)
        if free_running is True or acquisition_time is None:
            file_size_MB = len(self.selected_channels) * (1000 / int(bin_width))
            self.bin_file_size = format_size(file_size_MB * 1024 * 1024)
            self.bin_file_size_label.setText(
                "File size: " + str(self.bin_file_size) + "/s"
            )
        else:
            file_size_MB = (
                int(acquisition_time)
                * len(self.selected_channels)
                * (1000 / int(bin_width))
            )
            self.bin_file_size = format_size(file_size_MB * 1024 * 1024)
            self.bin_file_size_label.setText("File size: " + str(self.bin_file_size))
   
 
 
    def humanize_number(self, number):
        if number == 0:
            return "0"
        units = ["", "K", "M", "G", "T", "P"]
        k = 1000.0
        magnitude = int(floor(log(number, k)))
        scaled_number = number / k**magnitude
        return f"{int(scaled_number)}.{str(scaled_number).split('.')[1][:2]}{units[magnitude]}"
    

    def closeEvent(self, event):
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        if PLOTS_CONFIG_POPUP in self.widgets:
            self.widgets[PLOTS_CONFIG_POPUP].close()
        if LASERBLOOD_METADATA_POPUP in self.widgets:        
            self.widgets[LASERBLOOD_METADATA_POPUP].close()    
        if READER_POPUP in self.widgets:
            self.widgets[READER_POPUP].close()
        if READER_METADATA_POPUP in self.widgets:
            self.widgets[READER_METADATA_POPUP].close()
        if FITTING_POPUP in self.widgets:
            self.widgets[FITTING_POPUP].close()
        event.accept()

    def eventFilter(self, source, event):
        try:
            if event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
            ):
                self.overlay.raise_()
                self.overlay.resize(self.size())
            return super().eventFilter(source, event)
        except:
            pass



if __name__ == "__main__":
    # check correct app version in .ini file
    check_and_update_ini()
    # remove .pid file if exists
    if os.path.exists(".pid"):
        os.remove(".pid")
    app = QApplication(sys.argv)
    window = SpectroscopyWindow()
    window.showMaximized()
    window.show()
    def custom_message_handler(msg_type, context, message):
        if msg_type == QtMsgType.QtWarningMsg:
            if "QWindowsWindow::setGeometry" in message:
                return  
        print(message) 
    qInstallMessageHandler(custom_message_handler)        
    app.exec()
    window.pull_from_queue_timer.stop()
    sys.exit()
