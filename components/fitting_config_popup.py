import json
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
from utils.export_data import ExportData
from components.gradient_text import GradientText
from utils.gui_styles import GUIStyles
from utils.layout_utilities import clear_layout_widgets, draw_layout_separator
from components.lin_log_control import LinLogControl
from utils.resource_path import resource_path
from utils.fitting_utilities import (
    convert_fitting_result_into_json_serializable_item,
    fit_decay_curve,
)
import settings.settings as s

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
    """
    A popup window for configuring, running, and viewing fluorescence decay fitting.

    This widget displays decay curves for multiple channels, allows users to
    select a Region of Interest (ROI) for fitting, starts the fitting process,
    and displays the results including the fitted curve, residuals, and calculated parameters.
    """
    def __init__(
        self,
        window,
        data,
        preloaded_fitting=None,
        read_mode=False,
        save_plot_img=False,
        y_data_shift=0,
        laser_period_ns=0
    ):
        """
        Initializes the FittingDecayConfigPopup.

        Args:
            window: The main application window instance.
            data (list): A list of dictionaries, each containing data for one channel's decay curve.
            preloaded_fitting (dict, optional): Pre-existing fitting data to display. Defaults to None.
            read_mode (bool, optional): If True, the popup is in a view-only mode. Defaults to False.
            save_plot_img (bool, optional): If True, shows a button to save the plot as an image. Defaults to False.
            y_data_shift (int, optional): A global time shift to apply to the y-data. Defaults to 0.
            laser_period_ns (float, optional): The laser period in nanoseconds, used for plot limits. Defaults to 0.
        """
        super().__init__()
        self.app = window
        self.data = data
        self.y_data_shift = y_data_shift
        self.laser_period_ns = laser_period_ns
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
        self.roi_warnings = {}
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
        self.app.widgets[s.FITTING_POPUP] = self

    def initialize_dicts_for_plot_cached_data(self):
        """Initializes dictionaries to cache plot data for each channel."""
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
        """
        Creates the top control bar with title and action buttons.

        Returns:
            QWidget: The widget containing the control bar.
        """
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
            colors=[(0.7, "#1E90FF"), (1.0, s.PALETTE_RED_1)],
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
        self.export_img_btn = ExportPlotImageButton(app=self.app)
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
        """
        Creates the layout for the loading indicator (text and GIF).

        Returns:
            QHBoxLayout: The layout containing the loading widgets.
        """
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
        """Initiates the fitting process in a background worker thread."""
        clear_layout_widgets(self.errors_layout)
        self.loading_text.setVisible(True)
        self.gif_label.setVisible(True)
        self.worker = FittingWorker(
            self.data,
            self.roi_checkboxes,
            self.cut_data_x,
            self.cut_data_y,
            self.y_data_shift,
        )
        self.worker.fitting_done.connect(self.handle_fitting_done)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()

    def process_fitting_results(self, results):
        """
        Processes and displays the fitting results received from the worker.

        Args:
            results (list): A list of result dictionaries from the fitting process.
        """
        self.fitting_results = results
        for result in results:
            if "error" in result:
                title = (
                    "Channel " + str(result["channel"] + 1) if "channel" in result else ""
                )
                self.display_error(result["error"], title)
            else:
                channel = next(
                    (
                        item["channel_index"]
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
        """
        Slot to handle the successful completion of the fitting process.

        Args:
            results (list): The list of fitting results from the worker.
        """
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
        """
        Slot to handle errors that occurred during the fitting process.

        Args:
            error_message (str): The error message from the worker.
        """
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)
        print(f"Error: {error_message}")
        self.display_error(error_message, "")

    def display_spectroscopy_curve(self, plot_widget, channel):
        """
        Displays the initial raw spectroscopy curve on a plot.

        Args:
            plot_widget (pg.PlotWidget): The widget to plot on.
            channel (int): The channel index of the data to display.

        Returns:
            tuple: A tuple containing the x and y data arrays that were plotted.
        """
        data = [d for d in self.data if d["channel_index"] == channel]
        y = np.roll(data[0]["y"], data[0]["time_shift"])
        plot_widget.plot(data[0]["x"], y, pen=pg.mkPen("#f72828", width=2))
        return data[0]["x"], y

    def display_plot(self, title, channel, index):
        """
        Creates and displays the entire plot area for a single channel.

        This includes the main plot, residuals plot, title, and controls like ROI and Lin/Log.

        Args:
            title (str): The title for the plot.
            channel (int): The channel index for the data.
            index (int): The sequential index of the plot, used for grid layout.
        """
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

        container = QHBoxLayout()
        # LIN LOG
        lin_log_container = QVBoxLayout()
        lin_log_widget = LinLogControl(
            self.app,
            channel,
            time_shifts=0,
            lin_log_modes=self.lin_log_modes,
            persist_changes=False,
            data_type=s.TAB_FITTING,
            fitting_popup=self,
            lin_log_switches=self.lin_log_switches,
        )
        lin_log_container.addWidget(lin_log_widget)
        lin_log_container.addStretch(1)
        container.addLayout(lin_log_container, 1)
        charts_layout = QVBoxLayout()
        warning_layout = QHBoxLayout()
        self.roi_warnings[channel] = QLabel("")
        self.roi_warnings[channel].setWordWrap(True)
        self.roi_warnings[channel].setStyleSheet(
            "color: #eed202; font-family: Montserrat; font-size: 14px; margin-top: 10px; margin-bottom: 10px;"
        )
        self.roi_warnings[channel].setVisible(False)
        warning_layout.addWidget(self.roi_warnings[channel])
        charts_layout.addLayout(warning_layout)
        # Fitted curve
        plot_widget = pg.PlotWidget()
        plot_widget.setMinimumHeight(250)
        plot_widget.setMaximumHeight(300)
        plot_widget.setBackground("#0a0a0a")
        plot_widget.setLabel("left", "Counts", color="white")
        plot_widget.setLabel("bottom", "Time", color="white")
        plot_widget.getAxis("left").setPen("white")
        plot_widget.getAxis("bottom").setPen("white")
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        margin = 0.5
        plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
        plot_widget.setLimits(xMin=0 - margin, xMax=self.laser_period_ns + margin)        
        if not (self.read_mode):
            # Spectroscopy curve
            x, y = self.display_spectroscopy_curve(plot_widget, channel)
            # Roi selection
            roi = pg.LinearRegionItem([2, 8])
            result = self.get_saved_roi(channel)
            if result is not None:
                min_x, max_x = result
                roi.setRegion([min_x, max_x])
                self.set_roi_mask(roi, x, y, channel)
            roi.setVisible(False)    
            roi.sigRegionChanged.connect(
                lambda: self.on_roi_selection_changed(roi, x, y, channel)
            )
            roi.sigRegionChangeFinished.connect(
                lambda: self.limit_roi_bounds(roi)
            )            
            self.roi_items[channel] = roi
            plot_widget.addItem(roi)
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
        charts_layout.addWidget(plot_widget)
        charts_layout.addWidget(residuals_widget)
        container.addLayout(charts_layout, 11)
        layout.addLayout(container, stretch=2)
        fitted_params_text = QLabel("")
        fitted_params_text.setStyleSheet("color: #cecece; font-family: Montserrat;")
        charts_layout.addWidget(fitted_params_text)
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
        """
        Updates a channel's plot with the fitting results.

        Args:
            result (dict): The fitting result dictionary for the channel.
            channel (int): The channel index to update.
        """
        from core.plots_controller import PlotsController
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
        PlotsController.set_plot_y_range(plot_widget)
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
        """
        Adds a chart widget to the main grid layout.

        Args:
            chart_widget (QWidget): The widget to add.
            index (int): The sequential index to determine the position in the grid.
        """
        col_length = 1
        if len(self.data) > 4:
            col_length = 4
        else:
            col_length = len(self.data)
        self.plot_layout.addWidget(
            chart_widget, index // col_length, index % col_length
        )

    def display_error(self, error_message, title):
        """
        Displays an error message in the UI.

        Args:
            error_message (str): The error message to display.
            title (str): A title for the error (e.g., the channel name).
        """
        self.error_label = QLabel(f"Error {title}: {error_message}")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.error_label.setStyleSheet(
            f"font-size: 20px; color: red; background-color: {DARK_THEME_BG_COLOR}; margin-left: 10px;"
        )
        self.errors_layout.addWidget(self.error_label)
        
    def get_saved_roi(self, channel):
        """
        Retrieves the saved Region of Interest (ROI) for a channel from settings.

        Args:
            channel (int): The channel index.

        Returns:
            tuple or None: The (min, max) tuple for the ROI, or None if not found.
        """
        if channel in self.app.roi:
            return self.app.roi[channel]
        else:
            return None

    def on_roi_selection_changed(self, roi, x, y, channel):
        """
        Callback for when the ROI selection is changed by the user.

        Args:
            roi (pg.LinearRegionItem): The ROI item that was changed.
            x (np.ndarray): The x-data array for the plot.
            y (np.ndarray): The y-data array for the plot.
            channel (int): The channel index.
        """
        self.set_roi_mask(roi, x, y, channel)
        self.app.settings.setValue(s.SETTINGS_ROI, json.dumps(self.app.roi))    
        
    def limit_roi_bounds(self, roi):
        """
        Ensures the ROI selection does not go beyond the plot's x-axis limits.

        Args:
            roi (pg.LinearRegionItem): The ROI item to check.
        """
        min_val, max_val = roi.getRegion()
        min_limit = 0
        max_limit = self.laser_period_ns
        if min_val < min_limit:
            min_val = min_limit
        if max_val > max_limit:
            max_val = max_limit 
        roi.setRegion([min_val, max_val])             
        
    def set_roi_mask(self, roi, x, y, channel):
        """
        Applies the ROI to the data, storing the "cut" data for fitting.

        Args:
            roi (pg.LinearRegionItem): The ROI item defining the region.
            x (np.ndarray): The full x-data array.
            y (np.ndarray): The full y-data array.
            channel (int): The channel index.
        """
        if not roi.isVisible():
            return
        min_x, max_x = roi.getRegion()
        mask = (x >= min_x) & (x <= max_x)
        selected_x = x[mask]
        selected_y = y[mask]
        self.cut_data_x[channel] = selected_x
        self.cut_data_y[channel] = selected_y
        self.app.roi[channel] = (min_x, max_x)        
                

    def create_roi_checkbox(self, channel):
        """
        Creates the 'ROI' checkbox for a specific channel.

        Args:
            channel (int): The channel index.

        Returns:
            QCheckBox: The created checkbox widget.
        """
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
        """
        Callback for when the ROI checkbox state changes. Shows/hides the ROI tool.

        Args:
            checked (bool): The new state of the checkbox.
            channel (int): The channel index.
        """
        if checked:
            self.roi_warnings[channel].setText(
                "Please select a significant portion of the curve that includes points from both the rising edge, the peak, and the falling edge for an accurate fit. Insufficient data may lead to unreliable fitting results."
            )
            self.roi_warnings[channel].setVisible(True)
        else:
            self.roi_warnings[channel].setVisible(False)
            self.roi_warnings[channel].setText("")
        if channel in self.roi_items:
            self.roi_items[channel].setVisible(checked)

    def set_roi_checkboxes_visibility(self, visible):
        """
        Shows or hides all ROI-related checkboxes and warning labels.

        Args:
            visible (bool): True to show, False to hide.
        """
        for ch, widget in self.roi_checkboxes.items():
            if widget is not None:
                widget.setVisible(visible)
        for ch, widget in self.roi_warnings.items():
            if widget is not None:
                widget.setVisible(visible)       

    def export_fitting_data(self):
        """Exports the fitting results to files."""
        parsed_fitting_results = convert_fitting_result_into_json_serializable_item(
            self.fitting_results
        )
        ExportData.save_fitting_data(parsed_fitting_results, self, self.app)

    def reset(self):
        """Resets the popup to its initial state, clearing all plots and results."""
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
        """Centers the popup window on the current screen."""
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
        """
        Determines which screen the mouse cursor is currently on.

        Returns:
            int: The screen number, or -1 if not found.
        """
        cursor_pos = QCursor.pos()
        screens = QGuiApplication.screens()
        for screen_number, screen in enumerate(screens):
            if screen.geometry().contains(cursor_pos):
                return screen_number
        return -1


class FittingWorker(QThread):
    """
    A worker thread to perform the decay curve fitting in the background.

    This prevents the GUI from freezing during the potentially long fitting process.

    Signals:
        fitting_done (pyqtSignal): Emitted when fitting is complete, carrying a list of results.
        error_occurred (pyqtSignal): Emitted if an error occurs during fitting.
    """
    fitting_done = pyqtSignal(
        list
    )  # Emit a list of tuples (chart title (channel),  fitting result)
    error_occurred = pyqtSignal(str)  # Emit an error message

    def __init__(
        self, data, roi_checkboxes, cut_data_x, cut_data_y, y_data_shift, parent=None
    ):
        """
        Initializes the FittingWorker.

        Args:
            data (list): The list of channel data to be fitted.
            roi_checkboxes (dict): A dictionary of ROI checkboxes to check if ROI is active.
            cut_data_x (dict): A dictionary of x-data, cut by ROI.
            cut_data_y (dict): A dictionary of y-data, cut by ROI.
            y_data_shift (int): A global time shift to apply to the data.
            parent (QObject, optional): The parent object. Defaults to None.
        """
        super().__init__(parent)
        self.data = data
        self.roi_checkboxes = roi_checkboxes
        self.cut_data_x = cut_data_x
        self.cut_data_y = cut_data_y
        self.y_data_shift = y_data_shift

    def get_data_point(self, data_point, channel):
        """
        Gets the appropriate data (full or ROI-cut) for a given channel.

        Args:
            data_point (dict): The full data dictionary for the channel.
            channel (int): The channel index.

        Returns:
            tuple: A tuple of (x_data, y_data) arrays for fitting.
        """
        if channel in self.roi_checkboxes and self.roi_checkboxes[channel].isChecked():
            return self.cut_data_x[channel], self.cut_data_y[channel]
        else:
            return data_point["x"], data_point["y"]

    def run(self):
        """
        The main execution method of the thread.

        Iterates through the data for each channel, performs the fitting,
        and emits the results or an error.
        """
        results = []
        for data_point in self.data:
            try:
                x, y = self.get_data_point(data_point, data_point["channel_index"])
                result = fit_decay_curve(
                    x, y, data_point["channel_index"], y_shift=data_point["time_shift"]
                )
                results.append((result))
            except TimeoutError as te:
                self.error_occurred.emit(f"An error occurred: {str(te)}")
                return                    
            except Exception as e:
                print(e)
                self.error_occurred.emit(f"An error occurred: {str(e)}")
                return
        self.fitting_done.emit(results)
