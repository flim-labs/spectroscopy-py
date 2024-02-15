import os
import sys

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QTimer, QSettings, QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLayout, QCheckBox, QLabel, \
    QSizePolicy

from gui_components.fancy_checkbox import FancyButton
from gui_components.input_number_control import InputNumberControl
from gui_components.select_control import SelectControl
from gui_components.switch_control import SwitchControl
from gui_styles import GUIStyles

VERSION = "1.0.0"
APP_DEFAULT_WIDTH = 1000
APP_DEFAULT_HEIGHT = 800
TOP_BAR_HEIGHT = 250
MAX_CHANNELS = 8
current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class SpectroscopyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.settings = self.init_settings()

        self.channel_checkboxes = []
        self.sync_buttons = []
        self.control_inputs = {}

        self.dynamic_curves = []
        self.static_curves = []

        self.selected_channels = []
        self.selected_sync = self.settings.value("sync", "sync_in")
        self.sync_in_frequency_mhz = float(self.settings.value("sync_mhz", .0))

        print(self.selected_sync, self.sync_in_frequency_mhz)

        self.get_selected_channels_from_settings()

        (self.top_bar, self.grid_layout) = self.init_ui()
        self.generate_plots()

        self.timer_update = QTimer()
        self.timer_update.timeout.connect(self.update_plots)
        # self.timer_update.start(25)

    def init_ui(self):
        self.setWindowTitle("Spectroscopy v" + VERSION)
        GUIStyles.customize_theme(self)
        GUIStyles.set_fonts()
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

        enabled_checkbox = QCheckBox("Enabled")
        enabled_checkbox.setChecked(True)
        enabled_checkbox.stateChanged.connect(
            lambda state: self.top_bar_set_enabled(enabled_checkbox.isChecked()))
        top_bar.addWidget(enabled_checkbox)

        container = QWidget()
        container.setLayout(top_bar)
        container.setFixedHeight(TOP_BAR_HEIGHT)
        return container

    def create_logo_and_title(self):
        logo_and_title = QHBoxLayout()
        pixmap = QPixmap(
            os.path.join(project_root, "assets", "flimlabs-logo.png")
        ).scaledToWidth(60)
        flim_header_icon = QLabel(pixmap=pixmap)
        header_title = QLabel("Spectroscopy v" + VERSION)
        header_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_title.setStyleSheet(GUIStyles.set_main_title_style())
        logo_and_title.addWidget(flim_header_icon)
        logo_and_title.addWidget(header_title)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        logo_and_title.addWidget(spacer)
        return logo_and_title

    def create_control_inputs(self):
        controls_row = QHBoxLayout()
        _, inp = SelectControl.setup(
            "Channel type:",
            self.settings.value("connection_type", "SMA"),
            controls_row,
            ["USB", "SMA"],
            self.on_connection_type_value_change
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        self.control_inputs["channel_type"] = inp

        _, inp = InputNumberControl.setup(
            "Bin width (µs):",
            1,
            1000000,
            int(self.settings.value("bin_width", 1000)),
            controls_row,
            self.on_bin_width_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs["bin_width"] = inp

        _, inp = InputNumberControl.setup(
            "Time span (s):",
            1,
            300,
            int(self.settings.value("time_span", 10)),
            controls_row,
            self.on_time_span_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs["time_span"] = inp

        switch_control = QVBoxLayout()
        inp = SwitchControl(
            active_color="#8d4ef2",
            checked=self.settings.value("free_running", "false") == "true"
        )
        inp.toggled.connect(self.on_free_running_changed)
        switch_control.addWidget(QLabel("Free running:"))
        switch_control.addSpacing(8)
        switch_control.addWidget(inp)
        controls_row.addLayout(switch_control)
        controls_row.addSpacing(20)
        self.control_inputs["free_running"] = inp

        _, inp = InputNumberControl.setup(
            "Acquisition time (s):",
            0,
            1800,
            int(self.settings.value("acquisition_time", 10)),
            controls_row,
            self.on_acquisition_time_change
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        self.control_inputs["acquisition_time"] = inp
        self.on_free_running_changed(self.settings.value("free_running", "false") == "true")
        return controls_row

    def get_free_running_state(self):
        return self.control_inputs["free_running"].isChecked()

    def on_acquisition_time_change(self, value):
        self.settings.setValue("acquisition_time", value)

    def on_time_span_change(self, value):
        self.settings.setValue("time_span", value)

    def on_free_running_changed(self, state):
        self.control_inputs["acquisition_time"].setEnabled(not state)
        self.settings.setValue("free_running", state)

    def on_bin_width_change(self, value):
        self.settings.setValue("bin_width", value)

    def on_connection_type_value_change(self, value):
        self.settings.setValue("connection_type", value)

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
            self.control_inputs[key].setEnabled(enabled)
        if enabled:
            self.control_inputs["acquisition_time"].setEnabled(not self.get_free_running_state())

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
        self.selected_sync = sync
        self.settings.setValue("sync", sync)

    def create_sync_buttons(self):
        buttons_layout = QHBoxLayout()

        sync_in_button = FancyButton("Sync In")
        buttons_layout.addWidget(sync_in_button)
        self.sync_buttons.append((sync_in_button, 'sync_in'))

        sync_out_80_button = FancyButton("Sync Out (80Mhz)")
        buttons_layout.addWidget(sync_out_80_button)
        self.sync_buttons.append((sync_out_80_button, 'sync_out_80'))

        sync_out_40_button = FancyButton("Sync Out (40Mhz)")
        buttons_layout.addWidget(sync_out_40_button)
        self.sync_buttons.append((sync_out_40_button, 'sync_out_40'))

        sync_out_20_button = FancyButton("Sync Out (20Mhz)")
        buttons_layout.addWidget(sync_out_20_button)
        self.sync_buttons.append((sync_out_20_button, 'sync_out_20'))

        sync_out_10_button = FancyButton("Sync Out (10Mhz)")
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

    def generate_plots(self):
        if len(self.selected_channels) == 0:
            self.grid_layout.addWidget(QWidget(), 0, 0)
            return

        for i in range(len(self.selected_channels)):
            h_layout = QHBoxLayout()

            dynamic_plot_widget = pg.PlotWidget()
            dynamic_plot_widget.setLabel('left', 'Intensity', units='c')
            dynamic_plot_widget.setLabel('bottom', 'Time', units='s')
            dynamic_plot_widget.setTitle(f'Channel {self.selected_channels[i] + 1} intensity')

            x = np.arange(100)
            y = x * 0
            dynamic_curve = dynamic_plot_widget.plot(x, y, pen='y')

            self.dynamic_curves.append(dynamic_curve)
            h_layout.addWidget(dynamic_plot_widget, 2)

            static_plot_widget = pg.PlotWidget()
            static_plot_widget.setLabel('left', 'Intensity', units='c')
            static_plot_widget.setLabel('bottom', 'Bin', units='s')
            static_plot_widget.setTitle(f'Channel {self.selected_channels[i] + 1} decay')

            x = np.linspace(0, 256, 256)
            y = x * 0
            static_curve = static_plot_widget.plot(x, y, pen='r')
            self.static_curves.append(static_curve)
            h_layout.addWidget(static_plot_widget, 1)

            col_length = 1
            if len(self.selected_channels) > 3:
                col_length = 2
            self.grid_layout.addLayout(h_layout, i // col_length, i % col_length)

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
        for curve in self.dynamic_curves:
            curve.clear()
        for curve in self.static_curves:
            curve.clear()
        self.dynamic_curves.clear()
        self.static_curves.clear()
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

    def update_plots(self):
        for curve in self.dynamic_curves:
            x, y = curve.getData()  # Get current data
            if len(x) >= 100:  # Keep only the last 100 points
                x = x[1:]  # Remove the first x value
                y = y[1:]  # Remove the first y value
            x = np.append(x, x[-1] + 1 if len(x) > 0 else 0)  # Append new x value
            y = np.append(y, np.random.normal())  # Append new random y value
            curve.setData(x, y)  # Update the curve with new data


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpectroscopyWindow()
    window.show()
    sys.exit(app.exec())
