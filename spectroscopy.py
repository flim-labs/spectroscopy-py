import time
from functools import partial
import json
import os
import queue
from math import floor, log
import sys
from components.settings_utilities import check_and_update_ini
import flim_labs
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer, QSettings, QSize, Qt, QEvent, QThreadPool, QtMsgType, qInstallMessageHandler
from PyQt6.QtGui import QPixmap, QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QHBoxLayout,
    QLayout,
    QLabel,
    QSizePolicy,
    QPushButton,
    QDialog,
    QMessageBox,
    QFileDialog,
)

from components.animations import VibrantAnimation
from components.box_message import BoxMessage
from components.buttons import (
    CollapseButton,
    ReadAcquireModeButton,
    TimeTaggerWidget,
)
from components.channels_detection import DetectChannelsButton
from components.check_card import CheckCard
from components.export_data import ExportData
from components.fancy_checkbox import FancyButton
from components.fitting_config_popup import FittingDecayConfigPopup
from components.gradient_text import GradientText
from components.gui_styles import GUIStyles
from components.helpers import calc_SBR, format_size, get_realtime_adjustment_value, mhz_to_ns, ns_to_mhz
from components.input_number_control import InputNumberControl, InputFloatControl
from components.laserblood_metadata_popup import LaserbloodMetadataPopup
from components.layout_utilities import draw_layout_separator, hide_layout, show_layout
from components.lin_log_control import LinLogControl
from components.link_widget import LinkWidget
from components.logo_utilities import OverlayWidget, TitlebarIcon
from components.plots_config import PlotsConfigPopup
from components.progress_bar import ProgressBar
from components.read_data import (
    ReadData,
    ReadDataControls,
    ReaderMetadataPopup,
    ReaderPopup,
)
from components.resource_path import resource_path
from components.select_control import SelectControl
from components.spectroscopy_curve_time_shift import SpectroscopyTimeShift
from components.switch_control import SwitchControl
from components.sync_in_popup import SyncInDialog
from components.time_tagger import TimeTaggerController
from core.acquisition_controller import AcquisitionController
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
        self.on_tab_selected(TAB_SPECTROSCOPY)
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
        self.toggle_intensities_widgets_visibility()
        self.refresh_reader_popup_plots = False
        frequency_mhz = self.get_current_frequency_mhz()
        LaserbloodMetadataPopup.set_frequency_mhz(frequency_mhz, self)
        LaserbloodMetadataPopup.set_FPGA_firmware(self)
        # Check card connection
        AcquisitionController.check_card_connection(self)        
   

    @staticmethod
    def init_settings():
        settings = QSettings("settings.ini", QSettings.Format.IniFormat)
        return settings
  

    def fit_button_show(self):
        if FIT_BTN not in self.control_inputs:
            self.control_inputs[FIT_BTN] = QPushButton("FIT")
            self.control_inputs[FIT_BTN].setFlat(True)
            self.control_inputs[FIT_BTN].setFixedHeight(55)
            self.control_inputs[FIT_BTN].setCursor(Qt.CursorShape.PointingHandCursor)
            self.control_inputs[FIT_BTN].clicked.connect(self.on_fit_btn_click)
            self.control_inputs[FIT_BTN].setStyleSheet(
                """
            QPushButton {
                background-color: #1E90FF;
                color: white;
                width: 60px;
                border-radius: 5px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 16px;
            }
            """
            )
            self.control_inputs[FIT_BTN_PLACEHOLDER].layout().addWidget(
                self.control_inputs[FIT_BTN]
            )

    
    def fit_button_hide(self):
        if FIT_BTN in self.control_inputs:
            self.control_inputs[FIT_BTN_PLACEHOLDER].layout().removeWidget(
                self.control_inputs[FIT_BTN]
            )
            self.control_inputs[FIT_BTN].deleteLater()
            del self.control_inputs[FIT_BTN]
            self.control_inputs[FIT_BTN_PLACEHOLDER].layout().setContentsMargins(
                0, 0, 0, 0
            )
   

    def on_tab_selected(self, tab_name):
        self.control_inputs[self.tab_selected].setChecked(False)
        self.tab_selected = tab_name
        self.control_inputs[self.tab_selected].setChecked(True)
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self)
        self.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
        self.control_inputs[EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and self.tab_selected != TAB_FITTING
        )
        if self.acquire_read_mode == "acquire":
            PlotsController.clear_plots(self, deep_clear=False)
            PlotsController.generate_plots(self)
            self.toggle_intensities_widgets_visibility()
        else:
            ReadDataControls.plot_data_on_tab_change(self)
        if tab_name == TAB_SPECTROSCOPY:
            self.widgets[TIME_TAGGER_WIDGET].setVisible(self.write_data_gui)
            self.fit_button_hide()
            self.hide_harmonic_selector()
            hide_layout(self.control_inputs["phasors_resolution_container"])
            hide_layout(self.control_inputs["quantize_phasors_container"])
            # hide tau input
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs["calibration"].show()
            self.control_inputs["calibration_label"].show()
            current_tau = self.settings.value(SETTINGS_TAU_NS, "0")
            self.control_inputs["tau"].setValue(float(current_tau))
            self.on_tau_change(float(current_tau))
            current_calibration = self.settings.value(
                SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE
            )
            self.on_calibration_change(int(current_calibration))
            self.control_inputs[LOAD_REF_BTN].hide()
            channels_grid = self.widgets[CHANNELS_GRID]
            plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
            if plot_config_btn is not None:
                plot_config_btn.setVisible(True)
        elif tab_name == TAB_FITTING:
            self.widgets[TIME_TAGGER_WIDGET].setVisible(self.write_data_gui)
            if ReadDataControls.fit_button_enabled(self):
                self.fit_button_show()
            else:
                self.fit_button_hide()
            self.control_inputs[LOAD_REF_BTN].hide()
            self.hide_harmonic_selector()
            hide_layout(self.control_inputs["phasors_resolution_container"])
            hide_layout(self.control_inputs["quantize_phasors_container"])
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs["calibration"].hide()
            self.control_inputs["calibration_label"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            channels_grid = self.widgets[CHANNELS_GRID]
            plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
            if plot_config_btn is not None:
                plot_config_btn.setVisible(True)
        elif tab_name == TAB_PHASORS:
            self.widgets[TIME_TAGGER_WIDGET].setVisible(False)
            self.fit_button_hide()
            (
                show_layout(self.control_inputs["phasors_resolution_container"])
                if self.quantized_phasors
                else hide_layout(self.control_inputs["phasors_resolution_container"])
            )
            show_layout(self.control_inputs["quantize_phasors_container"])
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs["calibration"].hide()
            self.control_inputs["calibration_label"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            if self.acquire_read_mode == "read":
                self.control_inputs[LOAD_REF_BTN].hide()
            else:
                self.control_inputs[LOAD_REF_BTN].show()
                self.control_inputs[LOAD_REF_BTN].setText("LOAD REFERENCE")
            channels_grid = self.widgets[CHANNELS_GRID]
            PhasorsController.initialize_phasor_feature(self)
            PhasorsController.generate_phasors_cluster_center(
                self,
                self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1
            )
            PhasorsController.generate_phasors_legend(
                self,
                self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1
            )
            if self.harmonic_selector_shown:
                if self.quantized_phasors:
                    PhasorsController.quantize_phasors(
                        self,
                        self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1,
                        bins=int(PHASORS_RESOLUTIONS[self.phasors_resolution]),
                    )
                else:
                    self.on_quantize_phasors_changed(False)
                self.show_harmonic_selector(
                    self.control_inputs[SETTINGS_HARMONIC].value()
                )
            plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
            if plot_config_btn is not None:
                plot_config_btn.setVisible(False)


    def on_start_button_click(self):
        if self.mode == MODE_STOPPED:
            self.acquisition_stopped = False
            if not (self.is_phasors()):
                self.harmonic_selector_shown = False
            AcquisitionController.begin_spectroscopy_experiment(self)
        elif self.mode == MODE_RUNNING:
            self.acquisition_stopped = True
            AcquisitionController.stop_spectroscopy_experiment(self)

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

    def on_fit_btn_click(self):
        data = []
        time_shift = 0
        frequency_mhz = self.get_frequency_mhz()
        laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
        if self.acquire_read_mode == "read":
            if self.reader_data["fitting"]["data"]["spectroscopy_data"]:
                data, time_shift = self.acquired_spectroscopy_data_to_fit(read=True)
            else:
                active_channels = ReadData.get_fitting_active_channels(self)
                for channel in active_channels:
                    data.append(
                        {
                            "x": [0],
                            "y": [0],
                            "time_shift": 0,
                            "title": "Channel " + str(channel + 1),
                            "channel_index": channel,
                        }
                    )
        else:
            data, time_shift = self.acquired_spectroscopy_data_to_fit(read=False)
        # check if every x len is the same as y len
        if not all(len(data[0]["x"]) == len(data[i]["x"]) for i in range(1, len(data))):
            BoxMessage.setup(
                "Error",
                "Different x-axis lengths detected. Please, check the data.",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return
        preloaded_fitting_results = ReadData.preloaded_fitting_data(self)
        read_mode = True if preloaded_fitting_results is not None else False
        self.fitting_config_popup = FittingDecayConfigPopup(
            self,
            data,
            read_mode=read_mode,
            preloaded_fitting=preloaded_fitting_results,
            save_plot_img=self.acquire_read_mode == "read",
            y_data_shift=time_shift,
            laser_period_ns=laser_period_ns
        )
        self.fitting_config_popup.show()

    def on_tau_change(self, value):
        self.settings.setValue(SETTINGS_TAU_NS, value)

    def on_harmonic_change(self, value):
        self.settings.setValue(SETTINGS_HARMONIC, value)
        
    def on_replicate_change(self, value):
        self.replicates = int(value)    

    def on_load_reference(self):
        if self.tab_selected == TAB_PHASORS:
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            # extension supported: .reference.json
            dialog.setNameFilter("Reference files (*reference.json)")
            dialog.setDefaultSuffix("reference.json")
            file_name, _ = dialog.getOpenFileName(
                self,
                "Load reference file",
                "",
                "Reference files (*reference.json)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_name:
                self.reference_file = file_name


    def get_free_running_state(self):
        return self.control_inputs[SETTINGS_FREE_RUNNING].isChecked()

    def on_acquisition_time_change(self, value):
        self.settings.setValue(SETTINGS_ACQUISITION_TIME, value)
        self.calc_exported_file_size()

    def on_cps_threshold_change(self, value):
        self.settings.setValue(SETTINGS_CPS_THRESHOLD, value)
        LaserbloodMetadataPopup.set_cps_threshold(self, value)

    def on_time_span_change(self, value):
        self.settings.setValue(SETTINGS_TIME_SPAN, value)

    def on_free_running_changed(self, state):
        self.control_inputs[SETTINGS_ACQUISITION_TIME].setEnabled(not state)
        self.settings.setValue(SETTINGS_FREE_RUNNING, state)
        self.calc_exported_file_size()

    def toggle_intensities_widgets_visibility(self):
        if self.intensities_widgets:
            for _, widget in self.intensities_widgets.items():
                if widget and isinstance(widget, QWidget):
                    widget.setVisible(self.acquire_read_mode == "acquire")

    def on_bin_width_change(self, value):
        self.settings.setValue(SETTINGS_BIN_WIDTH, value)
        self.calc_exported_file_size()

    def on_connection_type_value_change(self, value):
        self.settings.setValue(SETTINGS_CONNECTION_TYPE, value)
        LaserbloodMetadataPopup.set_FPGA_firmware(self)

    def on_quantize_phasors_changed(self, value):
        PhasorsController.clear_phasors_points(self)
        harmonic_value = int(self.control_inputs[HARMONIC_SELECTOR].currentText())
        self.quantized_phasors = value
        self.settings.setValue(SETTINGS_QUANTIZE_PHASORS, value)
        container = self.control_inputs["phasors_resolution_container"]
        if value:
            show_layout(container)
            bins = int(PHASORS_RESOLUTIONS[self.phasors_resolution])
            PhasorsController.quantize_phasors(self,harmonic_value, bins)
        else:
            hide_layout(container)
            for channel_index in self.plots_to_show:
                if channel_index in self.quantization_images:
                    widget = self.phasors_widgets[channel_index]
                    widget.removeItem(self.quantization_images[channel_index])
                    del self.quantization_images[channel_index]
                if channel_index in self.phasors_colorbars:
                    widget.removeItem(self.phasors_colorbars[channel_index])
                    del self.phasors_colorbars[channel_index]
            if len(self.plots_to_show) <= len(self.all_phasors_points):
                for channel_index in self.plots_to_show:
                    points = self.all_phasors_points[channel_index][harmonic_value]
                    PhasorsController.draw_points_in_phasors(self, channel_index, harmonic_value, points)

    def on_phasors_resolution_changed(self, value):
        self.phasors_resolution = int(value)
        harmonic_value = int(self.control_inputs[HARMONIC_SELECTOR].currentText())
        self.settings.setValue(SETTINGS_PHASORS_RESOLUTION, value)
        PhasorsController.quantize_phasors(
            self,
            harmonic_value,
            bins=int(PHASORS_RESOLUTIONS[self.phasors_resolution]),
        )

    def on_calibration_change(self, value):
        self.settings.setValue(SETTINGS_CALIBRATION_TYPE, value)
        if value == 1:
            self.control_inputs["tau_label"].show()
            self.control_inputs["tau"].show()
            self.control_inputs[SETTINGS_HARMONIC].show()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].show()
        else:
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()

    def on_export_data_changed(self, state):
        self.settings.setValue(SETTINGS_WRITE_DATA, state)
        self.write_data_gui = state
        if TIME_TAGGER_WIDGET in self.widgets:
            self.widgets[TIME_TAGGER_WIDGET].setVisible(state)
        self.bin_file_size_label.show() if state else self.bin_file_size_label.hide()
        self.calc_exported_file_size() if state else None
        
    def on_show_SBR_changed(self, state):
        self.settings.setValue(SETTINGS_SHOW_SBR, state)
        self.show_SBR = state
        self.SBR_set_visible(state)        
  
  
    def controls_set_enabled(self, enabled: bool):
        for key in self.control_inputs:
            if key != "start_button":
                widget = self.control_inputs[key]
                if isinstance(widget, QWidget):
                    widget.setEnabled(enabled)
        if "time_shift_sliders" in self.control_inputs:
            for _, widget in self.control_inputs["time_shift_sliders"].items():
                widget.setEnabled(enabled)
        if "time_shift_inputs" in self.control_inputs:
            for _, widget in self.control_inputs["time_shift_inputs"].items():
                widget.setEnabled(enabled)
        if enabled:
            self.control_inputs[SETTINGS_ACQUISITION_TIME].setEnabled(
                not self.get_free_running_state())
            
    def SBR_set_visible(self, visible):
        for _, widget in self.SBR_items.items():
            if  widget is not None:
                widget.setVisible(visible)                 

    def time_shifts_set_enabled(self, enabled: bool):
        if "time_shift_sliders" in self.control_inputs:
            for _, widget in self.control_inputs["time_shift_sliders"].items():
                widget.setEnabled(enabled)
        if "time_shift_inputs" in self.control_inputs:
            for _, widget in self.control_inputs["time_shift_inputs"].items():
                widget.setEnabled(enabled)

                
    def reset_time_shifts_values(self):
        if "time_shift_sliders" in self.control_inputs:
            for _, widget in self.control_inputs["time_shift_sliders"].items():
                widget.setValue(0)
        if "time_shift_inputs" in self.control_inputs:
            for _, widget in self.control_inputs["time_shift_inputs"].items():
                widget.setValue(0)                

    def top_bar_set_enabled(self, enabled: bool):
        self.sync_buttons_set_enabled(enabled)
        self.channel_selector_set_enabled(enabled)
        self.controls_set_enabled(enabled)

    def sync_buttons_set_enabled(self, enabled: bool):
        for i in range(len(self.sync_buttons)):
            self.sync_buttons[i][0].setEnabled(enabled)

    def channel_selector_set_enabled(self, enabled: bool):
        for i in range(len(self.channel_checkboxes)):
            self.channel_checkboxes[i].setEnabled(enabled)

    def on_channel_selected(self, checked: bool, channel: int):
        self.settings.setValue(SETTINGS_PLOTS_TO_SHOW, json.dumps(self.plots_to_show))
        if checked:
            if channel not in self.selected_channels:
                self.selected_channels.append(channel)
            if channel not in self.plots_to_show and len(self.plots_to_show) < 4:
                self.plots_to_show.append(channel)
        else:
            if channel in self.selected_channels:
                self.selected_channels.remove(channel)
            if channel in self.plots_to_show:
                self.plots_to_show.remove(channel)
        self.selected_channels.sort()
        self.plots_to_show.sort()
        self.settings.setValue(SETTINGS_PLOTS_TO_SHOW, json.dumps(self.plots_to_show))
        self.set_selected_channels_to_settings()
        PlotsController.clear_plots(self)
        PlotsController.generate_plots(self)
        self.calc_exported_file_size()
        LaserbloodMetadataPopup.set_FPGA_firmware(self)

    def on_sync_selected(self, sync: str):
        def update_phasors_lifetimes():
            frequency_mhz = self.get_current_frequency_mhz()
            LaserbloodMetadataPopup.set_frequency_mhz(frequency_mhz, self)
            if frequency_mhz != 0.0:
                self.time_shifts_set_enabled(True)
                laser_period_ns = mhz_to_ns(frequency_mhz)
                harmonic = self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1
                for _, channel in enumerate(self.plots_to_show):
                    PhasorsController.draw_lifetime_points_in_phasors(
                        self,
                        channel, harmonic, laser_period_ns, frequency_mhz
                    )
            else:
                self.time_shifts_set_enabled(False)
            self.reset_time_shifts_values()                          

        if self.selected_sync == sync and sync == "sync_in":
            self.start_sync_in_dialog()
            update_phasors_lifetimes()
            return
        self.selected_sync = sync
        self.settings.setValue(SETTINGS_SYNC, sync)
        LaserbloodMetadataPopup.set_FPGA_firmware(self)
        update_phasors_lifetimes()

    def start_sync_in_dialog(self):
        dialog = SyncInDialog()
        dialog.exec()
        if dialog.frequency_mhz != 0.0:
            self.sync_in_frequency_mhz = dialog.frequency_mhz
            self.settings.setValue(
                SETTINGS_SYNC_IN_FREQUENCY_MHZ, self.sync_in_frequency_mhz
            )
            self.update_sync_in_button()

    def update_sync_in_button(self):
        if self.sync_in_frequency_mhz == 0.0:
            self.time_shifts_set_enabled(False)
            self.sync_buttons[0][0].setText("Sync In (not detected)")
        else:
            self.time_shifts_set_enabled(True)
            self.sync_buttons[0][0].setText(
                f"Sync In ({self.sync_in_frequency_mhz} MHz)"
            )
    

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

    def get_current_frequency_mhz(self):
        if self.acquire_read_mode == "read":
            return ReadData.get_frequency_mhz(self)
        else:
            if self.selected_sync == "sync_in":
                frequency_mhz = self.sync_in_frequency_mhz
            else:
                frequency_mhz = int(self.selected_sync.split("_")[-1])
            return frequency_mhz

    def export_data(self):
        if not self.write_data:
            return
        dialog = QFileDialog()
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("Binary files (*.bin)")
        dialog.setDefaultSuffix("bin")
        file_name, _ = dialog.getSaveFileName(
            self,
            "Save binary file",
            "",
            "Binary files (*.bin)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_name:
            if not file_name.endswith(".bin"):
                file_name += ".bin"
            try:
                flim_labs.export_data(file_name)
            except Exception as e:
                BoxMessage.setup(
                    "Error",
                    "Error exporting data: " + str(e),
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )

    def get_frequency_mhz(self):
            if self.acquire_read_mode == "read":
                return ReadData.get_frequency_mhz(self)
            else:
                if self.selected_sync == "sync_in":
                    frequency_mhz = self.sync_in_frequency_mhz
                else:
                    frequency_mhz = int(self.selected_sync.split("_")[-1])
                return frequency_mhz
    
    def get_firmware_selected(self, frequency_mhz):    
        connection_type = self.control_inputs["channel_type"].currentText()
        if str(connection_type) == "USB":
            connection_type = "USB"
        else:
            connection_type = "SMA"
        firmware_selected = flim_labs.get_spectroscopy_firmware(
            sync="in" if self.selected_sync == "sync_in" else "out",
            frequency_mhz=frequency_mhz,
            channel=connection_type.lower(),
            channels=self.selected_channels,
            sync_connection="sma",
        )
        return firmware_selected, connection_type
    
    def get_acquisition_time(self):
        return  (
            None
            if self.get_free_running_state()
            else int(
                self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)
            )
        )
    
 


    def show_harmonic_selector(self, harmonics):
        if harmonics > 1:
            self.control_inputs[HARMONIC_SELECTOR].show()
            self.control_inputs[HARMONIC_SELECTOR_LABEL].show()
            selector_harmonics = [
                int(self.control_inputs[HARMONIC_SELECTOR].itemText(index))
                for index in range(self.control_inputs[HARMONIC_SELECTOR].count())
            ]
            if (
                len(selector_harmonics)
                != self.control_inputs[SETTINGS_HARMONIC].value()
                or self.acquire_read_mode == "read"
            ):
                # clear the items
                self.control_inputs[HARMONIC_SELECTOR].clear()
                for i in range(harmonics):
                    self.control_inputs[HARMONIC_SELECTOR].addItem(str(i + 1))
            self.control_inputs[HARMONIC_SELECTOR].setCurrentIndex(           
                self.phasors_harmonic_selected - 1)                      

    def hide_harmonic_selector(self):
        self.control_inputs[HARMONIC_SELECTOR].hide()
        self.control_inputs[HARMONIC_SELECTOR_LABEL].hide()
 

    def is_reference_phasors(self):
        selected_calibration = self.settings.value(
            SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE
        )
        return self.tab_selected == TAB_SPECTROSCOPY and selected_calibration == 1

    def is_phasors(self):
        return self.tab_selected == TAB_PHASORS

    def update_acquisition_countdowns(self, time_ns):
        free_running = self.settings.value(SETTINGS_FREE_RUNNING, DEFAULT_FREE_RUNNING)
        acquisition_time = self.control_inputs[SETTINGS_ACQUISITION_TIME].value()
        if free_running is True or free_running == "true":
            return
        elapsed_time_sec = time_ns / 1_000_000_000
        remaining_time_sec = max(0, acquisition_time - elapsed_time_sec)
        seconds = int(remaining_time_sec)
        milliseconds = int((remaining_time_sec - seconds) * 1000)
        milliseconds = milliseconds // 10
        for _, countdown_widget in self.acquisition_time_countdown_widgets.items():
            if countdown_widget:
                if not countdown_widget.isVisible():
                    countdown_widget.setVisible(True)
                countdown_widget.setText(
                    f"Remaining time: {seconds:02}:{milliseconds:02} (s)"
                )
                
    def update_SBR(self, channel_index, curve):
        if channel_index in self.SBR_items:
            SBR_value = calc_SBR(np.array(curve))
            self.SBR_items[channel_index].setText(f"SBR: {SBR_value:.2f} ㏈")                

    def update_cps(self, channel_index, time_ns, curve):
        # check if there is channel_index'th element in cps_counts
        if not (channel_index in self.cps_counts):
            return
        cps = self.cps_counts[channel_index]
        curve_sum = np.sum(curve)
        # SBR
        SBR_count = calc_SBR(np.array(curve))
        self.all_SBR_counts.append(SBR_count)
        if cps["last_time_ns"] == 0:
            cps["last_time_ns"] = time_ns
            cps["last_count"] = curve_sum
            cps["current_count"] = curve_sum
            return
        cps["current_count"] = cps["current_count"] + np.sum(curve)
        time_elapsed = time_ns - cps["last_time_ns"]
        if time_elapsed > 330_000_000:
            cps_value = (cps["current_count"] - cps["last_count"]) / (
                time_elapsed / 1_000_000_000
            )
            self.all_cps_counts.append(cps_value)            
            humanized_number = self.humanize_number(cps_value)
            self.cps_widgets[channel_index].setText(f"{humanized_number} CPS")
            cps_threshold = self.control_inputs[SETTINGS_CPS_THRESHOLD].value()
            if cps_threshold > 0:
                if cps_value > cps_threshold:
                    self.cps_widgets_animation[channel_index].start()
                else:
                    self.cps_widgets_animation[channel_index].stop()
            #SBR
            if self.show_SBR:
                self.update_SBR(channel_index, curve)                      
            cps["last_time_ns"] = time_ns
            cps["last_count"] = cps["current_count"]

    def humanize_number(self, number):
        if number == 0:
            return "0"
        units = ["", "K", "M", "G", "T", "P"]
        k = 1000.0
        magnitude = int(floor(log(number, k)))
        scaled_number = number / k**magnitude
        return f"{int(scaled_number)}.{str(scaled_number).split('.')[1][:2]}{units[magnitude]}"


    def on_harmonic_selector_change(self, value):
        frequency_mhz = self.get_current_frequency_mhz()
        laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
        PhasorsController.clear_phasors_points(self)
        if not self.phasors_widgets or value < 0:
            return
        self.harmonic_selector_value = int(value) + 1
        self.phasors_harmonic_selected = int(value) + 1
        if self.harmonic_selector_value >= 1 and self.quantized_phasors:
            PhasorsController.quantize_phasors(
                self,
                self.harmonic_selector_value,
                bins=int(PHASORS_RESOLUTIONS[self.phasors_resolution]),
            )
        if not self.quantized_phasors:
            for i, channel_index in enumerate(self.plots_to_show):
                if len(self.plots_to_show) <= len(self.all_phasors_points):
                    PhasorsController.draw_points_in_phasors(
                        self,
                        channel_index,
                        self.harmonic_selector_value,
                        self.all_phasors_points[channel_index][
                            self.harmonic_selector_value
                        ],
                    )
        PhasorsController.generate_phasors_cluster_center(self, self.harmonic_selector_value)
        PhasorsController.generate_phasors_legend(self, self.harmonic_selector_value)
        for i, channel_index in enumerate(self.plots_to_show):
            PhasorsController.draw_lifetime_points_in_phasors(
                self,
                channel_index,
                self.harmonic_selector_value,
                laser_period_ns,
                frequency_mhz,
            )
 

    def open_plots_config_popup(self):
        self.popup = PlotsConfigPopup(self, start_acquisition=False)
        self.popup.show()
    
    def open_laserblood_metadata_popup(self):    
        self.popup = LaserbloodMetadataPopup(self, start_acquisition=False)
        self.popup.show()    

    def open_reader_popup(self):
        self.popup = ReaderPopup(self, tab_selected=self.tab_selected)
        self.popup.show()

    def open_reader_metadata_popup(self):
        self.popup = ReaderMetadataPopup(self, tab_selected=self.tab_selected)
        self.popup.show()

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
