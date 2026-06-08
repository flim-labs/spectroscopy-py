"""
plot_initializers.py
============================================================
Data initialization helpers for intensity and decay curve plots.

Provides plain functions that retrieve cached plot data
or generate sensible numpy defaults based on application state.
"""

import numpy as np
import settings.settings as s
from utils.gui_styles import GUIStyles

from PyQt6.QtWidgets import (
    QWidget,
)


def generate_plots(app, frequency_mhz=0.0):
    """
    Generates and arranges all plots in the main grid layout.

    This is the main entry point for building the plot area. It iterates
    through the channels selected for display and, based on the active tab,
    calls the appropriate helper method to create the plot widget.

    Args:
        app: The main application instance.
        frequency_mhz (float, optional): The current laser frequency. Defaults to 0.0.
    """
    from core.plots.plot_builders import (
        create_spectroscopy_plot_widget,
        create_phasor_plot_widget,
    )
    app.lin_log_switches.clear()
    if not app.plots_to_show:
        app.grid_layout.addWidget(QWidget(), 0, 0)
        return

    plots_to_show = app.plots_to_show

    # In FITTING READ mode, force only first channel to be shown
    if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
        if len(plots_to_show) > 0:
            plots_to_show = [plots_to_show[0]]

    for i, channel in enumerate(plots_to_show):
        plot_widget = None
        if app.tab_selected in [s.TAB_SPECTROSCOPY, s.TAB_FITTING]:
            plot_widget = create_spectroscopy_plot_widget(app, channel, frequency_mhz)
        elif app.tab_selected == s.TAB_PHASORS:
            plot_widget = create_phasor_plot_widget(app, channel, frequency_mhz)

        if plot_widget:
            col_map = {1: 1, 2: 2, 3: 3}
            col_length = col_map.get(len(plots_to_show), 2)
            plot_widget.setStyleSheet(GUIStyles.chart_wrapper_style())
            app.grid_layout.addWidget(plot_widget, i // col_length, i % col_length)


def initialize_intensity_plot_data(app, channel):
    """
    Initializes data for an intensity plot.

    It first checks if data already exists for the given channel in the
    current tab. If so, it returns the existing data. Otherwise, it returns
    a default, empty dataset.

    Args:
        app: The main application instance.
        channel (int): The channel index for which to initialize data.

    Returns:
        tuple[np.ndarray, np.ndarray]: A tuple containing the x and y numpy arrays for the plot.
    """
    if app.tab_selected in app.intensity_lines:
        if channel in app.intensity_lines[app.tab_selected]:
            x, y = app.intensity_lines[app.tab_selected][channel].getData()
            return x, y
    x = np.arange(1)
    y = x * 0
    return x, y


def initialize_decay_curves(app, channel, frequency_mhz):
    """
    Initializes data for a decay curve plot.

    Handles different logic based on the selected tab (Spectroscopy, Fitting, etc.)
    and the display mode (Linear/Logarithmic). It can retrieve cached data or
    generate default data based on the laser frequency.

    Args:
        app: The main application instance.
        channel (int): The channel index.
        frequency_mhz (float): The current laser frequency in MHz, used to
                               calculate the time axis.

    Returns:
        tuple[np.ndarray, np.ndarray]: A tuple containing the x and y numpy arrays for the plot.
    """

    def get_default_x():
        # Use bin indices for FITTING READ mode only if data has been loaded
        if (
            app.tab_selected == s.TAB_FITTING
            and app.acquire_read_mode == "read"
            and hasattr(app, "reader_data")
            and app.reader_data.get("fitting", {})
            .get("data", {})
            .get("spectroscopy_data")
        ):
            return np.arange(256)
        # Use time values for other modes when frequency is available
        if frequency_mhz != 0.0:
            period = 1_000 / frequency_mhz
            return np.linspace(0, period, 256)
        # For SPECTROSCOPY/other modes with no frequency, return minimal array
        return np.arange(1)

    decay_curves = app.decay_curves[app.tab_selected]
    if app.tab_selected in [s.TAB_SPECTROSCOPY, s.TAB_FITTING]:
        cached_decay_values = app.cached_decay_values[app.tab_selected]
        if channel in cached_decay_values and channel in decay_curves:
            x, _ = decay_curves[channel].getData()
            y = cached_decay_values[channel]
        else:
            x = get_default_x()
            if channel not in app.lin_log_mode or app.lin_log_mode[channel] == "LIN":
                y = np.zeros(len(x))
            else:
                y = np.linspace(0, 100_000_000, len(x))
    else:
        if channel in decay_curves:
            x, y = decay_curves[channel].getData()
        else:
            x = get_default_x()
            y = np.zeros(len(x))
    return x, y
