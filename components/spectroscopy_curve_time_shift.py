import json
import numpy as np
from functools import partial
from PyQt6.QtWidgets import QHBoxLayout, QSlider, QWidget, QLabel
from PyQt6.QtCore import Qt
from utils.gui_styles import GUIStyles
from utils.helpers import calc_micro_time_ns
from components.input_number_control import InputNumberControl
from components.lin_log_control import LinLogControl
import settings.settings as s


class SpectroscopyTimeShift(QWidget):
    """A widget for adjusting the time shift of a spectroscopy decay curve.

    This widget provides a slider and a number input to control the time shift
    in bins, and displays the corresponding shift in nanoseconds.
    """
    def __init__(self, window, channel, parent=None):
        """Initializes the SpectroscopyTimeShift widget.

        Args:
            window: The main application window instance.
            channel (int): The channel index this widget controls.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.app = window
        self.channel = channel
        self.init_control_inputs()
        self.setLayout(self.create_controls())

    def init_control_inputs(self):
        """Initializes the dictionaries in the main app for storing control inputs if they don't exist."""
        if "time_shift_sliders" not in self.app.control_inputs:
            self.app.control_inputs["time_shift_sliders"] = {}
        if "time_shift_inputs" not in self.app.control_inputs:
            self.app.control_inputs["time_shift_inputs"] = {}
        if s.TIME_SHIFTS_NS not in self.app.control_inputs:
            self.app.control_inputs[s.TIME_SHIFTS_NS] = {}

    def create_controls(self):
        """Creates and arranges the UI controls for the time shift widget.

        Returns:
            QHBoxLayout: The layout containing the slider, number input, and ns label.
        """
        acquire_mode = self.app.acquire_read_mode == "acquire"
        time_shift = self.app.time_shifts.get(self.channel, 0) if acquire_mode else 0
        h_layout = QHBoxLayout()
        slider = self.setup_slider(time_shift)
        h_layout.addWidget(slider)
        _, inp = InputNumberControl.setup(
            "Time shift (bin):",
            0,
            255,
            int(time_shift),
            h_layout,
            partial(self.on_value_change, inp_type="input", channel=self.channel),
            control_layout="horizontal",
            spacing=0
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style()) 
        # Time shifts ns
        time_shift_ns = QLabel(f"{SpectroscopyTimeShift.get_time_shift_ns_value(self.app, time_shift):.6f} ns")
        time_shift_ns.setStyleSheet("color: #285da6; font-weight: 600")
        h_layout.addSpacing(5)
        h_layout.addWidget(time_shift_ns)
        self.app.control_inputs["time_shift_sliders"][self.channel] = slider
        self.app.control_inputs["time_shift_inputs"][self.channel] = inp
        self.app.control_inputs[s.TIME_SHIFTS_NS][self.channel] = time_shift_ns
        return h_layout

    def setup_slider(self, time_shift):
        """Creates and configures the time shift slider.

        Args:
            time_shift (int): The initial value for the slider.

        Returns:
            QSlider: The configured slider widget.
        """
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 255)
        slider.setValue(time_shift)
        slider.valueChanged.connect(partial(self.on_value_change, inp_type="slider", channel=self.channel))
        return slider

    def on_value_change(self, value, inp_type, channel):
        """Handles changes from the slider or number input.

        Updates the corresponding control, recalculates the time shift in ns,
        applies the shift to the plot data, and saves the new setting.

        Args:
            value (int): The new time shift value in bins.
            inp_type (str): The type of input that triggered the change ('slider' or 'input').
            channel (int): The channel index being modified.
        """
        from core.plots_controller import PlotsController
        self.app.time_shifts[self.channel] = value
        lin_log_mode = self.app.lin_log_mode[self.channel] if self.channel in self.app.lin_log_mode else 'LIN'
        if inp_type == "slider":
            self.app.control_inputs["time_shift_inputs"][self.channel].setValue(value)
        else:
            self.app.control_inputs["time_shift_sliders"][self.channel].setValue(value)
        SpectroscopyTimeShift.update_time_shift_ns_value(self.app, value, channel)    
        if self.app.tab_selected in self.app.decay_curves: 
            if self.channel in self.app.decay_curves[self.app.tab_selected]:
                decay_curve = self.app.decay_curves[self.app.tab_selected][self.channel]
                x, y = decay_curve.getData()
                if x is not None and y is not None:
                    if channel in self.app.cached_decay_values[self.app.tab_selected]:
                        cached_decay_curve = self.app.cached_decay_values[self.app.tab_selected][channel]
                        decay_widget = self.app.decay_widgets[channel]
                        if lin_log_mode == 'LIN':
                            ticks, y_data = LinLogControl.calculate_lin_mode(cached_decay_curve)
                            decay_widget.showGrid(x=False, y=False)
                        else:
                            ticks, y_data, _ = LinLogControl.calculate_log_mode(cached_decay_curve)
                            decay_widget.showGrid(x=False, y=True, alpha=0.3)     
                        decay_widget.getAxis("left").setTicks([ticks])    
                        y = np.roll(y_data, value)
                        decay_curve.setData(x, y)
                        PlotsController.set_plot_y_range(decay_widget)
        self.app.settings.setValue(s.SETTINGS_TIME_SHIFTS, json.dumps(self.app.time_shifts))
        

    @staticmethod
    def update_time_shift_ns_value(app, bin_value, channel): 
        """Updates the nanosecond time shift label for a specific channel.

        Args:
            app: The main application instance.
            bin_value (int): The time shift value in bins.
            channel (int): The channel index to update.
        """
        if s.TIME_SHIFTS_NS in app.control_inputs:
            time_shifts_ns_labels = app.control_inputs[s.TIME_SHIFTS_NS]
            if channel in time_shifts_ns_labels:
                ns_value = SpectroscopyTimeShift.get_time_shift_ns_value(app, bin_value)
                time_shifts_ns_labels[channel].setText(f"{ns_value:.6f} ns")

    @staticmethod
    def get_time_shift_ns_value(app, time_bin: int):
        """Calculates the time shift in nanoseconds from a bin value.

        Args:
            app: The main application instance.
            time_bin (int): The time shift value in bins.

        Returns:
            float: The calculated time shift in nanoseconds.
        """
        from core.controls_controller import ControlsController
        frequency_mhz = ControlsController.get_frequency_mhz(app)
        time_shift_ns = calc_micro_time_ns(time_bin, frequency_mhz)
        return time_shift_ns
    
        
    @staticmethod
    def get_channel_time_shift(app, channel):
        """Gets the current time shift for a given channel.

        Args:
            app: The main application instance.
            channel (int): The channel index.

        Returns:
            int: The time shift in bins for the specified channel, or 0 if not set.
        """
        return app.time_shifts[channel] if channel in app.time_shifts else 0