"""
plots_controller.py
============================================================
Facade / controller that delegates all plot generation, update and clearing
operations to the dedicated sub-modules in `core/`.

Sub-module responsibilities
---------------------------
core.plots.plot_initializers  — numpy data initialization for intensity and decay plots and plots generation
core.plot_builders      — pyqtgraph widget construction for all plot types
                          (intensity section, decay curve, spectroscopy panel,
                           phasor panel); wires widgets into app state dicts
core.plots.plot_updaters      — real-time data updates during acquisition or file reading
                          (intensity scrolling, decay lin/log, phasor accumulation)
"""

from copy import deepcopy

from core.plots.plot_initializers import (
    initialize_intensity_plot_data,
    initialize_decay_curves,
    generate_plots,
)
from core.plots.plot_builders import (
    create_intensity_section,
    create_decay_curve_widget,
    create_spectroscopy_plot_widget,
    create_phasor_plot_widget,
    set_plot_y_range,
)
from core.plots.plot_updaters import (
    update_intensity_plots,
    update_spectroscopy_plots,
    update_plots,
    clear_plots,
)

import settings.settings as s
from utils.gui_styles import GUIStyles
from utils.layout_utilities import clear_layout_tree

from PyQt6.QtWidgets import QWidget


class PlotsController:
    """
    Facade controller for all plot generation, update and clearing operations.

    Every method is a thin static wrapper that delegates to the appropriate
    `core/plot_*.py` sub-module.
    """

    # ------------------------------------------------------------------
    # Initialization delegates
    # ------------------------------------------------------------------

    @staticmethod
    def generate_plots(app, frequency_mhz=0.0):
        generate_plots(app, frequency_mhz)

    @staticmethod
    def initialize_intensity_plot_data(app, channel):
        return initialize_intensity_plot_data(app, channel)

    @staticmethod
    def initialize_decay_curves(app, channel, frequency_mhz):
        return initialize_decay_curves(app, channel, frequency_mhz)

    # ------------------------------------------------------------------
    # Builder delegates
    # ------------------------------------------------------------------

    @staticmethod
    def _create_intensity_section(app, channel, for_phasor_tab=False):
        return create_intensity_section(app, channel, for_phasor_tab)

    @staticmethod
    def _create_decay_curve_widget(app, channel, frequency_mhz):
        return create_decay_curve_widget(app, channel, frequency_mhz)

    @staticmethod
    def _create_spectroscopy_plot_widget(app, channel, frequency_mhz):
        return create_spectroscopy_plot_widget(app, channel, frequency_mhz)

    @staticmethod
    def _create_phasor_plot_widget(app, channel, frequency_mhz):
        return create_phasor_plot_widget(app, channel, frequency_mhz)

    @staticmethod
    def set_plot_y_range(plot):
        set_plot_y_range(plot)

    # ------------------------------------------------------------------
    # Updater delegates
    # ------------------------------------------------------------------

    @staticmethod
    def update_intensity_plots(app, channel_index, time_ns, curve):
        update_intensity_plots(app, channel_index, time_ns, curve)

    @staticmethod
    def update_spectroscopy_plots(app, x, y, channel_index, decay_curve):
        update_spectroscopy_plots(app, x, y, channel_index, decay_curve)

    @staticmethod
    def update_plots(app, channel_index, time_ns, curve, reader_mode=False):
        update_plots(app, channel_index, time_ns, curve, reader_mode)

    @staticmethod
    def clear_plots(app, deep_clear=True):
        clear_plots(app, deep_clear)
