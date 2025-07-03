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
from components.gui_styles import GUIStyles
from components.switch_control import SwitchControl
from settings import *


class LinLogControl(QWidget):
    def __init__(
        self,
        window,
        channel,
        time_shifts=0,
        lin_log_modes={},
        lin_log_switches = {},
        persist_changes=True,
        data_type=TAB_SPECTROSCOPY,
        fitting_popup = None,
        parent=None,
    ):
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
        self.lin_log_modes[self.channel] = "LIN" if state else "LOG"
        if self.persist_changes:
            self.app.settings.setValue(
                SETTINGS_LIN_LOG_MODE, json.dumps(self.lin_log_modes)
            )
        if self.data_type == TAB_SPECTROSCOPY:
            self.on_spectroscopy_lin_log_changed(state)
        if self.data_type == TAB_FITTING:
            self.on_fitting_lin_log_changed(state)    
            

    def on_spectroscopy_lin_log_changed(self, state):
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
        from core.plots_controller import PlotsController
        if self.fitting_popup is not None:
            plot_widget = self.fitting_popup.plot_widgets[self.channel]
            plot_widget.clear()
            counts_x = self.fitting_popup.cached_counts_data[self.channel]["x"]
            counts_y = self.fitting_popup.cached_counts_data[self.channel]["y"]
            fitted_x = self.fitting_popup.cached_fitted_data[self.channel]["x"]
            fitted_y = self.fitting_popup.cached_fitted_data[self.channel]["y"]
            if state:
                self.fitting_popup.lin_log_modes[self.channel] = "LIN"
                _, y_data = LinLogControl.calculate_lin_mode(counts_y) 
                y_ticks, fitted_data = LinLogControl.calculate_lin_mode(fitted_y)  
            else:
                self.fitting_popup.lin_log_modes[self.channel] = "LOG"  
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
        max_value = max(y_values)
        yticks_values = LinLogControl.calculate_lin_ticks(max_value, 10)
        ticks = [(value, str(int(value))) for value in yticks_values]
        return ticks, y_values

    @staticmethod
    def calculate_log_mode(y_values):
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
        return "0" if i < 0 else f"10{''.join(UNICODE_SUP[c] for c in str(i))}"

    @staticmethod
    def set_lin_log_switches_enable_mode(lin_log_switches, enabled):
        for switch in lin_log_switches.values():
            switch.setEnabled(enabled)
