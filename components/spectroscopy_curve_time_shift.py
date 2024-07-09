import json
import numpy as np
from functools import partial
from PyQt6.QtWidgets import QHBoxLayout, QSlider, QWidget
from PyQt6.QtCore import Qt
from components.gui_styles import GUIStyles
from components.input_number_control import InputNumberControl
from settings import *


class SpectroscopyTimeShift(QWidget):
    def __init__(self, window, channel, parent=None):
        super().__init__(parent)
        self.app = window
        self.channel = channel
        self.init_control_inputs()
        self.setLayout(self.create_controls())

    def init_control_inputs(self):
        if "time_shift_sliders" not in self.app.control_inputs:
            self.app.control_inputs["time_shift_sliders"] = {}
        if "time_shift_inputs" not in self.app.control_inputs:
            self.app.control_inputs["time_shift_inputs"] = {}

    def create_controls(self):
        time_shift = self.app.time_shifts.get(self.channel, 0)
        h_layout = QHBoxLayout()
        slider = self.setup_slider(time_shift)
        h_layout.addWidget(slider)
        _, inp = InputNumberControl.setup(
            "Time shift (bin):",
            0,
            255,
            int(time_shift),
            h_layout,
            partial(self.on_value_change, inp_type="input"),
            control_layout="horizontal",
            spacing=0
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style()) 
        self.app.control_inputs["time_shift_sliders"][self.channel] = slider
        self.app.control_inputs["time_shift_inputs"][self.channel] = inp
        return h_layout

    def setup_slider(self, time_shift):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 255)
        slider.setValue(time_shift)
        slider.valueChanged.connect(partial(self.on_value_change, inp_type="slider"))
        return slider

    def on_value_change(self, value, inp_type):
        self.app.time_shifts[self.channel] = value
        if inp_type == "slider":
            self.app.control_inputs["time_shift_inputs"][self.channel].setValue(value)
        else:
            self.app.control_inputs["time_shift_sliders"][self.channel].setValue(value)
        if self.channel in self.app.decay_curves:
            decay_curve = self.app.decay_curves[self.channel]
            x, y = decay_curve.getData()
            if x is not None and y is not None:
                x = self.app.cached_decay_x_values if not value else np.roll(self.app.cached_decay_x_values, value)
                decay_curve.setData(x, y)
        self.app.settings.setValue(SETTINGS_TIME_SHIFTS, json.dumps(self.app.time_shifts))
