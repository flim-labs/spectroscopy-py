import os
import queue
import sys
import threading
import time

import flim_labs
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer, QSettings, QSize, Qt, QEvent
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLayout, QCheckBox, QLabel, \
    QSizePolicy, QPushButton, QDialog

from gui_components.fancy_checkbox import FancyButton
from gui_components.gradient_text import GradientText
from gui_components.input_number_control import InputNumberControl
from gui_components.logo_utilities import OverlayWidget
from gui_components.select_control import SelectControl
from gui_components.switch_control import SwitchControl
from gui_styles import GUIStyles

VERSION = "1.0"
APP_DEFAULT_WIDTH = 1000
APP_DEFAULT_HEIGHT = 800
TOP_BAR_HEIGHT = 210
MAX_CHANNELS = 8
current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

SETTINGS_BIN_WIDTH = "bin_width"
DEFAULT_BIN_WIDTH = 1000
SETTINGS_TIME_SPAN = "time_span"
DEFAULT_TIME_SPAN = 10
SETTINGS_CONNECTION_TYPE = "connection_type"
DEFAULT_CONNECTION_TYPE = "SMA"
SETTINGS_FREE_RUNNING = "free_running"
DEFAULT_FREE_RUNNING = "false"
SETTINGS_ACQUISITION_TIME = "acquisition_time"
DEFAULT_ACQUISITION_TIME = 10
SETTINGS_SYNC = "sync"
DEFAULT_SYNC = "sync_in"
SETTINGS_SYNC_IN_FREQUENCY_MHZ = "sync_in_frequency_mhz"
DEFAULT_SYNC_IN_FREQUENCY_MHZ = 0.0

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

        self.intensity_lines = []
        self.decay_curves = []
        self.decay_curves_queue = queue.Queue()

        self.selected_channels = []
        self.selected_sync = self.settings.value(SETTINGS_SYNC, DEFAULT_SYNC)
        self.sync_in_frequency_mhz = float(
            self.settings.value(SETTINGS_SYNC_IN_FREQUENCY_MHZ, DEFAULT_SYNC_IN_FREQUENCY_MHZ))

        self.get_selected_channels_from_settings()

        (self.top_bar, self.grid_layout) = self.init_ui()

        # self.update_sync_in_button()

        self.generate_plots()

        self.overlay = OverlayWidget(self)
        self.overlay.resize(QSize(100, 100))
        self.installEventFilter(self)
        self.overlay.raise_()

        GUIStyles.set_fonts_deep(self)

        self.timer_update = QTimer()
        self.timer_update.timeout.connect(self.update_plots)

        self.pull_from_queue_timer = QTimer()
        self.pull_from_queue_timer.timeout.connect(self.pull_from_queue)
        # self.timer_update.start(25)

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

        top_bar.addLayout(self.create_logo_and_title())
        top_bar.addSpacing(10)
        top_bar.addLayout(self.create_channel_selector())
        top_bar.addLayout(self.create_sync_buttons())
        top_bar.addLayout(self.create_control_inputs())

        container = QWidget()
        container.setLayout(top_bar)
        container.setFixedHeight(TOP_BAR_HEIGHT)
        return container

    def create_logo_and_title(self):
        row = QHBoxLayout()
        pixmap = QPixmap(
            os.path.join(project_root, "assets", "flimlabs-logo.png")
        ).scaledToWidth(60)
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

    def create_control_inputs(self):
        controls_row = QHBoxLayout()
        _, inp = SelectControl.setup(
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

        spacer = QWidget()
        spacer.setMaximumWidth(300)
        controls_row.addWidget(spacer)

        # green background and white text
        start_button = QPushButton("Start")
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
            self.control_inputs["start_button"].setText("Start")
            self.control_inputs["start_button"].setStyleSheet("""
                        QPushButton {
                            background-color: #13B6B4;
                            border: 1px solid #13B6B4;
                            color: white;
                            min-width: 100px;
                            border-radius: 4px;
                            font-family: "Montserrat";
                            font-size: 14px;
                            font-weight: thin;
                        }

                        QPushButton:hover {
                            background-color: #23F3AB;
                            border: 2px solid #23F3AB;
                            color: black;
                        }
                    """)
        else:
            self.control_inputs["start_button"].setText("Stop")
            self.control_inputs["start_button"].setStyleSheet("""
                        QPushButton {
                            background-color: #f34d23;
                            border: 1px solid #f34d23;
                            font-family: "Montserrat";
                            color: white;
                            letter-spacing: 0.1em;
                            min-width: 100px;
                            border-radius: 4px;
                            font-size: 14px;
                            font-weight: bold;
                        }
                        
                        QPushButton:hover {
                            background-color: #b63613;
                            border: 2px solid #b63613;
                            color: white;
                        }
                    """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(event.size())

    def on_start_button_click(self):
        if self.mode == MODE_STOPPED:
            self.begin_spectroscopy_experiment()
        elif self.mode == MODE_RUNNING:
            self.stop_spectroscopy_experiment()

    def get_free_running_state(self):
        return self.control_inputs[SETTINGS_FREE_RUNNING].isChecked()

    def on_acquisition_time_change(self, value):
        self.settings.setValue(SETTINGS_ACQUISITION_TIME, value)

    def on_time_span_change(self, value):
        self.settings.setValue(SETTINGS_TIME_SPAN, value)

    def on_free_running_changed(self, state):
        self.control_inputs[SETTINGS_ACQUISITION_TIME].setEnabled(not state)
        self.settings.setValue(SETTINGS_FREE_RUNNING, state)

    def on_bin_width_change(self, value):
        self.settings.setValue(SETTINGS_BIN_WIDTH, value)

    def on_connection_type_value_change(self, value):
        self.settings.setValue(SETTINGS_CONNECTION_TYPE, value)

    def create_channel_selector(self):
        grid = QHBoxLayout()
        grid.addSpacing(20)
        for i in range(MAX_CHANNELS):
            from gui_components.fancy_checkbox import FancyCheckbox
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
            v_layout = QVBoxLayout()

            intensity_widget = pg.PlotWidget()
            intensity_widget.setLabel('left', 'AVG. Photon counts', units='c')
            intensity_widget.setLabel('bottom', 'Time', units='s')
            intensity_widget.setTitle(f'Channel {self.selected_channels[i] + 1} intensity')

            x = np.arange(1)
            y = x * 0
            intensity_plot = intensity_widget.plot(x, y, pen='y')
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
            v_layout.addWidget(curve_widget, 3)

            col_length = 1
            if len(self.selected_channels) == 2:
                col_length = 2
            elif len(self.selected_channels) == 3:
                col_length = 3
            if len(self.selected_channels) > 3:
                col_length = 2
            self.grid_layout.addLayout(v_layout, i // col_length, i % col_length)

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

    def begin_spectroscopy_experiment(self):
        if self.selected_sync == "sync_in":
            frequency_mhz = self.sync_in_frequency_mhz
        else:
            frequency_mhz = int(self.selected_sync.split("_")[-1])
        if frequency_mhz == 0.0:
            print("Error: Frequency not detected")
            return

        self.clear_plots()
        self.generate_plots(frequency_mhz)

        if len(self.selected_channels) == 0:
            print("Error: No channels selected")
            return

        acquisition_time_millis = None if self.get_free_running_state() else int(
            self.settings.value(SETTINGS_ACQUISITION_TIME, DEFAULT_ACQUISITION_TIME)) * 1000
        bin_width_micros = int(self.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH))

        connection_type = self.settings.value(SETTINGS_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)

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

        try:
            flim_labs.start_spectroscopy(
                enabled_channels=self.selected_channels,
                bin_width_micros=bin_width_micros,
                frequency_mhz=frequency_mhz,
                firmware_file=firmware_selected,
                acquisition_time_millis=acquisition_time_millis,
            )
        except Exception as e:
            print("Error: " + str(e))
        print("Spectroscopy started")
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
                    self.on_start_button_click()
                    self.mode = MODE_STOPPED
                    self.style_start_button()
                    QApplication.processEvents()
                    break
                ((channel,), (time_ns,), intensities) = v
                channel_index = self.selected_channels.index(channel)
                # self.decay_curves_queue.put((channel_index, time_ns, intensities))
                self.update_plots2(channel_index, time_ns, intensities)
                QApplication.processEvents()
        # QTimer.singleShot(1, self.pull_from_queue)

    def update_plots2(self, channel_index, time_ns, curve):
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
        GUIStyles.set_fonts_deep(self)

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
                self.label.setText(f"Frequency detected: {self.frequency_mhz} Mhz")
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
    app = QApplication(sys.argv)
    window = SpectroscopyWindow()
    window.show()
    sys.exit(app.exec())
    window.pull_from_queue_timer.stop()
