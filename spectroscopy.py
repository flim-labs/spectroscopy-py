import json
import os
import queue
import sys
import time
from math import floor, log
import flim_labs
import numpy as np
from components.box_message import BoxMessage
from components.buttons import CollapseButton, DownloadButton
from components.file_utils import save_spectroscopy_bin_file
from components.layout_utilities import draw_layout_separator
from components.lin_log_control import SpectroscopyLinLogControl
from components.plots_config import PlotsConfigPopup
import pyqtgraph as pg
from PyQt6.QtCore import QTimer, QSettings, QSize, Qt, QEvent
from PyQt6.QtGui import QPixmap, QFont, QIcon, QTransform
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
    QGraphicsView,
    QGraphicsScene,
    QGraphicsProxyWidget,
)
from components.fancy_checkbox import FancyButton
from components.gradient_text import GradientText
from components.gui_styles import GUIStyles
from components.helpers import format_size
from components.input_number_control import InputNumberControl, InputFloatControl
from components.link_widget import LinkWidget
from components.logo_utilities import OverlayWidget, TitlebarIcon
from components.resource_path import resource_path
from components.select_control import SelectControl
from components.switch_control import SwitchControl
from components.spectroscopy_curve_time_shift import SpectroscopyTimeShift
from settings import *

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class SpectroscopyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.update_plots_enabled = False
        self.settings = self.init_settings()
        self.widgets = {}
        self.channel_checkboxes = []
        self.sync_buttons = []
        self.control_inputs = {}
        self.mode = MODE_STOPPED
        self.tab_selected = "tab_spectroscopy"
        self.reference_file = None
        self.overlay2 = None
        self.acquisition_stopped = False
        self.intensity_lines = {}
        self.phasors_charts = {}
        self.phasors_widgets = {}
        self.phasors_coords = {}
        self.phasors_crosshairs = {}
        self.cps_widgets = {}
        self.cps_counts = {}
        self.decay_curves = {}
        self.decay_widgets = {}
        self.cached_decay_values = {}
        self.cached_decay_x_values = np.array([])
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
        self.decay_curves_queue = queue.Queue()
        self.harmonic_selector_value = 1
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
        self.selected_sync = self.settings.value(SETTINGS_SYNC, DEFAULT_SYNC)
        self.sync_in_frequency_mhz = float(
            self.settings.value(
                SETTINGS_SYNC_IN_FREQUENCY_MHZ, DEFAULT_SYNC_IN_FREQUENCY_MHZ
            )
        )
        self.write_data = True
        self.show_bin_file_size_helper = (
            self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA) == "true"
        )
        self.bin_file_size = ""
        self.bin_file_size_label = QLabel("")

        self.renamed_exported_spectroscopy_bin = None
        self.exported_source_spectroscopy_bin = None

        self.get_selected_channels_from_settings()

        (self.top_bar, self.grid_layout) = self.init_ui()

        self.on_tab_selected("tab_spectroscopy")

        # self.update_sync_in_button()

        self.generate_plots()
        self.all_phasors_points = self.get_empty_phasors_points()

        self.overlay = OverlayWidget(self)
        self.installEventFilter(self)

        self.timer_update = QTimer()
        self.timer_update.timeout.connect(self.update_plots)

        self.pull_from_queue_timer = QTimer()
        self.pull_from_queue_timer.timeout.connect(self.pull_from_queue)

        self.calc_exported_file_size()

    @staticmethod
    def get_empty_phasors_points():
        empty = []
        for i in range(8):
            empty.append({1: [], 2: [], 3: [], 4: []})
        return empty

    def init_ui(self):
        self.setWindowTitle("FlimLabs - SPECTROSCOPY v" + VERSION)
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self)
        main_layout = QVBoxLayout()
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar, 0, Qt.AlignmentFlag.AlignTop)
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
        self.control_inputs["tab_spectroscopy"] = QPushButton("SPECTROSCOPY")
        self.control_inputs["tab_spectroscopy"].setFlat(True)
        self.control_inputs["tab_spectroscopy"].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.control_inputs["tab_spectroscopy"].setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.control_inputs["tab_spectroscopy"].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs["tab_spectroscopy"])
        self.control_inputs["tab_spectroscopy"].setChecked(True)
        self.control_inputs["tab_spectroscopy"].clicked.connect(
            lambda: self.on_tab_selected("tab_spectroscopy")
        )
        tabs_layout.addWidget(self.control_inputs["tab_spectroscopy"])
        self.control_inputs["tab_data"] = QPushButton("PHASORS")
        self.control_inputs["tab_data"].setFlat(True)
        self.control_inputs["tab_data"].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.control_inputs["tab_data"].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["tab_data"].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs["tab_data"])
        self.control_inputs["tab_data"].clicked.connect(
            lambda: self.on_tab_selected("tab_data")
        )
        tabs_layout.addWidget(self.control_inputs["tab_data"])
        self.control_inputs["tab_deconv"] = QPushButton("FITTING")
        self.control_inputs["tab_deconv"].setFlat(True)
        self.control_inputs["tab_deconv"].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.control_inputs["tab_deconv"].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["tab_deconv"].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs["tab_deconv"])
        self.control_inputs["tab_deconv"].clicked.connect(
            lambda: self.on_tab_selected("tab_deconv")
        )
        tabs_layout.addWidget(self.control_inputs["tab_deconv"])
        top_bar_header.addLayout(tabs_layout)
        top_bar_header.addStretch(1)
        download_button = DownloadButton(self)
        info_link_widget, export_data_control = self.create_export_data_input()
        file_size_info_layout = self.create_file_size_info_row()
        top_bar_header.addWidget(download_button)
        top_bar_header.addWidget(info_link_widget)
        top_bar_header.addLayout(export_data_control)
        export_data_control.addSpacing(10)
        top_bar_header.addLayout(file_size_info_layout)
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
        # # add a label to use as status
        # self.control_inputs["status"] = QLabel("Status: Ready")
        # self.control_inputs["status"].setStyleSheet("QLabel { color : #FFA726; }")
        # top_bar.addWidget(self.control_inputs["status"])
        container = QWidget()
        container.setLayout(top_bar)
        return container

    def create_logo_and_title(self):
        row = QHBoxLayout()
        pixmap = QPixmap(
            resource_path("assets/spectroscopy-logo-white.png")
        ).scaledToWidth(40)
        ctl = QLabel(pixmap=pixmap)
        row.addWidget(ctl)
        row.addSpacing(10)
        ctl = GradientText(
            self,
            text="SPECTROSCOPY",
            colors=[(0.7, "#1E90FF"), (1.0, PALETTE_RED_1)],
            stylesheet=GUIStyles.set_main_title_style(),
        )
        ctl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(ctl)
        ctl = QWidget()
        ctl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(ctl)
        return row

    def create_export_data_input(self):
        export_data_active = (
            self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA) == "true"
        )
        # Link to export data documentation
        info_link_widget = LinkWidget(
            icon_filename=resource_path("assets/info-icon.png"),
            link="https://flim-labs.github.io/spectroscopy-py/v1.0/#gui-usage",
        )
        info_link_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        info_link_widget.show()
        # Export data switch control
        export_data_control = QHBoxLayout()
        export_data_label = QLabel("Export data:")
        inp = SwitchControl(
            active_color=PALETTE_BLUE_1, width=70, height=30, checked=export_data_active
        )
        inp.toggled.connect(self.on_export_data_changed)

        export_data_control.addWidget(export_data_label)
        export_data_control.addSpacing(8)
        export_data_control.addWidget(inp)
        export_data_control.addSpacing(8)
        return info_link_widget, export_data_control

    def create_file_size_info_row(self):
        export_data = self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA)
        export_data_active = export_data == True or export_data == "true"
        file_size_info_layout = QHBoxLayout()
        self.bin_file_size_label.setText("File size: " + str(self.bin_file_size))
        self.bin_file_size_label.setStyleSheet("QLabel { color : #f8f8f8; }")
        file_size_info_layout.addWidget(self.bin_file_size_label)
        (
            self.bin_file_size_label.show()
            if export_data_active
            else self.bin_file_size_label.hide()
        )
        return file_size_info_layout

    def create_control_inputs(self):
        controls_row = QHBoxLayout()
        controls_row.addSpacing(10)
        _, inp, __ = SelectControl.setup(
            "Channel type:",
            int(self.settings.value(SETTINGS_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)),
            controls_row,
            ["USB", "SMA"],
            self.on_connection_type_value_change,
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        self.control_inputs["channel_type"] = inp
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
        _, inp, label = SelectControl.setup(
            "Calibration:",
            int(
                self.settings.value(
                    SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE
                )
            ),
            controls_row,
            ["None", "Phasors Ref.", "IRF"],
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
        ctl, inp, label = SelectControl.setup(
            "Harmonic displayed:",
            1,
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
        save_button = QPushButton("SAVE")
        save_button.setFlat(True)
        save_button.setFixedHeight(55)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setHidden(True)
        save_button.clicked.connect(self.on_save_reference)
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
        self.control_inputs["save"] = save_button
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
        start_button = QPushButton("START")
        start_button.setObjectName("btn")
        start_button.setFlat(True)
        start_button.setFixedHeight(55)
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.on_start_button_click)
        self.control_inputs["start_button"] = start_button
        self.style_start_button()
        collapse_button = CollapseButton(self.widgets[TOP_COLLAPSIBLE_WIDGET])
        controls_row.addWidget(start_button)
        controls_row.addWidget(collapse_button)
        controls_row.addSpacing(10)
        return controls_row

    def style_start_button(self):
        if self.mode == MODE_STOPPED:
            self.control_inputs["start_button"].setText("START")
            GUIStyles.set_start_btn_style(self.control_inputs["start_button"])
        else:
            self.control_inputs["start_button"].setText("STOP")
            GUIStyles.set_stop_btn_style(self.control_inputs["start_button"])

    def change_download_script_options(self):
        if self.tab_selected == "tab_spectroscopy":
            self.control_inputs[PHASORS_SCRIPT_ACTION].setVisible(False)
            self.control_inputs[SPECTROSCOPY_SCRIPT_ACTION].setVisible(True)
        if self.tab_selected == "tab_data":
            self.control_inputs[PHASORS_SCRIPT_ACTION].setVisible(True)
            self.control_inputs[SPECTROSCOPY_SCRIPT_ACTION].setVisible(False)

    def on_tab_selected(self, tab_name):
        export_data = self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA)
        export_data_active = export_data == True or export_data == "true"
        self.control_inputs[self.tab_selected].setChecked(False)
        self.tab_selected = tab_name
        self.control_inputs[self.tab_selected].setChecked(True)
        self.hide_harmonic_selector()
        if tab_name == "tab_spectroscopy":
            self.control_inputs[DOWNLOAD_BUTTON].setVisible(export_data_active)
            # hide tau input
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs["calibration"].show()
            self.control_inputs["calibration_label"].show()
            current_tau = self.settings.value(SETTINGS_TAU_NS, "0")
            self.control_inputs["tau"].setValue(float(current_tau))
            current_harmonic = self.settings.value(SETTINGS_HARMONIC, "1")
            self.control_inputs[SETTINGS_HARMONIC].setValue(int(current_harmonic))
            self.on_tau_change(float(current_tau))
            self.on_harmonic_change(int(current_harmonic))
            current_calibration = self.settings.value(
                SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE
            )
            self.on_calibration_change(int(current_calibration))
            self.control_inputs[LOAD_REF_BTN].hide()
            channels_grid = self.widgets[CHANNELS_GRID]
            plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
            if plot_config_btn is not None:
                plot_config_btn.setVisible(True)
        elif tab_name == "tab_deconv":
            self.control_inputs[DOWNLOAD_BUTTON].setVisible(False)
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs["calibration"].hide()
            self.control_inputs["calibration_label"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs[LOAD_REF_BTN].show()
            self.control_inputs[LOAD_REF_BTN].setText("LOAD IRF")
            channels_grid = self.widgets[CHANNELS_GRID]
            plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
            if plot_config_btn is not None:
                plot_config_btn.setVisible(True)
        elif tab_name == "tab_data":
            self.control_inputs[DOWNLOAD_BUTTON].setVisible(export_data_active)
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs["calibration"].hide()
            self.control_inputs["calibration_label"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs[LOAD_REF_BTN].show()
            self.control_inputs[LOAD_REF_BTN].setText("LOAD REFERENCE")
            self.control_inputs["save"].setHidden(True)
            channels_grid = self.widgets[CHANNELS_GRID]
            plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
            if plot_config_btn is not None:
                plot_config_btn.setVisible(False)

        self.control_inputs["save"].setHidden(True)
        self.clear_plots()
        self.cached_decay_values.clear()
        self.generate_plots()

    def on_start_button_click(self):
        if self.mode == MODE_STOPPED:
            self.acquisition_stopped = False
            self.renamed_exported_spectroscopy_bin = None
            self.exported_source_spectroscopy_bin = None
            self.control_inputs["save"].setHidden(True)
            self.begin_spectroscopy_experiment()
        elif self.mode == MODE_RUNNING:
            self.acquisition_stopped = True
            self.stop_spectroscopy_experiment()
            self.change_download_script_options()

    def on_tau_change(self, value):
        self.settings.setValue(SETTINGS_TAU_NS, value)

    def on_harmonic_change(self, value):
        self.settings.setValue(SETTINGS_HARMONIC, value)

    def on_load_reference(self):
        if self.tab_selected == "tab_data":
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            # extension supported: .reference.json
            dialog.setNameFilter("Reference files (*.reference.json)")
            dialog.setDefaultSuffix("reference.json")
            file_name, _ = dialog.getOpenFileName(
                self,
                "Load reference file",
                "",
                "Reference files (*.reference.json)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_name:
                self.reference_file = file_name

    def on_save_reference(self):
        if self.tab_selected == "tab_spectroscopy":
            # read all lines from .pid file
            with open(".pid", "r") as f:
                lines = f.readlines()
                reference_file = lines[0].split("=")[1]
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            # extension supported: .reference.json
            dialog.setNameFilter("Reference files (*.reference.json)")
            dialog.setDefaultSuffix("reference.json")
            file_name, _ = dialog.getSaveFileName(
                self,
                "Save reference file",
                "",
                "Reference files (*.reference.json)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if file_name:
                if not file_name.endswith(".reference.json"):
                    file_name += ".reference.json"
                try:
                    with open(reference_file, "r") as f:
                        with open(file_name, "w") as f2:
                            f2.write(f.read())
                except:
                    BoxMessage.setup(
                        "Error",
                        "Error saving reference file",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )

    def get_free_running_state(self):
        return self.control_inputs[SETTINGS_FREE_RUNNING].isChecked()

    def on_acquisition_time_change(self, value):
        self.settings.setValue(SETTINGS_ACQUISITION_TIME, value)
        self.calc_exported_file_size()

    def on_time_span_change(self, value):
        self.settings.setValue(SETTINGS_TIME_SPAN, value)

    def on_free_running_changed(self, state):
        self.control_inputs[SETTINGS_ACQUISITION_TIME].setEnabled(not state)
        self.settings.setValue(SETTINGS_FREE_RUNNING, state)
        self.calc_exported_file_size()

    def on_bin_width_change(self, value):
        self.settings.setValue(SETTINGS_BIN_WIDTH, value)
        self.calc_exported_file_size()

    def on_connection_type_value_change(self, value):
        self.settings.setValue(SETTINGS_CONNECTION_TYPE, value)

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
        self.control_inputs[DOWNLOAD_BUTTON].setVisible(state)
        self.settings.setValue(SETTINGS_WRITE_DATA, state)
        self.bin_file_size_label.show() if state else self.bin_file_size_label.hide()
        self.calc_exported_file_size() if state else None

    def create_channel_selector(self):
        grid = QHBoxLayout()
        plots_config_btn = QPushButton(" PLOTS CONFIG")
        plots_config_btn.setIcon(QIcon(resource_path("assets/chart-icon.png")))
        GUIStyles.set_stop_btn_style(plots_config_btn)
        plots_config_btn.setFixedWidth(150)
        plots_config_btn.setFixedHeight(40)
        plots_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plots_config_btn.clicked.connect(self.open_plots_config_popup)
        for i in range(MAX_CHANNELS):
            ch_wrapper = QWidget()
            ch_wrapper.setObjectName(f"ch_checkbox_wrapper")
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
            grid.addWidget(ch_wrapper)
            self.channel_checkboxes.append(fancy_checkbox)
        grid.addWidget(plots_config_btn)
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
                not self.get_free_running_state()
            )

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
        self.plots_to_show.clear()
        self.settings.setValue(SETTINGS_PLOTS_TO_SHOW, json.dumps(self.plots_to_show))
        if checked:
            if channel not in self.selected_channels:
                self.selected_channels.append(channel)
        else:
            if channel in self.selected_channels:
                self.selected_channels.remove(channel)
        self.selected_channels.sort()
        self.set_selected_channels_to_settings()
        self.cached_decay_values.clear()
        self.clear_plots()
        # self.generate_plots()
        self.calc_exported_file_size()

    def on_sync_selected(self, sync: str):
        if self.selected_sync == sync and sync == "sync_in":
            self.start_sync_in_dialog()
            return
        self.selected_sync = sync
        self.settings.setValue(SETTINGS_SYNC, sync)

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
            self.sync_buttons[0][0].setText("Sync In (not detected)")
        else:
            self.sync_buttons[0][0].setText(
                f"Sync In ({self.sync_in_frequency_mhz} MHz)"
            )

    def create_sync_buttons(self):
        buttons_layout = QHBoxLayout()
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
        return buttons_layout

    def generate_plots(self, frequency_mhz=0.0):
        self.lin_log_switches.clear()
        if len(self.plots_to_show) == 0:
            self.grid_layout.addWidget(QWidget(), 0, 0)
            return
        for i, channel in enumerate(self.plots_to_show):
            v_layout = QVBoxLayout()
            v_widget = QWidget()
            v_widget.setObjectName("chart_wrapper")
            if self.tab_selected != "tab_data":
                h_layout = QHBoxLayout()
                label = QLabel("No CPS")
                label.setStyleSheet(
                    "QLabel { color : #285da6; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px; }"
                )
                # label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                self.cps_widgets[channel] = label
                self.cps_counts[channel] = {
                    "last_time_ns": 0,
                    "last_count": 0,
                    "current_count": 0,
                }
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
                x = np.arange(1)
                y = x * 0
                intensity_plot = intensity_widget.plot(x, y, pen="#1E90FF", pen_width=2)
                self.intensity_lines[channel] = intensity_plot
                h_layout.addWidget(label, stretch=1)
                if len(self.plots_to_show) == 1:
                    intensity_plot_stretch = 6
                elif len(self.plots_to_show) == 2:
                    intensity_plot_stretch = 4
                elif len(self.plots_to_show) == 3:
                    intensity_plot_stretch = 2
                else:
                    intensity_plot_stretch = 4
                h_layout.addWidget(intensity_widget, stretch=intensity_plot_stretch)
                v_layout.addLayout(h_layout, 2)
                h_decay_layout = QHBoxLayout()
                lin_log_widget = SpectroscopyLinLogControl(self, channel)
                curve_widget = pg.PlotWidget()
                curve_widget.setLabel("left", "Photon counts", units="")
                curve_widget.setLabel("bottom", "Time", units="ns")
                curve_widget.setTitle(f"Channel {channel + 1} decay")
                curve_widget.setBackground("#0a0a0a")
                if frequency_mhz != 0.0:
                    period = 1_000 / frequency_mhz
                    x = np.linspace(0, period, 256)
                else:
                    x = np.arange(1)
                y = x * 0
                if channel not in self.lin_log_mode or self.lin_log_mode[channel] == "LIN":
                    static_curve = curve_widget.plot(x, y, pen="#f72828", pen_width=2)
                else:
                    y = (
                        np.linspace(0, 100000000, 256)
                        if frequency_mhz != 0.0
                        else np.array([0])
                    )
                    log_values, ticks = SpectroscopyLinLogControl.calculate_log_ticks(y)
                    static_curve = curve_widget.plot(
                        x, log_values, pen="#f72828", pen_width=2
                    )
                    axis = curve_widget.getAxis("left")
                    axis.setTicks([ticks])
                curve_widget.plotItem.getAxis("left").enableAutoSIPrefix(False)
                curve_widget.plotItem.getAxis("bottom").enableAutoSIPrefix(False)
                self.cached_decay_values[channel] = np.array([0])
                self.decay_curves[channel] = static_curve
                self.decay_widgets[channel] = curve_widget
                time_shift_layout = SpectroscopyTimeShift(self, channel)
                v_decay_layout = QVBoxLayout()
                v_decay_layout.addWidget(time_shift_layout)
                v_decay_layout.addWidget(curve_widget)
                h_decay_layout.addWidget(lin_log_widget, 1)
                h_decay_layout.addLayout(v_decay_layout, 11)
                v_layout.addLayout(h_decay_layout, 3)
                v_widget.setLayout(v_layout)
            else:
                h_layout = QHBoxLayout()
                label = QLabel("No CPS")
                label.setStyleSheet(
                    "QLabel { color : #f72828; font-size: 42px; font-weight: bold; background-color: #000000; padding: 8px; }"
                )
                # label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                self.cps_widgets[channel] = label
                self.cps_counts[channel] = {
                    "last_time_ns": 0,
                    "last_count": 0,
                    "current_count": 0,
                }
                curve_widget = pg.PlotWidget()
                curve_widget.setLabel("left", "Photon counts", units="")
                curve_widget.setLabel("bottom", "Time", units="ns")
                curve_widget.setTitle(f"Channel {channel + 1} decay")
                if frequency_mhz != 0.0:
                    period = 1_000 / frequency_mhz
                    x = np.linspace(0, period, 256)
                else:
                    x = np.arange(1)
                y = x * 0
                static_curve = curve_widget.plot(x, y, pen="#f72828", pen_width=2)
                self.decay_curves[channel] = static_curve
                h_layout.addWidget(label, stretch=1)
                h_layout.addWidget(curve_widget, stretch=1)
                v_layout.addLayout(h_layout, 1)
                # add a phasors chart
                phasors_widget = pg.PlotWidget()
                # mantain aspect ratio
                phasors_widget.setAspectLocked(True)
                phasors_widget.setLabel("left", "s", units="")
                phasors_widget.setLabel("bottom", "g", units="")
                phasors_widget.setTitle(f"Channel {channel + 1} phasors")
                phasors_widget.setCursor(Qt.CursorShape.BlankCursor)
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
                v_layout.addWidget(phasors_widget, 4)
                v_widget.setLayout(v_layout)
                self.generate_coords(channel)
                # create crosshair for phasors (a circle)
                crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(30, 144, 255))
                font = QFont()
                font.setPixelSize(25)
                crosshair.setFont(font)
                phasors_widget.addItem(crosshair, ignoreBounds=True)
                self.phasors_crosshairs[channel] = crosshair
            col_length = 1
            if len(self.plots_to_show) == 2:
                col_length = 2
            elif len(self.plots_to_show) == 3:
                col_length = 3
            if len(self.plots_to_show) > 3:
                col_length = 2
            v_widget.setStyleSheet(GUIStyles.chart_wrapper_style())
            self.grid_layout.addWidget(v_widget, i // col_length, i % col_length)

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
        self.phasors_widgets[channel_index].addItem(coord_text, ignoreBounds=True)
        self.phasors_widgets[channel_index].addItem(crosshair, ignoreBounds=True)

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
        harmonic = self.harmonic_selector_value
        g = mouse_point.x()
        s = mouse_point.y()
        if freq_mhz == 0.0:
            return
        tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (s / g) * 1e3
        tau_m_component = (1 / (s**2 + g**2)) - 1
        if tau_m_component < 0:
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} ns")
            text.setHtml(
                '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                    f"𝜏ϕ={round(tau_phi, 2)} ns"
                )
            )
        else:
            tau_m = (
                (1 / (2 * np.pi * freq_mhz * harmonic)) * np.sqrt(tau_m_component) * 1e3
            )
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏m={round(tau_m, 2)} ns")
            text.setHtml(
                '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                    f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏m={round(tau_m, 2)} ns"
                )
            )

    def draw_semi_circle(self, widget):
        x = np.linspace(0, 1, 1000)
        y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
        widget.plot(x, y, pen="#1E90FF", pen_width=4)
        widget.plot([-0.1, 1.1], [0, 0], pen="#1E90FF", pen_width=4)

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

    def stop_plots(self):
        self.timer_update.stop()

    def clear_plots(self):
        self.phasors_charts.clear()
        self.phasors_widgets.clear()
        self.decay_widgets.clear()
        self.phasors_coords.clear()
        self.cps_widgets.clear()
        self.cps_counts.clear()
        self.intensity_lines.clear()
        self.decay_curves.clear()
        self.cached_decay_x_values = np.array([])
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

    def begin_spectroscopy_experiment(self):
        bin_width_micros = int(
            self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)
        )
        if self.selected_sync == "sync_in":
            frequency_mhz = self.sync_in_frequency_mhz
        else:
            frequency_mhz = int(self.selected_sync.split("_")[-1])
        if frequency_mhz == 0.0:
            BoxMessage.setup(
                "Error",
                "Frequency not detected",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return
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
        if self.tab_selected != "tab_data":
            open_config_plots_popup = len(self.plots_to_show) == 0
            if open_config_plots_popup:
                popup = PlotsConfigPopup(self, start_acquisition=True)
                popup.show()
                return
        self.clear_plots()
        self.cached_decay_values.clear()
        self.generate_plots(frequency_mhz)
        self.hide_harmonic_selector()
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
        if self.tab_selected == "tab_data":
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
                None if self.tab_selected != "tab_data" else self.reference_file
            )
            self.all_phasors_points = self.get_empty_phasors_points()
            flim_labs.start_spectroscopy(
                enabled_channels=self.selected_channels,
                bin_width_micros=bin_width_micros,
                frequency_mhz=frequency_mhz,
                firmware_file=firmware_selected,
                acquisition_time_millis=acquisition_time_millis,
                tau_ns=tau_ns,
                reference_file=reference_file,
                harmonics=int(self.harmonic_selector_value),
            )
        except Exception as e:
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
        SpectroscopyLinLogControl.set_lin_log_switches_enable_mode(self, False)
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
            self.phasors_widgets[channel_index].clear()
            self.phasors_widgets[channel_index].addItem(image_item, ignoreBounds=True)
            self.draw_semi_circle(self.phasors_widgets[channel_index])
            self.generate_coords(channel_index)
            if not all_zeros:
                self.generate_colorbar(channel_index, h_min, h_max)

    def generate_colorbar(self, channel_index, min_value, max_value):
        colorbar = pg.GradientLegend((10, 100), (10, 100))
        colorbar.setColorMap(self.create_cool_colormap(0, 1))
        colorbar.setLabels({f"{min_value}": 0, f"{max_value}": 1})
        self.phasors_widgets[channel_index].addItem(colorbar)

    def show_harmonic_selector(self, harmonics):
        if harmonics > 1:
            self.control_inputs[HARMONIC_SELECTOR].show()
            self.control_inputs[HARMONIC_SELECTOR_LABEL].show()
            # clear the items
            self.control_inputs[HARMONIC_SELECTOR].clear()
            for i in range(harmonics):
                self.control_inputs[HARMONIC_SELECTOR].addItem(str(i + 1))
            self.control_inputs[HARMONIC_SELECTOR].setCurrentIndex(0)
            self.harmonic_selector_value = 1

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
        return self.tab_selected == "tab_spectroscopy" and selected_calibration == 1

    def is_phasors(self):
        return self.tab_selected == "tab_data"

    def update_cps(self, channel_index, time_ns, curve):
        # check if there is channel_index'th element in cps_counts
        if not (channel_index in self.cps_counts):
            return
        cps = self.cps_counts[channel_index]
        curve_sum = np.sum(curve)
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
            self.cps_widgets[channel_index].setText(
                f"{self.humanize_number(cps_value)} CPS"
            )
            cps["last_time_ns"] = time_ns
            cps["last_count"] = cps["current_count"]

    def humanize_number(self, number):
        if number == 0:
            return "0"
        units = ["", "K", "M", "G", "T", "P"]
        k = 1000.0
        magnitude = int(floor(log(number, k)))
        return "%.2f%s" % (number / k**magnitude, units[magnitude])

    def update_plots2(self, channel_index, time_ns, curve):
        if channel_index in self.intensity_lines:
            intensity_line = self.intensity_lines[channel_index]
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
        # Update decay plot
        decay_curve = self.decay_curves[channel_index]
        time_shift = 0 if channel_index not in self.time_shifts else self.time_shifts[channel_index]
        if decay_curve is not None:
            x, y = decay_curve.getData()
            if self.tab_selected != "tab_spectroscopy":
                decay_curve.setData(x, curve + y)
            else:
                last_cached_decay_value = self.cached_decay_values[channel_index]
                self.cached_decay_values[channel_index] = np.array(curve) + last_cached_decay_value
                # Handle linear/logarithmic mode
                decay_widget = self.decay_widgets[channel_index]
                if channel_index not in self.lin_log_mode or self.lin_log_mode[channel_index] == "LIN":
                    decay_widget.showGrid(x=False, y=False, alpha=0.3)
                    decay_curve.setData(x, np.roll(self.cached_decay_values[channel_index], time_shift))
                else:
                    decay_widget.showGrid(x=False, y=True, alpha=0.3)
                    sum_decay = self.cached_decay_values[channel_index]
                    log_values, ticks = SpectroscopyLinLogControl.calculate_log_ticks(sum_decay)
                    decay_curve.setData(x, np.roll(log_values, time_shift))
                    axis = decay_widget.getAxis("left")
                    axis.setTicks([ticks])
        QApplication.processEvents()
        time.sleep(0.01)

    def on_harmonic_selector_change(self, value):
        self.harmonic_selector_value = int(value) + 1
        if self.harmonic_selector_value >= 1:
            self.quantize_phasors(self.harmonic_selector_value)

    def update_plots(self):
        try:
            (channel_index, time_ns, curve) = self.decay_curves_queue.get(
                block=True, timeout=0.1
            )
        except queue.Empty:
            QApplication.processEvents()
            return
        except Exception as e:
            print("Error: " + str(e))
            return
        x, y = self.intensity_lines[channel_index].getData()
        if x is None or (len(x) == 1 and x[0] == 0):
            x = np.array([time_ns / 1_000_000_000])
            y = np.array([np.sum(curve)])
        else:
            x = np.append(x, time_ns / 1_000_000_000)
            y = np.append(y, np.sum(curve))
        # if len(x) > 100:
        #     x = x[1:]
        #     y = y[1:]
        self.intensity_lines[channel_index].setData(x, y)
        x, y = self.decay_curves[channel_index].getData()
        self.decay_curves[channel_index].setData(x, curve + y)
        QApplication.processEvents()
        time.sleep(0.01)

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
        export_data = self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA)
        is_export_data_active = export_data == True or export_data == "true"
        if is_export_data_active:
            save_spectroscopy_bin_file(self)
        SpectroscopyLinLogControl.set_lin_log_switches_enable_mode(self, True)
        self.top_bar_set_enabled(True)
        self.change_download_script_options()
        QApplication.processEvents()
        if self.is_reference_phasors():
            # read reference file from .pid file
            with open(".pid", "r") as f:
                lines = f.readlines()
                reference_file = lines[0].split("=")[1]
                self.reference_file = reference_file
                self.control_inputs["save"].setHidden(False)
                print(f"Last reference file: {reference_file}")
            if not (self.is_phasors()):
                self.control_inputs["save"].setHidden(False)
                if self.is_phasors():
                    self.control_inputs["save"].setHidden(True)
                    self.quantize_phasors(1)
                    self.show_harmonic_selector(self.harmonic_selector_value)

    def open_plots_config_popup(self):
        self.popup = PlotsConfigPopup(self, start_acquisition=False)
        self.popup.show()

    def closeEvent(self, event):
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        if PLOTS_CONFIG_POPUP in self.widgets:
            self.widgets[PLOTS_CONFIG_POPUP].close()
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

class SyncInDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sync In Measure Frequency")
        self.setFixedSize(300, 200)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.label = QLabel("Do you want to start to measure frequency?")
        self.layout.addWidget(self.label)
        self.label.setWordWrap(True)
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.no_button = QPushButton("No")
        self.no_button.clicked.connect(self.on_no_button_click)
        self.button_layout.addWidget(self.no_button)
        self.yes_button = QPushButton("Do it")
        self.yes_button.clicked.connect(self.on_yes_button_click)
        self.button_layout.addWidget(self.yes_button)
        self.frequency_mhz = 0.0
        GUIStyles.customize_theme(self)
        GUIStyles.set_fonts()

    def on_yes_button_click(self):
        self.label.setText(
            "Measuring frequency... The process can take a few seconds. Please wait. After 30 seconds, the process "
            "will be interrupted automatically."
        )
        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)
        QApplication.processEvents()
        try:
            res = flim_labs.detect_laser_frequency()
            if res is None or res == 0.0:
                self.frequency_mhz = 0.0
                self.label.setText(
                    "Frequency not detected. Please check the connection and try again."
                )
                self.no_button.setText("Cancel")
            else:
                self.frequency_mhz = round(res, 3)
                self.label.setText(f"Frequency detected: {self.frequency_mhz} MHz")
                self.no_button.setText("Done")
        except Exception as e:
            self.frequency_mhz = 0.0
            self.label.setText("Error: " + str(e))
            self.no_button.setText("Cancel")
        self.yes_button.setEnabled(True)
        self.yes_button.setText("Retry again")
        self.no_button.setEnabled(True)

    def on_no_button_click(self):
        self.close()


if __name__ == "__main__":
    # remove .pid file if exists
    if os.path.exists(".pid"):
        os.remove(".pid")
    app = QApplication(sys.argv)
    window = SpectroscopyWindow()
    window.showMaximized()
    window.show()
    app.exec()
    window.pull_from_queue_timer.stop()
    sys.exit()
