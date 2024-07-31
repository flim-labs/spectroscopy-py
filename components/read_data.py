from functools import partial
import json
import os
import re
import struct
import numpy as np
from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
from components.input_text_control import InputTextControl
from components.layout_utilities import clear_layout
from components.resource_path import resource_path
from settings import *
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QApplication,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QGridLayout,
    QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor, QIcon
from components.logo_utilities import TitlebarIcon

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ReadData:
    @staticmethod
    def read_bin_data(window, app, tab_selected, file_type):
        active_tab = ReadData.get_data_type(tab_selected)
        if file_type == "spectroscopy":
            result = ReadData.read_bin(
                window, app, b"SP01", "Spectroscopy", ReadData.read_spectroscopy_data
            )
            if result:
                file_name, file_type, times, channels_curves, metadata = result
                app.reader_data[active_tab]["plots"] = []
                app.reader_data[active_tab]["data"]["times"] = times
                app.reader_data[active_tab]["data"]["channels_curves"] = channels_curves
                app.reader_data[active_tab]["metadata"] = metadata
                app.reader_data[active_tab]["files"][file_type] = file_name

    @staticmethod
    def get_data_type(active_tab):
        if active_tab == TAB_SPECTROSCOPY:
            return "spectroscopy"
        elif active_tab == TAB_PHASORS:
            return "phasors"
        else:
            return "fitting"

    @staticmethod
    def plot_spectroscopy_data(app, times, channels_curves, laser_period_ns):
        num_bins = 256
        x = np.linspace(0, laser_period_ns, num_bins)
        x_values = x / 1_000
        for channel, curves in channels_curves.items():
            if channel in app.plots_to_show:
                y_values = np.sum(curves, axis=0)
                app.cached_decay_values[channel] = y_values
                app.update_plots2(channel, x_values, y_values, reader_mode=True)

    @staticmethod
    def read_bin(window, app, magic_bytes, file_type, read_data_cb):
        try:
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setNameFilter("Bin files (*.bin)")
            file_name, _ = dialog.getOpenFileName(
                window,
                f"Load {file_type} file",
                "",
                "Bin files (*.bin)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not file_name:
                return
            if not (file_name.endswith(".bin")):
                BoxMessage.setup(
                    "Invalid extension",
                    "Invalid extension. File should be a .bin",
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )
                return None

            with open(file_name, "rb") as f:
                if f.read(4) != magic_bytes:
                    BoxMessage.setup(
                        "Invalid file",
                        f"Invalid file. The file is not a valid {file_type} file.",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return None
                return read_data_cb(f, file_name)

        except Exception as e:
            BoxMessage.setup(
                "Error reading file",
                "Error reading .bin file",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return None

    @staticmethod
    def read_spectroscopy_data(file, file_name):
        try:
            (json_length,) = struct.unpack("I", file.read(4))
            json_data = file.read(json_length).decode("utf-8")
            metadata = json.loads(json_data)
            channel_curves = {
                channel: [] for channel in range(len(metadata["channels"]))
            }
            times = []
            number_of_channels = len(metadata["channels"])
            channel_values_unpack_string = "I" * 256
            while True:
                data = file.read(8)
                if not data:
                    break
                (time,) = struct.unpack("d", data)
                times.append(time / 1_000_000_000)

                for i in range(number_of_channels):
                    data = file.read(4 * 256)
                    if len(data) < 4 * 256:
                        return times, channel_curves
                    curve = struct.unpack(channel_values_unpack_string, data)
                    channel_curves[i].append(np.array(curve))
            file_type = "spectroscopy"
            return file_name, file_type, times, channel_curves, metadata
        except Exception as e:
            print(f"Error reading spectroscopy data: {e}")
            BoxMessage.setup(
                "Error reading file",
                "Error reading Spectroscopy file",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return None


class ReadDataControls:
    @staticmethod
    def handle_widgets_visibility(app, read_mode):
        app.control_inputs["start_button"].setVisible(not read_mode)
        app.control_inputs["read_bin_button"].setVisible(read_mode)
        app.widgets[TOP_COLLAPSIBLE_WIDGET].setVisible(not read_mode)
        app.widgets["collapse_button"].setVisible(not read_mode)
        app.control_inputs[SETTINGS_BIN_WIDTH].setEnabled(not read_mode)
        app.control_inputs[SETTINGS_ACQUISITION_TIME].setEnabled(not read_mode)
        app.control_inputs[SETTINGS_FREE_RUNNING].setEnabled(not read_mode)
        app.control_inputs[SETTINGS_CALIBRATION_TYPE].setEnabled(not read_mode)
        app.control_inputs["tau"].setEnabled(not read_mode)
        app.control_inputs[SETTINGS_TIME_SPAN].setEnabled(not read_mode)
        app.control_inputs[SETTINGS_HARMONIC].setEnabled(not read_mode)
        if app.tab_selected == TAB_PHASORS:
            app.control_inputs[LOAD_REF_BTN].setVisible(not read_mode)

    @staticmethod
    def handle_plots_config(app, file_type):
        file_metadata = app.reader_data[file_type]["metadata"]
        if "channels" in file_metadata and file_metadata["channels"] is not None:
            selected_channel = file_metadata["channels"]
            selected_channel.sort()
            app.selected_channels = selected_channel
            app.plots_to_show = app.reader_data[file_type]["plots"]


class ReaderPopup(QWidget):
    def __init__(self, window, tab_selected):
        super().__init__()
        self.app = window
        self.tab_selected = tab_selected
        self.widgets = {}
        self.layouts = {}
        self.channels_checkboxes = []
        self.data_type = ReadData.get_data_type(self.tab_selected)
        self.setWindowTitle("Read data")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # PLOT BUTTON ROW
        plot_btn_row = self.create_plot_btn_layout()
        # LOAD FILE ROW
        load_file_row = self.init_file_load_ui()
        self.layout.addSpacing(10)
        self.layout.insertLayout(1, load_file_row)
        # LOAD CHANNELS GRID
        self.layout.addSpacing(20)
        channels_layout = self.init_channels_layout()
        if channels_layout is not None:
            self.layout.insertLayout(2, channels_layout)

        self.layout.addSpacing(20)
        self.layout.insertLayout(3, plot_btn_row)
        self.setLayout(self.layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.app.widgets[READER_POPUP] = self
        self.center_window()

    def init_file_load_ui(self):
        v_box = QVBoxLayout()
        files = self.app.reader_data[self.data_type]["files"]
        for file_type, file_path in files.items():
            if file_type == "phasors" and self.data_type == "phasors":
                input_desc = QLabel(f"LOAD RELATED {file_type.upper()} FILE:")
            else:
                input_desc = QLabel(f"LOAD A {file_type.upper()} FILE:")
            input_desc.setStyleSheet("font-size: 16px")
            control_row = QHBoxLayout()
            _, input = InputTextControl.setup(
                label="",
                placeholder="Load .bin file",
                event_callback=lambda text: self.on_loaded_file_change(text, file_type),
                text=file_path,
            )
            input.setStyleSheet(GUIStyles.set_input_text_style())
            widget_key = f"load_{file_type}_input"
            self.widgets[widget_key] = input
            load_file_btn = QPushButton()
            load_file_btn.setIcon(QIcon(resource_path("assets/folder-white.png")))
            load_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            GUIStyles.set_start_btn_style(load_file_btn)
            load_file_btn.setFixedHeight(36)
            load_file_btn.clicked.connect(
                partial(self.on_load_file_btn_clicked, file_type)
            )
            control_row.addWidget(input)
            control_row.addWidget(load_file_btn)
            v_box.addWidget(input_desc)
            v_box.addSpacing(10)
            v_box.addLayout(control_row)
            v_box.addSpacing(10)
        return v_box

    def init_channels_layout(self):
        self.channels_checkboxes.clear()
        file_metadata = self.app.reader_data[self.data_type]["metadata"]
        plots_to_show = self.app.reader_data[self.data_type]["plots"]
        if "channels" in file_metadata and file_metadata["channels"] is not None:
            selected_channels = file_metadata["channels"]
            selected_channels.sort()
            self.app.selected_channels = selected_channels
            for i, ch in enumerate(self.app.channel_checkboxes):
                ch.set_checked(i in self.app.selected_channels)
            self.app.set_selected_channels_to_settings()
            if len(plots_to_show) == 0:
                plots_to_show = selected_channels[:4]
            self.app.plots_to_show = plots_to_show
            self.app.settings.setValue(
                SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
            )
            self.app.clear_plots()
            self.app.generate_plots()
            self.app.toggle_intensities_widgets_visibility()
            channels_layout = QVBoxLayout()
            desc = QLabel("CHOOSE MAX 4 PLOTS TO DISPLAY:")
            desc.setStyleSheet("font-size: 16px")
            grid = QGridLayout()
            for ch in selected_channels:
                checkbox, checkbox_wrapper = self.set_checkboxes(f"Channel {ch + 1}")
                isChecked = ch in plots_to_show
                checkbox.setChecked(isChecked)
                if len(plots_to_show) >= 4 and ch not in plots_to_show:
                    checkbox.setEnabled(False)
                grid.addWidget(checkbox_wrapper)
            channels_layout.addWidget(desc)
            channels_layout.addSpacing(10)
            channels_layout.addLayout(grid)
            self.layouts["ch_layout"] = channels_layout
            return channels_layout
        else:
            return None

    def create_plot_btn_layout(self):
        row_btn = QHBoxLayout()
        plot_btn = QPushButton("PLOT DATA")
        plot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plot_btn.setObjectName("btn")
        GUIStyles.set_stop_btn_style(plot_btn)
        plot_btn.setFixedHeight(40)
        plot_btn.setFixedWidth(200)
        plots_to_show = self.app.reader_data[self.data_type]["plots"]
        plot_btn.setEnabled(len(plots_to_show) > 0)
        plot_btn.clicked.connect(self.on_plot_data_btn_clicked)
        self.widgets["plot_btn"] = plot_btn
        row_btn.addStretch(1)
        row_btn.addWidget(plot_btn)
        return row_btn

    def remove_channels_grid(self):
        if "ch_layout" in self.layouts:
            clear_layout(self.layouts["ch_layout"])
            del self.layouts["ch_layout"]

    def set_checkboxes(self, text):
        checkbox_wrapper = QWidget()
        checkbox_wrapper.setObjectName(f"simple_checkbox_wrapper")
        row = QHBoxLayout()
        checkbox = QCheckBox(text)
        checkbox.setStyleSheet(
            GUIStyles.set_simple_checkbox_style(color=PALETTE_BLUE_1)
        )
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(
            lambda state, checkbox=checkbox: self.on_channel_toggled(state, checkbox)
        )
        row.addWidget(checkbox)
        checkbox_wrapper.setLayout(row)
        checkbox_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
        return checkbox, checkbox_wrapper

    def on_channel_toggled(self, state, checkbox):
        label_text = checkbox.text()
        ch_index = self.extract_channel_from_label(label_text)
        if state:
            if ch_index not in self.app.plots_to_show:
                self.app.plots_to_show.append(ch_index)
        else:
            if ch_index in self.app.plots_to_show:
                self.app.plots_to_show.remove(ch_index)
        self.app.plots_to_show.sort()
        self.app.settings.setValue(
            SETTINGS_PLOTS_TO_SHOW, json.dumps(self.app.plots_to_show)
        )
        self.app.reader_data[self.data_type]["plots"] = self.app.plots_to_show
        if len(self.app.plots_to_show) >= 4:
            for checkbox in self.channels_checkboxes:
                if checkbox.text() != label_text and not checkbox.isChecked():
                    checkbox.setEnabled(False)
        else:
            for checkbox in self.channels_checkboxes:
                checkbox.setEnabled(True)
        if "plot_btn" in self.widgets:
            plot_btn_enabled = len(self.app.plots_to_show) > 0
            self.widgets["plot_btn"].setEnabled(plot_btn_enabled)
        self.app.clear_plots()
        self.app.cached_decay_values.clear()
        self.app.generate_plots()
        self.app.toggle_intensities_widgets_visibility()

    def on_loaded_file_change(self, text, file_type):
        self.app.reader_data[self.data_type]["files"][file_type] = text

    def on_load_file_btn_clicked(self, file_type):
        ReadData.read_bin_data(self, self.app, self.tab_selected, file_type)
        file_name = self.app.reader_data[self.data_type]["files"][file_type]
        if len(file_name) > 0:
            widget_key = f"load_{file_type}_input"
            self.widgets[widget_key].setText(file_name)
            self.remove_channels_grid()
            channels_layout = self.init_channels_layout()
            if channels_layout is not None:
                self.layout.insertLayout(2, channels_layout)

    def on_plot_data_btn_clicked(self):
        data = self.app.reader_data[self.data_type]["data"]
        metadata = self.app.reader_data[self.data_type]["metadata"]
        laser_period_ns = (
            metadata["laser_period_ns"]
            if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
            else 25
        )
        if "times" in data and "channels_curves" in data:
            ReadData.plot_spectroscopy_data(self.app, data["times"], data["channels_curves"], laser_period_ns)
            self.close()
 

    def center_window(self):
        self.setMinimumWidth(500)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())

    def extract_channel_from_label(self, text):
        ch = re.search(r"\d+", text).group()
        ch_num = int(ch)
        ch_num_index = ch_num - 1
        return ch_num_index


class ReaderMetadataPopup(QWidget):
    def __init__(self, window, tab_selected):
        super().__init__()
        self.app = window
        self.setWindowTitle("File metadata")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.app.widgets[READER_METADATA_POPUP] = self
