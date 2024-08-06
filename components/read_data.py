from functools import partial
import json
import os
import re
import struct
import numpy as np
from components.box_message import BoxMessage
from components.file_utils import FileUtils
from components.gui_styles import GUIStyles
from components.helpers import ns_to_mhz
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
    QScrollArea
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
        file_info = {
            "spectroscopy": (b"SP01", "Spectroscopy", ReadData.read_spectroscopy_data),
            "phasors": (b"SPF1", "Phasors", ReadData.read_phasors_data),
        }
        if file_type not in file_info:
            return
        result = ReadData.read_bin(window, app, *file_info[file_type], active_tab)
        if not result:
            return
        file_name, file_type, *data, metadata = result
        app.reader_data[active_tab]["plots"] = []
        app.reader_data[active_tab]["metadata"] = metadata
        app.reader_data[active_tab]["files"][file_type] = file_name
        if file_type == "spectroscopy":
            times, channels_curves = data
            app.reader_data[active_tab]["data"] = {
                "times": times,
                "channels_curves": channels_curves,
            }
            if active_tab == "phasors":
                app.reader_data[active_tab]["spectroscopy_metadata"] = metadata
                app.reader_data[active_tab]["data"]["spectroscopy_data"] = {
                    "times": times,
                    "channels_curves": channels_curves,
                }
        elif file_type == "phasors":
            phasors_data = data[0]
            app.reader_data[active_tab]["data"]["phasors_data"] = phasors_data
            app.reader_data[active_tab]["phasors_metadata"] = metadata
            
            
    @staticmethod
    def read_laserblood_metadata(window, app, tab_selected):
        active_tab = ReadData.get_data_type(tab_selected)
        result = ReadData.read_json(window, "Laserblood metadata")
        if not result:
            return
        file_name, data = result
        app.reader_data[active_tab]["files"]["laserblood_metadata"] = file_name
        app.reader_data[active_tab]["laserblood_metadata"] = data

    @staticmethod
    def get_data_type(active_tab):
        return {TAB_SPECTROSCOPY: "spectroscopy", TAB_PHASORS: "phasors"}.get(
            active_tab, "fitting"
        )

    @staticmethod
    def plot_data(app):
        data_type = ReadData.get_data_type(app.tab_selected)
        spectroscopy_data = (
            app.reader_data[data_type]["data"]
            if data_type == "spectroscopy"
            else app.reader_data[data_type]["data"]["spectroscopy_data"]
        )
        metadata = app.reader_data[data_type]["metadata"]
        laser_period_ns = (
            metadata["laser_period_ns"]
            if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
            else 25
        )
        channels = metadata["channels"] if "channels" in metadata else []
        if "times" in spectroscopy_data and "channels_curves" in spectroscopy_data and not(metadata == {}):
            ReadData.plot_spectroscopy_data(
                app,
                spectroscopy_data["times"],
                spectroscopy_data["channels_curves"],
                laser_period_ns,
                channels
            )
        if data_type == "phasors":
            phasors_data = app.reader_data[data_type]["data"]["phasors_data"]
            if not(metadata == {}):
                ReadData.plot_phasors_data(app, phasors_data, metadata["harmonics"])
            

    @staticmethod
    def plot_spectroscopy_data(app, times, channels_curves, laser_period_ns, metadata_channels):
        num_bins = 256
        x_values = np.linspace(0, laser_period_ns, num_bins) / 1_000
        for channel, curves in channels_curves.items():
            if metadata_channels[channel] in app.plots_to_show:
                y_values = np.sum(curves, axis=0)
                if app.tab_selected != TAB_PHASORS:
                    app.cached_decay_values[app.tab_selected][metadata_channels[channel]] = y_values
                app.update_plots2(metadata_channels[channel], x_values, y_values, reader_mode=True)

    @staticmethod
    def plot_phasors_data(app, data, harmonics):
        app.all_phasors_points = app.get_empty_phasors_points()
        app.control_inputs[HARMONIC_SELECTOR].setCurrentIndex(0)
        harmonics_length = len(harmonics) if isinstance(harmonics, list) else harmonics
        if harmonics_length > 1:
            app.harmonic_selector_shown = True
            app.show_harmonic_selector(harmonics)
        for channel, channel_data in data.items():
            if channel in app.plots_to_show:
                for harmonic, values in channel_data.items():
                    if harmonic == 1:
                        app.draw_points_in_phasors(channel, harmonic, values)
                    app.all_phasors_points[channel][harmonic].extend(values)          
        if app.quantized_phasors:
            app.quantize_phasors(
                app.phasors_harmonic_selected,
                bins=int(PHASORS_RESOLUTIONS[app.phasors_resolution]),
            )
        else:
            app.on_quantize_phasors_changed(False)
        app.generate_phasors_cluster_center(app.phasors_harmonic_selected)   
        app.generate_phasors_legend(app.phasors_harmonic_selected)

    @staticmethod
    def are_phasors_and_spectroscopy_ref_from_same_acquisition(
        app, file, file_type, metadata
    ):
        reader_data = app.reader_data["phasors"]
        file_type_to_compare = "spectroscopy" if file_type == "phasors" else "phasors"
        metadata_to_compare = (
            "spectroscopy_metadata" if file_type == "phasors" else "phasors_metadata"
        )

        if reader_data["files"].get(file_type_to_compare):
            if set(metadata["channels"]) != set(
                reader_data[metadata_to_compare]["channels"]
            ):
                ReadData.show_warning_message(
                    "Channels mismatch",
                    "Active channels mismatching in Phasors file and Spectroscopy reference. Files are not from the same acquisition",
                )
                return False
            if (
                FileUtils.compare_file_timestamps(
                    reader_data["files"][file_type_to_compare], file
                )
                > 120
            ):
                ReadData.show_warning_message(
                    "Files creation time distance too large",
                    "Creation time distance of Phasors and Spectroscopy reference too large. The files do not come from the same acquisition",
                )
                return False
        return True

    @staticmethod
    def show_warning_message(title, message):
        BoxMessage.setup(
            title, message, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
        )

    @staticmethod
    def read_json(window, file_type):
        dialog = QFileDialog()
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setNameFilter("JSON files (*.json)")
        file_name, _ = dialog.getOpenFileName(
            window,
            f"Load {file_type} file",
            "",
            "JSON files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_name or not file_name.endswith(".json"):
            ReadData.show_warning_message(
                "Invalid extension", "Invalid extension. File should be a .json"
            )
            return None, None

        try:
            with open(file_name, "r") as f:
                data = json.load(f)
                return file_name, data
        except json.JSONDecodeError:
            ReadData.show_warning_message(
                "Invalid JSON", "The file could not be parsed as valid JSON."
            )
            return None, None
        except Exception as e:
            ReadData.show_warning_message(
                "Error reading file", f"Error reading {file_type} file: {str(e)}"
            )
            return None, None



    @staticmethod
    def read_bin(window, app, magic_bytes, file_type, read_data_cb, tab_selected):
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
        if not file_name or not file_name.endswith(".bin"):
            ReadData.show_warning_message(
                "Invalid extension", "Invalid extension. File should be a .bin"
            )
            return None

        try:
            with open(file_name, "rb") as f:
                if f.read(4) != magic_bytes:
                    ReadData.show_warning_message(
                        "Invalid file",
                        f"Invalid file. The file is not a valid {file_type} file.",
                    )
                    return None
                return read_data_cb(f, file_name, file_type, tab_selected, app)
        except Exception:
            ReadData.show_warning_message(
                "Error reading file", f"Error reading {file_type} file"
            )
            return None

    @staticmethod
    def read_spectroscopy_data(file, file_name, file_type, tab_selected, app):
        try:
            json_length = struct.unpack("I", file.read(4))[0]
            metadata = json.loads(file.read(json_length).decode("utf-8"))
            if tab_selected == "phasors":
                if not ReadData.are_phasors_and_spectroscopy_ref_from_same_acquisition(
                    app, file_name, file_type.lower(), metadata
                ):
                    return None
            channel_curves = {i: [] for i in range(len(metadata["channels"]))}
            times = []
            number_of_channels = len(metadata["channels"])
            while True:
                data = file.read(8)
                if not data:
                    break
                time = struct.unpack("d", data)[0]
                times.append(time / 1_000_000_000)
                for i in range(number_of_channels):
                    data = file.read(4 * 256)
                    if len(data) < 4 * 256:
                        return times, channel_curves
                    channel_curves[i].append(np.array(struct.unpack("I" * 256, data)))
            return file_name, "spectroscopy", times, channel_curves, metadata
        except Exception:
            ReadData.show_warning_message(
                "Error reading file", "Error reading Spectroscopy file"
            )
            return None

    @staticmethod
    def read_phasors_data(file, file_name, file_type, tab_selected, app):
        phasors_data = {}
        try:
            json_length = struct.unpack("I", file.read(4))[0]
            metadata = json.loads(file.read(json_length).decode("utf-8"))
            if not ReadData.are_phasors_and_spectroscopy_ref_from_same_acquisition(
                app, file_name, file_type.lower(), metadata
            ):
                return None
            while True:
                bytes_read = file.read(32)
                if not bytes_read:
                    break
                try:
                    time_ns, channel_name, harmonic_name, g, s = struct.unpack(
                        "QIIdd", bytes_read
                    )
                except struct.error:
                    ReadData.show_warning_message(
                        "Error unpacking file", "Error unpacking Phasors file data"
                    )
                    break
                phasors_data.setdefault(channel_name, {}).setdefault(
                    harmonic_name, []
                ).append((g, s))
            return file_name, "phasors", phasors_data, metadata
        except Exception:
            ReadData.show_warning_message(
                "Error reading file", "Error reading Phasors file"
            )
            return None

    @staticmethod
    def get_phasors_frequency_mhz(app):
        metadata = app.reader_data["phasors"]["phasors_metadata"]
        if "laser_period_ns" in metadata:
            return ns_to_mhz(metadata["laser_period_ns"]) 
        return 0.0
    
    @staticmethod
    def get_spectroscopy_frequency_mhz(app):
       metadata = app.reader_data["spectroscopy"]["metadata"]
       if "laser_period_ns" in metadata:
            return ns_to_mhz(metadata["laser_period_ns"]) 
       return 0.0
   
    @staticmethod
    def get_frequency_mhz(app):
        if app.tab_selected == TAB_SPECTROSCOPY:
            return ReadData.get_spectroscopy_frequency_mhz(app) 
        elif app.tab_selected == TAB_PHASORS:
            return ReadData.get_phasors_frequency_mhz(app) 
        else: 
            return 0.0       

    @staticmethod
    def get_spectroscopy_file_x_values(app):
        if app.acquire_read_mode == 'read':
            metadata = app.reader_data[ReadData.get_data_type(app.tab_selected)]["metadata"]
            if metadata and "laser_period_ns" in metadata:
                x_values = np.linspace(0, metadata["laser_period_ns"], 256) / 1_000
                return x_values
        return None    
        

class ReadDataControls:

    @staticmethod
    def handle_widgets_visibility(app, read_mode):
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(app)
        app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
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
        file_metadata = app.reader_data[file_type].get("metadata", {})
        if file_metadata.get("channels"):
            app.selected_channels = sorted(file_metadata["channels"])
            app.plots_to_show = app.reader_data[file_type].get("plots", [])
            for i, checkbox in enumerate(app.channel_checkboxes):
                checkbox.set_checked(i in app.selected_channels)

    @staticmethod
    def plot_data_on_tab_change(app):
        file_type = ReadData.get_data_type(app.tab_selected)
        if app.acquire_read_mode == 'read':
            ReadDataControls.handle_plots_config(app, file_type)
            app.clear_plots()
            app.generate_plots(ReadData.get_frequency_mhz(app))
            app.toggle_intensities_widgets_visibility()
            ReadData.plot_data(app)
            
    
    @staticmethod
    def read_bin_metadata_enabled(app):
        data_type = ReadData.get_data_type(app.tab_selected) 
        metadata = app.reader_data[data_type]["metadata"]  
        if data_type != 'phasors':
            return not(metadata  == {}) and app.acquire_read_mode == 'read'
        else:
            phasors_file = app.reader_data[data_type]["files"]["phasors"] 
            return not(metadata == {}) and not(phasors_file.strip() == "") and app.acquire_read_mode == 'read'


class ReaderPopup(QWidget):
    def __init__(self, window, tab_selected):
        super().__init__()
        self.app = window
        self.tab_selected = tab_selected
        self.widgets = {}
        self.layouts = {}
        self.channels_checkboxes = []
        self.channels_checkbox_first_toggle = True
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
            elif file_type == "spectroscopy":
                input_desc = QLabel(f"LOAD A {file_type.upper()} FILE:")
            else:
                file_name = file_type.upper().replace('_', ' ')
                input_desc = QLabel(f"LOAD A {file_name} FILE:")    
            input_desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            control_row = QHBoxLayout()

            def on_change(file_type=file_type):
                def callback(text):
                    self.on_loaded_file_change(text, file_type)

                return callback

            _, input = InputTextControl.setup(
                label="",
                placeholder="Load .bin file" if file_type != "laserblood_metadata" else "Load .json file",
                event_callback=on_change(),
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
                plots_to_show = selected_channels[:2]
            self.app.plots_to_show = plots_to_show
            self.app.settings.setValue(
                SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
            )
            channels_layout = QVBoxLayout()
            desc = QLabel("CHOOSE MAX 4 PLOTS TO DISPLAY:")
            desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
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
        self.app.generate_plots()
        self.app.toggle_intensities_widgets_visibility()

    def on_loaded_file_change(self, text, file_type):
        if (text != self.app.reader_data[self.data_type]["files"][file_type] 
            and file_type != "laserblood_metadata"):
            self.app.clear_plots()
            self.app.generate_plots()
            self.app.toggle_intensities_widgets_visibility()
        self.app.reader_data[self.data_type]["files"][file_type] = text

    def on_load_file_btn_clicked(self, file_type):
        if file_type == "laserblood_metadata":
            ReadData.read_laserblood_metadata(self, self.app, self.tab_selected)
        else:
            ReadData.read_bin_data(self, self.app, self.tab_selected, file_type)
        file_name = self.app.reader_data[self.data_type]["files"][file_type]
        if file_name is not None and len(file_name) > 0:
            bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
            self.app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
            widget_key = f"load_{file_type}_input"
            self.widgets[widget_key].setText(file_name)
            if file_type != "laserblood_metadata":
                self.remove_channels_grid()
                channels_layout = self.init_channels_layout()
                if channels_layout is not None:
                    self.layout.insertLayout(2, channels_layout)
                    

    def on_plot_data_btn_clicked(self):
        ReadData.plot_data(self.app)
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
        self.tab_selected = tab_selected
        self.data_type = ReadData.get_data_type(self.tab_selected)
        self.setWindowTitle(f"{self.data_type.capitalize()} file metadata")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        metadata_table = self.create_metadata_table()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setLayout(metadata_table)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        main_layout.addSpacing(10)
        self.setLayout(main_layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.app.widgets[READER_METADATA_POPUP] = self

    def get_metadata_keys_dict(self):
        return {
            "channels": "Enabled Channels",
            "bin_width_micros": "Bin width (μs)",
            "acquisition_time_millis": "Acquisition time (s)",
            "laser_period_ns": "Laser period (ns)",
            "harmonics": "Harmonics",
            "tau_ns": "Tau (ns)",
        }
        
    def parse_laserblood_metadata(self, laserblood_metadata): 
        data = {} 
        for item in laserblood_metadata:
            key = item["label"] + " (" + item["unit"] + ")" if item["unit"] else item["label"]
            value = item["value"]
            data[key] = value
        return data    

    def create_label_row(self, key, value, key_bg_color, value_bg_color):
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0, 0, 0, 0)
        h_box.setSpacing(0)
        key_label = QLabel(key)
        key_label.setStyleSheet(f"width: 200px; font-size: 14px; border: 1px solid {key_bg_color}; padding: 8px; color: white; background-color: {key_bg_color}")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"width: 500px; font-size: 14px; border: 1px solid {value_bg_color}; padding: 8px; color: white")
        h_box.addWidget(key_label)
        h_box.addWidget(value_label)
        return h_box

    def create_metadata_table(self):
        metadata_keys = self.get_metadata_keys_dict()
        metadata = self.app.reader_data[self.data_type]["metadata"]
        laserblood_metadata = self.app.reader_data[self.data_type]["laserblood_metadata"]
        file = self.app.reader_data[self.data_type]["files"][self.data_type]
        v_box = QVBoxLayout()
        v_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel(f"{self.data_type.upper()} FILE METADATA")
        title.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
        v_box.addWidget(title)
        v_box.addSpacing(10)
        file_info_row = self.create_label_row("File", file, "#DA1212", "#DA1212")
        v_box.addLayout(file_info_row)
        if laserblood_metadata:            
            parsed_laserblood_metadata = self.parse_laserblood_metadata(laserblood_metadata)        
            for key, value in parsed_laserblood_metadata.items():
                metadata_row = self.create_label_row(key, str(value), "#11468F", "#11468F")
                v_box.addLayout(metadata_row)
        else:
            if metadata:
                for key, value in metadata_keys.items():
                    if key in metadata:
                        metadata_value = str(metadata[key])
                        if key == "channels":
                            metadata_value = ", ".join(["Channel " + str(ch + 1) for ch in metadata[key]])
                        if key == "acquisition_time_millis":
                            metadata_value = str(metadata[key] / 1000)
                        metadata_row = self.create_label_row(value, metadata_value, "#11468F", "#11468F")
                        v_box.addLayout(metadata_row)

        return v_box