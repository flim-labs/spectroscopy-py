import json
import os
import queue
import sys
import time
from math import floor, log

import flim_labs
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer, QSettings, QSize, Qt, QEvent
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLayout, QLabel, \
    QSizePolicy, QPushButton, QDialog, QMessageBox, QFileDialog

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

VERSION = "1.2"
APP_DEFAULT_WIDTH = 1000
APP_DEFAULT_HEIGHT = 800
TOP_BAR_HEIGHT = 250
MAX_CHANNELS = 8
current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

SETTINGS_BIN_WIDTH = "bin_width"
DEFAULT_BIN_WIDTH = 1000
SETTINGS_TIME_SPAN = "time_span"
DEFAULT_TIME_SPAN = 10
SETTINGS_CONNECTION_TYPE = "connection_type"
SETTINGS_CALIBRATION_TYPE = "calibration"
DEFAULT_SETTINGS_CALIBRATION_TYPE = 0
DEFAULT_CONNECTION_TYPE = "1"
SETTINGS_FREE_RUNNING = "free_running"
DEFAULT_FREE_RUNNING = "false"
SETTINGS_ACQUISITION_TIME = "acquisition_time"
SETTINGS_TAU_NS = "tau_ns"
SETTINGS_HARMONIC = "harmonic"
HARMONIC_SELECTOR = "harmonic_selector"
HARMONIC_SELECTOR_LABEL = "harmonic_selector_label"
SETTINGS_HARMONIC_LABEL = "harmonic_label"
SETTINGS_HARMONIC_DEFAULT = 1
DEFAULT_ACQUISITION_TIME = 10
SETTINGS_SYNC = "sync"
DEFAULT_SYNC = "sync_in"
SETTINGS_SYNC_IN_FREQUENCY_MHZ = "sync_in_frequency_mhz"
DEFAULT_SYNC_IN_FREQUENCY_MHZ = 0.0
SETTINGS_WRITE_DATA = "write_data"
DEFAULT_WRITE_DATA = True
CURSOR_TEXT = "⨁"

LOAD_REF_BTN = "load_reference_btn"

MODE_STOPPED = "stopped"
MODE_RUNNING = "running"


class SpectroscopyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.update_plots_enabled = False
        self.settings = self.init_settings()

        self.channel_checkboxes = []
        self.sync_buttons = []
        self.control_inputs = {}

        self.mode = MODE_STOPPED
        self.tab_selected = "tab_spectroscopy"
        self.reference_file = None

        self.intensity_lines = []
        self.phasors_charts = []
        self.phasors_widgets = []
        self.phasors_coords = []
        self.phasors_crosshairs = []
        self.cps_widgets = []
        self.cps_counts = []
        self.decay_curves = []
        self.decay_curves_queue = queue.Queue()
        self.harmonic_selector_value = 1
        self.cached_time_span_seconds = 3

        self.selected_channels = []
        self.selected_sync = self.settings.value(SETTINGS_SYNC, DEFAULT_SYNC)
        self.sync_in_frequency_mhz = float(
            self.settings.value(SETTINGS_SYNC_IN_FREQUENCY_MHZ, DEFAULT_SYNC_IN_FREQUENCY_MHZ))

        self.write_data = True
        self.show_bin_file_size_helper = self.settings.value(SETTINGS_WRITE_DATA, DEFAULT_WRITE_DATA) == 'true'

        self.bin_file_size = ''
        self.bin_file_size_label = QLabel("")

        self.get_selected_channels_from_settings()

        (self.top_bar, self.grid_layout) = self.init_ui()

        self.on_tab_selected("tab_spectroscopy")

        # self.update_sync_in_button()

        self.generate_plots()

        self.overlay = OverlayWidget(self)
        self.overlay.resize(QSize(100, 100))
        self.installEventFilter(self)
        self.overlay.raise_()

        GUIStyles.set_fonts(self)

        self.timer_update = QTimer()
        self.timer_update.timeout.connect(self.update_plots)

        self.pull_from_queue_timer = QTimer()
        self.pull_from_queue_timer.timeout.connect(self.pull_from_queue)
        # self.timer_update.start(25)

        self.calc_exported_file_size()

    def eventFilter(self, source, event):
        try:
            if event.type() in (
                    QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                self.overlay.raise_()
                self.overlay.resize(self.size())
            return super().eventFilter(source, event)
        except:
            pass

    def init_ui(self):
        self.setWindowTitle("FlimLabs - SPECTROSCOPY v" + VERSION)
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self)
        main_layout = QVBoxLayout()
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(main_layout)

        self.resize(self.settings.value("size", QSize(APP_DEFAULT_WIDTH, APP_DEFAULT_HEIGHT)))
        self.move(
            self.settings.value("pos", QApplication.primaryScreen().geometry().center() - self.frameGeometry().center())
        )

        return top_bar, grid_layout

    @staticmethod
    def init_settings():
        settings = QSettings('settings.ini', QSettings.Format.IniFormat)
        return settings

    def closeEvent(self, event):
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        event.accept()

    def create_top_bar(self):
        top_bar = QVBoxLayout()
        top_bar.setAlignment(Qt.AlignmentFlag.AlignTop)

        top_bar_header = QHBoxLayout()

        top_bar_header.addLayout(self.create_logo_and_title())

        # add hlayout
        tabs_layout = QHBoxLayout()
        # set height of parent
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        # no spacing
        tabs_layout.setSpacing(0)

        self.control_inputs["tab_spectroscopy"] = QPushButton("Spectroscopy")
        self.control_inputs["tab_spectroscopy"].setFlat(True)
        self.control_inputs["tab_spectroscopy"].setSizePolicy(QSizePolicy.Policy.Preferred,
                                                              QSizePolicy.Policy.Preferred)
        self.control_inputs["tab_spectroscopy"].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["tab_spectroscopy"].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs["tab_spectroscopy"])
        self.control_inputs["tab_spectroscopy"].setChecked(True)
        self.control_inputs["tab_spectroscopy"].clicked.connect(lambda: self.on_tab_selected("tab_spectroscopy"))
        tabs_layout.addWidget(self.control_inputs["tab_spectroscopy"])

        self.control_inputs["tab_data"] = QPushButton("Phasors")
        self.control_inputs["tab_data"].setFlat(True)
        self.control_inputs["tab_data"].setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.control_inputs["tab_data"].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["tab_data"].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs["tab_data"])
        self.control_inputs["tab_data"].clicked.connect(lambda: self.on_tab_selected("tab_data"))
        tabs_layout.addWidget(self.control_inputs["tab_data"])

        self.control_inputs["tab_deconv"] = QPushButton("Fitting")
        self.control_inputs["tab_deconv"].setFlat(True)
        self.control_inputs["tab_deconv"].setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.control_inputs["tab_deconv"].setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_inputs["tab_deconv"].setCheckable(True)
        GUIStyles.set_config_btn_style(self.control_inputs["tab_deconv"])
        self.control_inputs["tab_deconv"].clicked.connect(lambda: self.on_tab_selected("tab_deconv"))
        tabs_layout.addWidget(self.control_inputs["tab_deconv"])

        top_bar_header.addLayout(tabs_layout)

        top_bar_header.addStretch(1)
        info_link_widget, export_data_control = self.create_export_data_input()
        file_size_info_layout = self.create_file_size_info_row()

        top_bar_header.addWidget(info_link_widget)
        top_bar_header.addLayout(export_data_control)
        export_data_control.addSpacing(10)

        top_bar_header.addLayout(file_size_info_layout)

        top_bar.addLayout(top_bar_header)
        top_bar.addSpacing(10)
        top_bar.addLayout(self.create_channel_selector())
        top_bar.addLayout(self.create_sync_buttons())
        top_bar.addSpacing(5)
        top_bar.addLayout(self.create_control_inputs())

        # # add a label to use as status
        # self.control_inputs["status"] = QLabel("Status: Ready")
        # self.control_inputs["status"].setStyleSheet("QLabel { color : #FFA726; }")
        # top_bar.addWidget(self.control_inputs["status"])

        container = QWidget()
        container.setLayout(top_bar)
        container.setFixedHeight(TOP_BAR_HEIGHT)
        return container

    def create_logo_and_title(self):
        row = QHBoxLayout()

        pixmap = QPixmap(
            resource_path("assets/spectroscopy-logo-white.png")
        ).scaledToWidth(38)
        ctl = QLabel(pixmap=pixmap)
        row.addWidget(ctl)

        row.addSpacing(10)

        ctl = GradientText(self,
                           text="SPECTROSCOPY",
                           colors=[(0.5, "#23F3AB"), (1.0, "#8d4ef2")],
                           stylesheet=GUIStyles.set_main_title_style())
        ctl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(ctl)

        ctl = QWidget()
        ctl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(ctl)
        return row

    def create_export_data_input(self):
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
            active_color="#FB8C00", width=70, height=30, checked=self.write_data
        )
        inp.toggled.connect(self.on_export_data_changed)
        export_data_control.addWidget(export_data_label)
        export_data_control.addSpacing(8)
        export_data_control.addWidget(inp)

        return info_link_widget, export_data_control

    def create_file_size_info_row(self):
        file_size_info_layout = QHBoxLayout()
        self.bin_file_size_label.setText("File size: " + str(self.bin_file_size))
        self.bin_file_size_label.setStyleSheet("QLabel { color : #FFA726; }")

        file_size_info_layout.addWidget(self.bin_file_size_label)
        self.bin_file_size_label.show() if self.write_data is True else self.bin_file_size_label.hide()

        return file_size_info_layout

    def create_control_inputs(self):
        controls_row = QHBoxLayout()
        _, inp, __ = SelectControl.setup(
            "Channel type:",
            self.settings.value(SETTINGS_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE),
            controls_row,
            ["USB", "SMA"],
            self.on_connection_type_value_change
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        self.control_inputs["channel_type"] = inp

        _, inp = InputNumberControl.setup(
            "Bin width (µs):",
            100,
            1000000,
            int(self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)),
            controls_row,
            self.on_bin_width_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_BIN_WIDTH] = inp

        _, inp = InputNumberControl.setup(
            "Time span (s):",
            1,
            300,
            int(self.settings.value(SETTINGS_TIME_SPAN, DEFAULT_TIME_SPAN)),
            controls_row,
            self.on_time_span_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_TIME_SPAN] = inp

        switch_control = QVBoxLayout()
        inp = SwitchControl(
            active_color="#8d4ef2",
            checked=self.settings.value(SETTINGS_FREE_RUNNING, DEFAULT_FREE_RUNNING) == "true"
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
            int(self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)),
            controls_row,
            self.on_acquisition_time_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_ACQUISITION_TIME] = inp
        self.on_free_running_changed(self.settings.value(SETTINGS_FREE_RUNNING, DEFAULT_FREE_RUNNING) == "true")

        _, inp, label = SelectControl.setup(
            "Calibration:",
            int(self.settings.value(SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE)),
            controls_row,
            ["None", "Phasors Ref.", "IRF"],
            self.on_calibration_change
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
            self.on_tau_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs["tau"] = inp
        self.control_inputs["tau_label"] = label

        label, inp = InputNumberControl.setup(
            "Harmonics",
            1,
            1,
            int(self.settings.value(SETTINGS_HARMONIC, "1")),
            controls_row,
            self.on_harmonic_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs[SETTINGS_HARMONIC] = inp
        self.control_inputs[SETTINGS_HARMONIC_LABEL] = label

        ctl, inp, label = SelectControl.setup(
            "Harmonic:",
            1,
            controls_row,
            ["1", "2", "3", "4"],
            self.on_harmonic_selector_change
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        self.control_inputs[HARMONIC_SELECTOR_LABEL] = label
        self.control_inputs[HARMONIC_SELECTOR] = inp
        label.hide()
        inp.hide()

        spacer = QWidget()
        spacer.setMaximumWidth(300)
        controls_row.addWidget(spacer)

        save_button = QPushButton("LOAD REFERENCE")
        save_button.setFlat(True)
        save_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setHidden(True)
        save_button.clicked.connect(self.on_load_reference)
        save_button.setStyleSheet("""
        QPushButton {
            background-color: #8d4ef2;
            color: white;
            border-radius: 5px;
            padding: 5px 10px;
            font-size: 16px;
        }
        """)
        self.control_inputs[LOAD_REF_BTN] = save_button
        controls_row.addWidget(save_button)

        save_button = QPushButton("SAVE")
        save_button.setFlat(True)
        save_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setHidden(True)
        save_button.clicked.connect(self.on_save_reference)
        save_button.setStyleSheet("""
        QPushButton {
            background-color: #8d4ef2;
            color: white;
            border-radius: 5px;
            padding: 5px 10px;
            font-size: 16px;
        }
        """)
        self.control_inputs["save"] = save_button
        controls_row.addWidget(save_button)

        export_button = QPushButton("EXPORT")
        export_button.setFlat(True)
        export_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setHidden(True)
        export_button.clicked.connect(self.export_data)
        export_button.setStyleSheet("""
        QPushButton {
            background-color: #8d4ef2;
            color: white;
            border-radius: 5px;
            padding: 5px 10px;
            font-size: 16px;
        }
        """)
        self.control_inputs["export_button"] = export_button
        controls_row.addWidget(export_button)

        start_button = QPushButton("START")
        start_button.setFlat(True)
        start_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.on_start_button_click)
        self.control_inputs["start_button"] = start_button
        self.style_start_button()
        controls_row.addWidget(start_button)

        return controls_row

    def style_start_button(self):
        if self.mode == MODE_STOPPED:
            self.control_inputs["start_button"].setText("START")
            GUIStyles.set_start_btn_style(self.control_inputs["start_button"])
        else:
            self.control_inputs["start_button"].setText("STOP")
            GUIStyles.set_stop_btn_style(self.control_inputs["start_button"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(event.size())

    def on_tab_selected(self, tab_name):
        self.control_inputs[self.tab_selected].setChecked(False)
        self.tab_selected = tab_name
        self.control_inputs[self.tab_selected].setChecked(True)
        if tab_name == "tab_spectroscopy":
            # hide tau input
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs["calibration"].show()
            self.control_inputs["calibration_label"].show()
            self.control_inputs[SETTINGS_CALIBRATION_TYPE].setCurrentIndex(DEFAULT_SETTINGS_CALIBRATION_TYPE)
            self.on_tau_change(0.0)
            self.on_harmonic_change(1)
            self.on_calibration_change(DEFAULT_SETTINGS_CALIBRATION_TYPE)
            self.control_inputs[LOAD_REF_BTN].hide()
        elif tab_name == "tab_deconv":
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs["calibration"].hide()
            self.control_inputs["calibration_label"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs[LOAD_REF_BTN].show()
            self.control_inputs[LOAD_REF_BTN].setText("LOAD IRF")
        elif tab_name == "tab_data":
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs["calibration"].hide()
            self.control_inputs["calibration_label"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()
            self.control_inputs[LOAD_REF_BTN].show()
            self.control_inputs[LOAD_REF_BTN].setText("LOAD REFERENCE")

        self.control_inputs["save"].setHidden(True)

        self.clear_plots()
        self.generate_plots()

    def on_start_button_click(self):
        if self.mode == MODE_STOPPED:
            self.begin_spectroscopy_experiment()
        elif self.mode == MODE_RUNNING:
            self.stop_spectroscopy_experiment()

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
                options=QFileDialog.Option.DontUseNativeDialog
            )
            if file_name:
                self.reference_file = file_name

    def on_save_reference(self):
        if self.tab_selected == "tab_spectroscopy":

            print("TODO: CHECK id OF COMBO!")

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
                options=QFileDialog.Option.DontUseNativeDialog
            )
            if file_name:
                if not file_name.endswith('.reference.json'):
                    file_name += '.reference.json'
                try:
                    with open(reference_file, "r") as f:
                        with open(file_name, "w") as f2:
                            f2.write(f.read())
                except:
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Error saving reference file",
                                QMessageBox.StandardButton.Ok).exec()

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
            self.on_harmonic_change(1)
            self.on_tau_change(0.0)
            self.control_inputs["tau"].setValue(0.0)
            self.control_inputs[SETTINGS_HARMONIC].setValue(1)
        else:
            self.control_inputs["tau_label"].hide()
            self.control_inputs["tau"].hide()
            self.control_inputs[SETTINGS_HARMONIC].hide()
            self.control_inputs[SETTINGS_HARMONIC_LABEL].hide()

    def on_export_data_changed(self, state):
        self.settings.setValue(SETTINGS_WRITE_DATA, state)
        self.bin_file_size_label.show() if state else self.bin_file_size_label.hide()
        self.calc_exported_file_size() if state else None

    def create_channel_selector(self):
        grid = QHBoxLayout()
        grid.addSpacing(20)
        for i in range(MAX_CHANNELS):
            from components.fancy_checkbox import FancyCheckbox
            fancy_checkbox = FancyCheckbox(text=f"Channel {i + 1}")
            if self.selected_channels:
                fancy_checkbox.set_checked(i in self.selected_channels)
            fancy_checkbox.toggled.connect(lambda checked, channel=i: self.on_channel_selected(checked, channel))
            grid.addWidget(fancy_checkbox)
            self.channel_checkboxes.append(fancy_checkbox)
        grid.addSpacing(20)
        return grid

    def controls_set_enabled(self, enabled: bool):
        for key in self.control_inputs:
            if key != "start_button":
                self.control_inputs[key].setEnabled(enabled)
        if enabled:
            self.control_inputs[SETTINGS_ACQUISITION_TIME].setEnabled(not self.get_free_running_state())

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
        if checked:
            if channel not in self.selected_channels:
                self.selected_channels.append(channel)
        else:
            if channel in self.selected_channels:
                self.selected_channels.remove(channel)
        self.selected_channels.sort()
        self.set_selected_channels_to_settings()
        self.clear_plots()
        self.generate_plots()
        self.calc_exported_file_size()

    def on_sync_selected(self, sync: str):
        if self.selected_sync == sync and sync == 'sync_in':
            self.start_sync_in_dialog()
            return
        self.selected_sync = sync
        self.settings.setValue(SETTINGS_SYNC, sync)

    def start_sync_in_dialog(self):
        dialog = SyncInDialog()
        dialog.exec()
        if dialog.frequency_mhz != 0.0:
            self.sync_in_frequency_mhz = dialog.frequency_mhz
            self.settings.setValue(SETTINGS_SYNC_IN_FREQUENCY_MHZ, self.sync_in_frequency_mhz)
            self.update_sync_in_button()

    def update_sync_in_button(self):
        if self.sync_in_frequency_mhz == 0.0:
            self.sync_buttons[0][0].setText("Sync In (not detected)")
        else:
            self.sync_buttons[0][0].setText(f"Sync In ({self.sync_in_frequency_mhz} MHz)")

    def create_sync_buttons(self):
        buttons_layout = QHBoxLayout()

        sync_in_button = FancyButton("Sync In")
        buttons_layout.addWidget(sync_in_button)
        self.sync_buttons.append((sync_in_button, 'sync_in'))
        self.update_sync_in_button()

        sync_out_80_button = FancyButton("Sync Out (80MHz)")
        buttons_layout.addWidget(sync_out_80_button)
        self.sync_buttons.append((sync_out_80_button, 'sync_out_80'))

        sync_out_40_button = FancyButton("Sync Out (40MHz)")
        buttons_layout.addWidget(sync_out_40_button)
        self.sync_buttons.append((sync_out_40_button, 'sync_out_40'))

        sync_out_20_button = FancyButton("Sync Out (20MHz)")
        buttons_layout.addWidget(sync_out_20_button)
        self.sync_buttons.append((sync_out_20_button, 'sync_out_20'))

        sync_out_10_button = FancyButton("Sync Out (10MHz)")
        buttons_layout.addWidget(sync_out_10_button)
        self.sync_buttons.append((sync_out_10_button, 'sync_out_10'))

        for button, name in self.sync_buttons:
            def on_toggle(toggled_name):
                for b, n in self.sync_buttons:
                    b.set_selected(n == toggled_name)
                self.on_sync_selected(toggled_name)

            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(self.selected_sync == name)

        return buttons_layout

    def generate_plots(self, frequency_mhz=0.0):
        if len(self.selected_channels) == 0:
            self.grid_layout.addWidget(QWidget(), 0, 0)
            return

        for i in range(len(self.selected_channels)):
            channel_index = i
            v_layout = QVBoxLayout()

            if self.tab_selected != "tab_data":

                intensity_widget = pg.PlotWidget()
                intensity_widget.setLabel('left', 'AVG. Photon counts', units='')
                intensity_widget.setLabel('bottom', 'Time', units='s')
                intensity_widget.setTitle(f'Channel {self.selected_channels[i] + 1} intensity')

                # remove margins
                intensity_widget.plotItem.setContentsMargins(0, 0, 0, 0)

                x = np.arange(1)
                y = x * 0
                intensity_plot = intensity_widget.plot(x, y, pen='#23F3AB')
                self.intensity_lines.append(intensity_plot)

                v_layout.addWidget(intensity_widget, 1)

                curve_widget = pg.PlotWidget()
                curve_widget.setLabel('left', 'Photon counts', units='')
                curve_widget.setLabel('bottom', 'Time', units='ns')
                curve_widget.setTitle(f'Channel {self.selected_channels[i] + 1} decay')

                if frequency_mhz != 0.0:
                    period = 1_000 / frequency_mhz
                    x = np.linspace(0, period, 256)
                else:
                    x = np.arange(1)

                y = x * 0
                static_curve = curve_widget.plot(x, y, pen='r')
                self.decay_curves.append(static_curve)
                v_layout.addWidget(curve_widget, 4)
            else:
                h_layout = QHBoxLayout()
                label = QLabel("No CPS")
                label.setStyleSheet(
                    "QLabel { color : #FFA726; font-size: 65px; weight: bold; background-color: #000000; padding: 8px; }")
                # label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                self.cps_widgets.append(label)
                self.cps_counts.append({"last_time_ns": 0, "last_count": 0, "current_count": 0})

                curve_widget = pg.PlotWidget()
                curve_widget.setLabel('left', 'Photon counts', units='')
                curve_widget.setLabel('bottom', 'Time', units='ns')
                curve_widget.setTitle(f'Channel {self.selected_channels[i] + 1} decay')

                if frequency_mhz != 0.0:
                    period = 1_000 / frequency_mhz
                    x = np.linspace(0, period, 256)
                else:
                    x = np.arange(1)

                y = x * 0
                static_curve = curve_widget.plot(x, y, pen='r')
                self.decay_curves.append(static_curve)
                h_layout.addWidget(label, stretch=1)
                h_layout.addWidget(curve_widget, stretch=1)
                v_layout.addLayout(h_layout, 1)

                # add a phasors chart
                phasors_widget = pg.PlotWidget()

                # mantain aspect ratio
                phasors_widget.setAspectLocked(True)
                phasors_widget.setLabel('left', 's', units='')
                phasors_widget.setLabel('bottom', 'g', units='')
                phasors_widget.setTitle(f'Channel {self.selected_channels[i] + 1} phasors')
                phasors_widget.setCursor(Qt.CursorShape.BlankCursor)
                self.draw_semi_circle(phasors_widget)

                self.phasors_charts.append(
                    phasors_widget.plot([], [], pen=None, symbol='o', symbolPen=None, symbolSize=1,
                                        symbolBrush='#23F3AB'))

                self.phasors_widgets.append(phasors_widget)

                v_layout.addWidget(phasors_widget, 4)

                self.generate_coords(i)

                # create crosshair for phasors (a circle)
                crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(35, 243, 171))
                font = QFont()
                font.setPixelSize(25)
                crosshair.setFont(font)
                phasors_widget.addItem(crosshair, ignoreBounds=True)
                self.phasors_crosshairs.append(crosshair)

            col_length = 1
            if len(self.selected_channels) == 2:
                col_length = 2
            elif len(self.selected_channels) == 3:
                col_length = 3
            if len(self.selected_channels) > 3:
                col_length = 2
            self.grid_layout.addLayout(v_layout, i // col_length, i % col_length)

    def generate_coords(self, channel_index):
        font = QFont()
        font.setPixelSize(25)
        coord_text = pg.TextItem("", anchor=(0.5, 1))
        coord_text.setFont(font)

        crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(35, 243, 171))
        font = QFont()
        font.setPixelSize(25)
        crosshair.setFont(font)
        is_in_array = len(self.phasors_crosshairs) > channel_index
        if not is_in_array:
            self.phasors_crosshairs.append(crosshair)
        else:
            self.phasors_crosshairs[channel_index] = crosshair

        is_in_array = len(self.phasors_coords) > channel_index
        if not is_in_array:
            self.phasors_widgets[channel_index].sceneObj.sigMouseMoved.connect(
                lambda event, ccc=channel_index: self.on_phasors_mouse_moved(event, ccc)
            )
            self.phasors_coords.append(coord_text)
        else:
            self.phasors_coords[channel_index] = coord_text
        self.phasors_widgets[channel_index].addItem(coord_text, ignoreBounds=True)
        self.phasors_widgets[channel_index].addItem(crosshair, ignoreBounds=True)

    def on_phasors_mouse_moved(self, event, channel_index):
        for i in range(len(self.phasors_coords)):
            if i != channel_index:
                self.phasors_coords[i].setText("")
                self.phasors_crosshairs[i].setText("")

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

        tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (s / g) * 1e3

        tau_m_component = (1 / (s ** 2 + g ** 2)) - 1
        if tau_m_component < 0:
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} μs")
        else:
            tau_m = (1 / (2 * np.pi * freq_mhz * harmonic)) * np.sqrt(tau_m_component) * 1e3
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} μs; 𝜏m={round(tau_m, 2)} μs")

    def draw_semi_circle(self, widget):
        x = np.linspace(0, 1, 1000)
        y = np.sqrt(0.5 ** 2 - (x - 0.5) ** 2)
        widget.plot(x, y, pen='#23F3AB')
        widget.plot([-0.1, 1.1], [0, 0], pen='#23F3AB')

    def get_selected_channels_from_settings(self):
        self.selected_channels = []
        for i in range(MAX_CHANNELS):
            if self.settings.value(f"channel_{i}", 'false') == 'true':
                self.selected_channels.append(i)

    def set_selected_channels_to_settings(self):
        for i in range(MAX_CHANNELS):
            self.settings.setValue(f"channel_{i}", 'false')
            if i in self.selected_channels:
                self.settings.setValue(f"channel_{i}", 'true')

    def stop_plots(self):
        self.timer_update.stop()

    def clear_plots(self):
        for curve in self.intensity_lines:
            curve.clear()
        for curve in self.decay_curves:
            curve.clear()
        for phasor in self.phasors_charts:
            phasor.clear()
        self.phasors_charts.clear()
        self.phasors_widgets.clear()
        self.phasors_coords.clear()
        self.cps_widgets.clear()
        self.cps_counts.clear()
        self.intensity_lines.clear()
        self.decay_curves.clear()
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
        acquisition_time = self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)
        bin_width = self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)

        if free_running is True or acquisition_time is None:
            file_size_MB = len(self.selected_channels) * (1000 / int(bin_width))
            self.bin_file_size = format_size(file_size_MB * 1024 * 1024)
            self.bin_file_size_label.setText("File size: " + str(self.bin_file_size) + "/s")
        else:
            file_size_MB = int(acquisition_time) * len(self.selected_channels) * (1000 / int(bin_width))
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
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if file_name:
            if not file_name.endswith('.bin'):
                file_name += '.bin'
            try:
                flim_labs.export_data(file_name)
            except Exception as e:
                QMessageBox(QMessageBox.Icon.Warning, "Error", "Error exporting data: " + str(e),
                            QMessageBox.StandardButton.Ok).exec()

    def begin_spectroscopy_experiment(self):
        if self.selected_sync == "sync_in":
            frequency_mhz = self.sync_in_frequency_mhz
        else:
            frequency_mhz = int(self.selected_sync.split("_")[-1])
        if frequency_mhz == 0.0:
            QMessageBox(QMessageBox.Icon.Warning, "Error", "Frequency not detected",
                        QMessageBox.StandardButton.Ok).exec()
            return

        self.clear_plots()
        self.generate_plots(frequency_mhz)

        if len(self.selected_channels) == 0:
            QMessageBox(QMessageBox.Icon.Warning, "Error", "No channels selected",
                        QMessageBox.StandardButton.Ok).exec()
            return

        acquisition_time_millis = None if self.get_free_running_state() else int(
            self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)) * 1000
        bin_width_micros = int(self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH))

        connection_type = self.control_inputs["channel_type"].currentText()

        if str(connection_type) == "USB":
            connection_type = "USB"
        else:
            connection_type = "SMA"

        firmware_selected = flim_labs.get_spectroscopy_firmware(
            sync="in" if self.selected_sync == "sync_in" else "out",
            frequency_mhz=frequency_mhz,
            channel=connection_type.lower(),
            sync_connection="sma"
        )

        print(f"Firmware selected: {firmware_selected}")
        print(f"Connection type: {connection_type}")
        print(f"Frequency: {frequency_mhz} Mhz")
        print(f"Selected channels: {self.selected_channels}")
        print(f"Acquisition time: {acquisition_time_millis} ms")
        print(f"Bin width: {bin_width_micros} µs")
        print(f"Free running: {self.get_free_running_state()}")
        print(f"Tau: {self.settings.value(SETTINGS_TAU_NS, '0')} ns")
        print(f"Tau: {self.settings.value(SETTINGS_TAU_NS, '0')} ns")
        print(f"Reference file: {self.reference_file}")

        self.cached_time_span_seconds = float(self.settings.value(SETTINGS_TIME_SPAN, DEFAULT_TIME_SPAN))

        if self.tab_selected == "tab_data":
            if not self.reference_file:
                QMessageBox(QMessageBox.Icon.Warning, "Error", "No reference file selected",
                            QMessageBox.StandardButton.Ok).exec()
                return

            # load reference file (is a json)
            # example: {
            #   "bin_width_micros": 1000,
            #   "calibrations": [
            #     [
            #       -1.652415386892391,
            #       1.0223231306721805
            #     ],
            #     [
            #       -1.9086511584591719,
            #       1.0557978525373855
            #     ]
            #   ],
            #   "channels": [1,3],
            #   "curves": [
            #     [ ... 256 intensities ... ],
            #     [ ... 256 intensities ... ]
            #   ],
            #   "laser_period_ns": 25.0,
            #   "tau_ns": 2.0
            # }
            with open(self.reference_file, "r") as f:
                reference_data = json.load(f)
                if "channels" not in reference_data:
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Invalid reference file (missing channels)",
                                QMessageBox.StandardButton.Ok).exec()
                    return
                elif len(reference_data["channels"]) != len(self.selected_channels):
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Invalid reference file (channels mismatch)",
                                QMessageBox.StandardButton.Ok).exec()
                    return
                if "curves" not in reference_data:
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Invalid reference file (missing curves)",
                                QMessageBox.StandardButton.Ok).exec()
                    return
                elif len(reference_data["curves"]) != len(self.selected_channels):
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Invalid reference file (curves mismatch)",
                                QMessageBox.StandardButton.Ok).exec()
                    return
                if "laser_period_ns" not in reference_data:
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Invalid reference file (missing laser period)",
                                QMessageBox.StandardButton.Ok).exec()
                    return
                if "tau_ns" not in reference_data:
                    QMessageBox(QMessageBox.Icon.Warning, "Error", "Invalid reference file (missing tau)",
                                QMessageBox.StandardButton.Ok).exec()
                    return

        try:
            # set tau_ns if selected tab is reference
            tau_ns = float(self.settings.value(SETTINGS_TAU_NS, "0")) if self.is_reference_phasors() else None

            reference_file = None if self.tab_selected != "tab_data" else self.reference_file

            flim_labs.start_spectroscopy(
                enabled_channels=self.selected_channels,
                bin_width_micros=bin_width_micros,
                frequency_mhz=frequency_mhz,
                firmware_file=firmware_selected,
                acquisition_time_millis=acquisition_time_millis,
                tau_ns=tau_ns,
                reference_file=reference_file
            )
        except Exception as e:
            QMessageBox(QMessageBox.Icon.Warning, "Error", "Error starting spectroscopy: " + str(e),
                        QMessageBox.StandardButton.Ok).exec()
            return
        self.mode = MODE_RUNNING
        self.style_start_button()
        QApplication.processEvents()
        self.update_plots_enabled = True
        self.top_bar_set_enabled(False)
        # self.timer_update.start(18)
        self.pull_from_queue_timer.start(25)
        # self.pull_from_queue()

    def pull_from_queue(self):
        val = flim_labs.pull_from_queue()
        if len(val) > 0:
            for v in val:
                if v == ('end',):  # End of acquisition
                    print("Got end of acquisition, stopping")
                    self.stop_spectroscopy_experiment()
                    self.style_start_button()
                    self.control_inputs["save"].setHidden(True)
                    QApplication.processEvents()

                    if self.is_reference_phasors():
                        # read reference file from .pid file
                        with open(".pid", "r") as f:
                            lines = f.readlines()
                            reference_file = lines[0].split("=")[1]
                        self.reference_file = reference_file
                        self.control_inputs["save"].setHidden(False)
                        print(f"Last reference file: {reference_file}")

                        break

                    if self.is_phasors():
                        self.quantize_phasors()
                        self.add_harmonic_selector(int(self.settings.value(SETTINGS_HARMONIC, "1")))
                        break

                    break

                if 'sp_phasors' in v[0]:
                    channel = v[1][0]
                    harmonic = v[1][0]
                    phasors = v[3]
                    self.draw_points_in_phasors(channel, harmonic, phasors)
                    continue

                try:
                    ((channel,), (time_ns,), intensities) = v
                except:
                    print(v)
                ((channel,), (time_ns,), intensities) = v
                channel_index = self.selected_channels.index(channel)
                # self.decay_curves_queue.put((channel_index, time_ns, intensities))

                self.update_plots2(channel_index, time_ns, intensities)
                self.update_cps(channel_index, time_ns, intensities)
                QApplication.processEvents()
        # QTimer.singleShot(1, self.pull_from_queue)

    def draw_points_in_phasors(self, channel, harmonic, phasors):
        channel_index = self.selected_channels.index(channel)
        x, y = self.phasors_charts[channel_index].getData()
        if x is None:
            x = np.array([])
            y = np.array([])

        new_x = [p[0] for p in phasors]
        new_y = [p[1] for p in phasors]

        x = np.concatenate((x, new_x))
        y = np.concatenate((y, new_y))

        self.phasors_charts[channel_index].setData(x, y)
        pass

    def quantize_phasors(self):
        # create an 2d histogram of the phasors on the unit circle splitting the circle in 256 bins
        # the histogram will be normalized to the maximum value
        # the histogram will be quantized to 256 bins
        # for every channel:
        bins = 64
        for selected_channel in self.selected_channels:
            channel_index = self.selected_channels.index(selected_channel)
            x, y = self.phasors_charts[channel_index].getData()
            if x is None:
                continue
            # Create a 2D histogram on x, y with 256 bins

            h, xedges, yedges = np.histogram2d(x, y, bins=bins * 4, range=[[-2, 2], [-2, 2]])

            nonZeroH = h[h > 0]
            hMin = np.min(nonZeroH)
            hMax = np.max(h)

            print(f"Min: {hMin}, Max: {hMax}")

            h = h / np.max(h)
            h[h == 0] = np.nan
            # Applying a colormap and setting image with half opacity
            image_item = pg.ImageItem()
            image_item.setImage(h, levels=(0, 1))
            image_item.setLookupTable(self.create_cool_colormap().getLookupTable(0, 1.0))
            image_item.setOpacity(1)
            image_item.resetTransform()
            # no change on chart
            image_item.setScale(1 / bins)
            image_item.setPos(-2, -2)
            self.phasors_widgets[channel_index].clear()
            self.phasors_widgets[channel_index].addItem(image_item, ignoreBounds=True)
            self.draw_semi_circle(self.phasors_widgets[channel_index])
            self.generate_coords(channel_index)
            self.generate_colorbar(channel_index, hMin, hMax)

    def generate_colorbar(self, channel_index, min_value, max_value):
        # Create a colorbar
        colorbar = pg.GradientLegend((10, 100), (10, 100))
        colorbar.setColorMap(self.create_cool_colormap(min_value, max_value))
        colorbar.setLabels({'min': min_value, 'max': max_value})
        self.phasors_widgets[channel_index].addItem(colorbar)

    def add_harmonic_selector(self, harmonics):
        if harmonics > 1:
            self.control_inputs[HARMONIC_SELECTOR].show()
            self.control_inputs[HARMONIC_SELECTOR_LABEL].show()
            self.control_inputs[HARMONIC_SELECTOR].setMaximum(harmonics)
            self.control_inputs[HARMONIC_SELECTOR].setValue(1)
            self.harmonic_selector_value = 1

    def hide_harmonic_selector(self):
        self.control_inputs[HARMONIC_SELECTOR].hide()
        self.control_inputs[HARMONIC_SELECTOR_LABEL].hide()

    def create_hot_colormap(self):
        # Create the color stops from black to red to yellow to white
        pos = np.array([0.0, 0.33, 0.67, 1.0])
        color = np.array([
            [0, 0, 0, 255],  # Black
            [255, 0, 0, 255],  # Red
            [255, 255, 0, 255],  # Yellow
            [255, 255, 255, 255]  # White
        ], dtype=np.ubyte)
        cmap = pg.ColorMap(pos, color)
        return cmap

    def create_cool_colormap(self, start=0.0, end=1.0):
        # Define the color stops from cyan to magenta
        pos = np.array([start, end])
        color = np.array([
            [0, 255, 255, 255],  # Cyan
            [255, 0, 255, 255]  # Magenta
        ], dtype=np.float32)
        cmap = pg.ColorMap(pos, color)
        return cmap

    def is_reference_phasors(self):
        selected_calibration = self.settings.value(SETTINGS_CALIBRATION_TYPE, DEFAULT_SETTINGS_CALIBRATION_TYPE)
        return self.tab_selected == "tab_spectroscopy" and selected_calibration == 1

    def is_phasors(self):
        return self.tab_selected == "tab_data"

    def update_cps(self, channel_index, time_ns, curve):

        # check if there is channel_index'th element in cps_counts
        if len(self.cps_counts) <= channel_index:
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
            cps_value = (cps["current_count"] - cps["last_count"]) / (time_elapsed / 1_000_000_000)
            self.cps_widgets[channel_index].setText(f"{self.humanize_number(cps_value)} CPS")
            cps["last_time_ns"] = time_ns
            cps["last_count"] = cps["current_count"]

    def humanize_number(self, number):
        if number == 0:
            return '0'
        units = ['', 'K', 'M', 'G', 'T', 'P']
        k = 1000.0
        magnitude = int(floor(log(number, k)))
        return '%.2f%s' % (number / k ** magnitude, units[magnitude])

    def update_plots2(self, channel_index, time_ns, curve):
        intensity_line = self.intensity_lines[channel_index] if channel_index < len(self.intensity_lines) else None
        if intensity_line is not None:
            x, y = intensity_line.getData()
            if x is None or (len(x) == 1 and x[0] == 0):
                x = np.array([time_ns / 1_000_000_000])
                y = np.array([np.sum(curve)])
            else:
                x = np.append(x, time_ns / 1_000_000_000)
                y = np.append(y, np.sum(curve))

            # trim the data based on self.cached_time_span_seconds

            if len(x) > 2:
                while x[-1] - x[0] > self.cached_time_span_seconds:
                    x = x[1:]
                    y = y[1:]

            intensity_line.setData(x, y)

        decay_curve = self.decay_curves[channel_index] if channel_index < len(self.decay_curves) else None
        if decay_curve is not None:
            x, y = decay_curve.getData()
            decay_curve.setData(x, curve + y)
        QApplication.processEvents()
        time.sleep(0.01)

    def on_harmonic_selector_change(self, value):
        self.harmonic_selector_value = value
        print(f"Harmonic selected: {value}")

    def update_plots(self):
        try:
            (channel_index, time_ns, curve) = self.decay_curves_queue.get(block=True, timeout=0.1)
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
        self.top_bar_set_enabled(True)


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
            "will be interrupted automatically.")
        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)
        QApplication.processEvents()
        try:
            res = flim_labs.detect_laser_frequency()
            if res is None or res == 0.0:
                self.frequency_mhz = 0.0
                self.label.setText("Frequency not detected. Please check the connection and try again.")
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
    window.show()
    app.exec()
    window.pull_from_queue_timer.stop()
    sys.exit()
