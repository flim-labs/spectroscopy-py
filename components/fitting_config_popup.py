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
from core.phasors_controller import PhasorsController
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
        self.preloaded_spectroscopy = self.data  # Use self.data as preloaded_spectroscopy for multi-file display
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
        self.roi_regions = {}  # Store ROI regions for multi-file mode
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
        
        # Check if we have multiple files with file_index
        # For fitting results: check read_mode (only in read mode)
        # For spectroscopy data: check file_index presence AND multiple entries
        
        has_multiple_files_from_fitting = self.read_mode and self.preloaded_fitting and any('file_index' in r for r in self.preloaded_fitting if "error" not in r)
        
        # For spectroscopy: use multi-file logic if in read_mode and has file_index (regardless of count)
        has_multiple_files_from_spectroscopy = (self.read_mode and 
                                               self.data and 
                                               any('file_index' in d for d in self.data))
        
        has_multiple_files = has_multiple_files_from_fitting or has_multiple_files_from_spectroscopy
        
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
        
        # Schedule a refresh after the window is shown to ensure plots are visible
        from PyQt6.QtCore import QTimer
        
        # Cancel any existing timers to avoid conflicts
        if hasattr(self, '_refresh_timer') and self._refresh_timer is not None:
            self._refresh_timer.stop()
        
        self._refresh_timer = QTimer()
        self._refresh_timer.singleShot(100, self.force_plots_refresh)

    def force_plots_refresh(self):
        """Force refresh of all plot widgets to ensure they are visible."""
        try:
            from PyQt6.QtWidgets import QApplication
            for channel, plot_widget in self.plot_widgets.items():
                plot_widget.update()
                plot_widget.repaint()
                
                # Force auto-range to ensure proper rendering when widget becomes visible
                plot_widget.autoRange()
            
            QApplication.processEvents()
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def showEvent(self, event):
        """Override showEvent to debug when window becomes visible."""
        super().showEvent(event)
    
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
        
        # Show export button only in ACQUIRE mode, hide in READ mode (fitting popup only)
        is_read_mode = hasattr(self.app, 'acquire_read_mode') and self.app.acquire_read_mode == "read"
        self.export_fitting_btn.setVisible(not is_read_mode)
        # Start fitting btn
        self.start_fitting_btn = QPushButton("START FITTING")
        self.start_fitting_btn.setObjectName("btn")
        GUIStyles.set_start_btn_style(self.start_fitting_btn)
        self.start_fitting_btn.setFixedHeight(55)
        self.start_fitting_btn.setFixedWidth(150)
        self.start_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_fitting_btn.clicked.connect(self.start_fitting)
        # Hide START FITTING button if preloaded_fitting exists (already fitted data)
        self.start_fitting_btn.setVisible(self.preloaded_fitting is None)
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
        # Set initial visibility based on save_plot_img parameter
        self.export_img_btn.setVisible(self.save_plot_img)
        controls_row.addStretch(1)
        
        # Show EXPORT button only in ACQUIRE mode (not in READ mode)
        if not self.read_mode:
            controls_row.addWidget(self.export_fitting_btn)
            controls_row.addSpacing(10)
        
        # Always show START FITTING and RESET buttons (both ACQUIRE and READ modes)
        controls_row.addWidget(self.start_fitting_btn)
        controls_row.addSpacing(10)
        controls_row.addWidget(reset_btn)
        controls_row.addSpacing(20)
        
        # Show export image button in READ mode when save_plot_img is True
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
        clear_layout_widgets(self.errors_layout)
        self.loading_text.setVisible(True)
        self.gif_label.setVisible(True)
        self.worker = FittingWorker(
            self.data,
            self.roi_checkboxes,
            self.cut_data_x,
            self.cut_data_y,
            self.y_data_shift,
            self.roi_regions,  # Pass ROI regions for multi-file mode
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
            if "error" in result:
                title = (
                    "Channel " + str(result["channel"] + 1) if "channel" in result else ""
                )
                self.display_error(result["error"], title)
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
        if len(data) == 0:
            return np.array([]), np.array([])
        
        # Ensure y is a proper numpy array
        y_data = np.array(data[0]["y"])
        if y_data.ndim == 0:
            # Scalar value
            return np.array([]), np.array([])
        elif y_data.ndim > 1:
            # Multi-dimensional, flatten or take first dimension
            y_data = y_data.flatten()
                
        # Validate that y_data has sufficient length
        x_data = np.array(data[0]["x"])
        if len(y_data) < 2 or len(x_data) < 2:
            return np.array([]), np.array([])
        
        # Ensure X and Y have the same length
        min_len = min(len(x_data), len(y_data))
        if len(x_data) != len(y_data):
            x_data = x_data[:min_len]
            y_data = y_data[:min_len]
        
        # Use app.time_shifts to be consistent with main window
        time_shift = 0 if channel not in self.app.time_shifts else self.app.time_shifts[channel]
        y = np.roll(y_data, time_shift)
        
        # Add legend for single file case
        if not hasattr(plot_widget.plotItem, 'legend') or plot_widget.plotItem.legend is None:
            plot_widget.addLegend(offset=(10, 10))
        
        # Get file name from data or fallback to reader_data
        file_name = data[0].get('file_name', 'File 1')
        
        if file_name in ['File 1', 'Single File'] or not file_name:
            # Try to get actual file name from reader_data
            fitting_files = self.app.reader_data.get("fitting", {}).get("files", {}).get("spectroscopy", "")
            if fitting_files:
                if isinstance(fitting_files, str):
                    file_name = os.path.basename(fitting_files)
                elif isinstance(fitting_files, list) and len(fitting_files) > 0:
                    file_name = os.path.basename(fitting_files[0])
            
            # If still no good name, try alternative paths
            if file_name in ['File 1', 'Single File'] or not file_name:
                # Try spectroscopy files from main reader_data
                spectroscopy_files = self.app.reader_data.get("spectroscopy", {}).get("files", {}).get("spectroscopy", "")
                if spectroscopy_files:
                    if isinstance(spectroscopy_files, str):
                        file_name = os.path.basename(spectroscopy_files)
                    elif isinstance(spectroscopy_files, list) and len(spectroscopy_files) > 0:
                        file_name = os.path.basename(spectroscopy_files[0])
                
        # Don't show filename in legend here - it will be added as a separate legend entry
        plot_widget.plot(x_data, y, pen=pg.mkPen("#f72828", width=2))
        return x_data, y

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
        # Hide channel title in READ tab (regardless of read_mode)
        is_read_tab = hasattr(self.app, 'acquire_read_mode') and self.app.acquire_read_mode == 'read'
        title_visible = not is_read_tab
        chart_title.setVisible(title_visible)
        title_layout.addStretch()
        title_layout.addWidget(chart_title)
        # Add ROI checkbox in both ACQUIRE and READ modes
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
            "color: #FF6B6B; font-size: 12px; font-weight: bold; padding: 5px;"
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
        
        # Detect multi-file mode
        is_multi_file_fitting = (
            self.read_mode and 
            self.preloaded_fitting and 
            any('file_index' in r for r in self.preloaded_fitting if "error" not in r)
        )
        
        is_multi_file_spectroscopy = (
            self.read_mode and 
            self.preloaded_spectroscopy and 
            any('file_index' in s for s in self.preloaded_spectroscopy if "error" not in s)
        )
        
        # Set X-axis range based on mode
        if is_multi_file_fitting or is_multi_file_spectroscopy:
            # Auto-range for multi-file comparison
            plot_widget.enableAutoRange()
        else:
            # Single file mode: use actual data range instead of laser_period_ns
            if self.read_mode and self.preloaded_spectroscopy:
                # Get actual data range from spectroscopy data
                spectroscopy_data = self.preloaded_spectroscopy[channel - 1]
                if "error" not in spectroscopy_data:
                    x_data = spectroscopy_data.get("x", [])
                    if len(x_data) > 0:
                        data_min = min(x_data)
                        data_max = max(x_data)
                        margin = (data_max - data_min) * 0.05  # 5% margin
                        plot_widget.setXRange(data_min - margin, data_max + margin)
                        plot_widget.setLimits(xMin=data_min - margin, xMax=data_max + margin)
                    else:
                        # Fallback to laser period
                        margin = 0.5
                        plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
                        plot_widget.setLimits(xMin=0 - margin, xMax=self.laser_period_ns + margin)
                else:
                    # Fallback to laser period
                    margin = 0.5
                    plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
                    plot_widget.setLimits(xMin=0 - margin, xMax=self.laser_period_ns + margin)
            else:
                # Acquire mode: use laser period
                margin = 0.5
                plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
                plot_widget.setLimits(xMin=0 - margin, xMax=self.laser_period_ns + margin)
        
        # Handle spectroscopy curve and ROI based on mode
        if is_multi_file_spectroscopy:
            # Multi-file spectroscopy mode: display all files with different colors
            from core.phasors_controller import PhasorsController
            
            all_x_data = []
            all_y_data = []
            
            # Add legend BEFORE plotting so it can collect items
            is_read_mode = hasattr(self.app, 'acquire_read_mode') and self.app.acquire_read_mode == "read"
            if (is_read_mode or self.read_mode) and len(self.preloaded_spectroscopy) >= 1:
                legend = plot_widget.addLegend(offset=(10, 10))
                legend.setLabelTextColor('white')
            
            # Display spectroscopy curves for all files
            for file_idx, spectroscopy_data in enumerate(self.preloaded_spectroscopy):
                if "error" in spectroscopy_data:
                    continue
                # In multi-file mode, display all files (channel filter removed)
                x = spectroscopy_data.get("x", [])
                y = spectroscopy_data.get("y", [])
                
                if len(x) > 0 and len(y) > 0:
                    all_x_data.extend(x)
                    all_y_data.extend(y)
                    
                    # Get color for this file
                    actual_file_idx = spectroscopy_data.get('file_index', file_idx)
                    # Use cyan for single file to be more visible, otherwise use file-specific color
                    if len(self.preloaded_spectroscopy) == 1:
                        color = "#00d4ff"  # Cyan for single file
                    else:
                        color = PhasorsController.get_color_for_file_index(actual_file_idx)
                    
                    # Plot with color and legend
                    file_name = spectroscopy_data.get("file_name", f"File {actual_file_idx + 1}")
                    # Clean file name for legend (remove path and extension)
                    import os
                    legend_name = os.path.splitext(os.path.basename(file_name))[0] if file_name else f"File {actual_file_idx + 1}"
                    pen = pg.mkPen(color=color, width=2)
                    plot_item = plot_widget.plot(
                        x, y,
                        pen=pen,
                        name=legend_name
                    )
            
            # Create combined ROI based on all data
            if len(all_x_data) > 0:
                x_min = min(all_x_data)
                x_max = max(all_x_data)
                x_range = x_max - x_min
                
                # Initialize ROI to 10%-50% of data range
                roi_start = x_min + x_range * 0.1
                roi_end = x_min + x_range * 0.5
                
                roi = pg.LinearRegionItem([roi_start, roi_end])
                
                # Try to load saved ROI for this channel
                result = self.get_saved_roi(channel)
                if result is not None:
                    saved_min_x, saved_max_x = result
                    # Validate saved ROI is within data range
                    if saved_min_x >= x_min and saved_max_x <= x_max:
                        roi.setRegion([saved_min_x, saved_max_x])
                        # Set ROI mask for all files
                        for spectroscopy_data in self.preloaded_spectroscopy:
                            if "error" in spectroscopy_data:
                                continue
                            x = spectroscopy_data.get("x", [])
                            y = spectroscopy_data.get("y", [])
                            if len(x) > 0 and len(y) > 0:
                                self.set_roi_mask(roi, x, y, channel)
                
                roi.setVisible(False)
                roi.sigRegionChanged.connect(
                    lambda: self.on_roi_selection_changed_multi_file(roi, channel)
                )
                roi.sigRegionChangeFinished.connect(
                    lambda: self.limit_roi_bounds(roi)
                )
                self.roi_items[channel] = roi
                plot_widget.addItem(roi)
            
            # Force plot widget update to ensure curves are visible
            plot_widget.update()
            plot_widget.repaint()
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
        
        elif not self.read_mode:
            # Single file acquire mode
            if channel != 0:
                x, y = self.display_spectroscopy_curve(plot_widget, channel)
                
                # Initialize ROI based on data range
                if len(x) > 0:
                    x_min = min(x)
                    x_max = max(x)
                    x_range = x_max - x_min
                    
                    # Initialize ROI to 10%-50% of data range
                    roi_start = x_min + x_range * 0.1
                    roi_end = x_min + x_range * 0.5
                    
                    roi = pg.LinearRegionItem([roi_start, roi_end])
                    
                    # Try to load saved ROI
                    result = self.get_saved_roi(channel)
                    if result is not None:
                        saved_min_x, saved_max_x = result
                        # Validate saved ROI is within data range
                        if saved_min_x >= x_min and saved_max_x <= x_max:
                            roi.setRegion([saved_min_x, saved_max_x])
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
        
        else:
            # Single file read mode
            if channel != 0:
                # Display spectroscopy curve
                spectroscopy_data = self.preloaded_spectroscopy[channel - 1]
                if "error" not in spectroscopy_data:
                    x = spectroscopy_data.get("x", [])
                    y = spectroscopy_data.get("y", [])
                    
                    if len(x) > 0 and len(y) > 0:
                        plot_widget.plot(x, y, pen=pg.mkPen(color="#00d4ff", width=2))
                        
                        # Initialize ROI based on data range
                        x_min = min(x)
                        x_max = max(x)
                        x_range = x_max - x_min
                        
                        # Initialize ROI to 10%-50% of data range
                        roi_start = x_min + x_range * 0.1
                        roi_end = x_min + x_range * 0.5
                        
                        roi = pg.LinearRegionItem([roi_start, roi_end])
                        
                        # Try to load saved ROI
                        result = self.get_saved_roi(channel)
                        if result is not None:
                            saved_min_x, saved_max_x = result
                            # Validate saved ROI is within data range
                            if saved_min_x >= x_min and saved_max_x <= x_max:
                                roi.setRegion([saved_min_x, saved_max_x])
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
        
        # Final refresh to ensure plot is visible
        plot_widget.update()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

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
        # Use truncated_x_values for fitted curve X
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
        
        if hasattr(plot_widget.plotItem, 'legend') and plot_widget.plotItem.legend is not None:
            plot_widget.plotItem.legend.scene().removeItem(plot_widget.plotItem.legend)
            plot_widget.plotItem.legend = None
        
        plot_widget.clear()
        
        legend = plot_widget.addLegend(offset=(0, 20), labelTextSize='11pt')
        legend.setParent(plot_widget)
        
        # Get file name for legend with comprehensive fallback resolution
        file_index = result.get('file_index', 0)
        file_name = result.get('file_name', f'File {file_index + 1}')
        
        # Try to resolve actual file name if it's a generic placeholder
        if file_name in ['File 1', f'File {file_index + 1}', 'Single File'] or not file_name:
            # Try fitting/spectroscopy path
            fitting_files = self.app.reader_data.get("fitting", {}).get("files", {}).get("spectroscopy", "")
            if fitting_files:
                if isinstance(fitting_files, str):
                    file_name = os.path.basename(fitting_files)
                elif isinstance(fitting_files, list) and len(fitting_files) > file_index:
                    file_name = os.path.basename(fitting_files[file_index])
            
            # Try fitting/fitting path if still not resolved
            if file_name in ['File 1', f'File {file_index + 1}', 'Single File'] or not file_name:
                fitting_files = self.app.reader_data.get("fitting", {}).get("files", {}).get("fitting", "")
                if fitting_files:
                    if isinstance(fitting_files, str):
                        file_name = os.path.basename(fitting_files)
                    elif isinstance(fitting_files, list) and len(fitting_files) > file_index:
                        file_name = os.path.basename(fitting_files[file_index])
            
            # Try spectroscopy/spectroscopy path if still not resolved
            if file_name in ['File 1', f'File {file_index + 1}', 'Single File'] or not file_name:
                spectroscopy_files = self.app.reader_data.get("spectroscopy", {}).get("files", {}).get("spectroscopy", "")
                if spectroscopy_files:
                    if isinstance(spectroscopy_files, str):
                        file_name = os.path.basename(spectroscopy_files)
                    elif isinstance(spectroscopy_files, list) and len(spectroscopy_files) > file_index:
                        file_name = os.path.basename(spectroscopy_files[file_index])
            
            # Try metadata as final fallback
            if file_name in ['File 1', f'File {file_index + 1}', 'Single File'] or not file_name:
                metadata = self.app.reader_data.get("metadata", {})
                if isinstance(metadata, list) and len(metadata) > file_index:
                    metadata_item = metadata[file_index]
                    if isinstance(metadata_item, dict) and 'filename_raw' in metadata_item:
                        file_name = metadata_item['filename_raw']
        
        color = PhasorsController.get_color_for_file_index(file_index)
        
        # Add explanatory legend entries first (gray)
        legend_counts = plot_widget.plot([], [], pen=None, symbol='o', symbolSize=6, symbolBrush='gray', name="Counts")
        legend_fitted = plot_widget.plot([], [], pen=pg.mkPen('gray', width=2), name="Fitted curve")
        
        # Ensure arrays have matching lengths
        min_len = min(len(truncated_x_values), len(y_data))
        truncated_x_values = truncated_x_values[:min_len]
        y_data = y_data[:min_len]
        
        # For fitted data, ensure matching lengths
        fitted_min_len = min(len(self.cached_fitted_data[channel]["x"]), len(fitted_data))
        fitted_x = self.cached_fitted_data[channel]["x"][:fitted_min_len]
        fitted_y = fitted_data[:fitted_min_len]
        
        # Plot Counts (points) with symbolSize=6
        plot_widget.plot(
            truncated_x_values,
            y_data,
            pen=None,
            symbol="o",
            symbolSize=6,
            symbolBrush=color,
        )
        
        # Plot Fitted curve (line) - use cached_fitted_data x values
        plot_widget.plot(
            fitted_x,
            fitted_y,
            pen=pg.mkPen(color, width=2),
        )
        
        # Plot original spectroscopy curve in read mode (red line width=1)
        if self.read_mode and self.preloaded_spectroscopy:
            # Get original spectroscopy data for this channel
            spectroscopy_data = None
            if isinstance(self.preloaded_spectroscopy, list):
                for spec_data in self.preloaded_spectroscopy:
                    if spec_data.get('channel') == channel:
                        spectroscopy_data = spec_data
                        break
            elif isinstance(self.preloaded_spectroscopy, dict) and self.preloaded_spectroscopy.get('channel') == channel:
                spectroscopy_data = self.preloaded_spectroscopy
            
            if spectroscopy_data:
                spec_x = np.array(spectroscopy_data.get('x_values', []))
                spec_y = np.array(spectroscopy_data.get('y_values', []))
                if len(spec_x) > 0 and len(spec_y) > 0:
                    # Apply lin/log transformation
                    if channel not in self.lin_log_modes or self.lin_log_modes[channel] == "LIN":
                        _, spec_y_transformed = LinLogControl.calculate_lin_mode(spec_y)
                    else:
                        spec_y_transformed, _, _ = LinLogControl.calculate_log_ticks(spec_y)
                    
                    plot_widget.plot(
                        spec_x,
                        spec_y_transformed,
                        pen=pg.mkPen('#f72828', width=1),
                    )
        
        # Add single legend entry for this file with colored indicator (only in read mode)
        if self.read_mode:
            legend_item = pg.PlotDataItem(pen=pg.mkPen(color, width=10))
            legend.addItem(legend_item, file_name)
        
        # Adjust plot range to match data (not dummy spectroscopy)
        plot_widget.enableAutoRange()
        plot_widget.getViewBox().autoRange()
        
        # Calculate residuals as y_data - fitted_values
        # Interpolate fitted values to match y_data points
        from scipy.interpolate import interp1d
        if len(fitted_x) > 1 and len(fitted_y) > 1:
            # Create interpolation function
            interp_func = interp1d(fitted_x, fitted_y, kind='linear', bounds_error=False, fill_value='extrapolate')
            # Get fitted values at the same x positions as y_data
            fitted_at_data_points = interp_func(truncated_x_values)
            # Calculate residuals
            residuals = y_data - fitted_at_data_points
        else:
            # Fallback to using result residuals if interpolation fails
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
        
        # Add global legend entries to explain symbols (gray color)
        plot_widget.plot([], [], pen=None, symbol='o', symbolSize=6, symbolBrush='gray', name="Counts")
        plot_widget.plot([], [], pen=pg.mkPen('gray', width=2), name="Fitted curve")
        
        all_y_data = []
        all_fitted_data = []
        all_y_data_original = []  # Original data before transformation
        all_fitted_data_original = []  # Original fitted data before transformation
        
        for idx, result in enumerate(results):
            file_index = result.get('file_index', 0)
            file_name = result.get('file_name', f'File {file_index + 1}')
            color = PhasorsController.get_color_for_file_index(file_index)
            
            # Get x values
            decay_start = result["decay_start"]
            truncated_x_values = np.array(result["x_values"][decay_start:])
            
            # Calculate y_data (full array, scaled)
            y_data_full = np.array(result["y_data"]) * result["scale_factor"]
            fitted_data_full = np.array(result["fitted_values"]) * result["scale_factor"]
            
            # Store original data for tick calculation
            all_y_data_original.extend(y_data_full)
            all_fitted_data_original.extend(fitted_data_full)
            
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
        
        # Set y-axis ticks based on ORIGINAL combined data (before transformation)
        if len(all_y_data_original + all_fitted_data_original) > 0:
            if channel not in self.lin_log_modes or self.lin_log_modes[channel] == "LIN":
                y_ticks, _ = LinLogControl.calculate_lin_mode(np.array(all_y_data_original + all_fitted_data_original))
            else:
                _, y_ticks, _ = LinLogControl.calculate_log_ticks(np.array(all_y_data_original + all_fitted_data_original))
            
            axis = plot_widget.getAxis("left")
            axis.setTicks([y_ticks])
        
        # Force ViewBox autoRange and verify all curves visible
        plot_widget.enableAutoRange()
        plot_widget.getViewBox().autoRange()
        
        # Verify range encompasses all data
        if len(all_y_data + all_fitted_data) > 0:
            all_data = np.array(all_y_data + all_fitted_data)
            data_min, data_max = np.min(all_data), np.max(all_data)
            current_range = plot_widget.getViewBox().viewRange()[1]
            if current_range[0] > data_min or current_range[1] < data_max:
                # Manually set range if autoRange didn't work
                padding = (data_max - data_min) * 0.1
                plot_widget.setYRange(data_min - padding, data_max + padding, padding=0)
        
        # Show residuals for all files with different colors
        residuals_widget.clear()
        for idx, result in enumerate(results):
            file_index = result.get('file_index', 0)
            color = PhasorsController.get_color_for_file_index(file_index)
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
            return
        params_layout = params_container.fitted_params_layout
        
        # Cache data for LIN/LOG control - use first file as reference
        if results:
            first_result = results[0]
            self.cached_counts_data[channel] = {
                "x": np.array(first_result["t_data"]),
                "y": np.array(first_result["y_data"]) * first_result["scale_factor"]
            }
            self.cached_fitted_data[channel] = {
                "x": np.array(first_result["t_data"]),
                "y": np.array(first_result["fitted_values"]) * first_result["scale_factor"]
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
            color = PhasorsController.get_color_for_file_index(file_index)
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
    
    def on_roi_selection_changed_multi_file(self, roi, channel):
        """
        Callback for when the ROI selection is changed in multi-file mode.

        Args:
            roi (pg.LinearRegionItem): The ROI item that was changed.
            channel (int): The channel index.
        """
        min_x, max_x = roi.getRegion()
        # Store ROI region for multi-file mode
        self.roi_regions[channel] = (min_x, max_x)
        self.app.roi[channel] = (min_x, max_x)
        self.app.settings.setValue(s.SETTINGS_ROI, json.dumps(self.app.roi))
        
    def limit_roi_bounds(self, roi):
        """
        Ensures the ROI selection does not go beyond the plot's x-axis limits.

        Args:
            roi (pg.LinearRegionItem): The ROI item to check.
        """
        min_val, max_val = roi.getRegion()
        min_limit = 0
        # Use data range instead of laser_period_ns for bin indices
        if self.data and len(self.data) > 0:
            x_data = self.data[0].get('x', [])
            if len(x_data) > 0:
                max_limit = np.max(x_data)
            else:
                max_limit = self.laser_period_ns
        else:
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
        
        # Check if we're in multi-file mode
        has_multi_file = self.data and len(self.data) > 1 and any('file_index' in d for d in self.data)
        
        if has_multi_file:
            # For multi-file mode, just store the ROI region - we'll apply it per file in get_data_point
            self.app.roi[channel] = (min_x, max_x)
        else:
            # For single file mode, apply the mask and store the cut data
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
            roi = self.roi_items[channel]
            roi.setVisible(checked)

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
        
        # Check if multi-file mode to create single plot or multiple plots
        has_multiple_files_from_fitting = self.read_mode and self.preloaded_fitting and any('file_index' in r for r in self.preloaded_fitting if "error" not in r)
        has_multiple_files_from_spectroscopy = (self.data and 
                                               any('file_index' in d for d in self.data) and 
                                               len(self.data) > 1)  # Only multi-file if more than 1 entry
        has_multiple_files = has_multiple_files_from_fitting or has_multiple_files_from_spectroscopy
        
        if has_multiple_files:
            # Create single plot for multiple files comparison
            title = "Multi-File Comparison"
            self.cached_counts_data[0] = {"y": [], "x": []}
            self.cached_fitted_data[0] = {"y": [], "x": []}
            self.display_plot(title, 0, 0)
            # Enable lin/log control for multi-file spectroscopy visualization
            if has_multiple_files_from_spectroscopy and not has_multiple_files_from_fitting:
                LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, True)
        else:
            # Create plot for each channel (single file mode)
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
        self, data, roi_checkboxes, cut_data_x, cut_data_y, y_data_shift, roi_regions, parent=None
    ):
        """
        Initializes the FittingWorker.

        Args:
            data (list): The list of channel data to be fitted.
            roi_checkboxes (dict): A dictionary of ROI checkboxes to check if ROI is active.
            cut_data_x (dict): A dictionary of x-data, cut by ROI (for single file mode).
            cut_data_y (dict): A dictionary of y-data, cut by ROI (for single file mode).
            y_data_shift (int): A global time shift to apply to the data.
            roi_regions (dict): A dictionary of ROI regions (min, max) for each channel.
            parent (QObject, optional): The parent object. Defaults to None.
        """
        super().__init__(parent)
        self.data = data
        self.roi_checkboxes = roi_checkboxes
        self.cut_data_x = cut_data_x
        self.cut_data_y = cut_data_y
        self.y_data_shift = y_data_shift
        self.roi_regions = roi_regions

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
            # Check if we're in multi-file mode
            has_file_index = 'file_index' in data_point
            
            if has_file_index and channel in self.roi_regions:
                # Multi-file mode: apply ROI to this specific file's data
                x = data_point["x"]
                y = data_point["y"]
                
                # Ensure X and Y have the same length
                min_len = min(len(x), len(y))
                if len(x) != len(y):
                    x = x[:min_len]
                    y = y[:min_len]
                
                min_x, max_x = self.roi_regions[channel]
                mask = (x >= min_x) & (x <= max_x)
                return x[mask], y[mask]
            elif channel in self.cut_data_x:
                # Single file mode: use the pre-cut data
                return self.cut_data_x[channel], self.cut_data_y[channel]
            else:
                # Fallback: no ROI data available
                return data_point["x"], data_point["y"]
        else:
            return data_point["x"], data_point["y"]

    def run(self):
        """
        The main execution method of the thread.

        Iterates through the data for each channel, performs the fitting,
        and emits the results or an error.
        """
        results = []
        for idx, data_point in enumerate(self.data):
            try:               
                x, y = self.get_data_point(data_point, data_point["channel_index"])
                result = fit_decay_curve(
                    x, y, data_point["channel_index"], y_shift=data_point["time_shift"]
                )
                # Preserve file_index and file_name from input data
                if "file_index" in data_point:
                    result["file_index"] = data_point["file_index"]
                if "file_name" in data_point:
                    result["file_name"] = data_point["file_name"]
                results.append((result))
            except TimeoutError as te:
                self.error_occurred.emit(f"An error occurred: {str(te)}")
                return                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(f"An error occurred: {str(e)}")
                return
        self.fitting_done.emit(results)
