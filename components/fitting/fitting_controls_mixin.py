"""
fitting_controls_mixin.py
=========================
Mixin class providing the top control bar, loading indicator,
fitting trigger, export and reset functionality.
"""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QMovie
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
)
from components.gradient_text import GradientText
from utils.gui_styles import GUIStyles
from utils.layout_utilities import clear_layout_widgets
from components.lin_log_control import LinLogControl
from utils.resource_path import resource_path
from utils.export_data import ExportData
from utils.fitting_utilities import convert_fitting_result_into_json_serializable_item
import settings.settings as s


class FittingControlsMixin:
    """Mixin that provides the control bar, loading row, start/reset and export actions."""

    # ------------------------------------------------------------------
    # Controls bar
    # ------------------------------------------------------------------

    def create_controls_bar(self):
        """
        Creates the top control bar with title and action buttons.

        Returns:
            QWidget: The widget containing the control bar.
        """
        from components.buttons import ExportPlotImageButton

        controls_bar_widget = QWidget()
        controls_bar_widget.setObjectName("controlsBar")
        controls_bar_widget.setContentsMargins(0,10,0,10)
        controls_bar_widget.setStyleSheet(
            "#controlsBar { border-bottom: 1px solid #282828; }"
        )
        controls_bar_widget.setStyleSheet("background-color: #1c1c1c;")
        controls_bar = QVBoxLayout()
        controls_bar.setContentsMargins(0, 0, 0, 0)
        # --- Custom alignment row for title and algorithm selector ---
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(0)
        controls_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Container for title and algorithm selector, vertically centered
        title_algo_widget = QWidget()
        title_algo_layout = QHBoxLayout()
        title_algo_layout.setContentsMargins(0, 0, 0, 0)
        title_algo_layout.setSpacing(20)
        title_algo_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        fitting_title = GradientText(
            self,
            text="INTENSITY DECAY FITTING",
            colors=[(0.7, "#1E90FF"), (1.0, s.PALETTE_RED_1)],
            stylesheet=GUIStyles.set_main_title_style(),
        )

        fitting_title.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        title_algo_layout.addSpacing(10)
        title_algo_layout.addWidget(
            fitting_title, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        # Algorithm selector layout
        algorithm_layout = QVBoxLayout()
        algorithm_layout.setContentsMargins(0, 0, 0, 0)

        algorithm_row_widget = QWidget()
        algorithm_row_widget.setMinimumHeight(36)  # Ridotto

        algorithm_row_widget.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )
        algorithm_row_layout = QHBoxLayout()
        algorithm_row_layout.setContentsMargins(0, 0, 0, 0)
        algorithm_row_layout.setSpacing(8)
        algorithm_row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        algorithm_label = QLabel("Fitting Algorithm: Levenberg-Marquardt")
        algorithm_label.setStyleSheet(GUIStyles.fitting_algorithm_label_style())
        algorithm_label.setMinimumHeight(36)
        algorithm_label.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        algorithm_row_layout.addWidget(
            algorithm_label, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        algorithm_row_widget.setLayout(algorithm_row_layout)
        algorithm_layout.addWidget(algorithm_row_widget)

        title_algo_layout.addLayout(algorithm_layout)
        title_algo_widget.setLayout(title_algo_layout)
        controls_row.addWidget(
            title_algo_widget, alignment=Qt.AlignmentFlag.AlignVCenter
        )
        controls_row.addSpacing(30)

        # Export fitting data btn
        self.export_fitting_btn = QPushButton("EXPORT")
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:  #11468F; font-weight: bold; padding: 8px; border-radius: 4px;"
        )
        self.export_fitting_btn.setFixedHeight(36)
        self.export_fitting_btn.setFixedWidth(90)
        self.export_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_fitting_btn.clicked.connect(self.export_fitting_data)
        self.export_fitting_btn.setEnabled(False)

        # Show export button only in ACQUIRE mode, hide in READ mode (fitting popup only)
        is_read_mode = (
            hasattr(self.app, "acquire_read_mode")
            and self.app.acquire_read_mode == "read"
        )
        self.export_fitting_btn.setVisible(not is_read_mode)
        # Start fitting btn
        self.start_fitting_btn = QPushButton("START FITTING")
        self.start_fitting_btn.setObjectName("btn")
        GUIStyles.set_start_btn_style(self.start_fitting_btn)
        self.start_fitting_btn.setFixedHeight(36)
        self.start_fitting_btn.setFixedWidth(150)
        self.start_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_fitting_btn.clicked.connect(self.start_fitting)
        # Hide START FITTING button if preloaded_fitting exists (already fitted data)
        self.start_fitting_btn.setVisible(self.preloaded_fitting is None)
        # Reset btn
        reset_btn = QPushButton("RESET")
        reset_btn.setObjectName("btn")
        GUIStyles.set_stop_btn_style(reset_btn)
        reset_btn.setFixedHeight(36)
        reset_btn.setFixedWidth(150)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset)
        # Export plot img btn
        self.export_img_btn = ExportPlotImageButton(app=self.app, height=36)
        # Set initial visibility based on save_plot_img parameter
        # Hide if in read mode without preloaded fitting (will show after fitting completes)
        initial_visibility = self.save_plot_img and not (self.read_mode and self.preloaded_fitting is None)
        self.export_img_btn.setVisible(initial_visibility)
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
        # controls_bar.addWidget(draw_layout_separator())

        controls_bar_widget.setLayout(controls_bar)
        return controls_bar_widget

    # ------------------------------------------------------------------
    # Loading row
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Start fitting
    # ------------------------------------------------------------------

    def start_fitting(self):
        from components.fitting.fitting_worker import FittingWorker

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

    # ------------------------------------------------------------------
    # Export fitting data
    # ------------------------------------------------------------------

    def export_fitting_data(self):
        """Exports the fitting results to files with ROI-aware data."""

        # Build IRFs and raw signals for export (use ROI-cut data if available)
        irfs_to_export = []
        raw_signals_to_export = []

        for result in self.fitting_results:
            # Get channel from result
            channel = result.get("channel_index", result.get("channel", 0))

            # Use ROI-cut IRF if available, otherwise find original IRF
            if channel in self.cut_irfs:
                irfs_to_export.append(self.cut_irfs[channel])
            else:
                # Find original IRF index for this channel
                data_index = next(
                    (
                        idx
                        for idx, d in enumerate(self.data)
                        if d.get("channel_index") == channel
                    ),
                    None,
                )
                if data_index is not None and data_index < len(self.irfs):
                    irfs_to_export.append(self.irfs[data_index])
                else:
                    irfs_to_export.append(None)

            # Use ROI-cut raw signal if available, otherwise find original
            if channel in self.cut_raw_signals:
                raw_signals_to_export.append({"y": self.cut_raw_signals[channel]})
            else:
                data_index = next(
                    (
                        idx
                        for idx, d in enumerate(self.data)
                        if d.get("channel_index") == channel
                    ),
                    None,
                )
                if data_index is not None and data_index < len(self.raw_signals):
                    raw_signals_to_export.append(self.raw_signals[data_index])
                else:
                    raw_signals_to_export.append(None)

        parsed_fitting_results = convert_fitting_result_into_json_serializable_item(
            self.fitting_results,
            raw_signals_to_export,
            self.use_deconvolution,
            irfs_to_export,
            self.laser_period_ns,
            self.irfs_tau_ns,
        )
        ExportData.save_fitting_data(parsed_fitting_results, self, self.app)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self):
        """Resets the popup to its initial state, clearing all plots and results."""
        # Block UI updates during reset to prevent visual glitches and improve performance
        self.setUpdatesEnabled(False)

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
        self.cut_irfs.clear()
        self.cut_raw_signals.clear()
        for ch, checkbox in self.roi_checkboxes.items():
            if checkbox:
                checkbox.setChecked(False)

        # Check if multi-file mode to create single plot or multiple plots
        has_multiple_files_from_fitting = (
            self.read_mode
            and self.preloaded_fitting
            and any(
                "file_index" in r for r in self.preloaded_fitting if "error" not in r
            )
        )
        has_multiple_files_from_spectroscopy = (
            self.data
            and any("file_index" in d for d in self.data)
            and len(self.data) > 1
        )  # Only multi-file if more than 1 entry
        has_multiple_files = (
            has_multiple_files_from_fitting or has_multiple_files_from_spectroscopy
        )

        if has_multiple_files:
            # Create single plot for multiple files comparison
            title = "Multi-File Comparison"
            self.cached_counts_data[0] = {"y": [], "x": []}
            self.cached_fitted_data[0] = {"y": [], "x": []}
            self.display_plot(title, 0, 0)
            # Enable lin/log control for multi-file spectroscopy visualization
            if (
                has_multiple_files_from_spectroscopy
                and not has_multiple_files_from_fitting
            ):
                LinLogControl.set_lin_log_switches_enable_mode(
                    self.lin_log_switches, True
                )
        else:
            # Create plot for each channel (single file mode)
            for index, data_point in enumerate(self.data):
                self.display_plot(
                    data_point["title"], data_point["channel_index"], index
                )

        self.export_img_btn.setVisible(False)

        # Re-enable UI updates after reset
        self.setUpdatesEnabled(True)
