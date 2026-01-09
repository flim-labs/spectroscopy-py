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
        self.file_colors = ['#f72828', '#00FF00', '#FFA500', '#FF00FF']  # Red, Green, Orange, Magenta
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
        
        # Check if we have multiple files with file_index (read mode only)
        has_multiple_files = self.read_mode and self.preloaded_fitting and any('file_index' in r for r in self.preloaded_fitting if "error" not in r)
        
        if has_multiple_files:
            # Create single plot for multiple files comparison
            title = "Multi-File Comparison"
            # Initialize cached data for channel 0
            self.cached_counts_data[0] = {"y": [], "x": []}
            self.cached_fitted_data[0] = {"y": [], "x": []}
            self.display_plot(title, 0, 0)
        else:
            # Create plot for each channel (both acquire mode and single-file read mode)
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
        Groups results by file_index if multiple files are loaded.

        Args:
            results (list): A list of result dictionaries from the fitting process.
        """
        self.fitting_results = results
        
        # Add file_name and file_index to results if not present
        for result in results:
            if "error" not in result:
                if "file_index" not in result:
                    result["file_index"] = 0
                if "file_name" not in result or result.get("file_name") == "File 1":
                    # Try to get file name from reader_data
                    fitting_files = self.app.reader_data.get("fitting", {}).get("files", {}).get("spectroscopy", "")
                    if fitting_files:
                        if isinstance(fitting_files, str):
                            result["file_name"] = os.path.basename(fitting_files)
                        elif isinstance(fitting_files, list) and len(fitting_files) > 0:
                            file_idx = result.get("file_index", 0)
                            if file_idx < len(fitting_files):
                                result["file_name"] = os.path.basename(fitting_files[file_idx])
                            else:
                                result["file_name"] = os.path.basename(fitting_files[0])
        
        # Check if results have multiple different file_index values (true multi-file)
        valid_results = [r for r in results if "error" not in r]
        unique_file_indices = set(r.get('file_index', 0) for r in valid_results)
        has_multiple_files = len(unique_file_indices) > 1
        
        # In READ mode with multiple channels from same file, we could average them
        # But in ACQUIRE mode, we ALWAYS want separate plots per channel
        has_multiple_channels_same_file = self.read_mode and len(valid_results) > 1 and len(unique_file_indices) == 1
        
        if has_multiple_files or has_multiple_channels_same_file:
            # For multiple files OR multiple channels from same file (READ mode only), show aggregated result
            if has_multiple_channels_same_file:
                # Average the channels (READ mode only)
                averaged_result = self._average_channels(valid_results)
                if averaged_result and 0 in self.plot_widgets:
                    self.update_plot(averaged_result, 0)
                    # Store the averaged result for export instead of original results
                    if self.save_plot_img:
                        self.export_img_btn.set_data_to_save([averaged_result])
                        self.export_img_btn.setVisible(True)
            else:
                # Multiple files case (READ mode)
                if valid_results:
                    # Check if channel 0 plot exists (should have been created in __init__ for multi-file mode)
                    if 0 in self.plot_widgets:
                        self.update_plot(valid_results, 0)
                        # Set data for export
                        if self.save_plot_img:
                            self.export_img_btn.set_data_to_save(valid_results)
                            self.export_img_btn.setVisible(True)
                    else:
                        # Fallback: display per-channel if channel 0 plot doesn't exist
                        for result in valid_results:
                            channel = next(
                                (
                                    item["channel_index"]
                                    for item in self.data
                                    if item["channel_index"] == result.get("channel", 0)
                                ),
                                None,
                            )
                            if channel is not None:
                                self.update_plot(result, channel)
        else:
            # Original behavior for single file
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
                    # If channel not found in data (e.g., fitting only without spectroscopy),
                    # use the channel from result directly if plot exists
                    if channel is None:
                        channel = result.get("channel", 0)
                    
                    if channel is not None and channel in self.plot_widgets:
                        self.update_plot(result, channel)
            
            # Set export data for single file mode
            if self.save_plot_img:
                self.export_img_btn.set_data_to_save(results)
                self.export_img_btn.setVisible(True)
        
        # Hide roi checkboxes
        self.set_roi_checkboxes_visibility(False)
        LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, True)
        # Note: export button visibility is now set inside the if/else branches above
        # to ensure correct data is passed for export

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
        # Show the channel title only in ACQUIRE mode, hide in READ mode
        chart_title.setVisible(not self.read_mode)
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
        plot_widget.setMinimumHeight(500)
        plot_widget.setMaximumHeight(600)
        plot_widget.setBackground("#0a0a0a")
        plot_widget.setLabel("left", "Counts", color="white")
        plot_widget.setLabel("bottom", "Time", color="white")
        plot_widget.getAxis("left").setPen("white")
        plot_widget.getAxis("bottom").setPen("white")
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Don't set fixed limits for multi-file comparison in read mode
        if not (self.read_mode and self.preloaded_fitting and any('file_index' in r for r in self.preloaded_fitting if "error" not in r)):
            margin = 0.5
            plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
            plot_widget.setLimits(xMin=0 - margin, xMax=self.laser_period_ns + margin)
        else:
            # Auto-range for multi-file comparison
            plot_widget.enableAutoRange()
            
        if not (self.read_mode):
            # Spectroscopy curve - skip for channel 0 (averaged/multi-file)
            if channel != 0:
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
        residuals_widget.setMinimumHeight(120)
        residuals_widget.setMaximumHeight(150)
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
        
        # Container for fitted params (horizontal layout)
        fitted_params_container = QWidget()
        fitted_params_layout = QHBoxLayout(fitted_params_container)
        fitted_params_layout.setContentsMargins(0, 0, 0, 0)
        fitted_params_layout.setSpacing(20)
        fitted_params_container.fitted_params_layout = fitted_params_layout  # Save reference
        
        # Store container reference for multi-file updates
        if not hasattr(self, 'params_containers'):
            self.params_containers = {}
        self.params_containers[channel] = fitted_params_container
        
        # Create vertical container for single file: title on top, params below
        single_file_container = QWidget()
        single_file_vlayout = QVBoxLayout(single_file_container)
        single_file_vlayout.setContentsMargins(0, 0, 0, 0)
        single_file_vlayout.setSpacing(5)
        
        # Add "Fitted parameters:" title label
        params_title = QLabel("Fitted parameters:")
        params_title.setStyleSheet("color: #cecece; font-family: Montserrat; font-size: 16px;")
        single_file_vlayout.addWidget(params_title)
        
        # Add single label for single file mode
        fitted_params_text = QLabel("")
        fitted_params_text.setStyleSheet("color: #cecece; font-family: Montserrat; font-size: 16px;")
        single_file_vlayout.addWidget(fitted_params_text)
        
        fitted_params_layout.addWidget(single_file_container)
        
        # Hide the parameters container initially - show it only after fitting is done
        fitted_params_container.setVisible(False)
        
        charts_layout.addWidget(fitted_params_container)
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
        Supports multiple files with different colors.

        Args:
            result (dict or list): Single fitting result or list of results from multiple files.
            channel (int): The channel index to update.
        """
        from core.plots_controller import PlotsController
        
        # Check if plot_widget exists for this channel
        # If not found and channel is 0 (averaged data), try to use the first available plot
        if channel not in self.plot_widgets:
            if channel == 0 and len(self.plot_widgets) > 0:
                # Use the first available plot widget (for averaged channels case)
                channel = list(self.plot_widgets.keys())[0]
            else:
                print(f"Warning: No plot widget found for channel {channel}, skipping update")
                return
            
        plot_widget = self.plot_widgets[channel]
        residuals_widget = self.residuals_widgets[channel]
        fitted_params_text = self.fitted_params_labels[channel]
        
        # Handle multiple files
        if isinstance(result, list):
            self._update_plot_multiple_files(result, channel, plot_widget, residuals_widget, fitted_params_text)
        else:
            self._update_plot_single_file(result, channel, plot_widget, residuals_widget, fitted_params_text)
    
    def _update_plot_single_file(self, result, channel, plot_widget, residuals_widget, fitted_params_text):
        """Updates plot with single file data."""
        from core.plots_controller import PlotsController
        
        # Show the fitted parameters container now that we have results
        if channel in self.params_containers:
            self.params_containers[channel].setVisible(True)
        
        truncated_x_values = result["x_values"][result["decay_start"] :]
        # Cache y values to handle lin/log change
        self.cached_counts_data[channel]["y"] = (
            np.array(result["y_data"]) * result["scale_factor"]
        )
        self.cached_counts_data[channel]["x"] = result["t_data"]
        self.cached_fitted_data[channel]["y"] = np.array(
            result["fitted_values"] * result["scale_factor"]
        )
        # IMPORTANT: Use result["t_data"] as X for fitted curve, not truncated_x_values
        # This matches the logic from main branch
        self.cached_fitted_data[channel]["x"] = result["t_data"]
        
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
        
        if hasattr(plot_widget.plotItem, 'legend') and plot_widget.plotItem.legend is not None:
            plot_widget.plotItem.legend.scene().removeItem(plot_widget.plotItem.legend)
            plot_widget.plotItem.legend = None
        
        plot_widget.clear()
        
        legend = plot_widget.addLegend(offset=(0, 20), labelTextSize='11pt')
        legend.setParent(plot_widget)
        
        # Get file name for legend
        file_index = result.get('file_index', 0)
        file_name = result.get('file_name', f'File {file_index + 1}')
        color = self.file_colors[file_index % len(self.file_colors)]
        
        # Ensure arrays have matching lengths
        min_len = min(len(truncated_x_values), len(y_data))
        truncated_x_values = truncated_x_values[:min_len]
        y_data = y_data[:min_len]
        
        # For fitted data, use t_data directly (matches main branch logic)
        # No need to adjust length - fitted_data already matches t_data from fitting
        
        # Plot Counts (points)
        plot_widget.plot(
            truncated_x_values,
            y_data,
            pen=None,
            symbol="o",
            symbolSize=4,
            symbolBrush=color,
            name="Counts"
        )
        
        # Plot Fitted curve (line) - use result["t_data"] as X
        plot_widget.plot(
            result["t_data"],
            fitted_data,
            pen=pg.mkPen(color, width=2),
            name="Fitted curve"
        )
        
        # Add single legend entry for this file with colored indicator (only in read mode)
        if self.read_mode:
            legend_item = pg.PlotDataItem(pen=pg.mkPen(color, width=10))
            legend.addItem(legend_item, file_name)
        
        PlotsController.set_plot_y_range(plot_widget)
        # Residuals
        residuals = np.array(result["residuals"])
        # Ensure residuals match truncated_x_values length
        residuals_min_len = min(len(truncated_x_values), len(residuals))
        residuals_widget.clear()
        residuals_widget.plot(
            truncated_x_values[:residuals_min_len], residuals[:residuals_min_len], pen=pg.mkPen("#1E90FF", width=2)
        )
        residuals_widget.addLine(y=0, pen=pg.mkPen("w", style=Qt.PenStyle.DashLine))
        if len(result["fitted_params_text"]) > 55:
            fitted_params_text.setWordWrap(True)
        # Remove "Fitted parameters:\n" from the beginning since there's already a title label
        params_text_clean = result["fitted_params_text"].replace("Fitted parameters:\n", "", 1)
        fitted_params_text.setText(params_text_clean)
    
    def _update_plot_multiple_files(self, results, channel, plot_widget, residuals_widget, fitted_params_text):
        """Updates plot with multiple file data using different colors."""
        from core.plots_controller import PlotsController
        
        # Show the fitted parameters container now that we have results
        if channel in self.params_containers:
            self.params_containers[channel].setVisible(True)
        
        if hasattr(plot_widget.plotItem, 'legend') and plot_widget.plotItem.legend is not None:
            plot_widget.plotItem.legend.scene().removeItem(plot_widget.plotItem.legend)
            plot_widget.plotItem.legend = None
        
        plot_widget.clear()
        legend = plot_widget.addLegend(offset=(0, 20), labelTextSize='11pt')
        legend.setParent(plot_widget)
        
        # Add global legend entries to explain symbols
        legend_counts = pg.PlotDataItem(pen=None, symbol='o', symbolSize=6, symbolBrush='white')
        legend.addItem(legend_counts, "Counts")
        legend_fitted = pg.PlotDataItem(pen=pg.mkPen('white', width=2))
        legend.addItem(legend_fitted, "Fitted curve")
        
        all_y_data = []
        all_fitted_data = []
        
        for idx, result in enumerate(results):
            file_index = result.get('file_index', 0)
            file_name = result.get('file_name', f'File {file_index + 1}')
            color = self.file_colors[file_index % len(self.file_colors)]
            
            # Get x values
            decay_start = result["decay_start"]
            truncated_x_values = result["x_values"][decay_start:]
            
            # Calculate y_data (full array, scaled)
            y_data_full = np.array(result["y_data"]) * result["scale_factor"]
            fitted_data_full = np.array(result["fitted_values"]) * result["scale_factor"]
            
            # Apply lin/log mode to full arrays
            if channel not in self.lin_log_modes or self.lin_log_modes[channel] == "LIN":
                _, y_data_transformed = LinLogControl.calculate_lin_mode(y_data_full)
                _, fitted_data_transformed = LinLogControl.calculate_lin_mode(fitted_data_full)
            else:
                y_data_transformed, _, _ = LinLogControl.calculate_log_ticks(y_data_full)
                fitted_data_transformed, _, _ = LinLogControl.calculate_log_ticks(fitted_data_full)
            
            # For counts, we need to match with truncated_x_values
            # y_data corresponds to the data from decay_start onwards
            # truncated_x_values is x_values[decay_start:] which should match
            
            # However, y_data might be shorter due to fitting, so we need to align them properly
            # Use the length of y_data and take corresponding x values
            counts_len = len(y_data_transformed)
            counts_x = truncated_x_values[:counts_len]
            counts_y = y_data_transformed
            
            all_y_data.extend(counts_y)
            all_fitted_data.extend(fitted_data_transformed)
            
            # Add small horizontal offset (jittering) to make overlapping points visible
            # Offset is proportional to file index: centered around original position
            num_files = len(results)
            x_range = counts_x.max() - counts_x.min() if len(counts_x) > 0 else 1
            jitter_amount = 0.003 * x_range  # 0.3% of x range - very small offset
            # Center the jittering: offset from -(n-1)/2 to +(n-1)/2
            offset_x = (file_index - (num_files - 1) / 2) * jitter_amount
            counts_x_jittered = counts_x + offset_x
            
            # Plot counts with symbols (circles) only, no line (no legend)
            plot_widget.plot(
                counts_x_jittered,
                counts_y,
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=color,
            )
            
            # Plot fitted curve with solid line in file color (use t_data as x, no legend)
            t_data = result["t_data"]
            min_len_fit = min(len(t_data), len(fitted_data_transformed))
            
            plot_widget.plot(
                t_data[:min_len_fit],
                fitted_data_transformed[:min_len_fit],
                pen=pg.mkPen(color, width=2),
            )
            
            # Add single legend entry for this file with a colored rectangle (only in read mode)
            # Use a line with large width to create a rectangle effect
            if self.read_mode:
                legend_item = pg.PlotDataItem(pen=pg.mkPen(color, width=10))
                legend.addItem(legend_item, file_name)
        
        # Set y-axis ticks based on combined data
        if len(all_y_data + all_fitted_data) > 0:
            if channel not in self.lin_log_modes or self.lin_log_modes[channel] == "LIN":
                y_ticks, _ = LinLogControl.calculate_lin_mode(np.array(all_y_data + all_fitted_data))
            else:
                _, y_ticks, _ = LinLogControl.calculate_log_ticks(np.array(all_y_data + all_fitted_data))
            
            axis = plot_widget.getAxis("left")
            axis.setTicks([y_ticks])
        
        PlotsController.set_plot_y_range(plot_widget)
        
        # Show residuals for all files with different colors
        residuals_widget.clear()
        for idx, result in enumerate(results):
            file_index = result.get('file_index', 0)
            color = self.file_colors[file_index % len(self.file_colors)]
            residuals = result["residuals"]
            residuals_x = result["x_values"][result["decay_start"]:]
            min_len_res = min(len(residuals_x), len(residuals))
            residuals_widget.plot(
                residuals_x[:min_len_res], residuals[:min_len_res], pen=pg.mkPen(color, width=2)
            )
        residuals_widget.addLine(y=0, pen=pg.mkPen("w", style=Qt.PenStyle.DashLine))
        
        # Get the horizontal layout container from saved reference
        params_container = self.params_containers.get(channel)
        if not params_container:
            print(f"WARNING: No params_container found for channel {channel}")
            return
        params_layout = params_container.fitted_params_layout
        
        # Cache data for LIN/LOG control - use first file as reference
        if results:
            first_result = results[0]
            self.cached_counts_data[channel] = {
                "x": first_result["t_data"],
                "y": first_result["y_data"] * first_result["scale_factor"]
            }
            self.cached_fitted_data[channel] = {
                "x": first_result["t_data"],
                "y": first_result["fitted_values"] * first_result["scale_factor"]
            }
        
        # Clear existing widgets
        while params_layout.count():
            item = params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add one label per file, with "Fitted parameters:" title above each
        for result in results:
            file_index = result.get('file_index', 0)
            file_name = result.get('file_name', f'File {file_index + 1}')
            color = self.file_colors[file_index % len(self.file_colors)]
            # Remove "Fitted parameters:\n" from beginning - we'll add it as a separate title
            params_text = result["fitted_params_text"].replace("Fitted parameters:\n", "", 1)
            
            # Create a vertical container: title on top, then color indicator + text
            file_container = QWidget()
            file_vlayout = QVBoxLayout(file_container)
            file_vlayout.setContentsMargins(0, 0, 0, 0)
            file_vlayout.setSpacing(5)
            
            # Add "Fitted parameters:" title for this file
            file_title = QLabel("Fitted parameters:")
            file_title.setStyleSheet("color: #cecece; font-family: Montserrat; font-size: 16px;")
            file_vlayout.addWidget(file_title)
            
            # Create horizontal layout for color indicator + parameters
            content_widget = QWidget()
            content_hlayout = QHBoxLayout(content_widget)
            content_hlayout.setContentsMargins(0, 0, 0, 0)
            content_hlayout.setSpacing(10)
            
            # Add colored rectangle as indicator
            color_indicator = QLabel()
            color_indicator.setFixedSize(15, 15)
            color_indicator.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
            content_hlayout.addWidget(color_indicator, alignment=Qt.AlignmentFlag.AlignTop)
            
            # Add parameters text (convert newlines to <br> for HTML)
            colored_params_text = params_text.replace('\n', '<br>')
            
            file_label = QLabel(colored_params_text)
            file_label.setTextFormat(Qt.TextFormat.RichText)
            file_label.setStyleSheet("color: #cecece; font-family: Montserrat; font-size: 16px;")
            file_label.setWordWrap(True)
            content_hlayout.addWidget(file_label)
            
            file_vlayout.addWidget(content_widget)
            
            params_layout.addWidget(file_container)

    def _average_channels(self, results):
        """Calculates the average of multiple channels from the same file.
        
        Args:
            results (list): List of fitting results for different channels.
            
        Returns:
            dict: Averaged fitting result with channel=0.
        """
        if not results or len(results) == 0:
            return None
        
        # Find minimum length to handle arrays of different sizes
        min_len_y = min(len(r['y_data']) for r in results)
        min_len_fitted = min(len(r['fitted_values']) for r in results)
        min_len_residuals = min(len(r['residuals']) for r in results)
        min_len_x = min(len(r['x_values']) for r in results)
        min_len_t = min(len(r['t_data']) for r in results)
        
        # Calculate averages with truncated arrays
        avg_chi2 = np.mean([r['chi2'] for r in results])
        avg_r2 = np.mean([r.get('r2', 0) for r in results]) if all('r2' in r for r in results) else 0
        
        # Use first result as template
        first = results[0]
        
        # Calculate averaged y_data
        avg_y_data = np.mean([r['y_data'][:min_len_y] for r in results], axis=0)
        avg_fitted = np.mean([r['fitted_values'][:min_len_fitted] for r in results], axis=0)
        
        # Build fitted_params_text from averaged values
        fitted_params_text = f"Average of {len(results)} channels\n"
        fitted_params_text += first.get('fitted_params_text', '').split('\n')[0] + '\n'  # Keep first line (tau values)
        fitted_params_text += f'X² = {avg_chi2:.4f}\n'
        fitted_params_text += f'R² = {avg_r2:.4f}\n'
        
        avg_result = {
            'x_values': first['x_values'][:min_len_x],
            't_data': first['t_data'][:min_len_t],
            'y_data': avg_y_data,
            'fitted_values': avg_fitted,
            'residuals': np.mean([r['residuals'][:min_len_residuals] for r in results], axis=0),
            'fitted_params_text': fitted_params_text,
            'scale_factor': np.mean([r['scale_factor'] for r in results]),
            'decay_start': first['decay_start'],
            'channel': 0,
            'chi2': avg_chi2,
            'r2': avg_r2,
            'file_index': first.get('file_index', 0),
            'file_name': first.get('file_name', 'Averaged')
        }
        
        return avg_result

    def add_chart_to_grid(self, chart_widget, index):
        """
        Adds a chart widget to the main grid layout.

        Args:
            chart_widget (QWidget): The widget to add.
            index (int): The sequential index to determine the position in the grid.
        """
        # Always use horizontal layout with up to 4 plots per row
        col_length = 4
        
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
