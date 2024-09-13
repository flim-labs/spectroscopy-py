import json
import numpy as np
from functools import partial
from PyQt6.QtWidgets import QHBoxLayout, QSlider, QWidget
from PyQt6.QtCore import Qt
from components.gui_styles import GUIStyles
from components.helpers import calc_bin_from_micro_time_ns, calc_micro_time_ns
from components.input_number_control import InputFloatControl, InputNumberControl
from components.lin_log_control import LinLogControl
from settings import *


class SpectroscopyTimeShift(QWidget):
    def __init__(self, window, channel, parent=None):
        super().__init__(parent)
        self.app = window
        self.frequency_mhz = self.app.get_frequency_mhz()
        self.channel = channel
        self.init_control_inputs()
        self.setLayout(self.create_controls())

    def init_control_inputs(self):
        if "time_shift_sliders" not in self.app.control_inputs:
            self.app.control_inputs["time_shift_sliders"] = {}
        if "time_shift_inputs" not in self.app.control_inputs:
            self.app.control_inputs["time_shift_inputs"] = {}

    @staticmethod
    def get_time_shift_ns_value(app, time_bin: int):
        frequency_mhz = app.get_frequency_mhz()
        time_shift_ns = calc_micro_time_ns(time_bin, frequency_mhz)
        return time_shift_ns

    @staticmethod
    def get_time_shift_bin_value(app, time_ns: float):
        frequency_mhz = app.get_frequency_mhz()
        time_shift_bin = calc_bin_from_micro_time_ns(time_ns, frequency_mhz)
        return time_shift_bin

    def create_controls(self):
        time_shift_bin = int(self.app.time_shifts.get(self.channel, 0))
        time_shift_ns = SpectroscopyTimeShift.get_time_shift_ns_value(
            self.app, time_shift_bin
        )
        h_layout = QHBoxLayout()
        # slider (bin)
        slider = self.setup_slider(time_shift_bin)
        h_layout.addWidget(slider)
        # input float (ns)
        _, inp = InputFloatControl.setup(
            "Time shift (ns):",
            SpectroscopyTimeShift.get_time_shift_ns_value(self.app, 0),
            SpectroscopyTimeShift.get_time_shift_ns_value(self.app, 256),
            time_shift_ns,
            h_layout,
            partial(self.on_value_change, inp_type="input", channel=self.channel),
            control_layout="horizontal",
            spacing=0,
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        slider.setEnabled(self.frequency_mhz != 0.0)
        inp.setEnabled(self.frequency_mhz != 0.0)
        self.app.control_inputs["time_shift_sliders"][self.channel] = slider
        self.app.control_inputs["time_shift_inputs"][self.channel] = inp
        return h_layout

    def setup_slider(self, time_shift):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 256)
        slider.setValue(time_shift)
        slider.valueChanged.connect(
            partial(self.on_value_change, inp_type="slider", channel=self.channel)
        )
        return slider

    def on_value_change(self, value, inp_type, channel):
        time_shift_value = (
            int(value)
            if inp_type == "slider"
            else int(SpectroscopyTimeShift.get_time_shift_bin_value(self.app, value))
        )
        self.app.time_shifts[self.channel] = time_shift_value
        lin_log_mode = (
            self.app.lin_log_mode[self.channel]
            if self.channel in self.app.lin_log_mode
            else "LIN"
        )
        if inp_type == "slider":
            time_shift_ns = SpectroscopyTimeShift.get_time_shift_ns_value(
                self.app, value
            )
            self.app.control_inputs["time_shift_inputs"][self.channel].setValue(
                time_shift_ns
            )
        else:
            time_shift_bin = int(
                SpectroscopyTimeShift.get_time_shift_bin_value(self.app, value)
            )
            self.app.control_inputs["time_shift_sliders"][self.channel].setValue(
                time_shift_bin
            )
        if self.app.tab_selected in self.app.decay_curves:
            if self.channel in self.app.decay_curves[self.app.tab_selected]:
                decay_curve = self.app.decay_curves[self.app.tab_selected][self.channel]
                x, y = decay_curve.getData()
                if x is not None and y is not None:
                    if channel in self.app.cached_decay_values[self.app.tab_selected]:
                        cached_decay_curve = self.app.cached_decay_values[
                            self.app.tab_selected
                        ][channel]
                        decay_widget = self.app.decay_widgets[channel]
                        if lin_log_mode == "LIN":
                            ticks, y_data = LinLogControl.calculate_lin_mode(
                                cached_decay_curve
                            )
                            decay_widget.showGrid(x=False, y=False)
                        else:
                            ticks, y_data, _ = LinLogControl.calculate_log_mode(
                                cached_decay_curve
                            )
                            decay_widget.showGrid(x=False, y=True, alpha=0.3)
                        decay_widget.getAxis("left").setTicks([ticks])
                        y = np.roll(y_data, time_shift_value)
                        decay_curve.setData(x, y)
                        self.app.set_plot_y_range(decay_widget)
        self.app.settings.setValue(
            SETTINGS_TIME_SHIFTS, json.dumps(self.app.time_shifts)
        )

    @staticmethod
    def get_channel_time_shift(app, channel):
        return app.time_shifts[channel] if channel in app.time_shifts else 0
