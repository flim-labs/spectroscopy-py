"""
phasors_controller.py
============================================================
Facade / controller that delegates all phasor plot operations to the
dedicated sub-modules in `core/phasors/`.

Sub-module responsibilities
---------------------------
core.phasors.phasors_calculations — pure math and data helpers: lifetime tau calculations
                            (tau_phi, tau_m, tau_n), mean G/S computation,
                            empty point structure initialization, file color mapping.
core.phasors.phasors_drawing      — pyqtgraph rendering: semi-circle, phasor data points
                            (with per-file coloring in read mode), lifetime tau markers,
                            density quantization images, and colorbars.
core.phasors.phasors_ui           — UI interaction: crosshair creation, mouse-move event handler,
                            coordinate display, cluster center drawing, legend generation
                            and hiding, file legend creation/removal.
                            Spectroscopy base: clear_phasors_files_legend uses setVisible(False).
"""

from core.phasors.phasors_calculations import (
    get_empty_phasors_points,
    get_color_for_file_index,
    calculate_phasors_points_mean,
    calculate_tau,
    calculate_tau_n,
)
from core.phasors.phasors_drawing import (
    draw_semi_circle,
    draw_points_in_phasors,
    draw_lifetime_points_in_phasors,
    quantize_phasors,
    generate_colorbar,
    create_hot_colormap,
    create_cool_colormap,
)
from core.phasors.phasors_ui import (
    create_phasors_files_legend,
    clear_phasors_files_legend,
    clear_phasors_file_scatters,
    clear_phasors_features,
    create_phasor_crosshair,
    generate_coords,
    generate_phasors_cluster_center,
    generate_phasors_legend,
    hide_phasors_legends,
    on_phasors_mouse_moved,
)

from utils.helpers import mhz_to_ns
import settings.settings as s


class PhasorsController:
    """
    Facade controller for all phasor plot operations.

    Every method is a thin static wrapper that delegates to the appropriate
    `core/phasors_*.py` sub-module. The initialize_phasor_feature method
    remains implemented here as it orchestrates across drawing and UI modules.
    """

    # ------------------------------------------------------------------
    # Calculation delegates
    # ------------------------------------------------------------------

    @staticmethod
    def get_empty_phasors_points():
        return get_empty_phasors_points()

    @staticmethod
    def get_color_for_file_index(index):
        return get_color_for_file_index(index)

    @staticmethod
    def calculate_phasors_points_mean(app, channel_index, harmonic):
        return calculate_phasors_points_mean(app, channel_index, harmonic)

    @staticmethod
    def calculate_tau(g, s, freq_mhz, harmonic):
        return calculate_tau(g, s, freq_mhz, harmonic)

    @staticmethod
    def calculate_tau_n(r, freq):
        return calculate_tau_n(r, freq)

    # ------------------------------------------------------------------
    # Drawing delegates
    # ------------------------------------------------------------------

    @staticmethod
    def draw_semi_circle(widget):
        draw_semi_circle(widget)

    @staticmethod
    def draw_points_in_phasors(app, channel, harmonic, phasors):
        draw_points_in_phasors(app, channel, harmonic, phasors)

    @staticmethod
    def draw_lifetime_points_in_phasors(app, channel, harmonic, laser_period_ns, frequency_mhz):
        draw_lifetime_points_in_phasors(app, channel, harmonic, laser_period_ns, frequency_mhz)

    @staticmethod
    def quantize_phasors(app, harmonic, bins=64):
        quantize_phasors(app, harmonic, bins)

    @staticmethod
    def generate_colorbar(app, channel_index, min_value, max_value):
        generate_colorbar(app, channel_index, min_value, max_value)

    @staticmethod
    def create_hot_colormap():
        return create_hot_colormap()

    @staticmethod
    def create_cool_colormap(start=0.0, end=1.0):
        return create_cool_colormap(start, end)

    # ------------------------------------------------------------------
    # UI delegates
    # ------------------------------------------------------------------

    @staticmethod
    def create_phasors_files_legend(app, channel, file_order):
        create_phasors_files_legend(app, channel, file_order)

    @staticmethod
    def clear_phasors_files_legend(app):
        clear_phasors_files_legend(app)

    @staticmethod
    def clear_phasors_file_scatters(app):
        clear_phasors_file_scatters(app)

    @staticmethod
    def clear_phasors_features(app, feature):
        clear_phasors_features(app, feature)

    @staticmethod
    def create_phasor_crosshair(app, channel_index, phasors_widget):
        create_phasor_crosshair(app, channel_index, phasors_widget)

    @staticmethod
    def generate_coords(app, channel_index):
        generate_coords(app, channel_index)

    @staticmethod
    def generate_phasors_cluster_center(app, harmonic):
        generate_phasors_cluster_center(app, harmonic)

    @staticmethod
    def generate_phasors_legend(app, harmonic):
        generate_phasors_legend(app, harmonic)

    @staticmethod
    def hide_phasors_legends(app):
        hide_phasors_legends(app)

    @staticmethod
    def on_phasors_mouse_moved(app, event, channel_index):
        on_phasors_mouse_moved(app, event, channel_index)

    # ------------------------------------------------------------------
    # Orchestration (coordinates drawing + UI modules)
    # ------------------------------------------------------------------

    @staticmethod
    def clear_phasors_points(app):
        """
        Clears all raw data points from the phasor plots.

        Args:
            app: The main application instance.
        """
        for ch in app.plots_to_show:
            if ch in app.phasors_charts:
                app.phasors_charts[ch].setData([], [])

    @staticmethod
    def initialize_phasor_feature(app):
        """
        Initializes all features for the phasor plots.

        This includes setting the cursor, drawing crosshairs, and adding the
        reference lifetime points.

        Args:
            app: The main application instance.
        """
        from core.controls_controller import ControlsController

        frequency_mhz = ControlsController.get_current_frequency_mhz(app)
        if frequency_mhz != 0:
            laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
            for _, channel in enumerate(app.plots_to_show):
                if app.acquire_read_mode == "acquire":
                    if channel in app.phasors_widgets:
                        from PyQt6.QtCore import Qt
                        app.phasors_widgets[channel].setCursor(Qt.CursorShape.BlankCursor)
                        generate_coords(app, channel)
                        create_phasor_crosshair(app, channel, app.phasors_widgets[channel])
                draw_lifetime_points_in_phasors(
                    app,
                    channel,
                    app.control_inputs[s.HARMONIC_SELECTOR].currentIndex() + 1,
                    laser_period_ns,
                    frequency_mhz,
                )