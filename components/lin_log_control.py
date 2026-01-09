import json
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsProxyWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTransform
from utils.gui_styles import GUIStyles
from components.switch_control import SwitchControl
import settings.settings as s


class LinLogControl(QWidget):
    """A widget for switching between linear and logarithmic scales on a plot.

    This control is displayed as a vertical switch with "LIN" and "LOG" labels.
    It is designed to be placed alongside a pyqtgraph plot to control the
    y-axis scale.
    """
    def __init__(
        self,
        window,
        channel,
        time_shifts=0,
        lin_log_modes={},
        lin_log_switches = {},
        persist_changes=True,
        data_type=s.TAB_SPECTROSCOPY,
        fitting_popup = None,
        parent=None,
    ):
        """Initializes the LinLogControl widget.

        Args:
            window: The main application window instance.
            channel (str): The identifier for the plot channel this control is associated with.
            time_shifts (int, optional): Time shifts for the data. Defaults to 0.
            lin_log_modes (dict, optional): A dictionary to store the lin/log state for each channel. Defaults to {}.
            lin_log_switches (dict, optional): A dictionary to store switch instances for each channel. Defaults to {}.
            persist_changes (bool, optional): If True, the state is saved to settings. Defaults to True.
            data_type (str, optional): The type of data plot being controlled (e.g., 'spectroscopy' or 'fitting'). Defaults to s.TAB_SPECTROSCOPY.
            fitting_popup (QWidget, optional): Reference to the fitting popup window if applicable. Defaults to None.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.app = window
        self.fitting_popup = fitting_popup
        self.channel = channel
        self.time_shifts = time_shifts
        self.lin_log_modes = lin_log_modes
        self.lin_log_switches = lin_log_switches
        self.persist_changes = persist_changes
        self.data_type = data_type
        self.setObjectName("lin-log")
        self.setStyleSheet(GUIStyles.set_lin_log_widget_style())
        self.setLayout(self.create_controls())

    def create_controls(self):
        """Creates and arranges the widgets for the lin/log control.

        This includes the 'LOG' and 'LIN' labels and the vertical switch.

        Returns:
            QVBoxLayout: The layout containing the control's widgets.
        """
        v_box = QVBoxLayout()
        v_box.setContentsMargins(0, 0, 0, 0)
        v_box.addSpacing(60)
        v_box.addWidget(QLabel("LOG"), alignment=Qt.AlignmentFlag.AlignCenter)
        view = self.create_switch_view()
        v_box.addWidget(view, alignment=Qt.AlignmentFlag.AlignCenter)
        v_box.addWidget(QLabel("LIN"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.lin_log_switches[self.channel] = view.scene().items()[0].widget()
        return v_box

    def create_switch_view(self):
        """Creates the QGraphicsView that holds the rotated switch control.

        Returns:
            QGraphicsView: The view containing the rotated switch.
        """
        scene = QGraphicsScene()
        proxy = QGraphicsProxyWidget()
        switch_checked = self.lin_log_modes.get(self.channel, "LIN") == "LIN"
        switch_width = 50 if len(self.app.plots_to_show) > 3 else 100
        switch = SwitchControl(
            active_color="#f72828",
            unchecked_color="#f72828",
            width=switch_width,
            height=28,
            checked=switch_checked,
        )
        switch.toggled.connect(lambda state: self.on_lin_log_changed(state))
        proxy.setWidget(switch)
        scene.addItem(proxy)
        proxy.setTransform(QTransform().rotate(90))
        view = QGraphicsView(scene)
        switch.setStyleSheet("background-color: transparent")
        return view

    def on_lin_log_changed(self, state):
        """Handles the state change of the lin/log switch.

        Args:
            state (bool): The new state of the switch (True for LIN, False for LOG).
        """
        self.lin_log_modes[self.channel] = "LIN" if state else "LOG"
        if self.persist_changes:
            self.app.settings.setValue(
                s.SETTINGS_LIN_LOG_MODE, json.dumps(self.lin_log_modes)
            )
        if self.data_type == s.TAB_SPECTROSCOPY:
            self.on_spectroscopy_lin_log_changed(state)
        if self.data_type == s.TAB_FITTING:
            self.on_fitting_lin_log_changed(state)    
            

    def on_spectroscopy_lin_log_changed(self, state):
        """Updates the spectroscopy plot to reflect the new lin/log scale.

        Args:
            state (bool): The new state of the switch (True for LIN, False for LOG).
        """
        from core.plots_controller import PlotsController
        time_shifts = self.app.time_shifts[self.channel] if self.channel in self.app.time_shifts else 0  
        decay_curve = self.app.decay_curves[self.app.tab_selected][self.channel]
        decay_widget = self.app.decay_widgets[self.channel]
        x, _ = decay_curve.getData()
        cached_decay_values = self.app.cached_decay_values[self.app.tab_selected][
            self.channel
        ]
        if state:
            ticks, y_data = LinLogControl.calculate_lin_mode(
                cached_decay_values
            )
            decay_widget.showGrid(x=False, y=False)
        else:
            ticks, y_data, _ = LinLogControl.calculate_log_mode(
                cached_decay_values
            )
            decay_widget.showGrid(x=False, y=True, alpha=0.3)
        y = np.roll(y_data, time_shifts)
        decay_curve.setData(x, y)
        decay_widget.getAxis("left").setTicks([ticks])
        PlotsController.set_plot_y_range(decay_widget)


    def on_fitting_lin_log_changed(self, state):
        """Updates the fitting plot to reflect the new lin/log scale.

        Args:
            state (bool): The new state of the switch (True for LIN, False for LOG).
        """
        from core.plots_controller import PlotsController
        if self.fitting_popup is not None:
            # Update mode
            if state:
                self.fitting_popup.lin_log_modes[self.channel] = "LIN"
            else:
                self.fitting_popup.lin_log_modes[self.channel] = "LOG"
            
            # Check if multi-file mode
            is_multi_file = (self.fitting_popup.read_mode and 
                           self.fitting_popup.preloaded_fitting and 
                           len(self.fitting_popup.preloaded_fitting) > 1 and 
                           'file_index' in self.fitting_popup.preloaded_fitting[0])
            
            if is_multi_file:
                # Multi-file: re-call update method
                plot_widget = self.fitting_popup.plot_widgets[self.channel]
                residuals_widget = self.fitting_popup.residuals_widgets[self.channel]
                fitted_params_text = self.fitting_popup.fitted_params_labels[self.channel]
                self.fitting_popup._update_plot_multiple_files(
                    self.fitting_popup.preloaded_fitting, 
                    self.channel, 
                    plot_widget, 
                    residuals_widget, 
                    fitted_params_text
                )
            else:
                # Single file: original logic
                plot_widget = self.fitting_popup.plot_widgets[self.channel]
                plot_widget.clear()
                counts_x = self.fitting_popup.cached_counts_data[self.channel]["x"]
                counts_y = self.fitting_popup.cached_counts_data[self.channel]["y"]
                fitted_x = self.fitting_popup.cached_fitted_data[self.channel]["x"]
                fitted_y = self.fitting_popup.cached_fitted_data[self.channel]["y"]
                if state:
                    _, y_data = LinLogControl.calculate_lin_mode(counts_y) 
                    y_ticks, fitted_data = LinLogControl.calculate_lin_mode(fitted_y)  
                else:
                    y_data, __, _ = LinLogControl.calculate_log_ticks(counts_y) 
                    fitted_data, y_ticks, _ = LinLogControl.calculate_log_ticks(fitted_y)    
                axis = plot_widget.getAxis("left")    
                axis.setTicks([y_ticks])
                plot_widget.clear()
                legend = plot_widget.addLegend(offset=(0, 20))
                legend.setParent(plot_widget)
                # Fitted Curve
                plot_widget.plot(
                    counts_x,
                    y_data,
                    pen=None,
                    symbol="o",
                    symbolSize=4,
                    symbolBrush="#04f7ee",
                    name="Counts",
                )
                plot_widget.plot(
                    fitted_x,
                    fitted_data,
                    pen=pg.mkPen("#f72828", width=2),
                    name="Fitted curve",
                )
                PlotsController.set_plot_y_range(plot_widget)

    @staticmethod
    def calculate_lin_mode(y_values):
        """Calculates ticks for linear mode and returns original y-values.

        Args:
            y_values (np.ndarray): The input y-axis data.

        Returns:
            tuple: A tuple containing:
                - list: A list of (value, label) tuples for ticks.
                - np.ndarray: The original y_values.
        """
        max_value = max(y_values)
        yticks_values = LinLogControl.calculate_lin_ticks(max_value, 10)
        ticks = [(value, str(int(value))) for value in yticks_values]
        return ticks, y_values

    @staticmethod
    def calculate_log_mode(y_values):
        """Calculates log-transformed values and ticks for logarithmic mode.

        Args:
            y_values (np.ndarray): The input y-axis data.

        Returns:
            tuple: A tuple containing:
                - list: A list of (value, label) tuples for ticks.
                - np.ndarray: The log-transformed y-values.
                - float: The maximum exponent value.
        """
        log_values, exponents_lin_space_int, max_value = (
            LinLogControl.set_decay_log_mode(y_values)
        )
        ticks = [
            (i, LinLogControl.format_power_of_ten(i))
            for i in exponents_lin_space_int
        ]
        return ticks, log_values, max_value

    @staticmethod
    def calculate_lin_ticks(max_value, max_ticks):
        """Calculates tick values for a linear scale axis.

        Args:
            max_value (float): The maximum value on the axis.
            max_ticks (int): The maximum number of ticks desired.

        Returns:
            np.ndarray: An array of tick values.
        """
        if max_value <= 0:
            return [0]
        step = 10 ** (np.floor(np.log10(max_value)) - 1)
        ticks = np.arange(0, max_value + step, step)
        while len(ticks) > max_ticks:
            step *= 2
            ticks = np.arange(0, max_value + step, step)
        return ticks

    @staticmethod
    def calculate_log_ticks(data):
        """Calculates logarithmic values and corresponding tick labels for a dataset.

        Args:
            data (np.ndarray): The input data array.

        Returns:
            tuple: A tuple containing:
                - np.ndarray: The log-transformed data values.
                - list: A list of (position, label) tuples for ticks.
                - float: The maximum exponent value from the data.
        """
        log_values, exponents_lin_space_int, max_value = (
            LinLogControl.set_decay_log_mode(data)
        )
        ticks = [
            (i, LinLogControl.format_power_of_ten(i))
            for i in exponents_lin_space_int
        ]
        return log_values, ticks, max_value

    @staticmethod
    def set_decay_log_mode(values):
        """
        Converts data values to a logarithmic scale for plotting.

        This method handles non-positive values by replacing them with a small
        positive number (1e-9) before taking the base-10 logarithm.

        Args:
            values (np.ndarray): The input data array.

        Returns:
            tuple: A tuple containing:
                - np.ndarray: The log-transformed values.
                - np.ndarray: An array of integers for tick positions.
                - int: The maximum integer exponent.
        """
        values = np.array(values)
        values = np.where(values <= 0, 1e-9, values)
        log_values = np.log10(values)
        log_values = np.where(log_values < 0, -0.1, log_values)
        exponents_int = log_values.astype(int)
        exponents_lin_space_int = np.linspace(
            0, max(exponents_int), len(exponents_int)
        ).astype(int)
        return log_values, exponents_lin_space_int, max(exponents_int)

    @staticmethod
    def format_power_of_ten(i):
        """Formats an integer as a power of 10 using Unicode superscript characters.

        Args:
            i (int): The integer exponent.

        Returns:
            str: The formatted string (e.g., "10²" for i=2, or "0" for i < 0).
        """
        return "0" if i < 0 else f"10{''.join(s.UNICODE_SUP[c] for c in str(i))}"

    @staticmethod
    def set_lin_log_switches_enable_mode(lin_log_switches, enabled):
        """Enables or disables all lin/log switch controls.

        Args:
            lin_log_switches (dict): A dictionary of switch controls.
            enabled (bool): True to enable the switches, False to disable.
        """
        for switch in lin_log_switches.values():
            switch.setEnabled(enabled)
