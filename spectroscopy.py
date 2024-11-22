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
        self.get_selected_channels_from_settings()
        (self.top_bar, self.grid_layout) = self.init_ui()
        self.on_tab_selected(TAB_SPECTROSCOPY)
        # self.update_sync_in_button()
        self.generate_plots()
        self.all_phasors_points = self.get_empty_phasors_points()
        self.overlay = OverlayWidget(self)
        self.installEventFilter(self)
        self.pull_from_queue_timer = QTimer()
        self.pull_from_queue_timer.timeout.connect(self.pull_from_queue)
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
        self.check_card_connection()        

    @staticmethod
    def get_empty_phasors_points():
        empty = []
        for i in range(8):
            empty.append({1: [], 2: [], 3: [], 4: []})
        return empty

    def init_ui(self):
        self.setWindowTitle(
            "FlimLabs - SPECTROSCOPY v" + VERSION + " - API v" + flim_labs.get_version()
        )
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self)
        main_layout = QVBoxLayout()
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar, 0, Qt.AlignmentFlag.AlignTop)
        # Time tagger progress bar
        time_tagger_progress_bar = ProgressBar(
            visible=False, indeterminate=True, label_text="Time tagger processing..."
        )
        self.widgets[TIME_TAGGER_PROGRESS_BAR] = time_tagger_progress_bar
        main_layout.addWidget(time_tagger_progress_bar)
        main_layout.addSpacing(5)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(main_layout)
        self.resize(
            self.settings.value("size", QSize(APP_DEFAULT_WIDTH, APP_DEFAULT_HEIGHT))
        )
        self.move(
            self.settings.value(
                "pos",
                QApplication.primaryScreen().geometry().center()
                - self.frameGeometry().center(),
            )
        )
        return top_bar, grid_layout

    @staticmethod
    def init_settings():
        settings = QSettings("settings.ini", QSettings.Format.IniFormat)
        return settings

    def create_top_bar(self):
        top_bar = QVBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setAlignment(Qt.AlignmentFlag.AlignTop)
        top_collapsible_widget = QWidget()
        top_collapsible_layout = QVBoxLayout()
        top_collapsible_layout.setContentsMargins(0, 0, 0, 0)
        top_collapsible_layout.setSpacing(0)
        self.widgets[TOP_COLLAPSIBLE_WIDGET] = top_collapsible_widget
        top_bar_header = QHBoxLayout()
        top_bar_header.addSpacing(10)
        top_bar_header.addLayout(self.create_logo_and_title())
        # add hlayout
        tabs_layout = QHBoxLayout()
        # set height of parent
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        # no spacing
        tabs_layout.setSpacing(0)
        self.control_inputs[TAB_SPECTROSCOPY] = QPushButton("SPECTROSCOPY")
        self.control_inputs[TAB_SPECTROSCOPY].setFlat(True)
        self.control_inputs[TAB_SPECTROSCOPY].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.control_inputs[TAB_SPECTROSCOPY].setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.control_inputs[TAB_SPECTROSCOPY].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs[TAB_SPECTROSCOPY])
        self.control_inputs[TAB_SPECTROSCOPY].setChecked(True)
        self.control_inputs[TAB_SPECTROSCOPY].clicked.connect(
            lambda: self.on_tab_selected(TAB_SPECTROSCOPY)
        )
        tabs_layout.addWidget(self.control_inputs[TAB_SPECTROSCOPY])
        self.control_inputs[TAB_PHASORS] = QPushButton("PHASORS")
        self.control_inputs[TAB_PHASORS].setFlat(True)
        self.control_inputs[TAB_PHASORS].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.control_inputs[TAB_PHASORS].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs[TAB_PHASORS].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs[TAB_PHASORS])
        self.control_inputs[TAB_PHASORS].clicked.connect(
            lambda: self.on_tab_selected(TAB_PHASORS)
        )
        tabs_layout.addWidget(self.control_inputs[TAB_PHASORS])
        self.control_inputs[TAB_FITTING] = QPushButton("FITTING")
        self.control_inputs[TAB_FITTING].setFlat(True)
        self.control_inputs[TAB_FITTING].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.control_inputs[TAB_FITTING].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs[TAB_FITTING].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs[TAB_FITTING])
        self.control_inputs[TAB_FITTING].clicked.connect(
            lambda: self.on_tab_selected(TAB_FITTING)
        )
        tabs_layout.addWidget(self.control_inputs[TAB_FITTING])
        top_bar_header.addLayout(tabs_layout)
        top_bar_header.addStretch(1)
        # LASERBLOOD METADATA
        laserblood_btn_box = QVBoxLayout()
        laserblood_btn_box.setSpacing(0)
        laserblood_btn_box.setContentsMargins(0,8,0,0)
        laserblood_metadata_btn = QPushButton(" METADATA")
        laserblood_metadata_btn.setIcon(
            QIcon(resource_path("assets/laserblood-logo.png"))
        )
        laserblood_metadata_btn.setIconSize(QSize(50, 100))
        laserblood_metadata_btn.setFixedWidth(160)
        laserblood_metadata_btn.setFixedHeight(45)
        laserblood_metadata_btn.setStyleSheet(
            "font-family: Montserrat; font-weight: bold; background-color: white; color: #014E9C; padding: 0 14px;"
        )
        laserblood_metadata_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        laserblood_metadata_btn.clicked.connect(self.open_laserblood_metadata_popup)
        laserblood_btn_box.addWidget(laserblood_metadata_btn)
        top_bar_header.addLayout(laserblood_btn_box)
        top_bar_header.addSpacing(10)
        # ACQUIRE/READ MODE
        read_acquire_button_row = ReadAcquireModeButton(self)
        top_bar_header.addWidget(read_acquire_button_row)
        top_bar_header.addSpacing(10)

        info_link_widget, export_data_control = self.create_export_data_input()
        file_size_info_layout = self.create_file_size_info_row()
        top_bar_header.addWidget(
            info_link_widget, alignment=Qt.AlignmentFlag.AlignBottom
        )
        top_bar_header.addLayout(export_data_control)
        export_data_control.addSpacing(10)
        top_bar_header.addLayout(file_size_info_layout)
        top_bar_header.addSpacing(10)
        # Time Tagger
        time_tagger = TimeTaggerWidget(self)
        top_bar_header.addWidget(time_tagger)
        top_bar_header.addSpacing(10)
        top_bar.addLayout(top_bar_header)
        channels_widget = QWidget()
        sync_buttons_widget = QWidget()
        channels_widget.setLayout(self.create_channel_selector())
        sync_buttons_widget.setLayout(self.create_sync_buttons())
        top_collapsible_layout.addWidget(channels_widget, 0, Qt.AlignmentFlag.AlignTop)
        top_collapsible_layout.addWidget(
            sync_buttons_widget, 0, Qt.AlignmentFlag.AlignTop
        )
        top_collapsible_widget.setLayout(top_collapsible_layout)
        top_bar.addWidget(top_collapsible_widget)
        top_bar.addLayout(self.create_control_inputs())
        top_bar.addWidget(draw_layout_separator())
        top_bar.addSpacing(5)
        container = QWidget()
        container.setLayout(top_bar)
        return container

    def create_logo_and_title(self):
        row = QHBoxLayout()
        pixmap = QPixmap(
            resource_path("assets/spectroscopy-logo-white.png")
        ).scaledToWidth(30)
        ctl = QLabel(pixmap=pixmap)
        row.addWidget(ctl)
        row.addSpacing(10)
        ctl_layout = QVBoxLayout()
        ctl_layout.setContentsMargins(0, 20, 0, 0)
        ctl = GradientText(
            self,
            text="SPECTROSCOPY",
            colors=[(0.7, "#1E90FF"), (1.0, PALETTE_RED_1)],
            stylesheet=GUIStyles.set_main_title_style(),
        )
        ctl_layout.addWidget(ctl)
        row.addLayout(ctl_layout)
        ctl = QWidget()
        ctl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(ctl)
        return row

    def create_export_data_input(self):
        export_data_active = self.write_data_gui
        # Link to export data documentation
        info_link_widget = LinkWidget(
            icon_filename=resource_path("assets/info-icon.png"),
            link="https://flim-labs.github.io/spectroscopy-py/v1.0/#gui-usage",
        )
        info_link_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        info_link_widget.show()
        # Export data switch control
        export_data_control = QVBoxLayout()
        export_data_control.setContentsMargins(0, 0, 0, 0)
        export_data_control.setSpacing(0)
        export_data_label = QLabel("Export data:")
        inp = SwitchControl(
            active_color=PALETTE_BLUE_1, width=70, height=30, checked=export_data_active
        )
        inp.toggled.connect(self.on_export_data_changed)
        export_data_control.addWidget(export_data_label)
        export_data_control.addSpacing(5)
        export_data_control.addWidget(inp)
        return info_link_widget, export_data_control

    def create_file_size_info_row(self):
        export_data_active = self.write_data_gui
        file_size_info_layout = QVBoxLayout()
        file_size_info_layout.setContentsMargins(0, 0, 0, 0)
        file_size_info_layout.setSpacing(0)
        self.bin_file_size_label.setText("File size: " + str(self.bin_file_size))
        self.bin_file_size_label.setStyleSheet("QLabel { color : #f8f8f8; }")
        file_size_info_layout.addSpacing(15)
        file_size_info_layout.addWidget(self.bin_file_size_label)
        (
            self.bin_file_size_label.show()
            if export_data_active
            else self.bin_file_size_label.hide()
        )
        return file_size_info_layout

    def create_control_inputs(self):
        from components.buttons import ExportPlotImageButton

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 10, 0, 0)
        controls_row.addSpacing(10)
        _, inp = InputNumberControl.setup(
            "Bin width (µs):",
            1000,
            1000000,
            int(self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)),
            controls_row,
            self.on_bin_width_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_BIN_WIDTH] = inp
        _, inp = InputNumberControl.setup(
            "Time span (s):",
            1,
            300,
            int(self.settings.value(SETTINGS_TIME_SPAN, DEFAULT_TIME_SPAN)),
            controls_row,
            self.on_time_span_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_TIME_SPAN] = inp
        switch_control = QVBoxLayout()
        inp = SwitchControl(
            active_color="#11468F",
            checked=self.settings.value(SETTINGS_FREE_RUNNING, DEFAULT_FREE_RUNNING)
            == "true",
        )
        inp.toggled.connect(self.on_free_running_changed)
        switch_control.addWidget(QLabel("Free running:"))
        switch_control.addSpacing(8)
        switch_control.addWidget(inp)
        controls_row.addLayout(switch_control)
        controls_row.addSpacing(20)
        self.control_inputs[SETTINGS_FREE_RUNNING] = inp
        _, inp = InputNumberControl.setup(
            "Acquisition time (s):",
            1,
            1800,
            int(
                self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)
            ),
            controls_row,
            self.on_acquisition_time_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_ACQUISITION_TIME] = inp
        self.on_free_running_changed(
            self.settings.value(SETTINGS_FREE_RUNNING, DEFAULT_FREE_RUNNING) == "true"
        )
        # CPS THRESHOLD
        cps_threshold = int(self.settings.value(SETTINGS_CPS_THRESHOLD, DEFAULT_CPS_THRESHOLD))
        _, inp = InputNumberControl.setup(
            "Pile-up threshold (CPS):",
            0,
            100000000,
            cps_threshold,
            controls_row,
            self.on_cps_threshold_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style(min_width="120px"))
        self.control_inputs[SETTINGS_CPS_THRESHOLD] = inp
        LaserbloodMetadataPopup.set_cps_threshold(self, cps_threshold)
        
        #SHOW SBR 
        show_SBR_control = QVBoxLayout()
        show_SBR_control.setContentsMargins(0, 0, 0, 0)
        show_SBR_control.setSpacing(0)
        show_SBR_label = QLabel("Show SBR:")
        inp = SwitchControl(
            active_color=PALETTE_BLUE_1, width=70, height=30, checked=self.show_SBR
        )
        self.control_inputs[SETTINGS_SHOW_SBR] = inp
        inp.toggled.connect(self.on_show_SBR_changed)
        show_SBR_control.addWidget(show_SBR_label)
        show_SBR_control.addSpacing(5)
        show_SBR_control.addWidget(inp)    
        controls_row.addLayout(show_SBR_control)   
        controls_row.addSpacing(20)   
              
        # QUANTIZE PHASORS
        quantize_phasors_switch_control = QVBoxLayout()
        inp_quantize = SwitchControl(
            active_color="#11468F",
            checked=self.quantized_phasors,
        )
        inp_quantize.toggled.connect(self.on_quantize_phasors_changed)
        self.control_inputs[SETTINGS_QUANTIZE_PHASORS] = inp_quantize
        quantize_phasors_switch_control.addWidget(QLabel("Quantize Phasors:"))
        quantize_phasors_switch_control.addSpacing(8)
        quantize_phasors_switch_control.addWidget(inp_quantize)
        self.control_inputs["quantize_phasors_container"] = (
            quantize_phasors_switch_control
        )
        (
            show_layout(quantize_phasors_switch_control)
            if self.tab_selected == TAB_PHASORS
            else hide_layout(quantize_phasors_switch_control)
        )
        controls_row.addLayout(quantize_phasors_switch_control)
        controls_row.addSpacing(20)

        # PHASORS RESOLUTION
        phasors_resolution_container, inp, __, container  = SelectControl.setup(
            "Squares:",
            self.phasors_resolution,
            controls_row,
            PHASORS_RESOLUTIONS,
            self.on_phasors_resolution_changed,
            width=70,
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        (
            show_layout(phasors_resolution_container)
            if (self.tab_selected == TAB_PHASORS and self.quantized_phasors)
            else hide_layout(phasors_resolution_container)
        )
        self.control_inputs[SETTINGS_PHASORS_RESOLUTION] = inp
        self.control_inputs["phasors_resolution_container"] = (
            phasors_resolution_container
        )

        _, inp, label, container  = SelectControl.setup(
            "Calibration:",
            int(
                self.settings.value(
                    SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE
                )
            ),
            controls_row,
            ["None", "Phasors Ref."],
            self.on_calibration_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        self.control_inputs["calibration"] = inp
        self.control_inputs["calibration_label"] = label
        label, inp = InputFloatControl.setup(
            "TAU (ns):",
            0,
            1000,
            float(self.settings.value(SETTINGS_TAU_NS, "0")),
            controls_row,
            self.on_tau_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs["tau"] = inp
        self.control_inputs["tau_label"] = label
        label, inp = InputNumberControl.setup(
            "Harmonics",
            1,
            4,
            int(self.settings.value(SETTINGS_HARMONIC, "1")),
            controls_row,
            self.on_harmonic_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_HARMONIC] = inp
        self.control_inputs[SETTINGS_HARMONIC_LABEL] = label

        spacer = QWidget()
        controls_row.addWidget(spacer, 1)

        ctl, inp, label, container  = SelectControl.setup(
            "Harmonic displayed:",
            0,
            controls_row,
            ["1", "2", "3", "4"],
            self.on_harmonic_selector_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        self.control_inputs[HARMONIC_SELECTOR_LABEL] = label
        self.control_inputs[HARMONIC_SELECTOR] = inp
        label.hide()
        inp.hide()

        save_button = QPushButton("LOAD REFERENCE")
        save_button.setFlat(True)
        save_button.setFixedHeight(55)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setHidden(True)
        save_button.clicked.connect(self.on_load_reference)
        save_button.setStyleSheet(
            """
        QPushButton {
            background-color: #1E90FF;
            color: white;
            border-radius: 5px;
            padding: 5px 12px;
            font-weight: bold;
            font-size: 16px;
        }
        """
        )
        self.control_inputs[LOAD_REF_BTN] = save_button
        controls_row.addWidget(save_button)

        export_button = QPushButton("EXPORT")
        export_button.setFlat(True)
        export_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setHidden(True)
        export_button.clicked.connect(self.export_data)
        export_button.setStyleSheet(
            """
        QPushButton {
            background-color: #8d4ef2;
            color: white;
            border-radius: 5px;
            padding: 5px 10px;
            font-size: 16px;
        }
        """
        )
        self.control_inputs["export_button"] = export_button
        controls_row.addWidget(export_button)

        self.control_inputs[FIT_BTN_PLACEHOLDER] = QWidget()
        self.control_inputs[FIT_BTN_PLACEHOLDER].setLayout(QHBoxLayout())
        # if no fit button is present, it must no occupy space
        self.control_inputs[FIT_BTN_PLACEHOLDER].layout().setContentsMargins(0, 0, 0, 0)
        controls_row.addWidget(self.control_inputs[FIT_BTN_PLACEHOLDER])

        # START BUTTON
        start_button = QPushButton("START")
        start_button.setFixedWidth(150)
        start_button.setObjectName("btn")
        start_button.setFlat(True)
        start_button.setFixedHeight(55)
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.on_start_button_click)
        start_button.setVisible(self.acquire_read_mode == "acquire")
        self.control_inputs["start_button"] = start_button
        # BIN METADATA BUTTON
        bin_metadata_button = QPushButton()
        bin_metadata_button.setIcon(QIcon(resource_path("assets/metadata-icon.png")))
        bin_metadata_button.setIconSize(QSize(30, 30))
        bin_metadata_button.setStyleSheet("background-color: white; padding: 0 14px;")
        bin_metadata_button.setFixedHeight(55)
        bin_metadata_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["bin_metadata_button"] = bin_metadata_button
        bin_metadata_button.clicked.connect(self.open_reader_metadata_popup)
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self)
        bin_metadata_button.setVisible(bin_metadata_btn_visible)
        # EXPORT PLOT IMG BUTTON
        export_plot_img_button = ExportPlotImageButton(self)
        # READ BIN BUTTON
        read_bin_button = QPushButton("READ/PLOT")
        read_bin_button.setObjectName("btn")
        read_bin_button.setFlat(True)
        read_bin_button.setFixedHeight(55)
        read_bin_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["read_bin_button"] = read_bin_button
        read_bin_button.clicked.connect(self.open_reader_popup)
        read_bin_button.setVisible(self.acquire_read_mode == "read")
        self.style_start_button()
        collapse_button = CollapseButton(self.widgets[TOP_COLLAPSIBLE_WIDGET])
        controls_row.addWidget(start_button)
        controls_row.addWidget(bin_metadata_button)
        controls_row.addWidget(export_plot_img_button)
        controls_row.addWidget(read_bin_button)
        controls_row.addWidget(collapse_button)
        self.widgets["collapse_button"] = collapse_button
        controls_row.addSpacing(10)
        return controls_row

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

    def style_start_button(self):
        GUIStyles.set_start_btn_style(self.control_inputs["read_bin_button"])
        if self.mode == MODE_STOPPED:
            self.control_inputs["start_button"].setText("START")
            GUIStyles.set_start_btn_style(self.control_inputs["start_button"])
        else:
            self.control_inputs["start_button"].setText("STOP")
            GUIStyles.set_stop_btn_style(self.control_inputs["start_button"])

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
            self.clear_plots(deep_clear=False)
            self.generate_plots()
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
            self.initialize_phasor_feature()
            self.generate_phasors_cluster_center(
                self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1
            )
            self.generate_phasors_legend(
                self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1
            )
            if self.harmonic_selector_shown:
                if self.quantized_phasors:
                    self.quantize_phasors(
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
            self.begin_spectroscopy_experiment()
        elif self.mode == MODE_RUNNING:
            self.acquisition_stopped = True
            self.stop_spectroscopy_experiment()

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
        self.clear_phasors_points()
        harmonic_value = int(self.control_inputs[HARMONIC_SELECTOR].currentText())
        self.quantized_phasors = value
        self.settings.setValue(SETTINGS_QUANTIZE_PHASORS, value)
        container = self.control_inputs["phasors_resolution_container"]
        if value:
            show_layout(container)
            bins = int(PHASORS_RESOLUTIONS[self.phasors_resolution])
            self.quantize_phasors(harmonic_value, bins)
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
                    self.draw_points_in_phasors(channel_index, harmonic_value, points)

    def on_phasors_resolution_changed(self, value):
        self.phasors_resolution = int(value)
        harmonic_value = int(self.control_inputs[HARMONIC_SELECTOR].currentText())
        self.settings.setValue(SETTINGS_PHASORS_RESOLUTION, value)
        self.quantize_phasors(
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

    def create_channel_selector(self):
        grid = QHBoxLayout()
        # Detect channels button
        detect_channels_btn =  DetectChannelsButton(self)
        grid.addWidget(detect_channels_btn)        
        plots_config_btn = QPushButton(" PLOTS CONFIG")
        plots_config_btn.setIcon(QIcon(resource_path("assets/chart-icon.png")))
        GUIStyles.set_stop_btn_style(plots_config_btn)
        plots_config_btn.setFixedWidth(150)
        plots_config_btn.setFixedHeight(40)
        plots_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plots_config_btn.clicked.connect(self.open_plots_config_popup)
        widget_channel_type =  QWidget()
        row_channel_type = QHBoxLayout()
        row_channel_type.setContentsMargins(0,0,0,0)
        _, inp, __, container = SelectControl.setup(
            "Channel type:",
            int(self.settings.value(SETTINGS_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)),
            row_channel_type,
            ["USB", "SMA"],
            self.on_connection_type_value_change,
            spacing=None,    
        )
        inp.setFixedHeight(40)
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        widget_channel_type.setLayout(row_channel_type)
        self.control_inputs["channel_type"] = inp
        grid.addWidget(widget_channel_type, alignment=Qt.AlignmentFlag.AlignBottom)
        for i in range(MAX_CHANNELS):
            ch_wrapper = QWidget()
            ch_wrapper.setObjectName(f"ch_checkbox_wrapper")
            ch_wrapper.setFixedHeight(40)
            row = QHBoxLayout()
            from components.fancy_checkbox import FancyCheckbox

            fancy_checkbox = FancyCheckbox(text=f"Channel {i + 1}")
            fancy_checkbox.setStyleSheet(GUIStyles.set_checkbox_style())
            if self.selected_channels:
                fancy_checkbox.set_checked(i in self.selected_channels)
            fancy_checkbox.toggled.connect(
                lambda checked, channel=i: self.on_channel_selected(checked, channel)
            )
            row.addWidget(fancy_checkbox)
            ch_wrapper.setLayout(row)
            ch_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
            grid.addWidget(ch_wrapper, alignment=Qt.AlignmentFlag.AlignBottom)
            self.channel_checkboxes.append(fancy_checkbox)
        grid.addWidget(plots_config_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        self.widgets[CHANNELS_GRID] = grid
        return grid

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
        self.clear_plots()
        self.generate_plots()
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
                    self.draw_lifetime_points_in_phasors(
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

    def create_sync_buttons(self):
        buttons_layout = QHBoxLayout()
        # CHECK CARD
        check_card_widget = CheckCard(self)
        buttons_layout.addWidget(check_card_widget)   
        buttons_layout.addSpacing(20)        
        sync_in_button = FancyButton("Sync In")
        buttons_layout.addWidget(sync_in_button)
        self.sync_buttons.append((sync_in_button, "sync_in"))
        self.update_sync_in_button()
        sync_out_80_button = FancyButton("Sync Out (80MHz)")
        buttons_layout.addWidget(sync_out_80_button)
        self.sync_buttons.append((sync_out_80_button, "sync_out_80"))
        sync_out_40_button = FancyButton("Sync Out (40MHz)")
        buttons_layout.addWidget(sync_out_40_button)
        self.sync_buttons.append((sync_out_40_button, "sync_out_40"))
        sync_out_20_button = FancyButton("Sync Out (20MHz)")
        buttons_layout.addWidget(sync_out_20_button)
        self.sync_buttons.append((sync_out_20_button, "sync_out_20"))
        sync_out_10_button = FancyButton("Sync Out (10MHz)")
        buttons_layout.addWidget(sync_out_10_button)
        self.sync_buttons.append((sync_out_10_button, "sync_out_10"))
        for button, name in self.sync_buttons:
            def on_toggle(toggled_name):
                for b, n in self.sync_buttons:
                    b.set_selected(n == toggled_name)
                self.on_sync_selected(toggled_name)
            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(self.selected_sync == name) 
        self.widgets["sync_buttons_layout"] = buttons_layout
        return buttons_layout

    def initialize_intensity_plot_data(self, channel):
        if self.tab_selected in self.intensity_lines:
            if channel in self.intensity_lines[self.tab_selected]:
                x, y = self.intensity_lines[self.tab_selected][channel].getData()
                return x, y
        x = np.arange(1)
        y = x * 0
        return x, y

    def initialize_decay_curves(self, channel, frequency_mhz):
        def get_default_x():
            if frequency_mhz != 0.0:
                period = 1_000 / frequency_mhz
                return np.linspace(0, period, 256)
            return np.arange(1)

        decay_curves = self.decay_curves[self.tab_selected]
        if self.tab_selected in [TAB_SPECTROSCOPY, TAB_FITTING]:
            cached_decay_values = self.cached_decay_values[self.tab_selected]
            if channel in cached_decay_values and channel in decay_curves:
                x, _ = decay_curves[channel].getData()
                y = cached_decay_values[channel]
            else:
                x = get_default_x()
                if (
                    channel not in self.lin_log_mode
                    or self.lin_log_mode[channel] == "LIN"
                ):
                    y = x * 0
                else:
                    y = (
                        np.linspace(0, 100_000_000, 256)
                        if frequency_mhz != 0.0
                        else np.array([0])
                    )
        else:
            if channel in decay_curves:
                x, y = decay_curves[channel].getData()
            else:
                x = get_default_x()
                y = x * 0
        return x, y

    def generate_plots(self, frequency_mhz=0.0):
        self.lin_log_switches.clear()
        if len(self.plots_to_show) == 0:
            self.grid_layout.addWidget(QWidget(), 0, 0)
            return
        for i, channel in enumerate(self.plots_to_show):
            v_layout = QVBoxLayout()
            v_widget = QWidget()
            v_widget.setObjectName("chart_wrapper")
            if (
                self.tab_selected == TAB_SPECTROSCOPY
                or self.tab_selected == TAB_FITTING
            ):
                intensity_widget_wrapper = QWidget()
                h_layout = QHBoxLayout()
                cps_contdown_v_box = QVBoxLayout()
                cps_contdown_v_box.setContentsMargins(0, 0, 0, 0)
                cps_contdown_v_box.setSpacing(0)
                cps_label = QLabel("No CPS")
                cps_label.setStyleSheet(
                    "QLabel { color : #285da6; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px 8px 0 8px;}"
                )
                # label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                self.cps_widgets[channel] = cps_label
                self.cps_widgets_animation[channel] = VibrantAnimation(
                    self.cps_widgets[channel],
                    stop_color="#285da6",
                    bg_color="transparent",
                    start_color="#eed202",
                )
                self.cps_counts[channel] = {
                    "last_time_ns": 0,
                    "last_count": 0,
                    "current_count": 0,
                }
                countdown_label = QLabel("Remaining time:")
                countdown_label.setStyleSheet(
                    GUIStyles.acquisition_time_countdown_style()
                )
                countdown_label.setVisible(False)
                self.acquisition_time_countdown_widgets[channel] = countdown_label
                intensity_widget = pg.PlotWidget()
                intensity_widget.setLabel(
                    "left",
                    (
                        "AVG. Photon counts"
                        if len(self.plots_to_show) < 4
                        else "AVG. Photons"
                    ),
                    units="",
                )
                intensity_widget.setLabel("bottom", "Time", units="s")
                intensity_widget.setTitle(f"Channel {channel + 1} intensity")
                intensity_widget.setBackground("#141414")
                # remove margins
                intensity_widget.plotItem.setContentsMargins(0, 0, 0, 0)
                x, y = self.initialize_intensity_plot_data(channel)
                intensity_plot = intensity_widget.plot(
                    x, y, pen=pg.mkPen(color="#1E90FF", width=2)
                )
                self.intensity_lines[self.tab_selected][channel] = intensity_plot
                cps_contdown_v_box.addWidget(cps_label)
                cps_contdown_v_box.addWidget(countdown_label)
                h_layout.addLayout(cps_contdown_v_box, stretch=1)
                if len(self.plots_to_show) == 1:
                    intensity_plot_stretch = 6
                elif len(self.plots_to_show) == 2:
                    intensity_plot_stretch = 4
                elif len(self.plots_to_show) == 3:
                    intensity_plot_stretch = 2
                else:
                    intensity_plot_stretch = 4
                h_layout.addWidget(intensity_widget, stretch=intensity_plot_stretch)
                intensity_widget_wrapper.setLayout(h_layout)
                self.intensities_widgets[channel] = intensity_widget_wrapper
                v_layout.addWidget(intensity_widget_wrapper, 2)
                # Spectroscopy
                h_decay_layout = QHBoxLayout()
                # LIN LOG
                time_shifts = SpectroscopyTimeShift.get_channel_time_shift(
                    self, channel
                ) if self.acquire_read_mode == "acquire" else 0
                
                lin_log_modes = self.lin_log_mode
                lin_log_widget = LinLogControl(
                    self,
                    channel,
                    time_shifts=time_shifts,
                    lin_log_modes=lin_log_modes,
                    lin_log_switches=self.lin_log_switches,
                )
                curve_widget = pg.PlotWidget()
                curve_widget.setLabel("left", "Photon counts", units="")
                curve_widget.setLabel("bottom", "Time", units="ns")
                curve_widget.setTitle(f"Channel {channel + 1} decay")
                curve_widget.setBackground("#0a0a0a")
                x, y = self.initialize_decay_curves(channel, frequency_mhz)
                if (
                    channel not in self.lin_log_mode
                    or self.lin_log_mode[channel] == "LIN"
                ):
                    static_curve = curve_widget.plot(
                        x, y, pen=pg.mkPen(color="#f72828", width=2)
                    )

                else:
                    log_values, ticks, _ = LinLogControl.calculate_log_ticks(y)
                    static_curve = curve_widget.plot(
                        x, log_values, pen=pg.mkPen(color="#f72828", width=2)
                    )
                    axis = curve_widget.getAxis("left")
                    curve_widget.showGrid(x=False, y=True, alpha=0.3)
                    axis.setTicks([ticks])
                    self.set_plot_y_range(curve_widget)
                curve_widget.plotItem.getAxis("left").enableAutoSIPrefix(False)
                curve_widget.plotItem.getAxis("bottom").enableAutoSIPrefix(False)
                self.decay_curves[self.tab_selected][channel] = static_curve
                self.decay_widgets[channel] = curve_widget
                time_shift_layout = SpectroscopyTimeShift(self, channel)
                v_decay_layout = QVBoxLayout()
                v_decay_layout.setSpacing(0)
                v_decay_layout.addWidget(time_shift_layout)
                if self.acquire_read_mode != "read":
                    #SBR 
                    SBR_label = QLabel("SBR: 0 ㏈")
                    SBR_label.setStyleSheet(GUIStyles.SBR_label())
                    if not self.show_SBR:
                        SBR_label.hide()
                    self.SBR_items[channel] = SBR_label                      
                    v_decay_layout.addWidget(SBR_label)                
                v_decay_layout.addWidget(curve_widget)
                h_decay_layout.addWidget(lin_log_widget, 1)
                h_decay_layout.addLayout(v_decay_layout, 11)
                v_layout.addLayout(h_decay_layout, 3)
                v_widget.setLayout(v_layout)
                self.fit_button_hide()
            elif self.tab_selected == TAB_PHASORS:
                h_layout = QHBoxLayout()
                cps_contdown_v_box = QVBoxLayout()
                cps_contdown_v_box.setContentsMargins(0, 0, 0, 0)
                cps_contdown_v_box.setSpacing(0)
                cps_label = QLabel("No CPS")
                cps_label.setStyleSheet(
                    "QLabel { color : #f72828; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px 8px 0 8px; }"
                )
                # label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                self.cps_widgets[channel] = cps_label
                self.cps_widgets_animation[channel] = VibrantAnimation(
                    self.cps_widgets[channel],
                    stop_color="#f72828",
                    bg_color="transparent",
                    start_color="#eed202",
                )
                self.cps_counts[channel] = {
                    "last_time_ns": 0,
                    "last_count": 0,
                    "current_count": 0,
                }
                countdown_label = QLabel("Remaining time:")
                countdown_label.setStyleSheet(
                    GUIStyles.acquisition_time_countdown_style()
                )
                countdown_label.setVisible(False)
                self.acquisition_time_countdown_widgets[channel] = countdown_label
                curve_widget_container = QVBoxLayout()
                curve_widget_container.setContentsMargins(0,0,0,0)
                curve_widget_container.setSpacing(0)                
                curve_widget = pg.PlotWidget()
                curve_widget.setLabel("left", "Photon counts", units="")
                curve_widget.setLabel("bottom", "Time", units="ns")
                curve_widget.setTitle(f"Channel {channel + 1} decay")
                x, y = self.initialize_decay_curves(channel, frequency_mhz)
                static_curve = curve_widget.plot(
                    x, y, pen=pg.mkPen(color="#f72828", width=2)
                )
                self.decay_curves[self.tab_selected][channel] = static_curve
                self.decay_widgets[channel] = curve_widget
                if self.acquire_read_mode != "read":
                    #SBR 
                    SBR_label = QLabel("SBR: 0 ㏈")
                    SBR_label.setStyleSheet(GUIStyles.SBR_label(font_size="16px", background_color="#000000"))
                    if not self.show_SBR:
                        SBR_label.hide()
                    self.SBR_items[channel] = SBR_label                 
                    curve_widget_container.addWidget(SBR_label) 
                curve_widget_container.addWidget(curve_widget)                                     
                cps_contdown_v_box.addWidget(cps_label)
                cps_contdown_v_box.addWidget(countdown_label)
                h_layout.addLayout(cps_contdown_v_box, stretch=1)
                h_layout.addLayout(curve_widget_container, stretch=1)
                v_layout.addLayout(h_layout, 1)
                # add a phasors chart
                phasors_widget = pg.PlotWidget()
                # mantain aspect ratio
                phasors_widget.setAspectLocked(True)
                phasors_widget.setLabel("left", "s", units="")
                phasors_widget.setLabel("bottom", "g", units="")
                phasors_widget.setTitle(f"Channel {channel + 1} phasors")
                self.draw_semi_circle(phasors_widget)
                self.phasors_charts[channel] = phasors_widget.plot(
                    [],
                    [],
                    pen=None,
                    symbol="o",
                    symbolPen="#1E90FF",
                    symbolSize=1,
                    symbolBrush="#1E90FF",
                )
                self.phasors_widgets[channel] = phasors_widget
                v_layout.addWidget(phasors_widget, 3)
                v_widget.setLayout(v_layout)
                if self.acquire_read_mode == "read":
                    phasors_widget.setCursor(Qt.CursorShape.BlankCursor)
                    self.generate_coords(channel)
                    self.create_phasor_crosshair(channel, self.phasors_widgets[channel])
            col_length = 1
            if len(self.plots_to_show) == 2:
                col_length = 2
            elif len(self.plots_to_show) == 3:
                col_length = 3
            if len(self.plots_to_show) > 3:
                col_length = 2
            v_widget.setStyleSheet(GUIStyles.chart_wrapper_style())
            self.grid_layout.addWidget(v_widget, i // col_length, i % col_length)

    def calculate_phasors_points_mean(self, channel_index, harmonic):
        x = [p[0] for p in self.all_phasors_points[channel_index][harmonic]]
        y = [p[1] for p in self.all_phasors_points[channel_index][harmonic]]
        g_values = np.array(x)
        s_values = np.array(y)
        if (
            g_values.size == 0
            or s_values.size == 0
            or np.all(np.isnan(g_values))
            or np.all(np.isnan(s_values))
        ):
            return None, None
        mean_g = np.nanmean(g_values)
        mean_s = np.nanmean(s_values)
        return mean_g, mean_s

    def generate_phasors_cluster_center(self, harmonic):
        for i, channel_index in enumerate(self.plots_to_show):
            if channel_index in self.phasors_widgets:
                cluster_center_in_list = channel_index in self.phasors_clusters_center
                if cluster_center_in_list:
                    self.phasors_widgets[channel_index].removeItem(
                        self.phasors_clusters_center[channel_index]
                    )
                mean_g, mean_s = self.calculate_phasors_points_mean(
                    channel_index, harmonic
                )
                if mean_g is None or mean_s is None:
                    continue
                scatter = pg.ScatterPlotItem(
                    [mean_g],
                    [mean_s],
                    size=20,
                    pen={
                        "color": "yellow",
                        "width": 4,
                    },
                    symbol="x",
                )
                scatter.setZValue(2)
                self.phasors_widgets[channel_index].addItem(scatter)
                self.phasors_clusters_center[channel_index] = scatter

    def generate_phasors_legend(self, harmonic):
        for i, channel_index in enumerate(self.plots_to_show):
            if channel_index in self.phasors_widgets:
                legend_in_list = channel_index in self.phasors_legends
                if legend_in_list:
                    self.phasors_widgets[channel_index].removeItem(
                        self.phasors_legends[channel_index]
                    )
                mean_g, mean_s = self.calculate_phasors_points_mean(
                    channel_index, harmonic
                )
                if mean_g is None or mean_s is None:
                    continue
                freq_mhz = self.get_frequency_mhz()
                tau_phi, tau_m = self.calculate_tau(mean_g, mean_s, freq_mhz, harmonic)
                if tau_phi is None:
                    return
                if tau_m is None:
                    legend_text = (
                        '<div style="background-color: rgba(0, 0, 0, 0.1); padding: 20px; border-radius: 4px;'
                        ' color: #FF3131; font-size: 18px; border: 1px solid white; text-align: left;">'
                        f"G (mean)={round(mean_g, 2)}; "
                        f"S (mean)={round(mean_s, 2)}; "
                        f"𝜏ϕ={round(tau_phi, 2)} ns"
                        "</div>"
                    )
                else:
                    legend_text = (
                        '<div style="background-color: rgba(0, 0, 0, 0.1);  padding: 20px; border-radius: 4px;'
                        ' color: #FF3131; font-size: 18px;  border: 1px solid white; text-align: left;">'
                        f"G (mean)={round(mean_g, 2)}; "
                        f"S (mean)={round(mean_s, 2)}; "
                        f"𝜏ϕ={round(tau_phi, 2)} ns; "
                        f"𝜏m={round(tau_m, 2)} ns"
                        "</div>"
                    )
                legend_item = pg.TextItem(html=legend_text)
                legend_item.setPos(0.1, 0)
                self.phasors_widgets[channel_index].addItem(legend_item)
                self.phasors_legends[channel_index] = legend_item

    def create_phasor_crosshair(self, channel_index, phasors_widget):
        crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(30, 144, 255))
        font = QFont()
        font.setPixelSize(25)
        crosshair.setFont(font)
        crosshair.setZValue(3)
        phasors_widget.addItem(crosshair, ignoreBounds=True)
        self.phasors_crosshairs[channel_index] = crosshair

    def generate_coords(self, channel_index):
        font = QFont()
        font.setPixelSize(25)
        coord_text = pg.TextItem("", anchor=(0.5, 1))
        coord_text.setFont(font)
        crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(30, 144, 255))
        font = QFont()
        font.setPixelSize(25)
        crosshair.setFont(font)
        is_in_array = len(self.phasors_crosshairs) > channel_index
        if not is_in_array:
            self.phasors_crosshairs[channel_index] = crosshair
        else:
            self.phasors_crosshairs[channel_index] = crosshair
        is_in_array = len(self.phasors_coords) > channel_index
        if not is_in_array:
            self.phasors_widgets[channel_index].sceneObj.sigMouseMoved.connect(
                lambda event, ccc=channel_index: self.on_phasors_mouse_moved(event, ccc)
            )
            self.phasors_coords[channel_index] = coord_text
        else:
            self.phasors_coords[channel_index] = coord_text
        coord_text.setZValue(3)
        crosshair.setZValue(3)
        self.phasors_widgets[channel_index].addItem(coord_text, ignoreBounds=True)
        self.phasors_widgets[channel_index].addItem(crosshair, ignoreBounds=True)

    def calculate_tau(self, g, s, freq_mhz, harmonic):
            if freq_mhz == 0.0:
                return None, None 
            tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (s / g) * 1e3
            tau_m_component = (1 / (s**2 + g**2)) - 1
            if tau_m_component < 0:
                tau_m = None
            else:
                tau_m = (1 / (2 * np.pi * freq_mhz * harmonic)) * np.sqrt(tau_m_component) * 1e3
            return tau_phi, tau_m             

    def on_phasors_mouse_moved(self, event, channel_index):
        for i, channel in enumerate(self.phasors_coords):
            if channel != channel_index:
                self.phasors_coords[channel].setText("")
                self.phasors_crosshairs[channel].setText("")
        try:
            phasor_widget = self.phasors_widgets[channel_index]
            text = self.phasors_coords[channel_index]
            crosshair = self.phasors_crosshairs[channel_index]
        except:
            return
        mouse_point = phasor_widget.plotItem.vb.mapSceneToView(event)
        crosshair.setPos(mouse_point.x(), mouse_point.y())
        crosshair.setText(CURSOR_TEXT)
        text.setPos(mouse_point.x(), mouse_point.y())
        freq_mhz = self.get_current_frequency_mhz()
        harmonic = int(self.control_inputs[HARMONIC_SELECTOR].currentText())
        g = mouse_point.x()
        s = mouse_point.y()
        tau_phi, tau_m = self.calculate_tau(g, s, freq_mhz, harmonic)
        if tau_phi is None:
            return
        if tau_m is None:
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} ns")
            text.setHtml(
                '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                    f"𝜏ϕ={round(tau_phi, 2)} ns"
                )
            )
        else:
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏m={round(tau_m, 2)} ns")
            text.setHtml(
                '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                    f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏m={round(tau_m, 2)} ns"
                )
            )


    def draw_semi_circle(self, widget):
        x = np.linspace(0, 1, 1000)
        y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
        widget.plot(x, y, pen=pg.mkPen(color="#1E90FF", width=2))
        widget.plot([-0.1, 1.1], [0, 0], pen=pg.mkPen(color="#1E90FF", width=2))

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

    def clear_phasors_points(self):
        for ch in self.plots_to_show:
            if ch in self.phasors_charts:
                self.phasors_charts[ch].setData([], [])

    def clear_phasors_features(self, feature):
        for ch in feature:
            if ch in self.phasors_widgets:
                self.phasors_widgets[ch].removeItem(feature[ch])

    def clear_plots(self, deep_clear=True):
        self.clear_phasors_features(self.phasors_colorbars)
        self.clear_phasors_features(self.quantization_images)
        self.clear_phasors_features(self.phasors_clusters_center)
        self.clear_phasors_features(self.phasors_legends)
        self.clear_phasors_features(self.phasors_lifetime_points)
        for ch in self.phasors_lifetime_texts:
            for _, item in enumerate(self.phasors_lifetime_texts[ch]):
                self.phasors_widgets[ch].removeItem(item)
        self.quantization_images.clear()
        self.phasors_colorbars.clear()
        self.phasors_clusters_center.clear()
        self.phasors_legends.clear()
        self.phasors_lifetime_points.clear()
        self.phasors_lifetime_texts.clear()
        self.intensities_widgets.clear()
        self.phasors_charts.clear()
        self.phasors_widgets.clear()
        self.decay_widgets.clear()
        self.phasors_coords.clear()
        for i, animation in self.cps_widgets_animation.items():
            if animation:
                animation.stop()
        self.cps_widgets_animation.clear()
        self.cps_widgets.clear()
        self.cps_counts.clear()
        self.all_cps_counts.clear()
        self.all_SBR_counts.clear()
        self.SBR_items.clear()
        self.acquisition_time_countdown_widgets.clear()
        if deep_clear:
            self.intensity_lines = deepcopy(DEFAULT_INTENSITY_LINES)
            self.decay_curves = deepcopy(DEFAULT_DECAY_CURVES)
            self.cached_decay_values = deepcopy(DEFAULT_CACHED_DECAY_VALUES)
            self.clear_phasors_points()
            for ch in self.plots_to_show:
                if self.tab_selected != TAB_PHASORS:
                    self.cached_decay_values[self.tab_selected][ch] = np.array([0])
            if "time_shift_sliders" in self.control_inputs:
                self.control_inputs["time_shift_sliders"].clear()
            if "time_shift_inputs" in self.control_inputs:
                self.control_inputs["time_shift_inputs"].clear()
            for i in reversed(range(self.grid_layout.count())):
                widget = self.grid_layout.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
                layout = self.grid_layout.itemAt(i).layout()
                if layout is not None:
                    self.clear_layout_tree(layout)

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

    def begin_spectroscopy_experiment(self):
        try:
            self.check_card_connection(start_experiment=True)
        except Exception as e:
            BoxMessage.setup(
                    "Error",
                    "Error starting spectroscopy: " + str(e),
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )  
            return        
        is_export_data_active = self.write_data_gui
        bin_width_micros = int(
            self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)
        )
        frequency_mhz = self.get_frequency_mhz()
        if frequency_mhz == 0.0:
            BoxMessage.setup(
                "Error",
                "Frequency not detected",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return
        laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
        if len(self.selected_channels) == 0:
            BoxMessage.setup(
                "Error",
                "No channels selected",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return
        if bin_width_micros < 1000:
            BoxMessage.setup(
                "Error",
                "Bin width value cannot be less than 1000μs",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return
        if is_export_data_active and not LaserbloodMetadataPopup.laserblood_metadata_valid(self):                        
            BoxMessage.setup(
                "Error",
                "All required Laserblood metadata must be filled before starting the acquisition. Required fields are highlighted with a red border. Fields set to 0 are highlighted with a yellow border; it's recommended to double-check them, if present. Laser type and filter type must be set",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )    
            return   
        if self.tab_selected == TAB_SPECTROSCOPY or self.tab_selected == TAB_FITTING:
            open_config_plots_popup = len(self.selected_channels) > 4
            if open_config_plots_popup and not self.plots_to_show_already_appear:
                popup = PlotsConfigPopup(self, start_acquisition=True)
                popup.show()
                self.plots_to_show_already_appear = True
                return
        self.clear_plots()
        self.generate_plots(frequency_mhz)
        acquisition_time = self.get_acquisition_time()
        acquisition_time_millis = f"{acquisition_time * 1000} ms" if acquisition_time is not None else "Free running"
        firmware_selected, connection_type = self.get_firmware_selected(frequency_mhz)
        for _, channel in enumerate(self.plots_to_show):
            self.draw_lifetime_points_in_phasors(
                channel, 1, laser_period_ns, frequency_mhz
            )
        acquisition_time_millis = (
            None
            if self.get_free_running_state()
            else int(
                self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)
            )
            * 1000
        )
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
        self.harmonic_selector_value = self.control_inputs[SETTINGS_HARMONIC].value()
        if self.tab_selected == TAB_PHASORS:
            self.control_inputs[HARMONIC_SELECTOR].blockSignals(True)
            self.control_inputs[HARMONIC_SELECTOR].setCurrentIndex(0)
            self.control_inputs[HARMONIC_SELECTOR].blockSignals(False)
        self.phasors_harmonic_selected = 1   
        print(f"Firmware selected: {firmware_selected}")
        print(f"Connection type: {connection_type}")
        print(f"Frequency: {frequency_mhz} Mhz")
        print(f"Selected channels: {self.selected_channels}")
        print(f"Acquisition time: {acquisition_time_millis} ms")
        print(f"Bin width: {bin_width_micros} µs")
        print(f"Free running: {self.get_free_running_state()}")
        print(f"Tau: {self.settings.value(SETTINGS_TAU_NS, '0')} ns")
        print(f"Reference file: {self.reference_file}")
        print(f"Harmonics: {self.harmonic_selector_value}")
        self.cached_time_span_seconds = float(
            self.settings.value(SETTINGS_TIME_SPAN, DEFAULT_TIME_SPAN)
        )
        if self.tab_selected == TAB_PHASORS:
            if not self.reference_file:
                BoxMessage.setup(
                    "Error",
                    "No reference file selected",
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )
                return
            with open(self.reference_file, "r") as f:
                reference_data = json.load(f)
                if "channels" not in reference_data:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (missing channels)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return
                elif len(reference_data["channels"]) != len(self.selected_channels):
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (channels mismatch)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return
                elif "laser_period_ns" not in reference_data:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (missing laser period)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return 
                elif ns_to_mhz(reference_data["laser_period_ns"]) != frequency_mhz:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (laser period mismatch)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                        )
                    return                       
                if "harmonics" not in reference_data:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (missing harmonics)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return
                self.harmonic_selector_value = int(reference_data["harmonics"])
                if "curves" not in reference_data:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (missing curves)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return
                elif len(reference_data["curves"]) != len(self.selected_channels):
                    return
                if "laser_period_ns" not in reference_data:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (missing laser period)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return
                if "tau_ns" not in reference_data:
                    BoxMessage.setup(
                        "Error",
                        "Invalid reference file (missing tau)",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return
                if (
                    not (
                        all(
                            plot in reference_data["channels"]
                            for plot in self.plots_to_show
                        )
                    )
                ) or len(self.plots_to_show) == 0:
                    popup = PlotsConfigPopup(
                        self,
                        start_acquisition=True,
                        is_reference_loaded=True,
                        reference_channels=reference_data["channels"],
                    )
                    popup.show()
                    return
        try:
            tau_ns = (
                float(self.settings.value(SETTINGS_TAU_NS, "0"))
                if self.is_reference_phasors()
                else None
            )
            reference_file = (
                None
                if self.tab_selected == TAB_SPECTROSCOPY
                or self.tab_selected == TAB_FITTING
                else self.reference_file
            )
            self.all_phasors_points = self.get_empty_phasors_points()
            flim_labs.start_spectroscopy(
                enabled_channels=self.selected_channels,
                bin_width_micros=bin_width_micros,
                frequency_mhz=frequency_mhz,
                firmware_file=firmware_selected,
                acquisition_time_millis=acquisition_time * 1000 if acquisition_time else None,
                tau_ns=tau_ns,
                reference_file=reference_file,
                harmonics=int(self.harmonic_selector_value),
                write_bin=False,
                time_tagger=self.time_tagger and self.write_data_gui and self.tab_selected != TAB_PHASORS
            )
        except Exception as e:
            self.check_card_connection()
            BoxMessage.setup(
                "Error",
                "Error starting spectroscopy: " + str(e),
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return
        self.mode = MODE_RUNNING
        self.style_start_button()
        QApplication.processEvents()
        self.update_plots_enabled = True
        self.top_bar_set_enabled(False)
        LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, False)
        # self.timer_update.start(18)
        self.pull_from_queue_timer.start(25)
        # self.pull_from_queue()

    def pull_from_queue(self):
        val = flim_labs.pull_from_queue()
        if len(val) > 0:
            for v in val:
                if v == ("end",):  # End of acquisition
                    print("Got end of acquisition, stopping")
                    self.style_start_button()
                    self.acquisition_stopped = True
                    self.stop_spectroscopy_experiment()
                    break
                if self.mode == MODE_STOPPED:
                    break
                if "sp_phasors" in v[0]:
                    channel = v[1][0]
                    harmonic = v[2][0]
                    phasors = v[3]
                    channel_index = next(
                        (item for item in self.plots_to_show if item == channel), None
                    )
                    if harmonic == 1:
                        if channel_index is not None:
                            self.draw_points_in_phasors(channel, harmonic, phasors)
                    if channel_index is not None:
                        self.all_phasors_points[channel_index][harmonic].extend(phasors)
                    continue
                try:
                    ((channel,), (time_ns,), intensities) = v
                except:
                    print(v)
                ((channel,), (time_ns,), intensities) = v
                channel_index = next(
                    (item for item in self.plots_to_show if item == channel), None
                )
                if channel_index is not None:
                    self.update_plots2(channel_index, time_ns, intensities)
                    self.update_acquisition_countdowns(time_ns)
                    self.update_cps(channel_index, time_ns, intensities)
                QApplication.processEvents()

    def draw_points_in_phasors(self, channel, harmonic, phasors):
        if channel in self.plots_to_show:
            x, y = self.phasors_charts[channel].getData()
            if x is None:
                x = np.array([])
                y = np.array([])
            new_x = [p[0] for p in phasors]
            new_y = [p[1] for p in phasors]
            x = np.concatenate((x, new_x))
            y = np.concatenate((y, new_y))
            self.phasors_charts[channel].setData(x, y)
            pass
    
    def initialize_phasor_feature(self):
        frequency_mhz = self.get_current_frequency_mhz()
        if frequency_mhz != 0:
            laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
            for _, channel in enumerate(self.plots_to_show):
                if self.acquire_read_mode == "acquire":
                    if channel in self.phasors_widgets:
                        self.phasors_widgets[channel].setCursor(
                            Qt.CursorShape.BlankCursor
                        )
                        self.generate_coords(channel)
                        self.create_phasor_crosshair(
                            channel, self.phasors_widgets[channel]
                        )
                self.draw_lifetime_points_in_phasors(
                    channel,
                    self.control_inputs[HARMONIC_SELECTOR].currentIndex() + 1,
                    laser_period_ns,
                    frequency_mhz,
                )          

    def draw_lifetime_points_in_phasors(
        self, channel, harmonic, laser_period_ns, frequency_mhz
    ):
        if channel in self.plots_to_show and channel in self.phasors_widgets:
            if channel in self.phasors_lifetime_points:
                self.phasors_widgets[channel].removeItem(
                    self.phasors_lifetime_points[channel]
                )
            if channel in self.phasors_lifetime_texts:
                for _, item in enumerate(self.phasors_lifetime_texts[channel]):
                    self.phasors_widgets[channel].removeItem(item)
            tau_m = np.array(
                [
                    0.1e-9,
                    0.5e-9,
                    1e-9,
                    2e-9,
                    3e-9,
                    4e-9,
                    5e-9,
                    6e-9,
                    7e-9,
                    8e-9,
                    9e-9,
                    10e-9,
                ]
            )
            if frequency_mhz in [10, 20]:
                additional_tau = np.arange(10e-9, 26e-9, 5e-9)
                tau_m = np.concatenate((tau_m, additional_tau))
            tau_phi = tau_m
            fex = (1 / laser_period_ns) * 10e8
            k = 1 / (2 * np.pi * harmonic * fex)
            phi = np.arctan(tau_phi / k)
            factor = (tau_m / k) ** 2
            m = np.sqrt(1 / (1 + factor))
            g = m * np.cos(phi)
            s = m * np.sin(phi)
            scatter = pg.ScatterPlotItem(
                x=g, y=s, size=8, pen=None, brush="red", symbol="o"
            )
            scatter.setZValue(5)
            self.phasors_widgets[channel].addItem(scatter)
            self.phasors_lifetime_points[channel] = scatter
            texts = []
            for i in range(len(g)):
                text = pg.TextItem(
                    f"{tau_m[i] * 1e9:.1f} ns",
                    anchor=(0, 0),
                    color="white",
                    border=None,
                )
                text.setPos(g[i] + 0.01, s[i] + 0.01)
                text.setZValue(5)
                texts.append(text)
                self.phasors_widgets[channel].addItem(text)
            self.phasors_lifetime_texts[channel] = texts

    def quantize_phasors(self, harmonic, bins=64):
        for i, channel_index in enumerate(self.plots_to_show):
            x = [p[0] for p in self.all_phasors_points[channel_index][harmonic]]
            y = [p[1] for p in self.all_phasors_points[channel_index][harmonic]]
            if x is None or y is None or len(x) == 0 or len(y) == 0:
                continue
            h, xedges, yedges = np.histogram2d(
                x, y, bins=bins * 4, range=[[-2, 2], [-2, 2]]
            )
            non_zero_h = h[h > 0]
            all_zeros = len(non_zero_h) == 0
            h_min = np.min(non_zero_h)
            h_max = np.max(h)
            h = h / np.max(h)
            h[h == 0] = np.nan
            image_item = pg.ImageItem()
            image_item.setImage(h, levels=(0, 1))
            image_item.setLookupTable(
                self.create_cool_colormap().getLookupTable(0, 1.0)
            )
            image_item.setOpacity(1)
            image_item.resetTransform()
            image_item.setScale(1 / bins)
            image_item.setPos(-2, -2)
            if channel_index in self.quantization_images:
                self.phasors_widgets[channel_index].removeItem(
                    self.quantization_images[channel_index]
                )
            if channel_index in self.phasors_colorbars:
                self.phasors_widgets[channel_index].removeItem(
                    self.phasors_colorbars[channel_index]
                )
            image_item.setZValue(-1)
            self.phasors_widgets[channel_index].addItem(image_item, ignoreBounds=True)
            self.quantization_images[channel_index] = image_item
            if not all_zeros:
                self.generate_colorbar(channel_index, h_min, h_max)
            self.clear_phasors_points()

    def generate_colorbar(self, channel_index, min_value, max_value):
        colorbar = pg.GradientLegend((10, 100), (10, 100))
        colorbar.setColorMap(self.create_cool_colormap(0, 1))
        colorbar.setLabels({f"{min_value}": 0, f"{max_value}": 1})
        self.phasors_widgets[channel_index].addItem(colorbar)
        self.phasors_colorbars[channel_index] = colorbar

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

    @staticmethod
    def create_hot_colormap():
        # Create the color stops from black to red to yellow to white
        pos = np.array([0.0, 0.33, 0.67, 1.0])
        color = np.array(
            [
                [0, 0, 0, 255],  # Black
                [255, 0, 0, 255],  # Red
                [255, 255, 0, 255],  # Yellow
                [255, 255, 255, 255],  # White
            ],
            dtype=np.ubyte,
        )
        cmap = pg.ColorMap(pos, color)
        return cmap

    def create_cool_colormap(self, start=0.0, end=1.0):
        # Define the color stops from cyan to magenta
        pos = np.array([start, end])
        color = np.array(
            [[0, 255, 255, 255], [255, 0, 255, 255]],  # Cyan  # Magenta
            dtype=np.float32,
        )
        cmap = pg.ColorMap(pos, color)
        return cmap

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

    def update_intensity_plots(self, channel_index, time_ns, curve):
        bin_width_micros = int(
            self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)
        )
        adjustment = (
            get_realtime_adjustment_value(
                self.selected_channels, self.tab_selected == TAB_PHASORS
            )
            / bin_width_micros
        )
        curve = tuple(x / adjustment for x in curve)
        if self.tab_selected in self.intensity_lines:
            if channel_index in self.intensity_lines[self.tab_selected]:
                intensity_line = self.intensity_lines[self.tab_selected][channel_index]
                if intensity_line is not None:
                    x, y = intensity_line.getData()
                    # Initialize or append data
                    if x is None or (len(x) == 1 and x[0] == 0):
                        x = np.array([time_ns / 1_000_000_000])
                        y = np.array([np.sum(curve)])
                    else:
                        x = np.append(x, time_ns / 1_000_000_000)
                        y = np.append(y, np.sum(curve))
                    # Trim data based on time span
                    if len(x) > 2:
                        while x[-1] - x[0] > self.cached_time_span_seconds:
                            x = x[1:]
                            y = y[1:]
                    intensity_line.setData(x, y)

    def update_spectroscopy_plots(self, x, y, channel_index, decay_curve):
        time_shift = (
                0
                if channel_index not in self.time_shifts
                else self.time_shifts[channel_index]
            ) if self.acquire_read_mode == "acquire" else 0     
        # Handle linear/logarithmic mode
        decay_widget = self.decay_widgets[channel_index]
        if (
            channel_index not in self.lin_log_mode
            or self.lin_log_mode[channel_index] == "LIN"
        ):
            decay_widget.showGrid(x=False, y=False, alpha=0.3)
            decay_curve.setData(x, np.roll(y, time_shift))
            self.set_plot_y_range(decay_widget)
        else:
            decay_widget.showGrid(x=False, y=True, alpha=0.3)
            sum_decay = y
            log_values, ticks, _ = LinLogControl.calculate_log_ticks(sum_decay)
            decay_curve.setData(x, np.roll(log_values, time_shift))
            axis = decay_widget.getAxis("left")
            axis.setTicks([ticks])
            self.set_plot_y_range(decay_widget)

    def update_plots2(self, channel_index, time_ns, curve, reader_mode=False):
        if not reader_mode:
            # Update intensity plots
            self.update_intensity_plots(channel_index, time_ns, curve)
        decay_curve = self.decay_curves[self.tab_selected][channel_index]
        if decay_curve is not None:
            if reader_mode:
                x, y = time_ns, curve
            else:
                x, y = decay_curve.getData()
                if self.tab_selected == TAB_PHASORS:
                    decay_curve.setData(x, curve + y)
                elif self.tab_selected in (TAB_SPECTROSCOPY, TAB_FITTING):
                    last_cached_decay_value = self.cached_decay_values[
                        self.tab_selected
                    ][channel_index]
                    self.cached_decay_values[self.tab_selected][channel_index] = (
                        np.array(curve) + last_cached_decay_value
                    )
                    y = self.cached_decay_values[self.tab_selected][channel_index]
            if self.tab_selected in (TAB_SPECTROSCOPY, TAB_FITTING):
                self.update_spectroscopy_plots(x, y, channel_index, decay_curve)
            else:
                decay_curve.setData(x, curve + y)
        QApplication.processEvents()
        time.sleep(0.01)

    def set_plot_y_range(self, plot):
        plot.plotItem.autoRange()
        view_range = plot.viewRange()
        _, y_max = view_range[1]
        plot.setYRange(-1, y_max, padding=0)

    def on_harmonic_selector_change(self, value):
        frequency_mhz = self.get_current_frequency_mhz()
        laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
        self.clear_phasors_points()
        if not self.phasors_widgets or value < 0:
            return
        self.harmonic_selector_value = int(value) + 1
        self.phasors_harmonic_selected = int(value) + 1
        if self.harmonic_selector_value >= 1 and self.quantized_phasors:
            self.quantize_phasors(
                self.harmonic_selector_value,
                bins=int(PHASORS_RESOLUTIONS[self.phasors_resolution]),
            )
        if not self.quantized_phasors:
            for i, channel_index in enumerate(self.plots_to_show):
                if len(self.plots_to_show) <= len(self.all_phasors_points):
                    self.draw_points_in_phasors(
                        channel_index,
                        self.harmonic_selector_value,
                        self.all_phasors_points[channel_index][
                            self.harmonic_selector_value
                        ],
                    )
        self.generate_phasors_cluster_center(self.harmonic_selector_value)
        self.generate_phasors_legend(self.harmonic_selector_value)
        for i, channel_index in enumerate(self.plots_to_show):
            self.draw_lifetime_points_in_phasors(
                channel_index,
                self.harmonic_selector_value,
                laser_period_ns,
                frequency_mhz,
            )

    def stop_spectroscopy_experiment(self):
        print("Stopping spectroscopy")
        try:
            flim_labs.request_stop()
        except:
            pass
        self.mode = MODE_STOPPED
        self.style_start_button()
        QApplication.processEvents()
        # time.sleep(0.5)
        # self.pull_from_queue_timer.stop()
        # time.sleep(0.5)
        # self.timer_update.stop()
        # self.update_plots_enabled = False
        is_export_data_active = self.write_data_gui
        LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, True)
        self.top_bar_set_enabled(True)

        def clear_cps_and_countdown_widgets():
            for _, animation in self.cps_widgets_animation.items():
                if animation:
                    animation.stop()
            for _, widget in self.acquisition_time_countdown_widgets.items():
                if widget:
                    widget.setVisible(False)

        QTimer.singleShot(400, clear_cps_and_countdown_widgets)
        QApplication.processEvents()
        if self.is_reference_phasors():
            # read reference file from .pid file
            with open(".pid", "r") as f:
                lines = f.readlines()
                reference_file = lines[0].split("=")[1]
            self.reference_file = reference_file
            self.saved_spectroscopy_reference = reference_file
            print(f"Last reference file: {reference_file}")
        harmonic_selected = int(
            self.settings.value(SETTINGS_HARMONIC, SETTINGS_HARMONIC_DEFAULT)
        )
        if self.is_phasors():
            frequency_mhz = self.get_current_frequency_mhz()
            laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
            for _, channel_index in enumerate(self.plots_to_show):
                self.phasors_widgets[channel_index].setCursor(
                    Qt.CursorShape.BlankCursor
                )
                self.generate_coords(channel_index)
                self.create_phasor_crosshair(
                    channel_index, self.phasors_widgets[channel_index]
                )
                self.draw_lifetime_points_in_phasors(
                    channel_index, 1, laser_period_ns, frequency_mhz
                )
            if self.quantized_phasors:
                self.quantize_phasors(
                    1, bins=int(PHASORS_RESOLUTIONS[self.phasors_resolution])
                )
            self.generate_phasors_cluster_center(1)                       
            self.generate_phasors_legend(1)                     
        if harmonic_selected > 1:
            self.harmonic_selector_shown = True
        if is_export_data_active:
            QTimer.singleShot(
                300,
                partial(
                    ExportData.save_acquisition_data, self, active_tab=self.tab_selected
                ),
            )
        if self.tab_selected == TAB_FITTING:
            self.fit_button_show()
        LaserbloodMetadataPopup.set_FPGA_firmware(self)            
        LaserbloodMetadataPopup.set_average_CPS(self.all_cps_counts, self) 
        LaserbloodMetadataPopup.set_average_SBR(self.all_SBR_counts, self)       
          

    def check_card_connection(self, start_experiment = False):
        try:
            card_serial_number = flim_labs.check_card()
            CheckCard.update_check_message(self, str(card_serial_number), error=False)
        except Exception as e:
            if str(e) == "CardNotFound":
                CheckCard.update_check_message(self, "Card Not Found", error=True)
            else:
                CheckCard.update_check_message(self, str(e), error=True)
            if start_experiment:
                raise    
                

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
