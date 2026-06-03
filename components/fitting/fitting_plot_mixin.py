"""
fitting_plot_mixin.py
=====================
Mixin that provides all plot creation and update methods for the fitting popup.
"""

import os
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)
from components.lin_log_control import LinLogControl
from utils.gui_styles import GUIStyles
from core.phasors_controller import PhasorsController
import settings.settings as s


class FittingPlotMixin:
    """Mixin that handles all pyqtgraph plot creation, display and updates."""

    # ------------------------------------------------------------------
    # Spectroscopy curve display
    # ------------------------------------------------------------------

    def display_spectroscopy_curve(self, plot_widget, channel):
        """
        Displays the initial spectroscopy curve on a plot (raw or deconvolved).

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

        # Get time_shift from data if available (read-mode), otherwise use app.time_shifts (acquire-mode)
        time_shift = data[0].get(
            "time_shift",
            0 if channel not in self.app.time_shifts else self.app.time_shifts[channel],
        )
        y = np.roll(y_data, time_shift)

        # Add legend for single file case
        if (
            not hasattr(plot_widget.plotItem, "legend")
            or plot_widget.plotItem.legend is None
        ):
            plot_widget.addLegend(offset=(10, 10))

        # Get file name from data or fallback to reader_data
        file_name = data[0].get("file_name", "File 1")

        if file_name in ["File 1", "Single File"] or not file_name:
            # Try to get actual file name from reader_data
            fitting_files = (
                self.app.reader_data.get("fitting", {})
                .get("files", {})
                .get("spectroscopy", "")
            )
            if fitting_files:
                if isinstance(fitting_files, str):
                    file_name = os.path.basename(fitting_files)
                elif isinstance(fitting_files, list) and len(fitting_files) > 0:
                    file_name = os.path.basename(fitting_files[0])

            # If still no good name, try alternative paths
            if file_name in ["File 1", "Single File"] or not file_name:
                # Try spectroscopy files from main reader_data
                spectroscopy_files = (
                    self.app.reader_data.get("spectroscopy", {})
                    .get("files", {})
                    .get("spectroscopy", "")
                )
                if spectroscopy_files:
                    if isinstance(spectroscopy_files, str):
                        file_name = os.path.basename(spectroscopy_files)
                    elif (
                        isinstance(spectroscopy_files, list)
                        and len(spectroscopy_files) > 0
                    ):
                        file_name = os.path.basename(spectroscopy_files[0])

        # Plot IRF and raw signal ONLY in acquire mode (use_deconvolution is True)
        if self.use_deconvolution and self.irfs and self.raw_signals:
            # Find the index of this channel in self.data (since channels may not be 0,1,2...)
            data_index = None
            for idx, d in enumerate(self.data):
                if d["channel_index"] == channel:
                    data_index = idx
                    break

            if data_index is not None and data_index < len(self.irfs):
                irf = np.array(self.irfs[data_index])
                if len(irf) == len(x_data) and np.max(irf) > 0:
                    # Normalize IRF to 80% of max counts for visibility
                    irf_normalized = (irf / np.max(irf)) * np.max(y) * 0.8
                    plot_widget.plot(
                        x_data,
                        irf_normalized,
                        pen=pg.mkPen("#FFA500", width=1, style=Qt.PenStyle.DashLine),
                        name="IRF",
                    )

                # Plot raw signal
                if data_index < len(self.raw_signals):
                    raw_signal_data = self.raw_signals[data_index]
                    raw_signal = np.array(
                        raw_signal_data["y"]
                        if isinstance(raw_signal_data, dict)
                        else raw_signal_data
                    )
                    if len(raw_signal) == len(x_data):
                        plot_widget.plot(
                            x_data,
                            raw_signal,
                            pen=pg.mkPen(
                                "#00FFFF", width=1, style=Qt.PenStyle.DashLine
                            ),
                            name="Raw Signal",
                        )

        # Plot the main signal (deconvolved or raw) with prominence
        plot_widget.plot(
            x_data,
            y,
            pen=pg.mkPen("#f72828", width=2),
            name="Deconvolved Signal" if self.use_deconvolution else "Raw Signal",
        )

        return x_data, y

    # ------------------------------------------------------------------
    # Full plot area creation
    # ------------------------------------------------------------------

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
        is_read_tab = (
            hasattr(self.app, "acquire_read_mode")
            and self.app.acquire_read_mode == "read"
        )
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
            self.read_mode
            and self.preloaded_fitting
            and any(
                "file_index" in r for r in self.preloaded_fitting if "error" not in r
            )
        )

        is_multi_file_spectroscopy = (
            self.data
            and any("file_index" in d for d in self.data)
            and len(self.data) > 1
        )

        # Set X-axis range based on mode
        if is_multi_file_fitting or is_multi_file_spectroscopy:
            # Auto-range for multi-file comparison
            plot_widget.enableAutoRange()
        else:
            # Single file mode: use actual data range instead of laser_period_ns
            if self.data and len(self.data) > 0:
                # Use first entry's x data for range calculation
                x_data = np.array(self.data[0].get("x", []))
                if len(x_data) > 0:
                    data_min = np.min(x_data)
                    data_max = np.max(x_data)
                    margin = (data_max - data_min) * 0.1  # 10% margin
                    plot_widget.setXRange(data_min - margin, data_max + margin)
                    plot_widget.setLimits(
                        xMin=data_min - margin, xMax=data_max + margin
                    )
                else:
                    # Fallback to laser period
                    margin = 0.5
                    plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
                    plot_widget.setLimits(
                        xMin=0 - margin, xMax=self.laser_period_ns + margin
                    )
            else:
                # Fallback to laser period if no data available
                margin = 0.5
                plot_widget.setXRange(0 - margin, self.laser_period_ns + margin)
                plot_widget.setLimits(
                    xMin=0 - margin, xMax=self.laser_period_ns + margin
                )

        # Handle spectroscopy curve and ROI based on mode
        if is_multi_file_spectroscopy:
            # Multi-file spectroscopy mode: display all files with different colors
            from core.phasors_controller import PhasorsController

            all_x_data = []
            all_y_data = []

            # Add legend BEFORE plotting so it can collect items
            is_read_mode = (
                hasattr(self.app, "acquire_read_mode")
                and self.app.acquire_read_mode == "read"
            )
            if (is_read_mode or self.read_mode) and len(
                self.preloaded_spectroscopy
            ) >= 1:
                legend = plot_widget.addLegend(offset=(10, 10))
                legend.setLabelTextColor("white")

            # Display spectroscopy curves for all files
            for file_idx, spectroscopy_data in enumerate(self.preloaded_spectroscopy):
                if "error" in spectroscopy_data:
                    continue
                # In multi-file mode, display all files (channel filter removed)
                x = spectroscopy_data.get("x", [])
                y_data = np.array(spectroscopy_data.get("y", []))

                # Apply time shift if present
                time_shift = spectroscopy_data.get("time_shift", 0)
                if time_shift != 0 and len(y_data) > 0:
                    y = np.roll(y_data, time_shift)
                else:
                    y = y_data

                if len(x) > 0 and len(y) > 0:
                    all_x_data.extend(x)
                    all_y_data.extend(y)

                    # Get color for this file
                    actual_file_idx = spectroscopy_data.get("file_index", file_idx)
                    # Use cyan for single file to be more visible, otherwise use file-specific color
                    if len(self.preloaded_spectroscopy) == 1:
                        color = "#00d4ff"  # Cyan for single file
                    else:
                        color = PhasorsController.get_color_for_file_index(
                            actual_file_idx
                        )

                    # Plot with color and legend
                    file_name = spectroscopy_data.get(
                        "file_name", f"File {actual_file_idx + 1}"
                    )
                    # Clean file name for legend (remove path and extension)
                    import os

                    legend_name = (
                        os.path.splitext(os.path.basename(file_name))[0]
                        if file_name
                        else f"File {actual_file_idx + 1}"
                    )
                    pen = pg.mkPen(color=color, width=2)
                    plot_item = plot_widget.plot(x, y, pen=pen, name=legend_name)

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
                roi.sigRegionChangeFinished.connect(lambda: self.limit_roi_bounds(roi))
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
            if self.data and len(self.data) > 0:
                # Find data for this channel
                channel_data = [d for d in self.data if d["channel_index"] == channel]
                if channel_data:
                    data_entry = channel_data[0]
                    x = data_entry["x"]
                    time_shift = data_entry.get(
                        "time_shift",
                        0
                        if channel not in self.app.time_shifts
                        else self.app.time_shifts[channel],
                    )
                    y = np.roll(data_entry["y"], time_shift)

                    # Cache the data for lin/log controls
                    self.cached_counts_data[channel] = {"x": x, "y": y}

                    # Plot the spectroscopy curve
                    curve_item = plot_widget.plot(
                        x, y, pen=pg.mkPen("#f72828", width=2), name="Spectroscopy"
                    )

                    # Add ROI selection (same as acquire mode)
                    # Initialize ROI based on data range
                    x_min, x_max = np.min(x), np.max(x)
                    roi_start = x_min + (x_max - x_min) * 0.1  # 10% from start
                    roi_end = x_min + (x_max - x_min) * 0.5  # 50% from start
                    roi = pg.LinearRegionItem([roi_start, roi_end])
                    result = self.get_saved_roi(channel)
                    # Only use saved ROI if it's valid (min != max, within data range)
                    if result is not None:
                        min_x_saved, max_x_saved = result
                        # Check if saved values are within actual data range (with some tolerance)
                        data_range = x_max - x_min
                        if (
                            min_x_saved != max_x_saved
                            and abs(max_x_saved - min_x_saved) > 1
                            and min_x_saved >= x_min - data_range * 0.1
                            and max_x_saved <= x_max + data_range * 0.1
                        ):  # Valid range
                            roi.setRegion([min_x_saved, max_x_saved])
                            self.set_roi_mask(roi, x, y, channel)
                    roi.setVisible(False)
                    roi.sigRegionChanged.connect(
                        lambda roi=roi, x=x, y=y, ch=channel: self.on_roi_selection_changed(
                            roi, x, y, ch
                        )
                    )
                    roi.sigRegionChangeFinished.connect(
                        lambda roi=roi: self.limit_roi_bounds(roi)
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
        fitted_params_container.fitted_params_layout = (
            fitted_params_layout  # Save reference
        )

        # Store container reference for multi-file updates
        if not hasattr(self, "params_containers"):
            self.params_containers = {}
        self.params_containers[channel] = fitted_params_container

        # Create vertical container for single file: title on top, params below
        single_file_container = QWidget()
        single_file_vlayout = QVBoxLayout(single_file_container)
        single_file_vlayout.setContentsMargins(0, 0, 0, 0)
        single_file_vlayout.setSpacing(5)

        # Add "Fitted parameters:" title label
        params_title = QLabel("Fitted parameters:")
        params_title.setStyleSheet(
            "color: #cecece; font-family: Montserrat; font-size: 16px;"
        )
        single_file_vlayout.addWidget(params_title)

        # Add single label for single file mode
        fitted_params_text = QLabel("")
        fitted_params_text.setStyleSheet(
            "color: #cecece; font-family: Montserrat; font-size: 16px;"
        )
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

    # ------------------------------------------------------------------
    # Plot update dispatcher
    # ------------------------------------------------------------------

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
            self._update_plot_multiple_files(
                result, channel, plot_widget, residuals_widget, fitted_params_text
            )
        else:
            self._update_plot_single_file(
                result, channel, plot_widget, residuals_widget, fitted_params_text
            )

    # ------------------------------------------------------------------
    # Single-file plot update
    # ------------------------------------------------------------------

    def _update_plot_single_file(
        self, result, channel, plot_widget, residuals_widget, fitted_params_text
    ):
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

        if (
            hasattr(plot_widget.plotItem, "legend")
            and plot_widget.plotItem.legend is not None
        ):
            plot_widget.plotItem.legend.scene().removeItem(plot_widget.plotItem.legend)
            plot_widget.plotItem.legend = None

        plot_widget.clear()

        legend = plot_widget.addLegend(offset=(0, 20), labelTextSize="11pt")
        legend.setParent(plot_widget)

        # Get file name for legend with comprehensive fallback resolution
        file_index = result.get("file_index", 0)
        file_name = result.get("file_name", f"File {file_index + 1}")

        # Try to resolve actual file name if it's a generic placeholder
        if (
            file_name in ["File 1", f"File {file_index + 1}", "Single File"]
            or not file_name
        ):
            # Try fitting/spectroscopy path
            fitting_files = (
                self.app.reader_data.get("fitting", {})
                .get("files", {})
                .get("spectroscopy", "")
            )
            if fitting_files:
                if isinstance(fitting_files, str):
                    file_name = os.path.basename(fitting_files)
                elif (
                    isinstance(fitting_files, list) and len(fitting_files) > file_index
                ):
                    file_name = os.path.basename(fitting_files[file_index])

            # Try fitting/fitting path if still not resolved
            if (
                file_name in ["File 1", f"File {file_index + 1}", "Single File"]
                or not file_name
            ):
                fitting_files = (
                    self.app.reader_data.get("fitting", {})
                    .get("files", {})
                    .get("fitting", "")
                )
                if fitting_files:
                    if isinstance(fitting_files, str):
                        file_name = os.path.basename(fitting_files)
                    elif (
                        isinstance(fitting_files, list)
                        and len(fitting_files) > file_index
                    ):
                        file_name = os.path.basename(fitting_files[file_index])

            # Try spectroscopy/spectroscopy path if still not resolved
            if (
                file_name in ["File 1", f"File {file_index + 1}", "Single File"]
                or not file_name
            ):
                spectroscopy_files = (
                    self.app.reader_data.get("spectroscopy", {})
                    .get("files", {})
                    .get("spectroscopy", "")
                )
                if spectroscopy_files:
                    if isinstance(spectroscopy_files, str):
                        file_name = os.path.basename(spectroscopy_files)
                    elif (
                        isinstance(spectroscopy_files, list)
                        and len(spectroscopy_files) > file_index
                    ):
                        file_name = os.path.basename(spectroscopy_files[file_index])

            # Try metadata as final fallback
            if (
                file_name in ["File 1", f"File {file_index + 1}", "Single File"]
                or not file_name
            ):
                metadata = self.app.reader_data.get("metadata", {})
                if isinstance(metadata, list) and len(metadata) > file_index:
                    metadata_item = metadata[file_index]
                    if (
                        isinstance(metadata_item, dict)
                        and "filename_raw" in metadata_item
                    ):
                        file_name = metadata_item["filename_raw"]

        color = PhasorsController.get_color_for_file_index(file_index)

        # Add explanatory legend entries first
        counts_label = "Deconv Counts" if self.use_deconvolution else "Counts"
        legend_counts = plot_widget.plot(
            [],
            [],
            pen=pg.mkPen(None),
            symbol="o",
            symbolSize=6,
            symbolBrush=pg.mkBrush("#f72828"),
            name=counts_label,
        )
        legend_fitted = plot_widget.plot(
            [], [], pen=pg.mkPen("#f72828", width=2), name="Fitted curve"
        )

        # Add IRF and raw signal to legend ONLY in acquire mode
        if self.use_deconvolution and self.irfs and self.raw_signals:
            # Check if we have data for this channel
            data_index = None
            for idx, d in enumerate(self.data):
                if d["channel_index"] == channel:
                    data_index = idx
                    break
            if data_index is not None and data_index < len(self.irfs):
                legend_raw = plot_widget.plot(
                    [],
                    [],
                    pen=pg.mkPen(None),
                    symbol="s",
                    symbolSize=6,
                    symbolBrush=pg.mkBrush("#00FFFF"),
                    name="Raw Signal Counts",
                )
                legend_irf = plot_widget.plot(
                    [],
                    [],
                    pen=pg.mkPen("#FFA500", width=2, style=Qt.PenStyle.DashLine),
                    name="IRF",
                )

        # Ensure arrays have matching lengths
        min_len = min(len(truncated_x_values), len(y_data))
        truncated_x_values = truncated_x_values[:min_len]
        y_data = y_data[:min_len]

        # For fitted data, ensure matching lengths
        fitted_min_len = min(
            len(self.cached_fitted_data[channel]["x"]), len(fitted_data)
        )
        fitted_x = self.cached_fitted_data[channel]["x"][:fitted_min_len]
        fitted_y = fitted_data[:fitted_min_len]

        # Plot IRF and raw signal ONLY in acquire mode (before main data for z-order)
        if self.use_deconvolution and self.irfs and self.raw_signals:
            # Find the index of this channel in self.data
            data_index = None
            for idx, d in enumerate(self.data):
                if d["channel_index"] == channel:
                    data_index = idx
                    break

            if data_index is not None and data_index < len(self.irfs):
                # Use cut IRF if available (ROI applied), otherwise use full IRF
                if channel in self.cut_irfs:
                    irf = self.cut_irfs[channel]
                else:
                    irf = np.array(self.irfs[data_index])
                irf_x_full = result["x_values"]
                decay_start = result["decay_start"]
                if len(irf) > decay_start and len(irf_x_full) > decay_start:
                    irf = irf[decay_start:]
                    irf_x = irf_x_full[decay_start:]
                else:
                    irf_x = irf_x_full

                # Ensure IRF and X have matching lengths
                min_len = min(len(irf), len(irf_x))
                irf = irf[:min_len]
                irf_x = irf_x[:min_len]

                if len(irf) > 0 and np.max(irf) > 0:
                    # Normalize IRF to 80% of max counts (counts already trimmed with decay_start)
                    irf_normalized = (
                        (irf / np.max(irf))
                        * np.max(self.cached_counts_data[channel]["y"])
                        * 0.8
                    )
                    # Apply lin/log transformation to IRF
                    if (
                        channel not in self.lin_log_modes
                        or self.lin_log_modes[channel] == "LIN"
                    ):
                        _, irf_transformed = LinLogControl.calculate_lin_mode(
                            irf_normalized
                        )
                    else:
                        irf_transformed, _, _ = LinLogControl.calculate_log_ticks(
                            irf_normalized
                        )

                    # Ensure final matching lengths
                    final_len = min(len(irf_x), len(irf_transformed))
                    plot_widget.plot(
                        irf_x[:final_len],
                        irf_transformed[:final_len],
                        pen=pg.mkPen("#FFA500", width=2, style=Qt.PenStyle.DashLine),
                    )

                # Plot raw signal if available
                if data_index < len(self.raw_signals):
                    # Use cut raw signal if available (ROI applied), otherwise use full raw signal
                    if channel in self.cut_raw_signals:
                        raw_signal = self.cut_raw_signals[channel]
                    else:
                        raw_signal_data = self.raw_signals[data_index]
                        raw_signal = np.array(
                            raw_signal_data["y"]
                            if isinstance(raw_signal_data, dict)
                            else raw_signal_data
                        )
                    raw_signal_x_full = result["x_values"]
                    if (
                        len(raw_signal) > decay_start
                        and len(raw_signal_x_full) > decay_start
                    ):
                        raw_signal = raw_signal[decay_start:]
                        raw_signal_x = raw_signal_x_full[decay_start:]
                    else:
                        raw_signal_x = raw_signal_x_full

                    # Ensure raw signal and X have matching lengths
                    min_len = min(len(raw_signal), len(raw_signal_x))
                    raw_signal = raw_signal[:min_len]
                    raw_signal_x = raw_signal_x[:min_len]

                    if len(raw_signal) > 0:
                        # Apply lin/log transformation to raw signal
                        if (
                            channel not in self.lin_log_modes
                            or self.lin_log_modes[channel] == "LIN"
                        ):
                            _, raw_transformed = LinLogControl.calculate_lin_mode(
                                raw_signal
                            )
                        else:
                            raw_transformed, _, _ = LinLogControl.calculate_log_ticks(
                                raw_signal
                            )

                        # Ensure final matching lengths
                        final_len = min(len(raw_signal_x), len(raw_transformed))
                        plot_widget.plot(
                            raw_signal_x[:final_len],
                            raw_transformed[:final_len],
                            pen=None,
                            symbol="s",
                            symbolSize=6,
                            symbolBrush=pg.mkBrush("#00FFFF"),
                        )

        # Plot Counts (points) with symbolSize=6 - prominence for deconv counts
        plot_widget.plot(
            truncated_x_values,
            y_data,
            pen=None,
            symbol="o",
            symbolSize=6,
            symbolBrush=color,
        )

        # Plot Fitted curve (line) with prominence
        plot_widget.plot(
            fitted_x,
            fitted_y,
            pen=pg.mkPen(color, width=2.5),
        )

        # Plot original spectroscopy curve in read mode (red line width=1)
        if self.read_mode and self.preloaded_spectroscopy:
            # Get original spectroscopy data for this channel
            spectroscopy_data = None
            if isinstance(self.preloaded_spectroscopy, list):
                for spec_data in self.preloaded_spectroscopy:
                    if spec_data.get("channel") == channel:
                        spectroscopy_data = spec_data
                        break
            elif (
                isinstance(self.preloaded_spectroscopy, dict)
                and self.preloaded_spectroscopy.get("channel") == channel
            ):
                spectroscopy_data = self.preloaded_spectroscopy

            if spectroscopy_data:
                spec_x = np.array(spectroscopy_data.get("x_values", []))
                spec_y = np.array(spectroscopy_data.get("y_values", []))
                if len(spec_x) > 0 and len(spec_y) > 0:
                    # Apply lin/log transformation
                    if (
                        channel not in self.lin_log_modes
                        or self.lin_log_modes[channel] == "LIN"
                    ):
                        _, spec_y_transformed = LinLogControl.calculate_lin_mode(spec_y)
                    else:
                        spec_y_transformed, _, _ = LinLogControl.calculate_log_ticks(
                            spec_y
                        )

                    plot_widget.plot(
                        spec_x,
                        spec_y_transformed,
                        pen=pg.mkPen("#f72828", width=1),
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
            interp_func = interp1d(
                fitted_x,
                fitted_y,
                kind="linear",
                bounds_error=False,
                fill_value="extrapolate",
            )
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
            truncated_x_values[:residuals_min_len],
            residuals[:residuals_min_len],
            pen=pg.mkPen("#1E90FF", width=2),
        )
        residuals_widget.addLine(y=0, pen=pg.mkPen("w", style=Qt.PenStyle.DashLine))
        if len(result["fitted_params_text"]) > 55:
            fitted_params_text.setWordWrap(True)
        # Remove "Fitted parameters:\n" from the beginning since there's already a title label
        params_text_clean = result["fitted_params_text"].replace(
            "Fitted parameters:\n", "", 1
        )
        fitted_params_text.setText(params_text_clean)

    # ------------------------------------------------------------------
    # Multi-file plot update
    # ------------------------------------------------------------------

    def _update_plot_multiple_files(
        self, results, channel, plot_widget, residuals_widget, fitted_params_text
    ):
        """Updates plot with multiple file data using different colors."""
        from core.plots_controller import PlotsController

        # Show the fitted parameters container now that we have results
        if channel in self.params_containers:
            self.params_containers[channel].setVisible(True)

        if (
            hasattr(plot_widget.plotItem, "legend")
            and plot_widget.plotItem.legend is not None
        ):
            plot_widget.plotItem.legend.scene().removeItem(plot_widget.plotItem.legend)
            plot_widget.plotItem.legend = None

        plot_widget.clear()
        legend = plot_widget.addLegend(offset=(0, 20), labelTextSize="11pt")
        legend.setParent(plot_widget)

        # Add global legend entries to explain symbols
        plot_widget.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=6,
            symbolBrush=pg.mkBrush("gray"),
            name="Counts",
        )
        plot_widget.plot([], [], pen=pg.mkPen("gray", width=2), name="Fitted curve")

        all_y_data = []
        all_fitted_data = []
        all_y_data_original = []  # Original data before transformation
        all_fitted_data_original = []  # Original fitted data before transformation

        for idx, result in enumerate(results):
            file_index = result.get("file_index", 0)
            file_name = result.get("file_name", f"File {file_index + 1}")
            color = PhasorsController.get_color_for_file_index(file_index)

            # Get x values
            decay_start = result["decay_start"]
            truncated_x_values = np.array(result["x_values"][decay_start:])

            # Calculate y_data (full array, scaled)
            y_data_full = np.array(result["y_data"]) * result["scale_factor"]
            fitted_data_full = (
                np.array(result["fitted_values"]) * result["scale_factor"]
            )

            # Store original data for tick calculation
            all_y_data_original.extend(y_data_full)
            all_fitted_data_original.extend(fitted_data_full)

            # Apply lin/log mode to full arrays
            if (
                channel not in self.lin_log_modes
                or self.lin_log_modes[channel] == "LIN"
            ):
                _, y_data_transformed = LinLogControl.calculate_lin_mode(y_data_full)
                _, fitted_data_transformed = LinLogControl.calculate_lin_mode(
                    fitted_data_full
                )
            else:
                y_data_transformed, _, _ = LinLogControl.calculate_log_ticks(
                    y_data_full
                )
                fitted_data_transformed, _, _ = LinLogControl.calculate_log_ticks(
                    fitted_data_full
                )

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
            if (
                channel not in self.lin_log_modes
                or self.lin_log_modes[channel] == "LIN"
            ):
                y_ticks, _ = LinLogControl.calculate_lin_mode(
                    np.array(all_y_data_original + all_fitted_data_original)
                )
            else:
                _, y_ticks, _ = LinLogControl.calculate_log_ticks(
                    np.array(all_y_data_original + all_fitted_data_original)
                )

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
            file_index = result.get("file_index", 0)
            color = PhasorsController.get_color_for_file_index(file_index)
            residuals = result["residuals"]
            residuals_x = result["x_values"][result["decay_start"] :]
            min_len_res = min(len(residuals_x), len(residuals))
            residuals_widget.plot(
                residuals_x[:min_len_res],
                residuals[:min_len_res],
                pen=pg.mkPen(color, width=2),
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
                "y": np.array(first_result["y_data"]) * first_result["scale_factor"],
            }
            self.cached_fitted_data[channel] = {
                "x": np.array(first_result["t_data"]),
                "y": np.array(first_result["fitted_values"])
                * first_result["scale_factor"],
            }

        # Clear existing widgets
        while params_layout.count():
            item = params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add one label per file, with "Fitted parameters:" title above each
        for result in results:
            file_index = result.get("file_index", 0)
            file_name = result.get("file_name", f"File {file_index + 1}")
            color = PhasorsController.get_color_for_file_index(file_index)
            # Remove "Fitted parameters:\n" from beginning - we'll add it as a separate title
            params_text = result["fitted_params_text"].replace(
                "Fitted parameters:\n", "", 1
            )

            # Create a vertical container: title on top, then color indicator + text
            file_container = QWidget()
            file_vlayout = QVBoxLayout(file_container)
            file_vlayout.setContentsMargins(0, 0, 0, 0)
            file_vlayout.setSpacing(5)

            # Add "Fitted parameters:" title for this file
            file_title = QLabel("Fitted parameters:")
            file_title.setStyleSheet(
                "color: #cecece; font-family: Montserrat; font-size: 16px;"
            )
            file_vlayout.addWidget(file_title)

            # Create horizontal layout for color indicator + parameters
            content_widget = QWidget()
            content_hlayout = QHBoxLayout(content_widget)
            content_hlayout.setContentsMargins(0, 0, 0, 0)
            content_hlayout.setSpacing(10)

            # Add colored rectangle as indicator
            color_indicator = QLabel()
            color_indicator.setFixedSize(15, 15)
            color_indicator.setStyleSheet(
                f"background-color: {color}; border-radius: 3px;"
            )
            content_hlayout.addWidget(
                color_indicator, alignment=Qt.AlignmentFlag.AlignTop
            )

            # Add parameters text (convert newlines to <br> for HTML)
            colored_params_text = params_text.replace("\n", "<br>")

            file_label = QLabel(colored_params_text)
            file_label.setTextFormat(Qt.TextFormat.RichText)
            file_label.setStyleSheet(
                "color: #cecece; font-family: Montserrat; font-size: 16px;"
            )
            file_label.setWordWrap(True)
            content_hlayout.addWidget(file_label)

            file_vlayout.addWidget(content_widget)

            params_layout.addWidget(file_container)

    # ------------------------------------------------------------------
    # Grid layout helper
    # ------------------------------------------------------------------

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
