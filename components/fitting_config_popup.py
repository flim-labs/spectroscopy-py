"""
fitting_config_popup.py  (facade)
==================================
Public API for the fitting popup.

Defines FittingDecayConfigPopup by composing mixin classes from
the components/fitting/ sub-package.  All heavy logic lives in:

    components/fitting/fitting_controls_mixin.py  — controls bar, loading, start/reset/export
    components/fitting/fitting_roi_mixin.py        — ROI selection and management
    components/fitting/fitting_plot_mixin.py       — plot creation and update
    components/fitting/fitting_results_mixin.py    — result processing and display

Re-exports FittingWorker for backward compatibility.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QSizePolicy,
    QGridLayout,
)

import settings.settings as s
from utils.resource_path import resource_path

from components.fitting.fitting_constants import (
    DARK_THEME_BG_COLOR,
    DARK_THEME_TEXT_COLOR,
)
from components.fitting.fitting_worker import FittingWorker  # re-exported for back-compat
from components.fitting.fitting_controls_mixin import FittingControlsMixin
from components.fitting.fitting_roi_mixin import FittingROIMixin
from components.fitting.fitting_plot_mixin import FittingPlotMixin
from components.fitting.fitting_results_mixin import FittingResultsMixin


class FittingDecayConfigPopup(
    QWidget,
    FittingControlsMixin,
    FittingROIMixin,
    FittingPlotMixin,
    FittingResultsMixin,
):
    """
    A popup window for configuring, running, and viewing fluorescence decay fitting.

    This widget displays decay curves for multiple channels, allows users to
    select a Region of Interest (ROI) for fitting, starts the fitting process,
    and displays the results including the fitted curve, residuals, and calculated parameters.

    Heavy implementation is split across sub-modules in components/fitting/:
        - FittingControlsMixin  : control bar, loading row, start/reset/export
        - FittingROIMixin       : ROI selection, mask, checkbox
        - FittingPlotMixin      : plot creation and update (single- and multi-file)
        - FittingResultsMixin   : result processing, slot handlers, channel averaging
    """

    def __init__(
        self,
        window,
        data,
        preloaded_fitting=None,
        read_mode=False,
        save_plot_img=False,
        y_data_shift=0,
        laser_period_ns=0,
        use_deconvolution=False,
        irfs=[],
        raw_signals=[],
        irfs_tau_ns=None,
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
            use_deconvolution (bool, optional): If True, deconvolution will be applied. Defaults to False.
            irfs (list, optional): A list of IRFs to use for deconvolution. Defaults to an empty list.
            raw_signals (list, optional): Raw signals for each channel. Defaults to an empty list.
            irfs_tau_ns (float, optional): IRF tau in nanoseconds. Defaults to None.
        """
        super().__init__()
        # Prevent widget from being shown during construction
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)
        self.app = window
        self.data = data
        self.use_deconvolution = use_deconvolution
        self.irfs = irfs
        self.raw_signals = raw_signals
        self.preloaded_spectroscopy = (
            self.data
        )  # Use self.data as preloaded_spectroscopy for multi-file display
        self.y_data_shift = y_data_shift
        self.laser_period_ns = laser_period_ns
        self.irfs_tau_ns = irfs_tau_ns

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
        self.cut_irfs = {}  # Store ROI-cut IRFs
        self.cut_raw_signals = {}  # Store ROI-cut raw signals
        self.roi_regions = {}  # Store ROI regions for multi-file mode
        self.cached_counts_data = {}
        self.cached_fitted_data = {}
        self.file_colors = [
            "#f72828",
            "#00FF00",
            "#FFA500",
            "#FF00FF",
        ]  # Red, Green, Orange, Magenta

        self.initialize_dicts_for_plot_cached_data()

        self.controls_bar = self.create_controls_bar()
        self.main_layout.addWidget(self.controls_bar)
        self.main_layout.addSpacing(2)
        self.loading_row = self.create_loading_row()
        self.main_layout.addLayout(self.loading_row)
        self.main_layout.addSpacing(2)

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

        has_multiple_files_from_fitting = (
            self.read_mode
            and self.preloaded_fitting
            and any(
                "file_index" in r for r in self.preloaded_fitting if "error" not in r
            )
        )

        # For spectroscopy: use multi-file logic only if we have multiple entries with file_index
        has_multiple_files_from_spectroscopy = (
            self.read_mode
            and self.data
            and any("file_index" in d for d in self.data)
            and len(self.data) > 1
        )

        has_multiple_files = (
            has_multiple_files_from_fitting or has_multiple_files_from_spectroscopy
        )

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
                self.display_plot(
                    data_point["title"], data_point["channel_index"], index
                )

        if self.read_mode and self.preloaded_fitting:
            self.process_fitting_results(self.preloaded_fitting)
        self.scroll_widget.setLayout(self.plot_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addSpacing(0)  # Tolto lo spazio in basso
        self.errors_layout = QVBoxLayout()
        self.main_layout.addLayout(self.errors_layout)
        self.main_layout.addSpacing(0)  # Tolto lo spazio in basso
        self.setLayout(self.main_layout)
        self.app.widgets[s.FITTING_POPUP] = self

        # Schedule a refresh after the window is shown to ensure plots are visible
        from PyQt6.QtCore import QTimer

        # Cancel any existing timers to avoid conflicts
        if hasattr(self, "_refresh_timer") and self._refresh_timer is not None:
            self._refresh_timer.stop()

        self._refresh_timer = QTimer()
        self._refresh_timer.singleShot(100, self.force_plots_refresh)

        # Re-enable UI updates and showing after initialization
        self.setUpdatesEnabled(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Plot refresh
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Window utilities
    # ------------------------------------------------------------------

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
