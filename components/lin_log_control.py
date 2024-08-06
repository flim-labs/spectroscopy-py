import json
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QGraphicsView, QGraphicsScene, QGraphicsProxyWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTransform
from components.gui_styles import GUIStyles
from components.switch_control import SwitchControl
from settings import *


class SpectroscopyLinLogControl(QWidget):
    def __init__(self, window, channel, parent=None):
        super().__init__(parent)
        self.app = window
        self.channel = channel
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
        self.app.lin_log_switches[self.channel] = view.scene().items()[0].widget()
        return v_box

    def create_switch_view(self):
        scene = QGraphicsScene()
        proxy = QGraphicsProxyWidget()
        switch_checked = self.app.lin_log_mode.get(self.channel, "LIN") == "LIN"
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
        self.app.lin_log_mode[self.channel] = "LIN" if state else "LOG"
        time_shift = self.app.time_shifts[self.channel] if self.channel in self.app.time_shifts else 0
        self.app.settings.setValue(SETTINGS_LIN_LOG_MODE, json.dumps(self.app.lin_log_mode))
        decay_curve = self.app.decay_curves[self.app.tab_selected][self.channel]
        decay_widget = self.app.decay_widgets[self.channel]
        x, _ = decay_curve.getData()
        cached_decay_values = self.app.cached_decay_values[self.app.tab_selected][self.channel]
        if state:
            ticks, y_data = SpectroscopyLinLogControl.calculate_lin_mode(cached_decay_values)
            
            decay_widget.showGrid(x=False, y=False)
        else:
            ticks, y_data , _ = SpectroscopyLinLogControl.calculate_log_mode(cached_decay_values)
            decay_widget.showGrid(x=False, y=True, alpha=0.3)    
        y = np.roll(y_data, time_shift)    
        decay_curve.setData(x, y)
        decay_widget.getAxis("left").setTicks([ticks])
        self.app.set_plot_y_range(decay_widget,self.app.lin_log_mode[self.channel])
        

    @staticmethod
    def calculate_lin_mode(cached_decay_values):
        max_value = max(cached_decay_values) 
        yticks_values = SpectroscopyLinLogControl.calculate_lin_ticks(max_value, 10)
        ticks = [(value, str(int(value))) for value in yticks_values]
        return ticks, cached_decay_values

    @staticmethod
    def calculate_log_mode(cached_decay_values):
        log_values, exponents_lin_space_int, max_value = SpectroscopyLinLogControl.set_decay_log_mode(cached_decay_values)
        ticks = [(i, SpectroscopyLinLogControl.format_power_of_ten(i)) for i in exponents_lin_space_int]
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
        log_values, exponents_lin_space_int, max_value = SpectroscopyLinLogControl.set_decay_log_mode(data)
        ticks = [(i, SpectroscopyLinLogControl.format_power_of_ten(i)) for i in exponents_lin_space_int]
        return log_values, ticks, max_value

    @staticmethod
    def set_decay_log_mode(values):
        values = np.where(values == 0, 1e-9, values)
        log_values = np.log10(values)
        log_values = np.where(log_values < 0, -0.1, log_values)
        exponents_int = log_values.astype(int)
        exponents_lin_space_int = np.linspace(0, max(exponents_int), len(exponents_int)).astype(int)
        return log_values, exponents_lin_space_int, max(exponents_int)

    @staticmethod
    def format_power_of_ten(i):
        return "0" if i < 0 else f"10{''.join(UNICODE_SUP[c] for c in str(i))}"

    @staticmethod
    def set_lin_log_switches_enable_mode(app, enabled):
        for switch in app.lin_log_switches.values():
            switch.setEnabled(enabled)
