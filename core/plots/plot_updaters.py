"""
plot_updaters.py
============================================================
Real-time plot data update functions

Provides plain functions that update intensity plots (scrolling
time series) and decay curve plots (linear and logarithmic modes) during
acquisition or file reading sessions.
"""

import time
import numpy as np
from copy import deepcopy

from utils.helpers import get_realtime_adjustment_value
from components.lin_log_control import LinLogControl
import settings.settings as s

from PyQt6.QtWidgets import QApplication


def update_intensity_plots(app, channel_index, time_ns, curve):
    """
    Updates the intensity plot for a specific channel with new data.

    It appends the new data point (total counts in the curve vs. time)
    and trims the data from the left to maintain a fixed time window,
    creating a scrolling effect.

    Args:
        app: The main application instance.
        channel_index (int): The channel to update.
        time_ns (int): The timestamp of the new data in nanoseconds.
        curve (np.ndarray): The array of photon counts for the new data slice.
    """
    bin_width_micros = int(
        app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)
    )
    adjustment = (
        get_realtime_adjustment_value(
            app.selected_channels, app.tab_selected == s.TAB_PHASORS
        )
        / bin_width_micros
    )
    curve = tuple(x / adjustment for x in curve)
    if app.tab_selected in app.intensity_lines:
        if channel_index in app.intensity_lines[app.tab_selected]:
            intensity_line = app.intensity_lines[app.tab_selected][channel_index]
            if intensity_line is not None:
                x, y = intensity_line.getData()
                # Initialize or append data
                if x is None or (len(x) == 1 and x[0] == 0):
                    x = np.array([time_ns / 1_000_000_000])
                    y = np.array([np.sum(curve)])
                else:
                    x = np.append(x, time_ns / 1_000_000_000)
                    y = np.append(y, np.sum(curve))
                # Trim data based on time span
                if len(x) > 2:
                    while x[-1] - x[0] > app.cached_time_span_seconds:
                        x = x[1:]
                        y = y[1:]
                intensity_line.setData(x, y)


def update_spectroscopy_plots(app, x, y, channel_index, decay_curve):
    """
    Updates the decay curve plot, handling linear/log scales and time shifts.

    Args:
        app: The main application instance.
        x (np.ndarray): The x-axis data (time).
        y (np.ndarray): The y-axis data (counts).
        channel_index (int): The channel to update.
        decay_curve (pg.PlotDataItem): The plot item to update.
    """
    from core.plots.plot_builders import set_plot_y_range

    # Apply time_shift in both ACQUIRE and READ modes
    time_shift = (
        0
        if channel_index not in app.time_shifts
        else app.time_shifts[channel_index]
    )

    # Check if decay_widget exists for this channel
    if channel_index not in app.decay_widgets:
        return

    # Handle linear/logarithmic mode
    decay_widget = app.decay_widgets[channel_index]
    if (
        channel_index not in app.lin_log_mode
        or app.lin_log_mode[channel_index] == "LIN"
    ):
        decay_widget.showGrid(x=False, y=False, alpha=0.3)
        decay_curve.setData(x, np.roll(y, time_shift))
        set_plot_y_range(decay_widget)
    else:
        decay_widget.showGrid(x=False, y=True, alpha=0.3)
        sum_decay = y
        log_values, ticks, _ = LinLogControl.calculate_log_ticks(sum_decay)
        decay_curve.setData(x, np.roll(log_values, time_shift))
        axis = decay_widget.getAxis("left")
        axis.setTicks([ticks])
        set_plot_y_range(decay_widget)


def update_plots(app, channel_index, time_ns, curve, reader_mode=False):
    """
    Main function to update plots with new data during an acquisition.

    This function is called repeatedly with new data chunks. It dispatches
    the data to the intensity and decay curve update functions.

    Args:
        app: The main application instance.
        channel_index (int): The channel the data belongs to.
        time_ns (int): The timestamp of the data.
        curve (np.ndarray): The photon count data.
        reader_mode (bool, optional): True if data comes from a file reader,
                                      which affects how data is handled. Defaults to False.
    """
    if not reader_mode:
        # Update intensity plots
        update_intensity_plots(app, channel_index, time_ns, curve)

    # Get decay_curve if it exists, but don't fail if it doesn't (especially in reader_mode)
    decay_curve = None
    if (app.tab_selected in app.decay_curves and
            channel_index in app.decay_curves[app.tab_selected]):
        decay_curve = app.decay_curves[app.tab_selected][channel_index]

    # In reader_mode with fitting data, we can proceed without decay_curve
    if decay_curve is not None or (reader_mode and app.tab_selected == s.TAB_FITTING):
        if reader_mode:
            x, y = time_ns, curve
        elif decay_curve is not None:
            x, y = decay_curve.getData()
            if app.tab_selected == s.TAB_PHASORS:
                decay_curve.setData(x, curve + y)
            elif app.tab_selected in (s.TAB_SPECTROSCOPY, s.TAB_FITTING):
                last_cached_decay_value = app.cached_decay_values[
                    app.tab_selected
                ][channel_index]
                app.cached_decay_values[app.tab_selected][channel_index] = (
                    np.array(curve) + last_cached_decay_value
                )
                y = app.cached_decay_values[app.tab_selected][channel_index]
        if app.tab_selected in (s.TAB_SPECTROSCOPY, s.TAB_FITTING):
            update_spectroscopy_plots(app, x, y, channel_index, decay_curve)
        else:
            decay_curve.setData(x, curve + y)
    QApplication.processEvents()
    time.sleep(0.01)
    
    
    
def clear_plots(app, deep_clear=True):    
        """
        Clears all plots and associated data structures from the UI.

        Args:
            app: The main application instance.
            deep_clear (bool, optional): If True, performs a "deep" clear,
                which also resets cached data arrays and removes all widgets
                from the grid layout. If False, only clears plot features
                like legends and clusters. Defaults to True.
        """
        from core.phasors_controller import PhasorsController
        PhasorsController.clear_phasors_features(app, app.phasors_colorbars)
        PhasorsController.clear_phasors_features(app, app.quantization_images)
        PhasorsController.clear_phasors_features(app, app.phasors_clusters_center)
        PhasorsController.clear_phasors_features(app, app.phasors_legends)
        PhasorsController.clear_phasors_features(app, app.phasors_lifetime_points)
        PhasorsController.clear_phasors_file_scatters(app)
        PhasorsController.clear_phasors_files_legend(app)
        for ch in app.phasors_lifetime_texts:
            for _, item in enumerate(app.phasors_lifetime_texts[ch]):
                app.phasors_widgets[ch].removeItem(item)
        app.quantization_images.clear()
        app.phasors_colorbars.clear()
        app.phasors_clusters_center.clear()
        app.phasors_legends.clear()
        app.phasors_legend_labels.clear()  # Clear fixed legend labels
        app.phasors_lifetime_points.clear()
        app.phasors_lifetime_texts.clear()
        app.intensities_widgets.clear()
        app.phasors_charts.clear()
        app.phasors_widgets.clear()
        app.decay_widgets.clear()
        app.phasors_coords.clear()
        for i, animation in app.cps_widgets_animation.items():
            if animation:
                animation.stop()
        app.cps_widgets_animation.clear()
        app.cps_widgets.clear()
        app.cps_counts.clear()
        app.all_cps_counts.clear()
        app.all_SBR_counts.clear()
        app.SBR_items.clear()
        app.acquisition_time_countdown_widgets.clear()
        if deep_clear:
            app.intensity_lines = deepcopy(s.DEFAULT_INTENSITY_LINES)
            app.decay_curves = deepcopy(s.DEFAULT_DECAY_CURVES)
            app.cached_decay_values = deepcopy(s.DEFAULT_CACHED_DECAY_VALUES)
            PhasorsController.clear_phasors_points(app)
            for ch in app.plots_to_show:
                if app.tab_selected != s.TAB_PHASORS:
                    app.cached_decay_values[app.tab_selected][ch] = deepcopy([0])
            if "time_shift_sliders" in app.control_inputs:
                app.control_inputs["time_shift_sliders"].clear()
            if "time_shift_inputs" in app.control_inputs:
                app.control_inputs["time_shift_inputs"].clear()
            for i in reversed(range(app.grid_layout.count())):
                widget = app.grid_layout.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
                layout = app.grid_layout.itemAt(i).layout()
                if layout is not None:
                    clear_layout_tree(layout)