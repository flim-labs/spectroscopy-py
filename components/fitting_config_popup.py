import os
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import QCursor, QGuiApplication, QIcon, QMovie
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QGridLayout,
    QCheckBox,
)
from components.export_data import ExportData
from components.gradient_text import GradientText
from components.gui_styles import GUIStyles
from components.layout_utilities import clear_layout_widgets, draw_layout_separator
from components.lin_log_control import LinLogControl
from components.resource_path import resource_path
from fit_decay_curve import convert_fitting_result_into_json_serializable_item, fit_decay_curve
from settings import FITTING_POPUP, PALETTE_RED_1, TAB_FITTING

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

# Define style constants
DARK_THEME_BG_COLOR = "#141414"
DARK_THEME_TEXT_COLOR = "#cecece"
DARK_THEME_TEXT_FONT_SIZE = "20px"
DARK_THEME_HEADER_FONT_SIZE = "20px"
DARK_THEME_FONT_FAMILY = "Montserrat"
DARK_THEME_RADIO_BTN_STYLE = (
    f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
)
DARK_THEME_LABEL_STYLE = (
    f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
)


class FittingDecayConfigPopup(QWidget):
    def __init__(
        self, window, data, preloaded_fitting=None, read_mode=False, save_plot_img=False
    ):
        super().__init__()
        self.app = window
        self.data = data
        self.preloaded_fitting = preloaded_fitting
        self.read_mode = read_mode
        self.save_plot_img = save_plot_img
        self.setWindowTitle("Spectroscopy - Fitting Decay Config")
        self.setWindowIcon(QIcon(resource_path("assets/spectroscopy-logo.png")))
        self.setStyleSheet(
            f"background-color: {DARK_THEME_BG_COLOR}; color: {DARK_THEME_TEXT_COLOR}"
        )
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_bar = self.create_controls_bar()
        self.main_layout.addWidget(self.controls_bar)
        self.main_layout.addSpacing(10)
        self.loading_row = self.create_loading_row()
        self.main_layout.addLayout(self.loading_row)
        self.main_layout.addSpacing(10)
        self.fitting_results = []
        self.plot_widgets = {}
        self.residuals_widgets = {}
        self.fitted_params_labels = {}
        self.lin_log_modes = {}
        self.lin_log_switches = {}
        self.roi_checkboxes = {}
        self.roi_items = {}
        self.cut_data_x = {}
        self.cut_data_y = {}
        self.cached_counts_data = {}
        self.cached_fitted_data = {}
        self.initialize_dicts_for_plot_cached_data()
        # Create a scroll area for the plots
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #141414; border: none;")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.scroll_widget = QWidget()
        self.plot_layout = QGridLayout(self.scroll_widget)
        self.plot_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        for index, data_point in enumerate(self.data):
            self.display_plot(data_point["title"], data_point["channel_index"], index)   
        if self.read_mode and self.preloaded_fitting:
            self.process_fitting_results(self.preloaded_fitting)    
        self.scroll_widget.setLayout(self.plot_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addSpacing(10)
        self.errors_layout = QVBoxLayout()
        self.main_layout.addLayout(self.errors_layout)
        self.main_layout.addSpacing(20)
        self.setLayout(self.main_layout)
        self.app.widgets[FITTING_POPUP] = self

    def initialize_dicts_for_plot_cached_data(self):
        for index, item in enumerate(self.data):
            channel_index = item["channel_index"]
            if channel_index not in self.cached_counts_data:
                self.cached_counts_data[channel_index] = {"y": [], "x": []}
            if channel_index not in self.cached_fitted_data:
                self.cached_fitted_data[channel_index] = {"y": [], "x": []}
            self.cached_counts_data[channel_index]["y"] = []
            self.cached_counts_data[channel_index]["x"] = []
            self.cached_fitted_data[channel_index]["y"] = []
            self.cached_fitted_data[channel_index]["x"] = []

    def create_controls_bar(self):
        from components.buttons import ExportPlotImageButton
        controls_bar_widget = QWidget()
        controls_bar_widget.setStyleSheet("background-color: #1c1c1c")
        controls_bar = QVBoxLayout()
        controls_bar.setContentsMargins(0, 20, 0, 0)
        controls_row = QHBoxLayout()
        controls_row.setAlignment(Qt.AlignmentFlag.AlignBaseline)
        fitting_title = GradientText(
            self,
            text="INTENSITY DECAY FITTING",
            colors=[(0.7, "#1E90FF"), (1.0, PALETTE_RED_1)],
            stylesheet=GUIStyles.set_main_title_style(),
        )
        controls_row.addSpacing(10)
        controls_row.addWidget(fitting_title)
        controls_row.addSpacing(20)
        # Export fitting data btn
        self.export_fitting_btn = QPushButton("EXPORT")
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:  #11468F; font-weight: bold; padding: 8px; border-radius: 4px;"
        )
        self.export_fitting_btn.setFixedHeight(55)
        self.export_fitting_btn.setFixedWidth(90)
        self.export_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_fitting_btn.clicked.connect(self.export_fitting_data)
        self.export_fitting_btn.setEnabled(False)
        # Start fitting btn
        start_fitting_btn = QPushButton("START FITTING")
        start_fitting_btn.setObjectName("btn")
        GUIStyles.set_start_btn_style(start_fitting_btn)
        start_fitting_btn.setFixedHeight(55)
        start_fitting_btn.setFixedWidth(150)
        start_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_fitting_btn.clicked.connect(self.start_fitting)
        # Reset btn
        reset_btn = QPushButton("RESET")
        reset_btn.setObjectName("btn")
        GUIStyles.set_stop_btn_style(reset_btn)
        reset_btn.setFixedHeight(55)
        reset_btn.setFixedWidth(150)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset)  
        # Export plot img btn
        self.export_img_btn = ExportPlotImageButton(app = self.app)  
        self.export_img_btn.setVisible(False)    
        controls_row.addStretch(1)
        if not self.read_mode:
            controls_row.addWidget(self.export_fitting_btn)
            controls_row.addSpacing(10)
            controls_row.addWidget(start_fitting_btn)
            controls_row.addSpacing(10)
            controls_row.addWidget(reset_btn)
            controls_row.addSpacing(20)
        if self.save_plot_img:
            controls_row.addWidget(self.export_img_btn) 
            controls_row.addSpacing(20)         
        controls_bar.addLayout(controls_row)
        controls_bar.addWidget(draw_layout_separator())
        controls_bar_widget.setLayout(controls_bar)
        return controls_bar_widget

    def create_loading_row(self):
        loading_row = QHBoxLayout()
        loading_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_row.addSpacing(20)
        self.loading_text = QLabel("Processing data...")
        self.loading_text.setStyleSheet(
            "font-family: Montserrat; font-size: 18px; font-weight: bold; color: #50b3d7"
        )
        loading_gif = QMovie(resource_path("assets/loading.gif"))
        self.gif_label = QLabel()
        self.gif_label.setMovie(loading_gif)
        loading_gif.setScaledSize(QSize(36, 36))
        loading_gif.start()
        loading_row.addWidget(self.loading_text)
        loading_row.addSpacing(5)
        loading_row.addWidget(self.gif_label)
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)
        return loading_row

    def start_fitting(self):
        clear_layout_widgets(self.errors_layout)  
        self.loading_text.setVisible(True)
        self.gif_label.setVisible(True)
        self.worker = FittingWorker(
            self.data, self.roi_checkboxes, self.cut_data_x, self.cut_data_y
        )
        self.worker.fitting_done.connect(self.handle_fitting_done)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()
    
    def process_fitting_results(self, results):
        self.fitting_results = results
        for result in results:
                if "error" in result:
                    title = "Channel " + result["channel"] + 1
                    self.display_error(result["error"], title)
                else:
                    channel = next(
                        (
                            result["channel"]
                            for item in self.data
                            if item["channel_index"] == result["channel"]
                        ),
                        None,
                    )
                    if channel is not None:
                        self.update_plot(result, channel)
        # Hide roi checkboxes
        self.set_roi_checkboxes_visibility(False) 
        LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, True)  
        if self.save_plot_img:
            self.export_img_btn.set_data_to_save(results) 
            self.export_img_btn.setVisible(True)         
        
    @pyqtSlot(list)
    def handle_fitting_done(self, results):
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)
        # Process results
        self.process_fitting_results(results) 
        # Enable and style the export button
        self.export_fitting_btn.setEnabled(True)
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:#11468F; background-color: white; font-weight: bold; padding: 8px; border-radius: 4px;"
        )

    @pyqtSlot(str)
    def handle_error(self, error_message):
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)
        print(f"Error: {error_message}")
        self.display_error(error_message, "")

    def display_spectroscopy_curve(self, plot_widget, channel):
        data = [d for d in self.data if d["channel_index"] == channel]
        plot_widget.plot(data[0]["x"], data[0]["y"], pen=pg.mkPen("#f72828", width=2))
        return data[0]["x"], data[0]["y"]

    def display_plot(self, title, channel, index):
        layout = QVBoxLayout()
        title_layout = QHBoxLayout()
        chart_title = QLabel(title)
        chart_title.setStyleSheet(
            "color: #cecece; font-size: 18px; font-family: Montserrat; text-align: center;"
        )
        title_layout.addStretch()
        title_layout.addWidget(chart_title)
        if not (self.read_mode):
            title_layout.addStretch()
            roi_checkbox = self.create_roi_checkbox(channel)
            title_layout.addWidget(roi_checkbox)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(title_layout)
        # Fitted curve
        fitted_curve_container = QHBoxLayout()
        # LIN LOG
        lin_log_widget = LinLogControl(
            self.app,
            channel,
            time_shifts=0,
            lin_log_modes=self.lin_log_modes,
            persist_changes=False,
            data_type=TAB_FITTING,
            fitting_popup=self,
            lin_log_switches=self.lin_log_switches,
        )
        plot_widget = pg.PlotWidget()
        plot_widget.setMinimumHeight(250)
        plot_widget.setMaximumHeight(300)
        plot_widget.setBackground("#0a0a0a")
        plot_widget.setLabel("left", "Counts", color="white")
        plot_widget.setLabel("bottom", "Time", color="white")
        plot_widget.getAxis("left").setPen("white")
        plot_widget.getAxis("bottom").setPen("white")
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        if not (self.read_mode):
            # Spectroscopy curve
            x, y = self.display_spectroscopy_curve(plot_widget, channel)
            # Roi selection
            roi = pg.LinearRegionItem([2, 8])
            roi.setVisible(False)
            roi.sigRegionChanged.connect(
                lambda: self.on_roi_selection_changed(roi, x, y, channel)
            )
            self.roi_items[channel] = roi
            plot_widget.addItem(roi)
        fitted_curve_container.addWidget(lin_log_widget, 1)
        fitted_curve_container.addWidget(plot_widget, 11)
        # Residuals
        residuals_widget = pg.PlotWidget()
        residuals_widget.setMinimumHeight(150)
        residuals_widget.setMaximumHeight(200)
        residuals_widget.setBackground("#0a0a0a")
        residuals_widget.setLabel("left", "Residuals", color="white")
        residuals_widget.setLabel("bottom", "Time", color="white")
        residuals_widget.getAxis("left").setPen("white")
        residuals_widget.getAxis("bottom").setPen("white")
        residuals_widget.showGrid(x=True, y=True, alpha=0.3)
        layout.addLayout(fitted_curve_container, stretch=2)
        layout.addWidget(residuals_widget, stretch=1)
        fitted_params_text = QLabel("")
        fitted_params_text.setStyleSheet("color: #cecece; font-family: Montserrat;")
        layout.addWidget(fitted_params_text)
        charts_wrapper = QWidget()
        charts_wrapper.setContentsMargins(10, 10, 10, 10)
        charts_wrapper.setObjectName("chart_wrapper")
        charts_wrapper.setLayout(layout)
        charts_wrapper.setStyleSheet(GUIStyles.chart_wrapper_style())
        self.add_chart_to_grid(charts_wrapper, index)
        self.plot_widgets[channel] = plot_widget
        self.residuals_widgets[channel] = residuals_widget
        self.fitted_params_labels[channel] = fitted_params_text
        LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, False)

    def update_plot(self, result, channel):
        plot_widget = self.plot_widgets[channel]
        residuals_widget = self.residuals_widgets[channel]
        fitted_params_text = self.fitted_params_labels[channel]
        truncated_x_values = result["x_values"][result["decay_start"] :]
        # Cache y values to handle lin/log change
        self.cached_counts_data[channel]["y"] = (
            np.array(result["y_data"]) * result["scale_factor"]
        )
        self.cached_counts_data[channel]["x"] = result["t_data"]
        self.cached_fitted_data[channel]["y"] = np.array(
            result["fitted_values"] * result["scale_factor"]
        )
        self.cached_fitted_data[channel]["x"] = truncated_x_values
        # Retrieve Y values based on active lin/log mode
        if channel not in self.lin_log_modes or self.lin_log_modes[channel] == "LIN":
            _, y_data = LinLogControl.calculate_lin_mode(
                self.cached_counts_data[channel]["y"]
            )
            y_ticks, fitted_data = LinLogControl.calculate_lin_mode(
                self.cached_fitted_data[channel]["y"]
            )
        else:
            y_data, __, _ = LinLogControl.calculate_log_ticks(
                self.cached_counts_data[channel]["y"]
            )
            fitted_data, y_ticks, _ = LinLogControl.calculate_log_ticks(
                self.cached_fitted_data[channel]["y"]
            )

        axis = plot_widget.getAxis("left")
        axis.setTicks([y_ticks])
        plot_widget.clear()
        legend = plot_widget.addLegend(offset=(0, 20))
        legend.setParent(plot_widget)
        # Fitted Curve
        plot_widget.plot(
            truncated_x_values,
            y_data,
            pen=None,
            symbol="o",
            symbolSize=4,
            symbolBrush="#04f7ee",
            name="Counts",
        )
        plot_widget.plot(
            result["t_data"],
            fitted_data,
            pen=pg.mkPen("#f72828", width=2),
            name="Fitted curve",
        )
        self.app.set_plot_y_range(plot_widget)
        # Residuals
        residuals = result["residuals"]  
        residuals_widget.clear()
        residuals_widget.plot(
            truncated_x_values, residuals, pen=pg.mkPen("#1E90FF", width=2)
        )
        residuals_widget.addLine(y=0, pen=pg.mkPen("w", style=Qt.PenStyle.DashLine))
        if len(fitted_params_text.text()) > 55:
            fitted_params_text.setWordWrap(True)
        fitted_params_text.setText(result["fitted_params_text"])

    def add_chart_to_grid(self, chart_widget, index):
        col_length = 1
        if len(self.data) > 4:
            col_length = 4
        else:
            col_length = len(self.data)
        self.plot_layout.addWidget(
            chart_widget, index // col_length, index % col_length
        )

    def display_error(self, error_message, title):
        self.error_label = QLabel(f"Error {title}: {error_message}")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.error_label.setStyleSheet(
            f"font-size: 20px; color: red; background-color: {DARK_THEME_BG_COLOR}; margin-left: 10px;"
        )
        self.errors_layout.addWidget(self.error_label)

    def on_roi_selection_changed(self, roi, x, y, channel):
        if not roi.isVisible():
            return
        min_x, max_x = roi.getRegion()
        mask = (x >= min_x) & (x <= max_x)
        selected_x = x[mask]
        selected_y = y[mask]
        self.cut_data_x[channel] = selected_x
        self.cut_data_y[channel] = selected_y

    def create_roi_checkbox(self, channel):
        checkbox = QCheckBox("ROI")
        checkbox.setStyleSheet(GUIStyles.set_checkbox_style())
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(
            lambda checked, channel=channel: self.on_roi_checkbox_state_changed(
                checked, channel
            )
        )
        self.roi_checkboxes[channel] = checkbox
        return checkbox

    def on_roi_checkbox_state_changed(self, checked: bool, channel: int):
        if channel in self.roi_items:
            self.roi_items[channel].setVisible(checked)

    def set_roi_checkboxes_visibility(self, visible):
        for ch, widget in self.roi_checkboxes.items():
            if widget is not None:
                widget.setVisible(visible)
    
    def export_fitting_data(self):
        parsed_fitting_results = convert_fitting_result_into_json_serializable_item(self.fitting_results)
        ExportData.save_fitting_config_json(parsed_fitting_results, self)           
                
    def reset(self):
        for ch, plot in self.plot_widgets.items():
            if plot:
                plot.clear()   
        for ch, plot in self.residuals_widgets.items():
            if plot:
                plot.clear() 
        clear_layout_widgets(self.errors_layout)  
        self.fitting_results.clear()      
        self.plot_widgets.clear()   
        self.residuals_widgets.clear()    
        self.fitted_params_labels.clear()    
        self.roi_items.clear()  
        self.cut_data_x.clear()   
        self.cut_data_y.clear()
        for ch, checkbox in self.roi_checkboxes.items():
            if checkbox:
                checkbox.setChecked(False)
        for index, data_point in enumerate(self.data):
            self.display_plot(data_point["title"], data_point["channel_index"], index)
        self.export_img_btn.setVisible(False)    
                

    def center_window(self):
        screen_number = self.get_current_screen()
        if screen_number == -1:
            screen = QGuiApplication.primaryScreen()
        else:
            screen = QGuiApplication.screens()[screen_number]

        screen_geometry = screen.geometry()
        frame_gm = self.frameGeometry()
        screen_center = screen_geometry.center()
        frame_gm.moveCenter(screen_center)
        self.move(frame_gm.topLeft())

    @staticmethod
    def get_current_screen():
        cursor_pos = QCursor.pos()
        screens = QGuiApplication.screens()
        for screen_number, screen in enumerate(screens):
            if screen.geometry().contains(cursor_pos):
                return screen_number
        return -1


class FittingWorker(QThread):
    fitting_done = pyqtSignal(
        list
    )  # Emit a list of tuples (chart title (channel),  fitting result)
    error_occurred = pyqtSignal(str)  # Emit an error message

    def __init__(self, data, roi_checkboxes, cut_data_x, cut_data_y, parent=None):
        super().__init__(parent)
        self.data = data
        self.roi_checkboxes = roi_checkboxes
        self.cut_data_x = cut_data_x
        self.cut_data_y = cut_data_y
    
    def get_data_point(self, data_point, channel):
        if channel in self.roi_checkboxes and self.roi_checkboxes[channel].isChecked():
            return self.cut_data_x[channel], self.cut_data_y[channel]
        else:
            return data_point["x"], data_point["y"]

    def run(self):
        results = []
        for data_point in self.data:
            try:
                x, y = self.get_data_point(data_point, data_point["channel_index"])
                result = fit_decay_curve(
                    x, y, data_point["channel_index"]
                )
                results.append((result))
            except Exception as e:
                self.error_occurred.emit(f"An error occurred: {str(e)}")
                return
        self.fitting_done.emit(results)
